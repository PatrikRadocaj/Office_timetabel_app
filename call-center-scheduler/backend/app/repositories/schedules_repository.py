"""Generated schedules repository."""

from app.repositories.firestore_repository import FirestoreRepository


class SchedulesRepository(FirestoreRepository):
    def __init__(self):
        super().__init__("generated_schedules")
