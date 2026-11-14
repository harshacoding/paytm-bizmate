# BM 13 customer segmentation

BM-13 reads merchant-scoped BM-04 customer/order histories, uses the controlled demo clock and computes inactive consent-eligible recipients with integer-paise cost. The registered `segment_inactive_customers` tool uses BM-05 typed dispatch, customer-read permissions and WIN_BACK intent discovery.

The default window is 30 days. The latest qualifying order must be at least that old, including the exact boundary. Nonqualifying orders do not refresh the visit date. Histories without a qualifying order and histories containing future qualifying orders are excluded as unknown. Unmatched orders do not create customers. Duplicate customer/order IDs are rejected as ambiguous. Recipient IDs are sorted consistently.

Startup fixtures analyse 200 histories and return 120 eligible recipients at 200 paise each, totaling 24,000 paise or Rs 240. Empty audiences cost zero. Consent and time are read again on each request. A custom positive integer inactivity window is supported.

Start the API from the repository root and open http://127.0.0.1:8000/docs under **campaigns**.

```sh
backend/.venv/bin/python -m uvicorn bizmate.main:app --host 127.0.0.1 --port 8000
```

```sh
curl -sS -X POST http://127.0.0.1:8000/api/v1/campaigns/segment \
  -H 'Content-Type: application/json' -d '{}'
curl -sS -X POST http://127.0.0.1:8000/api/v1/campaigns/segment \
  -H 'Content-Type: application/json' -d '{"inactivity_days":45}'
backend/.venv/bin/python -m pytest backend/tests/test_segmentation.py -q
```

Expected default fields include `histories_analysed=200`, `inactive_count=120`, `eligible_count=120`, `estimated_cost_paise=24000` and `simulated=true`. The output also includes evaluation time, merchant ID, sorted recipient IDs, unit cost, consent exclusions and unknown-history exclusions.

On an existing demo database, previous clock/consent changes affect the result. To reproduce the initial fixture, use the BM-04 merchant-scoped reset, which clears mock actions and fixture changes for that merchant.

```sh
backend/.venv/bin/python backend/scripts/demo_data.py reset
```

Test consent changes by setting a recipient's consent to false through `PATCH /api/v1/demo/customers/customer-001/consent` with `{"marketing_consent":false}`, then run segmentation again. The default count becomes 119 and cost becomes 23,800 paise. For the same customer in another merchant's fixture, the original consent remains independent.

The endpoint validates merchant identity from trusted server context. Body-supplied merchant IDs and extra fields are rejected, and missing customer-read scope returns HTTP 403. A scripted customer-provider timeout returns HTTP 503. The segmentation operation writes no task, campaign, approval or send record.

BM-14 uses this audience and estimate for merchant review, exact-input approval and send-time eligibility revalidation. BM-13 cost is a synthetic estimate. Simulated send/delivery remains the campaign-execution task.
