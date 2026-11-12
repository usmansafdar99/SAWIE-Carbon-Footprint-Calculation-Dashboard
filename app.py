"""CarbonLens — Flask application entry point"""
import os

from dotenv import load_dotenv
from flask import Flask, render_template
from flask_cors import CORS

load_dotenv()

from database import Base, engine
import models  # noqa: F401  (ensures models are registered on Base before create_all)

from routes.auth import auth_bp
from routes.farms import farms_bp
from routes.calculations import calc_bp
from routes.reports import reports_bp
from routes.chatbot import chatbot_bp
from routes.contact import contact_bp
from routes.widgets import widgets_bp
from routes.history import history_bp

# ─── Create tables if they don't exist yet ────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ─── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
# Same-origin cookies carry the session; cross-site callers get no credentials.
CORS(app, supports_credentials=False)

app.register_blueprint(auth_bp, url_prefix="/api/auth")
app.register_blueprint(farms_bp, url_prefix="/api/farms")
app.register_blueprint(calc_bp, url_prefix="/api/farms")
app.register_blueprint(reports_bp, url_prefix="/api/reports")
app.register_blueprint(chatbot_bp, url_prefix="/api/chat")
app.register_blueprint(contact_bp, url_prefix="/api/contact")
app.register_blueprint(widgets_bp, url_prefix="/api/widgets")
app.register_blueprint(history_bp, url_prefix="/api/history")


@app.route("/")
def index():
    return render_template("index.html")


@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return resp


@app.route("/api/health")
def health():
    return {"status": "ok", "service": "CarbonLens"}


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "true").lower() == "true"
    app.run(host=host, port=port, debug=debug)
