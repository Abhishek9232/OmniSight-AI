"""
OmniSight-AI Proctoring Session Coordinator.
Encapsulates face detection, temporal state tracking, and event persistence for an attempt.
Enforces complete failure isolation: perception or database errors never bubble up
to interrupt the student or examination workflow.

Temporal Precision & Latency:
- Frame sampling operates at approximately 1 FPS (~1.0s interval).
- State continuity calculations use time.monotonic() to eliminate wall-clock drift.
- The temporal detection precision of sustained events (5s absence, 3s multiple faces)
  is approximately bounded by the sampling interval (± ~1.0s).
"""

from typing import Optional, Dict, Any
from src.proctoring.detector import FaceDetector
from src.proctoring.state import ProctoringStateTracker
from src.proctoring.service import record_monitoring_event
from src.proctoring.adapter import FrameInputAdapter, NullFrameAdapter


class ProctoringSession:
    """
    Stateful session coordinator bound to a specific examination attempt.
    Coordinates FaceDetector perception with ProctoringStateTracker continuity,
    automatically persisting validated, sustained events to MySQL.
    """

    def __init__(
        self,
        attempt_id: int,
        detector: Optional[FaceDetector] = None,
        tracker: Optional[ProctoringStateTracker] = None,
        frame_adapter: Optional[FrameInputAdapter] = None,
    ) -> None:
        """
        Initialize a proctoring session for a given attempt.

        Args:
            attempt_id: Target exam attempt ID.
            detector: Optional pre-configured FaceDetector instance (instantiates default if None).
            tracker: Optional pre-configured ProctoringStateTracker instance (instantiates default if None).
            frame_adapter: Optional FrameInputAdapter instance (defaults to NullFrameAdapter if None).
        """
        if not isinstance(attempt_id, int) or attempt_id <= 0:
            raise ValueError("Valid attempt_id must be a positive integer.")

        self.attempt_id = attempt_id
        self.detector = detector if detector is not None else FaceDetector()
        self.tracker = tracker if tracker is not None else ProctoringStateTracker()
        self.frame_adapter = frame_adapter if frame_adapter is not None else NullFrameAdapter()
        self._is_active = True

    @property
    def is_active(self) -> bool:
        """Return True if session is open, False if closed."""
        return self._is_active

    def process_frame(
        self,
        frame: Any,
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Process a single video frame through perception, state tracking, and persistence.
        Guaranteed to never raise an unhandled exception to the caller.

        Args:
            frame: Video frame (expected as numpy.ndarray).
            timestamp: Monotonic timestamp (float seconds) for deterministic time control.

        Returns:
            Dict conforming to the execution contract:
            {
                "success": bool,
                "face_count": int,
                "faces": List[Dict[str, int]],
                "state": str,
                "event_emitted": bool,
                "event": Optional[Dict[str, Any]],
                "persistence_result": Optional[Dict[str, Any]],
                "recovery": bool,
                "recovery_info": Optional[Dict[str, Any]],
                "error": Optional[str]
            }
        """
        if not self._is_active:
            return {
                "success": False,
                "face_count": 0,
                "faces": [],
                "state": self.tracker.current_state,
                "event_emitted": False,
                "event": None,
                "persistence_result": None,
                "recovery": False,
                "recovery_info": None,
                "error": "ProctoringSession is closed.",
            }

        try:
            # 1. Perception phase (stateless)
            det_result = self.detector.detect_faces(frame)
            if not det_result["success"]:
                return {
                    "success": False,
                    "face_count": 0,
                    "faces": [],
                    "state": self.tracker.current_state,
                    "event_emitted": False,
                    "event": None,
                    "persistence_result": None,
                    "recovery": False,
                    "recovery_info": None,
                    "error": f"Perception error: {det_result.get('error')}",
                }

            face_count = det_result["face_count"]
            faces = det_result["faces"]

            # 2. Temporal continuity tracking (in-memory, monotonic)
            emitted_event, recovery_info = self.tracker.process_observation(
                face_count=face_count,
                bounding_boxes=faces,
                timestamp=timestamp,
            )

            # 3. Persistence phase (atomic attempt guard)
            persistence_result: Optional[Dict[str, Any]] = None
            if emitted_event is not None:
                persistence_result = record_monitoring_event(
                    attempt_id=self.attempt_id,
                    event_type=emitted_event["event_type"],
                    event_metadata=emitted_event,
                )

            return {
                "success": True,
                "face_count": face_count,
                "faces": faces,
                "state": self.tracker.current_state,
                "event_emitted": emitted_event is not None,
                "event": emitted_event,
                "persistence_result": persistence_result,
                "recovery": recovery_info is not None,
                "recovery_info": recovery_info,
                "error": None,
            }

        except Exception as e:
            # Failure isolation: suppress all unexpected internal errors
            return {
                "success": False,
                "face_count": 0,
                "faces": [],
                "state": self.tracker.current_state,
                "event_emitted": False,
                "event": None,
                "persistence_result": None,
                "recovery": False,
                "recovery_info": None,
                "error": f"Proctoring session processing failure: {str(e)}",
            }

    def process_sample(self, timestamp: Optional[float] = None) -> Dict[str, Any]:
        """
        Acquire a frame from the configured frame_adapter and process it.
        If no frame is available or adapter reports unavailable, returns safely with zero side effects.

        Args:
            timestamp: Monotonic timestamp (float seconds).

        Returns:
            Dict conforming to execution contract.
        """
        if not self._is_active:
            return {
                "success": False,
                "face_count": 0,
                "faces": [],
                "state": self.tracker.current_state,
                "event_emitted": False,
                "event": None,
                "persistence_result": None,
                "recovery": False,
                "recovery_info": None,
                "error": "ProctoringSession is closed.",
            }

        try:
            if not self.frame_adapter.is_available():
                return {
                    "success": True,
                    "face_count": 0,
                    "faces": [],
                    "state": self.tracker.current_state,
                    "event_emitted": False,
                    "event": None,
                    "persistence_result": None,
                    "recovery": False,
                    "recovery_info": None,
                    "error": None,
                    "skipped": True,
                }

            frame = self.frame_adapter.get_frame()
            if frame is None:
                return {
                    "success": True,
                    "face_count": 0,
                    "faces": [],
                    "state": self.tracker.current_state,
                    "event_emitted": False,
                    "event": None,
                    "persistence_result": None,
                    "recovery": False,
                    "recovery_info": None,
                    "error": None,
                    "skipped": True,
                }

            return self.process_frame(frame, timestamp=timestamp)

        except Exception as e:
            return {
                "success": False,
                "face_count": 0,
                "faces": [],
                "state": self.tracker.current_state,
                "event_emitted": False,
                "event": None,
                "persistence_result": None,
                "recovery": False,
                "recovery_info": None,
                "error": f"Adapter sampling error: {str(e)}",
            }

    def reset(self) -> None:
        """Reset the internal state tracker."""
        self.tracker.reset()

    def close(self) -> None:
        """Close the session and prevent further frame processing."""
        self._is_active = False

    def stop(self) -> None:
        """Stop and close the session (alias for close)."""
        self.close()
