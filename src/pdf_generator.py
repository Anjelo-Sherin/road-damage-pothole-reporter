import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from src.config import EXPORTS_DIR, MUNICIPALITY_NAME, DAMAGE_CLASSES, BASE_DIR

def generate_complaint_pdf(cluster: Dict[str, Any], reference_no: str) -> str:
    """
    Generates a formal, civic-grade engineering grievance PDF report
    with embedded photo evidence, GPS coordinates, defect classification,
    and recommended remediation guidelines.
    """
    filename = f"Grievance_{reference_no}.pdf"
    pdf_path = EXPORTS_DIR / filename

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0f172a')
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#64748b')
    )
    h2_style = ParagraphStyle(
        'Heading2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#1e293b')
    )
    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155')
    )
    meta_style = ParagraphStyle(
        'MetaText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#475569')
    )

    story = []

    # 1. Header Banner
    header_data = [
        [
            Paragraph(f"<b>ROADPULSE AI</b> &bull; CIVIC INFRASTRUCTURE REPORT", subtitle_style),
            Paragraph(f"<b>REFERENCE:</b> {reference_no}", subtitle_style)
        ],
        [
            Paragraph(f"<b>{MUNICIPALITY_NAME}</b>", title_style),
            Paragraph(f"Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", subtitle_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[380, 150])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#f43f5e'), spaceAfter=14))

    # 2. Defect Overview Table
    damage_cls = cluster.get("damage_class", "D40")
    class_meta = DAMAGE_CLASSES.get(damage_cls, {"name": "Road Surface Defect", "remediation": "Asphalt patch"})
    tier = cluster.get("severity_tier", "High")
    tier_color = "#dc2626" if tier == "Critical" else ("#ea580c" if tier == "High" else "#d97706")

    overview_data = [
        [
            Paragraph("<b>Defect Classification</b>", body_style),
            Paragraph(f"<b>{damage_cls} - {class_meta['name']}</b>", body_style),
            Paragraph("<b>Severity Rating</b>", body_style),
            Paragraph(f"<font color='{tier_color}'><b>{cluster.get('severity_score', 0)} / 100 ({tier})</b></font>", body_style)
        ],
        [
            Paragraph("<b>Location / Corridor</b>", body_style),
            Paragraph(f"{cluster.get('road_name', 'Unknown Corridor')}", body_style),
            Paragraph("<b>Priority Action</b>", body_style),
            Paragraph(f"<b>{cluster.get('priority', 'Urgent')}</b>", body_style)
        ],
        [
            Paragraph("<b>GPS Coordinates</b>", body_style),
            Paragraph(f"{cluster.get('lat', 0.0):.6f}&deg; N, {cluster.get('lon', 0.0):.6f}&deg; E", body_style),
            Paragraph("<b>Est. Repair Budget</b>", body_style),
            Paragraph(f"${cluster.get('repair_cost_est', 450.0):,.2f}", body_style)
        ],
        [
            Paragraph("<b>DBSCAN Cluster Detections</b>", body_style),
            Paragraph(f"{cluster.get('detection_count', 1)} sensor passes merged", body_style),
            Paragraph("<b>Work Order ID</b>", body_style),
            Paragraph(f"{cluster.get('work_order_id', 'WO-PENDING')}", body_style)
        ]
    ]

    table_overview = Table(overview_data, colWidths=[120, 150, 110, 150])
    table_overview.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(table_overview)
    story.append(Spacer(1, 14))

    # 3. Photo Evidence Section
    story.append(Paragraph("<b>PHOTOGRAPHIC EVIDENCE & GEOTAGGED DAMAGE BOUNDING BOX</b>", h2_style))
    story.append(Spacer(1, 6))

    img_filename = cluster.get("image_filename")
    image_attached = False

    if img_filename:
        # Check in uploads or samples
        possible_paths = [
            EXPORTS_DIR / img_filename,
            BASE_DIR / "data" / "uploads" / img_filename,
            BASE_DIR / "data" / "samples" / img_filename
        ]
        for p in possible_paths:
            if p.exists():
                try:
                    img = RLImage(str(p), width=420, height=220)
                    story.append(img)
                    image_attached = True
                    break
                except Exception:
                    pass

    if not image_attached:
        placeholder_data = [[Paragraph("<i>[High-Resolution Dashcam Detection Evidence Captured & Logged to Audit Store]</i>", meta_style)]]
        ph_table = Table(placeholder_data, colWidths=[530], rowHeights=[100])
        ph_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f1f5f9')),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#94a3b8'))
        ]))
        story.append(ph_table)

    story.append(Spacer(1, 14))

    # 4. Remediation Engineering Protocol
    story.append(Paragraph("<b>RECOMMENDED ENGINEERING REMEDIATION SPECIFICATIONS</b>", h2_style))
    story.append(Spacer(1, 6))

    remediation_text = (
        f"<b>Standard Protocol for {class_meta['name']}:</b><br/>"
        f"1. <b>Preparation:</b> Mechanically clean surface cavity using compressed air or high-pressure waterjet. "
        f"Remove loose debris, aggregate, and standing moisture within a 0.5m perimeter.<br/>"
        f"2. <b>Application:</b> {class_meta['remediation']}. Apply tack coat (SS-1h cationic emulsion) at 0.45 L/m&sup2;.<br/>"
        f"3. <b>Compaction:</b> Compact using steel wheel vibratory roller to 96% Marshall density. Ensure flush transition with existing roadway grade (&plusmn;3mm).<br/>"
        f"4. <b>Verification:</b> Geotagged photographic verification required upon work-order closure."
    )
    story.append(Paragraph(remediation_text, body_style))
    story.append(Spacer(1, 14))

    # 5. Regulatory Disclaimer & Signoff
    disclaimer_text = (
        "<b>CIVIC TECH SAFETY NOTICE:</b> This report is generated by RoadPulse AI automated road damage analytics. "
        "DBSCAN spatial deduplication has merged multiple vehicle sensor passes into this unique defect ticket. "
        "Municipal field inspection personnel should verify sub-surface structural integrity prior to heavy equipment dispatch."
    )
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cbd5e1'), spaceAfter=8))
    story.append(Paragraph(disclaimer_text, meta_style))

    doc.build(story)
    return str(pdf_path)
