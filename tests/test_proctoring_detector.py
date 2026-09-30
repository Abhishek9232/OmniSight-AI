"""
Focused Unit Test Suite for OpenCV FaceDetector Component.
Verifies detector initialization, input validation, output contracts, channel handling,
configurable parameters, and failure safety.
"""

import sys
import os
from unittest.mock import patch, MagicMock
import numpy as np

workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

from src.proctoring.detector import (
    FaceDetector,
    DEFAULT_SCALE_FACTOR,
    DEFAULT_MIN_NEIGHBORS,
    DEFAULT_MIN_SIZE,
)


def test_initialization_valid():
    """Verify that FaceDetector initializes correctly with project-managed cascade."""
    detector = FaceDetector()
    assert os.path.exists(detector.cascade_path), f"Cascade file does not exist at {detector.cascade_path}"
    assert detector.is_ready is True, f"Detector failed to initialize: {detector.init_error}"
    assert detector.init_error is None
    assert detector.scale_factor == DEFAULT_SCALE_FACTOR
    assert detector.min_neighbors == DEFAULT_MIN_NEIGHBORS
    assert detector.min_size == DEFAULT_MIN_SIZE
    print("[OK] test_initialization_valid passed.")


def test_initialization_missing_cascade():
    """Verify that FaceDetector fails safely when cascade XML file is missing."""
    detector = FaceDetector(cascade_path="non_existent_haarcascade_file.xml")
    assert detector.is_ready is False
    assert detector.init_error is not None
    assert "not found" in detector.init_error.lower()

    # Verify that calling detect_faces on uninitialized detector returns clean error contract
    res = detector.detect_faces(np.zeros((100, 100, 3), dtype=np.uint8))
    assert res["success"] is False
    assert res["face_count"] == 0
    assert res["faces"] == []
    assert "Detector not initialized" in res["error"]
    print("[OK] test_initialization_missing_cascade passed.")


def test_invalid_inputs():
    """Verify that detect_faces handles corrupted and invalid frame inputs gracefully."""
    detector = FaceDetector()

    # 1. None frame
    res_none = detector.detect_faces(None)
    assert res_none["success"] is False
    assert res_none["face_count"] == 0
    assert "Input frame is None" in res_none["error"]

    # 2. Non-numpy input
    res_str = detector.detect_faces("invalid_frame_string")
    assert res_str["success"] is False
    assert res_str["face_count"] == 0
    assert "must be a numpy.ndarray" in res_str["error"]

    # 3. Empty numpy array
    res_empty = detector.detect_faces(np.array([]))
    assert res_empty["success"] is False
    assert res_empty["face_count"] == 0
    assert "is empty" in res_empty["error"]

    # 4. Invalid dimensions (1D array)
    res_1d = detector.detect_faces(np.zeros((100,), dtype=np.uint8))
    assert res_1d["success"] is False
    assert res_1d["face_count"] == 0
    assert "Invalid frame dimensions" in res_1d["error"]

    # 5. Unsupported channel count (5-channel array)
    res_5ch = detector.detect_faces(np.zeros((100, 100, 5), dtype=np.uint8))
    assert res_5ch["success"] is False
    assert res_5ch["face_count"] == 0
    assert "Unsupported frame channel count: 5" in res_5ch["error"]

    print("[OK] test_invalid_inputs passed.")


def test_zero_faces_detection():
    """Verify that a frame containing zero faces returns 0 count and empty faces list."""
    detector = FaceDetector()

    # Solid blank frame (no human face features)
    blank_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    res = detector.detect_faces(blank_frame)

    assert res["success"] is True
    assert res["face_count"] == 0
    assert isinstance(res["faces"], list)
    assert len(res["faces"]) == 0
    assert res["error"] is None
    print("[OK] test_zero_faces_detection passed.")


def test_one_and_multiple_faces_contract():
    """
    Verify clean dictionary output contracts for 1 face and multiple faces.
    Uses synthetic detection fixture to test contract invariants deterministically.
    """
    detector = FaceDetector()
    frame = np.zeros((240, 320, 3), dtype=np.uint8)

    # 1. Test Single Face Detection Contract
    mock_clf1 = MagicMock()
    mock_clf1.empty.return_value = False
    mock_clf1.detectMultiScale.return_value = np.array([[100, 80, 120, 120]])
    with patch.object(detector, "_classifier", mock_clf1):
        res1 = detector.detect_faces(frame)
        assert res1["success"] is True
        assert res1["face_count"] == 1
        assert len(res1["faces"]) == 1
        face = res1["faces"][0]
        assert face == {"x": 100, "y": 80, "w": 120, "h": 120}
        assert isinstance(face["x"], int)
        assert isinstance(face["y"], int)
        assert isinstance(face["w"], int)
        assert isinstance(face["h"], int)

    # 2. Test Multiple Faces Detection Contract
    multi_rects = np.array([[50, 40, 60, 60], [180, 70, 55, 55]])
    mock_clf2 = MagicMock()
    mock_clf2.empty.return_value = False
    mock_clf2.detectMultiScale.return_value = multi_rects
    with patch.object(detector, "_classifier", mock_clf2):
        res2 = detector.detect_faces(frame)
        assert res2["success"] is True
        assert res2["face_count"] == 2
        assert len(res2["faces"]) == 2
        assert res2["faces"][0] == {"x": 50, "y": 40, "w": 60, "h": 60}
        assert res2["faces"][1] == {"x": 180, "y": 70, "w": 55, "h": 55}

    print("[OK] test_one_and_multiple_faces_contract passed.")


def test_supported_channel_formats():
    """Verify that Grayscale, BGR, RGB, and BGRA frame formats are processed correctly."""
    detector = FaceDetector()

    # 1. 2D Grayscale
    gray_frame = np.zeros((100, 100), dtype=np.uint8)
    res_gray = detector.detect_faces(gray_frame)
    assert res_gray["success"] is True

    # 2. 3-Channel BGR / RGB
    bgr_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    res_bgr = detector.detect_faces(bgr_frame)
    assert res_bgr["success"] is True

    # 3. 4-Channel BGRA / RGBA
    bgra_frame = np.zeros((100, 100, 4), dtype=np.uint8)
    res_bgra = detector.detect_faces(bgra_frame)
    assert res_bgra["success"] is True

    # 4. 3D Single Channel
    ch1_frame = np.zeros((100, 100, 1), dtype=np.uint8)
    res_ch1 = detector.detect_faces(ch1_frame)
    assert res_ch1["success"] is True

    print("[OK] test_supported_channel_formats passed.")


def test_configurable_parameters():
    """Verify that custom detector parameters are accepted and passed to the classifier."""
    custom_scale = 1.2
    custom_neighbors = 6
    custom_min_size = (45, 45)

    detector = FaceDetector(
        scale_factor=custom_scale,
        min_neighbors=custom_neighbors,
        min_size=custom_min_size,
    )

    assert detector.scale_factor == custom_scale
    assert detector.min_neighbors == custom_neighbors
    assert detector.min_size == custom_min_size

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    mock_clf = MagicMock()
    mock_clf.empty.return_value = False
    mock_clf.detectMultiScale.return_value = []
    with patch.object(detector, "_classifier", mock_clf):
        detector.detect_faces(frame)
        assert mock_clf.detectMultiScale.called
        kwargs = mock_clf.detectMultiScale.call_args[1]
        assert kwargs["scaleFactor"] == custom_scale
        assert kwargs["minNeighbors"] == custom_neighbors
        assert kwargs["minSize"] == custom_min_size

    print("[OK] test_configurable_parameters passed.")


def test_failure_safety_on_detector_exception():
    """Verify that any unexpected OpenCV exception during detection is trapped safely."""
    detector = FaceDetector()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    mock_clf = MagicMock()
    mock_clf.empty.return_value = False
    mock_clf.detectMultiScale.side_effect = RuntimeError("Simulated OpenCV crash")
    with patch.object(detector, "_classifier", mock_clf):
        res = detector.detect_faces(frame)
        assert res["success"] is False
        assert res["face_count"] == 0
        assert res["faces"] == []
        assert "Simulated OpenCV crash" in res["error"]

    print("[OK] test_failure_safety_on_detector_exception passed.")


def main():
    print("=" * 70)
    print("RUNNING PROCTORING FACE DETECTOR UNIT TESTS")
    print("=" * 70)

    test_initialization_valid()
    test_initialization_missing_cascade()
    test_invalid_inputs()
    test_zero_faces_detection()
    test_one_and_multiple_faces_contract()
    test_supported_channel_formats()
    test_configurable_parameters()
    test_failure_safety_on_detector_exception()

    print("\n" + "=" * 70)
    print("ALL 8 PROCTORING DETECTOR TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()
