# RoadPulse AI: System Architecture & Technical Specifications

RoadPulse AI is designed as a modular, edge-capable civic infrastructure monitoring platform. This document outlines the component architecture, data flow, computer vision algorithms, and spatial clustering algorithms.

---

## 1. High-Level Component Diagram

```text
┌────────────────────────────────────────────────────────┐
│                   CLIENT PRESENTATION LAYER             │
│   - Leaflet GIS Interactive Map (Heatmap + Severity)    │
│   - Dashcam HUD Studio (Live Streaming Telemetry)       │
│   - Citizen Fast-Report (EXIF GPS Extraction)           │
│   - Municipality Command Hub (Work Order Management)    │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP REST / WebSocket
                            ▼
┌────────────────────────────────────────────────────────┐
│                   FASTAPI APPLICATION CORE             │
│   - REST Endpoints (/api/clusters, /api/detect, ...)   │
│   - WebSocket Telemetry Stream (/ws/live-drive)        │
│   - Static Asset & Media Handlers                      │
└─────┬─────────────────────┬──────────────────────┬─────┘
      │                     │                      │
      ▼                     ▼                      ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  CV DETECTOR │     │  GEOTAGGER   │     │ DBSCAN ENGINE│
│  - RDD2022   │     │  - Haversine │     │  - Density   │
│  - Cavity    │     │  - GPX Track │     │    Cluster   │
│    Filters   │     │  - EXIF GPS  │     │  - Centroids │
└──────────────┘     └──────────────┘     └──────────────┘
      │                     │                      │
      └─────────────────────┼──────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│                    DATA PERSISTENCE                    │
│   - SQLite Database (Detections, Clusters, Work Orders)│
│   - File Storage (Annotated Frames, Evidence Crops)    │
│   - ReportLab PDF Engine (Municipal Grievance Export)  │
└────────────────────────────────────────────────────────┘
```

---

## 2. Computer Vision Detection Pipeline (`src/detector.py`)

### 2.1 Region of Interest (ROI) Filtering
Dashcam footage contains substantial background noise:
- Sky and clouds (top 35%)
- Vehicle dashboard / bonnet (bottom 5%)
- Roadside foliage and pedestrian sidewalks (left/right 5%)

The detector segments the roadway plane using dynamic ROI coordinates:
$$y \in [0.35 H, 0.95 H], \quad x \in [0.05 W, 0.95 W]$$

### 2.2 Cavity Saliency & Blackhat Transform
Potholes (`D40`) manifest as dark depressions with irregular boundaries and localized depth shadows:
1. Greyscale conversion and Gaussian smoothing ($\sigma = 7$).
2. Blackhat morphological transform:
   $$\text{Blackhat}(I) = \text{Closing}(I, K) - I$$
   using an elliptical structuring element $K_{25 \times 25}$.
3. High-pass thresholding isolating dark craters from surrounding pavement.

### 2.3 Crack Saliency via Directional Gradients
Asphalt cracks (`D00`, `D10`, `D20`) are detected using Sobel directional gradients:
$$G_x = \frac{\partial I}{\partial x}, \quad G_y = \frac{\partial I}{\partial y}, \quad G = \sqrt{G_x^2 + G_y^2}$$
- **Aspect Ratio $\ge 2.2$**: Classified as Transverse Crack (`D10`).
- **Aspect Ratio $\le 0.55$**: Classified as Longitudinal Crack (`D00`).
- **High Perimeter Complexity ($P^2 / A > 30$)**: Classified as Alligator Crack (`D20`).

---

## 3. DBSCAN Spatial Deduplication (`src/clustering.py`)

### 3.1 Mathematical Formulation
Let each detection $d_i$ have GPS coordinates $(\phi_i, \lambda_i)$ in radians.
The distance between two detections is given by the great-circle Haversine formula:
$$d(d_1, d_2) = 2 R \arcsin \left( \sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos \phi_1 \cos \phi_2 \sin^2\left(\frac{\Delta \lambda}{2}\right)} \right)$$

With earth radius $R = 6,371,000 \text{ m}$ and $\epsilon = 20 \text{ m}$, the angular radius is:
$$\epsilon_{\text{rad}} = \frac{20}{6371000} \approx 3.139 \times 10^{-6} \text{ radians}$$

### 3.2 Canonical Entity Synthesis
For every cluster $C = \{d_1, d_2, \dots, d_m\}$:
1. **Centroid**:
   $$\bar{\phi} = \frac{1}{m} \sum_{i=1}^m \phi_i, \quad \bar{\lambda} = \frac{1}{m} \sum_{i=1}^m \lambda_i$$
2. **Representative Evidence**:
   $$d^* = \arg\max_{d \in C} \left( \text{confidence}(d) + \text{area\_ratio}(d) \right)$$
3. **Road Severity Index (RSI)**:
   $$\text{RSI} = \min\left(100, \max_{d \in C} \text{severity}(d) + \min(15, (m - 1) \times 2.5)\right)$$

---

## 4. Municipal PDF Grievance Compilation (`src/pdf_generator.py`)

Grievance reports are rendered via ReportLab flowables:
1. **Header Block**: Municipality authority branding and ISO timestamp.
2. **Defect Specification Matrix**: Exact lat/lon coordinates, RDD2022 code, severity score, and estimated repair budget.
3. **Geotagged Photo Evidence**: Bounding box visual crop showing ground defect in high resolution.
4. **Remediation Directive**: Standardized asphalt engineering procedures (tack coat rates, compaction standards, milling depths).
