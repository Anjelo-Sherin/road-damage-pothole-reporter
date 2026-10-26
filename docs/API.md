# RoadPulse AI: REST & WebSocket API Reference

The RoadPulse AI backend exposes RESTful endpoints for GIS defect query, photo inference, video processing, work-order status transitions, and PDF document downloads, alongside a real-time WebSocket for live telemetry streaming.

Default Base URL: `http://localhost:8015`

---

## 1. System Health & Analytics

### `GET /api/status`
Returns service operational health and model metadata.

**Response `200 OK`**:
```json
{
  "status": "online",
  "service": "RoadPulse AI",
  "version": "1.0.0",
  "detector": "RDD2022 YOLO/CV Pipeline",
  "spatial_clustering": "DBSCAN (eps=20.0m)"
}
```

### `GET /api/stats`
Returns system-wide KPI metrics for the civic dashboard.

**Response `200 OK`**:
```json
{
  "total_detections": 12,
  "total_clusters": 6,
  "critical_clusters": 2,
  "repaired_clusters": 1,
  "pending_repairs": 5,
  "total_complaints": 3,
  "total_drives": 1,
  "total_km_surveyed": 1.45,
  "dedupe_ratio_percent": 50.0,
  "class_distribution": {
    "D40": 3,
    "D20": 1,
    "D10": 1,
    "D00": 1
  }
}
```

---

## 2. GIS Defect & Cluster Endpoints

### `GET /api/clusters`
Fetches deduplicated road defects with optional query filtering.

**Query Parameters**:
- `severity_tier` (string, optional): `Critical`, `High`, `Medium`, `Low`, `All`
- `damage_class` (string, optional): `D40`, `D20`, `D10`, `D00`, `All`
- `status` (string, optional): `Reported`, `Under Review`, `Scheduled`, `Repaired`, `All`
- `road_name` (string, optional): Substring filter for road names

**Response `200 OK`**: Array of cluster records with representative detection data.

### `GET /api/clusters/{id}`
Returns granular metadata for a cluster, including all merged raw detections.

---

## 3. Civic Actions & Document Generation

### `POST /api/clusters/{id}/complaint`
Compiles an official municipal grievance PDF and prepares the email dispatch package.

**Request Body (optional)**:
```json
{
  "recipient_email": "custom-roads@municipality.gov"
}
```

**Response `200 OK`**:
```json
{
  "complaint_id": 4,
  "reference_no": "ROADPULSE-2026-T8392",
  "recipient": "roads-grievance@metro-civic.gov",
  "pdf_path": "data/exports/Grievance_ROADPULSE-2026-T8392.pdf",
  "pdf_download_url": "/api/complaints/4/pdf",
  "dispatch_success": true,
  "dispatch_message": "Simulated dispatch successful..."
}
```

### `GET /api/complaints/{id}/pdf`
Downloads the binary PDF file for printing or field dispatch.

---

## 4. Detection Ingestion

### `POST /api/detect/image`
Ingests an image from a phone camera or citizen upload. Auto-extracts EXIF GPS coordinates when available.

**Form Data**:
- `file`: Multipart image binary (JPEG/PNG)
- `lat` (optional): Override latitude
- `lon` (optional): Override longitude
- `road_name` (optional): Override road corridor

### `POST /api/detect/video`
Processes dashcam video and GPX tracks.

**Form Data**:
- `video_file`: MP4/MOV binary
- `gpx_file` (optional): XML GPX track file

---

## 5. WebSocket Telemetry

### `WS /ws/live-drive`
Streams real-time vehicle telemetry and frame events.

**Message Payload Example**:
```json
{
  "step": 6,
  "timestamp_sec": 6.0,
  "lat": 12.971718,
  "lon": 77.594662,
  "speed_kmh": 38.2,
  "road_name": "Grand Trunk Expressway",
  "has_defect": true,
  "defect": {
    "class": "D40",
    "name": "Severe Cavity Pothole",
    "sev": 89.4,
    "tier": "Critical",
    "img": "sample_pothole_d40_crit.jpg"
  }
}
```
