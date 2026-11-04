# AI usage

## Tools

- **Claude (claude.ai):** I used it to:
    - break the assignment into small steps
    - explain how pdfplumber reads a PDF
    - write the code one step at a time
    - fix errors from my Windows runs
    - organise the folders and add the upload page
    - write first drafts of these Markdown files
- **VS Code with Git Bash:** for editing and running everything

## How I worked

- One step at a time. After each step I ran the code on my own machine (Windows 11, Python 3.14) and pasted the real output back.
- I only moved on when the output matched what the PDF actually shows.
- I checked INV-04 by hand and compared the INV-06 output with the scan.

## Example 1: incomplete requirements

- At first the AI could only read parts of the assignment PDF, so it guessed the list of checks.
- That list was missing V7, the check that credit notes are all negative and invoices all positive.
- I noticed because the AI said its list was a guess. Once the full pages were read, V7 was there.
- Lesson: don't build on a summary of something you haven't fully read.

## Example 2: worked on Linux, crashed on Windows

- The AI tested its OCR code on Linux, where it worked.
- On my Windows machine, INV-06 failed with `No closing quotation`.
- The cause was a setting with quotes and a space in it, which Windows reads differently.
- Fix: I removed the quotes and the space, and added a check so it can't happen again.

## Other mistakes I caught

- `extract.py` only worked when run from the project folder. Fixed by building the paths from the file's own location.
- The first OCR version put a 2 % discount on lines that have no discount. Fixed by treating empty cells as empty.
- The AI's OCR results were a bit different from mine. The README uses my results.

## What I checked myself

- INV-01 matches the expected output exactly.
- INV-04 position 7: 26 × 48,02 = 1.248,52, not the printed 1.284,52.
- The INV-06 output, field by field, against the scan.
