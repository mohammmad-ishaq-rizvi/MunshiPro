"""Optional Gemma 4 helpers. Model output is always treated as an editable draft."""
import json
import os
import re

MODEL=os.getenv("GEMMA_MODEL","gemma-4-26b-a4b-it")

def _client():
    key=os.getenv("GEMINI_API_KEY")
    if not key: raise RuntimeError("Add GEMINI_API_KEY to use Gemma 4.")
    from google import genai
    return genai.Client(api_key=key)

def _json(text):
    match=re.search(r"\{.*\}|\[.*\]",text,re.S)
    if not match: raise ValueError("Gemma did not return structured JSON. Please enter the details manually.")
    return json.loads(match.group())

def parse_voice_order(transcript,catalog=None):
    from google.genai import types
    prompt=f"""Extract explicitly stated shop line items from this Hindi, Hinglish or English voice transcript. Return JSON only: {{\"items\":[{{\"product\":string,\"quantity\":number|null,\"unit_price\":number|null}}]}}. Do not invent prices, quantities, units, tax, or products. Use null for unstated values; quantity 1 only when clearly implied. Known catalogue: {json.dumps(catalog or {},ensure_ascii=False)}. Transcript: {transcript}"""
    response=_client().models.generate_content(model=MODEL,contents=prompt,config=types.GenerateContentConfig(temperature=0))
    data=_json(response.text or ""); rows=data if isinstance(data,list) else data.get("items",[])
    return [{"product":str(r.get("product","")),"quantity":None if r.get("quantity") in (None,"") else float(r["quantity"]),"unit_price":None if r.get("unit_price") in (None,"") else float(r["unit_price"]),"needs_review":r.get("quantity") in (None,"") or r.get("unit_price") in (None,"") or not str(r.get("product","")).strip()} for r in rows]

def read_ledger_image(data,mime_type="image/jpeg"):
    from google.genai import types
    image=types.Part.from_bytes(data=data,mime_type=mime_type)
    prompt="""Read this handwritten shop ledger page. Return JSON only: {\"rows\":[{\"date\":\"\",\"customer\":\"\",\"description\":\"\",\"debit\":0,\"credit\":0,\"confidence\":\"low|medium|high\"}]}. Preserve script and spelling. Transcribe visible rows only. Never infer unclear amounts, balances or transaction types. Use empty strings/null for unreadable fields. Every row needs human review."""
    response=_client().models.generate_content(model=MODEL,contents=[image,prompt],config=types.GenerateContentConfig(temperature=0))
    data=_json(response.text or ""); rows=data if isinstance(data,list) else data.get("rows",[])
    return [{**r,"reviewed":False} for r in rows]
