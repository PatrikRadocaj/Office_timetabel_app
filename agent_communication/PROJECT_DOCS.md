# Project Documentation Hub

Last updated: 2026-07-09

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
- Demand storage: compact daily Firestore documents under `demand_forecasts`, expanded to slot rows in memory for API compatibility, graphing, and scheduling
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
| FEAT-002 | Expose admin summary and schedule generation in React | Done | Codex | Admin page now loads dashboard summary, generates schedules, and displays assignment coverage results |
| FEAT-003 | Add edit/delete UI for admin catalog data | Done | Codex | Admin data preview now supports inline edit and confirmed delete for offices, skills, and agents |
| FEAT-004 | Add agent availability management in React | Done | Codex | Admin agent create/edit now sends and displays office-local weekday/hour availability windows |
| FEAT-006 | Implement agent dashboard quick actions | Done | Codex | View All My Shifts and Update Availability are real agent-facing flows; day-off and shift-swap request workflows are backlogged |
| DATA-003 | Compact demand forecast storage | Done | Codex | Daily demand saves now write one Firestore document per office/date/interval and expand to slots only in memory |
| DATA-004 | Migrate legacy demand slot documents to compact storage | Done | Codex | Legacy per-slot demand documents were backed up, compacted into 35 daily documents, and deleted from Firestore |
| DATA-005 | Reduce Firestore read volume for dashboard counts and daily demand | Done | Codex | Dashboard totals use Firestore aggregation counts; dashboard coverage loads only latest five schedules; daily demand replace/day-view use deterministic compact document ID prefix lookups |
| SCHED-001 | Match availability windows in office-local time | Done | Claude | Scheduler localizes availability and shift-preference hours to the agent's office timezone; midnight-ending slot leak fixed; TimeWindow now validated server-side; manual Munich smoke passed 2026-07-09 |
| FEAT-005 | Announcements admin management | Done | Claude | New admin-only `/api/v1/announcements` CRUD API plus React admin UI to create, edit, activate/deactivate, and delete announcements; agent dashboards keep showing active announcements; manual smoke passed 2026-07-09 |
| SEC-001 | Fix Firebase credential and runtime log git hygiene | Done | Codex | Removed tracked local service-account/runtime-log paths from the git index, added ignore rules, and documented local-only credential setup plus key rotation guidance |
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
| D-20260708-007 | 2026-07-08 | Accepted | Store demand forecasts as compact daily documents instead of one Firestore document per non-zero slot/skill. | This sharply reduces Firestore document count, read/write volume, and quota pressure while preserving slot-level scheduler behavior in memory. | User |
| D-20260708-008 | 2026-07-08 | Accepted | Agent availability windows use office-local whole hours with Monday = 0 through Sunday = 6; an empty availability list means always available. | Office-local hours match how demand days are defined; unrestricted-agent behavior is preserved. Rationale corrected 2026-07-08: the scheduler originally matched in UTC and was fixed under SCHED-001 to make this contract true. | Codex |
| D-20260708-009 | 2026-07-08 | Accepted | The scheduler evaluates availability windows and shift-preference day/night hours in the AGENT'S office timezone (not UTC, not the demand office). | Availability windows are entered per agent and documented as office-local; using the agent's own office keeps the contract true even if an agent is assigned to another office's demand. | Claude |
| D-20260709-001 | 2026-07-09 | Accepted | All `/api/v1/announcements` routes, including list, are admin-only; agents receive active announcements exclusively through `/api/v1/me/dashboard`. | The management list exposes inactive drafts, so it belongs to the admin surface; the dashboard already filters to the newest 10 active announcements. | Claude |
| D-20260709-002 | 2026-07-09 | Accepted | Agents can directly update their own availability through `/api/v1/me/availability`; day-off and shift-swap actions require a future request/approval model before implementation. | Availability is already part of the agent scheduling profile, while day-off and swap requests need workflow state, reviewer actions, and schedule-impact handling. | Codex |
| D-20260709-003 | 2026-07-09 | Accepted | Use Firestore aggregation counts for dashboard document totals and deterministic document ID prefix lookups for compact daily demand day operations. | These reads avoid streaming whole collections for counts or single-day demand views while preserving the compact daily demand storage model and suffixed additive documents. | Codex |

## Known Issues And Risks

| ID | Area | Issue/Risk | Severity | Status | Notes |
|---|---|---|---|---|---|
| RISK-001 | Workflow | Multiple historical coordination files exist. | Medium | Open | New active docs should be used going forward; old docs remain historical context. |
| RISK-002 | Frontend | Old vanilla frontend has been removed; historical QA docs may still reference it. | Low | Open | Treat those references as history and run fresh React UI QA. |
| RISK-003 | Git state | Existing local modified/untracked files are present. | Medium | Open | Future agents must inspect `git status` before edits and avoid overwriting user changes. |
| RISK-004 | Security | Firebase credentials and service account files must not be exposed. | High | Open | Keep secrets out of commits and screenshots. On 2026-07-09, `call-center-scheduler/backend/service-account.json` was removed from git tracking; rotate any Firebase/GCP service-account key that was previously committed. Local setup should use `FIREBASE_SERVICE_ACCOUNT_PATH` or `FIREBASE_SERVICE_ACCOUNT_JSON` only. |
| RISK-005 | QA freshness | Existing QA reports are from 2026-05-09. | Medium | Open | Run a fresh baseline after protocol approval and before major development. |
| RISK-006 | Routing | FastAPI currently serves React only for `/`, `/dashboard`, and `/admin`. | Low | Open | Add an SPA catch-all when new React routes are introduced so direct navigation does not 404. |
| RISK-007 | Role UX | Admins have both employee-dashboard and admin-panel access. | Low | Monitoring | Keep `/admin` protected; do not reintroduce automatic redirects away from `/dashboard`. |
| RISK-008 | Firebase | Firestore quota for project `scheduler-app-54991` can be exhausted during repeated admin/API smoke testing. | Medium | Monitoring | Compact demand storage reduces future pressure; legacy slot documents were migrated/deleted on 2026-07-08. Dashboard counts now use aggregation counts, dashboard coverage loads only the latest five schedules, and daily demand day operations use deterministic document ID prefix lookups. |

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
11. Show the start-end range in the schedule assignment table's Time column.
12. Clear stale `scheduleResult` when a new schedule generation attempt fails.
13. Add office-timezone-aware schedule generation windows so admin browser timezone differences do not produce partial office-day windows.
14. Add referential-integrity guards for office and skill deletes, returning `409` with reference counts or documenting an intentional cascade policy.
15. Enforce office and skill name uniqueness on update, matching the create-path `409`; also apply the weekly max-hours hard-limit check in agent update.
16. Validate office timezone values as real IANA zones on create/update, or replace free-text timezone entry with a timezone select in the UI.
17. Document compact-storage contract changes for single-slot, bulk, and CSV demand endpoints: only 30/60-minute slots, priority is per skill-day, and same-slot re-posts replace quantity instead of accumulating; decide whether the CSV template needs a note.
18. Harden compact demand expansion so malformed documents missing `forecast_date` or `interval_minutes` are skipped with a log entry instead of raising a 500.
19. Keep demand manual copy clear that `replace_existing_day=false` writes suffixed documents and stacks demand additively.
20. Refactor compact demand seed/migration scripts to reuse `DemandService._daily_document_payload` and avoid schema drift.
21. After Firestore quota recovers, run one targeted live check (one day-view load or one replace-day save) to confirm the `FieldPath.document_id()` prefix range query works against the real Firestore client, not only the test fakes.
22. Design and implement day-off request workflow: request model, agent create/list status, admin review/approve/reject, and scheduler/schedule-impact handling.
23. Design and implement shift-swap request workflow: request model, eligible target shift/agent selection, approval flow, and schedule update policy.
24. Update the task board with the first approved development task.
25. Keep the user manual current as features stabilize.

## Documentation Maintenance Rules

- Update this file whenever architecture, stack, task status, decisions, file structure, known issues, or backlog changes.
- Use short, dated entries rather than long narrative history.
- Move completed implementation detail to `TASK_LOG.md` and keep this hub current.
- Do not duplicate the same decision in multiple files.
- If a fact is uncertain, mark it as proposed, open, or needs verification.
