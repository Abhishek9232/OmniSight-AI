"""
OmniSight-AI Proctoring Temporal State Tracking Engine.
Converts instantaneous perception observations into sustained monitoring events.
Strictly in-memory and deterministic: tracks continuous duration, cooldowns, and recovery
using monotonic time (time.monotonic) to guarantee immunity to wall-clock skew.
"""

from typing import Dict, Any, List, Optional, Tuple
import time


# Domain event types
EVENT_FACE_ABSENT = "FACE_ABSENT"
EVENT_MULTIPLE_FACES = "MULTIPLE_FACES"

# System monitoring states
STATE_NORMAL = "NORMAL"
STATE_ABSENCE_CANDIDATE = "ABSENCE_CANDIDATE"
STATE_ABSENCE_SUSTAINED = "ABSENCE_SUSTAINED"
STATE_MULTI_CANDIDATE = "MULTI_CANDIDATE"
STATE_MULTI_SUSTAINED = "MULTI_SUSTAINED"

# Default temporal thresholds (in seconds)
DEFAULT_ABSENCE_THRESHOLD_SEC = 5.0
DEFAULT_MULTI_FACE_THRESHOLD_SEC = 3.0
DEFAULT_COOLDOWN_SEC = 20.0


class ProctoringStateTracker:
    """
    In-memory state machine tracking temporal continuity of proctoring observations.
    Evaluates successive face detection outputs and triggers sustained events
    while suppressing transient fluctuations (jitter) and rate-limiting via cooldowns.
    """

    def __init__(
        self,
        absence_threshold_sec: float = DEFAULT_ABSENCE_THRESHOLD_SEC,
        multi_face_threshold_sec: float = DEFAULT_MULTI_FACE_THRESHOLD_SEC,
        cooldown_sec: float = DEFAULT_COOLDOWN_SEC,
    ) -> None:
        """
        Initialize the state tracker with configurable temporal thresholds.

        Args:
            absence_threshold_sec: Continuous seconds of 0 faces required to emit FACE_ABSENT.
            multi_face_threshold_sec: Continuous seconds of >1 faces required to emit MULTIPLE_FACES.
            cooldown_sec: Minimum seconds required between consecutive events of the same type.
        """
        self.absence_threshold_sec = float(absence_threshold_sec)
        self.multi_face_threshold_sec = float(multi_face_threshold_sec)
        self.cooldown_sec = float(cooldown_sec)

        self._current_state: str = STATE_NORMAL

        # Monotonic start timestamps for candidate conditions
        self._absence_start_time: Optional[float] = None
        self._multi_face_start_time: Optional[float] = None

        # Monotonic timestamps of last emitted events for cooldown enforcement
        self._last_event_time: Dict[str, float] = {
            EVENT_FACE_ABSENT: -float("inf"),
            EVENT_MULTIPLE_FACES: -float("inf"),
        }

        # Monotonic timestamp of last recovery to NORMAL
        self._last_recovered_time: Optional[float] = None

    @property
    def current_state(self) -> str:
        """Return the current active state of the state machine."""
        return self._current_state

    @property
    def last_recovered_time(self) -> Optional[float]:
        """Return monotonic timestamp of the most recent recovery to NORMAL."""
        return self._last_recovered_time

    def process_observation(
        self,
        face_count: int,
        bounding_boxes: Optional[List[Dict[str, int]]] = None,
        timestamp: Optional[float] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Process an instantaneous face detection observation.

        Args:
            face_count: Number of faces detected in the current frame.
            bounding_boxes: Optional list of bounding box dicts [{"x", "y", "w", "h"}].
            timestamp: Monotonic timestamp (float seconds). If None, defaults to time.monotonic().

        Returns:
            Tuple of (emitted_event_or_None, recovery_info_or_None)
            - emitted_event: Dict containing event details if a sustained threshold and cooldown
              are satisfied, else None.
            - recovery_info: Dict containing recovery transition details if returning to NORMAL
              from a sustained anomaly, else None.
        """
        # Monotonic clock guarantees strictly forward, skew-free duration calculation
        now = time.monotonic() if timestamp is None else float(timestamp)
        boxes = bounding_boxes if bounding_boxes is not None else []

        emitted_event: Optional[Dict[str, Any]] = None
        recovery_info: Optional[Dict[str, Any]] = None

        # -------------------------------------------------------------
        # Branch 1: Face Absence (face_count == 0)
        # -------------------------------------------------------------
        if face_count == 0:
            # Clear multi-face tracking if previously active
            self._multi_face_start_time = None

            if self._absence_start_time is None:
                self._absence_start_time = now
                self._current_state = STATE_ABSENCE_CANDIDATE

            continuous_duration = now - self._absence_start_time

            if continuous_duration >= self.absence_threshold_sec:
                self._current_state = STATE_ABSENCE_SUSTAINED
                cooldown_elapsed = now - self._last_event_time[EVENT_FACE_ABSENT]

                if cooldown_elapsed >= self.cooldown_sec:
                    self._last_event_time[EVENT_FACE_ABSENT] = now
                    emitted_event = {
                        "event_type": EVENT_FACE_ABSENT,
                        "sustained_duration_sec": round(continuous_duration, 3),
                        "threshold_sec": self.absence_threshold_sec,
                        "cooldown_applied_sec": self.cooldown_sec,
                        "face_count": 0,
                        "bounding_boxes": [],
                        "monotonic_timestamp": now,
                    }

            return emitted_event, None

        # -------------------------------------------------------------
        # Branch 2: Multiple Faces (face_count > 1)
        # -------------------------------------------------------------
        elif face_count > 1:
            # Clear absence tracking if previously active
            self._absence_start_time = None

            if self._multi_face_start_time is None:
                self._multi_face_start_time = now
                self._current_state = STATE_MULTI_CANDIDATE

            continuous_duration = now - self._multi_face_start_time

            if continuous_duration >= self.multi_face_threshold_sec:
                self._current_state = STATE_MULTI_SUSTAINED
                cooldown_elapsed = now - self._last_event_time[EVENT_MULTIPLE_FACES]

                if cooldown_elapsed >= self.cooldown_sec:
                    self._last_event_time[EVENT_MULTIPLE_FACES] = now
                    emitted_event = {
                        "event_type": EVENT_MULTIPLE_FACES,
                        "sustained_duration_sec": round(continuous_duration, 3),
                        "threshold_sec": self.multi_face_threshold_sec,
                        "cooldown_applied_sec": self.cooldown_sec,
                        "face_count": face_count,
                        "bounding_boxes": boxes,
                        "monotonic_timestamp": now,
                    }

            return emitted_event, None

        # -------------------------------------------------------------
        # Branch 3: Normal Baseline (face_count == 1)
        # -------------------------------------------------------------
        else:
            # Check if recovering from an active anomaly
            if self._current_state in (STATE_ABSENCE_SUSTAINED, STATE_MULTI_SUSTAINED):
                recovered_from = (
                    EVENT_FACE_ABSENT
                    if self._current_state == STATE_ABSENCE_SUSTAINED
                    else EVENT_MULTIPLE_FACES
                )
                start_time = (
                    self._absence_start_time
                    if recovered_from == EVENT_FACE_ABSENT
                    else self._multi_face_start_time
                )
                total_anomaly_duration = (
                    round(now - start_time, 3) if start_time is not None else 0.0
                )
                recovery_info = {
                    "recovered_from": recovered_from,
                    "total_anomaly_duration_sec": total_anomaly_duration,
                    "monotonic_timestamp": now,
                }

            # Reset candidate timers
            self._absence_start_time = None
            self._multi_face_start_time = None
            self._current_state = STATE_NORMAL
            self._last_recovered_time = now

            return None, recovery_info

    def reset(self) -> None:
        """Reset the state machine back to its initial NORMAL state."""
        self._current_state = STATE_NORMAL
        self._absence_start_time = None
        self._multi_face_start_time = None
        self._last_event_time = {
            EVENT_FACE_ABSENT: -float("inf"),
            EVENT_MULTIPLE_FACES: -float("inf"),
        }
        self._last_recovered_time = None
