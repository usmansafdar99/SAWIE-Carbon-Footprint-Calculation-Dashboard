# CarbonLens · Flask Edition
Cotton Carbon Footprint Calculator by SAWiE (Sustainable Agriculture Water and Intelligent Ecosystems)

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and edit environment file
cp .env.example .env

# 3. Run
python app.py
# → opens at http://localhost:8000
```

## Project Structure

```
carbonlens_flask/
├── app.py               # Flask application entry point
├── auth_utils.py        # JWT & password helpers
├── database.py          # SQLAlchemy engine + session
├── models.py            # User, Farm, Season, Emission models
├── calculator.py        # Carbon footprint calculation engine
├── requirements.txt
├── .env.example
├── routes/
│   ├── auth.py          # POST /api/auth/login|register|guest-login
│   ├── farms.py         # CRUD /api/farms/
│   ├── calculations.py  # POST /api/farms/{id}/seasons/{id}/calculate
│   └── reports.py       # POST /api/reports/ → PDF / Word download
├── templates/
│   └── index.html       # Full SPA frontend (same design + formulas)
└── static/
    ├── sawie.png         # SAWiE logo
    └── login-bg.jpeg     # Login background image
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/auth/register | — | Create account |
| POST | /api/auth/login | — | Login → JWT |
| POST | /api/auth/guest-login | — | Guest access (24 h) |
| GET | /api/auth/me | ✓ | Current user |
| GET/POST | /api/farms/ | ✓ | List / create farms |
| GET/PUT/DELETE | /api/farms/{id} | ✓ | Farm CRUD |
| POST | /api/farms/{id}/seasons | ✓ | Create season |
| POST | /api/farms/{id}/seasons/{id}/calculate | ✓ | Run calculation |
| POST | /api/reports/ | ✓ | Generate PDF/Word report |
| GET | /api/reports/{id}/download | ✓ | Download report |
| GET | /api/health | — | Health check |

## Changes vs Original

- **Framework**: FastAPI → Flask  
- **Logo**: Fixed path (`/static/sawie.png`) — logo now displays correctly  
- **Fertiliser note removed**: The "Nitrogen drives field N₂O (IPCC/Bouwman)…" footnote has been removed from the fertiliser step  
- **Formulas**: All carbon footprint formulas and emission factors are identical  
- **Theme**: Same green SAWiE design system  


## Theme and platform update (November 2026)

**Design**
- Green and white SaaS theme with Outfit and Plus Jakarta Sans fonts (self-hosted in `static/fonts/`).
- Pages: Home, About, Calculator, Contact, Sign in / Sign up. About and Contact content comes from sawie.net.
- New SAWiE logo (`static/img/sawie-logo.png`) in the navigation, footer, assistant, report and the home-page source diagram.
- Animations use Motion (`static/vendor/motion.js`); charts use Chart.js (`static/vendor/chart.umd.min.js`). Nothing loads from a CDN.
- Calculation code (`computeAll()`, emission factors, `calculator.py`) is unchanged.

**Weather**
- `GET /api/widgets/weather` picks the location in this order: `?lat=&lon=` from the browser, `?city=`, then the visitor's IP.
- Browsers only share GPS on HTTPS or localhost. On a LAN address such as `http://192.168.x.x:8000` the app uses the network location instead, and users can type a city.

**Sign-in**
- HttpOnly, SameSite=Lax session cookie (`cl_session`); 12 hours, or 7 days with "Keep me signed in". `POST /api/auth/logout` clears it.
- Season endpoints, `/api/farms/latest` and `/api/chat/ask` require sign-in and only return the signed-in user's farms.
- Database stays SQLite (`carbonlens.db`); `.env` is unchanged.
