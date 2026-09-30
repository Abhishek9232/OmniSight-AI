"""
Unit Test Suite for ProctoringStateTracker (Phase 5 Step 2).
Verifies deterministic state transitions, continuous temporal thresholds (5s absence, 3s multi-face),
independent 20s cooldowns, monotonic calculations, jitter resistance, and recovery tracking.
Runs with zero external dependencies (no DB, no webcam, no OpenCV).
"""

import sys
import os

workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

from src.proctoring.state import (
    ProctoringStateTracker,
    EVENT_FACE_ABSENT,
    EVENT_MULTIPLE_FACES,
    STATE_NORMAL,
    STATE_ABSENCE_CANDIDATE,
    STATE_ABSENCE_SUSTAINED,
    STATE_MULTI_CANDIDATE,
    STATE_MULTI_SUSTAINED,
)


def test_absence_under_threshold():
    """Verify that absence under 5 seconds does not trigger FACE_ABSENT."""
    tracker = ProctoringStateTracker()
    assert tracker.current_state == STATE_NORMAL

    # T = 0.0s: Initial 0-face observation
    ev1, rec1 = tracker.process_observation(face_count=0, timestamp=0.0)
    assert ev1 is None
    assert rec1 is None
    assert tracker.current_state == STATE_ABSENCE_CANDIDATE

    # T = 2.5s: Continuous absence, still below threshold
    ev2, rec2 = tracker.process_observation(face_count=0, timestamp=2.5)
    assert ev2 is None
    assert tracker.current_state == STATE_ABSENCE_CANDIDATE

    # T = 4.9s: 4.9s continuous, strictly below 5.0s threshold
    ev3, rec3 = tracker.process_observation(face_count=0, timestamp=4.9)
    assert ev3 is None
    assert tracker.current_state == STATE_ABSENCE_CANDIDATE

    print("[OK] test_absence_under_threshold passed.")


def test_absence_at_and_over_threshold():
    """Verify that continuous absence >= 5 seconds triggers FACE_ABSENT."""
    tracker = ProctoringStateTracker()

    tracker.process_observation(face_count=0, timestamp=10.0)
    ev, rec = tracker.process_observation(face_count=0, timestamp=15.0)

    assert ev is not None
    assert rec is None
    assert ev["event_type"] == EVENT_FACE_ABSENT
    assert ev["sustained_duration_sec"] == 5.0
    assert ev["face_count"] == 0
    assert tracker.current_state == STATE_ABSENCE_SUSTAINED

    print("[OK] test_absence_at_and_over_threshold passed.")


def test_absence_jitter_reset():
    """Verify that transient single face resets the continuous absence timer."""
    tracker = ProctoringStateTracker()

    # Absence for 4.5 seconds
    tracker.process_observation(face_count=0, timestamp=0.0)
    tracker.process_observation(face_count=0, timestamp=4.5)
    assert tracker.current_state == STATE_ABSENCE_CANDIDATE

    # Brief face appearance at 4.6s (jitter / head turn)
    ev_norm, rec_norm = tracker.process_observation(face_count=1, timestamp=4.6)
    assert ev_norm is None
    assert tracker.current_state == STATE_NORMAL

    # Absence begins anew at 5.0s and reaches 7.0s (only 2.0s continuous)
    tracker.process_observation(face_count=0, timestamp=5.0)
    ev_new, _ = tracker.process_observation(face_count=0, timestamp=7.0)

    # Must NOT emit event because continuous duration from 5.0s is only 2.0s
    assert ev_new is None
    assert tracker.current_state == STATE_ABSENCE_CANDIDATE

    print("[OK] test_absence_jitter_reset passed.")


def test_multiple_faces_threshold():
    """Verify that continuous multiple faces >= 3 seconds triggers MULTIPLE_FACES."""
    tracker = ProctoringStateTracker()

    # T = 0.0s: 2 faces observed
    ev1, _ = tracker.process_observation(face_count=2, timestamp=0.0)
    assert ev1 is None
    assert tracker.current_state == STATE_MULTI_CANDIDATE

    # T = 2.9s: Still under 3.0s threshold
    ev2, _ = tracker.process_observation(face_count=2, timestamp=2.9)
    assert ev2 is None
    assert tracker.current_state == STATE_MULTI_CANDIDATE

    # T = 3.0s: Exact threshold reached
    boxes = [{"x": 10, "y": 10, "w": 50, "h": 50}, {"x": 80, "y": 10, "w": 50, "h": 50}]
    ev3, _ = tracker.process_observation(face_count=2, bounding_boxes=boxes, timestamp=3.0)
    assert ev3 is not None
    assert ev3["event_type"] == EVENT_MULTIPLE_FACES
    assert ev3["sustained_duration_sec"] == 3.0
    assert ev3["face_count"] == 2
    assert ev3["bounding_boxes"] == boxes
    assert tracker.current_state == STATE_MULTI_SUSTAINED

    print("[OK] test_multiple_faces_threshold passed.")


def test_multiple_faces_jitter_reset():
    """Verify that single face resets the multiple faces continuous counter."""
    tracker = ProctoringStateTracker()

    tracker.process_observation(face_count=3, timestamp=0.0)
    tracker.process_observation(face_count=3, timestamp=2.5)

    # Return to 1 face at 2.6s
    tracker.process_observation(face_count=1, timestamp=2.6)
    assert tracker.current_state == STATE_NORMAL

    # Multiple faces resumed at 3.0s and checked at 4.5s (1.5s continuous)
    tracker.process_observation(face_count=2, timestamp=3.0)
    ev, _ = tracker.process_observation(face_count=2, timestamp=4.5)
    assert ev is None
    assert tracker.current_state == STATE_MULTI_CANDIDATE

    print("[OK] test_multiple_faces_jitter_reset passed.")


def test_cooldown_rate_limiting():
    """
    Verify that 20-second cooldown suppresses repeated events during
    continuous anomaly and emits only after the 20s interval elapses.
    """
    tracker = ProctoringStateTracker(absence_threshold_sec=5.0, cooldown_sec=20.0)

    emitted_timestamps = []

    # Simulate 60 seconds of continuous face absence evaluated every second
    for sec in range(0, 61):
        t = float(sec)
        ev, _ = tracker.process_observation(face_count=0, timestamp=t)
        if ev is not None:
            emitted_timestamps.append(t)

    # Expected emission times:
    # 5.0s: first sustained event
    # 25.0s: 20s cooldown expired and absence still continuous
    # 45.0s: 20s cooldown expired and absence still continuous
    assert emitted_timestamps == [5.0, 25.0, 45.0], f"Unexpected emission timestamps: {emitted_timestamps}"
    assert len(emitted_timestamps) == 3

    print("[OK] test_cooldown_rate_limiting passed.")


def test_independent_cooldowns_per_event_type():
    """Verify that cooldown for FACE_ABSENT does not block MULTIPLE_FACES."""
    tracker = ProctoringStateTracker(
        absence_threshold_sec=5.0,
        multi_face_threshold_sec=3.0,
        cooldown_sec=20.0,
    )

    # Trigger FACE_ABSENT at t=5.0s
    tracker.process_observation(face_count=0, timestamp=0.0)
    ev_abs, _ = tracker.process_observation(face_count=0, timestamp=5.0)
    assert ev_abs is not None
    assert ev_abs["event_type"] == EVENT_FACE_ABSENT

    # At t=6.0s, switch to multiple faces (t=6.0 to 9.0s -> 3.0s continuous)
    tracker.process_observation(face_count=2, timestamp=6.0)
    ev_multi, _ = tracker.process_observation(face_count=2, timestamp=9.0)

    # Despite 20s absence cooldown being active, MULTIPLE_FACES has its own independent cooldown
    assert ev_multi is not None
    assert ev_multi["event_type"] == EVENT_MULTIPLE_FACES
    assert ev_multi["sustained_duration_sec"] == 3.0

    print("[OK] test_independent_cooldowns_per_event_type passed.")


def test_recovery_tracking():
    """Verify that returning to exactly 1 face generates clean recovery information."""
    tracker = ProctoringStateTracker(absence_threshold_sec=5.0)

    # Trigger sustained absence from t=10.0 to t=15.0
    tracker.process_observation(face_count=0, timestamp=10.0)
    ev, rec1 = tracker.process_observation(face_count=0, timestamp=15.0)
    assert ev is not None
    assert rec1 is None
    assert tracker.current_state == STATE_ABSENCE_SUSTAINED

    # Recover to 1 face at t=18.5
    ev_rec, recovery = tracker.process_observation(face_count=1, timestamp=18.5)
    assert ev_rec is None
    assert recovery is not None
    assert recovery["recovered_from"] == EVENT_FACE_ABSENT
    assert recovery["total_anomaly_duration_sec"] == 8.5  # 18.5 - 10.0
    assert tracker.current_state == STATE_NORMAL
    assert tracker.last_recovered_time == 18.5

    # Subsequent normal frame produces no redundant recovery
    _, rec_subsequent = tracker.process_observation(face_count=1, timestamp=19.0)
    assert rec_subsequent is None

    print("[OK] test_recovery_tracking passed.")


def test_reset():
    """Verify that reset restores default state and timers."""
    tracker = ProctoringStateTracker()
    tracker.process_observation(face_count=0, timestamp=0.0)
    tracker.process_observation(face_count=0, timestamp=5.0)
    assert tracker.current_state == STATE_ABSENCE_SUSTAINED

    tracker.reset()
    assert tracker.current_state == STATE_NORMAL
    assert tracker._absence_start_time is None
    assert tracker._multi_face_start_time is None
    assert tracker.last_recovered_time is None

    print("[OK] test_reset passed.")


def main():
    print("=" * 70)
    print("RUNNING PROCTORING STATE TRACKER UNIT TESTS")
    print("=" * 70)

    test_absence_under_threshold()
    test_absence_at_and_over_threshold()
    test_absence_jitter_reset()
    test_multiple_faces_threshold()
    test_multiple_faces_jitter_reset()
    test_cooldown_rate_limiting()
    test_independent_cooldowns_per_event_type()
    test_recovery_tracking()
    test_reset()

    print("\n" + "=" * 70)
    print("ALL 9 PROCTORING STATE TRACKER TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()
