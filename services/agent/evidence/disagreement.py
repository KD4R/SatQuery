"""
evidence/disagreement.py — Multi-sensor disagreement and discrepancy analysis.
"""

from typing import Optional
from pydantic import BaseModel, Field


class DisagreementReport(BaseModel):
    """Structured report detailing discrepancies between SAR and Optical water detections."""

    sar_area_sqkm: float = Field(ge=0.0)
    optical_area_sqkm: float = Field(ge=0.0)
    intersection_sqkm: float = Field(ge=0.0)
    union_sqkm: float = Field(ge=0.0)
    iou_score: float = Field(ge=0.0, le=1.0)
    disagreement_percentage: float = Field(ge=0.0, le=100.0)
    disagreement_area_sqkm: float = Field(ge=0.0)
    likely_anomaly: Optional[str] = None
    arbitrated_water_area_sqkm: float = Field(ge=0.0)


def analyze_sensor_disagreement(
    sar_area_sqkm: float,
    optical_area_sqkm: float,
    intersection_sqkm: float,
    terrain_slope_deg: float = 0.0,
) -> DisagreementReport:
    """
    Computes IoU and detects terrain radar shadow or optical cloud shadow anomalies.
    """
    if sar_area_sqkm < 0.0 or optical_area_sqkm < 0.0 or intersection_sqkm < 0.0:
        raise ValueError("Area values must be non-negative")

    if intersection_sqkm > min(sar_area_sqkm, optical_area_sqkm):
        raise ValueError(
            f"Intersection ({intersection_sqkm} sq km) cannot exceed "
            f"individual sensor areas ({min(sar_area_sqkm, optical_area_sqkm)} sq km)"
        )

    union_sqkm = sar_area_sqkm + optical_area_sqkm - intersection_sqkm
    if union_sqkm == 0.0:
        return DisagreementReport(
            sar_area_sqkm=0.0,
            optical_area_sqkm=0.0,
            intersection_sqkm=0.0,
            union_sqkm=0.0,
            iou_score=1.0,
            disagreement_percentage=0.0,
            disagreement_area_sqkm=0.0,
            likely_anomaly=None,
            arbitrated_water_area_sqkm=0.0,
        )

    iou = round(intersection_sqkm / union_sqkm, 4)
    disagreement_area = round(union_sqkm - intersection_sqkm, 2)
    disagreement_pct = round((disagreement_area / union_sqkm) * 100.0, 2)

    anomaly = None
    # If SAR detects water on steep slopes where Optical does not -> Radar Shadow
    if terrain_slope_deg > 15.0 and (sar_area_sqkm - optical_area_sqkm) > (
        0.25 * optical_area_sqkm
    ):
        anomaly = "RADAR_SHADOW_TERRAIN_ARTEFACT"
        arbitrated_area = optical_area_sqkm
    # If Optical detects water where SAR does not -> Cloud shadow misclassification
    elif (optical_area_sqkm - sar_area_sqkm) > (0.30 * sar_area_sqkm):
        anomaly = "OPTICAL_CLOUD_SHADOW_CONFUSION"
        arbitrated_area = sar_area_sqkm
    else:
        arbitrated_area = round((sar_area_sqkm + optical_area_sqkm) / 2.0, 2)

    return DisagreementReport(
        sar_area_sqkm=sar_area_sqkm,
        optical_area_sqkm=optical_area_sqkm,
        intersection_sqkm=intersection_sqkm,
        union_sqkm=round(union_sqkm, 2),
        iou_score=iou,
        disagreement_percentage=disagreement_pct,
        disagreement_area_sqkm=disagreement_area,
        likely_anomaly=anomaly,
        arbitrated_water_area_sqkm=arbitrated_area,
    )
