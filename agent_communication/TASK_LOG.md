# Task Log

This file is append-only. Add new entries at the top or bottom consistently; current convention is newest first under this header.

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
