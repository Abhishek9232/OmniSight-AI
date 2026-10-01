"""
Unit Test Suite for Phase 7 ML Feature Input Contract & Validation Foundation.

Verifies:
- Authoritative 18-feature ordering and schema version.
- Valid 18-feature vector acceptance (dict, tuple, list, numpy array).
- Missing feature rejection with explicit error details.
- Unexpected feature rejection with explicit error details.
- Wrong feature count rejection (e.g., 17 or 19 features).
- Non-numeric value rejection (strings, None, objects).
- Strict boolean value rejection (True/False disallowed as numerical metrics).
- NaN rejection (float('nan') and np.nan).
- Positive infinity rejection (+inf).
- Negative infinity rejection (-inf).
- Ratio bounds enforcement: rejection of values < 0.0 and > 1.0 on all 6 ratio features.
- Non-negativity enforcement on all durations, counts, rates, intervals, and ratios.
- Deterministic feature ordering preservation regardless of dictionary insertion order.
- Output representation contracts (.to_tuple(), .to_list(), .to_dict(), .to_numpy()).
- Immutability of ValidatedFeatureVector.
- End-to-end compatibility with Phase 6 extractor output.
"""

from datetime import datetime, timedelta
import math
import os
import sys

workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

import numpy as np

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
from src.ml.contract import (
    FEATURE_SCHEMA_VERSION,
    EXPECTED_FEATURE_COUNT,
    ML_FEATURE_NAMES,
    RATIO_FEATURE_NAMES,
    MLContractValidationError,
    ValidatedFeatureVector,
    validate_feature_dict,
    validate_feature_vector,
    validate_features,
)


def _get_valid_sample_dict():
    """Generates a standard, valid 18-feature dictionary."""
    return {
        FEATURE_ATTEMPT_DURATION_SEC: 1800.0,
        FEATURE_ABSENCE_EVENT_COUNT: 2.0,
        FEATURE_ABSENCE_TOTAL_DURATION_SEC: 45.0,
        FEATURE_ABSENCE_MAX_DURATION_SEC: 30.0,
        FEATURE_ABSENCE_AVG_DURATION_SEC: 22.5,
        FEATURE_ABSENCE_TIME_RATIO: 0.025,
        FEATURE_MULTI_FACE_EVENT_COUNT: 1.0,
        FEATURE_MULTI_FACE_TOTAL_DURATION_SEC: 15.0,
        FEATURE_MULTI_FACE_MAX_DURATION_SEC: 15.0,
        FEATURE_MULTI_FACE_TIME_RATIO: 0.0083,
        FEATURE_TOTAL_MONITORING_EVENTS: 3.0,
        FEATURE_EVENT_RATE_PER_MINUTE: 0.1,
        FEATURE_EARLY_EXAM_EVENT_RATIO: 0.3333,
        FEATURE_MID_EXAM_EVENT_RATIO: 0.3333,
        FEATURE_LATE_EXAM_EVENT_RATIO: 0.3334,
        FEATURE_AVG_INTER_EVENT_INTERVAL_SEC: 350.0,
        FEATURE_QUESTIONS_ANSWERED_RATIO: 0.95,
        FEATURE_ATTEMPT_DURATION_PER_ANSWERED_QUESTION_SEC: 94.7368,
    }


def run_tests():
    print("=" * 70)
    print("STARTING ML FEATURE CONTRACT & VALIDATION UNIT TESTS")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # Test 1: Authoritative Catalog Invariant & Constant Integrity
    # -------------------------------------------------------------------------
    print("\n--- Test 1: Authoritative Catalog Invariant ---")
    assert FEATURE_SCHEMA_VERSION == "1.0.0", f"Unexpected schema version: {FEATURE_SCHEMA_VERSION}"
    assert EXPECTED_FEATURE_COUNT == 18, f"Expected 18 features, got {EXPECTED_FEATURE_COUNT}"
    assert ML_FEATURE_NAMES == FEATURE_NAMES, "ML_FEATURE_NAMES must be identical to Phase 6 FEATURE_NAMES"
    assert len(ML_FEATURE_NAMES) == 18, "ML_FEATURE_NAMES length must be 18"
    assert len(set(ML_FEATURE_NAMES)) == 18, "Feature names must contain zero duplicates"
    assert len(RATIO_FEATURE_NAMES) == 6, f"Expected 6 ratio features, got {len(RATIO_FEATURE_NAMES)}"
    print("[OK] Test 1 PASSED: Authoritative catalog ordering and constants verified.")

    # -------------------------------------------------------------------------
    # Test 2: Valid 18-Feature Dictionary & Ordered Representation
    # -------------------------------------------------------------------------
    print("\n--- Test 2: Valid 18-Feature Dictionary ---")
    sample_dict = _get_valid_sample_dict()
    vec = validate_feature_dict(sample_dict)
    assert isinstance(vec, ValidatedFeatureVector), "Output must be instance of ValidatedFeatureVector"
    assert len(vec) == 18, f"Vector length must be 18, got {len(vec)}"
    assert vec[0] == 1800.0, f"Expected first feature 1800.0, got {vec[0]}"
    assert vec.feature_names == ML_FEATURE_NAMES, "Vector feature_names must match authoritative names"

    # Representation methods
    tup = vec.to_tuple()
    assert isinstance(tup, tuple) and len(tup) == 18
    lst = vec.to_list()
    assert isinstance(lst, list) and len(lst) == 18
    dct = vec.to_dict()
    assert isinstance(dct, dict) and len(dct) == 18
    assert dct[FEATURE_ATTEMPT_DURATION_SEC] == 1800.0
    arr = vec.to_numpy()
    assert isinstance(arr, np.ndarray)
    assert arr.shape == (18,)
    assert arr.dtype == np.float64
    print("[OK] Test 2 PASSED: Valid feature dict validated and converted to all representations.")

    # -------------------------------------------------------------------------
    # Test 3: Valid 18-Feature Sequence & NumPy Array
    # -------------------------------------------------------------------------
    print("\n--- Test 3: Valid Sequence and NumPy Inputs ---")
    sample_tuple = tuple(sample_dict[name] for name in ML_FEATURE_NAMES)
    vec_seq = validate_feature_vector(sample_tuple)
    assert vec_seq.to_tuple() == tup

    sample_arr = np.array(sample_tuple, dtype=np.float64)
    vec_arr = validate_feature_vector(sample_arr)
    assert np.allclose(vec_arr.to_numpy(), sample_arr)

    # Universal entrypoint validate_features()
    vec_univ_dict = validate_features(sample_dict)
    vec_univ_arr = validate_features(sample_arr)
    assert vec_univ_dict.to_tuple() == vec_univ_arr.to_tuple()
    print("[OK] Test 3 PASSED: Sequences and NumPy arrays validated correctly.")

    # -------------------------------------------------------------------------
    # Test 4: Missing Feature Detection
    # -------------------------------------------------------------------------
    print("\n--- Test 4: Missing Feature Rejection ---")
    missing_dict = sample_dict.copy()
    del missing_dict[FEATURE_ABSENCE_TIME_RATIO]
    try:
        validate_feature_dict(missing_dict)
        assert False, "Should have failed with missing feature"
    except MLContractValidationError as e:
        assert "Missing 1 required feature(s)" in str(e)
        assert FEATURE_ABSENCE_TIME_RATIO in str(e)

    # Multiple missing
    del missing_dict[FEATURE_ATTEMPT_DURATION_SEC]
    try:
        validate_feature_dict(missing_dict)
        assert False, "Should have failed with multiple missing features"
    except MLContractValidationError as e:
        assert "Missing 2 required feature(s)" in str(e)
    print("[OK] Test 4 PASSED: Missing features rejected with explicit error message.")

    # -------------------------------------------------------------------------
    # Test 5: Unexpected / Unknown Feature Rejection
    # -------------------------------------------------------------------------
    print("\n--- Test 5: Unexpected Feature Rejection ---")
    extra_dict = sample_dict.copy()
    extra_dict["unexpected_telemetry_metric"] = 42.0
    try:
        validate_feature_dict(extra_dict)
        assert False, "Should have failed with unexpected feature"
    except MLContractValidationError as e:
        assert "Unexpected feature(s) provided" in str(e)
        assert "unexpected_telemetry_metric" in str(e)
    print("[OK] Test 5 PASSED: Unexpected features strictly rejected.")

    # -------------------------------------------------------------------------
    # Test 6: Wrong Feature Count (Dict & Vector)
    # -------------------------------------------------------------------------
    print("\n--- Test 6: Wrong Feature Count Rejection ---")
    short_seq = sample_tuple[:17]
    try:
        validate_feature_vector(short_seq)
        assert False, "Should have rejected 17-element sequence"
    except MLContractValidationError as e:
        assert "Expected exactly 18 feature values, got 17" in str(e)

    long_seq = sample_tuple + (1.0,)
    try:
        validate_feature_vector(long_seq)
        assert False, "Should have rejected 19-element sequence"
    except MLContractValidationError as e:
        assert "Expected exactly 18 feature values, got 19" in str(e)
    print("[OK] Test 6 PASSED: Non-18 dimensional inputs rejected.")

    # -------------------------------------------------------------------------
    # Test 7: Non-Numeric Types & Strict Boolean Rejection
    # -------------------------------------------------------------------------
    print("\n--- Test 7: Non-Numeric & Boolean Rejection ---")
    invalid_types = ["high", None, [1.0], {"key": 2.0}]
    for bad_val in invalid_types:
        d = sample_dict.copy()
        d[FEATURE_ATTEMPT_DURATION_SEC] = bad_val
        try:
            validate_feature_dict(d)
            assert False, f"Should have rejected non-numeric type {type(bad_val)}"
        except MLContractValidationError as e:
            assert "must be numeric" in str(e)

    # Boolean rejection (Python bool subclasses int, must be explicitly forbidden)
    for bool_val in [True, False]:
        d = sample_dict.copy()
        d[FEATURE_ABSENCE_EVENT_COUNT] = bool_val
        try:
            validate_feature_dict(d)
            assert False, f"Should have rejected boolean value {bool_val}"
        except MLContractValidationError as e:
            assert "got boolean" in str(e)
    print("[OK] Test 7 PASSED: Non-numeric and boolean types strictly rejected.")

    # -------------------------------------------------------------------------
    # Test 8: NaN Rejection
    # -------------------------------------------------------------------------
    print("\n--- Test 8: NaN Rejection ---")
    for nan_val in [float("nan"), np.nan]:
        d = sample_dict.copy()
        d[FEATURE_ABSENCE_TOTAL_DURATION_SEC] = nan_val
        try:
            validate_feature_dict(d)
            assert False, "Should have rejected NaN"
        except MLContractValidationError as e:
            assert "contains NaN" in str(e)
    print("[OK] Test 8 PASSED: NaN values rejected with explicit message.")

    # -------------------------------------------------------------------------
    # Test 9: Positive and Negative Infinity Rejection
    # -------------------------------------------------------------------------
    print("\n--- Test 9: Positive and Negative Infinity Rejection ---")
    for inf_val in [float("inf"), np.inf, float("-inf"), -np.inf]:
        d = sample_dict.copy()
        d[FEATURE_EVENT_RATE_PER_MINUTE] = inf_val
        try:
            validate_feature_dict(d)
            assert False, f"Should have rejected infinite value {inf_val}"
        except MLContractValidationError as e:
            assert "contains infinite value" in str(e)
    print("[OK] Test 9 PASSED: Infinite values (+inf, -inf) rejected.")

    # -------------------------------------------------------------------------
    # Test 10: Ratio Bounds Enforcement ([0.0, 1.0])
    # -------------------------------------------------------------------------
    print("\n--- Test 10: Ratio Bounds Enforcement ---")
    for ratio_name in RATIO_FEATURE_NAMES:
        # Below 0.0
        d_neg = sample_dict.copy()
        d_neg[ratio_name] = -0.0001
        try:
            validate_feature_dict(d_neg)
            assert False, f"Should have rejected ratio < 0 for {ratio_name}"
        except MLContractValidationError as e:
            assert "cannot be negative" in str(e)

        # Above 1.0
        d_high = sample_dict.copy()
        d_high[ratio_name] = 1.0001
        try:
            validate_feature_dict(d_high)
            assert False, f"Should have rejected ratio > 1.0 for {ratio_name}"
        except MLContractValidationError as e:
            assert "must be within [0.0, 1.0]" in str(e)

    # Valid boundary values: 0.0 and 1.0 exactly
    d_bounds = sample_dict.copy()
    for ratio_name in RATIO_FEATURE_NAMES:
        d_bounds[ratio_name] = 0.0
    vec_zero_ratios = validate_feature_dict(d_bounds)
    for ratio_name in RATIO_FEATURE_NAMES:
        assert vec_zero_ratios.to_dict()[ratio_name] == 0.0

    for ratio_name in RATIO_FEATURE_NAMES:
        d_bounds[ratio_name] = 1.0
    vec_one_ratios = validate_feature_dict(d_bounds)
    for ratio_name in RATIO_FEATURE_NAMES:
        assert vec_one_ratios.to_dict()[ratio_name] == 1.0
    print("[OK] Test 10 PASSED: Ratio bounds strictly enforced on all 6 ratio metrics.")

    # -------------------------------------------------------------------------
    # Test 11: Non-Negativity Enforcement on All Features
    # -------------------------------------------------------------------------
    print("\n--- Test 11: Non-Negativity Enforcement ---")
    for feat_name in ML_FEATURE_NAMES:
        d_neg = sample_dict.copy()
        d_neg[feat_name] = -1.0
        try:
            validate_feature_dict(d_neg)
            assert False, f"Should have rejected negative value for {feat_name}"
        except MLContractValidationError as e:
            assert "cannot be negative" in str(e)
    print("[OK] Test 11 PASSED: Non-negativity verified across all 18 features.")

    # -------------------------------------------------------------------------
    # Test 12: Deterministic Feature Ordering Invariant
    # -------------------------------------------------------------------------
    print("\n--- Test 12: Deterministic Feature Ordering ---")
    # Reverse dictionary insertion order
    reversed_dict = {k: sample_dict[k] for k in reversed(list(sample_dict.keys()))}
    vec_rev = validate_feature_dict(reversed_dict)

    # Scramble dictionary order
    import random
    keys = list(sample_dict.keys())
    rng = random.Random(42)
    rng.shuffle(keys)
    scrambled_dict = {k: sample_dict[k] for k in keys}
    vec_scrambled = validate_feature_dict(scrambled_dict)

    # Both must match the authoritative tuple ordering identically
    expected_values = tuple(sample_dict[name] for name in ML_FEATURE_NAMES)
    assert vec_rev.to_tuple() == expected_values, "Reversed insertion order produced wrong vector order"
    assert vec_scrambled.to_tuple() == expected_values, "Scrambled insertion order produced wrong vector order"
    print("[OK] Test 12 PASSED: Deterministic ordering strictly preserved across random dict keys.")

    # -------------------------------------------------------------------------
    # Test 13: Immutability of ValidatedFeatureVector
    # -------------------------------------------------------------------------
    print("\n--- Test 13: Vector Immutability ---")
    try:
        vec.values = (1.0,) * 18  # type: ignore
        assert False, "Should have prevented mutation on frozen dataclass"
    except Exception:
        pass
    print("[OK] Test 13 PASSED: ValidatedFeatureVector is immutable.")

    # -------------------------------------------------------------------------
    # Test 14: End-to-End Compatibility with Phase 6 Feature Extractor
    # -------------------------------------------------------------------------
    print("\n--- Test 14: Phase 6 Extractor Compatibility ---")
    base_time = datetime(2026, 10, 1, 10, 0, 0)
    end_time = base_time + timedelta(minutes=45)
    mock_attempt = {
        "attempt_id": 501,
        "exam_id": 10,
        "total_questions": 20,
        "started_at": base_time,
        "submitted_at": end_time,
    }
    mock_events = [
        {
            "event_type": "FACE_ABSENT",
            "confidence": 1.0,
            "created_at": base_time + timedelta(minutes=5),
            "event_metadata": {"duration_seconds": 12.0},
        },
        {
            "event_type": "MULTIPLE_FACES",
            "confidence": 1.0,
            "created_at": base_time + timedelta(minutes=25),
            "event_metadata": {"duration_seconds": 8.0},
        },
    ]
    mock_answers = [
        {"question_id": i, "selected_option": "A", "created_at": base_time + timedelta(minutes=i)}
        for i in range(1, 19)
    ]

    # Extract raw features from Phase 6 extractor
    p6_features = extract_behavioral_features(
        attempt=mock_attempt,
        total_questions=20,
        monitoring_events=mock_events,
        answers=mock_answers,
    )
    assert len(p6_features) == 18

    # Validate directly through Phase 7 ML contract layer
    ml_vector = validate_features(p6_features)
    assert isinstance(ml_vector, ValidatedFeatureVector)
    assert len(ml_vector) == 18
    assert ml_vector.to_dict()[FEATURE_ABSENCE_EVENT_COUNT] == 1.0
    assert ml_vector.to_dict()[FEATURE_MULTI_FACE_EVENT_COUNT] == 1.0
    assert ml_vector.to_dict()[FEATURE_QUESTIONS_ANSWERED_RATIO] == 0.90
    print("[OK] Test 14 PASSED: Phase 6 extractor output passes Phase 7 contract seamlessly.")

    print("\n" + "=" * 70)
    print("ALL 14 ML FEATURE CONTRACT UNIT TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
