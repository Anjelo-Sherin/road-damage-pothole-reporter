import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
from src.config import DAMAGE_CLASSES, UPLOAD_DIR

class RoadDamageDetector:
    """
    Computer Vision Road Damage & Pothole Detector.
    Supports RDD2022 (Road Damage Dataset) standards:
    - D00: Longitudinal Crack (parallel to driving direction)
    - D10: Transverse Crack (perpendicular to road lane)
    - D20: Alligator Crack (fatigue mesh / crocodile pattern)
    - D40: Pothole / Severe Cavity
    """

    def __init__(self, min_confidence: float = 0.50):
        self.min_confidence = min_confidence

    def analyze_frame(self, image_np: np.ndarray, frame_id: int = 0) -> List[Dict[str, Any]]:
        """
        Analyzes a single BGR image array for road defects.
        Extracts road plane ROI (lower 60% of dashcam view, excluding car hood/sky),
        performs multi-scale morphological, gradient, and texture filtering to identify
        potholes and cracks with precise spatial coordinates.
        """
        h, w = image_np.shape[:2]
        detections = []

        # Define driving road surface ROI (exclude sky above 35% and car bonnet below 95%)
        roi_top = int(h * 0.35)
        roi_bottom = int(h * 0.95)
        roi_left = int(w * 0.05)
        roi_right = int(w * 0.95)

        roi = image_np[roi_top:roi_bottom, roi_left:roi_right]
        roi_h, roi_w = roi.shape[:2]

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)

        # 1. Dark cavity filter for potholes (D40)
        # Potholes exhibit sharp localized luminance drop relative to surrounding pavement
        kernel_large = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
        tophat = cv2.morphologyEx(blurred, cv2.MORPH_BLACKHAT, kernel_large)
        _, thresh_pothole = cv2.threshold(tophat, 35, 255, cv2.THRESH_BINARY)

        contours_pothole, _ = cv2.findContours(thresh_pothole, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours_pothole:
            area = cv2.contourArea(cnt)
            if area < 650:
                continue

            bx, by, bw, bh = cv2.boundingRect(cnt)
            aspect_ratio = bw / float(bh) if bh > 0 else 1.0

            # Filter out extreme horizontal or vertical noise lines
            if 0.4 <= aspect_ratio <= 3.5:
                # Convert back to full image coordinates
                fx1 = (roi_left + bx) / w
                fy1 = (roi_top + by) / h
                fx2 = (roi_left + bx + bw) / w
                fy2 = (roi_top + by + bh) / h

                area_ratio = (bw * bh) / (w * h)
                # Compute localized texture contrast
                mask_crop = gray[by:by+bh, bx:bx+bw]
                depth_variance = float(np.std(mask_crop)) if mask_crop.size > 0 else 20.0
                conf = min(0.96, max(0.65, 0.70 + (depth_variance / 180.0) + min(0.15, area_ratio * 4.0)))

                severity = self.calculate_severity("D40", area_ratio, conf)
                detections.append({
                    "damage_class": "D40",
                    "class_name": DAMAGE_CLASSES["D40"]["name"],
                    "confidence": round(conf, 3),
                    "bbox": [round(fx1, 4), round(fy1, 4), round(fx2, 4), round(fy2, 4)],
                    "bbox_area_ratio": round(area_ratio, 5),
                    "severity_score": severity["score"],
                    "severity_tier": severity["tier"]
                })

        # 2. Crack detection via multi-directional gradient edges (D00, D10, D20)
        sobel_x = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
        grad_mag_f = np.sqrt(sobel_x**2 + sobel_y**2)
        max_val = grad_mag_f.max()
        if max_val > 0:
            grad_mag = np.uint8(np.clip((grad_mag_f / max_val) * 255.0, 0, 255))
        else:
            grad_mag = np.zeros(blurred.shape, dtype=np.uint8)

        _, thresh_cracks = cv2.threshold(grad_mag, 65, 255, cv2.THRESH_BINARY)
        kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed_cracks = cv2.morphologyEx(thresh_cracks, cv2.MORPH_CLOSE, kernel_close)

        contours_crack, _ = cv2.findContours(closed_cracks, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours_crack:
            area = cv2.contourArea(cnt)
            if area < 500:
                continue

            bx, by, bw, bh = cv2.boundingRect(cnt)
            area_ratio = (bw * bh) / (w * h)

            # Avoid huge bounding boxes that encompass half the road
            if area_ratio > 0.35:
                continue

            aspect_ratio = bw / float(bh) if bh > 0 else 1.0

            # Determine crack classification:
            # Aspect ratio > 2.2 -> Transverse Crack (D10)
            # Aspect ratio < 0.55 -> Longitudinal Crack (D00)
            # Else spiderweb / high perimeter -> Alligator Crack (D20)
            peri = cv2.arcLength(cnt, True)
            complexity = (peri ** 2) / (area + 1e-5)

            if aspect_ratio >= 2.2:
                cls_code = "D10"
            elif aspect_ratio <= 0.55:
                cls_code = "D00"
            elif complexity > 30.0:
                cls_code = "D20"
            else:
                cls_code = "D20"

            fx1 = (roi_left + bx) / w
            fy1 = (roi_top + by) / h
            fx2 = (roi_left + bx + bw) / w
            fy2 = (roi_top + by + bh) / h

            conf = min(0.94, max(0.60, 0.68 + min(0.20, area_ratio * 3.5)))
            severity = self.calculate_severity(cls_code, area_ratio, conf)

            # Check if this overlaps with an already detected pothole
            overlap = False
            for d in detections:
                if d["damage_class"] == "D40":
                    dx1, dy1, dx2, dy2 = d["bbox"]
                    if not (fx2 < dx1 or fx1 > dx2 or fy2 < dy1 or fy1 > dy2):
                        overlap = True
                        break

            if not overlap:
                detections.append({
                    "damage_class": cls_code,
                    "class_name": DAMAGE_CLASSES[cls_code]["name"],
                    "confidence": round(conf, 3),
                    "bbox": [round(fx1, 4), round(fy1, 4), round(fx2, 4), round(fy2, 4)],
                    "bbox_area_ratio": round(area_ratio, 5),
                    "severity_score": severity["score"],
                    "severity_tier": severity["tier"]
                })

        # Sort detections by severity score descending
        detections.sort(key=lambda x: x["severity_score"], reverse=True)
        return detections[:6]  # Top prominent defects per frame

    def calculate_severity(self, damage_class: str, area_ratio: float, confidence: float) -> Dict[str, Any]:
        """
        Computes civic severity index (0 - 100) based on damage class weight,
        surface area coverage, and detection confidence.
        """
        class_meta = DAMAGE_CLASSES.get(damage_class, {"weight": 1.0, "name": "Defect"})
        weight = class_meta["weight"]

        # Base score scaled by class danger + area + confidence
        raw_score = (weight * 25.0) + (min(area_ratio, 0.15) / 0.15 * 35.0) + (confidence * 25.0)
        score = round(min(100.0, max(10.0, raw_score)), 1)

        if score >= 75.0:
            tier = "Critical"
        elif score >= 50.0:
            tier = "High"
        elif score >= 30.0:
            tier = "Medium"
        else:
            tier = "Low"

        return {"score": score, "tier": tier}

    def annotate_image(
        self,
        image_np: np.ndarray,
        detections: List[Dict[str, Any]],
        gps_info: Optional[Dict[str, Any]] = None
    ) -> np.ndarray:
        """
        Draws sleek bounding boxes, class labels, and telemetry banner.
        """
        annotated = image_np.copy()
        h, w = annotated.shape[:2]

        color_map = {
            "D00": (248, 189, 56),   # Cyan/Blue
            "D10": (36, 191, 251),   # Amber/Yellow
            "D20": (60, 146, 251),   # Orange
            "D40": (94, 63, 244)     # Red/Crimson (BGR)
        }

        for det in detections:
            cls = det["damage_class"]
            conf = det["confidence"]
            score = det["severity_score"]
            tier = det["severity_tier"]
            b = det["bbox"]

            x1 = int(b[0] * w)
            y1 = int(b[1] * h)
            x2 = int(b[2] * w)
            y2 = int(b[3] * h)

            col = color_map.get(cls, (0, 255, 255))

            # Bounding box with corner accents
            cv2.rectangle(annotated, (x1, y1), (x2, y2), col, 2)
            corner_len = min(16, min(x2 - x1, y2 - y1) // 3)
            # Top-left corner
            cv2.line(annotated, (x1, y1), (x1 + corner_len, y1), col, 4)
            cv2.line(annotated, (x1, y1), (x1, y1 + corner_len), col, 4)
            # Bottom-right corner
            cv2.line(annotated, (x2, y2), (x2 - corner_len, y2), col, 4)
            cv2.line(annotated, (x2, y2), (x2, y2 - corner_len), col, 4)

            # Label banner
            label = f"{cls} {det['class_name']}: {int(conf*100)}% | Sev: {score} ({tier})"
            (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated, (x1, max(0, y1 - th - 8)), (x1 + tw + 10, y1), col, -1)
            cv2.putText(annotated, label, (x1 + 5, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (20, 20, 20), 1, cv2.LINE_AA)

        # Telemetry HUD on top left if GPS provided
        if gps_info:
            hud_text = f"GPS: {gps_info.get('lat', 0.0):.6f}, {gps_info.get('lon', 0.0):.6f} | Speed: {gps_info.get('speed_kmh', 35):.1f} km/h | {gps_info.get('road_name', 'Survey Drive')}"
            cv2.rectangle(annotated, (10, 10), (w - 10, 42), (20, 24, 33), -1)
            cv2.rectangle(annotated, (10, 10), (w - 10, 42), (70, 80, 100), 1)
            cv2.putText(annotated, hud_text, (20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (240, 245, 255), 1, cv2.LINE_AA)

        return annotated
