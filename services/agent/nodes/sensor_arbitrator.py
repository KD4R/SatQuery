"""
nodes/sensor_arbitrator.py — Adaptive sensor arbitration based on physics, weather, and hazard type.
"""

from typing import Optional
from packages.contracts.agent import SensorDecisionResponse


def arbitrate_sensors(
    hazard_type: str = "flood",
    cloud_cover: float = 0.0,
    is_night: bool = False,
    priority: str = "balanced",
    trace_id: Optional[str] = None,
) -> SensorDecisionResponse:
    """
    Arbitrates between active microwave (SAR) and passive optical sensors based on
    environmental conditions, cloud cover, and solar illumination.
    """
    if not (0.0 <= cloud_cover <= 100.0):
        raise ValueError(f"Cloud cover {cloud_cover}% must be between 0.0 and 100.0")

    hazard = hazard_type.lower().strip()
    if not hazard:
        raise ValueError("Hazard type cannot be empty")

    # Decision logic
    if is_night:
        primary = "SAR"
        secondary = None
        score = 0.98
        rationale = (
            "Nighttime conditions preclude optical sensors; SAR active microwave is selected."
        )
    elif cloud_cover > 20.0:
        primary = "SAR"
        secondary = "OPTICAL" if cloud_cover < 60.0 else None
        score = 0.95
        rationale = (
            f"Atmospheric cloud cover at {cloud_cover:.1f}% exceeds optical threshold (20%); "
            "SAR C-band microwave selected for cloud-penetrating ground observation."
        )
    elif hazard in ("flood", "inundation") and priority == "accuracy":
        # Optical + SAR fusion
        primary = "SAR"
        secondary = "OPTICAL"
        score = 0.92
        rationale = (
            "Flood inundation mapping benefits from SAR specular reflectance of open water "
            "supplemented by optical multispectral NDWI verification."
        )
    else:
        primary = "OPTICAL"
        secondary = "SAR"
        score = 0.90
        rationale = (
            f"Clear atmospheric conditions ({cloud_cover:.1f}% cloud) allow high-resolution "
            "optical multispectral imagery with secondary SAR radar backing."
        )

    return SensorDecisionResponse(
        primary_sensor=primary,
        secondary_sensor=secondary,
        rationale=rationale,
        arbitration_score=score,
        trace_id=trace_id,
    )
