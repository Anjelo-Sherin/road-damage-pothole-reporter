import pytest
from pathlib import Path
from src.pdf_generator import generate_complaint_pdf

def test_generate_pdf():
    cluster_mock = {
        "id": 999,
        "damage_class": "D40",
        "severity_score": 92.5,
        "severity_tier": "Critical",
        "road_name": "MG Road Expressway (KM 12)",
        "lat": 12.9716,
        "lon": 77.5946,
        "priority": "Emergency (24h)",
        "repair_cost_est": 850.0,
        "detection_count": 4,
        "work_order_id": "WO-2026-TEST"
    }

    pdf_path = generate_complaint_pdf(cluster_mock, "TEST-REF-001")
    assert Path(pdf_path).exists()
    assert Path(pdf_path).stat().st_size > 1000  # Non-empty valid PDF
