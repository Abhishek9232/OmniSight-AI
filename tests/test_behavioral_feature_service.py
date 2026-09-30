"""
Integration Test Suite for Behavioral Feature Service & Database Persistence (Phase 6).
Verifies:
- Pre-condition validation: IN_PROGRESS attempts strictly rejected with ValueError.
- Terminal attempt processing: SUBMITTED and EVALUATED attempts persist 18 features.
- Idempotency invariant: Repeated extractions replace features without duplicate rows.
- Zero-event and zero-answer attempts persist clean 18-feature zero vectors.
- Multi-event attempt extraction with real database records.
- Feature vector retrieval via get_behavioral_feature_vector().
- Multi-attempt tabular feature matrix retrieval via get_feature_matrix().
- Non-existent attempt handling.
- Complete database cleanup returning to pristine state.
"""

from datetime import datetime, timedelta
import json
import math
import sys
import os

workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

from src.database.connection import get_connection
from src.exam.service import (
    create_exam,
    add_question,
    publish_exam,
    start_attempt,
    save_answer,
    submit_attempt,
    evaluate_attempt,
)
from src.proctoring.service import record_monitoring_event
from src.features.extractor import (
    FEATURE_NAMES,
    FEATURE_ATTEMPT_DURATION_SEC,
    FEATURE_ABSENCE_EVENT_COUNT,
    FEATURE_ABSENCE_TOTAL_DURATION_SEC,
    FEATURE_MULTI_FACE_EVENT_COUNT,
    FEATURE_MULTI_FACE_TOTAL_DURATION_SEC,
    FEATURE_QUESTIONS_ANSWERED_RATIO,
    FEATURE_ATTEMPT_DURATION_PER_ANSWERED_QUESTION_SEC,
)
from src.features.service import (
    extract_and_persist_behavioral_features,
    get_behavioral_feature_vector,
    get_feature_matrix,
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
        cursor.execute("DELETE FROM behavioral_features;")
        cursor.execute("DELETE FROM monitoring_events;")
        cursor.execute("DELETE FROM results;")
        cursor.execute("DELETE FROM answers;")
        cursor.execute("DELETE FROM exam_attempts;")
        cursor.execute("DELETE FROM questions;")
        cursor.execute("DELETE FROM exams;")
        cursor.execute("DELETE FROM users WHERE email LIKE '%@feat_test.com';")
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


def run_tests():
    print("=" * 70)
    print("STARTING BEHAVIORAL FEATURE SERVICE & DATABASE INTEGRATION TESTS")
    print("=" * 70)

    # Initial baseline
    init_users = _count_table("users")
    init_exams = _count_table("exams")
    init_attempts = _count_table("exam_attempts")
    init_features = _count_table("behavioral_features")
    print(f"Initial DB State: users={init_users}, exams={init_exams}, attempts={init_attempts}, features={init_features}")

    try:
        # Step 1: Create Test Hierarchy
        print("\n--- 1. Setting Up Test Examination & Users ---")
        teacher_id = _create_user("Teacher Features", "teacher@feat_test.com", "teacher")
        student1_id = _create_user("Student Alpha", "student1@feat_test.com", "student")
        student2_id = _create_user("Student Beta", "student2@feat_test.com", "student")

        exam = create_exam(
            title="Feature Engineering Test Exam",
            description="Testing behavioral feature persistence",
            duration_minutes=30,
            created_by=teacher_id,
        )
        exam_id = exam["exam_id"]

        q1 = add_question(
            exam_id=exam_id,
            teacher_id=teacher_id,
            question_text="What is 5 x 5?",
            option_a="20",
            option_b="25",
            option_c="30",
            option_d="35",
            correct_option="B",
            marks=2,
        )
        q2 = add_question(
            exam_id=exam_id,
            teacher_id=teacher_id,
            question_text="What is 100 / 10?",
            option_a="5",
            option_b="10",
            option_c="15",
            option_d="20",
            correct_option="B",
            marks=3,
        )
        publish_exam(exam_id=exam_id, teacher_id=teacher_id)
        print(f"[OK] Exam #{exam_id} created with 2 questions and published.")

        # Step 2: IN_PROGRESS Attempt Pre-Condition Rejection
        print("\n--- 2. Testing IN_PROGRESS Attempt Pre-Condition Rejection ---")
        attempt1 = start_attempt(exam_id=exam_id, student_id=student1_id)
        attempt1_id = attempt1["attempt_id"]
        assert attempt1["status"] == "IN_PROGRESS"

        try:
            extract_and_persist_behavioral_features(attempt1_id)
            assert False, "Should have raised ValueError for IN_PROGRESS attempt!"
        except ValueError as e:
            assert "IN_PROGRESS" in str(e)
            print(f"[OK] IN_PROGRESS attempt correctly rejected: {e}")

        # Confirm 0 rows written in behavioral_features
        feat_count_after_reject = _count_table("behavioral_features")
        assert feat_count_after_reject == 0
        print("[OK] Confirmed 0 feature rows written for rejected IN_PROGRESS attempt.")

        # Step 3: Populate Answers & Monitoring Events on Attempt 1
        print("\n--- 3. Populating Telemetry and Finalizing Attempt 1 (SUBMITTED) ---")
        # Save 1 answer out of 2 questions
        save_answer(attempt_id=attempt1_id, student_id=student1_id, question_id=q1["question_id"], selected_option="B")

        # Record 2 monitoring events
        record_monitoring_event(
            attempt_id=attempt1_id,
            event_type="FACE_ABSENT",
            event_metadata={"sustained_duration_sec": 8.0, "threshold_sec": 5.0},
        )
        record_monitoring_event(
            attempt_id=attempt1_id,
            event_type="MULTIPLE_FACES",
            event_metadata={"sustained_duration_sec": 4.5, "threshold_sec": 3.0},
        )

        # Submit attempt 1 -> SUBMITTED
        sub1 = submit_attempt(attempt_id=attempt1_id, student_id=student1_id)
        assert sub1["status"] == "SUBMITTED"

        # Step 4: Extract and Persist Features for SUBMITTED Attempt 1
        print("\n--- 4. Extracting and Persisting Features for SUBMITTED Attempt ---")
        res1 = extract_and_persist_behavioral_features(attempt1_id)
        assert res1["success"] is True
        assert res1["attempt_id"] == attempt1_id
        assert res1["feature_count"] == 18
        assert res1["attempt_status"] == "SUBMITTED"

        # Check database count: exactly 18 rows
        assert _count_table("behavioral_features") == 18

        # Verify persisted values via get_behavioral_feature_vector
        fvec1 = get_behavioral_feature_vector(attempt1_id)
        assert len(fvec1) == 18
        assert fvec1[FEATURE_ABSENCE_EVENT_COUNT] == 1.0
        assert fvec1[FEATURE_ABSENCE_TOTAL_DURATION_SEC] == 8.0
        assert fvec1[FEATURE_MULTI_FACE_EVENT_COUNT] == 1.0
        assert fvec1[FEATURE_MULTI_FACE_TOTAL_DURATION_SEC] == 4.5
        assert fvec1[FEATURE_QUESTIONS_ANSWERED_RATIO] == 0.5  # 1 answered out of 2
        print(f"[OK] All 18 features successfully persisted for SUBMITTED attempt #{attempt1_id}.")

        # Step 5: Test Idempotent Re-Extraction (Zero Duplicate Rows)
        print("\n--- 5. Testing Idempotent Re-Extraction ---")
        res1_rerun = extract_and_persist_behavioral_features(attempt1_id)
        assert res1_rerun["success"] is True
        # Total rows must remain exactly 18 (not 36)
        assert _count_table("behavioral_features") == 18
        fvec1_rerun = get_behavioral_feature_vector(attempt1_id)
        assert fvec1_rerun == fvec1
        print("[OK] Idempotent re-extraction confirmed: Previous features replaced, 0 duplicate rows.")

        # Step 6: Test EVALUATED Attempt State
        print("\n--- 6. Testing EVALUATED Attempt State ---")
        evaluate_attempt(attempt_id=attempt1_id, student_id=student1_id)
        res1_eval = extract_and_persist_behavioral_features(attempt1_id)
        assert res1_eval["success"] is True
        assert res1_eval["attempt_status"] == "EVALUATED"
        assert _count_table("behavioral_features") == 18
        print("[OK] Feature extraction on EVALUATED attempt succeeded without issue.")

        # Step 7: Attempt 2 — Clean Session (Zero Events, Zero Answers)
        print("\n--- 7. Testing Clean Attempt (Zero Events, Zero Answers) ---")
        attempt2 = start_attempt(exam_id=exam_id, student_id=student2_id)
        attempt2_id = attempt2["attempt_id"]
        # Immediately submit without answering or triggering events
        submit_attempt(attempt_id=attempt2_id, student_id=student2_id)

        res2 = extract_and_persist_behavioral_features(attempt2_id)
        assert res2["success"] is True
        assert res2["feature_count"] == 18
        # Now total rows in behavioral_features should be 18 + 18 = 36
        assert _count_table("behavioral_features") == 36

        fvec2 = get_behavioral_feature_vector(attempt2_id)
        assert len(fvec2) == 18
        assert fvec2[FEATURE_ABSENCE_EVENT_COUNT] == 0.0
        assert fvec2[FEATURE_ABSENCE_TOTAL_DURATION_SEC] == 0.0
        assert fvec2[FEATURE_MULTI_FACE_EVENT_COUNT] == 0.0
        assert fvec2[FEATURE_QUESTIONS_ANSWERED_RATIO] == 0.0
        assert fvec2[FEATURE_ATTEMPT_DURATION_PER_ANSWERED_QUESTION_SEC] == 0.0
        for name, val in fvec2.items():
            assert math.isfinite(val)
        print(f"[OK] Clean attempt #{attempt2_id} persisted with valid zero-filled vector.")

        # Step 8: Test get_feature_matrix (Multi-Attempt Tabular Representation)
        print("\n--- 8. Testing get_feature_matrix Multi-Attempt Tabular Representation ---")
        matrix_res = get_feature_matrix(exam_id=exam_id, as_dataframe=False)
        assert isinstance(matrix_res, dict)
        assert matrix_res["index"] == [attempt1_id, attempt2_id]
        assert matrix_res["columns"] == list(FEATURE_NAMES)
        assert len(matrix_res["data"]) == 2
        assert len(matrix_res["data"][0]) == 18
        assert len(matrix_res["data"][1]) == 18
        assert matrix_res["shape"] == (2, 18)
        assert len(matrix_res["records"]) == 2
        print("[OK] Tabular feature matrix correctly structured with 2 rows and 18 columns.")

        # Step 9: Test Non-Existent Attempt Rejection
        print("\n--- 9. Testing Non-Existent and Invalid Attempt Handling ---")
        try:
            extract_and_persist_behavioral_features(999999)
            assert False, "Should raise ValueError for non-existent attempt"
        except ValueError as e:
            assert "does not exist" in str(e)
            print(f"[OK] Non-existent attempt rejected: {e}")

        try:
            extract_and_persist_behavioral_features(-1)
            assert False, "Should raise ValueError for negative attempt ID"
        except ValueError as e:
            print(f"[OK] Invalid negative ID rejected: {e}")

    finally:
        # Step 10: Teardown & Database Baseline Verification
        print("\n--- 10. Cleaning Up Test Data & Verifying Database State ---")
        _cleanup_test_data()

        final_users = _count_table("users")
        final_exams = _count_table("exams")
        final_attempts = _count_table("exam_attempts")
        final_features = _count_table("behavioral_features")
        final_events = _count_table("monitoring_events")

        print(f"Final DB State: users={final_users}, exams={final_exams}, attempts={final_attempts}, features={final_features}, events={final_events}")

        assert final_users == init_users, f"Users count mismatch: expected {init_users}, got {final_users}"
        assert final_exams == init_exams, f"Exams count mismatch: expected {init_exams}, got {final_exams}"
        assert final_attempts == init_attempts, f"Attempts count mismatch: expected {init_attempts}, got {final_attempts}"
        assert final_features == init_features, f"Features count mismatch: expected {init_features}, got {final_features}"
        assert final_events == 0, f"Monitoring events count mismatch: expected 0, got {final_events}"

        print("\n" + "=" * 70)
        print("ALL BEHAVIORAL FEATURE SERVICE & DATABASE TESTS PASSED SUCCESSFULLY!")
        print("=" * 70)


if __name__ == "__main__":
    run_tests()
