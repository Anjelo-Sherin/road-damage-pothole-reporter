import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Server Config
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8015"))
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

# Directories
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
EXPORTS_DIR = DATA_DIR / "exports"
SAMPLES_DIR = DATA_DIR / "samples"
DATABASE_PATH = DATA_DIR / "road_damage.db"

for d in [DATA_DIR, UPLOAD_DIR, EXPORTS_DIR, SAMPLES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Spatial Clustering (DBSCAN)
# 20 meters default clustering radius for merging duplicate detections
DBSCAN_EPS_METERS = float(os.getenv("DBSCAN_EPS_METERS", "20.0"))
DBSCAN_MIN_SAMPLES = int(os.getenv("DBSCAN_MIN_SAMPLES", "1"))

# RDD2022 Damage Classes & Severity Multipliers
DAMAGE_CLASSES = {
    "D00": {"name": "Longitudinal Crack", "weight": 1.2, "color": "#38bdf8", "remediation": "Crack sealing with polymer bitumen"},
    "D10": {"name": "Transverse Crack", "weight": 1.4, "color": "#fbbf24", "remediation": "Transverse route & cold mastic seal"},
    "D20": {"name": "Alligator Crack", "weight": 2.0, "color": "#fb923c", "remediation": "Sub-base stabilization & full patch overlay"},
    "D40": {"name": "Pothole / Cavity", "weight": 2.8, "color": "#f43f5e", "remediation": "Deep milling with hot-mix asphalt (HMA) compaction"},
}

# Municipality & Civic Grievance
MUNICIPALITY_NAME = os.getenv("MUNICIPALITY_NAME", "Metropolitan Infrastructure & Civic Works Authority")
MUNICIPALITY_EMAIL = os.getenv("MUNICIPALITY_EMAIL", "roads-grievance@metro-civic.gov")
SIMULATE_EMAIL_DISPATCH = os.getenv("SIMULATE_EMAIL_DISPATCH", "True").lower() in ("true", "1", "yes")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
