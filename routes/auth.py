"""Authentication routes — register, login, forgot-password (username-based OTP)"""
import os
import secrets
import string
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, request, jsonify, g
from sqlalchemy.exc import IntegrityError

from auth_utils import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REMEMBER_TOKEN_EXPIRE_MINUTES,
    clear_auth_cookie,
    set_auth_cookie,
    token_from_request,
    create_access_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from database import SessionLocal
from models import User

auth_bp = Blueprint("auth", __name__)

# ─── In-memory OTP store: {username: {"otp": str, "expires": datetime}} ───────
_otp_store: dict = {}
OTP_EXPIRE_MINUTES = 10


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _db():
    return SessionLocal()


def get_current_user(token: str):
    username = decode_token(token)
    if not username:
        return None
    db = _db()
    try:
        return db.query(User).filter(User.username == username).first()
    finally:
        db.close()


def _user_dict(user, created_at=None):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "created_at": str(created_at or user.created_at),
    }


def _generate_otp(length=6) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))


def _send_otp_email(to_email: str, username: str, otp: str) -> bool:
    """Send OTP via Brevo transactional email API. Returns True on success."""
    import requests as _requests

    api_key   = os.getenv("BREVO_API_KEY", "")
    from_email = os.getenv("BREVO_FROM_EMAIL", "")
    from_name  = os.getenv("BREVO_FROM_NAME", "CarbonLens")

    if not api_key or not from_email:
        return False  # Brevo not configured

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px;
                border:1px solid #e0e0e0;border-radius:10px;">
      <h2 style="color:#1a6b2e;margin-bottom:4px;">&#128274; Password Reset</h2>
      <p style="color:#555;font-size:14px;">Hi <b>{username}</b>, your OTP for CarbonLens password reset:</p>
      <div style="font-size:36px;font-weight:900;letter-spacing:10px;
                  color:#243342;text-align:center;padding:16px 0;">{otp}</div>
      <p style="color:#888;font-size:12px;">This OTP expires in <b>{OTP_EXPIRE_MINUTES} minutes</b>.<br>
      If you did not request this, please ignore this email.</p>
      <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
      <p style="color:#aaa;font-size:11px;">CarbonLens by SAWiE &middot; info@sawie.net</p>
    </div>"""

    payload = {
        "sender":      {"name": from_name, "email": from_email},
        "to":          [{"email": to_email}],
        "subject":     "CarbonLens — Password Reset OTP",
        "htmlContent": html_body,
    }
    headers = {
        "accept":       "application/json",
        "content-type": "application/json",
        "api-key":      api_key,
    }

    try:
        resp = _requests.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload, headers=headers, timeout=10
        )
        return resp.status_code in (200, 201)
    except Exception:
        return False


# ─── Decorator ────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = token_from_request(request)
        if not token:
            return jsonify({"detail": "Not authenticated"}), 401
        user = get_current_user(token)
        if not user or not user.is_active:
            resp = jsonify({"detail": "Session expired. Please sign in again."})
            clear_auth_cookie(resp)
            return resp, 401
        g.current_user = user
        return f(*args, **kwargs)
    return decorated


# ─── Routes ───────────────────────────────────────────────────────────────────

@auth_bp.post("/register")
def register():
    data = request.get_json() or {}
    db = _db()
    try:
        existing = db.query(User).filter(
            (User.username == data.get("username")) |
            (User.email == data.get("email"))
        ).first()
        if existing:
            return jsonify({"detail": "Username or email already registered"}), 400

        user = User(
            username=data["username"],
            email=data["email"],
            full_name=data.get("full_name", ""),
            hashed_password=get_password_hash(data["password"]),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return jsonify(_user_dict(user)), 201
    except IntegrityError:
        db.rollback()
        return jsonify({"detail": "Username or email already registered"}), 400
    except KeyError as e:
        return jsonify({"detail": f"Missing field: {e}"}), 422
    finally:
        db.close()


@auth_bp.post("/login")
def login():
    data = request.get_json() or {}
    db = _db()
    try:
        user = db.query(User).filter(User.username == data.get("username")).first()
        if not user or not verify_password(data.get("password", ""), user.hashed_password):
            return jsonify({"detail": "Invalid username or password"}), 401
        if not user.is_active:
            return jsonify({"detail": "Account is inactive"}), 403

        remember = bool(data.get("remember"))
        minutes = REMEMBER_TOKEN_EXPIRE_MINUTES if remember else ACCESS_TOKEN_EXPIRE_MINUTES
        token = create_access_token({"sub": user.username}, timedelta(minutes=minutes))
        # The token travels only in the HttpOnly cookie; the page never sees it.
        resp = jsonify({"user": _user_dict(user)})
        set_auth_cookie(resp, token, remember, secure=request.is_secure)
        return resp
    finally:
        db.close()


@auth_bp.post("/forgot-password")
def forgot_password():
    """Step 1: takes username → finds email → sends OTP."""
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()

    if not username:
        return jsonify({"detail": "Username is required."}), 422

    db = _db()
    try:
        user = db.query(User).filter(User.username == username).first()
    finally:
        db.close()

    # Always return success to avoid leaking which usernames exist
    if not user:
        return jsonify({"detail": "ok", "message": "If that username exists, an OTP has been sent to the registered email."}), 200

    otp = _generate_otp()
    _otp_store[username] = {
        "otp": otp,
        "expires": datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES),
    }

    sent = _send_otp_email(user.email, user.username, otp)

    if not sent:
        # SMTP not configured — remove OTP and tell admin
        _otp_store.pop(username, None)
        return jsonify({
            "detail": "smtp_error",
            "message": "Email service is not configured. Please contact: info@sawie.net"
        }), 503

    return jsonify({
        "detail": "ok",
        "message": f"OTP sent to the email registered with '{username}'. Check your inbox (and spam).",
    }), 200


@auth_bp.post("/verify-otp")
def verify_otp():
    """Step 2: verify OTP — returns success so frontend can show new-password step."""
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    otp = (data.get("otp") or "").strip()

    if not username or not otp:
        return jsonify({"detail": "Username and OTP are required."}), 422

    record = _otp_store.get(username)
    if not record:
        return jsonify({"detail": "No OTP was requested for this username."}), 400
    if datetime.utcnow() > record["expires"]:
        _otp_store.pop(username, None)
        return jsonify({"detail": "OTP has expired. Please request a new one."}), 400
    if record["otp"] != otp:
        record["attempts"] = record.get("attempts", 0) + 1
        if record["attempts"] >= 5:
            _otp_store.pop(username, None)
            return jsonify({"detail": "Too many wrong attempts. Please request a new OTP."}), 429
        return jsonify({"detail": "Incorrect OTP. Please try again."}), 400

    # Mark OTP as verified (keep it until reset is done)
    record["verified"] = True
    return jsonify({"detail": "ok", "message": "OTP verified. You may now set a new password."}), 200


@auth_bp.post("/reset-password")
def reset_password():
    """Step 3: set new password — requires verified OTP still in store."""
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    otp = (data.get("otp") or "").strip()
    new_password = data.get("new_password") or ""

    if not username or not otp or not new_password:
        return jsonify({"detail": "username, otp, and new_password are required."}), 422
    if len(new_password) < 6:
        return jsonify({"detail": "Password must be at least 6 characters."}), 422

    record = _otp_store.get(username)
    if not record or not record.get("verified"):
        return jsonify({"detail": "OTP not verified. Please complete OTP verification first."}), 400
    if datetime.utcnow() > record["expires"]:
        _otp_store.pop(username, None)
        return jsonify({"detail": "Session expired. Please start over."}), 400
    if record["otp"] != otp:
        return jsonify({"detail": "Invalid session. Please start over."}), 400

    db = _db()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return jsonify({"detail": "User not found."}), 404
        user.hashed_password = get_password_hash(new_password)
        db.commit()
    finally:
        db.close()

    _otp_store.pop(username, None)  # Consume OTP
    return jsonify({"detail": "ok", "message": "Password reset successfully. You can now log in."}), 200


@auth_bp.post("/logout")
def logout():
    resp = jsonify({"detail": "ok"})
    clear_auth_cookie(resp)
    return resp


@auth_bp.get("/me")
@login_required
def me():
    return jsonify(_user_dict(g.current_user))


@auth_bp.post("/change-password")
@login_required
def change_password():
    """Logged-in user changes their own password (requires current password)."""
    data = request.get_json() or {}
    current_password = data.get("current_password") or ""
    new_password = data.get("new_password") or ""

    if not current_password or not new_password:
        return jsonify({"detail": "Current and new password are required."}), 422
    if len(new_password) < 6:
        return jsonify({"detail": "New password must be at least 6 characters."}), 422

    db = _db()
    try:
        user = db.query(User).filter(User.id == g.current_user.id).first()
        if not user or not verify_password(current_password, user.hashed_password):
            return jsonify({"detail": "Current password is incorrect."}), 401
        user.hashed_password = get_password_hash(new_password)
        db.commit()
        return jsonify({"detail": "ok", "message": "Password changed successfully."})
    finally:
        db.close()
