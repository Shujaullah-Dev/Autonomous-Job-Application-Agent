# Local QA and device testing

This page is the repeatable test plan for running the product on one computer before it is published. It covers the backend API, the React frontend, the automated suites, a desktop checklist, and mobile checks at emulated and real device widths.

The goal is not only "the page loads". Each check names what it proves, so a failure can be traced to the backend, the browser client, or the environment.

## Current connection status

| Area | Status | How it is exercised |
| --- | --- | --- |
| Public job search and job detail | Live against the backend | `GET /api/v1/jobs`, `GET /api/v1/jobs/{job_id}` |
| Candidate profile, skills, experience, education | Live against the backend after Supabase sign-in | `/api/v1/candidates/...`, resolved through `GET /api/v1/candidates/me` |
| Resume preview and import | Demo review with client-side file validation | The screen does not upload the selected file |
| Supabase signup, login, recovery, sign-out | Live when `frontend/.env.local` holds project values | Browser talks to Supabase directly |
| Shortlists, applications, follow-ups, interviews, notifications, settings | Demo state in the browser | No private backend call is made |
| Private backend routers (workflows, applications, interviews, notifications) | Available with a Supabase access token | `Authorization: Bearer <token>` plus candidate ownership; the development key works only in development |
| Development operations (`/api/v1/ops/*`, job creation) | Development only | `X-Dev-Job-Key` plus `APP_ENV=development`; `401` outside development |

A demo session is intentionally isolated. If a live check fails, confirm first that the screen is not in demo mode.

## Test levels

| Level | Command or action | What it proves |
| --- | --- | --- |
| Backend lint | `python -m ruff check .` | Style, imports, and obvious defects |
| Backend tests | `python -m pytest -q` | Routes, schemas, resume parsing, ingestion, workflows, SQLite persistence |
| Frontend static checks | `npm run lint`, `npm run format:check`, `npm run typecheck` | Types, lint rules, formatting, generated-type drift |
| Frontend unit/UI tests | `npm run test` | Validation, guards, error mapping, demo state rules |
| Frontend browser journeys | `npm run test:e2e` | Desktop Chromium and a 390 px mobile viewport |
| API smoke tests | `curl.exe` requests in this guide | Live contracts, status codes, CORS, key gating |
| Manual desktop pass | Checklist below | Layout, keyboard, error and empty states |
| Manual mobile pass | Emulation and a real phone | Drawer navigation, stacked layout, touch targets |
| Cross-device pass | Two browsers or two accounts | No shared local state, no secret leakage |

## 1. Prepare the environment

### Backend settings (repository-root `.env`)

Copy `.env.example` to `.env` if it does not exist. The backend reads only the root `.env`; it does not read `frontend/.env.local`.

| Variable | Required | QA value | Effect |
| --- | --- | --- | --- |
| `DATABASE_URL` | Yes | `sqlite:///./local_qa.db` | SQLAlchemy connection; the API fails to start without it |
| `DEV_JOB_WRITE_KEY` | Yes | any local string, e.g. `local-dev-key` | Development-only gate for job creation and the private feature routers; required at startup |
| `SUPABASE_URL` | No | your project URL | Derives the JWKS URL and the expected token issuer |
| `SUPABASE_JWT_SECRET` | No | legacy JWT secret | Verifies HS256 access tokens |
| `SUPABASE_JWKS_URL` | No | JWKS URL | Explicit verification keys when `SUPABASE_URL` is not set |
| `SUPABASE_JWT_ISSUER` | No | `https://<ref>.supabase.co/auth/v1` | Expected `iss` claim |
| `SUPABASE_JWT_AUDIENCE` | No | `authenticated` | Expected `aud` claim |
| `LANGGRAPH_CHECKPOINT_URL` | No | empty, or a PostgreSQL URL | Durable workflow checkpoints; unset keeps the in-process saver |
| `APP_ENV` | No | `development` | Job writes and development-key gates return `403`; candidate-scoped routers answer `401` outside development because a shared key cannot identify a user |
| `FRONTEND_URL` | No | `http://127.0.0.1:5173` | First CORS origin; must match the browser origin exactly |
| `DEBUG` | No | `false` | FastAPI debug mode; keep `false` for realistic errors |
| `RESUME_AI_ENABLED` | No | `false` | `true` sends extracted resume text to Groq |
| `GROQ_API_KEY` | No | empty | Required only when resume AI is enabled |
| `JOB_SOURCE_TIMEOUT_SECONDS` | No | `20` | Timeout for Greenhouse and Lever requests |
| `LANGCHAIN_EXPLANATIONS_ENABLED` | No | `false` | Enables the optional explanation stack |
| `APPLICATION_DRAFTS_AI_ENABLED` | No | `false` | Enables AI application drafts |

`FRONTEND_URL` is not the only allowed origin: `http://localhost:3000`, `http://127.0.0.1:3000`, `http://localhost:5173`, and `http://127.0.0.1:5173` are always allowed. Any other host, including a LAN address or a staging domain, must be set in `FRONTEND_URL` or the browser request fails the CORS check.

Never put `DEV_JOB_WRITE_KEY`, `DATABASE_URL`, `GROQ_API_KEY`, or any Supabase secret into a `VITE_*` variable. Vite inlines those values into the JavaScript bundle.

### Identity checks for local QA

Set `SUPABASE_URL` (or `SUPABASE_JWKS_URL` plus `SUPABASE_JWT_ISSUER`) in the same root `.env` to make the API verify real access tokens. With identity configured:

- A private route without a token answers `401` outside development.
- A token from another account cannot read or change your candidate; expect `404`.
- `GET /api/v1/candidates/me` returns your profile and `404` before one exists.
- An unreachable identity provider answers `503`; the API never reports the token as valid.

`backend/tests/test_auth_ownership.py` automates these cases. For a manual pass, sign in through the frontend, copy the access token, and use Swagger's **Authorize** dialog against `/api/v1/candidates/me` and a second account's candidate UUID. Details and expected codes are in [auth-and-ownership.md](auth-and-ownership.md).

### Frontend settings (`frontend/.env.local`)

Create the file from `frontend/.env.example`:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
```

| Variable | Required | Effect when absent |
| --- | --- | --- |
| `VITE_API_BASE_URL` | No | Defaults to `http://127.0.0.1:8000` |
| `VITE_SUPABASE_URL` | For accounts | Sign-in forms show a configuration message; the demo still works |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | For accounts | Same as above; publishable/anon key only |

Restart the Vite dev server after editing this file. Vite reads environment values at startup.

For Supabase sign-in, the project's Site URL must be the frontend origin and `/auth/callback` must be an allowed redirect. The local values are `http://127.0.0.1:5173` and `http://127.0.0.1:5173/auth/callback`. Use a dedicated QA Supabase project, create a test account, and confirm the verification email before sign-in tests.

Without Supabase values, only the demo is usable. The profile screen then saves to demo state and does not call the API, so live candidate CRUD cannot be checked from the UI. Test it at the API level instead (section 5).

## 2. Create a disposable local database

The Alembic chain still has the duplicate candidate revision described in [Database migrations](../README.md#database-migrations), so do not point a fresh QA run at a Supabase or production database. Create a throwaway SQLite file from the ORM metadata instead.

From the repository root in PowerShell:

```powershell
cd backend
$env:DATABASE_URL = "sqlite:///./local_qa.db"
$env:DEV_JOB_WRITE_KEY = "local-dev-key"
$env:APP_ENV = "development"
..\.venv\Scripts\python.exe -c "import app.models, app.models.candidate, app.models.skill, app.models.education, app.models.experience; from app.db.base import Base; from app.db.session import engine; Base.metadata.create_all(engine); print(len(Base.metadata.tables), 'tables')"
```

The command prints `15 tables`. The same command in Git Bash:

```bash
cd backend
DATABASE_URL="sqlite:///./local_qa.db" DEV_JOB_WRITE_KEY="local-dev-key" ../.venv/Scripts/python.exe -c "import app.models, app.models.candidate, app.models.skill, app.models.education, app.models.experience; from app.db.base import Base; from app.db.session import engine; Base.metadata.create_all(engine); print(len(Base.metadata.tables), 'tables')"
```

Delete `backend/local_qa.db` to reset all data and rerun the command. Keep this file out of commits. Set the same `DATABASE_URL` in the shell that starts the API so both use the same file; a relative SQLite path resolves against the directory the process runs in.

Do not run `alembic upgrade head` against a fresh database until the migration history is repaired.

## 3. Start both applications

Use two terminals.

Terminal 1, backend, from `backend/` so the relative SQLite path matches the file created in the previous step:

```powershell
cd backend
$env:DATABASE_URL = "sqlite:///./local_qa.db"
$env:DEV_JOB_WRITE_KEY = "local-dev-key"
$env:APP_ENV = "development"
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If you prefer the repository-root command from the main README, set `DATABASE_URL` to the same absolute path or to `sqlite:///./backend/local_qa.db`; a relative SQLite URL resolves against the process working directory.

Confirm readiness before opening the frontend:

```powershell
curl.exe -s http://127.0.0.1:8000/health
curl.exe -s http://127.0.0.1:8000/health/db
```

Expected: `{"status":"ok"}` and `{"status":"ok","database":"connected"}`. Interactive API documentation is at `http://127.0.0.1:8000/docs`. A `503` on `/health/db` means the database URL is wrong, the file is locked by another process, or the schema was never created.

Terminal 2, frontend, from the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. Keep one host form (`127.0.0.1` or `localhost`) across the browser URL, `FRONTEND_URL`, and the Supabase redirect URLs. Mixing the two creates a second browser origin with its own storage, its own CORS entry, and its own sign-in session.

## 4. Automated suites

Backend, from the repository root:

```powershell
python -m ruff check .
python -m pytest -q
python -m alembic heads
```

The current suite reports `All checks passed!` and `464 passed`. `alembic heads` must print exactly one revision (`d26auth01`). Test counts change as tests are added; treat a failure as a defect, not as a stale number.

Frontend, from `frontend/`:

```powershell
npm run lint
npm run format:check
npm run typecheck
npm run test
npm run build
npx playwright install chromium
npm run test:e2e
```

The current run reports zero lint warnings, a clean format check, 36 Vitest tests across four files, a successful production build, and four passing Playwright scenarios (two journeys in desktop Chromium and in an iPhone 13 viewport). On Windows, Prettier needs `npx prettier --check . --end-of-line auto` because the checkout uses CRLF line endings.

To prove the generated types still match the backend, regenerate and diff:

```powershell
.venv/Scripts/python.exe -B frontend/scripts/export_openapi.py
cd frontend
npm run api:types
git diff --exit-code -- src/lib/api-types.ts
```

The frontend CI workflow runs the same checks, plus the type-drift diff, on Node 24.

## 5. API-level smoke tests

These checks cover behavior the demo UI cannot reach. Use `curl.exe` in PowerShell; plain `curl` is an alias in Windows PowerShell 5 and does not accept the same flags. Every command prints the status line first.

Job search and filters:

```powershell
curl.exe -s -i "http://127.0.0.1:8000/api/v1/jobs?limit=2"
curl.exe -s -i "http://127.0.0.1:8000/api/v1/jobs?q=React&limit=5"
curl.exe -s -i "http://127.0.0.1:8000/api/v1/jobs?work_mode=remote&minimum_salary=90000&salary_currency=USD"
```

Expected: `200` with `total`, `limit`, `offset`, and `items`. A missing `salary_currency` next to `minimum_salary` must return `422`.

Job creation is gated on purpose. Both cases must be checked:

```powershell
curl.exe -s -i -X POST "http://127.0.0.1:8000/api/v1/jobs" -H "Content-Type: application/json" -d "{\"title\":\"QA Engineer\",\"company_name\":\"Example Co\",\"description\":\"Test listing\",\"job_url\":\"https://example.com/jobs/qa-1\"}"
```

Expected: `403`, because no key was sent.

```powershell
curl.exe -s -i -X POST "http://127.0.0.1:8000/api/v1/jobs" -H "Content-Type: application/json" -H "X-Dev-Job-Key: local-dev-key" -d "{\"title\":\"QA Engineer\",\"company_name\":\"Example Co\",\"description\":\"Test listing\",\"job_url\":\"https://example.com/jobs/qa-1\",\"work_mode\":\"remote\",\"salary_min\":90000,\"salary_max\":120000,\"salary_currency\":\"usd\"}"
```

Expected: `201` with the created record and an uppercase `USD`. Repeating the same `job_url` returns `409`.

Candidate, skill, and update flow. Replace the ID with the one returned by the create call:

```powershell
curl.exe -s -i -X POST "http://127.0.0.1:8000/api/v1/candidates" -H "Content-Type: application/json" -d "{\"full_name\":\"QA Candidate\",\"email\":\"qa@example.com\"}"
curl.exe -s -i "http://127.0.0.1:8000/api/v1/candidates/CANDIDATE_ID"
curl.exe -s -i -X PATCH "http://127.0.0.1:8000/api/v1/candidates/CANDIDATE_ID" -H "Content-Type: application/json" -d "{\"location\":\"Lahore\"}"
curl.exe -s -i -X POST "http://127.0.0.1:8000/api/v1/candidates/CANDIDATE_ID/skills" -H "Content-Type: application/json" -d "{\"name\":\"Python\"}"
```

Expected in order: `201`, `200`, `200` with the new location, `201` for the skill. Repeating the skill returns `409`; `DELETE` on an existing skill returns `204`; an unknown candidate returns `404`; an empty body for `PATCH` returns `400`; an invalid email returns `422`.

Private feature routers now require a verified access token. Without one, development still accepts the key gate and outside development the request is rejected:

```powershell
curl.exe -s -i "http://127.0.0.1:8000/api/v1/candidates/CANDIDATE_ID/applications"
```

Expected: `403` in development without a key, because the development gate still applies to these routers; `401` outside development, because a shared key cannot represent a user; `200` in development once you add `-H "X-Dev-Job-Key: local-dev-key"`. To check ownership itself, send `-H "Authorization: Bearer <token>"` and confirm another account's candidate answers `404`.

## 6. CORS checks

Simulate the browser preflight from the Vite origin:

```powershell
curl.exe -s -i -X OPTIONS "http://127.0.0.1:8000/api/v1/jobs" -H "Origin: http://127.0.0.1:5173" -H "Access-Control-Request-Method: GET" -H "Access-Control-Request-Headers: authorization"
```

Expected: `200`, `access-control-allow-origin: http://127.0.0.1:5173`, and `Authorization` listed in `access-control-allow-headers`.

```powershell
curl.exe -s -i "http://127.0.0.1:8000/api/v1/jobs" -H "Origin: https://evil.example"
```

Expected: `200` body, but no `access-control-allow-origin` header. If the header appears, the allowlist was replaced with a wildcard and must be restored.

## 7. Desktop checklist

Run this in a maximized window and then at 1024 px width. Use synthetic data only.

### Landing and accounts

| ID | Steps | Expected |
| --- | --- | --- |
| D1 | Open `/` | Product explanation, working account links, visible demo entry |
| D2 | Choose **Explore the demo** | Workspace opens with the sample journey; no sign-in required |
| D3 | Open `/dashboard` while signed out and not in demo | Redirect to `/login` |
| D4 | Sign in with the QA account (Supabase configured) | Protected workspace opens; reload keeps the session |
| D5 | Sign out from Settings, then open `/profile` directly | Redirect to `/login`; private query cache is cleared |
| D6 | Request a password recovery email | Success message; the delivery depends on the Supabase email provider |

### Demo journey

| ID | Steps | Expected |
| --- | --- | --- |
| D7 | Shortlists → create → select a role → approve | Confirmation is required before approval; no application is created automatically |
| D8 | Create a draft, edit the letter, save | Revision number increases and earlier text is preserved |
| D9 | Mark ready without the review checkbox | Confirm button stays disabled |
| D10 | Prepare Manual Handoff | Keeps status ready; repeating it changes no history |
| D11 | Report submission | Records a user report and states that no employer confirmation was received |
| D12 | Follow-ups: schedule, complete, dismiss | Groups move as expected; the message says no message was sent |
| D13 | Interviews: schedule, overlap, reschedule, cancel, download `.ics` | Overlaps rejected; stale version rejected; file downloads as `interview.ics` |
| D14 | Notifications | Due reminders appear; future reminders stay in the separate section |
| D15 | Settings → reset demo | Sample state returns to its initial values |

### Live data and API errors

| ID | Steps | Expected |
| --- | --- | --- |
| D16 | Open Discover jobs | Rows come from the backend; the request is visible in the network panel |
| D17 | Type a keyword, change work mode, salary, currency | URL query state updates; results narrow |
| D18 | Clear filters, then request an empty page | Empty state with a recovery action |
| D19 | Reload a `/jobs/{id}` URL | Detail page renders or shows a recovery page for an unknown ID |
| D20 | Stop the backend, then reload Discover jobs | Readable error message, no stack trace; restart and retry succeeds |
| D21 | Sign in and save a profile with one added and one removed skill | `Profile saved to the API.` No repeated `409`; reload shows the saved record |
| D22 | Upload a `.txt` or an oversized file on `/resume` | Validation message before any request |
| D23 | Open an unknown route | Accessible recovery page with a home link |

### Accessibility and security

| ID | Steps | Expected |
| --- | --- | --- |
| D24 | Tab through the workspace | Visible focus rings; skip link reaches main content |
| D25 | Open a dialog, press Escape | Focus returns to the trigger |
| D26 | Enable reduced motion in the OS | Animations are not required to understand state |
| D27 | Inspect any request in the network panel | No `X-Dev-Job-Key` header and no secret in the payload |
| D28 | Search the built assets for `DEV_JOB_WRITE_KEY`, `service_role`, `DATABASE_URL`, `GROQ` | No matches |
| D29 | Zoom to 200% | Content remains readable without overlap |

## 8. Mobile testing

### A. Automated mobile project

```powershell
cd frontend
npm run test:e2e -- --project=mobile
```

The mobile project uses the Playwright iPhone 13 descriptor at 390 x 844. Both journeys include an assertion that `scrollWidth` does not exceed the viewport width, which is the quickest automated signal for horizontal overflow.

### B. Browser device emulation

1. Open `http://127.0.0.1:5173` in Chrome or Edge, then open DevTools (`F12`).
2. Enable device toolbar (`Ctrl+Shift+M`).
3. Test three sizes: `360 x 800` (small Android), `390 x 844` (iPhone 13/14), and `768 x 1024` (tablet).
4. Enable touch simulation and reload.
5. Repeat the navigation, drawer, job filter, profile form, and dialog checks from the desktop list.

Emulation verifies layout and touch handling, not the real mobile browser engine or the on-screen keyboard.

### C. Real phone on the same network

This is the only check that covers mobile Safari/Chrome input behavior and real touch targets.

1. Find the computer's LAN address: `ipconfig`, then read the IPv4 address, for example `192.168.1.20`.
2. Allow that origin in the backend: set `FRONTEND_URL=http://192.168.1.20:5173` in the root `.env` and restart the API.
3. Point the frontend at the API on the same host: set `VITE_API_BASE_URL=http://192.168.1.20:8000` in `frontend/.env.local`.
4. Start Vite on the network interface: `npm run dev -- --host 0.0.0.0 --port 5173` from `frontend/`. Windows Firewall may ask for permission; allow private networks only.
5. Open `http://192.168.1.20:5173` on the phone.
6. Run the checks below, then revert `FRONTEND_URL`, `VITE_API_BASE_URL`, and the dev command so the loopback-only defaults return.

The Supabase project must also allow the LAN origin as a site/redirect URL if you sign in on the phone. Prefer keeping phone checks in demo mode, with job search as the live check.

### Cross-device checklist

| ID | Check | Expected |
| --- | --- | --- |
| M1 | Open every route at 360 px | No horizontal scrolling anywhere |
| M2 | Open navigation | Dismissible drawer with a visible expanded state; closes after choosing a link |
| M3 | Tap each primary action | Target is at least 44 px and reachable with a thumb |
| M4 | Discover jobs | Filters stack vertically; cards remain legible |
| M5 | Application detail | Timeline and buttons stack without overlap |
| M6 | Profile and onboarding forms | Labels visible; keyboard does not hide the active field or the submit button |
| M7 | Interview date and time inputs | Native pickers work on iOS and Android |
| M8 | Download `.ics` | File saves or opens in the calendar app |
| M9 | Rotate to landscape, then back | Layout reflows; no clipped content |
| M10 | Pull the page down to refresh | Session or demo state survives, or the app returns cleanly to the start |

## 9. Cross-device and two-session checks

| ID | Steps | Expected |
| --- | --- | --- |
| X1 | Sign in on two browsers with two different QA accounts | Each sees only its own session and local data |
| X2 | Save a profile in browser A, reload browser B | No shared demo state and no cross-account data |
| X3 | Sign out in A | B is unaffected |
| X4 | Open the app in a private window | No stale session; demo entry still works |
| X5 | Clear site data, then reload | App returns to the signed-out landing page without crashing |

The API now enforces candidate ownership, so X1-X3 can be checked end to end with two accounts once `SUPABASE_URL` and the `VITE_SUPABASE_*` values are set. Every candidate-scoped route answers `404` for another account's record; expect that, not `403`.

## 10. Known gaps

These cannot pass today and must not be reported as working:

- Live signed-in UI needs real Supabase project values and a verified test account.
- The private screens for shortlists, applications, follow-ups, interviews and notifications still read demo state, so their backend routes are reached only by API calls (`curl`/Swagger), not by the UI.
- Resume preview and import in the UI use a fixed sample; the selected file is not uploaded.
- The Alembic history cannot provision a fresh database; local QA uses ORM-created SQLite tables.
- In-memory workflow state and notification scheduling are not durable across worker restarts.
- Docker and the container workflows may be unverified on this computer; the local Python and Vite servers are the supported QA path.

## 11. Exit criteria before publishing

- Backend lint and tests pass, and `alembic heads` prints one revision.
- Frontend lint, format check, type check, unit tests, build, and both Playwright projects pass.
- Health, CORS preflight, foreign-origin rejection, and the API smoke table behave as listed.
- Desktop and mobile checklists pass with no horizontal overflow and no console errors.
- No secret appears in built assets or browser requests.
- `FRONTEND_URL` and `VITE_API_BASE_URL` are set to the real HTTPS origins, not loopback.
- Supabase site and redirect URLs match the deployed origin.
- Auth and ownership are implemented and covered by `backend/tests/test_auth_ownership.py`; two-account isolation is confirmed manually before real user data is stored.

Record the commit, date, browsers, device sizes, and any skipped check in the pull request. A missing check is reported, not marked as passed.
