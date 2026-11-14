# Shared API contract

Harsha owns domain and policy semantics; Devi owns HTTP transport and storage. Saiteja consumes generated TypeScript types.

- Source of truth: `backend/src/bizmate/domain/models.py` and `backend/src/bizmate/api/routes.py`.
- Export: `npm run contracts:generate` writes `contracts/openapi.json` and `frontend/src/api/schema.d.ts`.
- Check: `npm run contracts:check` fails when backend OpenAPI differs. CI also regenerates frontend types and checks Git drift.
- Change backend schemas, regenerate, update examples/tests, and commit all affected files in the same PR. Do not hand-edit generated files.
- Money fields ending in `_paise` are integer paise. UI converts for display only.
- Contract version 0.4.0 includes Conversation, Message, LanguageContext and related components, language codes en/te/hi, preferred/detected/response language metadata, optional task/conversation links and a generated `lifecycle.json` transition map. Original message content is preserved. Conversation/language components are shared DTOs; they do not imply new HTTP endpoints or language detection. See [BM-02 integration notes](../docs/BM_02_CONTRACTS.md).
- Merchant context is server-owned. Request schemas deliberately reject `merchant_id`, status, tool arguments, or approval claims that are not part of the endpoint contract.

The local scaffold implements task intake/list/detail/events/messages, a synthetic session, health, and static component previews. It does not perform investigation or sends. Approval decisions return HTTP 501 until BM-06 is implemented. `/docs` on the backend provides the complete interactive API reference.
