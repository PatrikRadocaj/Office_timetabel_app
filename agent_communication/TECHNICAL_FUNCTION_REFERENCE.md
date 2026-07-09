# Technical Function Reference

Purpose: this document is a presentation-oriented guide to the maintained application code. It explains the named functions, methods, and UI callbacks in the FastAPI backend and React frontend so a technical presenter can describe how the project works end to end.

Scope:
- Included: `call-center-scheduler/backend/app/**` and `react-app/src/**`.
- Excluded: tests, generated build output, static image assets, dependency folders, local logs, and one-off scripts.
- Anonymous inline React event handlers are explained under the component or callback that owns them.

## System Map

The application has three main layers:

1. React/Vite frontend in `react-app/src`.
2. FastAPI backend in `call-center-scheduler/backend/app`.
3. Firebase Auth and Firestore as external services.

Main runtime flow:

1. User logs in or registers through React.
2. React stores the Firebase ID token and user profile in local storage.
3. API requests go through `apiRequest`, which attaches the bearer token.
4. FastAPI validates the token with Firebase, loads the local user profile from Firestore, and enforces role checks.
5. Router functions delegate business behavior to service classes.
6. Services use repository classes to read and write Firestore documents.

## Backend Entrypoint And Core

### `app/main.py`

- `lifespan(_)`: initializes Firebase when the FastAPI app starts.
- `dependency_error_handler(_, exc)`: converts dependency failures such as Firestore outage into structured JSON responses.
- `health()`: returns `{"status": "ok"}` for health checks.
- `serve_index()`: serves the React build for `/`.
- `serve_dashboard()`: serves the React build for `/dashboard`.
- `serve_admin()`: serves the React build for `/admin`.
- `serve_react_app()`: returns `react-app/dist/index.html` or a clear 404 if the React build is missing.

### `app/api/deps.py`

- `get_current_user(credentials)`: validates the bearer token with Firebase, loads the matching user profile, and rejects missing, invalid, deleted, or disabled sessions.
- `require_admin(current_user)`: allows only users with role `admin`; non-admin users receive a 403.

### `app/core/config.py`

- `Settings.validate_slot_minutes(value)`: enforces that schedule slots are multiples of 15 minutes.
- `Settings.parsed_cors_origins`: converts the comma-separated CORS setting into a list.
- `get_settings()`: returns cached runtime settings loaded from environment variables.

### `app/core/firebase.py`

- `initialize_firebase()`: initializes Firebase once using service-account JSON, service-account path, or application default credentials.
- `get_firestore_client()`: returns the Firestore client for the initialized Firebase app.
- `verify_id_token(id_token)`: verifies a Firebase ID token and checks whether it was revoked.
- `revoke_refresh_tokens(uid)`: revokes refresh tokens to force logout for a Firebase user.

### `app/core/timezones.py`

- `resolve_office_timezone(office)`: resolves an office timezone string into an IANA timezone object, defaulting safely when needed.

### `app/core/exceptions.py`

- `DependencyUnavailableError.__init__()`: stores dependency name, detail message, and HTTP status for infrastructure failures.

## Backend API Routers

Routers are thin HTTP adapters. They validate request/response models, enforce dependencies, and call services.

### Auth Router

- `register(payload)`: creates a Firebase Auth user and a local user profile.
- `login(payload)`: signs in with Firebase Identity Toolkit and returns token plus local profile.
- `logout(current_user)`: revokes the current user's Firebase refresh tokens.
- `me(current_user)`: returns the authenticated user's local profile.

### Offices Router

- `list_offices()`: returns offices sorted by name.
- `create_office(payload)`: creates an office after admin authorization.
- `update_office(office_id, payload)`: updates office fields after admin authorization.
- `delete_office(office_id)`: deletes an office only when reference guards allow it.

### Skills Router

- `list_skills()`: returns skills sorted by name.
- `create_skill(payload)`: creates a skill after admin authorization.
- `update_skill(skill_id, payload)`: updates skill fields after admin authorization.
- `delete_skill(skill_id)`: deletes a skill only when reference guards allow it.

### Agents Router

- `list_agents()`: returns agents sorted by full name.
- `create_agent(payload)`: creates an agent profile with office, skills, hours, and availability.
- `update_agent(agent_id, payload)`: updates an existing agent profile.
- `delete_agent(agent_id)`: deletes an agent profile.

### Demand Router

- `list_demand(start_at, end_at)`: lists expanded demand rows, optionally filtered by time.
- `create_demand(payload)`: saves one demand slot into compact daily storage.
- `create_daily_demand(payload)`: saves a full day grid as one compact Firestore document.
- `create_bulk_demand(payload)`: saves multiple demand items.
- `get_day_view(office_id, forecast_date, interval_minutes)`: returns a day grid with demand and latest active schedule coverage.
- `upload_demand_csv(file)`: imports CSV demand rows into compact daily storage.

### Schedules Router

- `generate_schedule(payload)`: runs schedule generation for a requested time range.

### Dashboard Router

- `summary(start_at, end_at)`: returns admin dashboard counts and coverage points.

### Me Router

- `my_dashboard(current_user)`: returns the agent-facing dashboard payload.
- `my_shifts(current_user)`: returns all authoritative shifts for the current agent.
- `my_availability(current_user)`: returns the current agent availability windows.
- `update_my_availability(payload, current_user)`: updates the current agent availability windows.

### Announcements Router

- `list_announcements()`: returns admin-visible announcements.
- `create_announcement(payload)`: creates an announcement.
- `update_announcement(announcement_id, payload)`: edits an announcement.
- `delete_announcement(announcement_id)`: deletes an announcement.

### Day-Off Request Routers

- `list_my_day_off_requests(current_user)`: lists requests belonging to the current agent.
- `create_my_day_off_request(payload, current_user)`: creates a pending day-off request.
- `list_day_off_requests()`: lists all day-off requests for admins.
- `review_day_off_request(request_id, payload, current_user)`: approves or rejects a pending day-off request.

### Shift-Swap Request Routers

- `my_shift_swap_options(current_user)`: returns source and target shift options for the current agent.
- `list_my_shift_swap_requests(current_user)`: lists the current agent's swap requests.
- `create_my_shift_swap_request(payload, current_user)`: creates a pending shift-swap request.
- `list_shift_swap_requests()`: lists all shift-swap requests for admins.
- `review_shift_swap_request(request_id, payload, current_user)`: approves or rejects a pending shift-swap request.

## Backend Models And Validators

Pydantic models define API contracts and perform input validation.

### Common Models

- `TimeWindow.ensure_start_before_end()`: ensures availability windows have `start_hour < end_hour`.
- `utcnow()`: returns a timezone-aware UTC timestamp for created/updated fields.

### Auth Models

- `RegisterRequest.validate_password_strength(value)`: requires uppercase, lowercase, and numeric password characters.
- `RegisterRequest.validate_public_role(value)`: prevents public registration from creating admin users.

### Agent Models

- `AgentBase.ensure_unique_skill_ids()`: prevents duplicate skill entries on one agent profile.

### Demand Models

- `SkillDemandSeriesCreate.validate_quantities(value)`: rejects negative or extremely large demand quantities.
- `DailyDemandForecastCreate.validate_interval_minutes(value)`: restricts compact daily demand to 30- or 60-minute intervals.
- `DailyDemandForecastCreate.validate_unique_skill_ids(value)`: prevents duplicate skills in one daily demand payload.
- `DailyDemandForecastCreate.validate_shape()`: checks the quantity array length and requires at least one non-zero demand slot.

### Day-Off Request Models

- `DayOffRequestCreate.ensure_end_after_start()`: requires the end date to be on or after the start date.
- `DayOffRequestReview.ensure_review_status()`: allows only approved or rejected review outcomes.

### Shift-Swap Request Models

- `ShiftSwapRequestCreate.ensure_distinct_assignments()`: prevents requesting a swap against the same assignment.
- `ShiftSwapRequestReview.ensure_review_status()`: allows only approved or rejected review outcomes.

## Backend Repositories

Repository classes isolate Firestore access from business logic.

### `FirestoreRepository`

- `__init__(collection_name)`: binds the repository to one Firestore collection.
- `_serialize(value)`: converts datetimes and nested values into API-safe JSON-compatible forms.
- `_doc_to_dict(document)`: converts a Firestore snapshot to a dict and injects the document id.
- `_aggregation_count_value(result)`: extracts an integer from Firestore aggregation count results.
- `_apply_filters(query, filters)`: applies Firestore where filters.
- `_wrap_firestore_error(exc)`: maps Firestore errors to user-friendly dependency errors.
- `create(data, document_id=None)`: creates a document and writes timestamps.
- `get(document_id)`: returns one document or `None`.
- `update(document_id, data)`: updates a document and returns the refreshed document.
- `delete(document_id)`: deletes a document and reports whether it existed.
- `list(filters=None, order_by=None, limit=None)`: streams documents with optional filters, sorting, and limit.
- `count(filters=None)`: uses Firestore aggregation count when available, otherwise falls back to streaming count.
- `list_by_document_id_prefix(prefix, limit=None)`: lists documents whose Firestore document id starts with a prefix.

### Collection Repositories

- `AgentsRepository.__init__()`: binds to `agents`.
- `AnnouncementsRepository.__init__()`: binds to `announcements`.
- `DayOffRequestsRepository.__init__()`: binds to day-off request storage.
- `DemandForecastsRepository.__init__()`: binds to `demand_forecasts`.
- `OfficesRepository.__init__()`: binds to `offices`.
- `ShiftSwapRequestsRepository.__init__()`: binds to shift-swap request storage.
- `SkillsRepository.__init__()`: binds to `skills`.
- `UsersRepository.__init__()`: binds to `users`.
- `UsersRepository.get_by_email(email)`: finds a user profile by email.

### `SchedulesRepository`

- `_as_utc(value)`: normalizes schedule timestamps to UTC.
- `SchedulesRepository.__init__()`: binds to generated schedule storage.
- `SchedulesRepository.list_active(...)`: returns only schedules considered active for dashboards and shift logic.
- `SchedulesRepository.count_active()`: counts only active schedules.

## Backend Services

### `AuthService`

- `__init__()`: loads settings and the users repository.
- `register(payload)`: creates a Firebase user, persists a local agent-role profile, rolls back Firebase on profile persistence failure, and returns auth tokens.
- `login(payload)`: signs in through Firebase, creates a fallback local profile if needed, rejects disabled accounts, and returns auth tokens.
- `logout(uid)`: revokes Firebase refresh tokens.
- `_identity_toolkit_request(endpoint, body)`: calls Firebase Identity Toolkit and maps network or auth errors.
- `_map_auth_error(error_code)`: converts Firebase error codes into HTTP status and message pairs.
- `_build_auth_response(user_doc, firebase_data)`: builds the typed API response from local profile plus Firebase token data.

### `OfficeService`

- `__init__()`: initializes office, agent, demand, and schedule repositories.
- `create(payload)`: validates unique office name and IANA timezone before creating.
- `list()`: returns offices by name.
- `update(office_id, payload)`: validates duplicates and timezone before updating.
- `delete(office_id)`: blocks deletion when agents, demand, or schedules still reference the office.
- `_ensure_unique_name(name, current_office_id)`: checks for duplicate office names excluding the current office.
- `_reference_counts(office_id)`: counts records that reference an office.

### `SkillService`

- `__init__()`: initializes skill, agent, demand, and schedule repositories.
- `create(payload)`: creates a skill after duplicate-name check.
- `list()`: returns skills by name.
- `update(skill_id, payload)`: updates a skill after duplicate-name check.
- `delete(skill_id)`: blocks deletion when agents, demand, or schedules still reference the skill.
- `_ensure_unique_name(name, current_skill_id)`: checks for duplicate skill names excluding the current skill.
- `_reference_counts(skill_id)`: counts records that reference a skill.

### `AgentService`

- `__init__()`: initializes agent, office, skill repositories and settings.
- `create(payload)`: validates office/skill references, hard weekly-hour limit, and unique email.
- `list()`: returns agents by full name.
- `update(agent_id, payload)`: validates hard weekly-hour limit and updated office/skill references.
- `delete(agent_id)`: deletes an agent profile.
- `_validate_agent_references(office_id, skills)`: confirms referenced office and skills exist.

### Catalog Helper Functions

- `_ensure_aware_utc(timestamp)`: parses or normalizes timestamps to UTC.
- `_validate_iana_timezone(timezone_name)`: validates a timezone name with Python `zoneinfo`.
- `_count_filtered(repo, filters)`: counts filtered repository rows, preferring repository `count`.
- `_count_agents_referencing_skill(repo, skill_id)`: counts agents that carry a skill.
- `_count_demand_referencing_skill(repo, skill_id)`: counts demand documents that reference a skill in old or compact storage.
- `_count_schedules_referencing(repo, office_id=None, skill_id=None)`: counts schedules containing assignments for an office or skill.
- `_assignment_matches(assignment, office_id=None, skill_id=None)`: checks whether one assignment references a target office or skill.
- `_skill_entry_id(entry)`: extracts `skill_id` from either dict or model entries.
- `_raise_referenced_conflict(resource_name, reference_counts)`: raises 409 with reference counts when deletion is unsafe.

### `DemandService`

- `__init__()`: initializes demand, office, skill, and schedule repositories.
- `create(payload)`: writes a single demand slot into a deterministic compact daily document.
- `create_bulk(payload)`: saves multiple single-slot demand rows.
- `create_daily(payload)`: saves one complete daily demand grid as one compact document.
- `ingest_csv(file)`: validates and imports CSV demand rows.
- `list(start_at=None, end_at=None)`: expands compact demand into slot rows and filters by time window.
- `day_view(office_id, forecast_date, interval_minutes)`: builds the admin graph grid with demand totals and latest active schedule coverage.
- `_resolve_office_timezone(office)`: delegates office timezone resolution.
- `_validate_references(office_id, skill_id)`: validates office and skill ids for demand writes.
- `_daily_document_id(office_id, forecast_date, interval_minutes)`: builds deterministic compact demand document ids.
- `_daily_document_payload(payload, forecast_batch_id)`: converts daily grid input into compact Firestore payload shape.
- `_represented_slot_count(skill_demands)`: counts non-zero slot quantities.
- `_list_daily_documents(office_id, forecast_date, interval_minutes)`: finds compact daily docs using document-id prefix where available.
- `_upsert_daily_document(document_id, data)`: updates an existing compact document or creates it.
- `_normalize_skill_demands(raw_entries, slot_count)`: pads and coerces compact skill demand arrays.
- `_expand_documents(documents, office_cache=None)`: expands compact docs and passes through legacy single-slot docs.
- `_is_compact_daily_document(document)`: identifies compact daily demand documents.
- `_expand_compact_daily_document(document, office_cache=None)`: converts compact daily storage into slot-level rows and skips malformed compact docs safely.

### `SchedulerService`

- `_as_utc(value)`: normalizes schedule timestamps to UTC.
- `__init__()`: initializes demand, agent, office, skill, schedule repositories and settings.
- `generate(payload)`: loads demand, ranks eligible agents, assigns agents greedily, writes an active generated schedule, and returns metrics.
- `_load_demand(start_at, end_at)`: asks `DemandService` for demand rows in the requested window.
- `_group_demand_by_slot_and_skill(rows)`: groups demand rows by slot start/end.
- `_rank_eligible_agents(...)`: filters agents by skill, availability, weekly hours, rest, and shift preference; returns the best candidates first.
- `_agent_has_skill(agent, skill_id, min_proficiency)`: checks skill coverage and proficiency.
- `_agent_is_available(agent, slot_start, slot_end, office_tz)`: checks whether a slot fits the agent's local availability windows.
- `_shift_preference_penalty(preference, slot_hour)`: scores day/night/any preference as a soft scheduling signal.

### `DashboardService`

- `_as_utc(value)`: normalizes timestamps to UTC.
- `__init__()`: initializes repositories used for counts and coverage.
- `summary(start_at=None, end_at=None)`: returns aggregate entity counts plus coverage points from recent active schedules.

### `MeService`

- `_as_utc(value)`: normalizes timestamps to UTC.
- `_resolve_timezone(timezone_name)`: returns a timezone object or UTC fallback.
- `_build_greeting(current_local_time)`: chooses morning, afternoon, or evening greeting.
- `__init__()`: initializes repositories used by personal dashboards.
- `dashboard(current_user)`: builds the agent dashboard, including today status, week schedule, hours, skills, availability, and announcements.
- `shifts(current_user)`: returns all authoritative shifts for the current agent.
- `availability(current_user)`: returns the current agent availability or 404 when no agent profile exists.
- `update_availability(current_user, availability)`: writes updated availability windows to the current agent profile.
- `_resolve_agent_profile(current_user)`: links a user to an agent profile by user id or email.
- `_collect_agent_slot_assignments(agent_id)`: reads active schedules newest first so newer schedules override older matching slots.
- `_build_weekly_schedule(...)`: builds seven dashboard rows for the current local week.
- `_build_shift_rows(...)`: converts raw assignments into day-level rows with office, skills, time, and hours.
- `_empty_day_row(current_day)`: creates a zero-hour day row.
- `_build_skills(agent, skills_by_id)`: maps agent skill ids to display names and proficiency percentages.
- `_availability(agent)`: returns normalized availability windows.
- `_load_announcements()`: returns up to ten active announcements newest first.

### `AnnouncementService`

- `__init__()`: stores a lazy repository slot.
- `repo`: lazily creates the announcements repository.
- `list()`: returns normalized announcements newest first.
- `create(payload)`: creates an announcement and stamps `published_at`.
- `update(announcement_id, payload)`: updates an announcement or returns 404.
- `delete(announcement_id)`: deletes an announcement or returns 404.
- `_normalize(row)`: fills legacy announcement fields such as missing title or old `body`.

### `DayOffRequestService`

- `__init__()`: stores lazy repository slots.
- `repo`: lazily creates the day-off request repository.
- `agents_repo`: lazily creates the agents repository.
- `list_for_agent(current_user)`: lists only requests belonging to the current agent.
- `create_for_agent(current_user, payload)`: creates a pending request and records schedule-impact policy.
- `list_for_admin()`: lists all requests newest first.
- `review(request_id, payload, current_user)`: approves or rejects a pending request and stamps reviewer metadata.
- `_require_agent_profile(current_user)`: returns the current agent or raises 404.
- `_resolve_agent_profile(current_user)`: links user to agent by user id or email.
- `_sort_newest_first(rows)`: orders requests by requested or created timestamp.
- `_normalize(row)`: guarantees schedule-impact policy is present.

### `ShiftSwapRequestService`

- `AssignmentRef.schedule_id`: returns the referenced schedule id.
- `AssignmentRef.assignment_key`: returns the stable assignment key.
- `_as_utc(value)`: normalizes timestamps to UTC.
- `assignment_key(assignment)`: builds a unique assignment key from slot, office, and skill.
- `__init__()`: stores lazy repository slots.
- `repo`, `agents_repo`, `offices_repo`, `skills_repo`, `schedules_repo`: lazy repository properties.
- `options_for_agent(current_user)`: returns source shifts and eligible target shifts for the current agent.
- `list_for_agent(current_user)`: lists the current agent's swap requests.
- `create_for_agent(current_user, payload)`: validates a requested swap and creates a pending request.
- `list_for_admin()`: lists all swap requests newest first.
- `review(request_id, payload, current_user)`: approves or rejects a pending swap; approval applies the schedule update.
- `_apply_approved_swap(request)`: rewrites the affected active schedule assignments with swapped agent ids.
- `_validate_swap_pair(...)`: enforces role ownership, office match, skill match, availability, overlap, and duplicate-assignment rules.
- `_find_ref(refs, schedule_id, key)`: finds one authoritative assignment reference.
- `_authoritative_assignment_refs()`: derives latest-per-slot active assignment refs from generated schedules.
- `_ensure_no_duplicate_pending_request(requester_agent_id, payload)`: blocks duplicate pending swap requests.
- `_require_agent_profile(current_user)`: returns the current agent or raises 404.
- `_resolve_agent_profile(current_user)`: links user to agent by user id or email.
- `_active_agents_by_id()`: maps active agents by id.
- `_agent_has_skill(agent, skill_id, skills)`: checks proficiency against the skill requirement.
- `_has_overlapping_assignment(...)`: detects conflicting assignments for a target agent.
- `_overlaps(first_start, first_end, second_start, second_end)`: checks interval overlap.
- `_copy_assignment_with_swapped_agent(assignment, old_agent_id, new_agent_id)`: returns an assignment copy with one agent replaced safely.
- `_sort_newest_first(rows)`: orders requests by requested or created timestamp.
- `_normalize(row)`: guarantees schedule-impact policy is present.
- `_option_for_ref(ref, agent, offices, skills)`: builds a UI option object for a shift assignment.
- `_shift_snapshot(ref, agent, offices, skills)`: records a request-time shift snapshot.

## React Frontend

### `src/main.tsx`

This file boots the React app, mounts `App`, and wraps routing in the browser router.

### `src/App.tsx`

- `App()`: defines the top-level routes for `/`, `/dashboard`, and `/admin`.
- `syncSession()`: reloads token and user profile from local storage after login, logout, or forced session cleanup.

### `src/routes/ProtectedRoute.tsx`

- `ProtectedRoute({ token, user, requireAdmin, children })`: redirects unauthenticated users to `/`, redirects non-admin users away from `/admin`, and renders protected content otherwise.

### `src/components/AlertBanner.tsx`

- `AlertBanner({ type, message, onClose })`: renders a dismissible Bootstrap alert for success, warning, info, or danger messages.

### `src/lib/auth.ts`

- `getAuthToken()`: reads the stored bearer token.
- `getCurrentUser()`: reads and parses the stored user profile.
- `saveAuth(payload)`: stores token and user after successful authentication.
- `clearAuth()`: removes token and user from local storage.
- `isLoggedIn()`: returns whether a token currently exists.

### `src/lib/api.ts`

- `ApiError.constructor(message, status, payload)`: creates a typed API error with HTTP status and response payload.
- `normalizeApiMessage(value)`: lowercases and trims backend detail text for comparisons.
- `formatReferenceCounts(value)`: formats delete-guard reference counts for UI alerts.
- `formatErrorDetail(detail, fallback)`: converts backend string, list, or object error details into a display message.
- `isSessionEndingAuthError(error)`: treats 401, disabled-user 403, and missing-profile 404 as session-ending errors.
- `apiRequest(path, options)`: sends fetch requests to `/api/v1`, attaches auth headers, parses JSON, clears auth on session-ending errors, and throws `ApiError` on failure.

### `src/lib/format.ts`

- `requireValue(value, label)`: throws when a required form field is blank.
- `formatDate(value)`: formats a date-like value for display.
- `formatTime(value)`: formats a time-like value as hour and minute.
- `formatDateTime(value)`: formats a timestamp for display.
- `formatHours(value)`: formats numeric hours with sensible rounding.
- `todayIsoDate()`: returns today's local date as `yyyy-mm-dd`.
- `buildTimeBlocks(intervalMinutes)`: builds `HH:mm` labels for a 24-hour grid.
- `normalizeSkillIds(ids)`: de-duplicates and sorts selected skill ids.

### `src/pages/AuthPage.tsx`

- `AuthPage({ token, user, onSessionChange })`: shows login/register forms and redirects authenticated users to `/dashboard`.
- `handleLogin(event)`: validates form input, posts `/auth/login`, stores auth, refreshes app session, and navigates to dashboard.
- `handleRegister(event)`: validates form input, posts `/auth/register`, stores auth, refreshes app session, and navigates to dashboard.

### `src/pages/DashboardPage.tsx`

Helper functions:

- `defaultAvailabilityWindow()`: creates a default Monday 09:00-17:00 availability row.
- `normalizeAvailability(windows)`: coerces loaded availability into valid integer rows.
- `validateAvailability(windows)`: validates day/hour ranges and start-before-end.
- `formatHour(hour)`: formats an integer hour as `HH:00`.
- `formatAvailabilityLabel(window)`: converts an availability window into readable day and time text.
- `optionValue(option)`: serializes a shift-swap option into a select value.
- `parseOptionValue(value)`: parses a selected shift-swap option.
- `formatShiftSwapOption(option, includeAgent=false)`: formats a shift option for the swap UI.

Component and callbacks:

- `DashboardPage({ user, onSessionChange })`: renders the personal dashboard, quick actions, day-off requests, shift swaps, full shift list, and availability editor.
- `handleSessionEnded()`: clears session state and redirects to login.
- `handleActionError(error, fallback)`: handles API errors, including session-ending errors.
- `loadDashboard()`: loads `/me/dashboard` and prevents protected UI rendering after invalid sessions.
- `handleLogout()`: calls logout where possible, clears local auth, and redirects to login.
- `openDayOffRequests()`: loads existing day-off requests and opens the request panel.
- `submitDayOffRequest(event)`: creates a new day-off request.
- `openShiftSwapRequests()`: loads shift-swap options and current requests.
- `submitShiftSwapRequest(event)`: creates a pending shift-swap request.
- `openAllShifts()`: loads all current agent shifts.
- `openAvailability()`: loads the current agent availability form.
- `addAvailabilityWindow()`: appends a default availability row.
- `updateAvailabilityWindow(index, patch)`: edits one availability row.
- `removeAvailabilityWindow(index)`: removes one availability row.
- `saveAvailability(event)`: validates and saves availability to `/me/availability`.

### `src/pages/AdminPage.tsx`

Top-level helper functions:

- `toDateTimeLocalValue(value)`: converts a `Date` into a browser datetime-local string.
- `addDaysToDateValue(dateValue, days)`: adds days to a `yyyy-mm-dd` value.
- `getZonedParts(value, timeZone)`: extracts date/time parts in a target IANA timezone.
- `getTimeZoneOffsetMs(value, timeZone)`: computes the timezone offset for a date.
- `officeLocalDateTimeToUtc(dateValue, timeZone, hour=0, minute=0)`: converts office-local date/time to UTC.
- `defaultScheduleStart()`: returns the default schedule start datetime-local value.
- `defaultScheduleEnd()`: returns the default schedule end datetime-local value.
- `formatPercent(value)`: formats a ratio as a percentage.
- `defaultAvailabilityWindow()`: creates a default availability row.
- `normalizeAvailability(windows)`: normalizes loaded availability rows.
- `validateAvailability(windows)`: validates availability row values.
- `formatHour(hour)`: formats an integer hour as `HH:00`.
- `formatAvailabilityLabel(window)`: renders availability as readable text.
- `formatSwapShift(shift, includeAgent=false)`: formats shift-swap request shifts for admin review.
- `AvailabilityEditor({ windows, onAdd, onUpdate, onRemove, compact })`: reusable availability editing UI for agent create/edit.

Main component and callbacks:

- `AdminPage({ user, onSessionChange })`: renders the admin panel for summary, catalog CRUD, demand, schedule generation, announcements, day-off review, and shift-swap review.
- `handleSessionEnded()`: clears invalid sessions and redirects to login.
- `handleApiError(error, fallback)`: shows API errors or ends the session when appropriate.
- `loadAdminSummary(options)`: loads `/dashboard/summary` and computes summary display values.
- `init()`: initial admin data loader for offices, skills, agents, demand, announcements, requests, and summary.
- `clearAdminAlert()`: dismisses current admin alert.
- `demandSelectionKey(ids)`: creates a stable key for selected demand skills.
- `logout()`: logs out the admin and returns to login.
- `reloadOffices()`, `reloadSkills()`, `reloadAgents()`, `reloadDemand()`, `reloadAnnouncements()`, `reloadDayOffRequests()`, `reloadShiftSwapRequests()`: refresh individual admin datasets.
- `addPendingSkill()`: adds a selected skill/proficiency row to the new-agent form.
- `addAgentAvailabilityWindow()`, `updateAgentAvailabilityWindow(index, patch)`, `removeAgentAvailabilityWindow(index)`: manage new-agent availability rows.
- `submitOffice(event)`: creates an office.
- `submitSkill(event)`: creates a skill.
- `submitAgent(event)`: creates an agent with skills and availability.
- `startOfficeEdit(office)`: opens office edit state.
- `updateOffice()`: saves office edits.
- `deleteOffice(office)`: confirms and deletes an office, displaying 409 reference counts if blocked.
- `startSkillEdit(skill)`: opens skill edit state.
- `updateSkill()`: saves skill edits.
- `deleteSkill(skill)`: confirms and deletes a skill, displaying 409 reference counts if blocked.
- `startAgentEdit(agent)`: opens agent edit state.
- `addEditAgentSkill()`: adds a skill row to the edit-agent form.
- `updateEditAgentSkillProficiency(skillId, proficiency)`: updates edit-agent skill proficiency.
- `removeEditAgentSkill(skillId)`: removes a skill from the edit-agent form.
- `addEditAgentAvailabilityWindow()`, `updateEditAgentAvailabilityWindow(index, patch)`, `removeEditAgentAvailabilityWindow(index)`: manage edit-agent availability rows.
- `updateAgent()`: saves agent edits.
- `deleteAgent(agent)`: confirms and deletes an agent.
- `submitAnnouncement(event)`: creates an announcement.
- `startAnnouncementEdit(announcement)`: opens announcement edit state.
- `updateAnnouncement()`: saves announcement edits.
- `toggleAnnouncementActive(announcement)`: activates or deactivates an announcement.
- `deleteAnnouncement(announcement)`: confirms and deletes an announcement.
- `reviewDayOffRequest(request, status)`: approves or rejects a day-off request.
- `reviewShiftSwapRequest(request, status)`: approves or rejects a shift-swap request.
- `loadDayView(officeId, dateValue, intervalMinutes)`: loads one office/day demand graph payload.
- `generateDemandGrid()`: creates an editable demand grid for selected office, date, interval, and skills.
- `saveDailyDemand(event)`: validates and posts compact daily demand.
- `uploadCsv(event)`: uploads CSV demand.
- `loadChart(options)`: loads the demand/coverage graph.
- `applyOfficeLocalScheduleWindow(days)`: fills schedule start/end using selected office-local date rules.
- `generateSchedule(event)`: posts schedule generation, shows assignment results, and refreshes summary/graph.
- `setAllDemandSkills(checked)`: selects or clears all demand skills.

## Presentation Workflows

### Authentication

React `AuthPage` calls `/auth/login` or `/auth/register`. `AuthService` communicates with Firebase Identity Toolkit, stores/loads the local user profile in Firestore, and returns an ID token. Later requests pass through `get_current_user`, which verifies the token and loads the profile.

### Admin Catalog Management

Admin routes use `require_admin`. Office, skill, and agent routers call `OfficeService`, `SkillService`, and `AgentService`. These services validate duplicates, references, timezones, and hard safety limits before calling Firestore repositories.

### Demand Forecasting

Admin demand UI builds either a grid or CSV upload. `DemandService` stores demand compactly as one document per office/day/interval where practical, then expands it into slot rows for lists, graphing, and schedule generation.

### Schedule Generation

`SchedulerService.generate` loads demand rows, active agents, offices, and skills. It groups demand by slot, ranks eligible agents, respects availability and weekly-hour constraints, writes an active generated schedule, and returns assignment metrics.

### Personal Dashboard

`MeService.dashboard` resolves the current user to an agent profile, reads active generated schedules, applies newest-schedule-wins semantics for duplicate slots, and returns a weekly dashboard plus skills, hours, availability, and announcements.

### Day-Off Requests

Agents create requests through Dashboard quick actions. Admins review them in AdminPage. Approval records the decision and review metadata; automatic schedule regeneration is intentionally separate from the request record.

### Shift-Swap Requests

Agents choose a source shift and target shift from active schedules. `ShiftSwapRequestService` validates ownership, office match, skill match, availability, overlaps, and duplicate pending requests. Admin approval applies the swap to the active schedule assignment.

## Technical Talking Points

- The project uses a strict split between routers, services, repositories, and models.
- Firestore access is centralized in `FirestoreRepository`, which keeps serialization, count optimization, and dependency error mapping consistent.
- Demand storage is compact to reduce Firestore document count while still exposing slot-level rows to the scheduler and graph UI.
- Schedule visibility is based on active generated schedules with newer schedules overriding older assignments for the same slot.
- React has centralized API/session behavior in `apiRequest`, so expired, deleted, and disabled sessions clear local auth consistently.
- Admin-only authorization is enforced in three places: React route guard, admin page behavior, and backend `require_admin`.
