"""CarbonLens Assistant — a topic-restricted chatbot.

Uses Groq's free-tier API (OpenAI-compatible /chat/completions endpoint).
Only answers questions related to CarbonLens, cotton carbon footprints,
emission factors, and the report/app itself — anything else gets politely
redirected, enforced via the system prompt.
"""
import os

import requests
from flask import Blueprint, request, jsonify

chatbot_bp = Blueprint("chatbot", __name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

SYSTEM_PROMPT = (
    "You are the CarbonLens Assistant, embedded inside the CarbonLens cotton "
    "carbon-footprint calculator app. You ONLY answer questions about: "
    "(1) how to use CarbonLens (registering a farm, entering a season, "
    "reading the results, downloading the Word/PDF report), "
    "(2) cotton farming's carbon footprint, emission sources (fertiliser, "
    "irrigation, machinery, residue burning, crop protection, labour), "
    "(3) general carbon-footprint / greenhouse-gas / sustainability concepts "
    "relevant to agriculture. "
    "If the user asks about anything unrelated (coding help, other software, "
    "general trivia, personal advice, other companies, etc.), politely say "
    "you can only help with CarbonLens and cotton carbon-footprint questions, "
    "and ask if they have a question about that instead. "
    "Keep answers short (2-5 sentences), clear, and practical. "
    "You may answer in the same mix of Urdu/English the user writes in."
)


@chatbot_bp.post("/ask")
def ask():
    data = request.get_json() or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []  # [{role:"user"/"assistant", content:"..."}]

    if not message:
        return jsonify({"detail": "Message is required"}), 400

    if not GROQ_API_KEY:
        return jsonify({
            "reply": "The assistant isn't configured yet — add a free GROQ_API_KEY "
                     "in the .env file to enable it (see console.groq.com)."
        }), 200

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    # keep only the last few turns to stay light on tokens
    for turn in history[-6:]:
        role = turn.get("role")
        content = (turn.get("content") or "")[:1000]
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message[:2000]})

    try:
        resp = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": messages,
                "temperature": 0.4,
                "max_tokens": 300,
            },
            timeout=20,
        )
        if resp.status_code != 200:
            # Print the real reason to the terminal so it's easy to diagnose
            # (e.g. deprecated model, bad key, rate limit) instead of a generic message.
            print(f"[CarbonLens Assistant] Groq API error {resp.status_code}: {resp.text}")
            return jsonify({
                "reply": "Sorry, the assistant hit a configuration issue. "
                         "Check the terminal log for the exact Groq API error."
            }), 200
        payload = resp.json()
        reply = payload["choices"][0]["message"]["content"].strip()
        return jsonify({"reply": reply})
    except requests.exceptions.RequestException as e:
        print(f"[CarbonLens Assistant] Request failed: {e}")
        return jsonify({
            "reply": "Sorry, the assistant is temporarily unavailable. Please try again shortly."
        }), 200
    except (KeyError, IndexError) as e:
        print(f"[CarbonLens Assistant] Unexpected response shape: {e}")
        return jsonify({
            "reply": "Sorry, I couldn't generate a reply just now — please try again."
        }), 200
