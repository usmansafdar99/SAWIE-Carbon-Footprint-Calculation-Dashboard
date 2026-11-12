"""Farm CRUD routes"""
from datetime import datetime

from flask import Blueprint, request, jsonify, g

from database import SessionLocal
from models import Farm, Season
from routes.auth import login_required

farms_bp = Blueprint("farms", __name__)


def _db():
    return SessionLocal()


def _farm_dict(farm):
    return {
        "id": farm.id,
        "farm_id": farm.farm_id,
        "farmer_name": farm.farmer_name,
        "owner_id": farm.owner_id,
        "province": farm.province,
        "district": farm.district,
        "tehsil": farm.tehsil,
        "village": farm.village,
        "area": farm.area,
        "harvested_area": farm.harvested_area,
        "soil_texture": farm.soil_texture,
        "soil_organic_matter": farm.soil_organic_matter,
        "soil_drainage": farm.soil_drainage,
        "soil_ph": farm.soil_ph,
        "climate": farm.climate,
        "moisture_regime": farm.moisture_regime,
        "created_at": str(farm.created_at),
        "updated_at": str(farm.updated_at),
    }


# ─── Create farm ──────────────────────────────────────────────────────────────
@farms_bp.post("/")
@login_required
def create_farm():
    data = request.get_json() or {}
    db = _db()
    FARM_FIELDS = {"farm_id","farmer_name","province","district","tehsil","village",
                   "area","harvested_area","soil_texture","soil_organic_matter",
                   "soil_drainage","soil_ph","climate","moisture_regime"}
    safe = {k:v for k,v in data.items() if k in FARM_FIELDS}
    try:
        if db.query(Farm).filter(Farm.farm_id == safe.get("farm_id")).first():
            return jsonify({"detail": "Farm ID already exists"}), 400
        farm = Farm(**safe, owner_id=g.current_user.id)
        db.add(farm)
        db.commit()
        db.refresh(farm)
        return jsonify(_farm_dict(farm)), 201
    except Exception as e:
        db.rollback()
        return jsonify({"detail": str(e)}), 500
    finally:
        db.close()


# ─── List farms ───────────────────────────────────────────────────────────────
@farms_bp.get("/")
@login_required
def list_farms():
    db = _db()
    try:
        farms = db.query(Farm).filter(Farm.owner_id == g.current_user.id).all()
        return jsonify([_farm_dict(f) for f in farms])
    finally:
        db.close()


# ─── Get one farm ─────────────────────────────────────────────────────────────
@farms_bp.get("/<int:farm_id>")
@login_required
def get_farm(farm_id):
    db = _db()
    try:
        farm = db.query(Farm).filter(
            Farm.id == farm_id, Farm.owner_id == g.current_user.id
        ).first()
        if not farm:
            return jsonify({"detail": "Farm not found"}), 404
        return jsonify(_farm_dict(farm))
    finally:
        db.close()


# ─── Update farm ──────────────────────────────────────────────────────────────
@farms_bp.put("/<int:farm_id>")
@login_required
def update_farm(farm_id):
    data = request.get_json() or {}
    db = _db()
    try:
        farm = db.query(Farm).filter(
            Farm.id == farm_id, Farm.owner_id == g.current_user.id
        ).first()
        if not farm:
            return jsonify({"detail": "Farm not found"}), 404
        for k, v in data.items():
            if hasattr(farm, k):
                setattr(farm, k, v)
        farm.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(farm)
        return jsonify(_farm_dict(farm))
    finally:
        db.close()


# ─── Delete farm ──────────────────────────────────────────────────────────────
@farms_bp.delete("/<int:farm_id>")
@login_required
def delete_farm(farm_id):
    db = _db()
    try:
        farm = db.query(Farm).filter(
            Farm.id == farm_id, Farm.owner_id == g.current_user.id
        ).first()
        if not farm:
            return jsonify({"detail": "Farm not found"}), 404
        db.delete(farm)
        db.commit()
        return jsonify({"message": "Farm deleted"})
    finally:
        db.close()


# ─── Calculation history for the logged-in user (all farms, all seasons) ─────
@farms_bp.get("/my-history")
@login_required
def my_history():
    db = _db()
    try:
        farms = db.query(Farm).filter(Farm.owner_id == g.current_user.id).all()
        rows = []
        for f in farms:
            for s in f.seasons:
                if s.total_co2_equiv is None:
                    continue  # skip incomplete/unsaved seasons
                rows.append({
                    "farm_db_id": f.id,
                    "farm_id": f.farm_id,
                    "farmer_name": f.farmer_name,
                    "district": f.district,
                    "province": f.province,
                    "season_id": s.id,
                    "season": s.season,
                    "crop": s.crop,
                    "seed_cotton_yield": s.seed_cotton_yield,
                    "total_co2_equiv": s.total_co2_equiv,
                    "intensity_per_kg": s.intensity_per_kg,
                    "created_at": str(s.created_at),
                    "updated_at": str(s.updated_at),
                })
        rows.sort(key=lambda r: r["updated_at"], reverse=True)
        return jsonify(rows)
    finally:
        db.close()


# ─── Get farm seasons ─────────────────────────────────────────────────────────
@farms_bp.get("/<int:farm_id>/seasons")
@login_required
def farm_seasons(farm_id):
    db = _db()
    try:
        farm = db.query(Farm).filter(
            Farm.id == farm_id, Farm.owner_id == g.current_user.id
        ).first()
        if not farm:
            return jsonify({"detail": "Farm not found"}), 404
        return jsonify([{
            "id": s.id,
            "farm_id": s.farm_id,
            "season": s.season,
            "crop": s.crop,
            "seed_cotton_yield": s.seed_cotton_yield,
            "total_co2_equiv": s.total_co2_equiv,
            "intensity_per_kg": s.intensity_per_kg,
            "created_at": str(s.created_at),
            "updated_at": str(s.updated_at),
        } for s in farm.seasons])
    finally:
        db.close()


# ─── Latest completed calculation (public, shown on home page preview) ───────
@farms_bp.get("/latest")
@login_required
def latest_farm_result():
    """Return the most recently calculated season, for the home-page
    'What your result looks like' preview. No auth required — only
    non-sensitive, aggregate figures are exposed (no contact/owner info)."""
    db = _db()
    try:
        season = (
            db.query(Season)
            .join(Farm, Farm.id == Season.farm_id)
            .filter(Farm.owner_id == g.current_user.id)
            .filter(Season.total_co2_equiv.isnot(None))
            .order_by(Season.updated_at.desc())
            .first()
        )
        if not season:
            return jsonify({"available": False})

        farm = db.query(Farm).filter(Farm.id == season.farm_id).first()

        breakdown = []
        for e in season.emissions:
            breakdown.append({
                "source": e.source,
                "value": e.value,
                "percentage": e.percentage,
            })

        return jsonify({
            "available": True,
            "farmer_first_name": (farm.farmer_name.split(" ")[0] if farm and farm.farmer_name else "A farmer"),
            "district": farm.district if farm else None,
            "province": farm.province if farm else None,
            "crop": season.crop,
            "season": season.season,
            "seed_cotton_yield": season.seed_cotton_yield,
            "total_co2_equiv": season.total_co2_equiv,
            "intensity_per_kg": season.intensity_per_kg,
            "area": farm.area if farm else None,
            "breakdown": breakdown,
            "updated_at": str(season.updated_at),
        })
    finally:
        db.close()


@farms_bp.get("/by-farmid/<farm_id_str>")
@login_required
def get_farm_by_farmid(farm_id_str):
    """Lookup farm by its string farm_id (e.g. PKC-2025-0847)."""
    db = _db()
    try:
        farm = db.query(Farm).filter(
            Farm.farm_id == farm_id_str,
            Farm.owner_id == g.current_user.id
        ).first()
        if not farm:
            return jsonify({"detail": "Not found"}), 404
        return jsonify(_farm_dict(farm))
    finally:
        db.close()


# ─── Upsert season (create or update by farm+season name) ────────────────────
@farms_bp.post("/<int:farm_id>/seasons/upsert")
@login_required
def upsert_season(farm_id):
    """Create season if it doesn't exist; update if it does (same farm+season)."""
    data = request.get_json() or {}
    db = _db()
    try:
        farm = db.query(Farm).filter(
            Farm.id == farm_id, Farm.owner_id == g.current_user.id
        ).first()
        if not farm:
            return jsonify({"detail": "Farm not found"}), 404

        season_name = data.get("season", "")
        season = db.query(Season).filter(
            Season.farm_id == farm_id,
            Season.season  == season_name,
        ).first()

        SEASON_FIELDS = {"season","crop","variety","seed_rate","seed_source",
                         "seed_cotton_yield","fertiliser_data","irrigation_data",
                         "machinery_data","pest_protection_data","residue_data",
                         "labour_data","total_co2_equiv","intensity_per_kg"}

        if season:
            for k, v in data.items():
                if k in SEASON_FIELDS:
                    setattr(season, k, v)
            season.updated_at = datetime.utcnow()
        else:
            safe = {k: v for k, v in data.items() if k in SEASON_FIELDS}
            season = Season(**safe, farm_id=farm_id)
            db.add(season)

        db.commit()
        db.refresh(season)
        return jsonify({"id": season.id, "season": season.season,
                        "total_co2_equiv": season.total_co2_equiv}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"detail": str(e)}), 500
    finally:
        db.close()
