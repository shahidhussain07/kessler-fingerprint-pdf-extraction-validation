"""Generic helpers that work for ANY supplier.

Nothing in this file knows about Kessler. Supplier-specific logic lives elsewhere.
"""
import json
import re
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

GERMAN_MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12,
}


def parse_number(text):
    """Turn a German-formatted number into a Decimal.

    "1.234,56" -> 1234.56     "225,80-" -> -225.80    "-13,97 €" -> -13.97
    "12,5"     -> 12.5        "1.000"   -> 1000       "19%"      -> 19
    """
    if text is None:
        return None
    cleaned = text.strip().replace("€", "").replace("%", "").replace(" ", "")
    if cleaned == "":
        return None

    is_negative = False
    if cleaned.endswith("-"):          # Kessler credit notes: "225,80-"
        is_negative = True
        cleaned = cleaned[:-1]
    if cleaned.startswith("-"):        # normal minus: "-13,97"
        is_negative = True
        cleaned = cleaned[1:]

    # German format: "." groups thousands, "," is the decimal separator
    cleaned = cleaned.replace(".", "").replace(",", ".")

    if not re.fullmatch(r"\d+(\.\d+)?", cleaned):
        raise ValueError(f"Not a German number: {text!r}")

    number = Decimal(cleaned)
    return -number if is_negative else number


def parse_date(text):
    """Turn a German date into "YYYY-MM-DD".

    "06.10.2026" -> "2026-10-06"      "19. Oktober 2026" -> "2026-10-19"
    """
    if text is None:
        return None
    text = text.strip()

    match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if match:
        day, month, year = match.groups()
        return date(int(year), int(month), int(day)).isoformat()

    match = re.search(r"(\d{1,2})\.\s*([A-Za-zÄÖÜäöü]+)\s+(\d{4})", text)
    if match:
        day, month_name, year = match.groups()
        month = GERMAN_MONTHS.get(month_name.lower())
        if month is None:
            raise ValueError(f"Unknown month name: {month_name!r}")
        return date(int(year), month, int(day)).isoformat()

    raise ValueError(f"Not a German date: {text!r}")


def add_days(iso_date, days):
    """"2026-10-14" + 7 days -> "2026-10-21". Used when Skonto says "within 7 days"."""
    return (date.fromisoformat(iso_date) + timedelta(days=days)).isoformat()


def clean_vat_id(text):
    """"DE 287 364 519" -> "DE287364519"."""
    return re.sub(r"\s+", "", text).upper()


def to_json_number(value):
    """Decimal -> float for the JSON file (Decimal("202.80") -> 202.8). None stays None."""
    return None if value is None else float(value)


def decimals_to_numbers(data):
    """Walk through dicts/lists and turn every Decimal into a float, ready for JSON."""
    if isinstance(data, dict):
        return {key: decimals_to_numbers(value) for key, value in data.items()}
    if isinstance(data, list):
        return [decimals_to_numbers(value) for value in data]
    if isinstance(data, Decimal):
        return to_json_number(data)
    return data


def read_pdf_lines(pdf_path):
    """Read a text PDF and return its visual lines, page by page.

    Result: [page1_lines, page2_lines, ...]
    Each line is a dict: {"top": 313.0, "words": [{"text": "KI-40112", "x0": 85.0}, ...]}
    Words in a line are sorted left to right.
    """
    import pdfplumber  # imported here so the other helpers work without it

    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # x_tolerance=1.5: the default (3) glues columns, e.g. "14,60" + "100" -> "14,60100"
            words = page.extract_words(x_tolerance=1.5)
            pages.append(group_words_into_lines(words))
    return pages


def group_words_into_lines(words, tolerance=3):
    """Put words whose 'top' positions are within `tolerance` points into the same line."""
    lines = []
    for word in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        simple_word = {"text": word["text"], "x0": word["x0"]}
        if lines and abs(lines[-1]["top"] - word["top"]) <= tolerance:
            lines[-1]["words"].append(simple_word)
        else:
            lines.append({"top": word["top"], "words": [simple_word]})
    for line in lines:
        line["words"].sort(key=lambda w: w["x0"])
    return lines


def words_to_text(words):
    """[{"text": "Ihre"}, {"text": "Bestellung"}] -> "Ihre Bestellung"."""
    return " ".join(word["text"] for word in words)


def save_json(data, path):
    """Write a dict to a JSON file (UTF-8, keeps umlauts readable)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
