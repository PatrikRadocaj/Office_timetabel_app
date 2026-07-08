# QA Handoff Report

## Project
- Name: Call Center Scheduler (school/university project)
- Root: `C:\Users\User\Desktop\web projekt\call-center-scheduler`
- Frontend: React/Vite/TypeScript + Bootstrap 5 (`C:\Users\User\Desktop\web projekt\react-app`)
- Backend: FastAPI (Python)
- Auth/DB: Firebase Auth + Firestore

## Current Status
- Backend was started and health endpoint returned `{"status":"ok"}`.
- Main development app URL: `http://localhost:5173/`
- Backend/API URL: `http://localhost:8000/`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/health`

## Scope for QA Agent
1. Validate core functional flows end-to-end.
2. Validate client-side and server-side validation behavior.
3. Validate role-based access (`admin` vs non-admin).
4. Validate schedule generation and dashboard coverage rendering.
5. Log defects with reproducible steps and severity.

## Environment Setup (for QA)
1. Ensure backend is running:
   - `cd backend`
   - `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
2. Ensure React frontend is running:
   - `cd ..\..\react-app`
   - `npm install`
   - `npm run dev`
3. Ensure Firebase is reachable and configured:
   - `backend/.env`
   - `backend/service-account.json`
4. Optional seed:
   - `python scripts\seed_firestore.py`

## Test Data Notes
- Sample files in `sample_data/`:
  - `users.json`
  - `offices.json`
  - `skills.json`
  - `agents.json`
  - `demand_forecasts.json`
  - `demand_upload_template.csv`
- `users` collection stores profile docs; Firebase Auth users must still exist in Auth.

## Functional Test Checklist

### 1) Auth
- Register new user with valid data -> success, redirected to dashboard.
- Register with weak password -> rejected (client and server).
- Login with valid credentials -> success.
- Login with wrong password -> rejected.
- Logout -> session cleared and redirected to login.

### 2) Authorization
- Non-admin user cannot access admin-only operations.
- Admin user can create/update/delete entities.
- Protected API endpoints reject missing/invalid Bearer token.

### 3) Admin: Offices/Skills/Agents
- Create office, verify table refresh.
- Create skill, verify table refresh and select options update.
- Create agent with multiple skills, verify list refresh.
- Negative tests:
  - duplicate office/skill names
  - duplicate agent email
  - invalid capacity/proficiency/hours

### 4) Demand Forecast
- Add manual demand row from UI.
- Upload valid CSV (`sample_data/demand_upload_template.csv`) -> success.
- Upload malformed CSV -> clear error message.
- Verify demand table updates.

### 5) Schedule Generation
- Generate schedule for a window that contains demand.
- Verify generated stats:
  - schedule_id exists
  - required/assigned/uncovered values are consistent
- Verify assignment table and coverage table render and update.
- Verify gap highlighting:
  - high gap
  - medium gap
  - zero/low gap

### 6) Dashboard
- Metric cards load without errors.
- Coverage points load and format correctly.
- Empty-state messages are clear when no data exists.

### 7) Responsiveness/UI
- Validate on desktop and mobile widths.
- Ensure forms are usable and no overlapping controls.
- Verify alerts and validation feedback are visible and understandable.

## API Sanity Checklist
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/offices`, `POST /api/v1/offices`
- `GET /api/v1/skills`, `POST /api/v1/skills`
- `GET /api/v1/agents`, `POST /api/v1/agents`
- `GET /api/v1/demand-forecasts`, `POST /api/v1/demand-forecasts`
- `POST /api/v1/demand-forecasts/upload-csv`
- `POST /api/v1/schedules/generate`
- `GET /api/v1/dashboard/summary`

## Known Risk Areas (focus here first)
1. Firebase token/session handling edge cases.
2. Admin role assignment consistency in Firestore `users` collection.
3. Date/time handling for demand slots and schedule windows.
4. Heuristic scheduling edge cases (capacity limits, partial coverage).
5. CSV ingestion error handling and row-level data quality.

## Defect Reporting Format
For each defect, provide:
1. Title
2. Severity (`Blocker`, `High`, `Medium`, `Low`)
3. Environment (OS/browser)
4. Preconditions
5. Steps to reproduce
6. Actual result
7. Expected result
8. Evidence (screenshot/log/API response)
9. Affected file/endpoint (if known)

## Exit Criteria (QA Pass)
- No `Blocker` or `High` severity defects open.
- Core flows (Auth, Admin CRUD, Demand, Schedule generation, Dashboard) pass.
- Validation and authorization behavior match expected requirements.
- UI remains functional on mobile and desktop.
