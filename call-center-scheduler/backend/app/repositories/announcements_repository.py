"""Announcements repository."""

from app.repositories.firestore_repository import FirestoreRepository


class AnnouncementsRepository(FirestoreRepository):
    def __init__(self):
        super().__init__("announcements")

