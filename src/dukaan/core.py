"""Deterministic business rules. AI/OCR suggestions never become records without review."""
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import datetime
import hashlib
import re

CENT = Decimal("0.01")

def money(value) -> Decimal:
    try:
        result = Decimal(str(value).replace(",", "").replace("₹", "").strip())
    except (InvalidOperation, AttributeError):
        raise ValueError("Enter a valid amount")
    if not result.is_finite() or result < 0: raise ValueError("Amount must be non-negative")
    return result.quantize(CENT, rounding=ROUND_HALF_UP)

def invoice_totals(items, tax_rate=0, discount=0, tax_type="none"):
    rate=Decimal(str(tax_rate)); discount=money(discount)
    if rate < 0 or rate > 100: raise ValueError("Tax rate must be between 0 and 100")
    subtotal=sum((money(i["quantity"])*money(i["unit_price"]) for i in items), Decimal(0))
    if discount > subtotal: raise ValueError("Discount cannot exceed subtotal")
    taxable=subtotal-discount; tax=(taxable*rate/100).quantize(CENT,rounding=ROUND_HALF_UP)
    cgst=sgst=igst=Decimal(0)
    if tax_type=="intra-state": cgst=sgst=(tax/2).quantize(CENT,rounding=ROUND_HALF_UP)
    elif tax_type=="inter-state": igst=tax
    elif tax_type!="none": raise ValueError("Choose a valid tax treatment")
    return {"subtotal":subtotal.quantize(CENT),"discount":discount,"taxable":taxable.quantize(CENT),"cgst":cgst,"sgst":sgst,"igst":igst,"tax":tax,"total":(taxable+tax).quantize(CENT)}

NUM={"एक":1,"दो":2,"तीन":3,"चार":4,"पांच":5,"पाँच":5,"छह":6,"सात":7,"आठ":8,"नौ":9,"दस":10,"डेढ़":1.5,"आधा":0.5}
def parse_order(text, catalog=None):
    """Parse explicit item chunks; unknown price remains unset for seller review."""
    catalog={str(k).casefold():v for k,v in (catalog or {}).items()}; rows=[]
    for chunk in re.split(r",|\n|\s+और\s+|\s+and\s+", text.strip(),flags=re.I):
        if not chunk.strip(): continue
        numbers=re.findall(r"\d+(?:\.\d+)?",chunk)
        qty_word=next((v for w,v in NUM.items() if w in chunk),None)
        qty=float(numbers[0]) if len(numbers)>1 else float(qty_word or (numbers[0] if numbers else 1))
        price=float(numbers[-1]) if len(numbers)>1 else None
        product=re.sub(r"\d+(?:\.\d+)?|₹|रुपये|रुपए|रुपया|rs\.?|\b(?:kg|किलो|लीटर|लिटर|pcs?|pieces?)\b|किलो|लीटर|का|की|के|each|at","",chunk,flags=re.I).strip(" :-")
        catalog_price=catalog.get(product.casefold())
        if price is None and catalog_price is not None: price=float(catalog_price)
        rows.append({"product":product or "", "quantity":qty,"unit_price":price,"needs_review":not bool(product) or price is None})
    return rows

def parse_ledger_text(text):
    """Conservative OCR line candidates; no balance or transaction is invented."""
    out=[]
    for line in text.splitlines():
        nums=re.findall(r"(?:₹|Rs\.?\s*)?([0-9][0-9,]*(?:\.\d{1,2})?)",line,re.I)
        if not line.strip(): continue
        date=re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",line)
        out.append({"date":date.group() if date else "", "description":line.strip(),"debit":float(nums[-2].replace(",","")) if len(nums)>1 else 0,"credit":float(nums[-1].replace(",","")) if nums else 0,"confidence":"low","reviewed":False})
    return out

def file_hash(data): return hashlib.sha256(data).hexdigest()

def validate_rows(rows):
    if not rows: raise ValueError("No transaction rows found")
    if not any(str(r.get("product",r.get("description",""))).strip() for r in rows): raise ValueError("No readable product or description found")
    return True
