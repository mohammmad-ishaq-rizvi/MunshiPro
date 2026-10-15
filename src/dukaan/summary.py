def summarize(rows: list[dict]) -> dict:
    sales = sum(float(r["amount"] or 0) for r in rows if r["kind"] == "sale")
    expenses = sum(float(r["amount"] or 0) for r in rows if r["kind"] == "expense")
    return {"sales": round(sales, 2), "expenses": round(expenses, 2),
            "net": round(sales - expenses, 2), "unclassified": sum(r["kind"] == "unknown" for r in rows)}
