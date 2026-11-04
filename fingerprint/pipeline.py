"""The whole flow in one place: PDF -> JSON -> schema check -> validation report.

Used by extract.py and validate.py (command line) and by app.py (upload page),
so every way of running the project does exactly the same thing.
"""
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from .checks import build_report, validate_document
from .helpers import decimals_to_numbers, save_json
from .kessler import extract_kessler

PROJECT_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_DIR / "samples" / "output_schema.json"
OUTPUT_DIR = PROJECT_DIR / "outputs"
REPORT_NAME = "validation_report.md"

_schema_checker = None


def schema_checker():
    """Load the schema once. FORMAT_CHECKER makes it also check "format": "date"."""
    global _schema_checker
    if _schema_checker is None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        _schema_checker = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    return _schema_checker


def extract_pdf(pdf_path, output_dir=OUTPUT_DIR, output_name=None):
    """Extract one PDF and save outputs/<name>.json (+ OCR confidence file for scans).

    output_name: file name stem to use (default: the PDF's own name).
    Returns a dict with everything a caller may want to show.
    """
    pdf_path = Path(pdf_path)
    name = output_name or pdf_path.stem

    result, layout, ocr_confidence = extract_kessler(pdf_path)
    result = decimals_to_numbers(result)

    output_path = Path(output_dir) / f"{name}.json"
    save_json(result, output_path)          # saved even if the schema check fails, so it can be inspected

    confidence_path = None
    if ocr_confidence is not None:
        from .ocr_helpers import write_confidence_report
        confidence_path = Path(output_dir) / f"{name}_ocr_confidence.md"
        write_confidence_report(ocr_confidence, confidence_path)

    schema_errors = [
        f"{'/'.join(str(part) for part in error.path) or '(root)'}: {error.message}"
        for error in schema_checker().iter_errors(result)
    ]
    return {
        "name": name,
        "result": result,
        "layout": layout,
        "ocr_confidence": ocr_confidence,
        "output_path": output_path,
        "confidence_path": confidence_path,
        "schema_errors": schema_errors,
    }


def validate_folder(folder=OUTPUT_DIR):
    """Run V1–V7 on every *.json in folder and write folder/validation_report.md.

    Returns [(file_name, document_number, check_results), ...].
    """
    folder = Path(folder)
    all_results = []
    for json_file in sorted(folder.glob("*.json")):
        doc = json.loads(json_file.read_text(encoding="utf-8"))
        all_results.append((json_file.name, doc.get("document_number", "?"), validate_document(doc)))
    if all_results:
        (folder / REPORT_NAME).write_text(build_report(all_results), encoding="utf-8")
    return all_results


def process_pdf(pdf_path, output_name=None):
    """Everything at once: extract, check schema, re-validate all outputs, update the report.

    Returns the extract_pdf() dict plus "checks" = the V1–V7 results for this document.
    """
    extracted = extract_pdf(pdf_path, output_name=output_name)
    all_results = validate_folder(OUTPUT_DIR)
    file_name = extracted["output_path"].name
    extracted["checks"] = next(results for name, _, results in all_results if name == file_name)
    return extracted
