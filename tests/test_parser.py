from dukaan.parser import parse_lines
from dukaan.summary import summarize


def test_extracts_amount_and_date_without_claiming_review():
    row = parse_lines("12/04/2025 बिक्री दूध ₹1,250")[0]
    assert row["amount"] == 1250
    assert row["date"] == "2025-04-12"
    assert row["kind"] == "sale"
    assert row["reviewed"] is False


def test_summary_ignores_unclassified_from_net():
    result = summarize([{"amount": 100, "kind": "sale"}, {"amount": 30, "kind": "expense"}, {"amount": 9, "kind": "unknown"}])
    assert result == {"sales": 100.0, "expenses": 30.0, "net": 70.0, "unclassified": 1}
