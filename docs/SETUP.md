# RoadPulse AI: Setup & Deployment Guide

This guide details running RoadPulse AI locally or via Docker containers.

---

## Prerequisites

- **Python**: 3.9, 3.10, or 3.11
- **Node/NPM** (Optional, frontend uses vanilla JS/Leaflet via CDN)
- **Docker & Docker Compose** (Optional for containerization)

---

## Method 1: Local Virtual Environment Setup

### 1. Create and Activate Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate  # macOS / Linux
# .venv\Scripts\activate   # Windows
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables (Optional)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Default parameters run out-of-the-box with simulated email dispatch and zero API key requirements.

### 4. Launch Application
```bash
python app.py
```
Visit **`http://localhost:8015`** in your browser.

---

## Method 2: Docker Container Deployment

### Using Docker Compose
```bash
docker-compose up --build
```
The application will be accessible at `http://localhost:8015` with data mounted persistently to `./data`.

---

## Testing Verification
```bash
PYTHONPATH=. pytest tests/ -v
```
All 11 tests will validate detector accuracy, DBSCAN clustering, PDF compilation, and FastAPI routes.
