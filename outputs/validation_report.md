# Validation report

Tolerance for amounts: ±0.01. A FAIL caused by the document itself is a real finding.

## Summary

| Document | V1 | V2 | V3 | V4 | V5 | V6 | V7 |
|---|---|---|---|---|---|---|---|
| INV-01_RE-2026-10418.json (RE-2026-10418) | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| INV-02_RE-2026-10431.json (RE-2026-10431) | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| INV-03_GS-2026-00872.json (GS-2026-00872) | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| INV-04_RE-2026-10457.json (RE-2026-10457) | **FAIL** | **FAIL** | PASS | PASS | PASS | PASS | PASS |
| INV-05_2026-R-00117.json (2026-R-00117) | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| INV-06_BONUS_scan_RE-2026-10466.json (RE-2026-10466) | **FAIL** | **FAIL** | **FAIL** | **FAIL** | PASS | PASS | **FAIL** |

## INV-01_RE-2026-10418.json – RE-2026-10418

- PASS V1 Line math
  - all 6 lines correct
- PASS V2 Net per VAT rate
  - 19 %: sum of lines 801.47 = net_by_vat_rate 801.47
  - all rates: 801.47 = net_total 801.47
- PASS V3 VAT per rate
  - 19 %: 801.47 × 19 % = 152.28 = printed 152.28
- PASS V4 Net + VAT = gross
  - 801.47 + 152.28 = 953.75, printed gross 953.75
- PASS V5 Supplier VAT ID
  - DE287364519
- PASS V6 Dates
  - valid: document_date, service_date, due_date, cash_discount.until
  - due_date 2026-11-05 ≥ document_date 2026-10-06
- PASS V7 Signs
  - invoice: all 11 amounts positive

## INV-02_RE-2026-10431.json – RE-2026-10431

- PASS V1 Line math
  - all 26 lines correct
- PASS V2 Net per VAT rate
  - 19 %: sum of lines 4787.18 = net_by_vat_rate 4787.18
  - 7 %: sum of lines 318.80 = net_by_vat_rate 318.80
  - all rates: 5105.98 = net_total 5105.98
- PASS V3 VAT per rate
  - 19 %: 4787.18 × 19 % = 909.56 = printed 909.56
  - 7 %: 318.80 × 7 % = 22.32 = printed 22.32
- PASS V4 Net + VAT = gross
  - 5105.98 + 931.88 = 6037.86, printed gross 6037.86
- PASS V5 Supplier VAT ID
  - DE287364519
- PASS V6 Dates
  - valid: document_date, service_date, due_date, cash_discount.until
  - due_date 2026-11-08 ≥ document_date 2026-10-09
- PASS V7 Signs
  - invoice: all 33 amounts positive

## INV-03_GS-2026-00872.json – GS-2026-00872

- PASS V1 Line math
  - all 3 lines correct
- PASS V2 Net per VAT rate
  - 19 %: sum of lines -400.05 = net_by_vat_rate -400.05
  - all rates: -400.05 = net_total -400.05
- PASS V3 VAT per rate
  - 19 %: -400.05 × 19 % = -76.01 = printed -76.01
- PASS V4 Net + VAT = gross
  - -400.05 + -76.01 = -476.06, printed gross -476.06
- PASS V5 Supplier VAT ID
  - DE287364519
- PASS V6 Dates
  - valid: document_date
  - no due_date printed – only date format checked
- PASS V7 Signs
  - credit_note: all 8 amounts negative

## INV-04_RE-2026-10457.json – RE-2026-10457

- **FAIL** V1 Line math
  - 1 of 15 lines wrong or not checkable:
  - Pos. 7 (KI-71004): 26.0 × 48.02 ÷ 1.0 × (1 − 0) = expected 1248.52, printed 1284.52, difference 36.00 (difference is a multiple of 0.09 – typical for swapped digits)
- **FAIL** V2 Net per VAT rate
  - 19 %: sum of lines 5249.22, net_by_vat_rate 5213.22, difference -36.00 (difference is a multiple of 0.09 – typical for swapped digits)
  - 7 %: sum of lines 69.80 = net_by_vat_rate 69.80
  - all rates: 5283.02 = net_total 5283.02
- PASS V3 VAT per rate
  - 19 %: 5213.22 × 19 % = 990.51 = printed 990.51
  - 7 %: 69.80 × 7 % = 4.89 = printed 4.89
- PASS V4 Net + VAT = gross
  - 5283.02 + 995.40 = 6278.42, printed gross 6278.42
- PASS V5 Supplier VAT ID
  - DE287364519
- PASS V6 Dates
  - valid: document_date, service_date, due_date, cash_discount.until
  - due_date 2026-11-13 ≥ document_date 2026-10-14
- PASS V7 Signs
  - invoice: all 22 amounts positive

## INV-05_2026-R-00117.json – 2026-R-00117

- PASS V1 Line math
  - all 5 lines correct
- PASS V2 Net per VAT rate
  - 19 %: sum of lines 925.33 = net_by_vat_rate 925.33
  - 7 %: sum of lines 49.80 = net_by_vat_rate 49.80
  - all rates: 975.13 = net_total 975.13
- PASS V3 VAT per rate
  - 19 %: 925.33 × 19 % = 175.81 = printed 175.81
  - 7 %: 49.80 × 7 % = 3.49 = printed 3.49
- PASS V4 Net + VAT = gross
  - 975.13 + 179.30 = 1154.43, printed gross 1154.43
- PASS V5 Supplier VAT ID
  - DE287364519
- PASS V6 Dates
  - valid: document_date, service_date, due_date
  - due_date 2026-11-18 ≥ document_date 2026-10-19
- PASS V7 Signs
  - invoice: all 12 amounts positive

## INV-06_BONUS_scan_RE-2026-10466.json – RE-2026-10466

- **FAIL** V1 Line math
  - 3 of 4 lines wrong or not checkable:
  - Pos. 2 (KI-63310): 20 × 12.3 ÷ 1 × (1 − 0.05) = expected 233.70, printed 235.60, difference 1.90
  - Pos. 3 (None): 300 × 3.85 ÷ 100 × (1 − 0) = expected 11.55, printed 11.58, difference 0.03
  - Pos. 4: cannot check, missing unit_price, line_total
- **FAIL** V2 Net per VAT rate
  - Pos. 4: VAT rate or line_total missing – sums are incomplete
  - 19 %: sum of lines 421.58, net_by_vat_rate 421.55, difference -0.03
  - 7 %: sum of lines 0.00, net_by_vat_rate 3.39, difference 3.39
  - all rates: 424.94 = net_total 424.94
- **FAIL** V3 VAT per rate
  - 19 %: 421.55 × 19 % = 80.09 = printed 80.09
  - 7 %: 3.39 × 7 % = expected 0.24, printed 2.44, difference 2.20
- **FAIL** V4 Net + VAT = gross
  - 424.94 + 82.53 = 507.47, printed gross 538.98, difference 31.51
- PASS V5 Supplier VAT ID
  - DE287364519
- PASS V6 Dates
  - valid: document_date, due_date
  - due_date 2026-11-14 ≥ document_date 2026-10-15
- **FAIL** V7 Signs
  - invoice: expected all positive, these are not:
  - Pos. 4 line_total = None
