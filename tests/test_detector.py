import pytest
import numpy as np
from src.detector import RoadDamageDetector

def test_detector_initialization():
    detector = RoadDamageDetector(min_confidence=0.5)
    assert detector.min_confidence == 0.5

def test_severity_calculation():
    detector = RoadDamageDetector()
    pothole_sev = detector.calculate_severity("D40", area_ratio=0.05, confidence=0.9)
    assert pothole_sev["score"] > 60.0
    assert pothole_sev["tier"] in ["High", "Critical"]

    crack_sev = detector.calculate_severity("D00", area_ratio=0.01, confidence=0.7)
    assert crack_sev["score"] < pothole_sev["score"]

def test_detector_empty_frame():
    detector = RoadDamageDetector()
    # Uniform black image with no road texture or contours
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = detector.analyze_frame(img)
    assert isinstance(detections, list)
