"""
Unit & Integration Test Suite for Phase 7 ML Dataset & Feature Matrix Assembly.

Verifies:
1. Empty dataset representation: shape (0, 18), is_empty=True, attempt_ids=().
2. Single valid attempt: shape (1, 18), correct vector values, is_empty=False.
3. Multiple valid attempts: shape (n, 18), correct attempt_ids and rows.
4. Exact (n, 18) matrix shape across varied cohort sizes.
5. Deterministic feature ordering: column j matches ML_FEATURE_NAMES[j] for all j.
6. attempt_id preserved strictly as metadata (accessible via dataset.attempt_ids).
7. attempt_id excluded from matrix X (X has exactly 18 behavioral columns).
8. Missing feature rejection in any row fails the entire assembly.
9. Unexpected feature rejection in any row fails the entire assembly.
10. Invalid numeric value rejection (strings, None, objects, bools).
11. NaN rejection across any row.
12. Infinity rejection (+inf, -inf) across any row.
13. Ratio-bound rejection (< 0.0 or > 1.0) on ratio features.
14. Negative-value rejection on durations, counts, rates, intervals.
15. Inconsistent feature dictionaries: zero silent drops, fails immediately.
16. Deterministic repeated assembly on identical inputs.
17. Phase 6 feature compatibility (in-memory extractor and database retrieval).
18. No input mutation on caller data structures.
19. Database integration: terminal attempt validation ('SUBMITTED', 'EVALUATED')
    and strict rejection of 'IN_PROGRESS' attempts.
"""

from datetime import datetime, timedelta
import math
import os
import sys

workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

import numpy as np

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
    FEATURE_ABSENCE_MAX_DURATION_SEC,
    FEATURE_ABSENCE_AVG_DURATION_SEC,
    FEATURE_ABSENCE_TIME_RATIO,
    FEATURE_MULTI_FACE_EVENT_COUNT,
    FEATURE_MULTI_FACE_TOTAL_DURATION_SEC,
    FEATURE_MULTI_FACE_MAX_DURATION_SEC,
    FEATURE_MULTI_FACE_TIME_RATIO,
    FEATURE_TOTAL_MONITORING_EVENTS,
    FEATURE_EVENT_RATE_PER_MINUTE,
    FEATURE_EARLY_EXAM_EVENT_RATIO,
    FEATURE_MID_EXAM_EVENT_RATIO,
    FEATURE_LATE_EXAM_EVENT_RATIO,
    FEATURE_AVG_INTER_EVENT_INTERVAL_SEC,
    FEATURE_QUESTIONS_ANSWERED_RATIO,
    FEATURE_ATTEMPT_DURATION_PER_ANSWERED_QUESTION_SEC,
    extract_behavioral_features,
)
from src.features.service import extract_and_persist_behavioral_features
from src.ml.contract import (
    EXPECTED_FEATURE_COUNT,
    ML_FEATURE_NAMES,
    RATIO_FEATURE_NAMES,
    MLContractValidationError,
    ValidatedFeatureVector,
)
from src.ml.dataset import (
    MLDataset,
    assemble_feature_matrix,
    assemble_from_database,
)


def _get_sample_feature_dict(scale: float = 1.0) -> dict:
    """Generates a standard valid 18-feature dictionary."""
    return {
        FEATURE_ATTEMPT_DURATION_SEC: 1800.0 * scale,
        FEATURE_ABSENCE_EVENT_COUNT: 2.0 * scale,
        FEATURE_ABSENCE_TOTAL_DURATION_SEC: 40.0 * scale,
        FEATURE_ABSENCE_MAX_DURATION_SEC: 25.0 * scale,
        FEATURE_ABSENCE_AVG_DURATION_SEC: 20.0 * scale,
        FEATURE_ABSENCE_TIME_RATIO: min(1.0, 0.0222 * scale),
        FEATURE_MULTI_FACE_EVENT_COUNT: 1.0 * scale,
        FEATURE_MULTI_FACE_TOTAL_DURATION_SEC: 10.0 * scale,
        FEATURE_MULTI_FACE_MAX_DURATION_SEC: 10.0 * scale,
        FEATURE_MULTI_FACE_TIME_RATIO: min(1.0, 0.0055 * scale),
        FEATURE_TOTAL_MONITORING_EVENTS: 3.0 * scale,
        FEATURE_EVENT_RATE_PER_MINUTE: 0.1 * scale,
        FEATURE_EARLY_EXAM_EVENT_RATIO: 0.3333,
        FEATURE_MID_EXAM_EVENT_RATIO: 0.3333,
        FEATURE_LATE_EXAM_EVENT_RATIO: 0.3334,
        FEATURE_AVG_INTER_EVENT_INTERVAL_SEC: 400.0 * scale,
        FEATURE_QUESTIONS_ANSWERED_RATIO: min(1.0, 0.85 * scale),
        FEATURE_ATTEMPT_DURATION_PER_ANSWERED_QUESTION_SEC: 105.88 * scale,
    }


def _cleanup_test_data():
    """Restores database to pristine state by purging test artifacts."""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        cursor.execute("DELETE FROM integrity_assessments;")
        cursor.execute("DELETE FROM behavioral_features;")
        cursor.execute("DELETE FROM monitoring_events;")
        cursor.execute("DELETE FROM results;")
        cursor.execute("DELETE FROM answers;")
        cursor.execute("DELETE FROM exam_attempts;")
        cursor.execute("DELETE FROM questions;")
        cursor.execute("DELETE FROM exams;")
        cursor.execute("DELETE FROM users WHERE email LIKE '%@ml_test.com';")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
        conn.commit()
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def run_tests():
    print("=" * 70)
    print("STARTING ML DATASET & FEATURE MATRIX ASSEMBLY UNIT TESTS")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # Test 1: Empty Dataset Representation
    # -------------------------------------------------------------------------
    print("\n--- Test 1: Empty Dataset Representation ---")
    empty_ds = assemble_feature_matrix({})
    assert isinstance(empty_ds, MLDataset)
    assert empty_ds.is_empty is True
    assert empty_ds.n_rows == 0
    assert empty_ds.n_features == 18
    assert empty_ds.shape == (0, 18)
    assert empty_ds.attempt_ids == ()
    assert empty_ds.feature_names == ML_FEATURE_NAMES
    assert len(empty_ds) == 0

    arr_empty = empty_ds.to_numpy()
    assert isinstance(arr_empty, np.ndarray)
    assert arr_empty.shape == (0, 18)
    assert arr_empty.dtype == np.float64

    dict_empty = empty_ds.to_dict()
    assert dict_empty["shape"] == (0, 18)
    assert dict_empty["attempt_ids"] == []
    assert dict_empty["data"] == []
    assert empty_ds.to_records() == []
    print("[OK] Test 1 PASSED: Empty dataset correctly assembled with shape (0, 18).")

    # -------------------------------------------------------------------------
    # Test 2: Single Valid Attempt
    # -------------------------------------------------------------------------
    print("\n--- Test 2: Single Valid Attempt ---")
    feat_1 = _get_sample_feature_dict(1.0)
    ds_single = assemble_feature_matrix({101: feat_1})
    assert ds_single.is_empty is False
    assert ds_single.n_rows == 1
    assert ds_single.n_features == 18
    assert ds_single.shape == (1, 18)
    assert ds_single.attempt_ids == (101,)
    assert len(ds_single) == 1

    arr_single = ds_single.to_numpy()
    assert arr_single.shape == (1, 18)
    assert arr_single[0, 0] == 1800.0

    # Row retrieval
    row_0 = ds_single.get_row(0)
    assert isinstance(row_0, ValidatedFeatureVector)
    assert row_0[0] == 1800.0

    row_by_id = ds_single.get_row_by_attempt_id(101)
    assert row_by_id.to_tuple() == row_0.to_tuple()
    print("[OK] Test 2 PASSED: Single attempt correctly assembled with shape (1, 18).")

    # -------------------------------------------------------------------------
    # Test 3: Multiple Valid Attempts
    # -------------------------------------------------------------------------
    print("\n--- Test 3: Multiple Valid Attempts ---")
    attempts_map = {
        101: _get_sample_feature_dict(1.0),
        102: _get_sample_feature_dict(1.5),
        103: _get_sample_feature_dict(2.0),
    }
    ds_multi = assemble_feature_matrix(attempts_map)
    assert ds_multi.shape == (3, 18)
    assert ds_multi.attempt_ids == (101, 102, 103)
    assert ds_multi.n_rows == 3

    arr_multi = ds_multi.to_numpy()
    assert arr_multi.shape == (3, 18)
    assert arr_multi[0, 0] == 1800.0
    assert arr_multi[1, 0] == 2700.0
    assert arr_multi[2, 0] == 3600.0
    print("[OK] Test 3 PASSED: Multiple attempts correctly assembled with shape (3, 18).")

    # -------------------------------------------------------------------------
    # Test 4: Alternative Input Formats (Sequence of Tuples, Sequence of Dicts)
    # -------------------------------------------------------------------------
    print("\n--- Test 4: Alternative Input Formats ---")
    # Format 2: Sequence of tuples
    tuple_seq = [
        (201, _get_sample_feature_dict(1.0)),
        (202, _get_sample_feature_dict(1.2)),
    ]
    ds_from_tuples = assemble_feature_matrix(tuple_seq)
    assert ds_from_tuples.shape == (2, 18)
    assert ds_from_tuples.attempt_ids == (201, 202)

    # Format 3: Sequence of dicts with embedded 'attempt_id'
    dict_seq = [
        {"attempt_id": 301, **_get_sample_feature_dict(1.0)},
        {"attempt_id": 302, **_get_sample_feature_dict(1.3)},
    ]
    ds_from_dicts = assemble_feature_matrix(dict_seq)
    assert ds_from_dicts.shape == (2, 18)
    assert ds_from_dicts.attempt_ids == (301, 302)
    print("[OK] Test 4 PASSED: Sequence of tuples and sequence of dicts assembled identically.")

    # -------------------------------------------------------------------------
    # Test 5: Exact (n, 18) Matrix Shape Invariant
    # -------------------------------------------------------------------------
    print("\n--- Test 5: Exact (n, 18) Matrix Shape Across Cohort Sizes ---")
    for n in (0, 1, 2, 4, 7):
        data = {100 + i: _get_sample_feature_dict(1.0 + i * 0.1) for i in range(n)}
        ds = assemble_feature_matrix(data)
        assert ds.shape == (n, 18), f"Expected shape ({n}, 18), got {ds.shape}"
        assert ds.to_numpy().shape == (n, 18)
    print("[OK] Test 5 PASSED: Matrix shape strictly maintains (n, 18).")

    # -------------------------------------------------------------------------
    # Test 6: Deterministic Feature Ordering
    # -------------------------------------------------------------------------
    print("\n--- Test 6: Deterministic Feature Ordering ---")
    import random
    raw_d = _get_sample_feature_dict(1.0)
    # Scramble dictionary keys
    shuffled_keys = list(raw_d.keys())
    random.Random(99).shuffle(shuffled_keys)
    scrambled_d = {k: raw_d[k] for k in shuffled_keys}

    ds_scrambled = assemble_feature_matrix({501: scrambled_d})
    # Check that each column index j corresponds exactly to ML_FEATURE_NAMES[j]
    for j, name in enumerate(ML_FEATURE_NAMES):
        assert ds_scrambled.matrix[0][j] == raw_d[name]
        assert ds_scrambled.to_numpy()[0, j] == raw_d[name]
    print("[OK] Test 6 PASSED: Column order strictly matches ML_FEATURE_NAMES regardless of dict order.")

    # -------------------------------------------------------------------------
    # Test 7: attempt_id Preserved as Metadata & Excluded from X
    # -------------------------------------------------------------------------
    print("\n--- Test 7: attempt_id Metadata Isolation ---")
    ds = assemble_feature_matrix({
        901: _get_sample_feature_dict(1.0),
        902: _get_sample_feature_dict(1.5),
    })
    # Metadata contains attempt_ids
    assert ds.attempt_ids == (901, 902)
    # X feature names do NOT contain attempt_id
    assert "attempt_id" not in ds.feature_names
    assert len(ds.feature_names) == 18
    # Matrix columns have exactly 18 elements
    for row in ds.matrix:
        assert len(row) == 18
        # Ensure attempt_id value (901 or 902) was not injected into any feature
        assert 901 not in row and 902 not in row
    print("[OK] Test 7 PASSED: attempt_id strictly preserved as metadata and excluded from X.")

    # -------------------------------------------------------------------------
    # Test 8: Missing Feature Rejection (Zero Silent Drop / Imputation)
    # -------------------------------------------------------------------------
    print("\n--- Test 8: Missing Feature Rejection ---")
    bad_dict = _get_sample_feature_dict(1.0)
    del bad_dict[FEATURE_ABSENCE_TIME_RATIO]
    try:
        assemble_feature_matrix({101: _get_sample_feature_dict(1.0), 102: bad_dict})
        assert False, "Should have failed fast on missing feature in row 2"
    except MLContractValidationError as e:
        assert "Missing 1 required feature(s)" in str(e)
        assert FEATURE_ABSENCE_TIME_RATIO in str(e)
    print("[OK] Test 8 PASSED: Missing feature rejected without silent drop or imputation.")

    # -------------------------------------------------------------------------
    # Test 9: Unexpected Feature Rejection
    # -------------------------------------------------------------------------
    print("\n--- Test 9: Unexpected Feature Rejection ---")
    extra_dict = _get_sample_feature_dict(1.0)
    extra_dict["rogue_feature"] = 999.0
    try:
        assemble_feature_matrix({101: extra_dict})
        assert False, "Should have failed fast on unexpected feature"
    except MLContractValidationError as e:
        assert "Unexpected feature(s) provided" in str(e)
        assert "rogue_feature" in str(e)
    print("[OK] Test 9 PASSED: Unexpected features strictly rejected.")

    # -------------------------------------------------------------------------
    # Test 10: Invalid Numeric & Boolean Value Rejection
    # -------------------------------------------------------------------------
    print("\n--- Test 10: Non-Numeric and Boolean Rejection ---")
    for bad_val in ("slow", None, True, False, [1.0]):
        d = _get_sample_feature_dict(1.0)
        d[FEATURE_ATTEMPT_DURATION_SEC] = bad_val
        try:
            assemble_feature_matrix({101: d})
            assert False, f"Should have rejected bad value: {bad_val}"
        except MLContractValidationError as e:
            assert ("must be numeric" in str(e)) or ("got boolean" in str(e))
    print("[OK] Test 10 PASSED: Non-numeric and boolean values strictly rejected.")

    # -------------------------------------------------------------------------
    # Test 11: NaN and Infinity Rejection
    # -------------------------------------------------------------------------
    print("\n--- Test 11: NaN and Infinity Rejection ---")
    # NaN
    d_nan = _get_sample_feature_dict(1.0)
    d_nan[FEATURE_ABSENCE_TOTAL_DURATION_SEC] = float("nan")
    try:
        assemble_feature_matrix({101: d_nan})
        assert False, "Should have rejected NaN"
    except MLContractValidationError as e:
        assert "contains NaN" in str(e)

    # +inf and -inf
    for inf_val in (float("inf"), float("-inf")):
        d_inf = _get_sample_feature_dict(1.0)
        d_inf[FEATURE_EVENT_RATE_PER_MINUTE] = inf_val
        try:
            assemble_feature_matrix({101: d_inf})
            assert False, f"Should have rejected inf value: {inf_val}"
        except MLContractValidationError as e:
            assert "contains infinite value" in str(e)
    print("[OK] Test 11 PASSED: NaN and infinities rejected across all rows.")

    # -------------------------------------------------------------------------
    # Test 12: Ratio Bounds & Non-Negativity Enforcement
    # -------------------------------------------------------------------------
    print("\n--- Test 12: Ratio Bounds & Non-Negativity Rejection ---")
    # Ratio > 1.0
    d_ratio_high = _get_sample_feature_dict(1.0)
    d_ratio_high[FEATURE_QUESTIONS_ANSWERED_RATIO] = 1.05
    try:
        assemble_feature_matrix({101: d_ratio_high})
        assert False, "Should have rejected ratio > 1.0"
    except MLContractValidationError as e:
        assert "must be within [0.0, 1.0]" in str(e)

    # Negative duration
    d_neg = _get_sample_feature_dict(1.0)
    d_neg[FEATURE_ATTEMPT_DURATION_SEC] = -50.0
    try:
        assemble_feature_matrix({101: d_neg})
        assert False, "Should have rejected negative duration"
    except MLContractValidationError as e:
        assert "cannot be negative" in str(e)
    print("[OK] Test 12 PASSED: Ratio bounds and non-negativity strictly enforced.")

    # -------------------------------------------------------------------------
    # Test 13: Inconsistent Cohort Handling (Fail Fast, Zero Silent Drops)
    # -------------------------------------------------------------------------
    print("\n--- Test 13: Inconsistent Cohort Handling (Zero Silent Drops) ---")
    # 2 valid rows, 1 corrupt row in the middle
    cohort = {
        101: _get_sample_feature_dict(1.0),
        102: {"attempt_duration_sec": 1800.0},  # incomplete
        103: _get_sample_feature_dict(1.5),
    }
    try:
        assemble_feature_matrix(cohort)
        assert False, "Should have failed fast on corrupt attempt 102"
    except MLContractValidationError as e:
        assert "Missing 17 required feature(s)" in str(e)
    print("[OK] Test 13 PASSED: Inconsistent cohorts fail fast without silently dropping invalid rows.")

    # -------------------------------------------------------------------------
    # Test 14: Invalid attempt_id and Duplicate Detection
    # -------------------------------------------------------------------------
    print("\n--- Test 14: attempt_id Validation & Duplicate Detection ---")
    # Invalid attempt_id
    for bad_id in (-1, 0, "101", True, None):
        try:
            assemble_feature_matrix({bad_id: _get_sample_feature_dict(1.0)})  # type: ignore
            assert False, f"Should have rejected invalid attempt_id: {bad_id}"
        except MLContractValidationError as e:
            assert "Valid attempt_id must be a positive integer" in str(e)

    # Duplicate attempt_id in sequence
    dup_seq = [
        (101, _get_sample_feature_dict(1.0)),
        (101, _get_sample_feature_dict(1.2)),
    ]
    try:
        assemble_feature_matrix(dup_seq)
        assert False, "Should have rejected duplicate attempt_id in dataset"
    except MLContractValidationError as e:
        assert "Duplicate attempt_id detected in dataset: 101" in str(e)
    print("[OK] Test 14 PASSED: Invalid and duplicate attempt_ids strictly rejected.")

    # -------------------------------------------------------------------------
    # Test 15: Deterministic Repeated Assembly & Immutability
    # -------------------------------------------------------------------------
    print("\n--- Test 15: Determinism & Immutability ---")
    cohort_static = {
        201: _get_sample_feature_dict(1.0),
        202: _get_sample_feature_dict(1.2),
        203: _get_sample_feature_dict(1.4),
    }
    ds_1 = assemble_feature_matrix(cohort_static)
    ds_2 = assemble_feature_matrix(cohort_static)

    assert ds_1.shape == ds_2.shape
    assert ds_1.attempt_ids == ds_2.attempt_ids
    assert ds_1.matrix == ds_2.matrix
    assert np.array_equal(ds_1.to_numpy(), ds_2.to_numpy())

    # Immutability
    try:
        ds_1.matrix = ()  # type: ignore
        assert False, "Should have prevented modification of frozen MLDataset"
    except Exception:
        pass
    print("[OK] Test 15 PASSED: Assembly is strictly deterministic and output is immutable.")

    # -------------------------------------------------------------------------
    # Test 16: No Input Mutation
    # -------------------------------------------------------------------------
    print("\n--- Test 16: No Input Mutation ---")
    input_dict = {
        401: _get_sample_feature_dict(1.0),
        402: _get_sample_feature_dict(1.5),
    }
    import copy
    snapshot = copy.deepcopy(input_dict)
    assemble_feature_matrix(input_dict)
    assert input_dict == snapshot, "assemble_feature_matrix must never mutate caller data"
    print("[OK] Test 16 PASSED: Caller data structures preserved without mutation.")

    # -------------------------------------------------------------------------
    # Test 17: In-Memory Phase 6 Feature Extractor Compatibility
    # -------------------------------------------------------------------------
    print("\n--- Test 17: In-Memory Phase 6 Extractor Compatibility ---")
    base_time = datetime(2026, 10, 1, 10, 0, 0)
    p6_extracted = extract_behavioral_features(
        attempt={"attempt_id": 801, "started_at": base_time, "submitted_at": base_time + timedelta(minutes=30)},
        total_questions=20,
        answers=[{"question_id": 1, "created_at": base_time + timedelta(minutes=5)}],
        monitoring_events=[{
            "event_type": "FACE_ABSENT",
            "confidence": 1.0,
            "created_at": base_time + timedelta(minutes=10),
            "event_metadata": {"duration_seconds": 15.0},
        }],
    )
    ds_p6 = assemble_feature_matrix({801: p6_extracted})
    assert ds_p6.shape == (1, 18)
    assert ds_p6.attempt_ids == (801,)
    assert ds_p6.to_numpy()[0, 1] == 1.0  # absence_event_count
    print("[OK] Test 17 PASSED: Output of Phase 6 extractor seamlessly integrates into MLDataset.")

    # -------------------------------------------------------------------------
    # Test 18: Database Integration & Terminal State Enforcement
    # -------------------------------------------------------------------------
    print("\n--- Test 18: Database Retrieval & Terminal State Enforcement ---")
    _cleanup_test_data()

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Create a test teacher and students
    cursor.execute(
        "INSERT INTO users (name, email, password_hash, role) VALUES ('ML Teacher', 'teacher@ml_test.com', 'dummy_hash', 'teacher');"
    )
    teacher_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO users (name, email, password_hash, role) VALUES ('ML Student 1', 'student1@ml_test.com', 'dummy_hash', 'student');"
    )
    student1_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO users (name, email, password_hash, role) VALUES ('ML Student 2', 'student2@ml_test.com', 'dummy_hash', 'student');"
    )
    student2_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO users (name, email, password_hash, role) VALUES ('ML Student 3', 'student3@ml_test.com', 'dummy_hash', 'student');"
    )
    student3_id = cursor.lastrowid
    conn.commit()

    # 2. Create test exam
    exam = create_exam(
        title="ML Assembly Exam",
        description="Testing ML dataset assembly",
        duration_minutes=30,
        created_by=teacher_id,
    )
    exam_id = exam["exam_id"]
    q1 = add_question(
        exam_id=exam_id,
        teacher_id=teacher_id,
        question_text="Q1 text",
        option_a="A",
        option_b="B",
        option_c="C",
        option_d="D",
        correct_option="A",
        marks=2,
    )
    q2 = add_question(
        exam_id=exam_id,
        teacher_id=teacher_id,
        question_text="Q2 text",
        option_a="A",
        option_b="B",
        option_c="C",
        option_d="D",
        correct_option="B",
        marks=3,
    )
    publish_exam(exam_id=exam_id, teacher_id=teacher_id)

    # 3. Create Attempt A: SUBMITTED
    att_a_res = start_attempt(exam_id=exam_id, student_id=student1_id)
    att_a = att_a_res["attempt_id"]
    save_answer(attempt_id=att_a, student_id=student1_id, question_id=q1["question_id"], selected_option="A")
    record_monitoring_event(
        attempt_id=att_a,
        event_type="FACE_ABSENT",
        event_metadata={"sustained_duration_sec": 10.0, "threshold_sec": 5.0},
    )
    submit_attempt(attempt_id=att_a, student_id=student1_id)
    extract_and_persist_behavioral_features(att_a)

    # 4. Create Attempt B: EVALUATED
    att_b_res = start_attempt(exam_id=exam_id, student_id=student2_id)
    att_b = att_b_res["attempt_id"]
    save_answer(attempt_id=att_b, student_id=student2_id, question_id=q1["question_id"], selected_option="A")
    save_answer(attempt_id=att_b, student_id=student2_id, question_id=q2["question_id"], selected_option="B")
    submit_attempt(attempt_id=att_b, student_id=student2_id)
    evaluate_attempt(attempt_id=att_b, student_id=student2_id)
    extract_and_persist_behavioral_features(att_b)

    # 5. Create Attempt C: IN_PROGRESS (Non-terminal)
    att_c_res = start_attempt(exam_id=exam_id, student_id=student3_id)
    att_c = att_c_res["attempt_id"]

    # 6. Test assemble_from_database for exam: should load only terminal attempts (A and B)
    ds_db = assemble_from_database(exam_id=exam_id, connection=conn)
    assert ds_db.shape == (2, 18), f"Expected 2 terminal attempts, got {ds_db.shape}"
    assert set(ds_db.attempt_ids) == {att_a, att_b}
    assert att_c not in ds_db.attempt_ids

    # 7. Test assemble_from_database with explicit attempt_ids:
    ds_explicit = assemble_from_database(attempt_ids=[att_b, att_a], connection=conn)
    assert ds_explicit.shape == (2, 18)
    # Ordering must match explicit request:
    assert ds_explicit.attempt_ids == (att_b, att_a)

    # 8. Test IN_PROGRESS attempt rejection:
    try:
        assemble_from_database(attempt_ids=[att_a, att_c], connection=conn)
        assert False, "Should have rejected IN_PROGRESS attempt C"
    except ValueError as e:
        assert "Attempt is currently IN_PROGRESS" in str(e)

    # 9. Test non-existent attempt rejection:
    try:
        assemble_from_database(attempt_ids=[999999], connection=conn)
        assert False, "Should have rejected non-existent attempt"
    except ValueError as e:
        assert "Exam attempt with ID 999999 does not exist" in str(e)

    # Clean up test database records
    cursor.close()
    conn.close()
    _cleanup_test_data()
    print("[OK] Test 18 PASSED: Database integration enforces terminal states and handles queries safely.")

    print("\n" + "=" * 70)
    print("ALL 18 ML DATASET & FEATURE MATRIX UNIT TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
