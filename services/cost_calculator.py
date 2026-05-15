"""
VeraBil — Repair Cost Calculation Engine

Formula:
  base_cost    = repair_cost  (Minor/Medium)  OR  replacement_cost  (Severe)
  paint_cost   = part.paint_cost  (if paint-related damage or Severe)
  labor_cost   = base_cost × labor_multiplier
  severity_adj = base_cost × (severity_multiplier - 1)
  total        = base_cost + paint_cost + labor_cost + severity_adj
"""

import logging
from typing import TypedDict

log = logging.getLogger(__name__)

# Fallback pricing when DB lookup fails
FALLBACK_PRICING = {
    "repair_cost":      250.0,
    "replacement_cost": 850.0,
    "paint_cost":       180.0,
}

FALLBACK_MULTIPLIERS = {
    "labor_multiplier":    0.40,
    "severity_multiplier": 1.0,
}

PAINT_DAMAGE_TYPES = {"Scratch", "Paint Damage", "Crack"}


class CostResult(TypedDict):
    base_cost:    float
    paint_cost:   float
    labor_cost:   float
    severity_adj: float
    total:        float
    repair_type:  str


def calculate_repair_cost(
    pricing:     dict,
    multipliers: dict,
    severity:    str,
) -> CostResult:
    """
    pricing     — dict with keys: repair_cost, replacement_cost, paint_cost
    multipliers — dict with keys: labor_multiplier, severity_multiplier
    severity    — "Minor" | "Medium" | "Severe"
    """
    p = {**FALLBACK_PRICING,     **pricing}
    m = {**FALLBACK_MULTIPLIERS, **multipliers}

    sev = severity.strip().capitalize()

    # Determine repair vs replacement
    if sev == "Severe":
        base_cost   = float(p["replacement_cost"])
        repair_type = "Replacement"
    else:
        base_cost   = float(p["repair_cost"])
        repair_type = "Repair"

    # Apply severity multiplier to base
    sev_mul      = float(m.get("severity_multiplier", 1.0))
    severity_adj = round(base_cost * (sev_mul - 1), 2)

    # Labor
    labor_mul  = float(m.get("labor_multiplier", 0.40))
    labor_cost = round(base_cost * labor_mul, 2)

    # Paint — always for Severe, or if damage type is paint-related (passed via multipliers dict)
    include_paint = sev == "Severe" or m.get("include_paint", False)
    paint_cost    = round(float(p["paint_cost"]), 2) if include_paint else 0.0

    total = round(base_cost + severity_adj + labor_cost + paint_cost, 2)

    log.info(
        "Cost calc: base=%.2f  sev_adj=%.2f  labor=%.2f  paint=%.2f  total=%.2f",
        base_cost, severity_adj, labor_cost, paint_cost, total,
    )

    return CostResult(
        base_cost    = round(base_cost, 2),
        paint_cost   = paint_cost,
        labor_cost   = labor_cost,
        severity_adj = severity_adj,
        total        = total,
        repair_type  = repair_type,
    )
