import smtplib
import random
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from src.config import (
    MUNICIPALITY_EMAIL, MUNICIPALITY_NAME, SIMULATE_EMAIL_DISPATCH,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, DAMAGE_CLASSES
)
from src.database import (
    get_cluster_by_id, insert_complaint, update_complaint_status, update_cluster_status
)
from src.pdf_generator import generate_complaint_pdf

def create_and_dispatch_complaint(
    cluster_id: int,
    recipient_email: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates an official grievance report PDF for a cluster,
    stores the complaint record, and dispatches (or simulates dispatch) to the municipal works authority.
    """
    cluster = get_cluster_by_id(cluster_id)
    if not cluster:
        raise ValueError(f"Cluster ID {cluster_id} not found.")

    recipient = recipient_email or MUNICIPALITY_EMAIL
    random_code = f"{random.randint(1000, 9999)}"
    ref_no = f"ROADPULSE-2026-T{random_code}"

    # Generate the official PDF report
    pdf_path = generate_complaint_pdf(cluster, ref_no)

    damage_name = DAMAGE_CLASSES.get(cluster["damage_class"], {}).get("name", "Road Defect")
    subject = f"[{cluster['severity_tier'].upper()} PRIORITY] Civic Grievance #{ref_no}: {cluster['damage_class']} on {cluster['road_name']}"

    email_body = f"""Dear {MUNICIPALITY_NAME} Road Maintenance Directorate,

An automated civic road safety report has been filed via RoadPulse AI regarding a critical road defect:

----------------------------------------------------------------------
GRIEVANCE TICKET: {ref_no}
DAMAGE CLASS:     {cluster['damage_class']} - {damage_name}
SEVERITY SCORE:   {cluster['severity_score']} / 100 ({cluster['severity_tier']})
LOCATION:         {cluster['road_name']}
GPS COORDINATES:  {cluster['lat']:.6f}° N, {cluster['lon']:.6f}° E
MAP EXPLORER:     https://www.openstreetmap.org/?mlat={cluster['lat']}&mlon={cluster['lon']}#map=18/{cluster['lat']}/{cluster['lon']}
ESTIMATED REPAIR: ${cluster['repair_cost_est']:,.2f}
SENSOR MERGES:    {cluster['detection_count']} dashcam passes merged (DBSCAN)
RECOMMENDATION:   {DAMAGE_CLASSES.get(cluster['damage_class'], {}).get('remediation', 'Pavement repair')}
----------------------------------------------------------------------

The formal technical specification PDF with geotagged bounding-box visual evidence is attached.
Please schedule roadway inspection and assign the corresponding municipal work order.

Sincerely,
RoadPulse AI Automated Civic Infrastructure Monitor
https://github.com/Anjelo-Sherin
"""

    complaint_id = insert_complaint(
        cluster_id=cluster_id,
        reference_no=ref_no,
        recipient_email=recipient,
        road_name=cluster["road_name"],
        damage_class=cluster["damage_class"],
        severity_tier=cluster["severity_tier"],
        pdf_path=str(pdf_path),
        email_body=email_body,
        status="Draft"
    )

    dispatch_success = False
    dispatch_message = ""

    if SIMULATE_EMAIL_DISPATCH or not SMTP_USER:
        # Civic simulation mode
        update_complaint_status(complaint_id, "Dispatched (Simulated)")
        update_cluster_status(cluster_id, "Under Review")
        dispatch_success = True
        dispatch_message = f"Simulated dispatch successful to {recipient}. Grievance ticket #{ref_no} active."
    else:
        # Live SMTP sending
        try:
            msg = MIMEMultipart()
            msg["From"] = SMTP_USER
            msg["To"] = recipient
            msg["Subject"] = subject
            msg.attach(MIMEText(email_body, "plain"))

            if Path(pdf_path).exists():
                with open(pdf_path, "rb") as f:
                    attach = MIMEApplication(f.read(), _subtype="pdf")
                    attach.add_header("Content-Disposition", "attachment", filename=Path(pdf_path).name)
                    msg.attach(attach)

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)

            update_complaint_status(complaint_id, "Dispatched (SMTP)")
            update_cluster_status(cluster_id, "Under Review")
            dispatch_success = True
            dispatch_message = f"Direct SMTP dispatch verified to {recipient}."
        except Exception as e:
            dispatch_message = f"SMTP transmission failed: {str(e)}. Grievance saved as Draft."

    return {
        "complaint_id": complaint_id,
        "reference_no": ref_no,
        "recipient": recipient,
        "pdf_path": str(pdf_path),
        "pdf_download_url": f"/api/complaints/{complaint_id}/pdf",
        "dispatch_success": dispatch_success,
        "dispatch_message": dispatch_message,
        "email_subject": subject,
        "email_body": email_body
    }
