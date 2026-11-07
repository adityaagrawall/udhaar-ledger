# Security

Udhaar Ledger is a portfolio project that handles only synthetic data, but it is built as if the data were real.

## Reporting a vulnerability

Please use GitHub's **private vulnerability reporting** (Security tab, "Report a vulnerability") rather than a public issue. Auth bypasses, tenant data leaks and exposed secrets are the most useful reports.

## How it is protected

| Area | Control |
|---|---|
| Authentication | Clerk only. The API verifies every session JWT: RS256 signature against Clerk's JWKS, issuer, expiry, required claims and the origin it was issued for. The token's own `alg` is never trusted. |
| Authorisation | Server-enforced roles. Viewers (including the public demo account) are read-only: any non-GET request is rejected with `403`, not merely hidden in the UI. A test walks every route in the OpenAPI schema and fails if one answers without a token. |
| Tenant isolation | Every query is scoped by organisation; cross-tenant access returns 404/403. Models are stored per organisation. |
| Demo account | No password exists. Visitors receive a one-time, short-lived Clerk sign-in ticket for a read-only user; the endpoint is rate limited. |
| Rate limiting | Per-IP limits on every route, with tighter limits on demo sign-in, imports, exports, model training and reminder drafts. |
| Transport and headers | HTTPS only (HSTS). API: `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a locked-down CSP and `no-store` on data responses. Frontend: a Content-Security-Policy limited to our own origin, the API and Clerk. |
| Input handling | Bounded field lengths, enum-constrained inputs, a request body size cap, row and unzipped-size limits on imports, CSV formula-injection guard on exports, and sanitised values before anything reaches an LLM prompt. |
| Errors | Unhandled errors return a generic message; details go to server logs only. API docs are hidden in production. |
| Secrets | Never committed. `.env` files are git-ignored, production refuses to start with a default or short `SECRET_KEY`, and CI scans history for leaked secrets. |
| Supply chain | Dependabot (minor and patch), `pip-audit` and `npm audit` in CI, dependency review on pull requests, CodeQL (security-extended), a non-root container, and a maintained JWT library (PyJWT). |

## Known limits (honest list)

- **Auto sign-up:** with `AUTO_PROVISION_USERS=true` (default) anyone who signs up joins the demo organisation as a read-only viewer. Set it to `false` to make the app invite-only.
- **Clerk development instance:** fine for a portfolio, but it has usage limits. A production instance needs its own domain.
- **CSP keeps `'unsafe-inline'` for scripts** because Next.js emits inline bootstrap code. The app renders no user-supplied HTML. A nonce-based policy would force dynamic rendering of every page.
- **Rate limits are in memory** per API instance. Fine for one instance; use a shared store (Redis) if you scale out.
- **No malware scanning** of uploaded spreadsheets beyond size, type and row limits.
- **The database role** used by the API is the Neon owner because the app creates its own tables on startup. A least-privilege runtime role plus a separate migration role is the next step.
