# Shared AI Development Entrypoint

This repository is maintained with a shared Codex + Claude workflow.

Before making changes, every AI agent should read these files in order:

1. `agent_communication/COLLABORATION_PROTOCOL.md`
2. `agent_communication/PROJECT_DOCS.md`
3. `agent_communication/TASK_LOG.md`
4. `call-center-scheduler/TEST_PROTOCOL.md` when changing behavior that needs QA
5. `agent_communication/USER_MANUAL.md` when changing user-visible behavior

Working rules:

- Treat `agent_communication/PROJECT_DOCS.md` as the current source of truth.
- Append status and handoffs to `agent_communication/TASK_LOG.md`.
- Record architectural or workflow decisions in the decisions section of `PROJECT_DOCS.md`.
- Keep docs and manual updates in the same change as user-facing behavior changes.
- Do not overwrite another agent's in-progress work. If scope overlaps, write a handoff note first.
- Do not commit credentials, local runtime logs, or generated secrets.

For Claude-specific startup notes, see `CLAUDE.md`. Both files intentionally point to the same shared documentation.
