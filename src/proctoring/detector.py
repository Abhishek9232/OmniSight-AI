"""
OmniSight-AI Stateless OpenCV Face Detection Module.
Provides deterministic face detection using OpenCV Haar Cascades.
Strictly stateless: answers only "What faces are observable in this frame?"
Zero dependency on Streamlit, MySQL, session state, or proctoring scoring.
"""

from typing import Dict, Any, List, Optional, Tuple, Union
import os
import numpy as np

# Safe conditional import of OpenCV
try:
    import cv2
    _OPENCV_AVAILABLE = True
except ImportError:
    cv2 = None
    _OPENCV_AVAILABLE = False


# Sensible MVP configuration defaults:
# - scale_factor = 1.1: Standard window scaling factor (10% per pass), balancing speed and detection granularity.
# - min_neighbors = 5: Quality candidate threshold, suppressing spurious background noise while reliably detecting faces.
# - min_size = (30, 30): Minimum bounding box dimensions, filtering out micro visual artifacts.
DEFAULT_SCALE_FACTOR = 1.1
DEFAULT_MIN_NEIGHBORS = 5
DEFAULT_MIN_SIZE = (30, 30)

# Project-managed Haar Cascade path:
# Resolves to <project_root>/assets/haarcascades/haarcascade_frontalface_default.xml
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, "..", ".."))
DEFAULT_CASCADE_PATH = os.path.join(
    _PROJECT_ROOT, "assets", "haarcascades", "haarcascade_frontalface_default.xml"
)


class FaceDetector:
    """
    Stateless OpenCV Haar Cascade face detector.
    Evaluates individual image frames and returns detected face counts and bounding boxes.
    """

    def __init__(
        self,
        cascade_path: Optional[str] = None,
        scale_factor: float = DEFAULT_SCALE_FACTOR,
        min_neighbors: int = DEFAULT_MIN_NEIGHBORS,
        min_size: Tuple[int, int] = DEFAULT_MIN_SIZE,
    ):
        """
        Initialize the FaceDetector with configurable detection parameters.

        Args:
            cascade_path: Path to Haar Cascade XML file. If None, resolves to project-managed
                          assets/haarcascades/haarcascade_frontalface_default.xml.
            scale_factor: MultiScale search window scaling factor (> 1.0).
            min_neighbors: Minimum candidate neighbor rectangles required to retain a face.
            min_size: Minimum bounding box size tuple (width, height) in pixels.
        """
        self.scale_factor = float(scale_factor) if scale_factor > 1.0 else DEFAULT_SCALE_FACTOR
        self.min_neighbors = int(min_neighbors) if min_neighbors >= 1 else DEFAULT_MIN_NEIGHBORS
        self.min_size = min_size if isinstance(min_size, (tuple, list)) and len(min_size) == 2 else DEFAULT_MIN_SIZE

        self._classifier: Optional[Any] = None
        self._init_error: Optional[str] = None

        # Resolve cascade XML path deterministically
        self.cascade_path = cascade_path if cascade_path is not None else DEFAULT_CASCADE_PATH

        if not _OPENCV_AVAILABLE:
            self._init_error = "OpenCV (cv2) library is not installed or unavailable in the environment."
            return

        if not hasattr(cv2, "CascadeClassifier"):
            self._init_error = (
                f"OpenCV ({getattr(cv2, '__version__', 'unknown')}) does not support CascadeClassifier. "
                "OpenCV 4.x (opencv-python-headless<5) is required for Haar cascades."
            )
            return

        # Validate file existence and load classifier safely
        try:
            if not os.path.exists(self.cascade_path):
                self._init_error = f"Haar cascade XML file not found at: {self.cascade_path}"
                return

            self._classifier = cv2.CascadeClassifier(self.cascade_path)
            if self._classifier.empty():
                self._classifier = None
                self._init_error = f"Failed to initialize CascadeClassifier from: {self.cascade_path}"
        except Exception as e:
            self._classifier = None
            self._init_error = f"OpenCV CascadeClassifier initialization error: {str(e)}"

    @property
    def is_ready(self) -> bool:
        """Return True if the detector successfully initialized its classifier, False otherwise."""
        return self._classifier is not None and self._init_error is None

    @property
    def init_error(self) -> Optional[str]:
        """Return the initialization error string if failed, or None if ready."""
        return self._init_error

    def detect_faces(self, frame: Any) -> Dict[str, Any]:
        """
        Detect human faces within a single image/frame.

        Args:
            frame: Image input, expected as a numpy ndarray (Grayscale, BGR, RGB, or BGRA).

        Returns:
            Dict conforming to the deterministic detection contract:
            {
                "success": bool,
                "face_count": int,
                "faces": List[Dict[str, int]],  # Each item: {"x": int, "y": int, "w": int, "h": int}
                "error": Optional[str]
            }
        """
        # 1. Guard against initialization failure
        if not self.is_ready:
            return {
                "success": False,
                "face_count": 0,
                "faces": [],
                "error": f"Detector not initialized: {self._init_error}",
            }

        # 2. Input validation: None check
        if frame is None:
            return {
                "success": False,
                "face_count": 0,
                "faces": [],
                "error": "Input frame is None.",
            }

        # 3. Input validation: Type check
        if not isinstance(frame, np.ndarray):
            return {
                "success": False,
                "face_count": 0,
                "faces": [],
                "error": f"Input frame must be a numpy.ndarray, got {type(frame).__name__}.",
            }

        # 4. Input validation: Empty array check
        if frame.size == 0:
            return {
                "success": False,
                "face_count": 0,
                "faces": [],
                "error": "Input frame array is empty (size 0).",
            }

        # 5. Channel conversion and grayscale normalization
        try:
            if frame.ndim == 2:
                # Already single-channel grayscale
                gray = frame
            elif frame.ndim == 3:
                channels = frame.shape[2]
                if channels == 1:
                    gray = frame[:, :, 0]
                elif channels == 3:
                    # Treat standard 3-channel as BGR/RGB
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                elif channels == 4:
                    # Treat 4-channel as BGRA/RGBA
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
                else:
                    return {
                        "success": False,
                        "face_count": 0,
                        "faces": [],
                        "error": f"Unsupported frame channel count: {channels}.",
                    }
            else:
                return {
                    "success": False,
                    "face_count": 0,
                    "faces": [],
                    "error": f"Invalid frame dimensions: {frame.ndim} (expected 2 or 3).",
                }

            # Ensure contiguous uint8 data type for OpenCV C++ operations
            if gray.dtype != np.uint8:
                gray = np.clip(gray, 0, 255).astype(np.uint8)

            # Preprocessing: Equalize histogram for illumination normalization
            gray_eq = cv2.equalizeHist(gray)

            # 6. Execute Haar Cascade multi-scale detection
            raw_detections = self._classifier.detectMultiScale(
                gray_eq,
                scaleFactor=self.scale_factor,
                minNeighbors=self.min_neighbors,
                minSize=self.min_size,
            )

            # 7. Format clean, sanitized bounding box dictionaries
            faces: List[Dict[str, int]] = []
            if raw_detections is not None and len(raw_detections) > 0:
                for det in raw_detections:
                    faces.append({
                        "x": int(det[0]),
                        "y": int(det[1]),
                        "w": int(det[2]),
                        "h": int(det[3]),
                    })

            return {
                "success": True,
                "face_count": len(faces),
                "faces": faces,
                "error": None,
            }

        except Exception as e:
            # Trapped exception ensures no OpenCV runtime errors escape
            return {
                "success": False,
                "face_count": 0,
                "faces": [],
                "error": f"Face detection processing error: {str(e)}",
            }
