# User Manual

Status: Draft template
Last updated: 2026-07-09

## Application Name

Call Center Scheduler

## Audience

This manual is for administrators and call center agents using the scheduling application, plus developers installing or running the project locally.

## What The Application Does

The application helps a multi-office call center manage:

- User registration and login
- Admin management of offices, skills, agents, and demand forecasts
- Demand CSV upload
- Schedule generation
- Dashboard metrics and coverage gaps
- Agent day-off requests and admin review
- Agent shift-swap requests and admin review
- Agent-specific dashboard data

## Prerequisites

For local development:

- Windows PowerShell or compatible shell
- Python 3.10+ recommended
- Node.js and npm
- Firebase project with Authentication and Firestore enabled
- Firebase service account JSON kept local-only and out of git
- Optional: Docker Desktop

## Installation

### Backend

```powershell
cd "C:\Users\User\Desktop\web projekt\call-center-scheduler\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Firebase Configuration

Create `backend\.env` from the example configuration and set your Firebase values.

Keep credentials local only:

- Prefer storing the service-account JSON outside this repository, for example under `C:\Users\User\firebase-keys\`.
- Set `FIREBASE_SERVICE_ACCOUNT_PATH` to that local file path, or provide the full JSON through `FIREBASE_SERVICE_ACCOUNT_JSON` from your shell or secret manager.
- Do not commit `.env` files, service-account JSON files, runtime logs, or backup JSON exports.
- If a real service-account key was ever committed to git, rotate that key in Firebase/GCP and replace the local file.

```env
APP_NAME=Call Center Scheduler API
API_V1_PREFIX=/api/v1
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173

FIREBASE_PROJECT_ID=your-project-id
FIREBASE_WEB_API_KEY=your-web-api-key
FIREBASE_SERVICE_ACCOUNT_PATH=C:/Users/User/firebase-keys/call-center-scheduler-service-account.json
# Alternatively, set FIREBASE_SERVICE_ACCOUNT_JSON through your shell or secret manager.

SCHEDULE_SLOT_MINUTES=30
DEFAULT_SHIFT_HOURS=8
MAX_WEEKLY_HOURS_HARD_LIMIT=60
```

Do not paste service-account JSON values into chat, screenshots, commits, task logs, or documentation.

### Frontend

```powershell
cd "C:\Users\User\Desktop\web projekt\react-app"
npm install
```

## Running The Application

### Run Backend

The backend serves the API. In development, run the React frontend separately with Vite.

```powershell
cd "C:\Users\User\Desktop\web projekt\call-center-scheduler\backend"
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open:

- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/health`

### Run React Frontend

```powershell
cd "C:\Users\User\Desktop\web projekt\react-app"
npm run dev
```

Open:

- App: `http://localhost:5173/`
- Login/Register: `http://localhost:5173/`
- Agent dashboard: `http://localhost:5173/dashboard`
- Admin page: `http://localhost:5173/admin`

The Vite dev server proxies `/api` to the backend on `http://127.0.0.1:8000`.

### Production-Style Local Run

```powershell
cd "C:\Users\User\Desktop\web projekt\react-app"
npm run build
cd "C:\Users\User\Desktop\web projekt\call-center-scheduler\backend"
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

After the React build exists, FastAPI can serve the app at `http://localhost:8000/`.

### Optional Docker Run

```powershell
cd "C:\Users\User\Desktop\web projekt\call-center-scheduler"
docker compose up --build
```

Docker builds the React frontend and serves it through FastAPI at `http://localhost:8000/`.

## Seeding Sample Data

After Firebase is configured:

```powershell
cd "C:\Users\User\Desktop\web projekt\call-center-scheduler"
python scripts\seed_firestore.py
```

Sample data is located in:

- `sample_data/users.json`
- `sample_data/offices.json`
- `sample_data/skills.json`
- `sample_data/agents.json`
- `sample_data/demand_forecasts.json`
- `sample_data/demand_upload_template.csv`

## First Admin Setup

1. Open `http://localhost:5173/`.
2. Register a user.
3. In Firebase Firestore, open the `users` collection.
4. Find the new user document. The document ID should match the Firebase UID.
5. Set `role` to `admin`.
6. Log in again and open `/admin`.

## Main Features

### Authentication

- Register with email and password.
- Log in with existing credentials.
- Log out to clear the session.

### Admin Area

Admins can manage:

- Admin summary metrics and coverage gaps
- Offices, including create, edit, and delete
- Skills, including create, edit, and delete
- Agents, including create, edit, delete, skill assignment changes, and availability windows
- Announcements, including create, edit, activate/deactivate, and delete
- Day-off requests, including review, approval, and rejection
- Shift-swap requests, including review, approval, rejection, and schedule assignment swaps
- Demand forecasts
- CSV demand uploads
- Schedule generation

### Dashboard

The dashboard shows personal schedule information, hours, skills, announcements, and quick actions. Admin users also land here after login because they may also be company employees.

### Agent Area

Agents should see their own dashboard data and should not have access to admin-only controls. From the dashboard, agents can view all active generated shifts assigned to them, update their own availability windows, submit day-off requests, and request shift swaps for admin review.

### Admin Access

Admins can open the admin area from the dashboard using the Admin Panel button, or by opening `/admin` directly. Non-admin users are redirected away from `/admin`.

## Common Workflows

### Manage Offices, Skills, And Agents

1. Log in as admin.
2. Open the admin area.
3. Use the create forms to add new offices, skills, or agents. Office timezone values must be valid IANA names such as `Europe/Berlin` or `UTC`; the UI suggests common seeded zones.
4. In Data Preview, use Edit to change an existing office, skill, or agent inline.
5. For agents, use Availability to add office-local weekday/hour windows. Monday is 0 and Sunday is 6. Leave availability empty when the agent should be treated as always available.
6. Use Delete to remove an item after confirming the browser prompt.
7. If the backend rejects an update or delete, review the alert banner for the exact error.

### Manage Announcements

1. Log in as admin.
2. Open the admin area.
3. Use the Create Announcement form to add a title and message. Leave Active checked so the announcement appears on agent dashboards immediately, or uncheck it to save a hidden draft.
4. In Data Preview, open the Announcements section to list all announcements, including inactive ones.
5. Use Edit to change the title, message, or active state inline; use Activate/Deactivate to toggle visibility without editing; use Delete to remove an announcement permanently after confirming the browser prompt.

Agent dashboards show the newest 10 active announcements. Deactivated announcements disappear from dashboards but stay listed in the admin panel. Only admins can view the management list or change announcements; agents receive active announcements through their dashboard only.

### Use Agent Quick Actions

1. Log in as an agent and open the dashboard.
2. Use Request Day Off to open your day-off request form and history.
3. Enter a start date, end date, and optional reason, then submit the request.
4. Use Request Shift Swap to choose one of your active generated shifts and a same-office target shift assigned to another agent.
5. Add an optional reason and submit the swap request for admin review.
6. Use View All My Shifts to load every active generated shift currently assigned to you, beyond the next 7 days shown in the dashboard summary.
7. Use Update Availability to add, edit, or remove your availability windows.
8. Availability windows use your office local time. Monday is 0 and Sunday is 6. Leave the list empty only if you should be treated as always available.
9. Save Availability writes directly to your agent scheduling profile.

Day-off requests can be pending, approved, or rejected. Approval records the request status only; it does not automatically remove generated assignments or regenerate schedules.

Shift-swap requests can be pending, approved, or rejected. Admin approval swaps the two agents in the active generated schedule assignments only after the backend revalidates that both assignments still exist, are in the same office, both agents have the required skills, both agents are available for the new slots, and the swap does not create duplicate or overlapping assignments.

### Review Day-Off Requests

1. Log in as admin.
2. Open the admin area.
3. In Data Preview, open Day-Off Requests.
4. Review the agent, requested dates, reason, and current status.
5. For pending requests, add an optional review note and choose Approve or Reject.
6. After approval, account for the time off manually when generating or adjusting schedules. The app records the approval but does not automatically change existing generated schedules.

### Review Shift-Swap Requests

1. Log in as admin.
2. Open the admin area.
3. In Data Preview, open Shift-Swap Requests.
4. Review the requester, target agent, source shift, target shift, reason, and status.
5. For pending requests, add an optional review note and choose Approve or Reject.
6. Approval revalidates the current active generated schedules before changing anything. If the assignments changed, skills no longer match, offices differ, availability no longer fits, or a duplicate/overlapping assignment would be created, the backend refuses the approval and shows the reason in the alert.
7. After approval, the source assignment contains the target agent and the target assignment contains the requester.

### Add Demand Forecasts

1. Log in as admin.
2. Open the admin area.
3. Add demand manually with the Daily Demand Forecast Builder or upload a CSV file.
4. Verify the demand table updates.

Demand forecasts are stored compactly: one Firestore document per office/date/interval can represent a full day of skill demand. The API still shows slot-level rows in the UI and scheduler by expanding that document in memory. Only 30-minute and 60-minute slots are supported.

Compact demand rules:

- Priority is stored per skill per day, not separately for every time block.
- Re-posting the same office, skill, date, interval, and slot replaces the quantity for that slot instead of adding to the previous value.
- Single-slot API posts, bulk API posts, and CSV imports all write into the same compact daily document model.
- A daily demand save with `replace_existing_day=true` replaces existing compact documents for that office/date/interval.
- A daily demand save with `replace_existing_day=false` writes an additional suffixed compact document. Those saved documents stack additively for the same office/date/interval.

CSV uploads must include this header:

```csv
office_id,skill_id,slot_start,slot_end,required_agents,priority
```

Use ISO datetimes for `slot_start` and `slot_end`, for example `2026-05-10T09:00:00Z`. Every row must be either a 30-minute or 60-minute slot aligned to the office-local interval grid.

### Generate A Schedule

1. Ensure offices, skills, agents, and demand forecasts exist.
2. Open the schedule generation section.
3. Prefer the Office-local helper: choose an office, choose the office local date, then click Use Day or Use Week. This sets the generation window from midnight in that office's timezone.
4. If needed, adjust the Start and End date/time fields manually.
5. Generate the schedule.
6. Review the schedule ID, total required agents, total assigned agents, uncovered demand, and assignment rows.
7. Use the Admin Summary section to review active schedules plus aggregate required, assigned, gap, and coverage values.

New generated schedules are marked `active`. Personal dashboards, View All My Shifts, Admin Summary coverage, and demand-day coverage use active schedules only. If a schedule is later marked `cancelled` or `archived` in Firestore, it is retained as history but ignored by those views. When multiple active schedules cover the same slot, the newest active schedule is authoritative for that slot.

The scheduler respects agent availability windows and evaluates them in the agent's office local timezone, so a Monday 09:00-17:00 window means 09:00-17:00 at that agent's office. Agents with no availability windows are treated as always available.

Note: the manual schedule generation Start and End controls display in the admin browser's local timezone and are sent to the backend as UTC. The Office-local helper converts the selected office date/week into the correct UTC window first, then displays that equivalent window in the browser-local controls.

## Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| Backend will not start | Missing dependencies | Activate the virtual environment and run `pip install -r requirements.txt` |
| React app will not start | Missing npm dependencies | Run `npm install` inside `react-app` |
| FastAPI root returns React build missing | React build does not exist | Use `npm run dev` for development or run `npm run build` before opening port 8000 |
| FastAPI serves HTML but built assets return 404 | Backend started before `npm run build`; `/assets` is mounted only at startup | Run `npm run build`, then restart the backend |
| Firebase errors | Missing or invalid `.env`/service account | Check Firebase project ID, API key, and service account path or `FIREBASE_SERVICE_ACCOUNT_JSON` |
| Cloud Firestore quota is exceeded | Firestore rejected reads/writes for the configured project | Wait for quota reset, reduce repeated admin/API refreshes, or increase the Firebase/Google Cloud quota |
| Login fails for seeded users | Seeded `users` docs are profiles only | Create matching Firebase Auth users or register through the app |
| App returns to login while you are using it | Session expired, user profile was deleted, or user was disabled | Log in again; if it repeats, ask an admin to verify your Firestore user profile is active |
| Admin page forbidden | User role is not `admin` in Firestore | Update the user's Firestore profile role |
| Agent shifts disappear after updating schedule visibility code | Older `generated_schedules` documents may not have `status: active` | Mark the intended visible schedules `active`, archive/cancel old schedules, or generate a fresh schedule |
| Shift-swap approval is refused | The request is stale or would break schedule integrity | Refresh Shift-Swap Requests and review the alert; the backend refuses swaps with skill mismatch, office mismatch, availability conflicts, duplicate assignment, or overlapping assignment |
| Office save says timezone is invalid | The office timezone is not a real IANA timezone name | Use a value like `Europe/Berlin`, `Europe/London`, or `UTC` |
| Every timezone is rejected as invalid | The backend virtual environment is missing the `tzdata` package on Windows | Activate `backend\\.venv` and run `pip install -r requirements.txt`, then restart the backend |
| Office or skill delete is refused | Agents, demand forecasts, or generated schedules still reference the item | Review the alert's reference counts and update/remove dependent records before retrying; deletes do not cascade |
| Port 8000 already in use | Another local server is running | Stop the old process or run Uvicorn on another port |
| CORS error | Frontend origin not configured | Add the frontend URL to `CORS_ORIGINS` |

## Developer Verification Checklist

Before handing the app to a user:

- Backend starts successfully.
- React dev server starts successfully.
- React production build succeeds.
- `GET /api/health` returns healthy status.
- Registration and login work.
- Protected endpoints reject missing or invalid tokens.
- Admin-only routes reject non-admin users.
- Admin CRUD works for the changed area.
- Schedule generation works with sample data.
- Dashboard renders without console errors.
- Manual is updated for changed workflows.

## Support Notes

When reporting a problem, include:

- Date and time
- Browser and operating system
- User role
- Page or endpoint
- Steps to reproduce
- Screenshot or API response if available
- Relevant backend log excerpt
