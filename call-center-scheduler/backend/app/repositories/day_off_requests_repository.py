"""Day-off requests repository."""

from app.repositories.firestore_repository import FirestoreRepository


class DayOffRequestsRepository(FirestoreRepository):
    def __init__(self):
        super().__init__("day_off_requests")
