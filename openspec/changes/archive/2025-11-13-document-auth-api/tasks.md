## 1. Information gathering
- [x] 1.1 Review `apps/api/routes/auth.py`, `apps/schemas/auth.py`, and `AuthService` to capture fields & error codes.
- [x] 1.2 Confirm time format (UTC ISO8601), token TTL (30 days), and lockout rules (3 failures → 15-minute cooldown).

## 2. Documentation drafting
- [x] 2.1 Create `docs/api/auth-login.md` (or README section) covering endpoint summary, URL/Method, request/response schema.
- [x] 2.2 Document error codes (`ACCOUNT_LOCKED`, `UNAUTHORIZED`, `INTERNAL_ERROR`) with HTTP status & meaning.
- [x] 2.3 Provide cURL/JS samples, highlighting `Content-Type`, JSON shape, and timestamp format.

## 3. Validation & references
- [x] 3.1 Self-review to ensure doc matches current implementation and includes all fields/examples.
- [x] 3.2 Add a link in README/docs index and mention the doc path in PR notes.
