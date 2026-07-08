# Task Log

This file is append-only. Add new entries at the top or bottom consistently; current convention is newest first under this header.

## Status Update
- Agent: Codex
- Task ID: DATA-001
- Timestamp: 2026-07-08
- Current state: Done.
- Completed: Reset Firestore demo data for Firebase project `scheduler-app-54991`; preserved `users`; deleted existing non-user collections; seeded IDnow-inspired offices, skills, and 150 fictional agents.
- In progress: None.
- Blockers: None.
- Files touched:
  - `call-center-scheduler/scripts/reset_idnow_demo_firestore.py`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - `python scripts\reset_idnow_demo_firestore.py` -> dry run confirmed 1 user preserved and 5 offices/16 skills/150 agents planned
  - `python scripts\reset_idnow_demo_firestore.py --execute` -> deleted `demand_forecasts`, `offices`, `skills`; wrote 5 offices, 16 skills, 150 agents
  - Firestore verification script -> `agents=150`, `offices=5`, `skills=16`, `users=1`
- Backup: `runtime_logs\firestore-idnow-reset-backup-20260708-174419.json`
- Next step: Use the seeded data for admin UI and scheduler development; demand forecasts/schedules are intentionally empty after reset.

## Status Update
- Agent: Claude
- Task ID: FEAT-002 (review)
- Timestamp: 2026-07-08
- Current state: Review complete. Verdict: APPROVED WITH FINDINGS — no blocking issues; manual admin browser smoke remains pending (blocked on a local admin session, same as Codex reported).
- Completed: Reviewed the AdminPage/types diffs against the backend contracts (`DashboardSummary`, `ScheduleGenerationRequest/Response` in `app/models/schedule.py`), traced the scheduler and demand timezone handling, checked 401-handling regressions, verified existing admin sections are untouched, and checked docs. Ran React build and backend tests.
- Findings (ordered by severity — none blocking):
  1. Low — The post-generation "silent" refreshes are not silent on failure: `loadChart({ silent: true })` and `loadAdminSummary()` errors route through `handleApiError`, which REPLACES the "Schedule <id> generated." success alert with a danger alert (e.g. "Failed to load chart"). A successful generation can therefore present as a failure. Suggested fix direction: swallow (or log-only) non-401 errors from the silent refreshes, or keep the success alert and surface refresh failures separately.
  2. Low — Timezone semantics: the generation window is interpreted in the ADMIN'S BROWSER timezone (`datetime-local` → `toISOString()`), while daily demand slots are built in each OFFICE'S timezone (`catalog_service` combines the date in office tz, stores UTC). These align when the admin's browser tz equals the office tz (current usage), but for an office in another timezone the default midnight-to-midnight window will not match that office's demand day. Backend `_as_utc` normalizes everything, so there is no crash — just possible partial windows. Suggest a one-line USER_MANUAL note now; office-tz-aware windowing is a future enhancement.
  3. Info — Assignment table's "Time" column shows only `slot_start`; showing the start–end range would be clearer. UX nit.
  4. Info — If generation fails, the previous `scheduleResult` stays visible beneath the error alert (stale result). Acceptable; nit.
  5. Info — Branch hygiene: FEAT-002 was developed on the `codex/invalid-token-redirect` branch working tree. Commit FEAT-002 as its own scoped commit (or branch) so history stays reviewable.
  6. Info (positive) — The init effect now skips non-admin users (`user?.role !== "admin"` guard), eliminating the previous doomed-to-403 API burst while the role-guard redirect ran. Nice hardening beyond scope.
- Review-goal confirmations:
  1. Admin Summary matches `DashboardSummary`: confirmed — `types.ts` mirrors the Pydantic model field-for-field; required/assigned/gap/ratio aggregates are computed client-side from `coverage_points` (the backend sends no aggregates), with a divide-by-zero guard on the ratio.
  2. Request matches `ScheduleGenerationRequest`: confirmed — `{ start_at, end_at }` as ISO strings; frontend validates parseability and end > start (backend re-validates too).
  3. Result UI matches `ScheduleGenerationResponse`: confirmed — schedule_id/total_required/total_assigned/uncovered_demand shown; per-row assigned count correctly derived from `assigned_agent_ids.length` (no `assigned` field exists per row); office/skill ids mapped to names with id fallback.
  4. 401 handling not regressed: confirmed — `loadAdminSummary`, `generateSchedule`, and the silent chart refresh all route through `handleApiError` → `handleUnauthorized`; `sessionInvalid` null-render still intact.
  5. Existing sections not broken: confirmed — diff is additive; `loadChart(options = {})` signature change is backward-compatible with all existing zero-arg call sites; summary refresh joins existing `Promise.all`s after create actions; demand builder, CSV upload, preview untouched.
  6. Loading/empty/error states: present — summary has loading/data/unavailable branches plus a no-coverage-points message; generation has a disabled-while-loading button, a pre-result hint, and a no-assignment-rows message; backend 400s ("No demand rows for selected window") surface via the error alert.
  7. Docs and task log accurate: confirmed — PROJECT_DOCS gained the FEAT-002 task row; USER_MANUAL's schedule-generation workflow matches the new UI; files-touched matches `git status` (`vite.config.ts` diff is line-endings only, correctly declared out of scope).
- Commands/tests run:
  - `npm run build` (react-app) -> passed (tsc + vite; pre-existing >500 kB chunk-size warning, cosmetic)
  - `python -m pytest backend/tests` -> 4 passed
- Manual smoke status: NOT RUN — same blocker as Codex (no valid local admin session in the browser). Still needed: log in as admin, confirm summary loads, generate a schedule for a window with saved demand, confirm results and silent chart refresh.
- Recommended next step: Codex commits FEAT-002 as a scoped commit, applies or backlogs finding 1 (success-alert clobbering) and the finding 2 manual note; user runs the admin-session smoke test.

## Status Update
- Agent: Codex
- Task ID: FEAT-002 admin schedule summary UI
- Timestamp: 2026-07-08 19:33:43 +02:00
- Current state: Implementation complete; automated verification passed; browser smoke is blocked by missing local admin session.
- Completed:
  - Added React Admin Summary UI that loads `GET /api/v1/dashboard/summary` on admin page load and displays total agents, offices, skills, active schedules, coverage points, required, assigned, gap, and aggregate coverage ratio.
  - Added React Schedule Generation UI with start/end datetime inputs, a Generate button for `POST /api/v1/schedules/generate`, result counters, and assignment rows showing office, skill, time, required, assigned, gap, and coverage ratio.
  - Refreshed admin summary after office/skill/agent changes and after schedule generation; refreshed the existing demand coverage graph silently after generation when graph filters are present.
  - Preserved existing demand builder, CSV upload, data preview, and demand graph behavior.
  - Updated `PROJECT_DOCS.md` and `USER_MANUAL.md`.
- Files touched:
  - `react-app/src/pages/AdminPage.tsx`
  - `react-app/src/types.ts`
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/USER_MANUAL.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - `npm run build` from `react-app` -> passed
  - `python -m pytest backend\tests` from `call-center-scheduler` -> 4 passed
  - Local server checks: `http://127.0.0.1:5173/` -> 200; `http://127.0.0.1:8000/api/health` -> 200
  - Browser auth check: opening `http://127.0.0.1:5173/admin` redirected to login because there is no valid admin session in the browser.
- Open issues:
  - Manual smoke "open admin, load summary, generate schedule for a date range with demand" still needs to be run after the user signs in locally with an admin account.
  - Pre-existing runtime log changes, `runtime_logs/**`, and `react-app/vite.config.ts` remain outside this task scope and were not modified intentionally.
- Next step: Claude/user review the React admin UI; then run the admin-session smoke test with valid local credentials.

## Status Update
- Agent: Codex
- Task ID: AUTH-INVALID-TOKEN-REDIRECT closeout
- Timestamp: 2026-07-08
- Current state: Closeout complete.
- Completed:
  - Committed approved AUTH-INVALID-TOKEN-REDIRECT work as `127ff2d5ab7c5070cda9ec10f200c7ec33e6d599` on branch `codex/invalid-token-redirect`.
  - Added backlog-only follow-ups to `PROJECT_DOCS.md`:
    - Treat `403` "User is disabled" and `404` "User profile not found" from `get_current_user` as frontend session-ending responses.
    - Wrap `syncSession` in `useCallback` in `react-app/src/App.tsx`; optionally add an `active` cancellation guard to `AdminPage` initialization.
- Files touched:
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - Before commit: `npm run build` from `react-app` -> passed
- Open issues: Backlog items recorded only; not implemented in this task.
- Next step: User chooses whether to implement one of the backlog items or hand the branch off for merge.

## Status Update
- Agent: Claude
- Task ID: AUTH-INVALID-TOKEN-REDIRECT (review)
- Timestamp: 2026-07-08
- Current state: Review complete. APPROVED — all acceptance criteria met; no blocking findings.
- Completed: Reviewed api.ts, DashboardPage, AdminPage, ProtectedRoute, App.tsx, and the task log entry. Ran React build and verified the backend 401 contract with TestClient.
- Findings (ordered by severity — none blocking):
  1. Low — Session-ending statuses other than 401 are not handled: a 403 "User is disabled" or 404 "User profile not found" from `get_current_user` leaves the user inside the protected shell with an error banner and a stored-but-useless token. Both are real "your session is no good" cases for a deactivated/deleted user. Out of this task's scope (which specified 401), but suggest a backlog item to treat them like invalid sessions.
  2. Info — `DashboardPage`/`AdminPage` data-loading effects depend on `handleUnauthorized`/`handleApiError`, whose identity chains to `onSessionChange` (`syncSession` in App.tsx is recreated on every App render). Safe today because App only re-renders on session change, which immediately navigates away — but if App ever gains unrelated state, these effects will silently re-run and refetch everything. One-line hardening: wrap `syncSession` in `useCallback`. Optional.
  3. Info — AdminPage's init effect has no `active`/cancelled guard (DashboardPage has one). Post-unmount setState is a no-op in React 18, so harmless; consistency nit only.
- Review-goal confirmations:
  1. Auth cleared on protected 401s: confirmed at two layers — `apiRequest` calls `clearAuth()` for any `auth: true` 401 (so `ccs_id_token`/`ccs_user` leave localStorage even if a caller forgets to handle the error), and page-level `handleUnauthorized` clears app state via `onSessionChange`.
  2. Redirect + shell suppression: confirmed — both pages set `sessionInvalid`, render `null`, and `navigate("/", { replace: true })`; no error banner renders for the 401 case because `handleApiError`/the dashboard catch return early for unauthorized errors.
  3. Public auth calls unaffected: confirmed — login/register use `auth: false`, so a wrong-password 401 does NOT clear storage and still shows the form error; logout intentionally ignores failure and clears anyway.
  4. No infinite loop / races: confirmed — redirect is one-way (cleared token means ProtectedRoute and AuthPage both resolve to the login view; `clearAuth` is idempotent). Audited every `apiRequest` call site in AdminPage: all protected calls route through `handleApiError` (init, create office/skill/agent, demand grid, daily forecast save, CSV upload, chart, and the reload helpers which are only called inside those try blocks).
  5. Valid session path intact: confirmed by code review (2xx path in `apiRequest` unchanged) and passing build; Codex's Chrome automation evidence covers runtime. Backend contract verified live: TestClient shows 401 for missing and invalid tokens on `/me/dashboard` and `/offices`, matching the frontend's 401-only check.
  6. Task log accurate: confirmed — files-touched list matches `git diff` (App.tsx/ProtectedRoute correctly untouched), and claimed behavior matches the implementation.
- Commands/tests run:
  - `npm run build` (react-app) -> passed (tsc + vite)
  - Backend TestClient: `GET /api/v1/me/dashboard` no token -> 401; invalid token -> 401; `GET /api/v1/offices` invalid token -> 401
- Blockers: None. Task can be considered done and committed.
- Next step: Codex commits the work. Optional backlog: handle 403-disabled/404-missing-profile as session-ending (finding 1); `useCallback` around `syncSession` (finding 2).

## Status Update
- Agent: Codex
- Task ID: AUTH-INVALID-TOKEN-REDIRECT
- Timestamp: 2026-07-08
- Current state: Done.
- Completed:
  - Added typed `ApiError` handling in `react-app/src/lib/api.ts`.
  - Protected API calls now clear saved auth when they receive HTTP 401.
  - DashboardPage and AdminPage now treat 401 as an invalid session, clear app auth state, redirect to `/`, and suppress protected shell/error rendering.
  - AdminPage protected API error handling is centralized so load, create, upload, save, and chart actions all handle expired tokens consistently.
- Files touched:
  - `react-app/src/lib/api.ts`
  - `react-app/src/pages/DashboardPage.tsx`
  - `react-app/src/pages/AdminPage.tsx`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - `npm run build` from `react-app` -> passed
  - Manual invalid-token check with Chrome automation:
    - Seeded invalid `ccs_id_token` and user in localStorage, opened `/dashboard` -> redirected to `/`, auth storage cleared, login shown, protected shell/API error absent.
    - Seeded invalid `ccs_id_token` and user in localStorage, opened `/admin` -> redirected to `/`, auth storage cleared, login shown, protected shell/API error absent.
- Backend tests: Not run; backend code was not touched.
- Open issues: None for this task.
- Next step: Optional review/commit when approved.

## Status Update
- Agent: Codex
- Task ID: AUTH-ADMIN-DASHBOARD-DEFAULT closeout
- Timestamp: 2026-07-08
- Current state: Closeout complete.
- Completed:
  - Committed approved AUTH-ADMIN-DASHBOARD-DEFAULT work as `b183d6de94e6bea09b3f68ac6503c73076718a9e`.
  - Added backlog-only follow-ups to `PROJECT_DOCS.md`:
    - Decide whether `GET /api/v1/dashboard/summary` should be admin-only.
    - Add frontend test infrastructure for React routing guards.
    - Consider admin-specific dashboard copy for admins with no agent profile.
- Files touched:
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - Before commit: `python -m pytest backend\tests` -> 4 passed
  - Before commit: `npm run build` -> passed
- Open issues: Backlog items recorded only; not implemented in this task.
- Next step: User chooses the next backlog or feature item to implement.

## Status Update
- Agent: Claude
- Task ID: AUTH-ADMIN-DASHBOARD-DEFAULT (review)
- Timestamp: 2026-07-08
- Current state: Review complete. APPROVED — task meets all stated acceptance criteria; no blocking findings.
- Completed: Reviewed AuthPage, DashboardPage, ProtectedRoute, AdminPage, App.tsx routing, me_service.py, the new backend test, and doc updates. Ran backend tests and React build.
- Findings (ordered by severity — none blocking):
  1. Low — Frontend role checks read `user.role` from localStorage, so a user can force the `/admin` UI shell open by editing local storage. Not exploitable: every admin API endpoint is protected server-side by `require_admin` (verified across offices/skills/agents/demand/schedules routers), so a spoofed client gets only empty tables and 403s. No action needed; noting so nobody mistakes the client guard for a security boundary.
  2. Low — Pre-existing, not from this task: `GET /api/v1/dashboard/summary` requires only authentication, not admin, so agents can read operational coverage metrics. Flagging for a product decision in the backlog; out of scope here.
  3. Low — Missing-test observations: `test_me_dashboard_access.py` covers the admin-payload case well, but there is no test that a non-agent/agent role distinction is enforced anywhere else, and the React app has no test infrastructure, so routing guards (ProtectedRoute redirect behavior) are verified only by inspection/build. The test also constructs `MeService` via `object.__new__` (bypassing `__init__`); it will break loudly if `dashboard()` gains a new repo dependency — acceptable, just brittle.
  4. Info — Minor UX: an admin with no agent profile sees "You have a day off today" and a "-" shift card. Consistent with the accepted decision (D-20260708-006) that admins get a generic personal dashboard; mention in case the user wants friendlier admin-specific copy later.
- Review-goal confirmations:
  1. Admins no longer auto-routed to `/admin`: confirmed — AuthPage sends all users (login, register, existing session) to `/dashboard`; DashboardPage contains no role-based redirect.
  2. Admins can still reach `/admin`: confirmed — `requireAdmin` guard passes admins; Admin Panel button renders in the dashboard navbar for `role === "admin"`; AdminPage has a Dashboard link back.
  3. Non-admins blocked from `/admin`: confirmed at three layers — ProtectedRoute redirects to `/dashboard`, AdminPage has a belt-and-braces useEffect redirect, and all admin API endpoints enforce `require_admin` (403) server-side.
  4. Backend dashboard behavior safe and tested: confirmed — `MeService.dashboard` degrades gracefully with no agent profile (no crash, own-profile resolution only, no cross-user exposure); covered by `test_me_dashboard_access.py`; the previously unattributed me_service.py change is now owned by decision D-20260708-006. Prior ARCH-002 review finding 1 is CLOSED.
  5. Docs in sync: confirmed — PROJECT_DOCS has D-20260708-006 (Accepted, Owner: User) and RISK-007; USER_MANUAL Dashboard and new Admin Access sections match the implemented behavior.
- Commands/tests run:
  - `python -m pytest backend/tests` -> 4 passed
  - `npm run build` (react-app) -> passed (tsc + vite)
- Blockers: None. Task can be considered done.
- Next step: Nothing required from Codex for this task. Optional backlog candidates: decide whether `/api/v1/dashboard/summary` should be admin-only (finding 2) and add basic frontend routing tests (finding 3).

## Status Update
- Agent: Codex
- Task ID: AUTH-ADMIN-DASHBOARD-DEFAULT
- Timestamp: 2026-07-08
- Current state: Done.
- Completed:
  - Changed React login/register and existing-session behavior so authenticated users, including admins, land on `/dashboard` by default.
  - Removed the dashboard page redirect that forced admins from `/dashboard` to `/admin`.
  - Added an Admin Panel button on the dashboard for users with `admin` role, preserving access to admin functionality.
  - Kept `/admin` protected: non-admin users are still redirected to `/dashboard`.
  - Accepted and documented the product decision that admins may use the normal personal dashboard; this resolves the prior `me_service.py` open question.
  - Added backend coverage proving an admin user can receive a generic personal dashboard payload.
- Files touched:
  - `react-app/src/pages/AuthPage.tsx`
  - `react-app/src/pages/DashboardPage.tsx`
  - `call-center-scheduler/backend/app/services/me_service.py`
  - `call-center-scheduler/backend/tests/test_me_dashboard_access.py`
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/USER_MANUAL.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - `python -m pytest backend\tests` -> 4 passed
  - `npm run build` -> passed
  - Route audit via `Select-String` confirmed no remaining automatic admin-to-`/admin` login/session/dashboard redirect; only the intended `/admin` access guard remains.
- Open issues: None for this task. Runtime logs and Firebase backup remain uncommitted local runtime data from earlier work.
- Next step: Review in browser with an admin account and continue with the next approved task.

## Status Update
- Agent: Codex
- Task ID: ARCH-002 closeout
- Timestamp: 2026-07-08
- Current state: Closeout complete; ARCH-002 baseline committed.
- Completed:
  - Resolved Claude finding 2 by adding a `USER_MANUAL.md` troubleshooting note that FastAPI mounts `/assets` only at startup.
  - Resolved Claude finding 3 by recording SPA catch-all need as `RISK-006` and backlog item in `PROJECT_DOCS.md`.
  - Diagnosed the user's browser screenshot: the live backend process was still running old code that served deleted `call-center-scheduler\frontend\dashboard.html`, causing `RuntimeError: File at path ... dashboard.html does not exist` and HTTP 500.
  - Restarted the process listening on port 8000; `http://127.0.0.1:8000/dashboard` now returns React HTML with HTTP 200.
  - Inspected `runtime_logs\firebase-clear-backup-20260708-164847.json`; no private-key/API-key/token/password markers were found, but it contains `email` and name fields, so it is treated as PII-bearing runtime data and left uncommitted.
  - Committed ARCH-002 baseline as `0f9987c784e9e195166895ea27f1adac4be93e68`.
- Finding 1 resolution: `call-center-scheduler/backend/app/services/me_service.py` was already modified before Codex's ARCH-002 work and is not attributable from current project notes. Per protocol, Codex did not guess, did not revert, and did not include it in the ARCH-002 commit. User decision needed: keep/document/test the new non-agent dashboard behavior, or revert the role-check removal.
- Files changed after Claude review:
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/USER_MANUAL.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - `python -m pytest backend\tests` -> 3 passed
  - `npm run build` -> passed
  - FastAPI TestClient smoke: `/api/health`, `/`, `/dashboard`, `/admin`, and `/assets/index-DHVjkXxo.js` -> all 200
  - Live server check: `GET http://127.0.0.1:8000/api/health` -> 200; `GET http://127.0.0.1:8000/dashboard` -> 200 React HTML
- Blockers: Open user decision on `me_service.py` authorization behavior.
- Next step: User decides whether to keep or revert the unattributed `me_service.py` change before broader QA/new feature work.

## Status Update
- Agent: Claude
- Task ID: ARCH-002 (review)
- Timestamp: 2026-07-08
- Current state: Review of the React-only frontend migration complete. Approved with one open question (see findings).
- Completed: Reviewed removal of `call-center-scheduler/frontend`, backend serving logic, config, Dockerfile, docker-compose, Vite proxy setup, and active docs. Ran backend tests, React build, and a FastAPI serving smoke test.
- Blockers: None for new development; finding 1 should be resolved first or explicitly accepted.
- Findings (ordered by severity):
  1. Medium — `backend/app/services/me_service.py` removes the agent-role 403 check from `MeService.dashboard` (`GET /api/v1/me/dashboard` now returns a generic/empty dashboard for any authenticated user instead of 403 for non-agents). This file is NOT listed in the ARCH-002 task log entries, so the change is unattributed and undocumented. It degrades gracefully (no crash, no cross-user data exposure — `_resolve_agent_profile` only resolves the caller's own profile), but it is an authorization behavior change that needs an owner decision: intentional (then document + test it) or leftover (then revert).
  2. Low — `app/main.py` mounts `/assets` only if `react-app/dist/assets` exists at process start. If the backend starts before `npm run build`, assets 404 until the backend restarts. Worth a troubleshooting note; no code change required.
  3. Low — FastAPI serves only `/`, `/dashboard`, `/admin` (no SPA catch-all). This exactly matches the current React routes in `react-app/src/App.tsx`, so no bug today, but any future React route will 404 on direct navigation via port 8000.
  4. Info — `docker compose config` could not be run (docker not on PATH in this environment). Dockerfile/compose reviewed statically: build context `..` + root `.dockerignore` are consistent, COPY paths resolve, and `/app/react-app/dist` matches the path candidates in `app/main.py`. No issues found, but Docker build remains unverified at runtime.
  5. Info — Worktree hygiene: all ARCH-002 changes are still uncommitted on `main`; `runtime_logs/` contains modified logs and an untracked `firebase-clear-backup-20260708-164847.json`. Per RISK-004, verify that backup contains no secrets/PII and keep logs/backups out of any commit.
- Scope confirmations:
  - `call-center-scheduler/frontend` removal is intentional and complete (git `D` entries; no orphan files).
  - Active docs (PROJECT_DOCS, USER_MANUAL, README, TEST_PROTOCOL, QA_HANDOFF_REPORT) consistently state React/Vite is the only frontend; remaining old-frontend references are in historical QA/handoff docs only, which is acceptable.
  - Backend works as API server; FastAPI serves `react-app/dist` after `npm run build` (verified via TestClient: `/` 200 HTML, `/dashboard` 200, `/assets/*.js` 200 with correct content type).
  - Vite config: port 5173, `/api` proxied to `http://127.0.0.1:8000`. Confirmed.
- Commands/tests run:
  - `python -m pytest backend/tests` -> 3 passed
  - `npm run build` (react-app) -> passed (tsc + vite)
  - FastAPI TestClient smoke: `/api/health` 200, `/` 200, `/dashboard` 200, `/assets/index-DHVjkXxo.js` 200
  - `docker compose config` -> not run (docker unavailable)
- Verdict: Clear to begin new implementation. Recommended first actions: (a) Codex or user attributes/decides finding 1, (b) commit the ARCH-002 worktree (excluding runtime logs/backups) so future diffs are reviewable.
- Next step: User/Codex responds to finding 1; then proceed with QA-001 or the first development task.

## Status Update
- Agent: Codex
- Task ID: ARCH-002
- Timestamp: 2026-07-08
- Current state: Done.
- Completed: Removed legacy `call-center-scheduler/frontend`, switched FastAPI/Docker docs and runtime wiring to React/Vite, updated active QA guidance, and verified the React build.
- In progress: None.
- Blockers: None.
- Files touched:
  - `.dockerignore`
  - `call-center-scheduler/backend/app/main.py`
  - `call-center-scheduler/backend/app/core/config.py`
  - `call-center-scheduler/backend/Dockerfile`
  - `call-center-scheduler/docker-compose.yml`
  - `call-center-scheduler/README.md`
  - `call-center-scheduler/QA_HANDOFF_REPORT.md`
  - `call-center-scheduler/TEST_PROTOCOL.md`
  - `call-center-scheduler/frontend/*` removed
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/USER_MANUAL.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - `python -m pytest backend\tests` -> 3 passed
  - `npm run build` -> passed
  - `python -m py_compile backend\app\main.py backend\app\core\config.py` -> passed
- Next step: Use React/Vite for all frontend development.

## Status Update
- Agent: Codex
- Task ID: ARCH-002
- Timestamp: 2026-07-08
- Current state: React frontend accepted as the only UI path.
- Completed: Updated backend serving logic, Docker build wiring, README, shared project docs, and user manual to use React/Vite instead of the legacy static frontend.
- In progress: Removing legacy `call-center-scheduler/frontend` files and running focused verification.
- Blockers: None.
- Files touched:
  - `.dockerignore`
  - `call-center-scheduler/backend/app/main.py`
  - `call-center-scheduler/backend/app/core/config.py`
  - `call-center-scheduler/backend/Dockerfile`
  - `call-center-scheduler/docker-compose.yml`
  - `call-center-scheduler/README.md`
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/USER_MANUAL.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run: Pending verification.
- Next step: Delete legacy frontend files and run backend unit tests plus React build.

## Status Update
- Agent: Codex
- Task ID: DOC-001
- Timestamp: 2026-07-08
- Current state: Collaboration protocol and shared documentation structure drafted.
- Completed: Added shared AI entrypoints, protocol, project hub, handoff templates, task log, and user manual draft.
- In progress: Awaiting user approval or requested changes.
- Blockers: None.
- Files touched:
  - `AGENTS.md`
  - `CLAUDE.md`
  - `agent_communication/COLLABORATION_PROTOCOL.md`
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/TASK_LOG.md`
  - `agent_communication/HANDOFF_TEMPLATE.md`
  - `agent_communication/USER_MANUAL.md`
- Commands/tests run: Workspace inspection and documentation review only; no application tests run.
- Next step: User approves the workflow or requests edits before development begins.
