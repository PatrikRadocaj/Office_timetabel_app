"""Agents repository."""

from app.repositories.firestore_repository import FirestoreRepository


class AgentsRepository(FirestoreRepository):
    def __init__(self):
        super().__init__("agents")
