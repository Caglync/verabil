"""
VeraBil — OpenAI Vision Service
Sends base64-encoded vehicle image to GPT-4o and parses structured damage data.
"""

import json
import logging
import re

from openai import OpenAI
from config import Config

log = logging.getLogger(__name__)
_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not Config.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set in environment.")
        _client = OpenAI(api_key=Config.OPENAI_API_KEY)
    return _client


SYSTEM_PROMPT = """You are VeraBil, an expert automotive damage assessment AI.

Analyze the uploaded vehicle image carefully and return ONLY valid JSON.
No markdown, no prose, no code fences.

IMPORTANT ANALYSIS RULES:
- Focus only on visible real damage, not reflections, shadows, dirt, perspective, or normal panel gaps.
- Identify the most damaged visible vehicle part.
- Prefer specific parts over generic names.
- If the front corner is damaged, distinguish between:
  Front Bumper, Hood, Front Grille, Left Headlight, Right Headlight, Left Fender, Right Fender.
- Do NOT say "Front Bumper" unless the bumper itself is clearly damaged.
- Do NOT say "Crack" unless there is a visible split, fracture, or broken line.
- If the damage is deformation without a visible split, use "Dent".
- If paint is scraped or missing, use "Paint Damage".
- If glass or lamp lens is broken, use "Glass Damage" or "Broken Part".
- If multiple parts are damaged, choose the most severe / most visually obvious part.

Allowed parts:
Front Bumper, Rear Bumper, Hood, Trunk, Roof,
Front Grille,
Left Headlight, Right Headlight,
Left Tail Light, Right Tail Light,
Left Fender, Right Fender,
Left Front Door, Right Front Door,
Left Rear Door, Right Rear Door,
Left Side Mirror, Right Side Mirror,
Windshield, Rear Window,
Left Quarter Panel, Right Quarter Panel,
Wheel, Vehicle Body

Allowed damage types:
Scratch, Dent, Crack, Broken Part, Paint Damage, Glass Damage

Severity rules:
- Minor: small scratch, small paint damage, light cosmetic issue.
- Medium: visible dent, moderate bumper/fender/door damage, damaged lamp housing but vehicle shape mostly intact.
- Severe: broken/missing part, crushed area, exposed internal components, major structural deformation, replacement likely needed.

Return this exact JSON schema:
{
  "part": "one allowed part",
  "damage_type": "one allowed damage type",
  "severity": "Minor | Medium | Severe",
  "confidence": 0-100,
  "explanation": "1-2 sentence professional explanation based only on visible damage."
}
"""


def analyze_image_with_vision(image_b64: str, mime_type: str) -> dict:
    """
    Send image to OpenAI Vision API and return parsed damage analysis dict.
    Raises RuntimeError on failure.
    """
    client = _get_client()

    log.info("Sending image to OpenAI Vision (%s, model=%s)", mime_type, Config.OPENAI_MODEL)

    response = client.chat.completions.create(
        model=Config.OPENAI_MODEL,
        max_tokens=700,
        temperature=0.0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Analyze this vehicle damage image. "
                            "Return only the JSON object. "
                            "Be conservative: do not overstate damage type or severity."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_b64}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ],
    )

    raw = response.choices[0].message.content.strip()
    log.debug("Raw OpenAI response: %s", raw)

    return _parse_ai_response(raw)


def _parse_ai_response(raw: str) -> dict:
    """Extract and validate JSON from model output."""
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise RuntimeError(f"Could not parse AI response as JSON: {raw[:200]}")

    valid_parts = {
        "Front Bumper", "Rear Bumper", "Hood", "Trunk", "Roof",
        "Front Grille",
        "Left Headlight", "Right Headlight",
        "Left Tail Light", "Right Tail Light",
        "Left Fender", "Right Fender",
        "Left Front Door", "Right Front Door",
        "Left Rear Door", "Right Rear Door",
        "Left Side Mirror", "Right Side Mirror",
        "Windshield", "Rear Window",
        "Left Quarter Panel", "Right Quarter Panel",
        "Wheel", "Vehicle Body",
    }

    valid_damage_types = {
        "Scratch", "Dent", "Crack", "Broken Part", "Paint Damage", "Glass Damage"
    }

    valid_severities = {"Minor", "Medium", "Severe"}

    part = str(data.get("part", "Vehicle Body")).strip()
    damage_type = str(data.get("damage_type", "Scratch")).strip()
    severity = str(data.get("severity", "Minor")).strip()

    if part not in valid_parts:
        part = _normalize_part(part)

    if damage_type not in valid_damage_types:
        damage_type = _normalize_damage_type(damage_type)

    if severity not in valid_severities:
        severity = _normalize_severity(severity)

    try:
        confidence = int(data.get("confidence", 70))
    except (TypeError, ValueError):
        confidence = 70

    confidence = max(0, min(100, confidence))

    explanation = str(data.get("explanation", "")).strip()

    return {
        "part": part,
        "damage_type": damage_type,
        "severity": severity,
        "confidence": confidence,
        "explanation": explanation,
    }


def _normalize_part(part: str) -> str:
    p = part.lower()

    if "headlight" in p or "lamp" in p:
        if "right" in p:
            return "Right Headlight"
        if "left" in p:
            return "Left Headlight"
        return "Left Headlight"

    if "tail" in p:
        if "right" in p:
            return "Right Tail Light"
        if "left" in p:
            return "Left Tail Light"
        return "Left Tail Light"

    if "bumper" in p:
        if "rear" in p or "back" in p:
            return "Rear Bumper"
        return "Front Bumper"

    if "hood" in p or "bonnet" in p:
        return "Hood"

    if "fender" in p or "wing" in p:
        if "right" in p:
            return "Right Fender"
        return "Left Fender"

    if "door" in p:
        if "rear" in p and "right" in p:
            return "Right Rear Door"
        if "rear" in p and "left" in p:
            return "Left Rear Door"
        if "right" in p:
            return "Right Front Door"
        return "Left Front Door"

    if "mirror" in p:
        if "right" in p:
            return "Right Side Mirror"
        return "Left Side Mirror"

    if "windshield" in p or "windscreen" in p:
        return "Windshield"

    if "grille" in p or "grill" in p:
        return "Front Grille"

    if "roof" in p:
        return "Roof"

    if "trunk" in p or "boot" in p:
        return "Trunk"

    if "quarter" in p:
        if "right" in p:
            return "Right Quarter Panel"
        return "Left Quarter Panel"

    if "wheel" in p or "rim" in p:
        return "Wheel"

    return "Vehicle Body"


def _normalize_damage_type(damage_type: str) -> str:
    d = damage_type.lower()

    if "dent" in d or "deform" in d or "bent" in d:
        return "Dent"

    if "crack" in d or "fracture" in d or "split" in d:
        return "Crack"

    if "paint" in d or "scrape" in d or "scuff" in d:
        return "Paint Damage"

    if "glass" in d or "windshield" in d:
        return "Glass Damage"

    if "broken" in d or "missing" in d or "shattered" in d:
        return "Broken Part"

    if "scratch" in d:
        return "Scratch"

    return "Scratch"


def _normalize_severity(severity: str) -> str:
    s = severity.lower()

    if "severe" in s or "heavy" in s or "major" in s:
        return "Severe"

    if "medium" in s or "moderate" in s:
        return "Medium"

    return "Minor"