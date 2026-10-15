"""Optional Gemma 4 helpers. Model output is always treated as an editable draft."""
import json
import os
import re

MODEL = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")


def _api_key():
    # 1) Streamlit Secrets (Streamlit Cloud or .streamlit/secrets.toml)
    try:
        import streamlit as st
        key = st.secrets.get("GEMINI_API_KEY")
        if key:
            return str(key).strip()
    except Exception:
        pass
    # 2) Environment variable (PyCharm, Docker, Render)
    return (os.getenv("GEMINI_API_KEY") or "").strip()


def _model():
    try:
        import streamlit as st
        m = st.secrets.get("GEMMA_MODEL")
        if m:
            return str(m).strip()
    except Exception:
        pass
    return MODEL


def _generate(contents):
    """Create a client, keep a reference for the whole call, then close it."""
    key = _api_key()
    if not key:
        raise RuntimeError("Add GEMINI_API_KEY to Streamlit Secrets or the environment to use Gemma 4.")
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key)  # held in a variable so it is not garbage collected mid-request
    try:
        response = client.models.generate_content(
            model=_model(),
            contents=contents,
            config=types.GenerateContentConfig(temperature=0),
        )
        return response.text or ""
    finally:
        try:
            client.close()
        except Exception:
            pass


def _json(text):
    match = re.search(r"\{.*\}|\[.*\]", text, re.S)
    if not match:
        raise ValueError("Gemma did not return structured JSON. Please enter the details manually.")
    return json.loads(match.group())


def parse_voice_order(transcript, catalog=None):
    prompt = f"""Extract explicitly stated shop line items from this Hindi, Hinglish or English voice transcript. Return JSON only: {{"items":[{{"product":string,"quantity":number|null,"unit_price":number|null}}]}}. Do not invent prices, quantities, units, tax, or products. Use null for unstated values; quantity 1 only when clearly implied. Known catalogue: {json.dumps(catalog or {}, ensure_ascii=False)}. Transcript: {transcript}"""
    data = _json(_generate(prompt))
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


def read_ledger_image(data, mime_type="image/jpeg"):
    from google.genai import types
    image = types.Part.from_bytes(data=data, mime_type=mime_type)
    prompt = """Read this handwritten shop ledger page. Return JSON only: {"rows":[{"date":"","customer":"","description":"","debit":0,"credit":0,"confidence":"low|medium|high"}]}. Preserve script and spelling. Transcribe visible rows only. Never infer unclear amounts, balances or transaction types. Use empty strings/null for unreadable fields. Every row needs human review."""
    parsed = _json(_generate([image, prompt]))
    rows = parsed if isinstance(parsed, list) else parsed.get("rows", [])
    return [{**r, "reviewed": False} for r in rows]