from decimal import Decimal
import pytest
from dukaan.core import invoice_totals, parse_order, validate_rows

def test_decimal_invoice_and_gst_split():
    result=invoice_totals([{"quantity":2,"unit_price":"10.25"}],5,1,"intra-state")
    assert result["subtotal"]==Decimal("20.50") and result["taxable"]==Decimal("19.50")
    assert result["cgst"]==Decimal("0.49") and result["sgst"]==Decimal("0.49")
    assert result["total"]==Decimal("20.48")

def test_interstate_gst_is_igst():
    result=invoice_totals([{"quantity":1,"unit_price":100}],18,0,"inter-state")
    assert result["igst"]==Decimal("18.00") and result["cgst"]==0

def test_discount_cannot_exceed_subtotal():
    with pytest.raises(ValueError): invoice_totals([{"quantity":1,"unit_price":2}],0,3)

def test_parser_flags_missing_price():
    row=parse_order("दो साबुन")[0]
    assert row["quantity"]==2 and row["unit_price"] is None and row["needs_review"]

def test_empty_extraction_rejected():
    with pytest.raises(ValueError): validate_rows([])
