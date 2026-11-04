"""Upload page: drop a Kessler PDF in the browser -> extract, check schema, validate – all in one go.

Usage:
    python app.py
    then open http://127.0.0.1:5000

It runs exactly the same code as extract.py + validate.py (fingerprint/pipeline.py), writes
outputs/<pdf-name>.json and refreshes outputs/validation_report.md.
Runs only on your own computer (127.0.0.1) – it is a demo tool, not a public server.
"""
import tempfile
from pathlib import Path

from flask import Flask, abort, render_template_string, request, send_from_directory
from werkzeug.utils import secure_filename

from fingerprint.pipeline import OUTPUT_DIR, process_pdf

app = Flask(__name__)


@app.template_global()
def money(value):
    """1284.5 -> "1284.50" for display; None (unreadable OCR cell) -> "–"."""
    return "–" if value is None else f"{value:.2f}"

app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024          # 20 MB upload limit

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kessler Fingerprint</title>
<style>
  :root { --ink:#1d2433; --muted:#5f6b7a; --line:#dde2e8; --bg:#f6f7f9; --pass:#1a7f37; --fail:#c62828; --accent:#2457d6; }
  * { box-sizing:border-box; }
  body { margin:0; font:15px/1.5 system-ui, "Segoe UI", sans-serif; color:var(--ink); background:var(--bg); }
  main { max-width:1100px; margin:0 auto; padding:24px 16px 48px; }
  h1 { font-size:22px; margin:0 0 4px; } h2 { font-size:17px; margin:28px 0 10px; }
  .muted { color:var(--muted); }
  .card { background:#fff; border:1px solid var(--line); border-radius:10px; padding:16px 18px; }
  #drop { border:2px dashed #b7c0cc; text-align:center; padding:32px 16px; cursor:pointer; }
  #drop.over { border-color:var(--accent); background:#eef3ff; }
  #drop input { display:none; }
  button { background:var(--accent); color:#fff; border:0; border-radius:6px; padding:9px 18px; font:inherit; cursor:pointer; }
  #busy { display:none; margin-top:12px; }
  table { width:100%; border-collapse:collapse; font-size:14px; background:#fff; }
  th, td { font-feature-settings:"calt" 0; text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); vertical-align:top; }
  th { background:#eef1f5; font-weight:600; }
  td.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
  .pass { color:var(--pass); font-weight:600; } .fail { color:var(--fail); font-weight:600; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:10px; }
  .grid div span { display:block; font-size:12px; color:var(--muted); }
  .error { border-color:#f1b5b5; background:#fff5f5; }
  .scroll { overflow-x:auto; }
  ul.details { margin:4px 0 0; padding-left:18px; color:var(--muted); }
  a { color:var(--accent); }
</style></head>
<body><main>
  <h1>Kessler Fingerprint</h1>
  <p class="muted">Drop a Kessler Industrietechnik PDF – it is read, extracted to JSON, checked against the schema and validated (V1–V7) in one step.</p>

  <form class="card" id="drop" method="post" enctype="multipart/form-data">
    <input type="file" name="pdf" id="file" accept="application/pdf,.pdf">
    <p><strong>Drag a PDF here</strong> or click to choose one</p>
    <p class="muted" id="chosen">Text PDFs take about a second, scanned PDFs (OCR) about 30–60 seconds.</p>
    <p id="busy" class="muted">Processing…</p>
  </form>

  {% if error %}
    <h2>Could not process {{ filename }}</h2>
    <div class="card error">{{ error }}</div>
  {% endif %}

  {% if info %}
    {% set doc = info.result %}
    <h2>{{ filename }}</h2>
    <div class="card grid">
      <div><span>Detected layout</span>{{ info.layout }}</div>
      <div><span>Document</span>{{ doc.document_type }} {{ doc.document_number }}</div>
      <div><span>Date / service / due</span>{{ doc.document_date }} / {{ doc.service_date or "–" }} / {{ doc.due_date or "–" }}</div>
      <div><span>Supplier</span>{{ doc.supplier.name }} ({{ doc.supplier.vat_id }})</div>
      <div><span>Buyer</span>{{ doc.buyer.name }}, {{ doc.buyer.street }}, {{ doc.buyer.postal_code }} {{ doc.buyer.city }} (Kd. {{ doc.buyer.customer_number }})</div>
      <div><span>Order / delivery note / ref. invoice</span>{{ doc.order_reference or "–" }} / {{ doc.delivery_note_number or "–" }} / {{ doc.referenced_invoice or "–" }}</div>
      <div><span>Schema</span>
        {% if info.schema_errors %}<b class="fail">FAIL</b>{% else %}<b class="pass">valid</b>{% endif %}</div>
      <div><span>Files</span>
        <a href="/outputs/{{ info.output_path.name }}">{{ info.output_path.name }}</a> ·
        <a href="/outputs/validation_report.md">validation_report.md</a>
        {% if info.confidence_path %} · <a href="/outputs/{{ info.confidence_path.name }}">OCR confidence</a>{% endif %}</div>
    </div>
    {% if info.schema_errors %}
      <ul class="details">{% for e in info.schema_errors %}<li>{{ e }}</li>{% endfor %}</ul>
    {% endif %}

    <h2>Validation</h2>
    <div class="scroll"><table>
      <tr><th>Check</th><th>Result</th><th>Details</th></tr>
      {% for check_id, name, passed, details in info.checks %}
      <tr><td>{{ check_id }} {{ name }}</td>
          <td class="{{ 'pass' if passed else 'fail' }}">{{ "PASS" if passed else "FAIL" }}</td>
          <td><ul class="details">{% for d in details %}<li>{{ d }}</li>{% endfor %}</ul></td></tr>
      {% endfor %}
    </table></div>

    <h2>Line items ({{ doc.line_items | length }})</h2>
    <div class="scroll"><table>
      <tr><th>Pos</th><th>Article</th><th>Description</th><th>Qty</th><th>Unit</th><th>Price</th><th>PE</th><th>Disc. %</th><th>Total</th><th>VAT</th></tr>
      {% for i in doc.line_items %}
      <tr><td>{{ i.position }}</td><td>{{ i.article_number or "–" }}</td><td>{{ i.description }}</td>
          <td class="num">{{ "%g" | format(i.quantity) if i.quantity is not none else "–" }}</td><td>{{ i.unit }}</td><td class="num">{{ "%g" | format(i.unit_price) if i.unit_price is not none else "–" }}</td>
          <td class="num">{{ "%g" | format(i.price_unit) }}</td><td class="num">{{ "%g" | format(i.discount_percent) if i.discount_percent is not none else "" }}</td>
          <td class="num">{{ money(i.line_total) }}</td><td class="num">{{ i.vat_rate }} %</td></tr>
      {% endfor %}
    </table></div>

    <h2>Totals</h2>
    <div class="scroll"><table>
      <tr><th>VAT rate</th><th>Net</th><th>VAT</th></tr>
      {% for rate, net in doc.totals.net_by_vat_rate.items() %}
      <tr><td>{{ rate }} %</td><td class="num">{{ money(net) }}</td><td class="num">{{ money(doc.totals.vat_by_vat_rate.get(rate)) }}</td></tr>
      {% endfor %}
      <tr><th>Total</th><th class="num">{{ money(doc.totals.net_total) }}</th><th class="num">{{ money(doc.totals.vat_total) }}</th></tr>
      <tr><th>Gross</th><th class="num" colspan="2">{{ money(doc.totals.gross_total) }}</th></tr>
    </table></div>
    <p class="muted">Cash discount (informational, never subtracted):
      {% if doc.cash_discount %}{{ doc.cash_discount.percent }} % until {{ doc.cash_discount.until }} = {{ doc.cash_discount.amount }}{% else %}none{% endif %}</p>
  {% endif %}
</main>
<script>
  const drop = document.getElementById("drop"), file = document.getElementById("file");
  const send = () => { if (file.files.length) {
      document.getElementById("chosen").textContent = file.files[0].name;
      document.getElementById("busy").style.display = "block"; drop.submit(); } };
  drop.addEventListener("click", () => file.click());
  file.addEventListener("change", send);
  ["dragenter", "dragover"].forEach(e => drop.addEventListener(e, ev => { ev.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach(e => drop.addEventListener(e, ev => { ev.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", ev => { file.files = ev.dataTransfer.files; send(); });
</script>
</body></html>"""


@app.get("/")
def index():
    return render_template_string(PAGE)


@app.post("/")
def upload():
    uploaded = request.files.get("pdf")
    filename = secure_filename(uploaded.filename) if uploaded else ""
    if not filename.lower().endswith(".pdf"):
        return render_template_string(PAGE, filename=filename or "upload", error="Please upload a .pdf file."), 400

    with tempfile.TemporaryDirectory() as temp_dir:      # the upload itself is not kept
        pdf_path = Path(temp_dir) / filename
        uploaded.save(pdf_path)
        if pdf_path.read_bytes()[:5] != b"%PDF-":
            return render_template_string(PAGE, filename=filename, error="This file is not a PDF."), 400
        try:
            info = process_pdf(pdf_path)
        except Exception as error:                       # e.g. "Unknown Kessler layout"
            return render_template_string(PAGE, filename=filename, error=str(error)), 422
    return render_template_string(PAGE, filename=filename, info=info)


@app.get("/outputs/<path:name>")
def output_file(name):
    if not (OUTPUT_DIR / name).is_file():
        abort(404)
    return send_from_directory(OUTPUT_DIR, name, mimetype="text/plain; charset=utf-8"
    if name.endswith(".md") else None)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
