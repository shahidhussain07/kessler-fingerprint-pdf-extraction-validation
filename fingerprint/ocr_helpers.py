"""Generic OCR helpers for scanned (image-only) PDFs. Nothing here knows about Kessler.

Idea: one OCR pass over a whole page is too noisy for this scan quality. So we:
  1. straighten the page (deskew),
  2. find the text rows with a projection profile (count dark pixels per pixel row),
  3. cut out single cells and OCR each cell several times with slightly different image clean-up,
  4. keep the reading that appears most often AND looks like the expected format (a "vote").
"""
import os
import shutil
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pymupdf
import pytesseract
from PIL import Image, ImageFilter, ImageOps

WINDOWS_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def setup_tesseract():
    """Find tesseract.exe: TESSERACT_CMD env variable, then PATH, then the default Windows install folder."""
    if os.environ.get("TESSERACT_CMD"):
        pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]
    elif shutil.which("tesseract") is None and os.path.exists(WINDOWS_TESSERACT):
        pytesseract.pytesseract.tesseract_cmd = WINDOWS_TESSERACT


def load_scan_image(pdf_path, dpi=300):
    """Return (grayscale image of page 1, points_per_pixel).

    If the page is one embedded image (a typical scan) we take that image as it is (no quality loss),
    otherwise we render the page at `dpi`. points_per_pixel converts pixel positions back to PDF points.
    """
    with pymupdf.open(pdf_path) as pdf:
        page = pdf[0]
        images = page.get_images(full=True)
        if len(images) == 1:
            pixmap = pymupdf.Pixmap(pdf, images[0][0])
        else:
            pixmap = page.get_pixmap(dpi=dpi)
        if pixmap.n > 1 or pixmap.alpha:                 # colour or alpha -> plain grayscale
            pixmap = pymupdf.Pixmap(pymupdf.csGRAY, pixmap)
        image = Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples)
        points_per_pixel = page.rect.width / pixmap.width
    return image, points_per_pixel


def deskew(image, max_angle=3.0, step=0.1):
    """Rotate the page so text lines are horizontal. Returns (straight_image, angle).

    For each test angle we rotate and count dark pixels per pixel row. When lines are horizontal,
    rows switch sharply between "full of text" and "empty" -> the row counts change a lot.
    The angle with the biggest change wins.
    """
    small = image.resize((image.width // 2, image.height // 2))

    def sharpness(angle):
        rotated = small.rotate(angle, resample=Image.BICUBIC, fillcolor=255)
        dark_per_row = (255 - np.asarray(rotated, dtype=float)).sum(axis=1)
        return np.var(np.diff(dark_per_row))

    steps = int(max_angle / step)
    best_angle = max((i * step for i in range(-steps, steps + 1)), key=sharpness)
    return image.rotate(best_angle, resample=Image.BICUBIC, fillcolor=255), round(best_angle, 1)


def find_text_bands(image, box):
    """Find horizontal bands that contain ink inside box=(left, top, right, bottom) in pixels.

    Returns [(top, bottom, widest_ink), ...]. widest_ink = most dark pixels in one row of the band:
    a thin band with very wide ink is a ruled line, not text.
    """
    left, top, right, bottom = box
    dark = np.asarray(image.crop(box)) < 128
    ink_per_row = dark.sum(axis=1)

    bands = []
    start = None
    for row, ink in enumerate(list(ink_per_row) + [0]):        # extra 0 closes the last band
        if ink and start is None:
            start = row
        elif not ink and start is not None:
            bands.append((top + start, top + row, int(ink_per_row[start:row].max())))
            start = None
    return bands


def write_confidence_report(confidence, path):
    """Save {field: (votes, readings)} as a Markdown table. Nested dicts (one per item line) are flattened."""
    rows = []
    for field, value in confidence.items():
        if isinstance(value, dict):
            rows += [(f"{field} / {name}", votes) for name, votes in value.items()]
        else:
            rows.append((field, value))

    lines = ["# OCR confidence", "",
             "How many of the 8 OCR readings of each cell agreed on the chosen value.",
             "8/8 or 1/1 (blank cell) = all agree. Below 5/8 = do not trust without a look at the scan.", "",
             "| Field | Agreeing readings | Trust |", "|---|---|---|"]
    for field, value in rows:
        if isinstance(value, tuple):
            votes, total = value
            trust = "high" if votes / total >= 0.75 else "medium" if votes / total >= 0.5 else "LOW"
            lines.append(f"| {field} | {votes}/{total} | {trust} |")
        else:
            lines.append(f"| {field} | {value} | |")
    with open(path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")


def cell_is_empty(cell, min_dark_pixels=8):
    """True if the cell has (almost) no dark pixels – a few specks of scan noise don't count."""
    return int((np.asarray(cell) < 128).sum()) < min_dark_pixels


def _ocr_variants(cell, whitelist, language):
    """OCR one cell image with 8 slightly different clean-ups (2 sizes x 2 stroke widths x 2 blurs).

    Returns 8 strings.
    """
    config = "--psm 7"                          # psm 7 = "the image is a single text line"
    if whitelist:
        # No quotes and no spaces here: on Windows pytesseract splits the config with
        # shlex(posix=False), and a quoted value with a space fails with "No closing quotation".
        # Tesseract still outputs spaces between words, they are not filtered by the whitelist.
        if " " in whitelist or '"' in whitelist:
            raise ValueError(f"OCR whitelist must not contain spaces or quotes: {whitelist!r}")
        config += f" -c tessedit_char_whitelist={whitelist}"

    jobs = []
    for scale in (3, 4):                       # enlarge: tesseract likes letters ~30 px high
        for thicken in (False, True):          # the scan breaks thin strokes ("9" falls apart)
            for blur in (1.0, 1.5):            # smooth the jagged 1-bit edges
                big = cell.resize((cell.width * scale, cell.height * scale), Image.LANCZOS)
                if thicken:
                    big = big.filter(ImageFilter.MinFilter(3))   # dark strokes grow by 1 pixel
                big = big.filter(ImageFilter.GaussianBlur(blur * scale / 3))
                big = big.point(lambda value: 255 if value > 150 else 0)
                jobs.append(ImageOps.expand(big, 20, 255))     # white border helps tesseract

    def run(img):
        return pytesseract.image_to_string(img, lang=language, config=config).strip()

    with ThreadPoolExecutor(max_workers=4) as pool:    # tesseract runs as a separate program -> threads help
        return list(pool.map(run, jobs))


def read_cell(image, box, whitelist=None, language="deu", is_valid=None, clean=None):
    """OCR the cell `box` several times and vote.

    clean(text)    -> turns a raw reading into the final value (or None if it can't)
    is_valid(value)-> True if the value has the expected format; invalid readings get no vote
    Returns (value, votes, total_readings). value is None if no reading was usable.
    """
    cell = image.crop(box)
    if cell_is_empty(cell):
        # Tesseract "sees" digits in blank cells (we got "2" for every empty discount cell).
        # A blank cell is a sure result: empty, all readings agree.
        return None, 1, 1
    readings = _ocr_variants(cell, whitelist, language)
    candidates = []
    for text in readings:
        value = clean(text) if clean else (text or None)
        if value is not None and (is_valid is None or is_valid(value)):
            candidates.append(value)
    if not candidates:
        return None, 0, len(readings)
    value, votes = Counter(candidates).most_common(1)[0]
    return value, votes, len(readings)
