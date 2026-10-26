import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_status_endpoint():
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert data["service"] == "RoadPulse AI"

def test_stats_endpoint():
    res = client.get("/api/stats")
    assert res.status_code == 200
    data = res.json()
    assert "total_detections" in data
    assert "total_clusters" in data
    assert "dedupe_ratio_percent" in data

def test_clusters_endpoint():
    res = client.get("/api/clusters")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) > 0

def test_municipality_roads_endpoint():
    res = client.get("/api/municipality/roads")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
