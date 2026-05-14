"""Users repository."""

from __future__ import annotations

from app.repositories.firestore_repository import FirestoreRepository


class UsersRepository(FirestoreRepository):
    def __init__(self):
        super().__init__("users")

    def get_by_email(self, email: str) -> dict | None:
        matches = self.list(filters=[("email", "==", email)], limit=1)
        return matches[0] if matches else None
