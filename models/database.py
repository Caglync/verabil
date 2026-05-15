"""
VeraBil — Database Model Definitions (documentation / reference)

These dataclasses mirror the MSSQL schema defined in database/schema.sql.
They are used for type hints and documentation — not ORM mapping.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Vehicle:
    vehicle_id:  int
    brand:       str
    model:       str
    year:        int
    created_at:  datetime


@dataclass
class VehiclePart:
    part_id:          int
    part_name:        str
    repair_cost:      float
    replacement_cost: float
    paint_cost:       float
    created_at:       datetime


@dataclass
class DamageType:
    damage_id:           int
    damage_type:         str           # Scratch | Dent | Crack | Broken Part | Paint Damage | Glass Damage
    severity:            str           # Minor | Medium | Severe
    labor_multiplier:    float
    severity_multiplier: float


@dataclass
class AnalysisHistory:
    history_id:      int
    analysis_id:     str
    image_path:      str
    ai_result_json:  str
    estimated_cost:  float
    created_at:      datetime
