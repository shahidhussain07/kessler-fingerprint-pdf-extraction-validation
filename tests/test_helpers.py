"""Quick checks for helpers.py. Run from the project folder: python -m tests.test_helpers"""
from decimal import Decimal

from fingerprint.helpers import add_days, clean_vat_id, parse_date, parse_number, to_json_number


def check(actual, expected):
    assert actual == expected, f"expected {expected!r}, got {actual!r}"


# Numbers – every format that appears in the samples
check(parse_number("8,45"), Decimal("8.45"))
check(parse_number("1.323,70"), Decimal("1323.70"))
check(parse_number("1.000"), Decimal("1000"))        # quantity with thousands dot
check(parse_number("12,5"), Decimal("12.5"))         # quantity in metres
check(parse_number("225,80-"), Decimal("-225.80"))   # credit note, trailing minus
check(parse_number("-13,97"), Decimal("-13.97"))     # INV-05 discount row
check(parse_number("260,70 €"), Decimal("260.70"))   # INV-05 euro sign
check(parse_number("19%"), Decimal("19"))            # INV-05 VAT column
check(parse_number("0,152"), Decimal("0.152"))       # INV-05 price per piece
check(parse_number(""), None)

try:
    parse_number("abc")
    raise AssertionError("should have failed")
except ValueError:
    pass

# Dates
check(parse_date("06.10.2026"), "2026-10-06")
check(parse_date("vom 22.09.2026"), "2026-09-22")
check(parse_date("19. Oktober 2026"), "2026-10-19")
check(parse_date("(bis 18. November 2026)."), "2026-11-18")
check(add_days("2026-10-14", 7), "2026-10-21")

# Other
check(clean_vat_id("DE 287 364 519"), "DE287364519")
check(to_json_number(Decimal("202.80")), 202.8)
check(to_json_number(None), None)

print("All helper checks passed")
