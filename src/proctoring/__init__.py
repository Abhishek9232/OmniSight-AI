"""
OmniSight-AI Proctoring Subsystem Package.
Provides computer-vision-based examination monitoring, temporal state tracking,
transaction-safe event persistence, and frame input adapters.
"""

from src.proctoring.detector import FaceDetector
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
from src.proctoring.service import (
    record_monitoring_event,
    get_attempt_monitoring_events,
    get_monitoring_event_summary,
)
from src.proctoring.adapter import (
    FrameInputAdapter,
    NullFrameAdapter,
    SimulatedFrameAdapter,
)
from src.proctoring.session import ProctoringSession

__all__ = [
    "FaceDetector",
    "ProctoringStateTracker",
    "ProctoringSession",
    "FrameInputAdapter",
    "NullFrameAdapter",
    "SimulatedFrameAdapter",
    "record_monitoring_event",
    "get_attempt_monitoring_events",
    "get_monitoring_event_summary",
    "EVENT_FACE_ABSENT",
    "EVENT_MULTIPLE_FACES",
    "STATE_NORMAL",
    "STATE_ABSENCE_CANDIDATE",
    "STATE_ABSENCE_SUSTAINED",
    "STATE_MULTI_CANDIDATE",
    "STATE_MULTI_SUSTAINED",
]
