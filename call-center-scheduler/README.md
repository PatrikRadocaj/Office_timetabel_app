# Call Center Scheduler (School Project)

Professional scheduler web app for a 24/7/365 multi-office call center.

Stack:
- Frontend: React + Vite + TypeScript + Bootstrap 5 + Chart.js
- Backend: Python FastAPI
- Auth/DB: Firebase Authentication + Firestore
- Integration: JSON REST API (`/api/v1/...`)

## 1) Project Structure

```text
web projekt/
  react-app/
    index.html
    package.json
    vite.config.ts
    src/
      App.tsx
      pages/
      components/
      lib/
      routes/
  call-center-scheduler/
    backend/
      .env.example
      Dockerfile
      requirements.txt
      app/
        main.py
        api/
        core/
        models/
        repositories/
        services/
      tests/
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
CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173

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
- API server: `http://localhost:8000/`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/health`

## 4) Frontend Setup (React)

From the workspace root:

```powershell
cd ..\react-app
npm install
npm run dev
```

Open:

- React app: `http://localhost:5173/`
- Backend API: `http://localhost:8000/`

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`.

For a production-style local build:

```powershell
cd ..\react-app
npm run build
```

After a React build exists, FastAPI can serve the compiled React app from `http://localhost:8000/`.

## 5) Seed Sample Data

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

## 6) First Admin User

1. Open `http://localhost:5173/` and register a user.
2. In Firestore console, open `users` collection.
3. Find the new user document (doc ID = Firebase UID) and set:
   - `role: "admin"`
4. Log in again. You can now use `/admin`.

## 7) Docker Run

Create `backend/.env` first, then:

```powershell
docker compose up --build
```

App runs at `http://localhost:8000/`.

Docker builds the React frontend and serves the compiled app through FastAPI.

## 8) Main Features

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

## 9) Key API Endpoints

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
