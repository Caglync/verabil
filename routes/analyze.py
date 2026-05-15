"""
VeraBil — /analyze and /result endpoints
POST /analyze        →  runs AI analysis, caches result, returns JSON
GET  /result/<id>    →  retrieves cached result by analysis_id
"""

import os
import uuid
import base64
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

from services.openai_service  import analyze_image_with_vision
from services.cost_calculator import calculate_repair_cost
from services.db_service      import (
    get_part_pricing,
    get_damage_multipliers,
    save_analysis_record,
)

log = logging.getLogger(__name__)
analyze_bp = Blueprint("analyze", __name__)

# In-memory result cache  {analysis_id: result_dict}
# Holds the last 50 results; sufficient for a demo/graduation project.
_result_cache: dict = {}
_CACHE_MAX = 50


def _allowed_file(filename: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


def _cache_result(analysis_id: str, result: dict) -> None:
    if len(_result_cache) >= _CACHE_MAX:
        oldest_key = next(iter(_result_cache))
        del _result_cache[oldest_key]
    _result_cache[analysis_id] = result


# ── POST /analyze ─────────────────────────────────────────────
@analyze_bp.post("/analyze")
def analyze():
    if "image" not in request.files:
        return jsonify({"error": "No image file provided."}), 400

    file = request.files["image"]
    if not file.filename or not _allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Accepted: jpg, png, webp."}), 400

    filename  = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    try:
        with open(save_path, "rb") as f:
            image_b64 = base64.standard_b64encode(f.read()).decode()

        mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                    "png": "image/png",  "webp": "image/webp"}
        ext  = filename.rsplit(".", 1)[-1].lower()
        mime = mime_map.get(ext, "image/jpeg")

        ai_result   = analyze_image_with_vision(image_b64, mime)
        part        = ai_result.get("part",        "Unknown Part")
        damage_type = ai_result.get("damage_type", "Unknown")
        severity    = ai_result.get("severity",    "Minor")
        confidence  = ai_result.get("confidence",  70)
        explanation = ai_result.get("explanation", "")

        pricing     = get_part_pricing(part)
        multipliers = get_damage_multipliers(damage_type, severity)
        cost_result = calculate_repair_cost(pricing, multipliers, severity)

        vehicle_brand = request.form.get("brand", "")
        vehicle_model = request.form.get("model", "")
        vehicle_year  = request.form.get("year",  "")

        analysis_id = f"VB-{uuid.uuid4().hex[:8].upper()}"
        timestamp   = datetime.utcnow().isoformat()

        try:
            save_analysis_record(
                analysis_id    = analysis_id,
                image_path     = filename,
                ai_result      = ai_result,
                estimated_cost = cost_result["total"],
                timestamp      = timestamp,
            )
        except Exception as db_err:
            log.warning("Could not save to DB (non-fatal): %s", db_err)

        result = {
            "success":      True,
            "analysis_id":  analysis_id,
            "timestamp":    timestamp,
            "part":         part,
            "damage_type":  damage_type,
            "severity":     severity,
            "confidence":   confidence,
            "explanation":  explanation,
            "repair_recommendation": cost_result.get("repair_type", "Repair"),
            "vehicle_brand": vehicle_brand,
            "vehicle_model": vehicle_model,
            "vehicle_year":  vehicle_year,
            "estimated_cost": cost_result["total"],
            "cost_breakdown": {
                "base_cost":    cost_result["base_cost"],
                "paint_cost":   cost_result["paint_cost"],
                "labor_cost":   cost_result["labor_cost"],
                "severity_adj": cost_result["severity_adj"],
                "total":        cost_result["total"],
            },
        }

        # Cache so GET /result/<id> can retrieve it
        _cache_result(analysis_id, result)

        return jsonify(result), 200

    except Exception as exc:
        log.exception("Analysis pipeline failed")
        return jsonify({"error": str(exc)}), 500

    finally:
        try:
            os.remove(save_path)
        except OSError:
            pass


# ── GET /result/<analysis_id> ─────────────────────────────────
@analyze_bp.get("/result/<analysis_id>")
def get_result(analysis_id: str):
    result = _result_cache.get(analysis_id)
    if not result:
        return jsonify({"error": "Result not found or expired."}), 404
    return jsonify(result), 200
