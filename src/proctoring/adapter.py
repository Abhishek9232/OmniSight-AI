"""
OmniSight-AI Proctoring Frame Input Adapter Module.
Defines the abstract boundary between video frame acquisition and proctoring evaluation.
Decouples proctoring logic from specific webcam drivers, browser APIs, or UI frameworks.
Allows pluggable frame sources including physical cameras, Streamlit adapters, and test fixtures.
"""

from abc import ABC, abstractmethod
from typing import Optional
import numpy as np


class FrameInputAdapter(ABC):
    """
    Abstract interface for video frame acquisition.
    Implementations provide image frames on demand to the proctoring session.
    """

    @abstractmethod
    def get_frame(self) -> Optional[np.ndarray]:
        """
        Acquire the latest video frame.

        Returns:
            numpy.ndarray representing an image frame (BGR, RGB, or Grayscale),
            or None if no frame is currently available.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the frame source is operational and accessible, False otherwise."""
        pass


class NullFrameAdapter(FrameInputAdapter):
    """
    Default fallback adapter when no physical or UI camera is attached.
    Safe, non-blocking, zero-overhead, always returns None.
    """

    def get_frame(self) -> Optional[np.ndarray]:
        """Always returns None since no camera source is attached."""
        return None

    def is_available(self) -> bool:
        """Indicates no camera is attached."""
        return False


class SimulatedFrameAdapter(FrameInputAdapter):
    """
    Simulated frame adapter for unit and integration testing.
    Allows injecting explicit image arrays or simulating camera disconnection.
    """

    def __init__(self, initial_frame: Optional[np.ndarray] = None) -> None:
        self._current_frame: Optional[np.ndarray] = initial_frame
        self._available: bool = True

    def set_frame(self, frame: Optional[np.ndarray]) -> None:
        """Set or update the active simulated frame."""
        self._current_frame = frame

    def set_available(self, available: bool) -> None:
        """Simulate camera connection or disconnection."""
        self._available = available

    def get_frame(self) -> Optional[np.ndarray]:
        """Return the current simulated frame if available, else None."""
        if not self._available:
            return None
        return self._current_frame

    def is_available(self) -> bool:
        """Return simulated availability status."""
        return self._available
