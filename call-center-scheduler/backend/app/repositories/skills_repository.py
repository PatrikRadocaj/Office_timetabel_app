"""Skills repository."""

from app.repositories.firestore_repository import FirestoreRepository


class SkillsRepository(FirestoreRepository):
    def __init__(self):
        super().__init__("skills")
