"""Weather and news widgets — proxy endpoints to avoid CORS."""
import os, time, re, html as _html, threading, xml.etree.ElementTree as ET
import requests as _req
from flask import Blueprint, jsonify, request

widgets_bp = Blueprint("widgets", __name__)

_weather_cache = {}   # city -> {data, ts}
_news_cache    = {}   # key  -> {data, ts}
WEATHER_TTL = 900     # 15 min
NEWS_TTL    = 86400    # 24 hours

SAWIE_NEWS = [
    {
        "title": "Unlocking Agricultural Carbon Markets: Climate-Smart Solutions for a Resilient Future",
        "desc": "SAWiE and its partners explored practical routes to reduce emissions, support sustainable rice production, and connect farmers with climate finance and agricultural carbon markets.",
        "url": "https://sawie.net/unlocking-agricultural-carbon-markets-climate-smart-solutions-for-a-resilient-future/",
        "source": "SAWiE | 27 August 2026",
        "image": "",
        "published_at": "2026-08-27",
    },
    {
        "title": "Stakeholder Consultation Meeting | Rice Methane Reduction Project | Layyah",
        "desc": "SAWiE's Layyah project focuses on reducing methane from rice cultivation through Alternate Wetting and Drying, supporting low-emission rice value chains and crop-specific carbon action alongside cotton footprinting.",
        "url": "https://sawie.net/%f0%9f%8c%be-stakeholder-consultation-meeting-rice-methane-reduction-project-layyah/",
        "source": "SAWiE | Rice Carbon Project",
        "image": "",
        "published_at": "2026-07-02",
    },
]
SAWIE_FEED = "https://sawie.net/feed/"

_IMG_EXT_RE = re.compile(r"\.(jpe?g|png|webp|gif)(\?|$)", re.I)
_WP_SIZE_RE = re.compile(r"-\d{2,4}x\d{2,4}(?=\.[^.]+$)", re.I)
_TRACKING_HINT_RE = re.compile(r"pixel|1x1|spacer|blank|icon|logo|avatar|favicon|emoji|s\.w\.org", re.I)

def _looks_like_real_image(url: str) -> bool:
    """Filter out tracking pixels, site logos/icons, and non-image URLs that
    the RSS/content-scraping regex can sometimes pick up, so the frontend
    doesn't end up trying to render a broken/blank image."""
    if not url or not url.startswith("http"):
        return False
    if _TRACKING_HINT_RE.search(url):
        return False
    # Accept if it has a recognisable image extension, OR comes from a known
    # image CDN pattern that omits the extension (e.g. ?w=..&q=.. resizers).
    if _IMG_EXT_RE.search(url):
        return True
    if any(host in url for host in ("images.unsplash.com", "media.", "img.", "/image/", "/images/")):
        return True
    return False

def _full_size_image(url: str) -> str:
    """Use the original WordPress upload instead of a small feed thumbnail."""
    return _WP_SIZE_RE.sub("", url or "")

def _image_ok(url: str) -> bool:
    """True if the URL really serves an image (guards against guessed URLs that 404)."""
    try:
        r = _req.get(url, timeout=6, stream=True, headers={"User-Agent": "Mozilla/5.0 CarbonLens/1.0"})
        ok = r.status_code == 200 and "image" in (r.headers.get("Content-Type", "").lower())
        r.close()
        return ok
    except Exception:
        return False

def _article_images(article_url: str):
    """Return (image, image_alt) from the article's social preview image.
    `image` is the best guess, `image_alt` is the untouched og:image URL so the
    browser can fall back to it if the first one fails."""
    for attempt in range(2):
        try:
            r = _req.get(article_url, timeout=8, headers={"User-Agent": "Mozilla/5.0 CarbonLens/1.0"})
            if r.status_code != 200:
                continue
            for pattern in (
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
            ):
                match = re.search(pattern, r.text, re.I)
                if match:
                    raw = _html.unescape(match.group(1)).strip()
                    if raw.startswith("//"):
                        raw = "https:" + raw
                    if not raw.startswith("http"):
                        continue
                    full = _full_size_image(raw)
                    if full != raw and not _image_ok(full):
                        full = raw          # guessed full-size file does not exist
                    return full, raw
        except Exception:
            pass
    return "", ""

def _article_image(article_url: str) -> str:
    """Read the publisher's official social preview image when RSS has none."""
    return _article_images(article_url)[0]

def _resolve_article_url(article_url: str) -> str:
    """Follow an aggregator link so cards point to the original publisher."""
    if "news.google.com/rss/articles/" not in article_url:
        return article_url
    try:
        r = _req.get(article_url, timeout=5, headers={"User-Agent": "CarbonLens/1.0"}, allow_redirects=True)
        final_url = r.url or article_url
        if final_url and "news.google.com" not in final_url:
            return final_url
    except Exception:
        pass
    return article_url

def _relevant(article: dict, terms) -> bool:
    text = f"{article.get('title', '')} {article.get('desc', '')}".lower()
    return any(term in text for term in terms)

def _parse_rss(feed_url, source_name, max_items=3):
    """Fetch one RSS feed and return list of article dicts."""
    articles = []
    try:
        r = _req.get(feed_url, timeout=3, headers={"User-Agent": "CarbonLens/1.0"})
        if r.status_code != 200:
            return articles
        root = ET.fromstring(r.content)
        ns = {"media": "http://search.yahoo.com/mrss/"}
        for item in root.findall(".//item")[:max_items]:
            title = (item.findtext("title") or "").strip()
            desc = _html.unescape(re.sub(r"<[^>]+>", "", item.findtext("description") or "")).strip()[:200]
            url = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            image = ""
            thumb = item.find("media:thumbnail", ns)
            content = item.find("media:content", ns)
            enclosure = item.find("enclosure")
            if thumb is not None:
                image = thumb.get("url", "")
            if content is not None and content.get("url"):
                image = content.get("url")
            if enclosure is not None and "image" in enclosure.get("type", ""):
                image = enclosure.get("url", "")
            for child in item.iter():
                if child.text and "<img" in child.text:
                    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', child.text)
                    if match:
                        image = match.group(1)
                        break
            image = _full_size_image(image)
            if not _looks_like_real_image(image):
                image = _article_image(url)
            if title and url:
                articles.append({
                    "title": title, "desc": desc, "url": url,
                    "image": image, "source": source_name, "published_at": pub,
                })
    except Exception:
        pass
    return articles

def _parse_rss_bounded(feed_url, source_name, max_items=3, timeout=4):
    """Fetch a feed without allowing a slow external host to block the app."""
    result = []
    worker = threading.Thread(
        target=lambda: result.extend(_parse_rss(feed_url, source_name, max_items)),
        daemon=True,
    )
    worker.start()
    worker.join(timeout)
    return result

def _fetch_live_news():
    """Return the two latest relevant SAWiE posts."""
    results = {"sawie": []}
    worker = threading.Thread(
        target=lambda: results.__setitem__("sawie", _parse_rss_bounded(SAWIE_FEED, "SAWiE", max_items=12)),
        daemon=True,
    )
    worker.start()
    worker.join(5)

    sawie_feed = results["sawie"]
    sawie_articles = [a for a in sawie_feed if _relevant(
        a, ("cotton", "carbon", "climate", "agriculture", "methane", "rice"))][:2]
    if len(sawie_articles) < 2:
        for article in SAWIE_NEWS:
            if article["url"] not in {a["url"] for a in sawie_articles}:
                sawie_articles.append(article)
            if len(sawie_articles) == 2:
                break

    final_articles = sawie_articles[:2]

    # Kisi bhi article mein image nahi hai tu OG image fetch karo parallel threads se
    final_articles = [dict(a) for a in final_articles]   # copies: never mutate SAWIE_NEWS

    def _resolve_image(article):
        if not article.get("image"):
            img, alt = _article_images(article["url"])
            article["image"] = img
            article["image_alt"] = alt

    threads = [threading.Thread(target=_resolve_image, args=(a,), daemon=True) for a in final_articles]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)

    return final_articles


import ipaddress


def _client_ip():
    """Best guess at the visitor's public IP (works behind a reverse proxy)."""
    for h in ("X-Forwarded-For", "X-Real-IP", "CF-Connecting-IP"):
        v = request.headers.get(h, "")
        if v:
            return v.split(",")[0].strip()
    return request.remote_addr or ""


def _is_public(ip):
    try:
        a = ipaddress.ip_address(ip)
        return not (a.is_private or a.is_loopback or a.is_link_local or a.is_reserved)
    except ValueError:
        return False


def _ip_location(ip):
    """City + coordinates for a public IP. Returns None if unknown."""
    try:
        r = _req.get(f"https://ipwho.is/{ip}", timeout=4, headers={"User-Agent": "CarbonLens/1.0"})
        d = r.json() if r.status_code == 200 else {}
        if d.get("success") and d.get("latitude") is not None:
            return {"lat": d["latitude"], "lon": d["longitude"],
                    "city": d.get("city") or "", "region": d.get("region") or "", "country": d.get("country") or ""}
    except Exception:
        pass
    return None


@widgets_bp.get("/weather")
def weather():
    """Weather for the visitor's location.

    Priority: exact coordinates from the browser (?lat=&lon=), then a city the
    user typed (?city=), then the visitor's IP address. When the app runs on a
    local network the server shares the visitor's internet connection, so
    wttr.in's own IP lookup gives the same town.
    """
    lat = request.args.get("lat", "").strip()
    lon = request.args.get("lon", "").strip()
    city = request.args.get("city", "").strip()
    label = None
    source = "ip"
    if lat and lon:
        try:
            location = f"{float(lat):.4f},{float(lon):.4f}"
            source = "gps"
        except ValueError:
            return jsonify({"error": "bad coordinates"}), 400
    elif city:
        location = city[:80]
        source = "city"
    else:
        ip = _client_ip()
        loc = _ip_location(ip) if _is_public(ip) else None
        if loc:
            location = f"{loc['lat']:.4f},{loc['lon']:.4f}"
            label = ", ".join(x for x in (loc["city"], loc["country"]) if x)
        else:
            location = ""          # wttr.in locates the server's own public IP

    now = time.time()
    key = location or "__auto__"
    if key in _weather_cache and now - _weather_cache[key]["ts"] < WEATHER_TTL:
        data = dict(_weather_cache[key]["data"]); data["source"] = source
        return jsonify(data)
    try:
        r = _req.get(f"https://wttr.in/{_quote(location)}?format=j1", timeout=8,
                     headers={"User-Agent": "CarbonLens/1.0"})
        if r.status_code != 200:
            return jsonify({"error": "weather unavailable"}), 502
        j = r.json()
        cur = j["current_condition"][0]
        nearest = (j.get("nearest_area") or [{}])[0]
        area = (nearest.get("areaName") or [{}])[0].get("value", "")
        region = (nearest.get("region") or [{}])[0].get("value", "")
        country = (nearest.get("country") or [{}])[0].get("value", "")
        if source == "city":
            label = city.title() + (f", {country}" if country and country.lower() not in city.lower() else "")
        display = label or ", ".join(x for x in (area, region if region != area else "", country) if x) or "Your location"
        forecast = []
        for day in (j.get("weather") or [])[:3]:
            hourly = day.get("hourly") or []
            mid = hourly[len(hourly) // 2] if hourly else {}
            forecast.append({
                "date": day.get("date"),
                "max_c": day.get("maxtempC"),
                "min_c": day.get("mintempC"),
                "icon": _weather_icon(int(mid.get("weatherCode", 113))),
                "desc": ((mid.get("weatherDesc") or [{}])[0]).get("value", ""),
                "rain_pct": mid.get("chanceofrain"),
            })
        result = {
            "city":      display,
            "temp_c":    cur["temp_C"],
            "feels_c":   cur["FeelsLikeC"],
            "humidity":  cur["humidity"],
            "desc":      cur["weatherDesc"][0]["value"],
            "wind_kmph": cur["windspeedKmph"],
            "icon":      _weather_icon(int(cur["weatherCode"])),
            "forecast":  forecast,
            "source":    source,
        }
        _weather_cache[key] = {"data": result, "ts": now}
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 502


def _quote(s):
    from urllib.parse import quote
    return quote(s, safe=",.-")


def _weather_icon(code):
    if code in (113,):                    return "☀️"
    if code in (116,):                    return "⛅"
    if code in (119, 122):               return "☁️"
    if code in (143, 248, 260):          return "🌫️"
    if code in (176,179,182,185):        return "🌦️"
    if code in (200,386,389,392,395):    return "⛈️"
    if code in (302,305,308,314,317):    return "🌧️"
    return "🌡️"


@widgets_bp.get("/news")
def news():
    cache_key = "agri"
    now = time.time()
    # bust=1 parameter aaye tu cache ignore karo (Refresh button se)
    force_refresh = request.args.get("bust", "0") == "1"
    if (not force_refresh
            and cache_key in _news_cache
            and now - _news_cache[cache_key]["ts"] < NEWS_TTL):
        return jsonify(_news_cache[cache_key]["data"])

    articles = _fetch_live_news()
    result = {"articles": articles}
    # If any image could not be resolved, keep the result only briefly so the
    # next visit retries instead of showing the fallback picture for 24 hours.
    complete = all(a.get("image") for a in articles)
    _news_cache[cache_key] = {"data": result, "ts": now if complete else now - NEWS_TTL + 300}
    return jsonify(result)
