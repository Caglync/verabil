"""
VeraBil — MSSQL Database Service
All database I/O lives here. pyodbc is used for MSSQL connectivity.
Returns safe fallback values when the DB is unreachable (dev mode).
"""
import json
import logging
from contextlib import contextmanager
from typing import Generator

import pyodbc

from config import Config

log = logging.getLogger(__name__)

# ── Windows Authentication Connection ─────────────────────────
_connection_string = (
    f"DRIVER={{{Config.DB_DRIVER}}};"
    f"SERVER={Config.DB_SERVER};"
    f"DATABASE={Config.DB_NAME};"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


@contextmanager
def get_db() -> Generator[pyodbc.Connection, None, None]:
    conn = pyodbc.connect(_connection_string, timeout=10)

    try:
        yield conn
        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ── Part pricing lookup ───────────────────────────────────────
_PART_ALIASES = {
    "front bumper": "Front Bumper",
    "rear bumper": "Rear Bumper",
    "hood": "Hood",
    "windshield": "Windshield",
    "door": "Door Panel",
    "left door": "Door Panel",
    "right door": "Door Panel",
    "fender": "Fender",
    "left fender": "Fender",
    "right fender": "Fender",
    "headlight": "Headlight Assembly",
    "tail light": "Tail Light Assembly",
    "roof": "Roof Panel",
    "trunk": "Trunk Lid",
    "side mirror": "Side Mirror",
    "quarter panel": "Quarter Panel",
    "wheel": "Wheel / Rim",
    "grille": "Front Grille",
    "vehicle body": "Door Panel",
}

_FALLBACK_PRICING = {
    "repair_cost": 250.0,
    "replacement_cost": 850.0,
    "paint_cost": 180.0,
}


def get_part_pricing(part_name: str) -> dict:
    normalized = _normalize_part(part_name)

    try:
        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT repair_cost, replacement_cost, paint_cost
                FROM VehicleParts
                WHERE LOWER(part_name) = LOWER(?)
                """,
                (normalized,)
            )

            row = cursor.fetchone()

            if row:
                return {
                    "repair_cost": float(row.repair_cost),
                    "replacement_cost": float(row.replacement_cost),
                    "paint_cost": float(row.paint_cost),
                }

            log.warning("Part '%s' not in DB — using fallback pricing.", normalized)

    except pyodbc.Error as exc:
        log.warning("DB unavailable for part lookup (%s) — using fallback.", exc)

    return dict(_FALLBACK_PRICING)


def _normalize_part(raw: str) -> str:
    lower = raw.lower().strip()

    for alias, canonical in _PART_ALIASES.items():
        if alias in lower:
            return canonical

    return raw.strip().title()


# ── Damage multipliers lookup ─────────────────────────────────
_FALLBACK_MULTIPLIERS = {
    "labor_multiplier": 0.40,
    "severity_multiplier": 1.00,
    "include_paint": False,
}

_PAINT_TYPES = {"Scratch", "Paint Damage"}


def get_damage_multipliers(damage_type: str, severity: str) -> dict:
    include_paint = damage_type in _PAINT_TYPES or severity == "Severe"

    try:
        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT labor_multiplier, severity_multiplier
                FROM DamageTypes
                WHERE LOWER(damage_type) = LOWER(?)
                AND LOWER(severity) = LOWER(?)
                """,
                (damage_type, severity)
            )

            row = cursor.fetchone()

            if row:
                return {
                    "labor_multiplier": float(row.labor_multiplier),
                    "severity_multiplier": float(row.severity_multiplier),
                    "include_paint": include_paint,
                }

            log.warning(
                "No multiplier row for (%s, %s) — fallback.",
                damage_type,
                severity
            )

    except pyodbc.Error as exc:
        log.warning("DB unavailable for multiplier lookup (%s) — fallback.", exc)

    fallback = dict(_FALLBACK_MULTIPLIERS)
    fallback["include_paint"] = include_paint

    if severity == "Medium":
        fallback["severity_multiplier"] = 1.25

    if severity == "Severe":
        fallback["severity_multiplier"] = 1.70

    return fallback


# ── Save analysis record ──────────────────────────────────────
def save_analysis_record(
    analysis_id: str,
    image_path: str,
    ai_result: dict,
    estimated_cost: float,
    timestamp: str,
) -> None:

    try:
        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO AnalysisHistory
                (analysis_id, image_path, ai_result_json, estimated_cost, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    analysis_id,
                    image_path,
                    json.dumps(ai_result),
                    estimated_cost,
                    timestamp,
                )
            )

        log.info("Saved analysis %s to DB.", analysis_id)

    except pyodbc.Error as exc:
        log.error("Failed to save analysis record: %s", exc)
        raise