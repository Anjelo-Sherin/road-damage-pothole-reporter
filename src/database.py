import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from src.config import DATABASE_PATH

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS drives (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        filename TEXT,
        total_frames INTEGER DEFAULT 0,
        duration_sec REAL DEFAULT 0.0,
        distance_km REAL DEFAULT 0.0,
        total_detections INTEGER DEFAULT 0,
        total_clusters INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        drive_id INTEGER,
        frame_id INTEGER,
        timestamp_sec REAL,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        damage_class TEXT NOT NULL,
        confidence REAL NOT NULL,
        bbox_x1 REAL NOT NULL,
        bbox_y1 REAL NOT NULL,
        bbox_x2 REAL NOT NULL,
        bbox_y2 REAL NOT NULL,
        bbox_area_ratio REAL NOT NULL,
        severity_score REAL NOT NULL,
        image_filename TEXT,
        cluster_id INTEGER,
        created_at TEXT NOT NULL,
        FOREIGN KEY (drive_id) REFERENCES drives (id)
    );

    CREATE TABLE IF NOT EXISTS clusters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cluster_label INTEGER NOT NULL,
        representative_detection_id INTEGER,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        damage_class TEXT NOT NULL,
        avg_confidence REAL NOT NULL,
        severity_score REAL NOT NULL,
        severity_tier TEXT NOT NULL,
        detection_count INTEGER NOT NULL DEFAULT 1,
        road_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Reported',
        priority TEXT NOT NULL DEFAULT 'Medium',
        repair_cost_est REAL DEFAULT 450.0,
        work_order_id TEXT,
        first_detected_at TEXT NOT NULL,
        last_detected_at TEXT NOT NULL,
        FOREIGN KEY (representative_detection_id) REFERENCES detections (id)
    );

    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cluster_id INTEGER NOT NULL,
        reference_no TEXT UNIQUE NOT NULL,
        recipient_email TEXT NOT NULL,
        road_name TEXT NOT NULL,
        damage_class TEXT NOT NULL,
        severity_tier TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Draft',
        pdf_path TEXT,
        email_body TEXT,
        dispatched_at TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (cluster_id) REFERENCES clusters (id)
    );

    CREATE INDEX IF NOT EXISTS idx_detections_coords ON detections (lat, lon);
    CREATE INDEX IF NOT EXISTS idx_clusters_coords ON clusters (lat, lon);
    CREATE INDEX IF NOT EXISTS idx_clusters_severity ON clusters (severity_score DESC);
    CREATE INDEX IF NOT EXISTS idx_clusters_status ON clusters (status);
    """)
    conn.commit()
    conn.close()

def insert_drive(name: str, filename: str = "", total_frames: int = 0, duration_sec: float = 0.0, distance_km: float = 0.0) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO drives (name, filename, total_frames, duration_sec, distance_km, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, filename, total_frames, duration_sec, distance_km, datetime.utcnow().isoformat()))
    drive_id = cur.lastrowid
    conn.commit()
    conn.close()
    return drive_id

def update_drive_stats(drive_id: int, total_detections: int, total_clusters: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE drives SET total_detections = ?, total_clusters = ? WHERE id = ?
    """, (total_detections, total_clusters, drive_id))
    conn.commit()
    conn.close()

def insert_detection(
    drive_id: Optional[int],
    frame_id: int,
    timestamp_sec: float,
    lat: float,
    lon: float,
    damage_class: str,
    confidence: float,
    bbox: List[float],
    bbox_area_ratio: float,
    severity_score: float,
    image_filename: str = "",
    cluster_id: Optional[int] = None
) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO detections (
            drive_id, frame_id, timestamp_sec, lat, lon, damage_class, confidence,
            bbox_x1, bbox_y1, bbox_x2, bbox_y2, bbox_area_ratio, severity_score,
            image_filename, cluster_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        drive_id, frame_id, timestamp_sec, lat, lon, damage_class, confidence,
        bbox[0], bbox[1], bbox[2], bbox[3], bbox_area_ratio, severity_score,
        image_filename, cluster_id, datetime.utcnow().isoformat()
    ))
    detection_id = cur.lastrowid
    conn.commit()
    conn.close()
    return detection_id

def insert_cluster(
    cluster_label: int,
    representative_detection_id: Optional[int],
    lat: float,
    lon: float,
    damage_class: str,
    avg_confidence: float,
    severity_score: float,
    severity_tier: str,
    detection_count: int,
    road_name: str,
    status: str = "Reported",
    priority: str = "Medium",
    repair_cost_est: float = 500.0,
    work_order_id: Optional[str] = None
) -> int:
    now_iso = datetime.utcnow().isoformat()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO clusters (
            cluster_label, representative_detection_id, lat, lon, damage_class,
            avg_confidence, severity_score, severity_tier, detection_count, road_name,
            status, priority, repair_cost_est, work_order_id, first_detected_at, last_detected_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        cluster_label, representative_detection_id, lat, lon, damage_class,
        avg_confidence, severity_score, severity_tier, detection_count, road_name,
        status, priority, repair_cost_est, work_order_id, now_iso, now_iso
    ))
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return cid

def update_detection_cluster_id(detection_id: int, cluster_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE detections SET cluster_id = ? WHERE id = ?", (cluster_id, detection_id))
    conn.commit()
    conn.close()

def get_all_clusters(
    status: Optional[str] = None,
    severity_tier: Optional[str] = None,
    damage_class: Optional[str] = None,
    road_name: Optional[str] = None,
    limit: int = 200
) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT c.*, d.image_filename, d.confidence as rep_conf, d.bbox_x1, d.bbox_y1, d.bbox_x2, d.bbox_y2
        FROM clusters c
        LEFT JOIN detections d ON c.representative_detection_id = d.id
        WHERE 1=1
    """
    params = []
    if status and status != "All":
        query += " AND c.status = ?"
        params.append(status)
    if severity_tier and severity_tier != "All":
        query += " AND c.severity_tier = ?"
        params.append(severity_tier)
    if damage_class and damage_class != "All":
        query += " AND c.damage_class = ?"
        params.append(damage_class)
    if road_name:
        query += " AND c.road_name LIKE ?"
        params.append(f"%{road_name}%")
    
    query += " ORDER BY c.severity_score DESC LIMIT ?"
    params.append(limit)

    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_cluster_by_id(cluster_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.*, d.image_filename, d.confidence as rep_conf, d.bbox_x1, d.bbox_y1, d.bbox_x2, d.bbox_y2
        FROM clusters c
        LEFT JOIN detections d ON c.representative_detection_id = d.id
        WHERE c.id = ?
    """, (cluster_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    res = dict(row)
    
    # Also fetch member detections
    cur.execute("""
        SELECT * FROM detections WHERE cluster_id = ? ORDER BY timestamp_sec ASC
    """, (cluster_id,))
    res["member_detections"] = [dict(r) for r in cur.fetchall()]
    conn.close()
    return res

def update_cluster_status(cluster_id: int, status: str, work_order_id: Optional[str] = None) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    if work_order_id:
        cur.execute("UPDATE clusters SET status = ?, work_order_id = ? WHERE id = ?", (status, work_order_id, cluster_id))
    else:
        cur.execute("UPDATE clusters SET status = ? WHERE id = ?", (status, cluster_id))
    updated = cur.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def insert_complaint(
    cluster_id: int,
    reference_no: str,
    recipient_email: str,
    road_name: str,
    damage_class: str,
    severity_tier: str,
    pdf_path: str,
    email_body: str,
    status: str = "Draft"
) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO complaints (
            cluster_id, reference_no, recipient_email, road_name, damage_class,
            severity_tier, status, pdf_path, email_body, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        cluster_id, reference_no, recipient_email, road_name, damage_class,
        severity_tier, status, pdf_path, email_body, datetime.utcnow().isoformat()
    ))
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return cid

def update_complaint_status(complaint_id: int, status: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE complaints SET status = ?, dispatched_at = ? WHERE id = ?
    """, (status, datetime.utcnow().isoformat(), complaint_id))
    conn.commit()
    conn.close()

def get_complaint_by_id(complaint_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_complaints_by_cluster(cluster_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM complaints WHERE cluster_id = ? ORDER BY id DESC", (cluster_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_worst_roads_leaderboard() -> List[Dict[str, Any]]:
    """
    Ranks roads by aggregate Road Severity Index (RSI), defect count, and critical defect ratio.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            road_name,
            COUNT(id) as defect_count,
            ROUND(SUM(severity_score), 2) as total_severity,
            ROUND(AVG(severity_score), 2) as avg_severity,
            SUM(CASE WHEN severity_tier = 'Critical' THEN 1 ELSE 0 END) as critical_count,
            SUM(CASE WHEN severity_tier = 'High' THEN 1 ELSE 0 END) as high_count,
            SUM(CASE WHEN status = 'Repaired' THEN 1 ELSE 0 END) as repaired_count,
            SUM(CASE WHEN status != 'Repaired' THEN 1 ELSE 0 END) as pending_count,
            ROUND(SUM(repair_cost_est), 2) as est_total_budget
        FROM clusters
        GROUP BY road_name
        ORDER BY total_severity DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_system_stats() -> Dict[str, Any]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM detections")
    total_detections = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM clusters")
    total_clusters = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM clusters WHERE severity_tier = 'Critical'")
    critical_clusters = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM clusters WHERE status = 'Repaired'")
    repaired_clusters = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM complaints")
    total_complaints = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM drives")
    total_drives = cur.fetchone()[0]

    cur.execute("SELECT SUM(distance_km) FROM drives")
    total_km = cur.fetchone()[0] or 0.0

    # Damage class distribution
    cur.execute("SELECT damage_class, COUNT(*) as count FROM clusters GROUP BY damage_class")
    class_dist = {r[0]: r[1] for r in cur.fetchall()}

    conn.close()

    dedupe_ratio = (
        round(((total_detections - total_clusters) / total_detections) * 100, 1)
        if total_detections > 0
        else 0.0
    )

    return {
        "total_detections": total_detections,
        "total_clusters": total_clusters,
        "critical_clusters": critical_clusters,
        "repaired_clusters": repaired_clusters,
        "pending_repairs": total_clusters - repaired_clusters,
        "total_complaints": total_complaints,
        "total_drives": total_drives,
        "total_km_surveyed": round(total_km, 2),
        "dedupe_ratio_percent": dedupe_ratio,
        "class_distribution": class_dist
    }

init_db()
