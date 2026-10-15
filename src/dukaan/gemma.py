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
    resp = requests.post(
        API_URL.format(model=model),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json=body,
        timeout=90,
    )
    if resp.status_code != 200:
        try:
            msg = resp.json()["error"]["message"]
        except Exception:
            msg = resp.text[:300]
        raise RuntimeError(f"Gemini API error {resp.status_code}: {msg}")
    try:
        parts_out = resp.json()["candidates"][0]["content"]["parts"]
        # skip the model's reasoning parts, keep only the answer
        return "".join(p.get("text", "") for p in parts_out if not p.get("thought"))
    except Exception:
        raise RuntimeError("Gemma returned no text. Try again or enter the details manually.")


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
                i += end          # jump past this block so inner items are not picked
                continue
            except ValueError:
                pass
        i += 1
    if found is None:
        raise ValueError("Gemma did not return valid JSON. Try again or enter the details manually.")
    return foundgit add -A
git commit -m "Fix JSON picking inner item"
git push origin main --force


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
    """Fix rotation, shrink and compress so the upload and the model are faster."""
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    return buf.getvalue(), "image/jpeg"


def read_ledger_image(data, mime_type="image/jpeg"):
    try:
        data, mime_type = _prepare_image(data)
    except Exception:
        pass
    prompt = """Read this handwritten shop ledger page.
Reply with ONLY one JSON object, no explanation, no markdown.
Example of the exact format: {"rows":[{"date":"12/03","customer":"Ramesh","description":"chawal 2kg","debit":120,"credit":0,"confidence":"medium"}]}
Rules: confidence is one of low, medium, high. Preserve script and spelling. Transcribe visible rows only. Never infer unclear amounts, balances or transaction types. Use "" or null for unreadable fields. Every row needs human review."""
    image = {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(data).decode()}}
    parsed = _json(_generate([image, {"text": prompt}], max_tokens=4096))
    rows = parsed if isinstance(parsed, list) else parsed.get("rows", [])
    return [{**r, "reviewed": False} for r in rows]