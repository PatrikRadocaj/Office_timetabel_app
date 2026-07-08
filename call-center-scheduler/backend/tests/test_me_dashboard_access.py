"""Access behavior for the personal dashboard endpoint."""

from __future__ import annotations

from app.services.me_service import MeService


class EmptyRepository:
    def list(self, *_, **__):
        return []


def test_admin_user_can_receive_generic_personal_dashboard() -> None:
    """Admins are employees too, so they may open the normal dashboard."""

    service = object.__new__(MeService)
    service.agents_repo = EmptyRepository()
    service.skills_repo = EmptyRepository()
    service.offices_repo = EmptyRepository()
    service.schedules_repo = EmptyRepository()
    service.announcements_repo = EmptyRepository()

    payload = service.dashboard(
        {
            "id": "admin-user-1",
            "email": "admin@example.com",
            "full_name": "Admin User",
            "role": "admin",
        }
    )

    assert payload["full_name"] == "Admin User"
    assert payload["is_scheduled_today"] is False
    assert payload["status_text"] == "You have a day off today"
    assert len(payload["weekly_schedule"]) == 7
    assert payload["skills"] == []
    assert payload["announcements"] == []
