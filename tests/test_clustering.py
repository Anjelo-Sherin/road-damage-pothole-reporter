import pytest
from src.clustering import perform_dbscan_clustering

def test_dbscan_deduplication():
    # 3 detections of the same pothole within 5 meters
    base_lat = 12.97160
    base_lon = 77.59460
    dets = [
        {"lat": base_lat + 0.00001, "lon": base_lon, "damage_class": "D40", "confidence": 0.92, "bbox_area_ratio": 0.05, "severity_score": 85.0},
        {"lat": base_lat + 0.00002, "lon": base_lon, "damage_class": "D40", "confidence": 0.94, "bbox_area_ratio": 0.06, "severity_score": 88.0},
        {"lat": base_lat + 0.00003, "lon": base_lon, "damage_class": "D40", "confidence": 0.89, "bbox_area_ratio": 0.04, "severity_score": 82.0},
        # Another defect far away (150 meters away)
        {"lat": base_lat + 0.00150, "lon": base_lon, "damage_class": "D10", "confidence": 0.80, "bbox_area_ratio": 0.03, "severity_score": 50.0},
    ]

    clusters = perform_dbscan_clustering(dets, eps_meters=20.0, min_samples=1)
    # The 3 close detections must be merged into 1 cluster, and the far one forms a 2nd cluster
    assert len(clusters) == 2
    merged_cluster = next(c for c in clusters if c["damage_class"] == "D40")
    assert merged_cluster["detection_count"] == 3
