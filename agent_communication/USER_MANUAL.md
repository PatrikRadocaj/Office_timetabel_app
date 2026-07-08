# User Manual

Status: Draft template
Last updated: 2026-07-08

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
- Agent-specific dashboard data

## Prerequisites

For local development:

- Windows PowerShell or compatible shell
- Python 3.10+ recommended
- Node.js and npm
- Firebase project with Authentication and Firestore enabled
- Firebase service account JSON
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

Create `backend\.env` from the example configuration and set:

```env
APP_NAME=Call Center Scheduler API
API_V1_PREFIX=/api/v1
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173

FIREBASE_PROJECT_ID=your-project-id
FIREBASE_WEB_API_KEY=your-web-api-key
FIREBASE_SERVICE_ACCOUNT_PATH=./service-account.json

SCHEDULE_SLOT_MINUTES=30
DEFAULT_SHIFT_HOURS=8
MAX_WEEKLY_HOURS_HARD_LIMIT=60
```

Do not commit `.env` files or service account credentials.

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
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
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
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
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
- Agents, including create, edit, delete, and skill assignment changes
- Demand forecasts
- CSV demand uploads
- Schedule generation

### Dashboard

The dashboard shows personal schedule information, hours, skills, announcements, and quick actions. Admin users also land here after login because they may also be company employees.

### Agent Area

Agents should see their own dashboard data and should not have access to admin-only controls.

### Admin Access

Admins can open the admin area from the dashboard using the Admin Panel button, or by opening `/admin` directly. Non-admin users are redirected away from `/admin`.

## Common Workflows

### Manage Offices, Skills, And Agents

1. Log in as admin.
2. Open the admin area.
3. Use the create forms to add new offices, skills, or agents.
4. In Data Preview, use Edit to change an existing office, skill, or agent inline.
5. Use Delete to remove an item after confirming the browser prompt.
6. If the backend rejects an update or delete, review the alert banner for the exact error.

### Add Demand Forecasts

1. Log in as admin.
2. Open the admin area.
3. Add demand manually or upload a CSV file.
4. Verify the demand table updates.

Demand forecasts are stored compactly: one Firestore document per office/date/interval can represent a full day of skill demand. The API still shows slot-level rows in the UI and scheduler by expanding that document in memory.

When a daily demand save uses `replace_existing_day=false`, the backend writes an additional suffixed compact document. Those saved documents stack additively for the same office/date/interval.

### Generate A Schedule

1. Ensure offices, skills, agents, and demand forecasts exist.
2. Open the schedule generation section.
3. Select the start and end date/time window.
4. Generate the schedule.
5. Review the schedule ID, total required agents, total assigned agents, uncovered demand, and assignment rows.
6. Use the Admin Summary section to review active schedules plus aggregate required, assigned, gap, and coverage values.

Note: the schedule generation start/end controls use the admin browser's local timezone. Demand days are defined in each office's timezone, so adjust the window when generating schedules for offices in a different timezone.

## Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| Backend will not start | Missing dependencies | Activate the virtual environment and run `pip install -r requirements.txt` |
| React app will not start | Missing npm dependencies | Run `npm install` inside `react-app` |
| FastAPI root returns React build missing | React build does not exist | Use `npm run dev` for development or run `npm run build` before opening port 8000 |
| FastAPI serves HTML but built assets return 404 | Backend started before `npm run build`; `/assets` is mounted only at startup | Run `npm run build`, then restart the backend |
| Firebase errors | Missing or invalid `.env`/service account | Check Firebase project ID, API key, and service account path |
| Cloud Firestore quota is exceeded | Firestore rejected reads/writes for the configured project | Wait for quota reset, reduce repeated admin/API refreshes, or increase the Firebase/Google Cloud quota |
| Login fails for seeded users | Seeded `users` docs are profiles only | Create matching Firebase Auth users or register through the app |
| Admin page forbidden | User role is not `admin` in Firestore | Update the user's Firestore profile role |
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
