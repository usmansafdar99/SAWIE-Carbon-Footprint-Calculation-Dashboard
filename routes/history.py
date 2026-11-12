"""
routes/history.py — Calculation history: save, view, and clear (OTP-gated)
Registered in app.py at url_prefix="/api/history"
"""
import os, secrets, time
from datetime import datetime

import requests as _requests
from flask import Blueprint, request, jsonify, g

from database import SessionLocal
from models import Farm, Season, Emission, Calculation
from routes.auth import login_required

history_bp = Blueprint("history", __name__)

# In-memory OTP store: {user_id: (otp_str, expires_timestamp)}
_clear_otp_store: dict = {}

BREVO_API_KEY    = os.getenv("BREVO_API_KEY", "")
BREVO_FROM_EMAIL = os.getenv("BREVO_FROM_EMAIL", "")
BREVO_FROM_NAME  = os.getenv("BREVO_FROM_NAME", "CarbonLens")


# ── POST /api/history/save ────────────────────────────────────────────────────
@history_bp.post("/save")
@login_required
def save_calculation():
    """Save one calculation in both history and normalized farm tables."""
    data = request.get_json() or {}
    db = SessionLocal()
    try:
        farm_id = data.get("farm_id") or ""
        season_name = data.get("season") or ""

        # Idempotency guard: if the exact same calculation for this user/farm/
        # season was saved in the last 10 seconds, skip re-inserting a history
        # row (protects against double-clicks / accidental double form-submits).
        from datetime import timedelta
        recent_dupe = db.query(Calculation).filter(
            Calculation.user_id == g.current_user.id,
            Calculation.farm_id == farm_id,
            Calculation.season == season_name,
            Calculation.total_co2_equiv == float(data.get("total_co2_equiv") or 0),
            Calculation.calculated_at >= datetime.utcnow() - timedelta(seconds=10),
        ).first()
        if recent_dupe:
            return jsonify({"message": "Already saved", "id": recent_dupe.id}), 200

        farm = db.query(Farm).filter(
            Farm.farm_id == farm_id,
            Farm.owner_id == g.current_user.id,
        ).first()
        if not farm:
            farm = Farm(
                farm_id=farm_id,
                farmer_name=data.get("farmer_name") or "Unknown",
                owner_id=g.current_user.id,
            )
            db.add(farm)
            db.flush()

        farm_fields = (
            "farmer_name", "province", "district", "tehsil", "village", "area",
            "harvested_area", "soil_texture", "soil_organic_matter", "soil_drainage",
            "soil_ph", "climate", "moisture_regime",
        )
        for field in farm_fields:
            value = data.get(field)
            if value is not None:
                setattr(farm, field, value)
        farm.updated_at = datetime.utcnow()

        season = db.query(Season).filter(
            Season.farm_id == farm.id,
            Season.season == season_name,
        ).first()
        season_fields = (
            "season", "crop", "variety", "seed_rate", "seed_source",
            "seed_cotton_yield", "fertiliser_data", "irrigation_data",
            "machinery_data", "pest_protection_data", "residue_data", "labour_data",
            "total_co2_equiv", "intensity_per_kg",
        )
        if not season:
            season = Season(farm_id=farm.id)
            db.add(season)
        for field in season_fields:
            value = data.get(field)
            if value is not None:
                setattr(season, field, value)
        season.updated_at = datetime.utcnow()
        db.flush()

        db.query(Emission).filter(Emission.season_id == season.id).delete()
        for source, value in (data.get("breakdown") or {}).items():
            if isinstance(value, dict):
                emission_value = value.get("value", 0)
                percentage = value.get("percentage", 0)
            else:
                emission_value = value
                total = float(data.get("total_co2_equiv") or 0)
                percentage = (float(value) / total * 100) if total else 0
            db.add(Emission(
                season_id=season.id,
                source=source,
                value=float(emission_value or 0),
                percentage=float(percentage or 0),
            ))

        calc = Calculation(
            user_id        = g.current_user.id,
            farm_id        = farm_id,
            farmer_name    = data.get("farmer_name")    or "",
            province       = data.get("province")       or "",
            district       = data.get("district")       or "",
            tehsil         = data.get("tehsil")         or "",
            village        = data.get("village")        or "",
            area           = float(data.get("area")           or 0),
            harvested_area = float(data.get("harvested_area") or 0),
            soil_texture          = data.get("soil_texture")          or "",
            soil_organic_matter   = data.get("soil_organic_matter")   or "",
            soil_drainage         = data.get("soil_drainage")         or "",
            soil_ph               = data.get("soil_ph")               or "",
            climate               = data.get("climate")               or "",
            moisture_regime       = data.get("moisture_regime")       or "",
            season            = data.get("season")            or "",
            crop              = data.get("crop")              or "Cotton",
            variety           = data.get("variety")           or "",
            seed_rate         = float(data.get("seed_rate")         or 0),
            seed_source       = data.get("seed_source")       or "",
            seed_cotton_yield = float(data.get("seed_cotton_yield") or 0),
            fertiliser_data      = data.get("fertiliser_data")      or {},
            irrigation_data      = data.get("irrigation_data")      or {},
            machinery_data       = data.get("machinery_data")       or {},
            pest_protection_data = data.get("pest_protection_data") or {},
            residue_data         = data.get("residue_data")         or {},
            labour_data          = data.get("labour_data")          or {},
            total_co2_equiv  = float(data.get("total_co2_equiv")  or 0),
            intensity_per_kg = float(data.get("intensity_per_kg") or 0),
            breakdown        = data.get("breakdown")        or {},
            calculated_at    = datetime.utcnow(),
        )
        db.add(calc)
        db.commit()
        return jsonify({"message": "Saved", "id": calc.id}), 201
    except Exception as e:
        db.rollback()
        return jsonify({"detail": str(e)}), 500
    finally:
        db.close()


# ── GET /api/history/ ─────────────────────────────────────────────────────────
@history_bp.get("/")
@login_required
def get_history():
    """Return all calculation records for the logged-in user (new + legacy)."""
    db = SessionLocal()
    try:
        rows = []

        # ── New Calculation records ────────────────────────────────────────────
        calcs = (
            db.query(Calculation)
            .filter(Calculation.user_id == g.current_user.id)
            .order_by(Calculation.calculated_at.desc())
            .all()
        )
        for c in calcs:
            rows.append({
                "source":           "calculation",
                "id":               c.id,
                "farm_id":          c.farm_id   or "—",
                "farmer_name":      c.farmer_name or "—",
                "district":         c.district,
                "province":         c.province,
                "season":           c.season,
                "crop":             c.crop,
                "seed_cotton_yield":c.seed_cotton_yield,
                "total_co2_equiv":  c.total_co2_equiv,
                "intensity_per_kg": c.intensity_per_kg,
                "calculated_at":    c.calculated_at.isoformat() if c.calculated_at else "",
            })

        # A saved calculation also updates the normalized Farm/Season tables.
        # Keep the Calculation row as the canonical history entry so that the
        # same save is not displayed once as new and once as legacy.
        calculation_keys = {
            (c.farm_id, c.season, c.total_co2_equiv)
            for c in calcs
        }

        # ── Legacy Farm / Season records ──────────────────────────────────────
        farms = db.query(Farm).filter(Farm.owner_id == g.current_user.id).all()
        for f in farms:
            for s in f.seasons:
                if s.total_co2_equiv is None:
                    continue
                if (f.farm_id, s.season, s.total_co2_equiv) in calculation_keys:
                    continue
                ts = s.updated_at or s.created_at
                rows.append({
                    "source":           "legacy",
                    "id":               f"legacy-{s.id}",
                    "farm_id":          f.farm_id,
                    "farmer_name":      f.farmer_name,
                    "district":         f.district,
                    "province":         f.province,
                    "season":           s.season,
                    "crop":             s.crop,
                    "seed_cotton_yield":s.seed_cotton_yield,
                    "total_co2_equiv":  s.total_co2_equiv,
                    "intensity_per_kg": s.intensity_per_kg,
                    "calculated_at":    ts.isoformat() if ts else "",
                })

        rows.sort(key=lambda r: r["calculated_at"], reverse=True)
        return jsonify(rows)
    finally:
        db.close()


# ── POST /api/history/request-clear ──────────────────────────────────────────
@history_bp.post("/request-clear")
@login_required
def request_clear():
    """Generate + email a 6-digit OTP so the user can confirm history deletion."""
    user = g.current_user
    otp = str(secrets.randbelow(900000) + 100000)   # 100000–999999
    _clear_otp_store[user.id] = (otp, time.time() + 600)  # valid 10 min

    sent = _send_otp_email(
        to_email = user.email,
        name     = user.full_name or user.username,
        otp      = otp,
    )
    if not sent:
        _clear_otp_store.pop(user.id, None)
        return jsonify({"detail": "Could not send OTP email. Please try again."}), 500

    masked = user.email[:3] + "***" + user.email[user.email.index("@"):]
    return jsonify({"message": f"OTP sent to {masked}"}), 200


# ── POST /api/history/verify-clear ───────────────────────────────────────────
@history_bp.post("/verify-clear")
@login_required
def verify_clear():
    """Verify OTP and permanently delete ALL history for the user."""
    data      = request.get_json() or {}
    otp_input = (data.get("otp") or "").strip()
    user      = g.current_user

    record = _clear_otp_store.get(user.id)
    if not record:
        return jsonify({"detail": "No OTP found. Please request a new one."}), 400

    stored_otp, expires_at = record
    if time.time() > expires_at:
        _clear_otp_store.pop(user.id, None)
        return jsonify({"detail": "OTP expired. Please request a new one."}), 400

    if otp_input != stored_otp:
        return jsonify({"detail": "Incorrect OTP. Please try again."}), 400

    _clear_otp_store.pop(user.id, None)

    db = SessionLocal()
    try:
        # Delete new Calculation records
        db.query(Calculation).filter(Calculation.user_id == user.id).delete()

        # Delete legacy Farm records (cascades to Season + Emission)
        farms = db.query(Farm).filter(Farm.owner_id == user.id).all()
        for farm in farms:
            db.delete(farm)

        db.commit()
        return jsonify({"message": "All calculation history has been cleared."})
    except Exception as e:
        db.rollback()
        return jsonify({"detail": str(e)}), 500
    finally:
        db.close()


# ── Helper: send OTP via Brevo ────────────────────────────────────────────────
def _send_otp_email(to_email: str, name: str, otp: str) -> bool:
    if not BREVO_API_KEY or not BREVO_FROM_EMAIL:
        print("[History OTP] Brevo credentials missing — OTP not sent")
        return False

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px;
                border:1px solid #e0e0e0;border-radius:10px;text-align:center;">
      <h2 style="color:#1a6b2e;margin-bottom:4px;">&#127807; CarbonLens</h2>
      <p style="color:#555;margin-top:4px;">History Clear Request</p>
      <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
      <p style="color:#333;">Hi <b>{name}</b>,<br>
         use the OTP below to permanently clear your calculation history:</p>
      <div style="font-size:40px;font-weight:700;letter-spacing:10px;color:#1a6b2e;
                  background:#eaf4ec;border-radius:10px;padding:18px 24px;
                  margin:20px auto;display:inline-block;">
        {otp}
      </div>
      <p style="color:#888;font-size:12px;margin-top:16px;">
        Valid for <b>10 minutes</b>. Do not share this code.<br>
        If you did not request this, ignore this email — your history is safe.
      </p>
      <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
      <p style="color:#aaa;font-size:11px;">CarbonLens by SAWiE</p>
    </div>"""

    payload = {
        "sender":      {"name": BREVO_FROM_NAME, "email": BREVO_FROM_EMAIL},
        "to":          [{"email": to_email}],
        "subject":     "CarbonLens — OTP to Clear Your History",
        "htmlContent": html,
    }
    headers = {
        "accept":       "application/json",
        "content-type": "application/json",
        "api-key":      BREVO_API_KEY,
    }
    try:
        resp = _requests.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload, headers=headers, timeout=10,
        )
        return resp.status_code in (200, 201)
    except Exception as exc:
        print(f"[History OTP] Brevo send failed: {exc}")
        return False
