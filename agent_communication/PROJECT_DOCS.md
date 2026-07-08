# Project Documentation Hub

Last updated: 2026-07-08

## Project Overview

The application is a call center scheduler for a 24/7/365 multi-office operation. It supports authentication, role-based workflows, admin data management, demand forecasting, schedule generation, and dashboard coverage reporting.

Current known project root:

- Workspace: `C:\Users\User\Desktop\web projekt`
- Backend app: `C:\Users\User\Desktop\web projekt\call-center-scheduler`
- Primary frontend app: `C:\Users\User\Desktop\web projekt\react-app`

## Architecture

Current accepted architecture:

- Frontend: React, Vite, TypeScript, Bootstrap 5, and Chart.js under `react-app`
- Backend: Python FastAPI under `call-center-scheduler/backend`
- Auth and database: Firebase Authentication and Firestore
- API style: JSON REST API under `/api/v1/...`
- Development frontend serving: Vite dev server on `http://localhost:5173`, proxying `/api` to FastAPI
- Production-style frontend serving: FastAPI can serve the compiled React build from `react-app/dist`
- Scheduling: backend heuristic scheduler service
- QA: documented manual/API regression protocol in `call-center-scheduler/TEST_PROTOCOL.md`

Deprecated architecture:

- The former vanilla HTML/CSS/JS frontend under `call-center-scheduler/frontend` is removed and should not receive new work.

## Tech Stack

| Area | Current stack | Notes |
|---|---|---|
| Backend | Python, FastAPI, Pydantic | Located in `call-center-scheduler/backend` |
| Database | Firestore | Requires Firebase project and service account |
| Authentication | Firebase Authentication | Email/password flow documented |
| Frontend | React, Vite, TypeScript, Bootstrap 5, Chart.js | Located in `react-app`; accepted primary UI |
| Testing | Pytest, documented QA checklist | `requirements-dev.txt` and `TEST_PROTOCOL.md` |
| Local run | Uvicorn, optional Docker Compose | See `README.md` and `USER_MANUAL.md` |

## File Structure

```text
C:\Users\User\Desktop\web projekt\
  AGENTS.md
  CLAUDE.md
  agent_communication/
    COLLABORATION_PROTOCOL.md
    PROJECT_DOCS.md
    TASK_LOG.md
    HANDOFF_TEMPLATE.md
    USER_MANUAL.md
    MASTER_PROJECT_STATUS.md
    coding_tasks/
    handoffs/
    locks/
    orchestrator_logs/
    qa_requests/
    qm_reports/
  call-center-scheduler/
    README.md
    TEST_PROTOCOL.md
    QA_HANDOFF_REPORT.md
    backend/
      app/
        api/
        core/
        models/
        repositories/
        services/
      tests/
    sample_data/
    scripts/
  react-app/
    package.json
    vite.config.ts
    src/
  runtime_logs/
```

## Current Tasks And Status

| ID | Task | Status | Owner | Notes |
|---|---|---|---|---|
| DOC-001 | Establish shared Codex + Claude protocol | In Review | Codex | Awaiting user approval |
| ARCH-001 | Decide primary frontend path | Done | User | React/Vite is the only frontend; legacy vanilla frontend removed |
| ARCH-002 | Remove legacy vanilla frontend wiring | Done | Codex | Backend now serves React build when present; Vite is dev UI |
| QA-001 | Refresh QA baseline after current local changes | Proposed | Codex/Claude | Existing docs show prior QA from 2026-05-09; current code has local modifications |
| DEV-001 | Audit current dirty worktree before development | Proposed | Codex/Claude | Local modified files and runtime logs exist as of 2026-07-08 |

## Decisions Log

| ID | Date | Status | Decision | Rationale | Owner |
|---|---|---|---|---|---|
| D-20260708-001 | 2026-07-08 | Proposed | Use `agent_communication/` in the git repo as the primary AI communication channel. | Plain Markdown is easy for Codex, Claude, and the user to inspect and version. | User |
| D-20260708-002 | 2026-07-08 | Proposed | Use `PROJECT_DOCS.md` as the living source of truth for architecture, tasks, decisions, known issues, and backlog. | A single hub reduces drift across agents and sessions. | User |
| D-20260708-003 | 2026-07-08 | Proposed | Keep `AGENTS.md` and `CLAUDE.md` as lightweight entrypoints that point to shared docs. | Codex and Claude commonly discover different startup files; both should converge on the same documentation. | User |
| D-20260708-004 | 2026-07-08 | Accepted | Use only the React/Vite frontend and remove the old vanilla frontend. | The user explicitly chose the React frontend as the single UI path. | User |
| D-20260708-005 | 2026-07-08 | Accepted | FastAPI remains the API server and may serve the built React app from `react-app/dist`. | This supports Vite development and a single-server production-style run. | Codex |
| D-20260708-006 | 2026-07-08 | Accepted | Admin users are also allowed to use the normal personal dashboard and should land on `/dashboard` after login. | Admins may also be employees; `/admin` remains protected and reachable from the dashboard. | User |

## Known Issues And Risks

| ID | Area | Issue/Risk | Severity | Status | Notes |
|---|---|---|---|---|---|
| RISK-001 | Workflow | Multiple historical coordination files exist. | Medium | Open | New active docs should be used going forward; old docs remain historical context. |
| RISK-002 | Frontend | Old vanilla frontend has been removed; historical QA docs may still reference it. | Low | Open | Treat those references as history and run fresh React UI QA. |
| RISK-003 | Git state | Existing local modified/untracked files are present. | Medium | Open | Future agents must inspect `git status` before edits and avoid overwriting user changes. |
| RISK-004 | Security | Firebase credentials and service account files must not be exposed. | High | Open | Keep secrets out of commits and screenshots. |
| RISK-005 | QA freshness | Existing QA reports are from 2026-05-09. | Medium | Open | Run a fresh baseline after protocol approval and before major development. |
| RISK-006 | Routing | FastAPI currently serves React only for `/`, `/dashboard`, and `/admin`. | Low | Open | Add an SPA catch-all when new React routes are introduced so direct navigation does not 404. |
| RISK-007 | Role UX | Admins have both employee-dashboard and admin-panel access. | Low | Monitoring | Keep `/admin` protected; do not reintroduce automatic redirects away from `/dashboard`. |

## Next Steps / Backlog

1. User reviews and approves or revises the collaboration protocol.
2. Audit current app state and dirty worktree.
3. Run backend unit tests and API health checks.
4. Run React build and UI smoke checks.
5. Add a FastAPI SPA catch-all before introducing additional React routes.
6. Decide whether `GET /api/v1/dashboard/summary` should be admin-only; it currently requires only authentication, so agents can read company-wide coverage metrics.
7. Add frontend test infrastructure, such as Vitest and React Testing Library, so routing guards like `ProtectedRoute` get automated coverage.
8. Consider admin-specific dashboard copy for admins with no agent profile; the current generic dashboard says "You have a day off today" and shows an empty shift card.
9. Treat `403` "User is disabled" and `404` "User profile not found" from `get_current_user` as frontend session-ending responses, like `401`, so deactivated/deleted users do not stay in a protected shell with a stale token.
10. Harden React session callback identity by wrapping `syncSession` in `useCallback` in `react-app/src/App.tsx`; optionally add an `active` cancellation guard to `AdminPage` initialization for consistency with `DashboardPage`.
11. Update the task board with the first approved development task.
12. Keep the user manual current as features stabilize.

## Documentation Maintenance Rules

- Update this file whenever architecture, stack, task status, decisions, file structure, known issues, or backlog changes.
- Use short, dated entries rather than long narrative history.
- Move completed implementation detail to `TASK_LOG.md` and keep this hub current.
- Do not duplicate the same decision in multiple files.
- If a fact is uncertain, mark it as proposed, open, or needs verification.
