# Production readiness: live workspace and release checklist

This page answers why the signed-in workspace showed sample data, records the changes that removed
that limitation, and lists what still stands between this checkout and a production release.

## 1. Why everything was set to demo

Three separate things combined to produce the "Private workspace access is pending" message:

1. **The route guard, not the API, blocked private screens.** `frontend/src/app/router.tsx`
   wrapped every private page in `DemoOnly`, which rendered its children only when
   `useAuth().demo` was true. A verified account therefore always saw the notice, while an
   anonymous visitor who chose "Explore the demo" saw the workspace.
2. **The private screens read from an in-memory sample store.** Dashboard, shortlists,
   applications, follow-ups, interviews, and notifications called `useDemo()` from
   `frontend/src/app/store.tsx`, which is seeded from `frontend/src/lib/demo.ts`. Every count,
   draft, follow-up, and interview on those screens was local sample state, cleared on reload.
3. **The notice was already out of date.** The FastAPI backend had ownership enforcement
   (`backend/app/core/auth.py`, `candidate_profiles.owner_id`, `/api/v1/candidates/me`,
   `require_candidate_owner`), and `docs/auth-and-ownership.md` documents it. Only the browser
   client was missing, so the copy "the API does not yet verify account ownership" was stale.

One further configuration gap mattered: the backend `.env` had no `SUPABASE_URL`, so identity
verification was not configured. Any bearer token was answered with `503`, which made real accounts
unusable even after the route guard was removed.

## 2. What changed in this pass

### Frontend: a real workspace data layer

| File | Change |
| --- | --- |
| `frontend/src/lib/live.ts` (new) | Loads the account profile, skills, experience, education, public jobs, applications, follow-ups, interviews, notifications, and saved workflows from the ownership-scoped API. Maps API records to the shapes the screens already render. Contains the write helpers for every workspace action, profile synchronization (skills, experience, education), resume preview/import, and notification handling. |
| `frontend/src/app/workspace.tsx` (new) | `WorkspaceProvider` / `useWorkspace()`. Serves live account data when a Supabase session exists, keeps the in-memory demo as an explicit opt-in, exposes `loading`, `error`, `hasProfile`, and one async action per workspace operation. |
| `frontend/src/app/router.tsx` | Removed `DemoOnly` and `ApiCandidatePage`. Every private route renders for a verified account. The demo is still reachable from the landing/auth screens. |
| `frontend/src/pages/Dashboard.tsx` | Live counts, loading state, API error display, and an onboarding call to action when the account has no profile. |
| `frontend/src/pages/Workflows.tsx` | Shortlists start, review, and draft creation call `POST /candidates/{id}/workflows`, `/review`, and `/tracked-applications/{jobId}`. |
| `frontend/src/pages/Applications.tsx` | Application list and detail use API records, revisions, and status history. Save, status changes, and manual handoff call the API. |
| `frontend/src/pages/FollowUps.tsx` | Scheduling and resolving use the follow-up routes; grouping stays client-side. |
| `frontend/src/pages/Interviews.tsx` | Create, reschedule, cancel, and complete call the interview routes with version numbers. |
| `frontend/src/pages/Notifications.tsx` | Loads server reminders, requests a processor run, and marks reminders read through the API. |
| `frontend/src/pages/Resume.tsx` | Signed-in uploads call `POST /resume/preview` (multipart) and `POST /resume/import` with explicit approval; the demo keeps its fixed sample. |
| `frontend/src/pages/Profile.tsx` | Saves the profile plus skills, experience, and education to the API; the form remounts when the account record resolves. |
| `frontend/src/components/layout/AppShell.tsx` | Removed the stale "access unavailable" notice; unread count and initials come from workspace state; a missing profile links to onboarding. |
| `frontend/src/lib/demo.ts` | Workflow scoring metadata and the server identifier for API reminders (demo behavior unchanged). |
| `frontend/src/test/ui.test.tsx` | Test wrapper mounts `WorkspaceProvider`; assertions unchanged. |

### Configuration

- `SUPABASE_URL` was added to the repository-root `.env` (the public project URL, read from the
  frontend configuration). Verified locally: `identity_configured = True`, issuer
  `https://<project>.supabase.co/auth/v1`, JWKS returned `200` with one signing key. Access tokens
  sent from the browser are now verified instead of rejected with `503`.

### Behavior that is now real

- Shortlist generation and approval, tracked applications, draft revisions, status history,
  manual handoff preparation, follow-ups, interviews, reminders, resume preview/import, and the
  profile (with skills, experience, and education) persist per account.
- Ownership is enforced server-side. A record that belongs to another account answers `404`, so
  the client cannot read or change it by guessing an identifier.
- The demo remains isolated: it never sends API writes and is clearly labelled.

## 3. Production checklist

Status legend: **Done** = implemented and checked in this pass; **Action required** = external
configuration or a code gate that still needs work; **Not started** = no implementation yet.

### Live workspace (this pass)

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Remove the demo-only route gate | Done | `frontend/src/app/router.tsx` |
| 2 | Load profile and account records from the API | Done | `frontend/src/lib/live.ts` |
| 3 | Wire every private mutation to an ownership-scoped route | Done | `frontend/src/app/workspace.tsx` |
| 4 | Resume preview/import from the browser | Done | `frontend/src/pages/Resume.tsx` |
| 5 | Onboarding path for accounts without a profile | Done | Dashboard and AppShell links to `/onboarding` |
| 6 | Keep the demo as an explicit, isolated mode | Done | `DemoProvider` + `useWorkspace()` |
| 7 | Backend token verification configured | Done | `SUPABASE_URL` set; JWKS `200` with one key |
| 8 | Frontend checks | Done | typecheck, ESLint (0 warnings), Prettier, 36 Vitest tests, production build |

### Database and background work

| # | Item | Status | Notes |
| --- | --- | --- | --- |
| 9 | Repair duplicate Alembic revisions `fa05578eada4` and `5b0bd740df7a` | Not started | Both create `candidate_profiles`; a clean database cannot reach head. Reproduce on a throwaway PostgreSQL database before touching real data. |
| 10 | Verify the `owner_id` migration (`d26auth01`) up and down | Not started | The ownership code depends on this column. |
| 11 | Align migration columns and constraints with the ORM models | Not started | Candidate table and job/application constraints drift. |
| 12 | Set `LANGGRAPH_CHECKPOINT_URL` | Action required | Without it, workflow checkpoints live in process memory and a restart can lose a pending shortlist. |
| 13 | Add a clean-database upgrade/downgrade test to CI | Not started | Prerequisite for item 9. |

### Runtime and deployment configuration

| # | Item | Status | Notes |
| --- | --- | --- | --- |
| 14 | Set the production HTTPS origin in `FRONTEND_URL` and the backend CORS list | Action required | Only `localhost`/`127.0.0.1` ports 3000 and 5173 plus `FRONTEND_URL` are allowed today. |
| 15 | Set Supabase Site URL and redirect URLs to the production origin | Action required | Includes `/auth/callback`. Must match the browser origin exactly. |
| 16 | Set `APP_ENV` away from `development` for the deployed API | Action required | The development key must be refused in production. |
| 17 | Deploy the frontend build and the API image over HTTPS | Action required | `frontend/dist` on a static host with SPA fallback and `_headers`; API via `compose.yaml` behind TLS. No host has been chosen. |
| 18 | Rotate `DEV_JOB_WRITE_KEY`, `SECRET_KEY`, and database credentials | Action required | Values currently come from the local `.env`. |
| 19 | Confirm transactional email delivery and rate limits | Action required | Signup confirmation and recovery depend on the Supabase email provider. |

### Security, privacy, and operations

| # | Item | Status | Notes |
| --- | --- | --- | --- |
| 20 | Two-account staging test (own records visible, foreign records `404`) | Action required | `backend/tests/test_auth_ownership.py` covers this at the API level; it has not been run against the live project with two real accounts. |
| 21 | Privacy policy, retention, and deletion | Not started | There is no account export or deletion endpoint; document retention before storing real resumes. |
| 22 | Rate limiting and abuse controls | Not started | No limits on auth-gated mutation routes. |
| 23 | Logging, error reporting, and backups | Not started | No hosted monitoring or database backup schedule is configured. |
| 24 | Browser check of the deployed origin | Action required | Repeat the flows after deployment: sign in, profile save, shortlist, draft revision, follow-up, interview, reminders. |

## 4. How to verify the live workspace locally

Backend (repository root):

```powershell
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm run dev
```

Then:

1. Sign in with a verified account (or create one and follow the confirmation link).
2. Open `/onboarding` and save a profile. Confirm the API returns the profile at
   `GET /api/v1/candidates/me`.
3. Create a shortlist, approve a role, create its draft, save a revision, mark it ready, and
   prepare a manual handoff. Each step is a separate API call documented in `/docs`.
4. Report a submission, schedule a follow-up and an interview, and use the notifications check.
5. Sign out and sign in as a second account. Its workspace must be empty, and the first account's
   application identifier must answer `404`.
6. Choose "Explore the demo" from the landing page to confirm the sample workspace still works and
   never calls the private API.

Checks run for this change:

```powershell
cd frontend
npm run typecheck
npm run lint
npm run format:check
npm run test
npm run build
```

Results: TypeScript passed, ESLint reported no findings, Prettier reported no drift, Vitest passed
36 tests, and the production build succeeded. Browser flows and a live two-account run were not
performed here.

## 5. Release decision

The demo/ownership gate is closed: a verified account now reads and writes its own records through
the API, and the backend verifies tokens with a configured JWKS. The project is **not** production
ready until items 9–24 are complete. The blocking code work is the database migration repair
(items 9–11); everything else is deployment configuration, external account settings, or policy.
