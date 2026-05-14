"""Demand forecasts repository."""

from app.repositories.firestore_repository import FirestoreRepository


class DemandForecastsRepository(FirestoreRepository):
    def __init__(self):
        super().__init__("demand_forecasts")
