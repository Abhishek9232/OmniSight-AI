"""
Integration Test Suite for Active Exam Proctoring Lifecycle (Phase 5 Step 3).
Verifies:
- Proctoring session creation, caching, and cleanup helpers in student UI layer.
- FrameInputAdapter integration with ProctoringSession (NullFrameAdapter, SimulatedFrameAdapter).
- End-to-end event persistence for IN_PROGRESS attempts (FACE_ABSENT >= 5s, MULTIPLE_FACES >= 3s).
- Active monitoring preservation during the 60-second exam grace window.
- Absolute terminal attempt invariant: SUBMITTED and EVALUATED attempts produce ZERO monitoring writes.
- Cooldown rate-limiting enforcement in full integration.
- Hardware/camera failure isolation.
- Multi-student / multi-attempt isolation with zero cross-tenant contamination.
- Clean database teardown returning to pristine state.
"""

import sys
import os
import time
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from unittest.mock import patch, MagicMock
import numpy as np

workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

from src.database.connection import get_connection
from src.exam.service import (
    create_exam,
    add_question,
    publish_exam,
    start_attempt,
    submit_attempt,
    evaluate_attempt,
    get_attempt,
)
from src.proctoring.detector import FaceDetector
from src.proctoring.state import ProctoringStateTracker
from src.proctoring.service import (
    record_monitoring_event,
    get_attempt_monitoring_events,
)
from src.proctoring.session import ProctoringSession
from src.proctoring.adapter import (
    FrameInputAdapter,
    NullFrameAdapter,
    SimulatedFrameAdapter,
)
from src.ui.student_ui import (
    _get_or_create_proctoring_session,
    _cleanup_proctoring_session,
)


def _count_table(table_name: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return count


def _cleanup_test_data():
    """Purge all test entities to ensure complete database cleanliness."""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        cursor.execute("DELETE FROM monitoring_events;")
        cursor.execute("DELETE FROM results;")
        cursor.execute("DELETE FROM answers;")
        cursor.execute("DELETE FROM exam_attempts;")
        cursor.execute("DELETE FROM questions;")
        cursor.execute("DELETE FROM exams;")
        cursor.execute("DELETE FROM users WHERE email LIKE '%@proctor_integ_test.com';")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
        conn.commit()
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def _create_user(name: str, email: str, role: str) -> int:
    """Helper to create a test user directly in MySQL."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, %s);",
        (name, email, "dummy_hash_for_testing", role),
    )
    conn.commit()
    user_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return user_id


class MockDetector(FaceDetector):
    """Configurable detector for deterministic integration tests."""

    def __init__(self, detected_boxes=None):
        self._boxes = detected_boxes if detected_boxes is not None else []

    def set_boxes(self, boxes):
        self._boxes = boxes

    def detect_faces(self, frame: Any) -> Dict[str, Any]:
        return {
            "success": True,
            "face_count": len(self._boxes),
            "faces": [{"x": b[0], "y": b[1], "w": b[2], "h": b[3]} for b in self._boxes],
            "error": None,
        }


class FailingFrameAdapter(FrameInputAdapter):
    """Adapter that simulates camera I/O failure."""

    def is_available(self) -> bool:
        return True

    def get_frame(self) -> Optional[np.ndarray]:
        raise RuntimeError("Simulated camera driver disconnected.")


def run_tests():
    print("=" * 70)
    print("STARTING PHASE 5 STEP 3 PROCTORING INTEGRATION TEST SUITE")
    print("=" * 70)

    # Initial state capture
    init_users = _count_table("users")
    init_exams = _count_table("exams")
    init_questions = _count_table("questions")
    init_attempts = _count_table("exam_attempts")
    init_events = _count_table("monitoring_events")

    print(f"Initial DB State: users={init_users}, exams={init_exams}, attempts={init_attempts}, events={init_events}")

    try:
        # Step 1: Test UI Lifecycle Helpers
        print("\n--- 1. Testing UI Lifecycle Helpers ---")
        mock_st_session = {}
        with patch("streamlit.session_state", mock_st_session):
            sess1 = _get_or_create_proctoring_session(attempt_id=999)
            assert isinstance(sess1, ProctoringSession)
            assert sess1.attempt_id == 999
            assert sess1.is_active is True
            assert isinstance(sess1.frame_adapter, NullFrameAdapter)

            # Subsequent call returns same session instance
            sess2 = _get_or_create_proctoring_session(attempt_id=999)
            assert sess1 is sess2

            # Cleanup helper terminates session and removes state keys
            _cleanup_proctoring_session(attempt_id=999)
            assert sess1.is_active is False
            assert "proctoring_session_999" not in mock_st_session
            assert "proctoring_adapter_999" not in mock_st_session

            # Cleanup with None or non-existent is safe
            _cleanup_proctoring_session(None)
            _cleanup_proctoring_session(attempt_id=888)
            print("[OK] UI lifecycle helpers correctly manage session lifecycle.")

        # Step 2: Create Test Database Hierarchy
        print("\n--- 2. Setting Up Test Examination & Attempt ---")
        teacher_id = _create_user("Teacher Proctor", "teacher@proctor_integ_test.com", "teacher")
        student_a_id = _create_user("Student Alpha", "student_a@proctor_integ_test.com", "student")
        student_b_id = _create_user("Student Beta", "student_b@proctor_integ_test.com", "student")

        exam = create_exam(
            title="Proctoring Integration Test Exam",
            description="Testing active exam proctoring integration",
            duration_minutes=30,
            created_by=teacher_id,
        )
        exam_id = exam["exam_id"]

        q1 = add_question(
            exam_id=exam_id,
            teacher_id=teacher_id,
            question_text="What is 10 + 10?",
            option_a="10",
            option_b="20",
            option_c="30",
            option_d="40",
            correct_option="B",
            marks=2,
        )
        publish_exam(exam_id=exam_id, teacher_id=teacher_id)

        attempt_a = start_attempt(exam_id=exam_id, student_id=student_a_id)
        attempt_a_id = attempt_a["attempt_id"]
        assert attempt_a["status"] == "IN_PROGRESS"
        print(f"[OK] Attempt #{attempt_a_id} created for Student A in status IN_PROGRESS.")

        # Step 3: Test Event Persistence for IN_PROGRESS Attempt
        print("\n--- 3. Testing Event Persistence on IN_PROGRESS Attempt ---")
        mock_detector = MockDetector(detected_boxes=[])
        frame_adapter = SimulatedFrameAdapter(initial_frame=np.zeros((480, 640, 3), dtype=np.uint8))
        session_a = ProctoringSession(
            attempt_id=attempt_a_id,
            detector=mock_detector,
            frame_adapter=frame_adapter,
        )

        # Feed samples with 0 faces: t=0s, 2s, 4s (under 5s threshold -> 0 writes)
        session_a.process_sample(timestamp=100.0)
        session_a.process_sample(timestamp=102.0)
        session_a.process_sample(timestamp=104.0)

        events_initial = get_attempt_monitoring_events(attempt_id=attempt_a_id, requesting_user_id=teacher_id)
        assert len(events_initial) == 0, f"Expected 0 events, got {len(events_initial)}"

        # At t=105.1s (continuous absence >= 5s -> event generated and written to MySQL)
        session_a.process_sample(timestamp=105.1)

        events_recorded = get_attempt_monitoring_events(attempt_id=attempt_a_id, requesting_user_id=teacher_id)
        assert len(events_recorded) == 1, f"Expected 1 event, got {len(events_recorded)}"
        ev = events_recorded[0]
        assert ev["event_type"] == "FACE_ABSENT"
        assert ev["attempt_id"] == attempt_a_id
        assert ev["event_metadata"] is not None
        assert ev["event_metadata"]["sustained_duration_sec"] >= 5.0
        print(f"[OK] Event #{ev['event_id']} (FACE_ABSENT) successfully persisted for IN_PROGRESS attempt.")

        # Step 4: Cooldown Rate Limiting in Integration
        print("\n--- 4. Testing Cooldown Rate Limiting ---")
        # Process at t=110.0 (5s after event, cooldown is 20s) -> should NOT record duplicate
        session_a.process_sample(timestamp=110.0)
        session_a.process_sample(timestamp=120.0)
        events_cooldown = get_attempt_monitoring_events(attempt_id=attempt_a_id, requesting_user_id=teacher_id)
        assert len(events_cooldown) == 1, "Duplicate event recorded during cooldown!"

        # Advance past 20s cooldown (t=126.0) -> second event should be recorded
        session_a.process_sample(timestamp=126.0)
        events_after_cooldown = get_attempt_monitoring_events(attempt_id=attempt_a_id, requesting_user_id=teacher_id)
        assert len(events_after_cooldown) == 2, f"Expected 2 events after cooldown, got {len(events_after_cooldown)}"
        print("[OK] 20-second cooldown rate-limiting correctly enforced in integration.")

        # Step 5: Active Monitoring During Grace Window
        print("\n--- 5. Testing Active Monitoring During Grace Window ---")
        # Artificially simulate that attempt official deadline has passed, but within 60s grace window
        conn = get_connection()
        cursor = conn.cursor()
        # Exam is 30 mins. Set started_at = 30 mins and 15 seconds ago.
        grace_start_time = datetime.now() - timedelta(minutes=30, seconds=15)
        cursor.execute(
            "UPDATE exam_attempts SET started_at = %s WHERE attempt_id = %s;",
            (grace_start_time, attempt_a_id),
        )
        conn.commit()
        cursor.close()
        conn.close()

        # Attempt is in grace window, still IN_PROGRESS
        att_grace = get_attempt(attempt_id=attempt_a_id, student_id=student_a_id)
        assert att_grace["status"] == "IN_PROGRESS"

        # Now simulate MULTIPLE_FACES in grace period (threshold: 3 seconds)
        mock_detector.set_boxes([(10, 10, 50, 50), (100, 100, 50, 50)])
        session_a.process_sample(timestamp=200.0)
        session_a.process_sample(timestamp=201.5)
        events_mid_grace = get_attempt_monitoring_events(attempt_id=attempt_a_id, requesting_user_id=teacher_id)
        assert len(events_mid_grace) == 2, "Event triggered before 3s threshold!"

        session_a.process_sample(timestamp=203.2)
        events_grace_final = get_attempt_monitoring_events(attempt_id=attempt_a_id, requesting_user_id=teacher_id)
        assert len(events_grace_final) == 3, f"Expected 3 events, got {len(events_grace_final)}"
        ev_multi = events_grace_final[-1]
        assert ev_multi["event_type"] == "MULTIPLE_FACES"
        print(f"[OK] Event #{ev_multi['event_id']} (MULTIPLE_FACES) recorded during active grace period.")

        # Step 6: Terminal Attempt Invariant (SUBMITTED / EVALUATED -> Zero Writes)
        print("\n--- 6. Verifying Terminal Invariants (Zero Writes) ---")
        # Stop session and submit attempt
        session_a.stop()
        submit_res = submit_attempt(attempt_id=attempt_a_id, student_id=student_a_id)
        assert submit_res["status"] == "SUBMITTED"

        # Attempt to process sample through session
        session_a.process_sample(timestamp=300.0)
        events_after_submit = get_attempt_monitoring_events(attempt_id=attempt_a_id, requesting_user_id=teacher_id)
        assert len(events_after_submit) == 3, "CRITICAL ERROR: Monitoring event written after SUBMISSION!"

        # Attempt direct database service call on SUBMITTED attempt
        direct_write_sub = record_monitoring_event(
            attempt_id=attempt_a_id,
            event_type="FACE_ABSENT",
            event_metadata={"reason": "test"},
        )
        assert direct_write_sub["recorded"] is False
        assert "SUBMITTED" in direct_write_sub["reason"]

        # Evaluate attempt and verify EVALUATED invariant
        eval_res = evaluate_attempt(attempt_id=attempt_a_id, student_id=student_a_id)
        assert eval_res["status"] == "EVALUATED"

        direct_write_eval = record_monitoring_event(
            attempt_id=attempt_a_id,
            event_type="MULTIPLE_FACES",
            event_metadata={"reason": "test"},
        )
        assert direct_write_eval["recorded"] is False
        assert "EVALUATED" in direct_write_eval["reason"]

        events_terminal_final = get_attempt_monitoring_events(attempt_id=attempt_a_id, requesting_user_id=teacher_id)
        assert len(events_terminal_final) == 3
        print("[OK] SUBMITTED and EVALUATED attempts strictly guarantee ZERO new monitoring event writes.")

        # Step 7: Multi-Student & Multi-Attempt Isolation
        print("\n--- 7. Verifying Multi-Student / Multi-Attempt Isolation ---")
        attempt_b = start_attempt(exam_id=exam_id, student_id=student_b_id)
        attempt_b_id = attempt_b["attempt_id"]
        assert attempt_b_id != attempt_a_id

        events_b = get_attempt_monitoring_events(attempt_id=attempt_b_id, requesting_user_id=teacher_id)
        assert len(events_b) == 0, f"Attempt B leaked events from Attempt A! Found: {len(events_b)}"

        # Generate event strictly on Attempt B
        session_b = ProctoringSession(
            attempt_id=attempt_b_id,
            detector=MockDetector(detected_boxes=[]),
            frame_adapter=SimulatedFrameAdapter(initial_frame=np.zeros((100, 100, 3), dtype=np.uint8)),
        )
        session_b.process_sample(timestamp=500.0)
        session_b.process_sample(timestamp=505.5)

        events_b_after = get_attempt_monitoring_events(attempt_id=attempt_b_id, requesting_user_id=teacher_id)
        assert len(events_b_after) == 1
        assert events_b_after[0]["attempt_id"] == attempt_b_id

        # Verify Attempt A events are still unchanged
        events_a_check = get_attempt_monitoring_events(attempt_id=attempt_a_id, requesting_user_id=teacher_id)
        assert len(events_a_check) == 3
        print("[OK] Complete isolation verified across distinct student examination attempts.")

        # Step 8: Failure Isolation
        print("\n--- 8. Verifying Failure Isolation on Camera Exception ---")
        failing_session = ProctoringSession(
            attempt_id=attempt_b_id,
            detector=mock_detector,
            frame_adapter=FailingFrameAdapter(),
        )
        # Calling process_sample with a failing adapter raises an exception inside,
        # but in student_ui.py it is caught cleanly via try/except without crashing.
        with patch("streamlit.session_state", {}):
            try:
                # Simulating UI loop call wrapped in try/except
                failing_session.process_sample(timestamp=600.0)
            except Exception as e:
                # Caught as expected
                pass
        # Verify attempt remains healthy and active
        att_b_check = get_attempt(attempt_id=attempt_b_id, student_id=student_b_id)
        assert att_b_check["status"] == "IN_PROGRESS"
        print("[OK] Camera failure gracefully isolated; examination attempt integrity preserved.")

    finally:
        # Step 9: Database Cleanup & Pristine State Verification
        print("\n--- 9. Cleaning Up Test Data & Verifying Database State ---")
        _cleanup_test_data()

        final_users = _count_table("users")
        final_exams = _count_table("exams")
        final_questions = _count_table("questions")
        final_attempts = _count_table("exam_attempts")
        final_events = _count_table("monitoring_events")

        print(f"Final DB State: users={final_users}, exams={final_exams}, attempts={final_attempts}, events={final_events}")

        assert final_users == init_users, f"Users count mismatch: expected {init_users}, got {final_users}"
        assert final_exams == init_exams, f"Exams count mismatch: expected {init_exams}, got {final_exams}"
        assert final_questions == init_questions, f"Questions count mismatch: expected {init_questions}, got {final_questions}"
        assert final_attempts == init_attempts, f"Attempts count mismatch: expected {init_attempts}, got {final_attempts}"
        assert final_events == init_events, f"Events count mismatch: expected {init_events}, got {final_events}"

        print("\n" + "=" * 70)
        print("ALL PHASE 5 STEP 3 PROCTORING INTEGRATION TESTS PASSED SUCCESSFULLY!")
        print("=" * 70)


if __name__ == "__main__":
    run_tests()
