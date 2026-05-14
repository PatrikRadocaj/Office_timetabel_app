# QA Feedback for Coding Agent

## Context
- Date: 2026-05-09
- Cycle: Retest Cycle 2 (after your remediation response)
- Scope tested: Auth/AuthZ matrix, token protection, dependency error contract, targeted security abuse test.
- Environment: Windows, local backend `http://localhost:8000`.

## Executive Summary
Most previously reported issues are fixed and verified in runtime. However, one new High-severity authorization vulnerability is open: public users can self-register with `role=admin` and obtain admin-only access.

## Defect Report (Current Open)

### 1) Self-registration privilege escalation (`role=admin` accepted)
1. Title
- Public user can create admin account during registration
2. Severity
- `High`
3. Environment
- Windows local environment, FastAPI backend on `http://localhost:8000`
4. Preconditions
- Register endpoint reachable
- No prior privileges required
5. Steps to reproduce
- Send `POST /api/v1/auth/register` with payload:
  - `email`: any new email
  - `password`: valid strong password
  - `full_name`: any
  - `role`: `admin`
- Login with the new account via `POST /api/v1/auth/login`
- Call admin-only endpoint, e.g. `GET /api/v1/agents` with returned bearer token
6. Actual result
- Registration succeeds with user role `admin`
- Admin-only endpoint returns `200` for this self-created account
7. Expected result
- Public registration must never allow user-controlled admin role assignment
- Role must default to non-admin (agent) unless assigned by a trusted admin workflow
8. Evidence
- API response from register contains `"role":"admin"`
- Authenticated call to `GET /api/v1/agents` returns `200`
9. Affected file/endpoint (if known)
- Endpoint: `POST /api/v1/auth/register`
- Likely files:
  - `backend/app/models/auth.py`
  - `backend/app/services/auth_service.py`

## Verification of Previously Reported Fixes

### Fixed and Verified
- Missing token protection on read routes:
  - `GET /api/v1/offices` -> `401` (no token)
  - `GET /api/v1/skills` -> `401` (no token)
  - `GET /api/v1/agents` -> `401` (no token)
  - `GET /api/v1/demand-forecasts` -> `401` (no token)
  - `GET /api/v1/dashboard/summary` -> `401` (no token)
- Role restrictions:
  - Agent token gets `403` on admin-only routes (`/agents`, `/demand-forecasts`)
- Core auth sanity:
  - Valid register -> `200`
  - Weak password -> `422`
  - Valid login -> `200`
  - Wrong password -> `401`
  - Logout -> `200`
- Controlled dependency error contract:
  - Structured `503` payload with `detail` and `dependency` confirmed via targeted simulation

### No Longer Reproducible as Original Blocker
- Original Firestore-related raw `500` behavior is mitigated by controlled dependency error handling.

## Required Fix for This Cycle
1. Remove client authority over role during self-register.
- Ignore incoming role in public register flow and force default role (`agent`), OR reject any non-agent role with `403`/`422`.
2. Add server-side guardrail tests.
- Add automated test ensuring `role=admin` in register payload cannot produce admin user.

## Suggested Implementation Direction
- In `RegisterRequest`, either remove `role` field from public schema or constrain it to fixed default.
- In `AuthService.register`, set persisted role explicitly from trusted server logic, not from request body.

## QA Status
- Overall verdict: `Needs Minor Fixes`
- QA gate: `FAIL` (open `High` defect)
