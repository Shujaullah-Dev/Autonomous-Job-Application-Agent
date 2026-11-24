# Authentication and candidate ownership

This page describes how the API decides who a request belongs to, what a
verified account may read or change, and which verification steps remain
before a public deployment.

The implementation is `backend/app/core/auth.py`. Tests are in
`backend/tests/test_auth_ownership.py`.

## Current model

- Supabase Auth owns sign-up, sign-in, recovery and session refresh. The
  browser obtains an access token; the API never creates passwords or stores
  sessions.
- The API verifies the token signature, issuer, audience and expiry before it
  uses any claim.
- A candidate profile has one owner: the token `sub` stored in
  `candidate_profiles.owner_id` (unique, nullable for legacy rows).
- Candidate-scoped routes require that owner. Missing records and records owned
  by another account both answer `404` so the API never confirms that another
  account's profile exists.
- The development key (`X-Dev-Job-Key`) is a **development-only** gate. It is
  refused outside `APP_ENV=development`, it never establishes ownership, and it
  is never sent from the browser.

## Configuration

Set these in the repository-root `.env`. None of them belongs in a `VITE_*`
variable.

| Variable | Purpose |
| --- | --- |
| `SUPABASE_URL` | Project URL. Derives the JWKS URL (`/auth/v1/.well-known/jwks.json`) and the expected issuer (`/auth/v1`) |
| `SUPABASE_JWT_SECRET` | Legacy symmetric Supabase JWT secret; verifies HS256 tokens |
| `SUPABASE_JWKS_URL` | Explicit JWKS URL; use instead of `SUPABASE_URL` when the project URL is not the same origin |
| `SUPABASE_JWT_ISSUER` | Explicit expected `iss` value |
| `SUPABASE_JWT_AUDIENCE` | Expected `aud` value; default `authenticated` |

Identity is *configured* when either `SUPABASE_JWT_SECRET` or a JWKS URL
(explicit or derived from `SUPABASE_URL`) is present. While identity is not
configured, any request that sends a bearer token is rejected with `503`
rather than being trusted, and the release-readiness report keeps
`production_user_auth_verified` false.

### Key rotation and outages

- Signing keys are cached for ten minutes per JWKS URL.
- An unknown `kid` triggers one cache refresh, which covers normal key
  rotation.
- An unreachable identity provider or an empty key set returns `503` with a
  generic message. The response never includes the JWKS URL, the secret, or
  provider internals.
- Only asymmetric JWKS algorithms `RS256`, `RS384`, `RS512`, `ES256`, `ES384`
  and `EdDSA` are accepted from a JWKS document.

## Endpoint behaviour

| Situation | Response |
| --- | --- |
| No `Authorization` header on a private route in development with the development key | Allowed (development gate only) |
| No `Authorization` header on a private route outside development | `401` with `WWW-Authenticate: Bearer` |
| Malformed header, bad signature, expired token, wrong issuer or wrong audience | `401` with a generic reason |
| Identity not configured but a token was supplied | `503` |
| JWKS unavailable or unknown signing key | `503` |
| Verified account requesting its own candidate record | Normal response |
| Verified account requesting another account's candidate record | `404` |
| Verified account without a profile | `404` from `GET /api/v1/candidates/me` |

The development key keeps its previous failure codes inside development
(`403` for a missing or incorrect key, `503` when `DEV_JOB_WRITE_KEY` is
empty). Outside development the same request now answers `401`, because a
shared key cannot represent a user.

## Creating and finding the profile

- `POST /api/v1/candidates` with a verified token stores `owner_id` from the
  token subject. The request `email` must equal the verified account email
  (`403` otherwise), and a second profile for the same account returns `409`.
- `GET /api/v1/candidates/me` returns the profile owned by the caller. It is
  the endpoint the frontend uses instead of trusting a stored UUID.
- Legacy rows with `owner_id = NULL` are linked only when the stored email
  matches the verified account email exactly (case-insensitive). A row with a
  different owner is never re-linked.

## Protected routers

`require_candidate_owner` is attached to every candidate-scoped router:
candidates, skills, experience, education, resumes, resume import, matches,
hybrid matches, recommendations, explanations, workflows, application
materials, application tracking, submission handoffs, follow-ups, interviews
and notification recovery.

`require_private_access` replaced the development-key dependency on those
routers. It accepts a verified token in any environment and the development
key only in development. `require_user` guards `/api/v1/candidates/me`, which
must always be authenticated.

Development operations (`/api/v1/ops/*`, job creation) intentionally keep the
development key and remain unavailable outside development.

## Frontend integration

- `frontend/src/lib/api.ts` attaches the Supabase access token, when a session
  exists, to every API request. It still refuses absolute URLs and path
  traversal and never sends `X-Dev-Job-Key`.
- `frontend/src/pages/Profile.tsx` resolves the account profile with
  `GET /api/v1/candidates/me` before using a stored identifier, and reuses that
  profile instead of creating a duplicate.
- Shortlists, applications, follow-ups, interviews and notifications still run
  on the demo state. The API now enforces ownership for those routes, so the
  remaining work is adapting each screen to the generated API types, not
  adding backend authorization.

## Verification

Run from `backend/`:

```powershell
..\.venv\Scripts\python.exe -m ruff check app tests
..\.venv\Scripts\python.exe -m pytest tests/test_auth_ownership.py -q
..\.venv\Scripts\python.exe -m pytest -q
```

`test_auth_ownership.py` covers: missing token, expired token, wrong signature,
wrong audience, wrong issuer, malformed header, own profile access, foreign
profile reads and writes, `/me` lookup and legacy linking, duplicate profile
conflicts, development-key compatibility, the production `401`, unconfigured
identity, and an unreachable JWKS.

For a manual check with Swagger:

1. Sign in through the frontend and copy the access token from the Supabase
   session.
2. Open `http://127.0.0.1:8000/docs`, choose **Authorize**, and paste the token.
3. Call `GET /api/v1/candidates/me`. Expect `200` for a profile you created
   with that account and `404` for a different account's UUID.
4. Call `GET /api/v1/candidates/{other_uuid}` with another account's ID and
   confirm the `404`.

## Remaining gaps

- The database migration that adds `owner_id` is additive and untested against
  a live database; the migration history still cannot create a clean schema
  (`fa05578eada4` and `5b0bd740df7a` both create `candidate_profiles`). Review
  and test on a disposable PostgreSQL database before applying it.
- Row-level security is not enabled, because the browser never queries tables
  directly. Revisit if direct table access is introduced.
- Rate limiting and abuse controls are not implemented.
- The frontend private screens still use demo state for shortlists,
  applications, follow-ups, interviews and notifications.
