"""Contact form — saves to DB and sends via Brevo API."""
import os
import re

import requests as _requests
from flask import Blueprint, request, jsonify

from database import SessionLocal
from models import ContactMessage

contact_bp = Blueprint("contact", __name__)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# Destination inboxes — set in .env
CONTACT_EMAIL_INFO = os.getenv("CONTACT_EMAIL_INFO", "")
CONTACT_EMAIL_TECH = os.getenv("CONTACT_EMAIL_TECH", "")

BREVO_API_KEY   = os.getenv("BREVO_API_KEY", "")
BREVO_FROM_EMAIL = os.getenv("BREVO_FROM_EMAIL", "")
BREVO_FROM_NAME  = os.getenv("BREVO_FROM_NAME", "CarbonLens")


def _send_email(category: str, name: str, sender_email: str, farm_id: str, message: str) -> bool:
    """Send contact message via Brevo. Returns True on success."""
    to_addr = CONTACT_EMAIL_INFO if category == "info" else CONTACT_EMAIL_TECH
    if not (BREVO_API_KEY and BREVO_FROM_EMAIL and to_addr):
        return False

    subject = "CarbonLens enquiry" if category == "info" else "CarbonLens technical support"
    if farm_id:
        subject += f" — Farm {farm_id}"

    cat_label = "For information" if category == "info" else "Technical support"
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;
                border:1px solid #e0e0e0;border-radius:10px;">
      <h2 style="color:#1a6b2e;margin-bottom:4px;">&#9993; CarbonLens Contact Form</h2>
      <table style="width:100%;font-size:14px;margin:16px 0;border-collapse:collapse;">
        <tr><td style="color:#888;padding:4px 0;width:110px;">From</td>
            <td><b>{name}</b> &lt;{sender_email}&gt;</td></tr>
        <tr><td style="color:#888;padding:4px 0;">Category</td>
            <td>{cat_label}</td></tr>
        <tr><td style="color:#888;padding:4px 0;">Farm ID</td>
            <td>{farm_id or '—'}</td></tr>
      </table>
      <hr style="border:none;border-top:1px solid #eee;margin:12px 0;">
      <p style="font-size:14px;color:#333;white-space:pre-wrap;">{message}</p>
      <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
      <p style="color:#aaa;font-size:11px;">CarbonLens by SAWiE — info@sawie.net</p>
    </div>"""

    payload = {
        "sender":      {"name": BREVO_FROM_NAME, "email": BREVO_FROM_EMAIL},
        "to":          [{"email": to_addr}],
        "replyTo":     {"email": sender_email, "name": name},
        "subject":     subject,
        "htmlContent": html_body,
    }
    headers = {
        "accept":       "application/json",
        "content-type": "application/json",
        "api-key":      BREVO_API_KEY,
    }
    try:
        resp = _requests.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload, headers=headers, timeout=10
        )
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"[Contact form] Brevo send failed: {e}")
        return False


@contact_bp.post("/send")
def send_contact():
    data     = request.get_json() or {}
    category = data.get("category")
    name     = (data.get("name")    or "").strip()
    email    = (data.get("email")   or "").strip()
    farm_id  = (data.get("farm_id") or "").strip()
    message  = (data.get("message") or "").strip()

    if category not in ("info", "tech"):
        return jsonify({"detail": "Please choose a category."}), 400
    if not name:
        return jsonify({"detail": "Please enter your name."}), 400
    if not email or not EMAIL_RE.match(email):
        return jsonify({"detail": "Please enter a valid email address."}), 400
    if not message or len(message) < 5:
        return jsonify({"detail": "Please write a short message."}), 400

    sent = _send_email(category, name, email, farm_id, message)

    db = SessionLocal()
    try:
        row = ContactMessage(
            category=category, name=name, email=email,
            farm_id=farm_id or None, message=message, email_sent=sent,
        )
        db.add(row)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Contact form] DB save failed: {e}")
        return jsonify({"detail": "Could not save your message. Please try again."}), 500
    finally:
        db.close()

    return jsonify({
        "message": "Thanks — your message has been sent. We'll get back to you soon."
                    if sent else
                    "Thanks — your message has been received. Our team will follow up soon."
    })


# ─── Book a Demo ──────────────────────────────────────────────────────────────
DEMO_TO_EMAIL = "hadia.zafar@sawie.net"

def _send_demo_email(name: str, sender_email: str, organization: str, details: str) -> bool:
    """Send Book a Demo request via Brevo to hadia.zafar@sawie.net."""
    if not (BREVO_API_KEY and BREVO_FROM_EMAIL):
        return False

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;
                border:1px solid #e0e0e0;border-radius:10px;">
      <h2 style="color:#1a6b2e;margin-bottom:4px;">&#128197; CarbonLens — Book a Demo Request</h2>
      <table style="width:100%;font-size:14px;margin:16px 0;border-collapse:collapse;">
        <tr><td style="color:#888;padding:6px 0;width:130px;vertical-align:top;">Name</td>
            <td><b>{name}</b></td></tr>
        <tr><td style="color:#888;padding:6px 0;vertical-align:top;">Email</td>
            <td><a href="mailto:{sender_email}">{sender_email}</a></td></tr>
        <tr><td style="color:#888;padding:6px 0;vertical-align:top;">Organization</td>
            <td>{organization or '—'}</td></tr>
        <tr><td style="color:#888;padding:6px 0;vertical-align:top;">Details</td>
            <td style="white-space:pre-wrap;">{details}</td></tr>
      </table>
      <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
      <p style="color:#aaa;font-size:11px;">CarbonLens by SAWiE — info@sawie.net</p>
    </div>"""

    payload = {
        "sender":      {"name": BREVO_FROM_NAME, "email": BREVO_FROM_EMAIL},
        "to":          [{"email": DEMO_TO_EMAIL}],
        "replyTo":     {"email": sender_email, "name": name},
        "subject":     f"CarbonLens Demo Request — {name} ({organization or 'N/A'})",
        "htmlContent": html_body,
    }
    headers = {
        "accept":       "application/json",
        "content-type": "application/json",
        "api-key":      BREVO_API_KEY,
    }
    try:
        resp = _requests.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload, headers=headers, timeout=10
        )
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"[Book a Demo] Brevo send failed: {e}")
        return False


@contact_bp.post("/book-demo")
def book_demo():
    data         = request.get_json() or {}
    name         = (data.get("name")         or "").strip()
    email        = (data.get("email")        or "").strip()
    organization = (data.get("organization") or "").strip()
    details      = (data.get("details")      or "").strip()

    if not name:
        return jsonify({"detail": "Please enter your name."}), 400
    if not email or not EMAIL_RE.match(email):
        return jsonify({"detail": "Please enter a valid email address."}), 400
    if not details or len(details) < 5:
        return jsonify({"detail": "Please add some details about your demo request."}), 400

    sent = _send_demo_email(name, email, organization, details)

    # Also log to DB as a contact message
    db = SessionLocal()
    try:
        row = ContactMessage(
            category="info",
            name=name,
            email=email,
            farm_id=None,
            message=f"[DEMO REQUEST] Org: {organization}\n{details}",
            email_sent=sent,
        )
        db.add(row)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Book a Demo] DB save failed: {e}")
    finally:
        db.close()

    return jsonify({
        "message": "Thanks! We've received your demo request and will be in touch shortly."
    })
