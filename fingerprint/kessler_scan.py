import difflib
import re
from datetime import date
from decimal import Decimal

from .ocr_helpers import deskew, find_text_bands, load_scan_image, read_cell, setup_tesseract

# --- Regions in PDF points (measured on INV-06, same layout as the text PDFs) ----------------
HEADER_TOP, HEADER_BOTTOM = 100, 200
HEADER_VALUES_X = (418, 553)            # right block, value column ("RE 2026 10466", "15 10 2026", ...)
ADDRESS_X = (46, 220)                   # left block, buyer address
TABLE_TOP, TABLE_BOTTOM = 260, 560
TABLE_X = (46, 600)
TOTALS_X = (337, 572)
TOTAL_VALUE_X = (500, 572)              # amount column of the totals block
GROSS_VALUE_X = (495, 546)              # "538,98" without the "EUR" after it
DUE_X = (46, 300)

# Item table cells. Wider than the x0 ranges in kessler.py, because a crop must hold the whole number.
SCAN_COLUMNS = {
    "position":       (46, 70),
    "article_number": (76, 152),
    "description":    (152, 330),
    "quantity":       (330, 368),
    "unit":           (368, 398),
    "unit_price":     (395, 455),
    "price_unit":     (455, 478),
    "discount":       (480, 512),
    "line_total":     (512, 572),
    "vat_rate":       (572, 600),
}

KNOWN_UNITS = ["Stk", "m", "psch"]
DIGITS = "0123456789"


# --- Cleaning functions: raw OCR text -> value (or None if it doesn't fit) ------------------
def clean_amount(text):
    """"174 40" / "174.40" / "17440" -> Decimal("174.40"). Kessler amounts always have 2 decimals."""
    digits = re.sub(r"\D", "", text)
    if len(digits) < 3:
        return None
    return Decimal(f"{int(digits[:-2])}.{digits[-2:]}")


def clean_integer(text):
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else None


def clean_date(text):
    """"15 10 2026" / "15.10.2026" -> "2026-10-15" (None if not a real date)."""
    match = re.search(r"(\d{1,2})\D+(\d{1,2})\D+(20\d{2})", text)
    if not match:
        return None
    day, month, year = (int(part) for part in match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def classify_header_value(text):
    """Recognise a header value by its format. Returns (field_name, value) or None."""
    text = text.strip()
    match = re.search(r"(RE|GS)\W*(20\d{2})\W*(\d{5})", text)
    if match:
        return ("document_number", f"{match.group(1)}-{match.group(2)}-{match.group(3)}")
    match = re.search(r"LS\W*(\d{5})", text)
    if match:
        return ("delivery_note_number", f"LS-{match.group(1)}")
    match = re.search(r"^(\d{10})(?!\d)", text)       # "4500093588 vom 06 10 2026" -> order number only
    if match:
        return ("order_reference", match.group(1))
    if re.fullmatch(r"\d{5}", text):
        return ("customer_number", text)
    iso = clean_date(text)
    if iso:
        return ("date", iso)
    return None


def clean_article_number(text):
    """"KI 40118" / "KI-40118" -> "KI-40118" (Kessler article numbers: 2 letters + 5 digits)."""
    match = re.search(r"([A-Z]{2})\W*(\d{5})(?!\d)", text)
    return f"{match.group(1)}-{match.group(2)}" if match else None


def nearest_unit(text):
    """Map an OCR reading to the closest known Kessler unit ("Sm" -> "Stk", "nm" -> "m")."""
    match = difflib.get_close_matches(text.strip(), KNOWN_UNITS, n=1, cutoff=0.3)
    return match[0] if match else None


# --- Reading the page ---------------------------------------------------------------------
class ScanPage:
    """A straightened scan plus a helper to turn PDF points into pixel boxes."""

    def __init__(self, pdf_path):
        setup_tesseract()
        raw_image, self.points_per_pixel = load_scan_image(pdf_path)
        self.image, self.angle = deskew(raw_image)

    def px(self, points):
        return int(round(points / self.points_per_pixel))

    def box(self, x_range, top, bottom, padding=3):
        """Pixel box for columns x_range (points) and rows top..bottom (pixels)."""
        right = min(self.px(x_range[1]), self.image.width)
        return (self.px(x_range[0]), top - padding, right, bottom + padding)

    def text_bands(self, x_range, top_points, bottom_points):
        return find_text_bands(self.image, (self.px(x_range[0]), self.px(top_points),
                                            min(self.px(x_range[1]), self.image.width), self.px(bottom_points)))


def is_text(band, min_height=9):
    return band[1] - band[0] >= min_height


def is_ruled_line(band, region_width):
    return band[1] - band[0] <= 5 and band[2] > region_width * 0.4


def read_header(page, confidence):
    fields = {}
    dates = []
    for top, bottom, _ in page.text_bands(HEADER_VALUES_X, HEADER_TOP, HEADER_BOTTOM):
        if bottom - top < 6:
            continue
        result, votes, total = read_cell(page.image, page.box(HEADER_VALUES_X, top, bottom),
                                         whitelist=DIGITS + ".-REGLSvom", clean=classify_header_value)
        if result is None:
            continue
        name, value = result
        if name == "date":
            dates.append((value, votes, total))
        elif name not in fields:
            fields[name] = value
            confidence[name] = (votes, total)

    # Layout A order: "Datum" comes before "Leistungsdatum"
    if dates:
        fields["document_date"] = dates[0][0]
        confidence["document_date"] = dates[0][1:]
    if len(dates) > 1:
        fields["service_date"] = dates[1][0]
        confidence["service_date"] = dates[1][1:]
    return fields


def read_buyer(page, confidence):
    lines = []
    for top, bottom, _ in page.text_bands(ADDRESS_X, HEADER_TOP, HEADER_BOTTOM):
        if not is_text(band := (top, bottom, 0)):        # tiny sender line is skipped
            continue
        text, votes, total = read_cell(page.image, page.box(ADDRESS_X, top, bottom), language="deu")
        if text and not re.match(r"^(Abt|Abteilung|z\.?\s?Hd)\b", text):   # business rule 9
            lines.append((text, votes, total))

    buyer = {"name": None, "street": None, "postal_code": None, "city": None}
    for index, (text, votes, total) in enumerate(lines):
        match = re.match(r"^(\d{5})\s+(.+)$", text)
        if match and index >= 2:
            buyer.update(name=lines[0][0], street=lines[index - 1][0],
                         postal_code=match.group(1), city=match.group(2))
            confidence["buyer.name"] = lines[0][1:]
            confidence["buyer.street"] = lines[index - 1][1:]
            confidence["buyer.city"] = (votes, total)
            break
    return buyer


def read_items_and_totals(page, confidence):
    region_width = page.px(TABLE_X[1]) - page.px(TABLE_X[0])
    bands = page.text_bands(TABLE_X, TABLE_TOP, TABLE_BOTTOM)

    # Table = text bands between the first two ruled lines (under the header / above the totals)
    line_indexes = [i for i, band in enumerate(bands) if is_ruled_line(band, region_width)]
    if len(line_indexes) < 2:
        raise ValueError("OCR: could not find the item table lines on the scan")
    item_bands = [b for b in bands[line_indexes[0] + 1:line_indexes[1]] if is_text(b)]

    items = []
    for number, (top, bottom, _) in enumerate(item_bands, start=1):
        cell = lambda column: page.box(SCAN_COLUMNS[column], top, bottom)
        item_votes = {}

        def vote(column, **options):
            value, votes, total = read_cell(page.image, cell(column), **options)
            item_votes[column] = (votes, total)
            return value

        discount, discount_votes, discount_total = read_cell(
            page.image, cell("discount"), whitelist=DIGITS, clean=clean_integer)
        item_votes["discount"] = (discount_votes, discount_total)

        items.append({
            "position": vote("position", whitelist=DIGITS, clean=clean_integer) or number,
            "article_number": vote("article_number", whitelist=DIGITS + "ABDIKLU-",
                                   clean=clean_article_number),
            "description": vote("description", language="deu"),
            "quantity": vote("quantity", whitelist=DIGITS + ",.", clean=clean_integer),
            "unit": vote("unit", language="deu", clean=nearest_unit),
            "unit_price": vote("unit_price", whitelist=DIGITS + ",.", clean=clean_amount),
            "price_unit": vote("price_unit", whitelist=DIGITS, clean=clean_integer,
                               is_valid=lambda v: v in (1, 10, 100, 1000)) or 1,
            "discount_percent": discount,
            "line_total": vote("line_total", whitelist=DIGITS + ",.", clean=clean_amount),
            "vat_rate": vote("vat_rate", whitelist=DIGITS, clean=clean_integer,
                             is_valid=lambda v: v in (19, 7)),
        })
        confidence[f"line {number}"] = item_votes

    # Totals: text bands right after the second ruled line, in Kessler's order:
    #   Nettobetrag per rate ..., zzgl. USt per rate ..., Rechnungsbetrag
    totals_bands = [b for b in page.text_bands(TOTALS_X, page.points_per_pixel * bands[line_indexes[1]][1],
                                               TABLE_BOTTOM) if is_text(b)]
    rates = sorted({item["vat_rate"] for item in items if item["vat_rate"]}, reverse=True)
    expected_bands = 2 * len(rates) + 1
    if len(totals_bands) < expected_bands:
        raise ValueError(f"OCR: expected {expected_bands} total lines, found {len(totals_bands)}")
    totals_bands = totals_bands[:expected_bands]

    amounts = []
    for index, (top, bottom, _) in enumerate(totals_bands):
        x_range = GROSS_VALUE_X if index == expected_bands - 1 else TOTAL_VALUE_X
        value, votes, total = read_cell(page.image, page.box(x_range, top, bottom),
                                        whitelist=DIGITS + ",.", clean=clean_amount)
        amounts.append(value)
        confidence[f"totals line {index + 1}"] = (votes, total)

    net_by_vat_rate = {str(rate): amounts[i] for i, rate in enumerate(rates)}
    vat_by_vat_rate = {str(rate): amounts[len(rates) + i] for i, rate in enumerate(rates)}
    totals = {
        "net_by_vat_rate": net_by_vat_rate,
        "vat_by_vat_rate": vat_by_vat_rate,
        "net_total": sum((v for v in net_by_vat_rate.values() if v is not None), Decimal("0")),
        "vat_total": sum((v for v in vat_by_vat_rate.values() if v is not None), Decimal("0")),
        "gross_total": amounts[-1],
    }

    # Due date: first text line below the totals, left side ("Zahlbar bis 14 11 2026 ohne Abzug")
    last_total_bottom = totals_bands[-1][1]
    due_date = None
    for top, bottom, _ in page.text_bands(DUE_X, page.points_per_pixel * last_total_bottom, TABLE_BOTTOM + 60):
        if is_text(band := (top, bottom, 0)):
            due_date, votes, total = read_cell(page.image, page.box(DUE_X, top, bottom),
                                               language="deu", clean=clean_date)
            confidence["due_date"] = (votes, total)
            break
    return items, totals, due_date


LOGO_X = (40, 140)          # big "KESSLER" logo, top left
LOGO_TOP, LOGO_BOTTOM = 30, 80


def check_kessler_logo(page):
    """Make sure this scan really is from Kessler before using Kessler's layout (and its VAT ID)."""
    for top, bottom, _ in page.text_bands(LOGO_X, LOGO_TOP, LOGO_BOTTOM):
        logo, _, _ = read_cell(page.image, page.box(LOGO_X, top, bottom),
                               whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        if logo == "KESSLER":
            return
    raise ValueError("OCR: 'KESSLER' logo not found – this scan is not a Kessler document")


def extract_layout_a_scan(pdf_path):
    """Read a scanned Kessler Layout A invoice. Returns (result, confidence).

    confidence: {field: (votes, readings)} – how many of the OCR readings agreed. Low = don't trust.
    """
    page = ScanPage(pdf_path)
    check_kessler_logo(page)
    confidence = {"deskew_angle": page.angle}

    header = read_header(page, confidence)
    buyer = read_buyer(page, confidence)
    items, totals, due_date = read_items_and_totals(page, confidence)
    document_number = header.get("document_number") or ""

    result = {
        "document_type": "credit_note" if document_number.startswith("GS") else "invoice",
        "document_number": document_number,
        "document_date": header.get("document_date"),
        "service_date": header.get("service_date"),
        "due_date": due_date,
        "currency": "EUR",
        # The footer text is too small on this scan for OCR. check_kessler_logo() confirmed the
        # supplier, so name and VAT ID come from the fingerprint, NOT from OCR (see README).
        "supplier": {"name": "Kessler Industrietechnik GmbH", "vat_id": "DE287364519"},
        "buyer": {**buyer, "customer_number": header.get("customer_number")},
        "order_reference": header.get("order_reference"),
        "delivery_note_number": header.get("delivery_note_number"),
        "referenced_invoice": None,
        "line_items": items,
        "totals": totals,
        "cash_discount": None,          # no Skonto line printed on INV-06
    }
    return result, confidence
