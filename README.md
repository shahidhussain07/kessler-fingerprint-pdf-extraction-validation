# Kessler Invoice Fingerprint

Reads PDF invoices and credit notes from **Kessler Industrietechnik GmbH** (customer: Rheinwerk Anlagenbau AG), turns each one into JSON that follows `samples/output_schema.json`, and checks that the numbers add up.

- Values are taken **as printed**. Nothing is corrected.
- If something doesn't add up, the validation report says where and by how much.

## Results

| Document | What it is       | Extract                         | Validation                                     |
| -------- | ---------------- | ------------------------------- | ---------------------------------------------- |
| INV-01   | Invoice, 1 page  | OK, matches the expected output | all PASS                                       |
| INV-02   | Invoice, 3 pages | OK, 26 items                    | all PASS                                       |
| INV-03   | Credit note      | OK, all amounts negative        | all PASS                                       |
| INV-04   | Invoice, 2 pages | OK                              | FAIL V1, V2 (error in the document, see below) |
| INV-05   | New layout       | OK                              | all PASS                                       |
| INV-06   | Scan (bonus)     | Partial, some fields empty      | FAIL where OCR misread numbers                 |

**INV-04:** position 7 prints 26 × 48,02 = 1.284,52, but the right amount is 1.248,52, which is 36,00 too much (two digits look swapped). The printed totals match the correct amount, so only that one line is wrong. The JSON keeps the printed value, and the report shows the difference. I would ask Kessler for a corrected invoice before paying.

## Installation

You need **Python 3** (tested with 3.13 and 3.14) and **git**.
The OCR bonus (INV-06) also needs the **Tesseract** program with German language data. INV-01 to INV-05 work without it.

### Windows

1. Get the code and create a virtual environment (Git Bash):

    ```bash
    git clone https://github.com/shahidhussain07/swe-intern-assignment-shahid-hussain
    cd swe-intern-assignment-shahid-hussain
    py -m venv .venv
    source .venv/Scripts/activate
    python -m pip install -r requirements.txt
    ```

    In PowerShell, activate with `.venv\Scripts\Activate.ps1` instead (in cmd: `.venv\Scripts\activate.bat`).

2. Tesseract (only for INV-06):
    - Download the installer from the UB Mannheim page: https://github.com/UB-Mannheim/tesseract/wiki
    - In the installer, under _Additional language data_, tick **German**.
    - Keep the default folder `C:\Program Files\Tesseract-OCR`. The code finds it there by itself.

### macOS

1. Get the code and create a virtual environment:

    ```bash
    git clone https://github.com/shahidhussain07/swe-intern-assignment-shahid-hussain
    cd swe-intern-assignment-shahid-hussain
    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -r requirements.txt
    ```

2. Tesseract (only for INV-06), with Homebrew:

    ```bash
    brew install tesseract tesseract-lang
    ```

### Linux

1. Get the code and create a virtual environment:

    ```bash
    git clone https://github.com/shahidhussain07/swe-intern-assignment-shahid-hussain
    cd swe-intern-assignment-shahid-hussain
    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -r requirements.txt
    ```

    On Debian/Ubuntu, run `sudo apt install python3-venv` first if `venv` is missing.

2. Tesseract (only for INV-06):

    ```bash
    sudo apt install tesseract-ocr tesseract-ocr-deu            # Debian / Ubuntu
    sudo dnf install tesseract tesseract-langpack-deu           # Fedora
    ```

### Check the setup

```bash
python -m tests.test_helpers      # should print: All helper checks passed
tesseract --list-langs            # should list "deu" (only needed for INV-06)
```

If Tesseract is installed somewhere the code can't find, set `TESSERACT_CMD` to the full path of the program.

## How to run

Run everything from the project folder, with the virtual environment active.

**Command line**

```bash
python extract.py samples/*.pdf      # one JSON per PDF in outputs/
python validate.py outputs/          # writes outputs/validation_report.md
```

You can also extract a single file: `python extract.py samples/INV-01_RE-2026-10418.pdf`.

**Check INV-01 against the expected output**

```bash
python -m tools.check_expected outputs/INV-01_RE-2026-10418.json samples/INV-01_expected_output.json
```

This prints `MATCH`, or lists every difference.

**Upload page (optional)**

```bash
python app.py
```

Open http://127.0.0.1:5000 and drag in a Kessler PDF. It extracts the JSON, checks it against the schema, runs V1–V7 and updates the report, all in one step. It uses the same code as the two commands and only runs on your own computer.

**See word positions in a PDF** (used to measure the layout)

```bash
python -m tools.debug_dump samples/*.pdf     # writes debug/<name>.txt
```

## Project structure

```
extract.py               command line: PDFs → outputs/*.json
validate.py              command line: outputs/ → validation_report.md
app.py                   optional upload page
fingerprint/
  pipeline.py            the whole flow: extract → schema check → checks → report
  kessler.py             Kessler rules for text PDFs (Layout A and Layout B)
  kessler_scan.py        Kessler rules for scans (OCR)
  helpers.py             general: German numbers and dates, reading PDF words, JSON
  ocr_helpers.py         general: load scan, straighten, read one cell with OCR
  checks.py              general: checks V1–V7 and the report
tools/                   debug_dump.py, check_expected.py
tests/                   test_helpers.py
samples/                 input PDFs, schema, expected output for INV-01
outputs/                 generated JSON files and the validation report
```

Kessler-specific rules live only in `kessler.py` and `kessler_scan.py`. Everything else would work for any supplier.

## How it works

- **A PDF is words with positions.** pdfplumber gives every word with its distance from the left edge (x) and from the top. Words at the same height form one line.
- **Header fields** are found by their label, e.g. the word after "Rechnungs-Nr.".
- **Table columns** are x ranges. Numbers are right-aligned, so each column is a range, not one exact spot.
- **Each table line** is either a new item, an extra description line for the item above, a carry-over ("Übertrag") to skip, or the end of the table. Anything else stops with an error instead of guessing.
- **Layouts:** the code checks page 1 and picks one:
    - "Rechnungs-Nr." means **Layout A** (INV-01 to INV-04).
    - "Rechnung Nr." plus "Rechnungsdatum" means **Layout B** (INV-05).
    - No text at all means a **scan** (INV-06).
    - Anything else is refused with "Unknown Kessler layout".
- **Money** is kept as exact decimals, not floats, so no rounding errors show up in the checks.

## Checks (validate.py)

| Check | What it tests                                                                        |
| ----- | ------------------------------------------------------------------------------------ |
| V1    | quantity × price ÷ price unit × (1 − discount) = line total                          |
| V2    | lines per VAT rate add up to the net per rate, and the rates add up to the net total |
| V3    | net × VAT rate = VAT per rate                                                        |
| V4    | net + VAT = gross                                                                    |
| V5    | supplier VAT ID is DE + 9 digits                                                     |
| V6    | dates are real dates, and the due date is not before the document date               |
| V7    | credit note: all amounts negative; invoice: all positive                             |

All amounts are compared with a tolerance of ±0.01. A FAIL shows the line, the expected value, the printed value and the difference.

## Values that are calculated, not printed

- **Layout A** `net_total` and `vat_total`: the sum of the printed per-rate values (Kessler prints no single total).
- **Layout B** `net_by_vat_rate`: the line totals added up per rate (only "Summe netto" is printed). V2 checks this sum against "Summe netto".
- **INV-04** Skonto date: "within 7 days of the invoice date", so the invoice date + 7 days = 2026-10-21.
- **INV-05** pos. 2 line total: the item amount minus the discount row (465,60 − 13,97 = 451,63).

## Known limits

- Column positions were measured on these samples. If Kessler moves its columns, they need to be measured again.
- A Layout B credit note, a multi-page Layout B and Skonto in Layout B haven't been seen yet. The code expects them to work like Layout A, but this is untested.
- The buyer address needs a German 5-digit postal code.
- Only Kessler documents are supported. Any other supplier is refused on purpose, because using Kessler's positions on another layout would give wrong values that look right.

## Bonus: the scanned INV-06

How it's read:

- The scan is low-resolution and tilted by about 0.9°, so the page is straightened first.
- Each value is cut out at the Layout A position and read 8 times with slightly different clean-up. The most common answer wins.
- Missing commas and dashes are rebuilt from Kessler's formats. For example, "174 40" becomes 174.40 and "RE 2026 10466" becomes RE-2026-10466.
- The big KESSLER logo is checked before anything else.
- The footer is too small to read, so the supplier name and VAT ID come from the fingerprint, not from OCR.
- Values that can't be read are left empty (`null`) instead of guessed. That's why INV-06 doesn't pass the schema check.

`outputs/INV-06_BONUS_scan_RE-2026-10466_ocr_confidence.md` shows how many of the 8 readings agreed for each value.

| Trust       | Fields                                                                                                                                              |
| ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Trust       | document number, document date, due date, customer number, order number, delivery note, buyer street and postal code, 19 % net and VAT, gross total |
| Check first | anything marked LOW in the confidence file, and any line or total that fails V1–V4                                                                  |
| Don't trust | descriptions, buyer name and city spelling, units, service date                                                                                     |

OCR results can differ a little between Tesseract versions, and between Windows and Linux.

## Other documents

- `MARKING_NOTES.md`: how each field is found, and what changed for INV-05
- `FAILURE_LOG.md`: problems I hit and how I fixed them
- `AI_USAGE.md`: how I used AI tools
