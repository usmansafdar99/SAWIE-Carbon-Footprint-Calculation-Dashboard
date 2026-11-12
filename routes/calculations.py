"""
routes/calculations.py — Season data entry + carbon footprint calculation
Registered in app.py at url_prefix="/api/farms"
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, g

from database import SessionLocal
from models import Farm, Season, Emission
from calculator import CarbonCalculator
from routes.auth import login_required

calc_bp = Blueprint("calculations", __name__)
calculator = CarbonCalculator()


def _owned_farm(db, farm_id):
    """Farm row only if it belongs to the signed-in user."""
    return db.query(Farm).filter(Farm.id == farm_id, Farm.owner_id == g.current_user.id).first()


def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── POST /api/farms/<farm_id>/seasons ─────────────────────────────────────────
@calc_bp.route("/<int:farm_id>/seasons", methods=["POST"])
@login_required
def create_season(farm_id):
    """
    Save a season's input data, run the calculator, and persist:
      • seasons.total_co2_equiv
      • seasons.intensity_per_kg
      • One emissions row per source
    """
    db = SessionLocal()
    try:
        # 1. Verify farm exists
        farm = _owned_farm(db, farm_id)
        if not farm:
            return jsonify({"error": "Farm not found"}), 404

        body = request.get_json(silent=True) or {}

        # 2. Build season record
        season = Season(
            farm_id        = farm_id,
            season         = body.get("season"),
            crop           = body.get("crop", "Cotton"),
            variety        = body.get("variety"),
            seed_rate      = body.get("seed_rate"),
            seed_source    = body.get("seed_source"),
            seed_cotton_yield = body.get("seed_cotton_yield", 1000),

            fertiliser_data      = body.get("fertiliser_data"),
            irrigation_data      = body.get("irrigation_data"),
            machinery_data       = body.get("machinery_data"),
            pest_protection_data = body.get("pest_protection_data"),
            residue_data         = body.get("residue_data"),
            labour_data          = body.get("labour_data"),

            # initialise to 0 — will be updated after calculation below
            total_co2_equiv = 0.0,
            intensity_per_kg = 0.0,

            created_at = datetime.utcnow(),
            updated_at = datetime.utcnow(),
        )
        db.add(season)
        db.flush()          # get season.id without full commit

        # 3. Run the calculator
        farm_data = {
            "area":           farm.area or 1,
            "harvested_area": farm.harvested_area or farm.area or 1,
        }
        season_data = {
            "seed_cotton_yield":   season.seed_cotton_yield,
            "fertiliser_data":     season.fertiliser_data or {},
            "irrigation_data":     season.irrigation_data or {},
            "machinery_data":      season.machinery_data  or {},
            "pest_protection_data":season.pest_protection_data or {},
            "residue_data":        season.residue_data    or {},
        }

        result = calculator.calculate_total_footprint(farm_data, season_data)

        # 4. ──────────────────────────────────────────────────────────────────
        #    KEY FIX: write calculated values back to the season row
        # ─────────────────────────────────────────────────────────────────────
        season.total_co2_equiv  = result["total_co2_equiv"]
        season.intensity_per_kg = result["intensity_per_kg"]
        season.updated_at       = datetime.utcnow()

        # 5. Save per-source breakdown into emissions table
        total = result["total_co2_equiv"] or 1   # avoid div-by-zero
        for source, value in result["emissions_breakdown"].items():
            emission = Emission(
                season_id  = season.id,
                source     = source,
                value      = value,
                percentage = round((value / total) * 100, 2),
            )
            db.add(emission)

        # 6. Commit everything in one transaction
        db.commit()

        return jsonify({
            "message":      "Season saved successfully",
            "season_id":    season.id,
            "total_co2_equiv":      result["total_co2_equiv"],
            "intensity_per_kg":     result["intensity_per_kg"],
            "comparison_percentage":result["comparison_percentage"],
            "national_average":     result["national_average_intensity"],
            "emissions_breakdown":  result["emissions_breakdown"],
        }), 201

    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


# ─── PUT /api/farms/<farm_id>/seasons/<season_id> ──────────────────────────────
@calc_bp.route("/<int:farm_id>/seasons/<int:season_id>", methods=["PUT"])
@login_required
def update_season(farm_id, season_id):
    """Update an existing season and recalculate."""
    db = SessionLocal()
    try:
        farm = _owned_farm(db, farm_id)
        season = db.query(Season).filter(
            Season.id == season_id, Season.farm_id == farm_id
        ).first() if farm else None
        if not season:
            return jsonify({"error": "Season not found"}), 404

        body = request.get_json(silent=True) or {}

        # Update fields
        for field in [
            "season", "crop", "variety", "seed_rate", "seed_source",
            "seed_cotton_yield", "fertiliser_data", "irrigation_data",
            "machinery_data", "pest_protection_data", "residue_data", "labour_data",
        ]:
            if field in body:
                setattr(season, field, body[field])

        season.updated_at = datetime.utcnow()

        # Recalculate
        farm_data = {
            "area":           farm.area or 1,
            "harvested_area": farm.harvested_area or farm.area or 1,
        }
        season_data = {
            "seed_cotton_yield":    season.seed_cotton_yield,
            "fertiliser_data":      season.fertiliser_data or {},
            "irrigation_data":      season.irrigation_data or {},
            "machinery_data":       season.machinery_data  or {},
            "pest_protection_data": season.pest_protection_data or {},
            "residue_data":         season.residue_data    or {},
        }
        result = calculator.calculate_total_footprint(farm_data, season_data)

        season.total_co2_equiv  = result["total_co2_equiv"]
        season.intensity_per_kg = result["intensity_per_kg"]

        # Replace emissions rows
        db.query(Emission).filter(Emission.season_id == season_id).delete()
        total = result["total_co2_equiv"] or 1
        for source, value in result["emissions_breakdown"].items():
            db.add(Emission(
                season_id  = season_id,
                source     = source,
                value      = value,
                percentage = round((value / total) * 100, 2),
            ))

        db.commit()

        return jsonify({
            "message":              "Season updated",
            "season_id":            season.id,
            "total_co2_equiv":      result["total_co2_equiv"],
            "intensity_per_kg":     result["intensity_per_kg"],
            "comparison_percentage":result["comparison_percentage"],
            "emissions_breakdown":  result["emissions_breakdown"],
        })

    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


# ─── GET /api/farms/<farm_id>/seasons ──────────────────────────────────────────
@calc_bp.route("/<int:farm_id>/seasons", methods=["GET"])
@login_required
def list_seasons(farm_id):
    db = SessionLocal()
    try:
        if not _owned_farm(db, farm_id):
            return jsonify({"error": "Farm not found"}), 404
        seasons = db.query(Season).filter(Season.farm_id == farm_id).all()
        return jsonify([{
            "id":               s.id,
            "season":           s.season,
            "crop":             s.crop,
            "total_co2_equiv":  s.total_co2_equiv,
            "intensity_per_kg": s.intensity_per_kg,
            "created_at":       s.created_at.isoformat() if s.created_at else None,
        } for s in seasons])
    finally:
        db.close()


# ─── GET /api/farms/<farm_id>/seasons/<season_id> ──────────────────────────────
@calc_bp.route("/<int:farm_id>/seasons/<int:season_id>", methods=["GET"])
@login_required
def get_season(farm_id, season_id):
    db = SessionLocal()
    try:
        season = db.query(Season).filter(
            Season.id == season_id, Season.farm_id == farm_id
        ).first() if _owned_farm(db, farm_id) else None
        if not season:
            return jsonify({"error": "Season not found"}), 404

        emissions = db.query(Emission).filter(Emission.season_id == season_id).all()
        breakdown = {e.source: {"value": e.value, "percentage": e.percentage}
                     for e in emissions}

        return jsonify({
            "id":                   season.id,
            "farm_id":              season.farm_id,
            "season":               season.season,
            "crop":                 season.crop,
            "variety":              season.variety,
            "seed_cotton_yield":    season.seed_cotton_yield,
            "fertiliser_data":      season.fertiliser_data,
            "irrigation_data":      season.irrigation_data,
            "machinery_data":       season.machinery_data,
            "pest_protection_data": season.pest_protection_data,
            "residue_data":         season.residue_data,
            "total_co2_equiv":      season.total_co2_equiv,
            "intensity_per_kg":     season.intensity_per_kg,
            "emissions_breakdown":  breakdown,
            "created_at":           season.created_at.isoformat() if season.created_at else None,
            "updated_at":           season.updated_at.isoformat() if season.updated_at else None,
        })
    finally:
        db.close()