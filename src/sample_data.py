import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from typing import List, Dict, Any

from src.config import SAMPLES_DIR, DAMAGE_CLASSES
from src.database import get_connection, insert_drive, insert_detection
from src.geotagger import generate_sample_track, reverse_geocode_road
from src.clustering import perform_dbscan_clustering

def create_synthetic_road_defect_image(
    filename: str,
    defect_type: str = "D40",
    defect_size: str = "large"
) -> str:
    """
    Synthesizes a realistic dashcam perspective image of asphalt roadway
    with asphalt texture, perspective lane markings, and an authentic road defect
    (pothole cavity or asphalt crack pattern).
    """
    img_path = SAMPLES_DIR / filename
    if img_path.exists():
        return filename

    width, height = 800, 480
    img = np.zeros((height, width, 3), dtype=np.uint8)

    # 1. Sky and Horizon (Top 35%)
    sky_color = np.array([195, 175, 150], dtype=np.uint8)  # BGR hazy daylight
    img[0:int(height*0.35), :] = sky_color

    # Horizon gradient
    for y in range(int(height*0.28), int(height*0.35)):
        blend = (y - height*0.28) / (height*0.07)
        img[y, :] = (1.0 - blend) * sky_color + blend * np.array([80, 80, 85])

    # 2. Road surface with textured asphalt grain
    asphalt_base = np.array([55, 58, 62], dtype=np.float32)
    road_mask = np.random.normal(0, 12, (height - int(height*0.35), width, 3))
    road_surface = np.clip(asphalt_base + road_mask, 25, 110).astype(np.uint8)
    img[int(height*0.35):, :] = road_surface

    # 3. Perspective Road Lane Markings (White and Yellow dashes)
    horizon_y = int(height * 0.35)
    vanishing_x = width // 2

    # Left lane edge
    cv2.line(img, (vanishing_x - 40, horizon_y), (60, height), (220, 220, 225), 3, cv2.LINE_AA)
    # Right lane edge
    cv2.line(img, (vanishing_x + 40, horizon_y), (width - 60, height), (220, 220, 225), 3, cv2.LINE_AA)

    # Center broken yellow divider
    for seg in range(6):
        y_start = int(horizon_y + (seg / 6.0)**1.5 * (height - horizon_y))
        y_end = int(horizon_y + ((seg + 0.6) / 6.0)**1.5 * (height - horizon_y))
        thick = max(1, int(1 + seg * 0.8))
        cv2.line(img, (vanishing_x, y_start), (vanishing_x, y_end), (30, 190, 240), thick, cv2.LINE_AA)

    # 4. Draw Defect in lower road plane
    cx = width // 2 + int(np.random.randint(-120, 120))
    cy = int(height * 0.65 + np.random.randint(-30, 50))

    if defect_type == "D40":  # Pothole cavity
        rw = np.random.randint(65, 110) if defect_size == "large" else np.random.randint(40, 65)
        rh = int(rw * np.random.uniform(0.5, 0.75))
        # Dark inner depression
        cv2.ellipse(img, (cx, cy), (rw, rh), 0, 0, 360, (22, 24, 28), -1, cv2.LINE_AA)
        # Jagged interior texture & gravel edges
        cv2.ellipse(img, (cx, cy), (int(rw*0.8), int(rh*0.8)), 0, 0, 360, (14, 15, 18), -1, cv2.LINE_AA)
        cv2.ellipse(img, (cx, cy), (rw, rh), 0, 0, 360, (75, 80, 85), 2, cv2.LINE_AA)
        # Deep shadow rim
        cv2.ellipse(img, (cx, cy + 2), (int(rw*0.95), int(rh*0.95)), 0, 0, 180, (10, 10, 12), 2, cv2.LINE_AA)

    elif defect_type == "D20":  # Alligator / fatigue mesh crack
        for _ in range(14):
            x1 = cx + np.random.randint(-70, 70)
            y1 = cy + np.random.randint(-40, 40)
            x2 = x1 + np.random.randint(-30, 30)
            y2 = y1 + np.random.randint(-25, 25)
            cv2.line(img, (x1, y1), (x2, y2), (20, 20, 22), 2, cv2.LINE_AA)
            cv2.line(img, (x1, y1), (x2, y2), (70, 75, 80), 1, cv2.LINE_AA)

    elif defect_type == "D10":  # Transverse crack (across the lane)
        tw = np.random.randint(140, 220)
        pts = []
        cur_x = cx - tw // 2
        cur_y = cy
        while cur_x < cx + tw // 2:
            pts.append((cur_x, cur_y + np.random.randint(-4, 4)))
            cur_x += np.random.randint(15, 30)
        for i in range(len(pts) - 1):
            cv2.line(img, pts[i], pts[i+1], (18, 18, 20), 2, cv2.LINE_AA)

    else:  # D00 Longitudinal crack (along driving direction)
        th = np.random.randint(90, 160)
        pts = []
        cur_x = cx
        cur_y = cy - th // 2
        while cur_y < cy + th // 2:
            pts.append((cur_x + np.random.randint(-5, 5), cur_y))
            cur_y += np.random.randint(15, 25)
        for i in range(len(pts) - 1):
            cv2.line(img, pts[i], pts[i+1], (18, 18, 20), 2, cv2.LINE_AA)

    # Save to samples directory
    cv2.imwrite(str(img_path), img)
    return filename

def seed_sample_database():
    """
    Initializes realistic starter data across 4 representative municipal roads
    if database is empty.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM clusters")
    count = cur.fetchone()[0]
    conn.close()

    if count > 0:
        return  # Already seeded

    # Generate sample imagery
    img_pothole_1 = create_synthetic_road_defect_image("sample_pothole_d40_crit.jpg", "D40", "large")
    img_pothole_2 = create_synthetic_road_defect_image("sample_pothole_d40_high.jpg", "D40", "medium")
    img_alligator_1 = create_synthetic_road_defect_image("sample_crack_d20_alligator.jpg", "D20", "large")
    img_transverse_1 = create_synthetic_road_defect_image("sample_crack_d10_transverse.jpg", "D10", "large")
    img_longitudinal_1 = create_synthetic_road_defect_image("sample_crack_d00_long.jpg", "D00", "large")

    # Seed Drive 1: Main City Corridor Survey
    drive1_id = insert_drive(
        name="Arterial Survey Run #104 (South Sector)",
        filename="dashcam_south_sector_4k.mp4",
        total_frames=180,
        duration_sec=90.0,
        distance_km=1.45
    )

    # Base coordinates (Metropolitan City Area)
    base_lat = 12.971598
    base_lon = 77.594562

    # Multiple raw detections simulating consecutive dashcam passes over 6 distinct defects
    raw_detections = [
        # Defect 1: Critical Pothole (3 passes within 8 meters -> DBSCAN clusters into 1)
        {"drive_id": drive1_id, "frame_id": 12, "timestamp_sec": 6.0, "lat": base_lat + 0.00012, "lon": base_lon + 0.00010, "damage_class": "D40", "conf": 0.94, "bbox": [0.42, 0.62, 0.64, 0.82], "area": 0.044, "sev": 88.5, "img": img_pothole_1},
        {"drive_id": drive1_id, "frame_id": 13, "timestamp_sec": 6.5, "lat": base_lat + 0.00014, "lon": base_lon + 0.00012, "damage_class": "D40", "conf": 0.92, "bbox": [0.40, 0.64, 0.66, 0.84], "area": 0.052, "sev": 91.0, "img": img_pothole_1},
        {"drive_id": drive1_id, "frame_id": 14, "timestamp_sec": 7.0, "lat": base_lat + 0.00015, "lon": base_lon + 0.00013, "damage_class": "D40", "conf": 0.89, "bbox": [0.38, 0.68, 0.68, 0.88], "area": 0.060, "sev": 89.2, "img": img_pothole_1},

        # Defect 2: Alligator Crack (2 passes -> DBSCAN clusters into 1)
        {"drive_id": drive1_id, "frame_id": 34, "timestamp_sec": 17.0, "lat": base_lat + 0.00085, "lon": base_lon + 0.00072, "damage_class": "D20", "conf": 0.88, "bbox": [0.35, 0.55, 0.65, 0.78], "area": 0.069, "sev": 74.0, "img": img_alligator_1},
        {"drive_id": drive1_id, "frame_id": 35, "timestamp_sec": 17.5, "lat": base_lat + 0.00088, "lon": base_lon + 0.00074, "damage_class": "D20", "conf": 0.85, "bbox": [0.32, 0.58, 0.68, 0.82], "area": 0.086, "sev": 76.5, "img": img_alligator_1},

        # Defect 3: Transverse Joint Crack (2 passes)
        {"drive_id": drive1_id, "frame_id": 62, "timestamp_sec": 31.0, "lat": base_lat + 0.00160, "lon": base_lon + 0.00140, "damage_class": "D10", "conf": 0.84, "bbox": [0.22, 0.62, 0.78, 0.74], "area": 0.067, "sev": 58.0, "img": img_transverse_1},
        {"drive_id": drive1_id, "frame_id": 63, "timestamp_sec": 31.5, "lat": base_lat + 0.00163, "lon": base_lon + 0.00142, "damage_class": "D10", "conf": 0.82, "bbox": [0.20, 0.64, 0.80, 0.76], "area": 0.072, "sev": 56.4, "img": img_transverse_1},

        # Defect 4: Moderate Pothole (Single pass)
        {"drive_id": drive1_id, "frame_id": 95, "timestamp_sec": 47.5, "lat": base_lat + 0.00240, "lon": base_lon + 0.00210, "damage_class": "D40", "conf": 0.86, "bbox": [0.45, 0.60, 0.62, 0.75], "area": 0.025, "sev": 68.0, "img": img_pothole_2},

        # Defect 5: Longitudinal Crack
        {"drive_id": drive1_id, "frame_id": 125, "timestamp_sec": 62.5, "lat": base_lat + 0.00315, "lon": base_lon + 0.00285, "damage_class": "D00", "conf": 0.79, "bbox": [0.48, 0.48, 0.56, 0.85], "area": 0.029, "sev": 42.0, "img": img_longitudinal_1},

        # Defect 6: Severe Pothole near Junction
        {"drive_id": drive1_id, "frame_id": 160, "timestamp_sec": 80.0, "lat": base_lat + 0.00395, "lon": base_lon + 0.00360, "damage_class": "D40", "conf": 0.95, "bbox": [0.38, 0.58, 0.66, 0.86], "area": 0.078, "sev": 94.0, "img": img_pothole_1},
    ]

    saved_detections = []
    for d in raw_detections:
        did = insert_detection(
            drive_id=d["drive_id"],
            frame_id=d["frame_id"],
            timestamp_sec=d["timestamp_sec"],
            lat=d["lat"],
            lon=d["lon"],
            damage_class=d["damage_class"],
            confidence=d["conf"],
            bbox=d["bbox"],
            bbox_area_ratio=d["area"],
            severity_score=d["sev"],
            image_filename=d["img"]
        )
        saved_detections.append({
            "id": did,
            "lat": d["lat"],
            "lon": d["lon"],
            "damage_class": d["damage_class"],
            "confidence": d["conf"],
            "bbox_area_ratio": d["area"],
            "severity_score": d["sev"],
            "image_filename": d["img"]
        })

    # Run DBSCAN deduplication
    clusters = perform_dbscan_clustering(saved_detections, eps_meters=20.0, min_samples=1)

    # Update drive stats
    from src.database import update_drive_stats
    update_drive_stats(drive1_id, len(saved_detections), len(clusters))
