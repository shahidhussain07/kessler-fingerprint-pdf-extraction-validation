"""Extract Kessler PDFs into JSON.

Usage:
    python extract.py samples/INV-01_RE-2026-10418.pdf
    python extract.py samples/*.pdf            (several files at once)

Writes outputs/<pdf-file-name>.json and checks it against samples/output_schema.json.
"""
import sys
from pathlib import Path

from fingerprint.pipeline import PROJECT_DIR, extract_pdf


def main():
    pdf_paths = sys.argv[1:]
    if not pdf_paths:
        sys.exit("usage: python extract.py <path-to-pdf> [<path-to-pdf> ...]")

    all_ok = True
    for pdf_path in pdf_paths:
        name = Path(pdf_path).name
        try:
            info = extract_pdf(pdf_path)
        except Exception as error:            # one bad PDF must not stop the others
            print(f"ERROR        {name}: {error}")
            all_ok = False
            continue

        output = info["output_path"].relative_to(PROJECT_DIR)
        if info["confidence_path"]:
            print(f"             OCR confidence per field -> {info['confidence_path'].relative_to(PROJECT_DIR)}")
        if info["schema_errors"]:
            all_ok = False
            print(f"SCHEMA FAIL  {name} -> {output}")
            for error in info["schema_errors"]:
                print(f"    {error}")
        else:
            print(f"OK           {name} -> {output}  (layout {info['layout']}, "
                  f"{len(info['result']['line_items'])} items)")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
