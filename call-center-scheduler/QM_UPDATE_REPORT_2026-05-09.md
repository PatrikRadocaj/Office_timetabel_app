# QM Update Report (Post-Previous QA/QM Handoff)

Date: 2026-05-09  
Project Root: `C:\Users\User\Desktop\web projekt\call-center-scheduler`  
Baseline documents reviewed:
- `QA_RESPONSE_FROM_CODING_AGENT.md`
- `QA_HANDOFF_REPORT.md`
- `QA_FEEDBACK_FOR_CODING_AGENT.md`

## 1) Executive Delta Summary

Since the previous QA/QM handoff, the system received four major update groups:
1. Demand Forecast model + Admin UX refactor to full-day interval grids.
2. Admin chart upgrade to display both demand and coverage.
3. Agent dashboard overhaul to remove admin operations and show personal schedule data.
4. Role-based redirect/navigation cleanup (admin -> `/admin`, agent -> `/dashboard`).

All updates were implemented in Vanilla HTML/CSS/JS + Bootstrap frontend and FastAPI backend, with Firestore-backed storage.

## 2) Backend/API Changes

## 2.1 Demand Forecast (Daily Grid Mode)
- Added daily input schemas and validation:
  - `backend/app/models/demand.py`
  - New models include:
    - `DailyDemandForecastCreate`
    - `DailyDemandForecastWriteResponse`
    - `DemandForecastDayViewRead`
  - Validation highlights:
    - `interval_minutes` must be `30` or `60`
    - per-skill quantities length must match 48/24 blocks
    - no negative quantities
    - at least one non-zero demand value

- Added endpoint:
  - `POST /api/v1/demand-forecasts/daily`
  - File: `backend/app/api/routers/demand.py`

- Added read endpoint:
  - `GET /api/v1/demand-forecasts/day-view?office_id=...&forecast_date=...&interval_minutes=...`
  - Returns full day blocks with per-skill totals.

- Service logic expanded:
  - File: `backend/app/services/catalog_service.py`
  - Daily mode persists normalized slot rows with metadata:
    - `forecast_date`, `interval_minutes`, `time_block`, `entry_mode`, `forecast_batch_id`
  - Uses office timezone (`ZoneInfo`) for slot generation.

## 2.2 Demand Coverage Overlay Data
- `day-view` response now also includes coverage (from latest generated matching schedule):
  - Per block:
    - `coverage_by_skill`
    - `total_covered`
    - `coverage_gap`
    - `coverage_ratio`
  - Payload metadata:
    - `coverage_schedule_id`
    - `coverage_generated_at`

Files:
- `backend/app/models/demand.py`
- `backend/app/services/catalog_service.py`

## 2.3 New Agent-Facing API
- New route:
  - `GET /api/v1/me/dashboard`
- Files:
  - `backend/app/api/routers/me.py`
  - `backend/app/services/me_service.py`
  - `backend/app/models/me.py`
  - `backend/app/repositories/announcements_repository.py`
  - `backend/app/main.py` (router registration)

Behavior:
- Agent role required (`403` for non-agent).
- Returns agent-focused payload:
  - greeting + date + status
  - today shift
  - next 7 days schedule
  - hours overview
  - skills with proficiency pct
  - announcements list

Data sourcing logic:
- Resolves agent profile by `user_id`, fallback by `email`.
- Weekly rows derived from generated schedule assignments where `assigned_agent_ids` includes current agent.
- Announcements read from Firestore collection `announcements` (latest active, up to 10).

## 3) Frontend Changes

## 3.1 Admin Demand Builder UX

File: `frontend/admin.html` + `frontend/js/admin-page.js`

Implemented:
- Full-day forecast builder with:
  - date picker
  - interval toggle (30/60)
  - generated time-block grid
- Skill selection added:
  - manual skill checkboxes
  - `Select All` / `Clear`
  - grid/save strictly bound to selected skills at generation time
- CSV legacy import retained.

## 3.2 Admin Forecast Graph

File: `frontend/js/admin-page.js`

Implemented:
- Chart now plots:
  - Demand line
  - Coverage line (dashed)
- Modes:
  - Skill filter = `all`: total demand vs total coverage
  - Specific skill: skill demand vs skill coverage
- Warning alert when no matching generated schedule exists (coverage=0).

## 3.3 Agent Dashboard Full Redesign

Files:
- `frontend/dashboard.html`
- `frontend/js/dashboard-page.js`

Previous dashboard content (admin-like operations) removed from agent view:
- Removed schedule generation controls.
- Removed company-wide operational snapshot.
- Removed full coverage heatmap admin behavior.

New agent page sections:
1. Welcome / date / status
2. Today’s shift card
3. Weekly schedule table (7 days, today highlighted)
4. Hours overview
5. Quick actions
6. My skills (progress bars)
7. Announcements

## 3.4 Role-Based Routing

File: `frontend/js/index-page.js`

Updated:
- After login/register:
  - `admin` -> `/admin`
  - `agent` -> `/dashboard`
- If already logged in on index page, same redirect logic applies.

Additional safeguard:
- `frontend/js/dashboard-page.js` redirects admins away from agent page to `/admin`.

## 4) Files Added

- `backend/app/models/me.py`
- `backend/app/repositories/announcements_repository.py`
- `backend/app/services/me_service.py`
- `backend/app/api/routers/me.py`
- `frontend/dashboard.html` (recreated with new structure)
- `frontend/js/dashboard-page.js` (rewritten)
- `QM_UPDATE_REPORT_2026-05-09.md` (this report)

## 5) Files Updated (Relevant)

- `backend/app/main.py`
- `backend/app/models/demand.py`
- `backend/app/services/catalog_service.py`
- `backend/app/api/routers/demand.py`
- `frontend/admin.html`
- `frontend/js/admin-page.js`
- `frontend/js/index-page.js`
- `frontend/css/styles.css`

## 6) Verification Performed

Commands executed successfully:
- `python -m compileall backend\app`
- `node --check frontend\js\admin-page.js`
- `node --check frontend\js\dashboard-page.js`
- `node --check frontend\js\index-page.js`
- `python -m pytest backend\tests -q` -> `2 passed`

Runtime checks:
- `GET http://localhost:8000/api/health` -> `{"status":"ok"}`
- Local servers currently listening:
  - backend `:8000`
  - react `:5173`

## 7) QA/QM Retest Focus (Recommended)

Priority A:
1. Role redirects:
   - login as admin -> lands on `/admin`
   - login as agent -> lands on `/dashboard`
2. Agent dashboard authz:
   - agent can access `/api/v1/me/dashboard`
   - admin gets `403` on `/api/v1/me/dashboard`
3. Admin feature segregation:
   - agent dashboard has no scheduler run / demand management controls.

Priority B:
4. Daily demand grid save validation:
   - 30-min vs 60-min counts
   - selected-skill-only payload
   - stale-grid regeneration guard
5. Day-view graph overlay:
   - with existing generated schedule -> non-zero coverage where assigned
   - without schedule -> warning + coverage line at 0.

Priority C:
6. Announcements rendering:
   - with and without `announcements` collection records.
7. Agent schedule fallback:
   - agent profile found by `user_id`
   - fallback by email + optional `user_id` backfill.

## 8) Known Limitations / Open Design Notes

1. Quick actions are currently UI placeholders (informational alert only; no mutation endpoints yet).
2. Break time in today/weekly shift is currently `null` unless a future source is introduced.
3. Coverage in admin graph is derived from the latest matching generated schedule (office/day/interval), not from a manually selected schedule ID.
4. If an agent has no matching `agents` doc, dashboard remains usable but schedule/skills may be empty.

## 9) Suggested Next Implementation Slice

1. Add real agent request workflows:
   - `POST /api/v1/me/requests/day-off`
   - `POST /api/v1/me/requests/shift-swap`
   - `PUT /api/v1/me/availability`
2. Add admin announcements CRUD endpoint/UI.
3. Add tests for `/api/v1/me/dashboard` role and data-shaping behavior.

