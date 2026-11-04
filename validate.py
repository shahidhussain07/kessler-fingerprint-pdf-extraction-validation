"""Check that the numbers in every extracted JSON add up.

Usage: python validate.py outputs/
Writes outputs/validation_report.md with a PASS/FAIL line per check (V1–V7) per document.
The checks themselves are in fingerprint/checks.py.
"""
import sys
from pathlib import Path

from fingerprint.pipeline import REPORT_NAME, validate_folder


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python validate.py <outputs-folder>")
    folder = Path(sys.argv[1])

    all_results = validate_folder(folder)
    if not all_results:
        sys.exit(f"No .json files found in {folder}")

    for file_name, _, results in all_results:
        failed = [check_id for check_id, _, passed, _ in results if not passed]
        print(f"{file_name:<45} {'all PASS' if not failed else 'FAIL: ' + ', '.join(failed)}")
    print(f"Report written to {folder / REPORT_NAME}")


if __name__ == "__main__":
    main()
