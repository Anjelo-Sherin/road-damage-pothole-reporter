import math
import numpy as np
from sklearn.cluster import DBSCAN
from typing import List, Dict, Any, Tuple
from src.config import DBSCAN_EPS_METERS, DBSCAN_MIN_SAMPLES, DAMAGE_CLASSES
from src.database import insert_cluster, update_detection_cluster_id
from src.geotagger import reverse_geocode_road

EARTH_RADIUS_METERS = 6371000.0

def perform_dbscan_clustering(
    detections: List[Dict[str, Any]],
    eps_meters: float = DBSCAN_EPS_METERS,
    min_samples: int = DBSCAN_MIN_SAMPLES
) -> List[Dict[str, Any]]:
    """
    Performs spatial deduplication using DBSCAN with haversine distance metric.
    Merges duplicate detections of the same pothole or crack across multiple frames
    or drives into a single canonical defect entity.
    """
    if not detections:
        return []

    # Convert lat/lon degrees to radians for scikit-learn haversine metric
    coords = np.array([[math.radians(d["lat"]), math.radians(d["lon"])] for d in detections])

    # eps in radians = eps_meters / earth_radius
    eps_radians = eps_meters / EARTH_RADIUS_METERS

    db = DBSCAN(eps=eps_radians, min_samples=min_samples, metric='haversine')
    labels = db.fit_predict(coords)

    # Group detections by cluster label
    clusters_map: Dict[int, List[Dict[str, Any]]] = {}
    for idx, label in enumerate(labels):
        if label not in clusters_map:
            clusters_map[label] = []
        clusters_map[label].append(detections[idx])

    canonical_clusters = []

    for label, group in clusters_map.items():
        # Representative detection: highest confidence and clearest image
        rep = max(group, key=lambda d: (d.get("confidence", 0.0), d.get("bbox_area_ratio", 0.0)))

        # Centroid coordinates
        avg_lat = sum(d["lat"] for d in group) / len(group)
        avg_lon = sum(d["lon"] for d in group) / len(group)

        # Primary class: highest severity class among the detections
        classes_present = [d["damage_class"] for d in group]
        # Pothole (D40) takes priority if present, then D20, then D10, then D00
        priority_order = ["D40", "D20", "D10", "D00"]
        dominant_class = rep.get("damage_class", "D40")
        for p_cls in priority_order:
            if p_cls in classes_present:
                dominant_class = p_cls
                break

        avg_conf = sum(d.get("confidence", 0.75) for d in group) / len(group)

        # Severity score aggregation: base max score + small frequency reinforcement
        max_score = max(d.get("severity_score", 40.0) for d in group)
        detection_count = len(group)
        freq_boost = min(15.0, (detection_count - 1) * 2.5)
        severity_score = round(min(100.0, max_score + freq_boost), 1)

        if severity_score >= 75.0:
            severity_tier = "Critical"
            priority = "Emergency (24-48h)"
            base_cost = 750.0
        elif severity_score >= 50.0:
            severity_tier = "High"
            priority = "Urgent (3-5 days)"
            base_cost = 480.0
        elif severity_score >= 30.0:
            severity_tier = "Medium"
            priority = "Routine (2 weeks)"
            base_cost = 260.0
        else:
            severity_tier = "Low"
            priority = "Monitoring"
            base_cost = 140.0

        if dominant_class == "D40":
            base_cost *= 1.4
        elif dominant_class == "D20":
            base_cost *= 1.25

        road = reverse_geocode_road(avg_lat, avg_lon)

        # Persist to database if detections have IDs
        rep_id = rep.get("id")
        cid = insert_cluster(
            cluster_label=int(label),
            representative_detection_id=rep_id,
            lat=round(avg_lat, 7),
            lon=round(avg_lon, 7),
            damage_class=dominant_class,
            avg_confidence=round(avg_conf, 3),
            severity_score=severity_score,
            severity_tier=severity_tier,
            detection_count=detection_count,
            road_name=road,
            status="Reported",
            priority=priority,
            repair_cost_est=round(base_cost, 2),
            work_order_id=f"WO-2026-{1000 + abs(int(label))}"
        )

        # Update member detections with their assigned cluster ID
        for member in group:
            if "id" in member and member["id"]:
                update_detection_cluster_id(member["id"], cid)

        canonical_clusters.append({
            "id": cid,
            "cluster_label": int(label),
            "lat": round(avg_lat, 7),
            "lon": round(avg_lon, 7),
            "damage_class": dominant_class,
            "class_name": DAMAGE_CLASSES.get(dominant_class, {}).get("name", "Defect"),
            "avg_confidence": round(avg_conf, 3),
            "severity_score": severity_score,
            "severity_tier": severity_tier,
            "detection_count": detection_count,
            "road_name": road,
            "priority": priority,
            "repair_cost_est": round(base_cost, 2),
            "representative_detection": rep,
            "status": "Reported"
        })

    return canonical_clusters
