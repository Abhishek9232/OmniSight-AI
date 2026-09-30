"""
Unit Test Suite for Pure Behavioral Feature Calculation Math (Phase 6).
Verifies:
- Mathematical correctness of all 18 standard behavioral features.
- Zero-event attempt boundary condition (all visual features evaluate to 0.0, no NaN/Inf).
- Zero-answer attempt boundary condition (ratios evaluate to 0.0, no ZeroDivisionError).
- Multiple FACE_ABSENT events (counts, cumulative durations, max, averages, ratios).
- Multiple MULTIPLE_FACES events (counts, cumulative durations, max, ratios).
- Metadata duration extraction (dict vs JSON string vs threshold fallback).
- Early / Mid / Late temporal binning across attempt duration.
- Inter-event interval calculation for 0, 1, and N events.
- Short-duration attempt safety (rate denominator clamping, zero divide-by-zero).
- Ratio bounds invariant ([0.0, 1.0] range preservation).
- Deterministic 4-decimal rounding across all features.
"""

from datetime import datetime, timedelta
import json
import math
import sys
import os

workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

from src.features.extractor import (
    extract_behavioral_features,
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
)


def run_tests():
    print("=" * 70)
    print("STARTING BEHAVIORAL FEATURE MATHEMATICAL UNIT TESTS")
    print("=" * 70)

    base_time = datetime(2026, 10, 1, 10, 0, 0)
    end_time = base_time + timedelta(minutes=30)  # 1800.0 seconds

    base_attempt = {
        "attempt_id": 101,
        "started_at": base_time,
        "submitted_at": end_time,
        "status": "SUBMITTED",
    }
    base_exam = {"exam_id": 1, "duration_minutes": 30, "question_count": 10}

    # -------------------------------------------------------------------------
    # Test 1: Zero-Event & Zero-Answer Clean Boundary
    # -------------------------------------------------------------------------
    print("\n--- Test 1: Zero-Event & Zero-Answer Clean Boundary ---")
    feat1 = extract_behavioral_features(
        attempt=base_attempt,
        exam=base_exam,
        total_questions=10,
        answers=[],
        monitoring_events=[],
    )

    assert len(feat1) == 18, f"Expected 18 features, got {len(feat1)}"
    assert feat1[FEATURE_ATTEMPT_DURATION_SEC] == 1800.0
    assert feat1[FEATURE_ABSENCE_EVENT_COUNT] == 0.0
    assert feat1[FEATURE_ABSENCE_TOTAL_DURATION_SEC] == 0.0
    assert feat1[FEATURE_ABSENCE_MAX_DURATION_SEC] == 0.0
    assert feat1[FEATURE_ABSENCE_AVG_DURATION_SEC] == 0.0
    assert feat1[FEATURE_ABSENCE_TIME_RATIO] == 0.0
    assert feat1[FEATURE_MULTI_FACE_EVENT_COUNT] == 0.0
    assert feat1[FEATURE_MULTI_FACE_TOTAL_DURATION_SEC] == 0.0
    assert feat1[FEATURE_MULTI_FACE_MAX_DURATION_SEC] == 0.0
    assert feat1[FEATURE_MULTI_FACE_TIME_RATIO] == 0.0
    assert feat1[FEATURE_TOTAL_MONITORING_EVENTS] == 0.0
    assert feat1[FEATURE_EVENT_RATE_PER_MINUTE] == 0.0
    assert feat1[FEATURE_EARLY_EXAM_EVENT_RATIO] == 0.0
    assert feat1[FEATURE_MID_EXAM_EVENT_RATIO] == 0.0
    assert feat1[FEATURE_LATE_EXAM_EVENT_RATIO] == 0.0
    assert feat1[FEATURE_AVG_INTER_EVENT_INTERVAL_SEC] == 0.0
    assert feat1[FEATURE_QUESTIONS_ANSWERED_RATIO] == 0.0
    assert feat1[FEATURE_ATTEMPT_DURATION_PER_ANSWERED_QUESTION_SEC] == 0.0

    for name, val in feat1.items():
        assert math.isfinite(val), f"Feature {name} is non-finite: {val}"
    print("[OK] Test 1 PASSED: Zero-event and zero-answer boundary correctly handled.")

    # -------------------------------------------------------------------------
    # Test 2: Answering Metrics with Partial & Full Answering
    # -------------------------------------------------------------------------
    print("\n--- Test 2: Answering Metrics Computation ---")
    answers_partial = [
        {"question_id": 1, "selected_option": "A"},
        {"question_id": 2, "selected_option": "B"},
        {"question_id": 3, "selected_option": None},  # cleared/unanswered
        {"question_id": 4, "selected_option": "D"},
    ]
    feat2 = extract_behavioral_features(
        attempt=base_attempt,
        exam=base_exam,
        total_questions=10,
        answers=answers_partial,
        monitoring_events=[],
    )
    # 3 answered out of 10 -> ratio = 0.3
    assert feat2[FEATURE_QUESTIONS_ANSWERED_RATIO] == 0.3
    # 1800s / 3 answered = 600.0s per answered question
    assert feat2[FEATURE_ATTEMPT_DURATION_PER_ANSWERED_QUESTION_SEC] == 600.0
    print("[OK] Test 2 PASSED: Answering ratio and time per answered question computed accurately.")

    # -------------------------------------------------------------------------
    # Test 3: Multiple FACE_ABSENT Events Math
    # -------------------------------------------------------------------------
    print("\n--- Test 3: Multiple FACE_ABSENT Events Math ---")
    events_absence = [
        {
            "event_type": "FACE_ABSENT",
            "event_timestamp": base_time + timedelta(minutes=5),
            "event_metadata": {"sustained_duration_sec": 7.5, "threshold_sec": 5.0},
        },
        {
            "event_type": "FACE_ABSENT",
            "event_timestamp": base_time + timedelta(minutes=10),
            "event_metadata": json.dumps({"sustained_duration_sec": 12.5, "threshold_sec": 5.0}),  # JSON string
        },
        {
            "event_type": "FACE_ABSENT",
            "event_timestamp": base_time + timedelta(minutes=15),
            "event_metadata": {"threshold_sec": 5.0},  # missing sustained_duration_sec -> fallback to threshold
        },
    ]
    feat3 = extract_behavioral_features(
        attempt=base_attempt,
        exam=base_exam,
        total_questions=10,
        answers=[],
        monitoring_events=events_absence,
    )
    # Event count = 3
    assert feat3[FEATURE_ABSENCE_EVENT_COUNT] == 3.0
    # Total duration = 7.5 + 12.5 + 5.0 = 25.0
    assert feat3[FEATURE_ABSENCE_TOTAL_DURATION_SEC] == 25.0
    # Max duration = 12.5
    assert feat3[FEATURE_ABSENCE_MAX_DURATION_SEC] == 12.5
    # Avg duration = 25.0 / 3 = 8.3333
    assert feat3[FEATURE_ABSENCE_AVG_DURATION_SEC] == 8.3333
    # Time ratio = 25.0 / 1800.0 = 0.0139
    assert feat3[FEATURE_ABSENCE_TIME_RATIO] == 0.0139
    assert feat3[FEATURE_MULTI_FACE_EVENT_COUNT] == 0.0
    assert feat3[FEATURE_MULTI_FACE_TOTAL_DURATION_SEC] == 0.0
    print("[OK] Test 3 PASSED: Multiple FACE_ABSENT metrics match exact expectations.")

    # -------------------------------------------------------------------------
    # Test 4: Multiple MULTIPLE_FACES Events Math
    # -------------------------------------------------------------------------
    print("\n--- Test 4: Multiple MULTIPLE_FACES Events Math ---")
    events_multi = [
        {
            "event_type": "MULTIPLE_FACES",
            "event_timestamp": base_time + timedelta(minutes=6),
            "event_metadata": {"sustained_duration_sec": 4.2},
        },
        {
            "event_type": "MULTIPLE_FACES",
            "event_timestamp": base_time + timedelta(minutes=18),
            "event_metadata": {"sustained_duration_sec": 9.8},
        },
    ]
    feat4 = extract_behavioral_features(
        attempt=base_attempt,
        exam=base_exam,
        total_questions=10,
        answers=[],
        monitoring_events=events_multi,
    )
    assert feat4[FEATURE_MULTI_FACE_EVENT_COUNT] == 2.0
    assert feat4[FEATURE_MULTI_FACE_TOTAL_DURATION_SEC] == 14.0
    assert feat4[FEATURE_MULTI_FACE_MAX_DURATION_SEC] == 9.8
    # 14.0 / 1800.0 = 0.0078
    assert feat4[FEATURE_MULTI_FACE_TIME_RATIO] == 0.0078
    assert feat4[FEATURE_ABSENCE_EVENT_COUNT] == 0.0
    print("[OK] Test 4 PASSED: Multiple MULTIPLE_FACES metrics match exact expectations.")

    # -------------------------------------------------------------------------
    # Test 5: Early / Mid / Late Temporal Binning
    # -------------------------------------------------------------------------
    print("\n--- Test 5: Early / Mid / Late Temporal Distribution ---")
    # Exam duration is 30 mins (1800s):
    # Early: [0, 10) mins
    # Mid:   [10, 20) mins
    # Late:  [20, 30] mins
    events_temporal = [
        {"event_type": "FACE_ABSENT", "event_timestamp": base_time + timedelta(minutes=2)},  # Early
        {"event_type": "FACE_ABSENT", "event_timestamp": base_time + timedelta(minutes=5)},  # Early
        {"event_type": "MULTIPLE_FACES", "event_timestamp": base_time + timedelta(minutes=15)},  # Mid
        {"event_type": "FACE_ABSENT", "event_timestamp": base_time + timedelta(minutes=25)},  # Late
    ]
    feat5 = extract_behavioral_features(
        attempt=base_attempt,
        exam=base_exam,
        total_questions=10,
        answers=[],
        monitoring_events=events_temporal,
    )
    assert feat5[FEATURE_TOTAL_MONITORING_EVENTS] == 4.0
    # 2 early / 4 = 0.5
    assert feat5[FEATURE_EARLY_EXAM_EVENT_RATIO] == 0.5
    # 1 mid / 4 = 0.25
    assert feat5[FEATURE_MID_EXAM_EVENT_RATIO] == 0.25
    # 1 late / 4 = 0.25
    assert feat5[FEATURE_LATE_EXAM_EVENT_RATIO] == 0.25
    # Sum of ratios must equal 1.0
    assert round(feat5[FEATURE_EARLY_EXAM_EVENT_RATIO] + feat5[FEATURE_MID_EXAM_EVENT_RATIO] + feat5[FEATURE_LATE_EXAM_EVENT_RATIO], 4) == 1.0
    print("[OK] Test 5 PASSED: Temporal binning ratios correctly map to exam thirds and sum to 1.0.")

    # -------------------------------------------------------------------------
    # Test 6: Inter-Event Arrival Intervals
    # -------------------------------------------------------------------------
    print("\n--- Test 6: Inter-Event Arrival Intervals ---")
    # Single event -> 0.0
    feat6_single = extract_behavioral_features(
        attempt=base_attempt,
        exam=base_exam,
        total_questions=10,
        monitoring_events=[{"event_type": "FACE_ABSENT", "event_timestamp": base_time + timedelta(minutes=5)}],
    )
    assert feat6_single[FEATURE_AVG_INTER_EVENT_INTERVAL_SEC] == 0.0

    # Three events at t=2m (120s), t=7m (420s), t=14m (840s):
    # Interval 1: 420 - 120 = 300s
    # Interval 2: 840 - 420 = 420s
    # Average interval: (300 + 420) / 2 = 360.0s
    events_intervals = [
        {"event_type": "FACE_ABSENT", "event_timestamp": base_time + timedelta(minutes=2)},
        {"event_type": "MULTIPLE_FACES", "event_timestamp": base_time + timedelta(minutes=7)},
        {"event_type": "FACE_ABSENT", "event_timestamp": base_time + timedelta(minutes=14)},
    ]
    feat6_multi = extract_behavioral_features(
        attempt=base_attempt,
        exam=base_exam,
        total_questions=10,
        monitoring_events=events_intervals,
    )
    assert feat6_multi[FEATURE_AVG_INTER_EVENT_INTERVAL_SEC] == 360.0
    print("[OK] Test 6 PASSED: Inter-event interval accurately computed for 0, 1, and N events.")

    # -------------------------------------------------------------------------
    # Test 7: Short-Duration Attempt Safety & Rate Clamping
    # -------------------------------------------------------------------------
    print("\n--- Test 7: Short-Duration Attempt Safety & Rate Clamping ---")
    short_attempt = {
        "attempt_id": 102,
        "started_at": base_time,
        "submitted_at": base_time + timedelta(seconds=15),  # 15 seconds attempt
        "status": "SUBMITTED",
    }
    short_events = [
        {"event_type": "FACE_ABSENT", "event_timestamp": base_time + timedelta(seconds=5), "event_metadata": {"sustained_duration_sec": 5.0}},
    ]
    feat7 = extract_behavioral_features(
        attempt=short_attempt,
        exam=base_exam,
        total_questions=5,
        answers=[{"question_id": 1, "selected_option": "A"}],
        monitoring_events=short_events,
    )
    assert feat7[FEATURE_ATTEMPT_DURATION_SEC] == 15.0
    # Rate per minute: denominator clamped to max(15s, 60s) / 60s = 1.0 minute -> 1.0 event/min (no extreme spike)
    assert feat7[FEATURE_EVENT_RATE_PER_MINUTE] == 1.0
    assert feat7[FEATURE_ABSENCE_TIME_RATIO] == round(5.0 / 15.0, 4)
    assert feat7[FEATURE_QUESTIONS_ANSWERED_RATIO] == 0.2
    assert feat7[FEATURE_ATTEMPT_DURATION_PER_ANSWERED_QUESTION_SEC] == 15.0
    print("[OK] Test 7 PASSED: Short-duration attempt safely calculated with clamped rate denominator.")

    # -------------------------------------------------------------------------
    # Test 8: Ratio Bounds & Non-Finite Invariant Verification
    # -------------------------------------------------------------------------
    print("\n--- Test 8: Ratio Bounds & Non-Finite Invariant Verification ---")
    ratio_features = [
        FEATURE_ABSENCE_TIME_RATIO,
        FEATURE_MULTI_FACE_TIME_RATIO,
        FEATURE_EARLY_EXAM_EVENT_RATIO,
        FEATURE_MID_EXAM_EVENT_RATIO,
        FEATURE_LATE_EXAM_EVENT_RATIO,
        FEATURE_QUESTIONS_ANSWERED_RATIO,
    ]
    all_test_outputs = [feat1, feat2, feat3, feat4, feat5, feat6_single, feat6_multi, feat7]
    for idx, fvec in enumerate(all_test_outputs, start=1):
        for name in FEATURE_NAMES:
            val = fvec[name]
            assert isinstance(val, (int, float)), f"Test output #{idx} feature {name} is not float/int: {type(val)}"
            assert math.isfinite(val), f"Test output #{idx} feature {name} is non-finite: {val}"
        for rf in ratio_features:
            assert 0.0 <= fvec[rf] <= 1.0, f"Test output #{idx} ratio {rf} = {fvec[rf]} outside [0, 1]!"
    print("[OK] Test 8 PASSED: All 18 features across all test cases strictly finite with ratios in [0, 1].")

    print("\n" + "=" * 70)
    print("ALL BEHAVIORAL FEATURE MATHEMATICAL UNIT TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
