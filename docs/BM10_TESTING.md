# BM 10 settlement reconciliation

The source-linked proof uses strict integer paise and the server-selected merchant's BM-04 settlement report. BM-05 registers `reconcile_settlement` as a settlement preparation tool requiring `payments:read`.

Run the API from the repository root, then open http://127.0.0.1:8000/docs under **settlements**.

```sh
backend/.venv/bin/python -m uvicorn bizmate.main:app --host 127.0.0.1 --port 8000
curl -sS -X POST http://127.0.0.1:8000/api/v1/settlements/reconcile \
  -H 'Content-Type: application/json' -d '{}'
backend/.venv/bin/python -m pytest backend/tests/test_reconciliation.py -q
```

Default proof amounts are sales 2,000,000 paise, commission 24,000, GST 4,320, refunds 80,000 and chargeback 35,000. Expected settlement is 1,856,680 paise. Against credit of 1,840,000 paise, residual is 16,680 paise or Rs 166.80.

Each named proof line contains `amount_paise`, `source_references`, `status` and an explanation. The `sources` array provides the underlying amount, kind, settlement reference and availability timestamp for each unique source. Expected and residual lines carry the union of their contributing source references. Saiteja can render these typed fields in the BM-09 proof card.

A missing component has a null amount and `missing` status. Derived amounts remain null until all required inputs are known. An explicit source record with amount zero establishes a known zero. Identical duplicate references are counted once. Conflicting duplicates, including references reused across kinds, leave affected amounts unknown. Overflow outside the shared exact-integer range also yields unknown/conflicting results. Other-settlement and future records are excluded with a warning. Positive residual indicates a shortfall and negative residual indicates overcredit.

The top-level status describes calculation evidence completeness. It does not change a business task's lifecycle. The endpoint is read-only. Ticket creation, report-timeout recovery, goal completion and fresh-credit follow-up are BM-08/BM-11/BM-12 integrations. Provider timeouts return HTTP 503 without generating a false proof.

To reproduce initial figures after changing demo time, reset the selected merchant's synthetic providers. This also clears that merchant's synthetic actions and failure scripts.

```sh
backend/.venv/bin/python backend/scripts/demo_data.py reset
```

Send `{"settlement_reference":"another-settlement"}` to select another settlement. If records are unavailable, the response remains incomplete with null amounts. Advancing the demo clock by 86,400 seconds makes the held credit visible and the seeded residual becomes zero. Reconciliation alone leaves persisted task status unchanged.
