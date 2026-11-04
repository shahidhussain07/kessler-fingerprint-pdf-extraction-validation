"""Dump text, lines and word positions of PDFs for layout exploration."""
import sys
from pathlib import Path

import pdfplumber

OUT_DIR = Path(__file__).resolve().parent.parent / "debug"


def group_lines(words, tol=3):
    """Group words into visual lines by their 'top' coordinate."""
    lines = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if lines and abs(lines[-1]["top"] - w["top"]) <= tol:
            lines[-1]["words"].append(w)
        else:
            lines.append({"top": w["top"], "words": [w]})
    for line in lines:
        line["words"].sort(key=lambda w: w["x0"])
    return lines


def dump(pdf_path: Path) -> None:
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        out.append(f"FILE: {pdf_path.name}  pages={len(pdf.pages)}")
        for pno, page in enumerate(pdf.pages, 1):
            # x_tolerance=1.5: default (3) glues adjacent columns, e.g. "14,60" + "100" -> "14,60100"
            words = page.extract_words(x_tolerance=1.5)
            out.append(f"\n===== PAGE {pno}  size={page.width:.0f}x{page.height:.0f}  "
                       f"words={len(words)}  images={len(page.images)} =====")

            out.append("\n--- extract_text() ---")
            out.append(page.extract_text(x_tolerance=1.5) or "<NO TEXT LAYER>")

            out.append("\n--- lines (top | x0:word ...) ---")
            for line in group_lines(words):
                cells = "  ".join(f"{w['x0']:.0f}:{w['text']}" for w in line["words"])
                out.append(f"{line['top']:6.1f} | {cells}")

    OUT_DIR.mkdir(exist_ok=True)
    target = OUT_DIR / f"{pdf_path.stem}.txt"
    target.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {target}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python debug_dump.py <pdf> [<pdf> ...]")
    for arg in sys.argv[1:]:
        dump(Path(arg))
