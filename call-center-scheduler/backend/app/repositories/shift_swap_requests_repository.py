"""Shift-swap requests repository."""

from app.repositories.firestore_repository import FirestoreRepository


class ShiftSwapRequestsRepository(FirestoreRepository):
    def __init__(self):
        super().__init__("shift_swap_requests")
