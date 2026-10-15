import re
from datetime import datetime

AMOUNT = re.compile(r"(?<!\w)(?:₹|Rs\.?\s*)?([0-9][0-9,]*(?:\.[0-9]{1,2})?)(?!\w)")
DATE = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b")


def parse_lines(text: str) -> list[dict]:
    """Extract cautious transaction candidates; all rows require human review."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        amount_match = AMOUNT.search(line)
        date_match = DATE.search(line)
        amount = float(amount_match.group(1).replace(",", "")) if amount_match else None
        date = ""
        if date_match:
            raw = date_match.group(1).replace("-", "/")
            for fmt in ("%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y"):
                try:
                    date = datetime.strptime(raw, fmt).date().isoformat()
                    break
                except ValueError:
                    pass
        lower = line.lower()
        kind = "sale" if any(w in lower for w in ("sale", "sold", "बिक्री", "बेचा")) else "expense" if any(w in lower for w in ("खर्च", "खरीद", "expense", "purchase")) else "unknown"
        description = line
        if amount_match:
            description = (line[:amount_match.start()] + line[amount_match.end():]).strip(" :-,₹")
        rows.append({"date": date, "description": description or line, "amount": amount,
                     "kind": kind, "source_text": line,
                     "confidence": 0.65 if amount is not None else 0.2, "reviewed": False})
    return rows
