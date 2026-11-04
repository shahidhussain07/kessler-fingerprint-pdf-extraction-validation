"""Kessler Industrietechnik GmbH – supplier fingerprint.

Everything in this file is specific to how Kessler prints its documents.
Generic tools (number/date parsing, reading PDF lines) come from helpers.py.
"""
import re
from decimal import Decimal

from .helpers import add_days, clean_vat_id, parse_date, parse_number, read_pdf_lines, words_to_text

# ---------------------------------------------------------------------------
# Layout A (INV-01 … INV-04): positions measured with debug_dump.py
# ---------------------------------------------------------------------------
# Header area of page 1 has two columns:
#   left  (x0 < 340)  -> sender line + buyer address
#   right (x0 >= 340) -> "label  value" pairs (Rechnungs-Nr., Datum, ...)
HEADER_SPLIT_X = 340


def split_line_at_x(line, split_x):
    """Return (left_text, right_text) of one line, cut at position split_x."""
    left_words = [w for w in line["words"] if w["x0"] < split_x]
    right_words = [w for w in line["words"] if w["x0"] >= split_x]
    return words_to_text(left_words), words_to_text(right_words)


def find_table_header_top(lines, first_word="Pos."):
    """
        Layout A header starts with "Pos." ("Pos. Art.-Nr. Bezeichnung ..."),
        Layout B header starts with "Pos"  ("Pos Menge Einh. Artikel ...").
    """
    for line in lines:
        if line["words"][0]["text"] == first_word:
            return line["top"]
    raise ValueError(f"Table header starting with {first_word!r} not found")


def read_header_fields(right_texts):
    """Read the right-hand "label value" block into a dict of raw strings.

    right_texts: list like ["Rechnungs-Nr. RE-2026-10418", "Datum 06.10.2026", ...]
    """
    patterns = {
        "invoice_number":   r"^Rechnungs-Nr\.\s+(\S+)",
        "credit_number":    r"^Gutschrift-Nr\.\s+(\S+)",
        "document_date":    r"^Datum\s+(\d{2}\.\d{2}\.\d{4})",
        "customer_number":  r"^Kunden-Nr\.\s+(\S+)",
        "order_reference":  r"^Ihre Bestellung\s+(\S+)",          # stops before "vom <date>"
        "delivery_note":    r"^Lieferschein-Nr\.\s+(\S+)",
        "service_date":     r"^Leistungsdatum\s+(\d{2}\.\d{2}\.\d{4})",
        "referenced_invoice": r"^Bezug\s+Rechnung\s+(\S+)",       # credit notes only
    }
    found = {}
    for text in right_texts:
        for field_name, pattern in patterns.items():
            match = re.search(pattern, text)
            if match and field_name not in found:
                found[field_name] = match.group(1)
    return found


def read_buyer_address(left_texts):
    """Read the buyer block, which sits between the sender line and the title.

    Example input:
        ["Rheinwerk Anlagenbau AG", "Abt. Kreditorenbuchhaltung", "Hafenstraße 88", "47119 Duisburg"]
    """
    # Department / "attention of" lines are not part of the company name (business rule 9)
    skip_starts = ("Abt.", "Abteilung", "z. Hd.", "z.Hd.", "zu Händen", "Attn")
    address_lines = [t for t in left_texts if t and not t.startswith(skip_starts)]

    # The city line is "5 digits + city name"
    city_index = None
    for index, text in enumerate(address_lines):
        if re.fullmatch(r"\d{5}\s+.+", text):
            city_index = index
            break
    if city_index is None or city_index < 2:
        raise ValueError(f"Could not read buyer address from: {address_lines}")

    postal_code, city = address_lines[city_index].split(maxsplit=1)
    return {
        "name": address_lines[0],
        "street": address_lines[city_index - 1],   # street is always right above the city
        "postal_code": postal_code,
        "city": city,
    }


def find_supplier(all_pages):
    """Supplier name from the sender line, VAT ID from the footer (printed on every page)."""
    name = None
    vat_id = None
    for lines in all_pages:
        for line in lines:
            text = words_to_text(line["words"])
            if name is None and "·" in text and text.startswith("Kessler"):
                name = text.split("·")[0].strip()          # "Kessler Industrietechnik GmbH"
            match = re.search(r"USt-IdNr\.\s*(DE[\d ]+)", text)
            if vat_id is None and match:
                vat_id = clean_vat_id(match.group(1))
    return {"name": name, "vat_id": vat_id}


def read_header_layout_a(all_pages):
    """Read all header fields of a Layout A document (only page 1 has the full header)."""
    first_page = all_pages[0]
    table_top = find_table_header_top(first_page)

    left_texts = []
    right_texts = []
    sender_line_seen = False
    for line in first_page:
        if line["top"] >= table_top:
            break
        left, right = split_line_at_x(line, HEADER_SPLIT_X)
        if right:
            right_texts.append(right)
        if "·" in left:                       # sender line: buyer address starts after it
            sender_line_seen = True
            continue
        if sender_line_seen and left in ("RECHNUNG", "GUTSCHRIFT"):
            sender_line_seen = False          # title: buyer address has ended
            continue
        if sender_line_seen and left:
            left_texts.append(left)

    fields = read_header_fields(right_texts)
    is_credit_note = "credit_number" in fields

    buyer = read_buyer_address(left_texts)
    buyer["customer_number"] = fields.get("customer_number")

    return {
        "document_type": "credit_note" if is_credit_note else "invoice",
        "document_number": fields["credit_number"] if is_credit_note else fields["invoice_number"],
        "document_date": parse_date(fields["document_date"]),
        "service_date": parse_date(fields.get("service_date")),
        "currency": "EUR",
        "supplier": find_supplier(all_pages),
        "buyer": buyer,
        "order_reference": fields.get("order_reference"),
        "delivery_note_number": fields.get("delivery_note"),
        "referenced_invoice": fields.get("referenced_invoice") if is_credit_note else None,
    }


# ---------------------------------------------------------------------------
# Layout A line items
# ---------------------------------------------------------------------------
# Column ranges by the word's left edge (x0), measured with debug_dump.py.
# Numbers are right-aligned, so their x0 moves with their width -> use ranges, not exact values.
#   (column name, from x, to x)
TABLE_COLUMNS_A = [
    ("position",       0,   80),
    ("article_number", 80,  155),
    ("description",    155, 335),
    ("quantity",       335, 368),
    ("unit",           368, 400),
    ("unit_price",     400, 452),
    ("price_unit",     452, 475),
    ("discount",       475, 512),
    ("line_total",     512, 570),
    ("vat_rate",       570, 600),
]


def split_line_into_columns(line, columns):
    """Put every word of a line into its column. Returns {"position": "1", "description": "Rillen… 6205-2RS", ...}."""
    cells = {}
    for word in line["words"]:
        for column_name, from_x, to_x in columns:
            if from_x <= word["x0"] < to_x:
                cells.setdefault(column_name, []).append(word["text"])
                break
    return {name: " ".join(texts) for name, texts in cells.items()}


def make_line_item(cells):
    """Turn the text cells of one item row into an item dict (numbers as Decimal)."""
    return {
        "position": int(cells["position"]),                       # "010" -> 10
        "article_number": cells["article_number"],
        "description": cells["description"],
        "quantity": parse_number(cells["quantity"]),
        "unit": cells["unit"],
        "unit_price": parse_number(cells["unit_price"]),
        "price_unit": parse_number(cells.get("price_unit", "1")),   # 1 if not printed
        "discount_percent": parse_number(cells.get("discount")),    # None if not printed
        "line_total": parse_number(cells["line_total"]),
        "vat_rate": int(parse_number(cells["vat_rate"])),
    }


def read_line_items_layout_a(all_pages):
    """Read item rows from every page.

    On each page we look at lines between the table header ("Pos. ...") and the end of the table.
    """
    items = []
    for page_lines in all_pages:
        table_top = find_table_header_top(page_lines)
        for line in page_lines:
            if line["top"] <= table_top:
                continue

            text = words_to_text(line["words"])
            first_word = line["words"][0]

            if text.startswith("Übertrag von"):
                continue
            if text.startswith("Übertrag") or text.startswith("Nettobetrag"):
                break

            cells = split_line_into_columns(line, TABLE_COLUMNS_A)

            if first_word["x0"] < 80 and first_word["text"].isdigit():
                items.append(make_line_item(cells))
            elif set(cells) == {"description"} and items:
                items[-1]["description"] += " " + cells["description"]   # business rule 5
            else:
                raise ValueError(f"Unknown row in item table: {text!r}")
    return items


# ---------------------------------------------------------------------------
# Layout A totals, due date and Skonto (printed below the item table on the last page)
# ---------------------------------------------------------------------------
# One pattern per kind of line. NUMBER matches German amounts with a minus at the end
# ("400,05-", Layout A credit notes) or at the start ("-13,97", Layout B discount rows).

NUMBER = r"-?[\d.,]+-?"
NET_LINE = re.compile(rf"^Nettobetrag\s+(\d+)\s*%\s*USt\s+({NUMBER})$")
VAT_LINE = re.compile(rf"^zzgl\.\s+(\d+)\s*%\s*USt\s+auf\s+{NUMBER}\s+({NUMBER})$")
GROSS_LINE = re.compile(rf"^(?:Rechnungsbetrag|Gutschriftsbetrag)\s+({NUMBER})\s+EUR")
DUE_LINE = re.compile(r"^Zahlbar bis (\d{2}\.\d{2}\.\d{4})")
SKONTO_BY_DATE = re.compile(rf"bis (\d{{2}}\.\d{{2}}\.\d{{4}}) abzüglich ({NUMBER}) % Skonto \(= ({NUMBER}) EUR\)")
SKONTO_BY_DAYS = re.compile(rf"innerhalb von (\d+) Tagen ab Rechnungsdatum ({NUMBER}) % Skonto \(= ({NUMBER}) EUR\)")


def read_totals_layout_a(all_pages, document_date):
    """Read totals, due date and Skonto. Returns (totals, due_date, cash_discount).

    document_date ("YYYY-MM-DD") is needed when Skonto is given as "within N days".
    """
    net_by_vat_rate = {}
    vat_by_vat_rate = {}
    gross_total = None
    due_date = None
    cash_discount = None

    last_page = all_pages[-1]
    for line in last_page:
        text = words_to_text(line["words"])

        match = NET_LINE.search(text)
        if match:
            net_by_vat_rate[match.group(1)] = parse_number(match.group(2))
            continue

        match = VAT_LINE.search(text)
        if match:
            vat_by_vat_rate[match.group(1)] = parse_number(match.group(2))
            continue

        match = GROSS_LINE.search(text)
        if match:
            gross_total = parse_number(match.group(1))
            continue

        match = DUE_LINE.search(text)
        if match:
            due_date = parse_date(match.group(1))
            continue

        match = SKONTO_BY_DATE.search(text)
        if match:
            cash_discount = {
                "percent": parse_number(match.group(2)),
                "until": parse_date(match.group(1)),
                "amount": parse_number(match.group(3)),
            }
            continue

        match = SKONTO_BY_DAYS.search(text)
        if match:
            cash_discount = {
                "percent": parse_number(match.group(2)),
                "until": add_days(document_date, int(match.group(1))),   # derived, not printed
                "amount": parse_number(match.group(3)),
            }

    if not net_by_vat_rate or gross_total is None:
        raise ValueError("Totals block not found on the last page")

    # Kessler prints no single "net total" / "VAT total" line -> add up the printed per-rate values.
    totals = {
        "net_by_vat_rate": net_by_vat_rate,
        "vat_by_vat_rate": vat_by_vat_rate,
        "net_total": sum(net_by_vat_rate.values(), Decimal("0")),
        "vat_total": sum(vat_by_vat_rate.values(), Decimal("0")),
        "gross_total": gross_total,
    }
    return totals, due_date, cash_discount


# ---------------------------------------------------------------------------
# Put everything together
# ---------------------------------------------------------------------------
def extract_layout_a(all_pages):
    """Read a Layout A document. Returns the full result dict (numbers still Decimal)."""
    header = read_header_layout_a(all_pages)
    items = read_line_items_layout_a(all_pages)
    totals, due_date, cash_discount = read_totals_layout_a(all_pages, header["document_date"])

    return {
        "document_type": header["document_type"],
        "document_number": header["document_number"],
        "document_date": header["document_date"],
        "service_date": header["service_date"],
        "due_date": due_date,
        "currency": header["currency"],
        "supplier": header["supplier"],
        "buyer": header["buyer"],
        "order_reference": header["order_reference"],
        "delivery_note_number": header["delivery_note_number"],
        "referenced_invoice": header["referenced_invoice"],
        "line_items": items,
        "totals": totals,
        "cash_discount": cash_discount,
    }


# ===========================================================================
# Layout B (INV-05, new format since 01.10.2026)
# ===========================================================================
# Page 1 header is mirrored compared to Layout A:
#   left  (x0 < 330)  -> "label  value" pairs (Rechnung Nr., Rechnungsdatum, ...)
#   right (x0 >= 330) -> logo, sender line + buyer address
HEADER_SPLIT_X_B = 330


def read_header_fields_b(left_texts):
    """Read the left-hand "label value" block of Layout B into a dict of raw strings."""
    patterns = {
        "invoice_number":  r"^Rechnung Nr\.\s+(\S+)",
        "credit_number":   r"^Gutschrift Nr\.\s+(\S+)",      # assumption: not seen in samples yet
        "document_date":   r"^Rechnungsdatum\s+(.+)$",        # "19. Oktober 2026"
        "service_date":    r"^Lieferdatum\s+(.+)$",
        "customer_number": r"^Kundennummer\s+(\S+)",
        "order_reference": r"^Bestellnummer\s+(\S+)",
        "delivery_note":   r"^Lieferschein\s+(\S+)",
    }
    found = {}
    for text in left_texts:
        for field_name, pattern in patterns.items():
            match = re.search(pattern, text)
            if match and field_name not in found:
                found[field_name] = match.group(1)
    return found


def read_header_layout_b(all_pages):
    """Read all header fields of a Layout B document (page 1)."""
    first_page = all_pages[0]
    table_top = find_table_header_top(first_page, first_word="Pos")

    left_texts = []
    right_texts = []
    sender_line_seen = False
    for line in first_page:
        if line["top"] >= table_top:
            break
        left, right = split_line_at_x(line, HEADER_SPLIT_X_B)
        if left:
            left_texts.append(left)
        if right.startswith("Kessler") and "·" in right:   # sender line: buyer address starts after it
            sender_line_seen = True
            continue
        if sender_line_seen and right:
            right_texts.append(right)

    fields = read_header_fields_b(left_texts)
    is_credit_note = "credit_number" in fields

    buyer = read_buyer_address(right_texts)          # same helper as Layout A, "z. Hd." is skipped
    buyer["customer_number"] = fields.get("customer_number")

    return {
        "document_type": "credit_note" if is_credit_note else "invoice",
        "document_number": fields["credit_number"] if is_credit_note else fields["invoice_number"],
        "document_date": parse_date(fields["document_date"]),
        "service_date": parse_date(fields.get("service_date")),
        "currency": "EUR",
        "supplier": find_supplier(all_pages),        # footer is identical in both layouts
        "buyer": buyer,
        "order_reference": fields.get("order_reference"),
        "delivery_note_number": fields.get("delivery_note"),
        "referenced_invoice": None,                  # no credit-note sample in Layout B yet
    }


# Item table columns of Layout B. No PE column, "€" signs sit inside the price and amount columns.
TABLE_COLUMNS_B = [
    ("position",       0,   80),
    ("quantity",       80,  105),
    ("unit",           105, 140),
    ("article_number", 140, 205),
    ("description",    205, 420),
    ("unit_price",     420, 470),
    ("vat_rate",       470, 510),
    ("line_total",     510, 600),
]

# "abzgl. Sonderrabatt 3 % auf 465,60 € -13,97 €"  -> 3 %, base 465,60, discount amount -13,97
DISCOUNT_ROW_B = re.compile(rf"^abzgl\..*?({NUMBER})\s*%\s+auf\s+({NUMBER})\s*€\s+({NUMBER})\s*€$")


def read_line_items_layout_b(all_pages):
    """Read item rows of Layout B.

    Same idea as Layout A, plus one new row type:
      "abzgl. Sonderrabatt 3 % auf 465,60 € -13,97 €" -> discount for the item above (business rule 7):
          discount_percent = 3, line_total = 465,60 + (-13,97) = 451,63. It is NOT a separate item.
    """
    items = []
    for page_lines in all_pages:
        table_top = find_table_header_top(page_lines, first_word="Pos")
        for line in page_lines:
            if line["top"] <= table_top:
                continue

            text = words_to_text(line["words"])
            first_word = line["words"][0]

            # Carry-over rows: not seen in Layout B yet, handled like Layout A to be safe
            if text.startswith("Übertrag von"):
                continue
            if text.startswith("Übertrag") or text.startswith("Summe netto"):
                break

            discount = DISCOUNT_ROW_B.search(text)
            if discount and items:
                item = items[-1]
                item["discount_percent"] = parse_number(discount.group(1))
                item["line_total"] = item["line_total"] + parse_number(discount.group(3))
                continue

            cells = split_line_into_columns(line, TABLE_COLUMNS_B)

            if first_word["x0"] < 80 and first_word["text"].isdigit():
                cells["price_unit"] = "1"                    # Layout B has no PE column
                items.append(make_line_item(cells))
            elif set(cells) == {"description"} and items:
                items[-1]["description"] += " " + cells["description"]
            else:
                raise ValueError(f"Unknown row in item table: {text!r}")
    return items


NET_TOTAL_B = re.compile(rf"^Summe netto\s+({NUMBER})\s*€$")          # "Summe netto 975,13 €"
VAT_LINE_B = re.compile(rf"^MwSt\s+(\d+)\s*%\s+({NUMBER})\s*€$")      # "MwSt 19% 175,81 €"
GROSS_LINE_B = re.compile(rf"^Gesamtbetrag\s+({NUMBER})\s*€$")        # "Gesamtbetrag 1.154,43 €"
DUE_LINE_B = re.compile(r"^Zahlungsziel:.*\(bis (.+?)\)")             # "... (bis 18. November 2026)."


def read_totals_layout_b(all_pages, items):
    """Read totals and due date of Layout B. Returns (totals, due_date, cash_discount).

    Layout B prints no net amount per VAT rate, only "Summe netto".
    So net_by_vat_rate is DERIVED by adding up the line totals per rate 
    """
    net_total = None
    vat_by_vat_rate = {}
    gross_total = None
    due_date = None

    for line in all_pages[-1]:
        text = words_to_text(line["words"])

        match = NET_TOTAL_B.search(text)
        if match:
            net_total = parse_number(match.group(1))
            continue
        match = VAT_LINE_B.search(text)
        if match:
            vat_by_vat_rate[match.group(1)] = parse_number(match.group(2))
            continue
        match = GROSS_LINE_B.search(text)
        if match:
            gross_total = parse_number(match.group(1))
            continue
        match = DUE_LINE_B.search(text)
        if match:
            due_date = parse_date(match.group(1))

    if net_total is None or gross_total is None:
        raise ValueError("Totals block not found on the last page")

    net_by_vat_rate = {}
    for item in items:
        rate = str(item["vat_rate"])
        net_by_vat_rate[rate] = net_by_vat_rate.get(rate, Decimal("0")) + item["line_total"]

    totals = {
        "net_by_vat_rate": net_by_vat_rate,
        "vat_by_vat_rate": vat_by_vat_rate,
        "net_total": net_total,                                    # printed
        "vat_total": sum(vat_by_vat_rate.values(), Decimal("0")),  # derived from printed per-rate VAT
        "gross_total": gross_total,
    }
    # "Kein Skontoabzug." -> no cash discount. A Skonto line in Layout B has not been seen yet.
    return totals, due_date, None


def extract_layout_b(all_pages):
    """Read a Layout B document. Returns the full result dict (numbers still Decimal)."""
    header = read_header_layout_b(all_pages)
    items = read_line_items_layout_b(all_pages)
    totals, due_date, cash_discount = read_totals_layout_b(all_pages, items)

    return {
        "document_type": header["document_type"],
        "document_number": header["document_number"],
        "document_date": header["document_date"],
        "service_date": header["service_date"],
        "due_date": due_date,
        "currency": header["currency"],
        "supplier": header["supplier"],
        "buyer": header["buyer"],
        "order_reference": header["order_reference"],
        "delivery_note_number": header["delivery_note_number"],
        "referenced_invoice": header["referenced_invoice"],
        "line_items": items,
        "totals": totals,
        "cash_discount": cash_discount,
    }


# ===========================================================================
# Entry point
# ===========================================================================
def detect_layout(all_pages):
    """Decide which Kessler layout this is, by labels printed on page 1."""
    page_1_text = " ".join(words_to_text(line["words"]) for line in all_pages[0])
    if "Rechnungs-Nr." in page_1_text or "Gutschrift-Nr." in page_1_text:
        return "A"
    if "Rechnungsdatum" in page_1_text and ("Rechnung Nr." in page_1_text or "Gutschrift Nr." in page_1_text):
        return "B"
    raise ValueError("Unknown Kessler layout (neither A nor B labels found on page 1)")


def extract_kessler(pdf_path):
    """Main entry point for a Kessler PDF: read it, pick the right layout.

    Returns (result, layout, ocr_confidence):
      layout          "A", "B" or "A-scan"
      ocr_confidence  {field: (votes, readings)} for scans, None for text PDFs
    """
    all_pages = read_pdf_lines(pdf_path)

    if not any(page_lines for page_lines in all_pages):
        # No text layer at all -> scanned document -> OCR (bonus, INV-06).
        # Imported here so the OCR libraries are only needed when a scan shows up.
        from .kessler_scan import extract_layout_a_scan
        result, confidence = extract_layout_a_scan(pdf_path)
        return result, "A-scan", confidence

    layout = detect_layout(all_pages)
    if layout == "A":
        return extract_layout_a(all_pages), "A", None
    return extract_layout_b(all_pages), "B", None
