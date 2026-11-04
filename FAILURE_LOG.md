# Failure log

## 1. Two columns glued into one word

- **What went wrong:** in INV-01 pos. 5, the price "14,60" and the price unit "100" came out as one word, "14,60100".
- **How I noticed:** the word dump showed one word too few in that row.
- **What I changed:** made pdfplumber's gap setting stricter (`x_tolerance=1.5`).
- **How I checked:** "14,60100" no longer appears, and INV-01 matches the expected output.

## 2. Missing check in the requirements (AI)

- **What went wrong:** the AI could only read parts of the assignment, so its list of checks had no V7 (signs).
- **How I noticed:** the AI said the list was a guess. The full pages showed V1–V7.
- **What I changed:** I built the validator from the real list and added V7.
- **How I checked:** the report shows V1–V7 for every file, and the credit note passes V7.

## 3. OCR on the whole scan gave garbage

- **What went wrong:** reading the full INV-06 page at once gave text like "RE-202 tIHös".
- **How I noticed:** I compared the OCR text with the scan.
- **What I changed:** straightened the slightly tilted page, then read each value on its own, 8 times, keeping the most common answer.
- **How I checked:** the number, dates, order number and gross total now read correctly.

## 4. OCR saw a "2" in empty cells

- **What went wrong:** three items with no discount got a 2 % discount.
- **How I noticed:** I compared the output with the scan. Only line 2 has a discount.
- **What I changed:** a cell with almost no dark pixels is now treated as empty.
- **How I checked:** those three lines now have no discount, and line 2 still has 5 %.

## 5. Order number not found on the scan

- **What went wrong:** OCR joined the number to the next word ("4500093588vom"), so my pattern didn't match.
- **How I noticed:** `order_reference` was empty, but the number is clear on the scan.
- **What I changed:** the pattern now means "10 digits not followed by another digit".
- **How I checked:** `order_reference` is 4500093588.

## 6. Crash on Windows: "No closing quotation" (AI)

- **What went wrong:** the AI's OCR code worked on Linux but crashed on my Windows machine.
- **How I noticed:** the first run on Windows.
- **What I changed:** removed the quotes and the space from the setting, and added a check so it can't come back.
- **How I checked:** INV-06 runs on Windows, and the other files are unchanged.

## 7. Only worked from the project folder (AI)

- **What went wrong:** `extract.py` couldn't find the schema when started from another folder.
- **How I noticed:** a test from a fresh copy of the project.
- **What I changed:** paths are now built from the code's own location.
- **How I checked:** it works from any folder, and all results are the same.

## Not fixed

- Some numbers on the scan are still misread. I didn't try to hide them. The checks V1–V4 flag them, so a person knows what to look at.
