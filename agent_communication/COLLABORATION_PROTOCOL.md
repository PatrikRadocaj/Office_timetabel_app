# Codex + Claude Collaboration Protocol

Last updated: 2026-07-09

## Purpose

Create one professional workflow that lets Codex, Claude, and the user develop the application across sessions without losing context, duplicating decisions, or overwriting each other's work.

## Recommended Communication Channel

Primary channel: this Git repository, specifically the `agent_communication/` folder.

Why this is the best practical option:

- Both AIs can read and update plain Markdown files.
- The documentation travels with the code and can be committed with changes.
- Status, decisions, and handoffs are reviewable in git history.
- It avoids dependence on a separate tool such as Notion that may not be available to both agents.

Optional secondary channel: GitHub issues or pull requests if the project moves to an active remote workflow. Use issues for user-visible tasks and PRs for reviewable code changes. The repo documentation remains the source of truth.

## Shared Source Of Truth

- Protocol: `agent_communication/COLLABORATION_PROTOCOL.md`
- Project state: `agent_communication/PROJECT_DOCS.md`
- Append-only handoffs/status: `agent_communication/TASK_LOG.md`
- Message templates: `agent_communication/HANDOFF_TEMPLATE.md`
- User manual: `agent_communication/USER_MANUAL.md`
- QA protocol: `call-center-scheduler/TEST_PROTOCOL.md`

Older files under `agent_communication/` and `call-center-scheduler/QA_*` remain useful historical context, but the files above are the active workflow.

## Roles

The user is the product owner and final decision maker for product scope, priorities, acceptance criteria, and unresolved tradeoffs.

Codex and Claude should use task roles, not permanent ownership:

- Driver: implements the current task, updates tests and docs, and writes the handoff.
- Reviewer: checks correctness, maintainability, regressions, security, and missing tests.
- QA agent: executes the QA protocol and records evidence.
- Architect: proposes major technical decisions and records accepted decisions.

Only one agent should be Driver for a given task or overlapping file set at a time.

## Workflow

1. Intake
   - Read the shared docs and latest task log.
   - Identify the task ID, goal, acceptance criteria, and impacted files.
   - If the task is ambiguous, record assumptions before editing.

2. Planning
   - For small changes, write a short plan in the task log.
   - For larger changes, include risks, test strategy, and ownership boundaries.
   - Mark one agent as Driver.

3. Implementation
   - Keep edits scoped to the task.
   - Follow existing project patterns before introducing new abstractions.
   - Avoid changing unrelated files, generated logs, credentials, or local environment files.

4. Verification
   - Run the narrowest useful tests first.
   - Run broader regression checks when auth, scheduling, data models, routing, or shared UI behavior changes.
   - After backend code changes, restart the running Uvicorn process from the current worktree, or use `uvicorn --reload`, before any manual smoke test. Do not trust results from a stale backend process.
   - Record commands and outcomes in the task log.

5. Documentation
   - Update `PROJECT_DOCS.md` when architecture, stack, file structure, tasks, known issues, or decisions change.
   - Update `USER_MANUAL.md` when install, setup, workflows, features, or troubleshooting change.
   - Update QA docs when a test case, risk area, or acceptance gate changes.

6. Handoff
   - Append a structured handoff to `TASK_LOG.md`.
   - Include changed files, tests run, open questions, and exact next steps.
   - If another agent should continue, state the requested next role clearly.

7. Review
   - The reviewer leads with findings, ordered by severity.
   - Findings must reference files, behavior, evidence, and expected fix direction.
   - If no issue is found, state residual risk and any tests not run.

## Task Division Rules

- Use one task owner per change.
- Do not let two agents edit the same file family in parallel unless the split is explicit.
- Backend API/model changes and frontend consumer changes should be coordinated in the same task or through a written contract.
- Security, auth, scheduler, and data-migration changes require review before being considered done.
- Documentation-only tasks can be done by either agent but still need a task log entry.

## Decision-Making Process

Use the decisions section in `PROJECT_DOCS.md`.

Decision statuses:

- Proposed: suggested but not approved.
- Accepted: current rule.
- Superseded: replaced by a later decision.
- Rejected: considered and declined.

Decision rules:

- The user decides product behavior and major architecture choices.
- The Driver may make local implementation decisions when reversible and consistent with the current architecture.
- Any decision that changes framework, database, auth model, deployment path, or core workflow must be recorded.
- If Codex and Claude disagree, each should write a short option analysis with recommendation, risk, and migration cost. The user decides.

## Version Control Approach

Recommended branch naming:

- `codex/<short-task-name>` for Codex-driven branches.
- `claude/<short-task-name>` for Claude-driven branches.
- `docs/<short-doc-task>` for documentation-only branches.

Commit guidance:

- Keep commits focused and reviewable.
- Pair code changes with relevant tests/docs.
- Do not commit local runtime logs, service account files, API keys, generated secrets, or temporary backups unless explicitly required and sanitized.
- Before handoff, run `git status --short --branch` and record notable dirty state.

PR guidance if GitHub is used:

- PR title should include task ID and short behavior summary.
- PR body should include changed behavior, tests run, screenshots if UI changed, and open risks.
- Draft PRs are preferred until the QA gate passes.

## Code Review Style

Reviewers should prioritize:

1. Correctness bugs and regressions.
2. Security and authorization issues.
3. Data integrity and migration risks.
4. Missing tests for changed behavior.
5. Maintainability issues that affect future work.

Avoid style-only churn unless it blocks readability or violates established project patterns.

## Standard AI Message Formats

### Status Update

```markdown
## Status Update
- Agent:
- Task ID:
- Timestamp:
- Current state:
- Completed:
- In progress:
- Blockers:
- Files touched:
- Commands/tests run:
- Next step:
```

### Handoff

```markdown
## AI Handoff
- From:
- To:
- Task ID:
- Timestamp:
- Goal:
- Current status:
- Files changed:
- Important context:
- Commands/tests run:
- Results/evidence:
- Decisions made:
- Known issues:
- Open questions:
- Requested next action:
```

### Review Finding

```markdown
## Review Finding
- Severity: Blocker | High | Medium | Low
- File/area:
- Issue:
- Why it matters:
- Evidence:
- Suggested fix:
```

### Decision Record

```markdown
| ID | Date | Status | Decision | Rationale | Owner |
|---|---|---|---|---|---|
```

## Definition Of Done

A task is done only when:

- Acceptance criteria are met.
- Relevant tests/checks have passed or skipped checks are explicitly justified.
- Documentation and user manual are updated if behavior changed.
- Known residual issues are recorded.
- `TASK_LOG.md` contains a handoff or completion entry.
- No unrelated local changes were introduced.
