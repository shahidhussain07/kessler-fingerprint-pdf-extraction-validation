"""Validation checks V1–V7 and the Markdown report.

Works on the extracted JSON (dicts) only – knows nothing about PDFs.
A FAIL caused by the document itself is a correct result, not a bug: we report it, we never fix it.
"""
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

TOLERANCE = Decimal("0.01")
CENT = Decimal("0.01")


def to_decimal(value):
    """0.1 stays exactly 0.1, 0.1 + 0.2 stays exactly 0.3, 1.00 stays exactly 1.00."""
    return Decimal(str(value))


def money(value):
    """Convert a Decimal to a string with 2 decimal places."""
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


def is_close(a, b):
    return abs(a - b) <= TOLERANCE


def difference_hint(difference):
    """A difference that is a multiple of 9 cents often means two digits were swapped (48.52 <-> 84.52)."""
    cents = int((abs(difference) * 100).to_integral_value())
    if cents and cents % 9 == 0:
        return " (difference is a multiple of 0.09 – typical for swapped digits)"
    return ""


# ---------------------------------------------------------------------------
# The checks. Each one returns (passed: bool, details: list of text lines)
# ---------------------------------------------------------------------------
def check_v1_line_math(doc):
    """V1: every line: quantity × unit_price ÷ price_unit × (1 − discount) = line_total."""
    sign = Decimal("-1") if doc["document_type"] == "credit_note" else Decimal("1")
    details = []
    for item in doc["line_items"]:
        missing = [key for key in ("quantity", "unit_price", "price_unit", "line_total") if item[key] is None]
        if missing:                       # can happen for unreadable OCR cells (INV-06)
            details.append(f"Pos. {item['position']}: cannot check, missing {', '.join(missing)}")
            continue
        discount = to_decimal(item["discount_percent"] or 0) / 100
        expected = (sign * to_decimal(item["quantity"]) * to_decimal(item["unit_price"])
                    / to_decimal(item["price_unit"]) * (1 - discount))
        printed = to_decimal(item["line_total"])
        if not is_close(expected, printed):
            difference = printed - expected
            details.append(
                f"Pos. {item['position']} ({item['article_number']}): "
                f"{item['quantity']} × {item['unit_price']} ÷ {item['price_unit']} × (1 − {discount}) "
                f"= expected {money(expected)}, printed {money(printed)}, "
                f"difference {money(difference)}{difference_hint(difference)}")
    total = len(doc["line_items"])
    if details:
        return False, [f"{len(details)} of {total} lines wrong or not checkable:"] + details
    return True, [f"all {total} lines correct"]


def check_v2_net_per_rate(doc):
    """V2: per VAT rate: sum of line_total = net_by_vat_rate."""
    sums = {}
    passed = True
    details = []
    for item in doc["line_items"]:
        if item["vat_rate"] is None or item["line_total"] is None:
            passed = False
            details.append(f"Pos. {item['position']}: VAT rate or line_total missing – sums are incomplete")
            continue
        rate = str(item["vat_rate"])
        sums[rate] = sums.get(rate, Decimal("0")) + to_decimal(item["line_total"])

    printed_rates = doc["totals"]["net_by_vat_rate"]
    for rate in sorted(set(sums) | set(printed_rates), key=int, reverse=True):
        expected = sums.get(rate, Decimal("0"))
        if printed_rates.get(rate) is None:
            passed = False
            details.append(f"{rate} %: lines add up to {money(expected)}, but no net amount printed for this rate")
            continue
        printed = to_decimal(printed_rates[rate])
        if is_close(expected, printed):
            details.append(f"{rate} %: sum of lines {money(expected)} = net_by_vat_rate {money(printed)}")
        else:
            passed = False
            difference = printed - expected
            details.append(f"{rate} %: sum of lines {money(expected)}, net_by_vat_rate {money(printed)}, "
                           f"difference {money(difference)}{difference_hint(difference)}")

    # Extra cross-check: the per-rate nets must add up to net_total.
    # Important for Layout B, where net_by_vat_rate is derived and only net_total is printed.
    rate_sum = sum((to_decimal(v) for v in printed_rates.values() if v is not None), Decimal("0"))
    net_total = to_decimal(doc["totals"]["net_total"])
    if is_close(rate_sum, net_total):
        details.append(f"all rates: {money(rate_sum)} = net_total {money(net_total)}")
    else:
        passed = False
        details.append(f"all rates: {money(rate_sum)}, net_total {money(net_total)}, "
                       f"difference {money(net_total - rate_sum)}")
    return passed, details


def check_v3_vat_per_rate(doc):
    """V3: per VAT rate: net × rate = vat_by_vat_rate."""
    net_rates = doc["totals"]["net_by_vat_rate"]
    vat_rates = doc["totals"]["vat_by_vat_rate"]
    passed = True
    details = []
    for rate in sorted(set(net_rates) | set(vat_rates), key=int, reverse=True):
        if net_rates.get(rate) is None or vat_rates.get(rate) is None:
            passed = False
            details.append(f"{rate} %: net or VAT amount missing for this rate")
            continue
        expected = to_decimal(net_rates[rate]) * Decimal(rate) / 100
        printed = to_decimal(vat_rates[rate])
        if is_close(expected, printed):
            details.append(f"{rate} %: {money(to_decimal(net_rates[rate]))} × {rate} % = "
                           f"{money(expected)} = printed {money(printed)}")
        else:
            passed = False
            details.append(f"{rate} %: {money(to_decimal(net_rates[rate]))} × {rate} % = expected "
                           f"{money(expected)}, printed {money(printed)}, difference {money(printed - expected)}")
    return passed, details


def check_v4_gross(doc):
    """V4: net_total + vat_total = gross_total."""
    totals = doc["totals"]
    missing = [key for key in ("net_total", "vat_total", "gross_total") if totals[key] is None]
    if missing:
        return False, [f"cannot check, missing {', '.join(missing)}"]
    net, vat, gross = (to_decimal(totals[key]) for key in ("net_total", "vat_total", "gross_total"))
    expected = net + vat
    line = f"{money(net)} + {money(vat)} = {money(expected)}, printed gross {money(gross)}"
    if is_close(expected, gross):
        return True, [line]
    return False, [f"{line}, difference {money(gross - expected)}"]


def check_v5_vat_id(doc):
    """V5: supplier VAT ID looks like a German VAT ID (DE + 9 digits)."""
    vat_id = doc["supplier"]["vat_id"] or ""
    if re.fullmatch(r"DE\d{9}", vat_id):
        return True, [f"{vat_id}"]
    return False, [f"{vat_id!r} is not DE + 9 digits"]


def check_v6_dates(doc):
    """V6: dates are valid; due_date (if present) is not before document_date."""
    date_fields = {
        "document_date": doc.get("document_date"),
        "service_date": doc.get("service_date"),
        "due_date": doc.get("due_date"),
        "cash_discount.until": (doc.get("cash_discount") or {}).get("until"),
    }
    passed = True
    details = []
    parsed = {}
    for name, value in date_fields.items():
        if value is None:
            continue
        try:
            parsed[name] = date.fromisoformat(value)
        except (TypeError, ValueError):
            passed = False
            details.append(f"{name}: {value!r} is not a valid date")

    if "due_date" in parsed and "document_date" in parsed:
        if parsed["due_date"] < parsed["document_date"]:
            passed = False
            details.append(f"due_date {parsed['due_date']} is before document_date {parsed['document_date']}")
        else:
            details.append(f"due_date {parsed['due_date']} ≥ document_date {parsed['document_date']}")
    elif "due_date" not in parsed:
        details.append("no due_date printed – only date format checked")

    if passed:
        details.insert(0, f"valid: {', '.join(parsed)}")
    return passed, details


def check_v7_signs(doc):
    """V7: credit notes: all amounts negative; invoices: all amounts positive."""
    is_credit_note = doc["document_type"] == "credit_note"
    wanted = "negative" if is_credit_note else "positive"

    amounts = [(f"Pos. {item['position']} line_total", item["line_total"]) for item in doc["line_items"]]
    totals = doc["totals"]
    for rate, value in totals["net_by_vat_rate"].items():
        amounts.append((f"net {rate} %", value))
    for rate, value in totals["vat_by_vat_rate"].items():
        amounts.append((f"VAT {rate} %", value))
    for key in ("net_total", "vat_total", "gross_total"):
        amounts.append((key, totals[key]))

    wrong = [f"{name} = {value}" for name, value in amounts
             if value is None or (to_decimal(value) >= 0 if is_credit_note else to_decimal(value) <= 0)]
    if wrong:
        return False, [f"{doc['document_type']}: expected all {wanted}, these are not:"] + wrong
    return True, [f"{doc['document_type']}: all {len(amounts)} amounts {wanted}"]


CHECKS = [
    ("V1", "Line math", check_v1_line_math),
    ("V2", "Net per VAT rate", check_v2_net_per_rate),
    ("V3", "VAT per rate", check_v3_vat_per_rate),
    ("V4", "Net + VAT = gross", check_v4_gross),
    ("V5", "Supplier VAT ID", check_v5_vat_id),
    ("V6", "Dates", check_v6_dates),
    ("V7", "Signs", check_v7_signs),
]


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def validate_document(doc):
    """Run all checks on one document. Returns [(check_id, name, passed, details), ...]."""
    results = []
    for check_id, name, check_function in CHECKS:
        try:
            passed, details = check_function(doc)
        except (KeyError, TypeError, ValueError) as error:   # broken JSON must not crash the report
            passed, details = False, [f"could not run check: {error!r}"]
        results.append((check_id, name, passed, details))
    return results


def build_report(all_results):
    """all_results: [(file_name, document_number, results), ...] -> Markdown text."""
    lines = ["# Validation report", "",
             f"Tolerance for amounts: ±{TOLERANCE}. A FAIL caused by the document itself is a real finding.", "",
             "## Summary", "",
             "| Document | " + " | ".join(check_id for check_id, _, _ in CHECKS) + " |",
             "|---|" + "---|" * len(CHECKS)]
    for file_name, document_number, results in all_results:
        cells = ["PASS" if passed else "**FAIL**" for _, _, passed, _ in results]
        lines.append(f"| {file_name} ({document_number}) | " + " | ".join(cells) + " |")

    for file_name, document_number, results in all_results:
        lines += ["", f"## {file_name} – {document_number}", ""]
        for check_id, name, passed, details in results:
            status = "PASS" if passed else "**FAIL**"
            lines.append(f"- {status} {check_id} {name}")
            for detail in details:
                lines.append(f"  - {detail}")
    return "\n".join(lines) + "\n"
