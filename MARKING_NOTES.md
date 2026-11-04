# Marking notes

For each field: **how I find it**, **why that holds up**, and **what would break it**.
All code is in `fingerprint/kessler.py` unless it says otherwise.

## Basic idea

- A PDF doesn't store a table. It stores words, each with a position on the page.
- I read every word with its position (`x0` = distance from the left edge, `top` = distance from the top).
- Words with almost the same `top` are grouped into one line.
- After that, a field is found either by its **label** (e.g. "Rechnungs-Nr.") or by its **column** (an x range).

## Layout A (INV-01 to INV-04)

### Header (page 1, above the table)

- The header has two sides on the same lines: address on the left, labels and values on the right. I cut every line at x = 340.

**document_number and document_type**

- How: the word after "Rechnungs-Nr." or "Gutschrift-Nr.". "Gutschrift-Nr." means credit note, otherwise invoice.
- Why it holds up: the label is printed once and never moves to another line.
- Breaks if: Kessler renames the label, e.g. "Rechnungsnummer".

**document_date**

- How: the date after "Datum" at the start of the line.
- Why it holds up: "start of the line" means "Leistungsdatum" is never picked by mistake.
- Breaks if: the date is printed in another format.

**service_date**

- How: the date after "Leistungsdatum". If there is none (INV-03), it stays empty.
- Why it holds up: INV-04's "Liefertermin KW 42" is a different label, so it is ignored.
- Breaks if: Kessler prints the service date under a new label.

**buyer.customer_number, order_reference, delivery_note_number, referenced_invoice**

- How: the word after "Kunden-Nr.", "Ihre Bestellung", "Lieferschein-Nr." and "Bezug Rechnung".
- Why it holds up: I only take one word, so "vom 22.09.2026" after the order number is left out automatically.
- Breaks if: a label is renamed, or an order number contains a space.

**buyer.name, street, postal_code, city**

- How: the left-side lines between the sender line and the title "RECHNUNG". Lines starting with "Abt." or "z. Hd." are dropped. The city line is "5 digits + name", the street is the line above it, and the name is the first line.
- Why it holds up: no fixed line numbers, so an extra department line doesn't shift anything.
- Breaks if: a foreign address has no 5-digit postal code, or the company name runs over two lines.

**supplier.name and supplier.vat_id**

- How: the name is the text before the first "·" on the first line that starts with "Kessler". The VAT ID comes after "USt-IdNr." in the footer, with spaces removed.
- Why it holds up: the footer is printed on every page and is the same in both layouts.
- Breaks if: the footer changes its wording.

**currency**

- Always EUR, as the schema requires.

### Line items (every page, below the "Pos." line)

- Each word goes into a column by its x position. I use a range per column, because numbers are right-aligned and longer numbers start further left. For example, the price column is x 400–452.
- Each line is one of these:
    - Starts with a number on the far left: a new item.
    - Has text only in the description column: an extra line, added to the item above.
    - Starts with "Übertrag von": the carry-over at the top of a page, skipped.
    - Starts with "Übertrag" or "Nettobetrag": the end of the table on that page.
    - Anything else: the code stops with an error instead of guessing.

**position, article_number, description, unit**

- Taken as printed. Leading zeros are removed from the position.

**quantity, unit_price, line_total**

- German numbers turned into normal numbers: "1.000" → 1000, "12,5" → 12.5, "225,80-" → −225.80 (credit note).

**price_unit**

- From the PE column. It is 1 when empty.

**discount_percent**

- From the Rab. % column. Empty when there is no discount.

**vat_rate**

- From the USt % column.

- Why it holds up: line types are recognised by what they look like, not by line numbers, so any number of pages works.
- Breaks if: Kessler moves the columns, or a description gets so long it spills into the quantity column.
- Bug I found: the PDF library glued "14,60" and "100" into one word, "14,60100". I made its gap setting stricter (`x_tolerance=1.5`).

### Totals and payment terms (last page)

**net_by_vat_rate and vat_by_vat_rate**

- How: "Nettobetrag 19 % USt …" and "zzgl. 19 % USt auf … …", one line per rate. The rate becomes the key ("19").

**net_total and vat_total**

- Kessler doesn't print these, so I add up the printed per-rate values.
- I use the printed values on purpose, not the sum of the lines. That way INV-04's wrong line (36,00 too high) still shows up in the check.

**gross_total**

- How: "Rechnungsbetrag" or "Gutschriftsbetrag" at the start of the line.

**due_date**

- How: the date after "Zahlbar bis". Empty if not printed.

**cash_discount**

- How: "bis <date> abzüglich 2 % Skonto (= 19,08 EUR)".
- INV-04 says "innerhalb von 7 Tagen" instead, so the date is the invoice date + 7 days.
- Skonto is never taken off any total.

- Breaks if: the wording of these lines changes. The code then stops with "Totals block not found" instead of writing wrong totals.

## Layout B (INV-05)

- **Header:** mirrored. Labels are on the left, the address on the right, and the cut is at x = 330.
- **Labels:** "Rechnung Nr.", "Rechnungsdatum", "Lieferdatum", "Kundennummer", "Bestellnummer", "Lieferschein". Each is found the same way as in Layout A.
- **Dates:** written out, e.g. "19. Oktober 2026". The date reader knows the German month names.
- **Buyer:** same reader as Layout A. "z. Hd." is dropped, and "DEUTSCHLAND" under the city is ignored.
- **supplier.name:** comes from the footer line, because the sender line shares a line with "Lieferschein LS-59188". It's the same name either way.
- **Columns:** a new order, with its own x ranges. There is no PE column, so `price_unit` is 1. The "€" and "%" signs are removed.
- **Discount row:** "abzgl. Sonderrabatt 3 % auf 465,60 € -13,97 €" is applied to the item above. It gets discount 3 % and total 451,63, and is not a separate item.
- **Totals:** "Summe netto" is the net total and "MwSt 19%" / "MwSt 7%" are the VAT. Net per rate is not printed, so I add up the lines per rate. The check then compares that sum with "Summe netto".
- **Due date:** the date in "(bis 18. November 2026)". "Kein Skontoabzug" means no cash discount.
- **Breaks if:** a Layout B credit note or a multi-page Layout B shows up. The code expects them to work like Layout A, but I couldn't test it without a sample.

## Scan (INV-06, bonus) – `fingerprint/kessler_scan.py`

- The page is an image, so there are no words with positions. I straighten the image and cut out each value at the Layout A positions.
- Each cut-out is read 8 times, and the most common answer wins.
- Header values are recognised by their shape: "RE…" is the document number, 10 digits is the order number, 5 digits is the customer number.
- Supplier name and VAT ID can't be read on this scan. They come from the fingerprint after checking that the logo says KESSLER.
- Values that can't be read are left empty, not guessed.

## How the layout is chosen

- No text on the page: scan.
- "Rechnungs-Nr." or "Gutschrift-Nr.": Layout A.
- "Rechnungsdatum" and "Rechnung Nr.": Layout B.
- Anything else: an error, "Unknown Kessler layout".

## INV-05: what I had to change and how I kept the old layout safe

INV-05 is the same supplier with a new layout. The header is mirrored, the labels are new, and dates are written out. The table has a new column order and no PE column. Discounts have their own row, and only the total net amount is printed.

What I changed:

- a second set of labels and a second column map
- German month names in the date reader
- the discount row as a new line type
- net per rate added up from the lines
- a small check that picks Layout A or B

How I kept Layout A safe:

- Layout A and Layout B are separate functions. A small entry function only picks one of them, so `extract.py` didn't change at all.
- Shared parts (address, supplier, numbers, dates) are reused, not copied.
- I only made two small changes to shared code, and both keep the old behaviour.
- After the change I ran INV-01 to INV-04 again, and the output was exactly the same.
- A layout the code doesn't know gives an error instead of being read as Layout A.
