"""SQLAlchemy models — User, Farm, Season, Emission"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
)
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    farms = relationship("Farm", back_populates="owner", cascade="all, delete-orphan")
    calculations = relationship("Calculation", back_populates="user", cascade="all, delete-orphan")


class Farm(Base):
    __tablename__ = "farms"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(String, unique=True, index=True, nullable=False)
    farmer_name = Column(String, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"))
    province = Column(String)
    district = Column(String)
    tehsil = Column(String)
    village = Column(String)
    area = Column(Float)
    harvested_area = Column(Float)
    soil_texture = Column(String)
    soil_organic_matter = Column(String)
    soil_drainage = Column(String)
    soil_ph = Column(String)
    climate = Column(String)
    moisture_regime = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="farms")
    seasons = relationship("Season", back_populates="farm", cascade="all, delete-orphan")


class Season(Base):
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"))
    season = Column(String)
    crop = Column(String, default="Cotton")
    variety = Column(String)
    seed_rate = Column(Float)
    seed_source = Column(String)
    seed_cotton_yield = Column(Float)
    fertiliser_data = Column(JSON, default=dict)
    irrigation_data = Column(JSON, default=dict)
    machinery_data = Column(JSON, default=dict)
    pest_protection_data = Column(JSON, default=dict)
    residue_data = Column(JSON, default=dict)
    labour_data = Column(JSON, default=dict)
    total_co2_equiv = Column(Float, nullable=True)
    intensity_per_kg = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    farm = relationship("Farm", back_populates="seasons")
    emissions = relationship("Emission", back_populates="season", cascade="all, delete-orphan")


class Emission(Base):
    __tablename__ = "emissions"

    id = Column(Integer, primary_key=True, index=True)
    season_id = Column(Integer, ForeignKey("seasons.id"))
    source = Column(String)
    value = Column(Float)
    percentage = Column(Float)

    season = relationship("Season", back_populates="emissions")


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String)          # "info" or "tech"
    name = Column(String)
    email = Column(String)
    farm_id = Column(String, nullable=True)
    message = Column(String)
    email_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Calculation(Base):
    """Single-table record: all farm inputs + carbon results. One row per calculation run."""
    __tablename__ = "calculations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # ── Farm / Farmer info ─────────────────────────────────────────────────────
    farm_id        = Column(String(100), default="")
    farmer_name    = Column(String(255), default="")
    province       = Column(String(100), default="")
    district       = Column(String(100), default="")
    tehsil         = Column(String(100), default="")
    village        = Column(String(100), default="")
    area           = Column(Float, default=0)
    harvested_area = Column(Float, default=0)
    soil_texture          = Column(String(100), default="")
    soil_organic_matter   = Column(String(50),  default="")
    soil_drainage         = Column(String(50),  default="")
    soil_ph               = Column(String(50),  default="")
    climate               = Column(String(100), default="")
    moisture_regime       = Column(String(100), default="")

    # ── Season / Crop info ────────────────────────────────────────────────────
    season            = Column(String(100), default="")
    crop              = Column(String(100), default="Cotton")
    variety           = Column(String(100), default="")
    seed_rate         = Column(Float, default=0)
    seed_source       = Column(String(100), default="")
    seed_cotton_yield = Column(Float, default=0)

    # ── All input data (JSON) ──────────────────────────────────────────────────
    fertiliser_data      = Column(JSON, default=dict)
    irrigation_data      = Column(JSON, default=dict)
    machinery_data       = Column(JSON, default=dict)
    pest_protection_data = Column(JSON, default=dict)
    residue_data         = Column(JSON, default=dict)
    labour_data          = Column(JSON, default=dict)

    # ── Results ───────────────────────────────────────────────────────────────
    total_co2_equiv  = Column(Float, default=0)
    intensity_per_kg = Column(Float, default=0)
    breakdown        = Column(JSON, default=dict)

    # ── Meta ──────────────────────────────────────────────────────────────────
    calculated_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="calculations")
