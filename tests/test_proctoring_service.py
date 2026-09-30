"""
Integration Test Suite for Proctoring Service & Session (Phase 5 Step 2).
Verifies:
- Transaction-safe atomic attempt status validation.
- Critical Invariant: Only IN_PROGRESS attempts accept monitoring event writes.
- Critical Invariant: SUBMITTED and EVALUATED attempts produce ZERO database writes.
- Role-based access control (RBAC) on proctoring telemetry queries.
- Failure isolation and error suppression.
- Clean database teardown returning to pristine state.
"""

import sys
import os
import json
from datetime import datetime
import numpy as np

workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

from src.database.connection import get_connection
from src.proctoring.service import (
    record_monitoring_event,
    get_attempt_monitoring_events,
    get_monitoring_event_summary,
)
from src.proctoring.session import ProctoringSession
from src.exam.service import (
    create_exam,
    add_question,
    publish_exam,
    start_attempt,
)


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
        cursor.execute("DELETE FROM users WHERE email LIKE '%@proctor_test.com';")
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
        (name, email, "dummy_hash", role),
    )
    conn.commit()
    user_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return user_id


def test_proctoring_service_and_session():
    """Full integration test covering proctoring service, session, and terminal invariants."""
    print("=" * 70)
    print("STARTING PROCTORING SERVICE & SESSION INTEGRATION TESTS")
    print("=" * 70)

    _cleanup_test_data()

    # 1. Provision test accounts
    teacher_id = _create_user("Proctor Teacher", "teacher@proctor_test.com", "teacher")
    other_teacher_id = _create_user("Other Teacher", "other_teacher@proctor_test.com", "teacher")
    student_id = _create_user("Proctor Student", "student@proctor_test.com", "student")
    other_student_id = _create_user("Other Student", "other_student@proctor_test.com", "student")
    admin_id = _create_user("Proctor Admin", "admin@proctor_test.com", "admin")

    # 2. Provision published exam with 1 question
    exam = create_exam("Proctoring Integrity Test Exam", "Exam for proctoring test", 30, teacher_id)
    exam_id = exam["exam_id"]
    add_question(exam_id, teacher_id, "Sample Q1", "A", "B", "C", "D", "A", 5)
    publish_exam(exam_id, teacher_id)

    # 3. Start attempt (status: IN_PROGRESS)
    attempt = start_attempt(exam_id, student_id)
    attempt_id = attempt["attempt_id"]
    assert attempt["status"] == "IN_PROGRESS"
    print(f"[OK] Test Attempt #{attempt_id} initiated in status IN_PROGRESS.")

    # -------------------------------------------------------------
    # Test 1: Record monitoring event on active IN_PROGRESS attempt
    # -------------------------------------------------------------
    meta1 = {
        "sustained_duration_sec": 5.12,
        "threshold_sec": 5.0,
        "cooldown_applied_sec": 20.0,
        "face_count": 0,
    }
    res1 = record_monitoring_event(attempt_id, "FACE_ABSENT", meta1)
    assert res1["success"] is True
    assert res1["recorded"] is True
    assert isinstance(res1["event_id"], int)
    event1_id = res1["event_id"]

    # Verify row directly in MySQL
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM monitoring_events WHERE event_id = %s;", (event1_id,))
    row1 = cursor.fetchone()
    assert row1 is not None
    assert row1["attempt_id"] == attempt_id
    assert row1["event_type"] == "FACE_ABSENT"
    parsed_meta = json.loads(row1["event_metadata"]) if isinstance(row1["event_metadata"], str) else row1["event_metadata"]
    assert parsed_meta["sustained_duration_sec"] == 5.12
    cursor.close()
    conn.close()
    print("[OK] Test 1 PASSED: Successfully persisted monitoring event for IN_PROGRESS attempt.")

    # -------------------------------------------------------------
    # Test 2: Invariant Check — SUBMITTED attempt produces ZERO writes
    # -------------------------------------------------------------
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE exam_attempts SET status = 'SUBMITTED', submitted_at = NOW() WHERE attempt_id = %s;", (attempt_id,))
    conn.commit()
    cursor.close()
    conn.close()

    meta2 = {"sustained_duration_sec": 6.0, "face_count": 0}
    res2 = record_monitoring_event(attempt_id, "FACE_ABSENT", meta2)
    assert res2["success"] is True
    assert res2["recorded"] is False
    assert "non-active status 'SUBMITTED'" in res2["reason"]

    # Verify zero new records in database
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM monitoring_events WHERE attempt_id = %s;", (attempt_id,))
    total_events_submitted = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    assert total_events_submitted == 1, f"Expected exactly 1 event, got {total_events_submitted}"
    print("[OK] Test 2 PASSED: SUBMITTED attempt strictly rejected event write (0 writes).")

    # -------------------------------------------------------------
    # Test 3: Invariant Check — EVALUATED attempt produces ZERO writes
    # -------------------------------------------------------------
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE exam_attempts SET status = 'EVALUATED' WHERE attempt_id = %s;", (attempt_id,))
    conn.commit()
    cursor.close()
    conn.close()

    meta3 = {"sustained_duration_sec": 3.5, "face_count": 2}
    res3 = record_monitoring_event(attempt_id, "MULTIPLE_FACES", meta3)
    assert res3["success"] is True
    assert res3["recorded"] is False
    assert "non-active status 'EVALUATED'" in res3["reason"]

    # Verify still exactly 1 event
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM monitoring_events WHERE attempt_id = %s;", (attempt_id,))
    total_events_evaluated = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    assert total_events_evaluated == 1
    print("[OK] Test 3 PASSED: EVALUATED attempt strictly rejected event write (0 writes).")

    # -------------------------------------------------------------
    # Test 4: Parameter validation and non-existent attempt handling
    # -------------------------------------------------------------
    res_bad_id = record_monitoring_event(999999, "FACE_ABSENT")
    assert res_bad_id["success"] is False
    assert res_bad_id["recorded"] is False
    assert "does not exist" in res_bad_id["error"]

    res_invalid_type = record_monitoring_event(attempt_id, "")
    assert res_invalid_type["success"] is False
    assert res_invalid_type["recorded"] is False
    print("[OK] Test 4 PASSED: Invalid inputs and non-existent attempts handled safely.")

    # -------------------------------------------------------------
    # Test 5: RBAC on get_attempt_monitoring_events & summary
    # -------------------------------------------------------------
    # 5a: Student views own attempt
    events_student = get_attempt_monitoring_events(attempt_id, student_id)
    assert len(events_student) == 1
    assert events_student[0]["event_type"] == "FACE_ABSENT"

    # 5b: Other student blocked
    try:
        get_attempt_monitoring_events(attempt_id, other_student_id)
        assert False, "Should have raised PermissionError for other student"
    except PermissionError as e:
        assert "Unauthorized" in str(e)

    # 5c: Owning teacher views attempt
    events_teacher = get_attempt_monitoring_events(attempt_id, teacher_id)
    assert len(events_teacher) == 1

    # 5d: Non-owning teacher blocked
    try:
        get_attempt_monitoring_events(attempt_id, other_teacher_id)
        assert False, "Should have raised PermissionError for non-owning teacher"
    except PermissionError as e:
        assert "Unauthorized" in str(e)

    # 5e: Admin can view any attempt
    events_admin = get_attempt_monitoring_events(attempt_id, admin_id)
    assert len(events_admin) == 1

    # 5f: Summary aggregation
    summary = get_monitoring_event_summary(attempt_id, student_id)
    assert summary["attempt_id"] == attempt_id
    assert summary["total_events"] == 1
    assert summary["absence_events"] == 1
    assert summary["multiple_faces_events"] == 0
    print("[OK] Test 5 PASSED: Strict RBAC verified across student, teacher, and admin callers.")

    # -------------------------------------------------------------
    # Test 6: ProctoringSession End-to-End Coordination & Isolation
    # -------------------------------------------------------------
    # Create another fresh attempt for session testing
    exam2 = create_exam("Proctoring Session Test Exam", "Exam 2", 20, teacher_id)
    exam2_id = exam2["exam_id"]
    add_question(exam2_id, teacher_id, "Sample Q", "A", "B", "C", "D", "A", 5)
    publish_exam(exam2_id, teacher_id)
    attempt2 = start_attempt(exam2_id, student_id)
    attempt2_id = attempt2["attempt_id"]

    session = ProctoringSession(attempt_id=attempt2_id)
    assert session.is_active is True

    # Feed solid black frame (0 faces) at t=0.0 and t=5.0
    black_frame = np.zeros((240, 320, 3), dtype=np.uint8)

    out1 = session.process_frame(black_frame, timestamp=0.0)
    assert out1["success"] is True
    assert out1["face_count"] == 0
    assert out1["event_emitted"] is False

    # T = 5.0s: Threshold met -> event emitted and persisted!
    out2 = session.process_frame(black_frame, timestamp=5.0)
    assert out2["success"] is True
    assert out2["event_emitted"] is True
    assert out2["event"]["event_type"] == "FACE_ABSENT"
    assert out2["persistence_result"]["recorded"] is True

    # Failure isolation: pass None frame
    out_err = session.process_frame(None)
    assert out_err["success"] is False
    assert out_err["event_emitted"] is False
    assert "Input frame is None" in out_err["error"]

    # Close session
    session.close()
    assert session.is_active is False
    out_closed = session.process_frame(black_frame)
    assert out_closed["success"] is False
    assert "closed" in out_closed["error"].lower()

    print("[OK] Test 6 PASSED: ProctoringSession end-to-end integration and failure isolation verified.")

    # -------------------------------------------------------------
    # 7. Clean up test data and verify pristine database
    # -------------------------------------------------------------
    _cleanup_test_data()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users;")
    user_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM exams;")
    exam_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM questions;")
    question_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM exam_attempts;")
    attempt_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM answers;")
    answer_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM results;")
    result_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM monitoring_events;")
    monitoring_count = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    assert user_count == 1, f"Expected 1 user, found {user_count}"
    assert exam_count == 0, f"Expected 0 exams, found {exam_count}"
    assert question_count == 0, f"Expected 0 questions, found {question_count}"
    assert attempt_count == 0, f"Expected 0 attempts, found {attempt_count}"
    assert answer_count == 0, f"Expected 0 answers, found {answer_count}"
    assert result_count == 0, f"Expected 0 results, found {result_count}"
    assert monitoring_count == 0, f"Expected 0 monitoring_events, found {monitoring_count}"

    print("[OK] Step 7 PASSED: Database restored to pristine state.")
    print("=" * 70)
    print("ALL PROCTORING SERVICE & SESSION INTEGRATION TESTS PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    test_proctoring_service_and_session()
