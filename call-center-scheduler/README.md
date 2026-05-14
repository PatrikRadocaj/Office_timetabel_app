# Call Center Scheduler (School Project)

Professional scheduler web app for a 24/7/365 multi-office call center.

Stack:
- Frontend: Vanilla HTML + CSS + JavaScript + Bootstrap 5
- Backend: Python FastAPI
- Auth/DB: Firebase Authentication + Firestore
- Integration: JSON REST API (`/api/v1/...`)

## 1) Project Structure

```text
call-center-scheduler/
  backend/
    .env.example
    Dockerfile
    requirements.txt
    app/
      main.py
      api/
        deps.py
        routers/
          auth.py
          offices.py
          skills.py
          agents.py
          demand.py
          schedules.py
          dashboard.py
      core/
        config.py
        firebase.py
      models/
        common.py
        auth.py
        office.py
        skill.py
        agent.py
        demand.py
        schedule.py
      repositories/
        firestore_repository.py
        users_repository.py
        offices_repository.py
        skills_repository.py
        agents_repository.py
        demand_repository.py
        schedules_repository.py
      services/
        auth_service.py
        catalog_service.py
        scheduler_service.py
        dashboard_service.py
  frontend/
    index.html
    dashboard.html
    admin.html
    css/styles.css
    js/
      api.js
      auth.js
      ui.js
      index-page.js
      dashboard-page.js
      admin-page.js
  sample_data/
    users.json
    offices.json
    skills.json
    agents.json
    demand_forecasts.json
    demand_upload_template.csv
  scripts/
    seed_firestore.py
  docker-compose.yml
  .gitignore
```

## 2) Firebase Setup

1. Create a Firebase project.
2. Enable **Authentication -> Sign-in method -> Email/Password**.
3. Create **Firestore Database** (Native mode).
4. Get your **Web API key**:
   - Firebase Console -> Project settings -> General -> Web API Key.
5. Create a **Service Account key JSON**:
   - Project settings -> Service accounts -> Generate new private key.
6. Save service account JSON file (for example at `backend/service-account.json`).

## 3) Backend Setup (FastAPI)

1. Copy env template:
   - `backend/.env.example` -> `backend/.env`
2. Fill required env vars in `backend/.env`:
   - `FIREBASE_PROJECT_ID`
   - `FIREBASE_WEB_API_KEY`
   - `FIREBASE_SERVICE_ACCOUNT_PATH` (or `FIREBASE_SERVICE_ACCOUNT_JSON`)

Example:

```env
APP_NAME=Call Center Scheduler API
API_V1_PREFIX=/api/v1
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000

FIREBASE_PROJECT_ID=your-project-id
FIREBASE_WEB_API_KEY=your-web-api-key
FIREBASE_SERVICE_ACCOUNT_PATH=./service-account.json

SCHEDULE_SLOT_MINUTES=30
DEFAULT_SHIFT_HOURS=8
MAX_WEEKLY_HOURS_HARD_LIMIT=60
```

Install and run:

```powershell
cd backend
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open:
- App UI: `http://localhost:8000/`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/health`

## 4) Seed Sample Data

From project root:

```powershell
python scripts\\seed_firestore.py
```

This seeds collections:
- `users`
- `offices`
- `skills`
- `agents`
- `demand_forecasts`

Note: `users.json` documents are profile docs only. They are **not** Firebase Auth accounts.

## 5) First Admin User

1. Open `http://localhost:8000/` and register a user.
2. In Firestore console, open `users` collection.
3. Find the new user document (doc ID = Firebase UID) and set:
   - `role: "admin"`
4. Log in again. You can now use `/admin`.

## 6) Docker Run

Create `backend/.env` first, then:

```powershell
docker compose up --build
```

App runs at `http://localhost:8000/`.

## 7) Main Features

- Register/Login/Logout with Firebase Auth through backend API
- Client + server validation
- Admin CRUD:
  - Offices
  - Skills
  - Agents
  - Demand forecasts
- Demand CSV upload endpoint
- Heuristic schedule generator with:
  - Skill matching and proficiency threshold
  - Office capacity limit
  - Weekly max hours
  - Rest period checks
  - Shift preference scoring
- Dashboard metrics + gap-highlighted coverage table

## 8) Key API Endpoints

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/offices`
- `POST /api/v1/offices` (admin)
- `GET /api/v1/skills`
- `POST /api/v1/skills` (admin)
- `GET /api/v1/agents`
- `POST /api/v1/agents` (admin)
- `GET /api/v1/demand-forecasts`
- `POST /api/v1/demand-forecasts` (admin)
- `POST /api/v1/demand-forecasts/upload-csv` (admin)
- `POST /api/v1/schedules/generate` (admin)
- `GET /api/v1/dashboard/summary`

