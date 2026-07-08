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

- Offices
- Skills
- Agents
- Demand forecasts
- CSV demand uploads
- Schedule generation

### Dashboard

The dashboard shows operational metrics and coverage information. Coverage gaps should be highlighted when demand is not fully covered.

### Agent Area

Agents should see their own dashboard data and should not have access to admin-only controls.

## Common Workflows

### Add Demand Forecasts

1. Log in as admin.
2. Open the admin area.
3. Add demand manually or upload a CSV file.
4. Verify the demand table updates.

### Generate A Schedule

1. Ensure offices, skills, agents, and demand forecasts exist.
2. Open the schedule generation section.
3. Select the date/window.
4. Generate the schedule.
5. Review assigned, required, and uncovered coverage values.

## Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| Backend will not start | Missing dependencies | Activate the virtual environment and run `pip install -r requirements.txt` |
| React app will not start | Missing npm dependencies | Run `npm install` inside `react-app` |
| FastAPI root returns React build missing | React build does not exist | Use `npm run dev` for development or run `npm run build` before opening port 8000 |
| FastAPI serves HTML but built assets return 404 | Backend started before `npm run build`; `/assets` is mounted only at startup | Run `npm run build`, then restart the backend |
| Firebase errors | Missing or invalid `.env`/service account | Check Firebase project ID, API key, and service account path |
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
