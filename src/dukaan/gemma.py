"""Optional Gemma 4 helpers. Model output is always treated as an editable draft."""
import base64
import io
import json
import os
import re

import requests
from PIL import Image, ImageOps

MODEL = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _secret(name):
    try:
        import streamlit as st
        value = st.secrets.get(name)
        if value:
            return str(value).strip()
    except Exception:
        pass
    return (os.getenv(name) or "").strip()


def _generate(parts, max_tokens=2048):
    key = _secret("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Add GEMINI_API_KEY to Streamlit Secrets or the environment to use Gemma 4.")
    model = _secret("GEMMA_MODEL") or MODEL
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": max_tokens},
    }
    resp = None
    last_err = None
    for _ in range(2):  # one automatic retry
        try:
            resp = requests.post(
                API_URL.format(model=model),
                headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                json=body,
                timeout=(15, 180),
            )
            break
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            last_err = e
    if resp is None:
        raise RuntimeError(
            "Google took too long to answer. Try a smaller or clearer photo, or try again in a minute."
        ) from last_err
    if resp.status_code != 200:
        try:
            msg = resp.json()["error"]["message"]
        except Exception:
            msg = resp.text[:300]
        raise RuntimeError(f"Gemini API error {resp.status_code}: {msg}")
    try:
        parts_out = resp.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts_out if not p.get("thought"))
    except Exception:
        return ""  # empty answer: callers fall back instead of failing


def _json(text):
    """Return the last complete top-level JSON object/array in the reply."""
    text = re.sub(r"```(?:json)?", "", text or "")
    dec = json.JSONDecoder()
    found = None
    i = 0
    while i < len(text):
        if text[i] in "{[":
            try:
                obj, end = dec.raw_decode(text[i:])
                if isinstance(obj, list) or (isinstance(obj, dict) and obj):
                    found = obj
                i += end
                continue
            except ValueError:
                pass
        i += 1
    if found is None:
        raise ValueError("Gemma did not return valid JSON. Try again or enter the details manually.")
    return found


def parse_voice_order(transcript, catalog=None):
    prompt = f"""Extract the shop line items explicitly stated in this Hindi, Hinglish or English voice transcript.
Reply with ONLY one JSON object, no explanation, no markdown.
Example of the exact format: {{"items":[{{"product":"chawal","quantity":2,"unit_price":60}},{{"product":"tel","quantity":1,"unit_price":null}}]}}
Rules: product is text, quantity and unit_price are numbers or null. Do not invent prices, quantities, units, tax or products. Use null for anything not stated; use quantity 1 only when clearly implied.
Known catalogue: {json.dumps(catalog or {}, ensure_ascii=False)}
Transcript: {transcript}"""
    data = _json(_generate([{"text": prompt}], max_tokens=2048))
    rows = data if isinstance(data, list) else data.get("items", [])
    out = []
    for r in rows:
        q, p = r.get("quantity"), r.get("unit_price")
        name = str(r.get("product", ""))
        out.append({
            "product": name,
            "quantity": None if q in (None, "") else float(q),
            "unit_price": None if p in (None, "") else float(p),
            "needs_review": q in (None, "") or p in (None, "") or not name.strip(),
        })
    return out


def _prepare_image(data, max_side=1600):
    """Fix rotation, boost contrast, shrink and compress."""
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageOps.autocontrast(img, cutoff=1)  # makes faint pen/pencil easier to read
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88, optimize=True)
    return buf.getvalue(), "image/jpeg"


_ALIASES = {
    "customer": ("customer", "name", "party", "naam", "person"),
    "description": ("description", "particulars", "item", "items", "details", "detail", "note", "vivaran"),
    "debit": ("debit", "dr", "debit_amount", "udhaar", "given"),
    "credit": ("credit", "cr", "credit_amount", "received", "jama"),
    "date": ("date", "tarikh", "day"),
    "confidence": ("confidence",),
}


def _pick(row, field):
    low = {str(k).lower().strip(): v for k, v in row.items()}
    for k in _ALIASES[field]:
        if k in low and low[k] not in (None,):
            return low[k]
    return ""


def _extract_rows(parsed):
    """Accept {"rows":[..]}, any other key holding a list, or a bare list."""
    if isinstance(parsed, dict):
        lst = None
        for k in ("rows", "entries", "ledger", "transactions", "items", "data"):
            if isinstance(parsed.get(k), list):
                lst = parsed[k]
                break
        if lst is None:
            lst = next((v for v in parsed.values() if isinstance(v, list)), [])
    else:
        lst = parsed
    out = []
    for r in lst:
        if isinstance(r, dict):
            desc = _pick(r, "description")
            amount = r.get("amount") or r.get("Amount")
            if amount not in (None, "") and not _pick(r, "debit") and not _pick(r, "credit"):
                desc = f"{desc} ₹{amount}".strip()
            out.append({"date": _pick(r, "date"), "customer": _pick(r, "customer"), "description": desc,
                        "debit": _pick(r, "debit"), "credit": _pick(r, "credit"),
                        "confidence": _pick(r, "confidence") or "low"})
        elif isinstance(r, str) and r.strip():
            out.append({"date": "", "customer": "", "description": r.strip(), "debit": 0, "credit": 0, "confidence": "low"})
    return [r for r in out if any(str(v).strip() not in ("", "0") for k, v in r.items() if k != "confidence")]


def _rows_from_text(text):
    rows = []
    for line in (text or "").splitlines():
        line = re.sub(r"^[\s\-\*\u2022\d\.\)]*(?=\S)", "", line.strip()) if re.match(r"^\s*[\-\*\u2022]", line) else line.strip()
        if len(line) < 2 or line.endswith(":") or line.lower().startswith(("here", "sure", "the image", "this image")):
            continue
        rows.append({"date": "", "customer": "", "description": line, "debit": 0, "credit": 0, "confidence": "low"})
    return rows


_PROMPT_JSON = """This is a photo of a handwritten shop ledger (khata) page, probably Hindi, Hinglish or English.
List EVERY line of handwriting you can see as one row, even if you are unsure. Do not skip lines because they look messy.
Reply with ONLY one JSON object, no explanation, no markdown, in this format:
{"rows":[{"date":"","customer":"","description":"","debit":0,"credit":0,"confidence":"low"}]}
Rules: copy the original script and spelling; put a person's name in customer; put what was bought or the note in description; put money amounts in debit (amount given on credit or sold) or credit (amount received) when it is clear, otherwise 0; confidence is low, medium or high. Use "" for anything unreadable. Do not invent values."""

_PROMPT_TEXT = """Transcribe all the handwritten text in this image exactly as written, one line per line, in its original script. If part is unclear, write what you best see. Output only the transcription, no commentary."""


def read_ledger_image(data, mime_type="image/jpeg"):
    try:
        data, mime_type = _prepare_image(data)
    except Exception:
        pass
    image = {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(data).decode()}}
    rows = []
    try:  # pass 1: structured rows
        rows = _extract_rows(_json(_generate([image, {"text": _PROMPT_JSON}], max_tokens=4096)))
    except Exception:
        rows = []
    if not rows:  # pass 2: plain transcription, one line per row
        rows = _rows_from_text(_generate([image, {"text": _PROMPT_TEXT}], max_tokens=2048))
    return [{**r, "reviewed": False} for r in rows]