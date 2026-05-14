"""Offices repository."""

from app.repositories.firestore_repository import FirestoreRepository


class OfficesRepository(FirestoreRepository):
    def __init__(self):
        super().__init__("offices")
