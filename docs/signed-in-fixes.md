# Signed-in inspection: problems found and fixed

Date: 2026-11-25
Scope: `frontend/` against the local API (`http://127.0.0.1:8000`) with a real signed-in account.

## Problems found

| # | Problem | Where | Severity |
|---|---------|-------|----------|
| 1 | Profile form always rendered empty, even though the account had 60 skills, 2 experiences and 3 education entries. Saving that empty form would have stripped the rest of the profile, because `syncSkills`/`syncExperiences`/`syncEducations` delete server rows missing from the submitted list. | `pages/Profile.tsx`, `app/workspace.tsx` | Critical (data loss) |
| 2 | "Your workspace is connected, but no profile is saved yet" banner (and the placeholder "JA" avatar) flashed on every page load, even for a fully provisioned account. `hasProfile` is `false` while the first workspace fetch is still running. | `components/layout/AppShell.tsx` | High (false alarm) |
| 3 | Creating a shortlist always produced `no_matches`. The client never sent `min_score`, so the API applied its default threshold of 50 while real scores top out around 36 for this profile. The empty shortlist page then rendered a blank table with no explanation or way forward. | `lib/live.ts`, `pages/Workflows.tsx` | High (core feature unusable) |
| 4 | A job that had been scored but had no skill overlap showed "Not scored yet — import your resume or add profile skills", which is wrong and misleading for a profile that already has skills. | `pages/Jobs.tsx` (`JobDetail`) | Medium |
| 5 | Workspace load failures were only rendered on the dashboard; every other page failed silently with empty data. | `components/layout/AppShell.tsx`, `pages/Dashboard.tsx` | Medium |
| 6 | Resume rankings did not refresh after a resume import, because the react-query key only contained the profile id and used a 60s `staleTime`. | `lib/useMatches.ts` | Medium |

## Fixes

1. `Profile` now renders a skeleton until the first workspace load finishes, so `ProfileForm` only mounts with hydrated data. It also surfaces the workspace error instead of an empty form.
2. The "no profile" banner is suppressed while `loading` is true.
3. `startWorkflow` sends `min_score: 0`, mirroring the ranked job list (`/recommendations?min_score=0`). The shortlist for this account now returns 4 roles (`pending_review`). `Workflows` renders a real empty state with links back to the job index if a shortlist is still empty.
4. `JobDetail` distinguishes "No overlap found" (scored, no shared skills) from "Not scored yet" (no profile evidence to score with).
5. The workspace error (with a "Try again" button calling `refresh()`) moved into `AppShell`, so every page reports a failed load. The duplicate dashboard alert was removed.
6. The matches query key now includes a fingerprint of the profile skills, so importing or editing skills re-ranks immediately.

## Verification

- `npm run typecheck`, `npm run lint` (0 warnings), `npm run test` (36/36), `npm run build` all pass.
- Profile page after the fix: name, email, 63 skills during the test, 2 experiences and 4 education entries all load.
- Resume upload end-to-end in the browser: drop a DOCX → `/resume/preview` (Groq) → review → "Add reviewed details" → `/resume/import` reported `3 skills, 2 roles, 1 education` created. Test rows were deleted afterwards (profile is back to 60 skills, 0 experiences, 3 educations).
- Saving the profile from the corrected form preserved all 63 skills, 2 experiences and 4 education entries (no deletions).
- Shortlist creation returns `pending_review` with 4 roles instead of `no_matches`.
- Job detail shows "No overlap found" for a scored-but-unmatched role.

## Follow-up: resume parsing always used the local fallback

### Problem

The resume upload reported "Local extraction (fallback used)" even with `RESUME_AI_ENABLED=true` and a valid `GROQ_API_KEY`. The backend log showed the real reason:

```
Groq unavailable (invalid_model_response). Local fallback activated.
```

Groq *was* called first, but `resume_groq.extract_groq` sent `max_completion_tokens: 3000`. The configured model (`openai/gpt-oss-20b`) is a reasoning model: its hidden reasoning tokens count against that same budget (about 830 of them for a short resume). For a normal resume the budget ran out mid-JSON, Groq returned HTTP 200 with `finish_reason: "length"`, and the code treated that as an unusable response. Reproduced against the live API: the same resume returned `finish_reason: "length"` at 3000 tokens and a complete, valid response at 6000.

Two visible symptoms followed:

1. The AI parser was effectively never used for real resumes.
2. The fallback was silent: the API returned a warning in `warnings`, but the profile import panel rendered only "Local extraction (fallback used)" with no explanation, and the resume page showed only a warning count.

### Fixes

1. `config.py` gains `groq_max_completion_tokens` (default `8000`) and `resume_groq.py` uses it instead of the hard-coded `3000`, leaving room for reasoning plus JSON.
2. `resume_groq.py` now reports truncation as its own reason (`response_truncated`, `finish_reason == "length"`) instead of the vague `invalid_model_response`, and re-raises `GroqUnavailable` without wrapping it.
3. `resume_analysis.py` maps each failure reason to readable text (`rate_limit` → "the AI service is rate limited") and returns a warning that names the AI parser and states that local extraction was used instead.
4. `Profile.tsx` shows that warning in an error alert whenever the local parser was used, and its progress text now says the file is being read with the AI parser. `Resume.tsx` shows the same alert next to the parser badge.

### Verification

- New backend tests cover a truncated Groq response (`response_truncated`) and that the request sends a token budget of at least 6000.
- Live Groq call with a realistic resume: 3000 tokens → `finish_reason: "length"`; 8000 tokens → `finish_reason: "stop"` with complete JSON.
- `pytest`, `npm run typecheck` and `npm run lint` pass.
