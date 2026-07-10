"""Reusable Firestore repository with consistent serialization."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from google.api_core import exceptions as google_api_exceptions
from google.cloud.firestore_v1 import Query
from google.cloud.firestore_v1.field_path import FieldPath

from app.core.exceptions import DependencyUnavailableError
from app.core.firebase import get_firestore_client
from app.models.common import utcnow

logger = logging.getLogger(__name__)


class FirestoreRepository:
    """Base repository that encapsulates boilerplate CRUD behavior."""

    def __init__(self, collection_name: str):
        self.collection_name = collection_name
        self.db = get_firestore_client()
        self.collection = self.db.collection(collection_name)

    @staticmethod
    def _serialize(value: Any) -> Any:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc).isoformat()
        if isinstance(value, dict):
            return {key: FirestoreRepository._serialize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [FirestoreRepository._serialize(item) for item in value]
        return value

    def _doc_to_dict(self, document) -> dict[str, Any]:
        payload = document.to_dict() or {}
        payload["id"] = document.id
        return self._serialize(payload)

    @staticmethod
    def _aggregation_count_value(result: Any) -> int:
        candidates: list[Any] = [result]
        while candidates:
            candidate = candidates.pop(0)
            if isinstance(candidate, dict):
                candidates.extend(candidate.values())
                continue
            if isinstance(candidate, (list, tuple)):
                candidates.extend(candidate)
                continue
            if hasattr(candidate, "value"):
                return int(candidate.value)
            if isinstance(candidate, (int, float)):
                return int(candidate)

        raise ValueError("Firestore count aggregation returned an unsupported result shape")

    @staticmethod
    def _apply_filters(query: Any, filters: list[tuple[str, str, Any]] | None = None) -> Any:
        for field_name, op, value in filters or []:
            query = query.where(field_name, op, value)
        return query

    @staticmethod
    def _wrap_firestore_error(exc: Exception) -> DependencyUnavailableError:
        message = str(exc)
        lowered = message.lower()

        if "maximum allowed size" in lowered or "longer than 1048487" in lowered:
            detail = (
                "A document write exceeds Firestore's 1 MiB size limit. "
                "Reduce the generation scope or report this as a size regression."
            )
        elif "quota exceeded" in lowered or isinstance(exc, google_api_exceptions.ResourceExhausted):
            detail = (
                "Cloud Firestore quota is exceeded for the configured project. "
                "Wait for quota reset, reduce Firestore usage, or increase the project quota."
            )
        elif "service_disabled" in lowered or "firestore.googleapis.com" in lowered and "disabled" in lowered:
            detail = (
                "Cloud Firestore API is disabled for the configured project. "
                "Enable firestore.googleapis.com in Google Cloud and retry."
            )
        elif "permission_denied" in lowered or "permission denied" in lowered:
            detail = (
                "Cloud Firestore access is denied. Verify service-account roles and project alignment."
            )
        else:
            detail = "Cloud Firestore is unavailable. Retry later or verify project configuration."

        return DependencyUnavailableError(dependency="firestore", detail=detail, status_code=503)

    def create(self, data: dict[str, Any], document_id: str | None = None) -> dict[str, Any]:
        now = utcnow()
        payload = {**data}
        payload.setdefault("created_at", now)
        payload["updated_at"] = now

        try:
            doc_ref = self.collection.document(document_id) if document_id else self.collection.document()
            doc_ref.set(payload)
            return self.get(doc_ref.id)
        except (google_api_exceptions.GoogleAPICallError, google_api_exceptions.RetryError) as exc:
            raise self._wrap_firestore_error(exc) from exc

    def get(self, document_id: str) -> dict[str, Any] | None:
        try:
            snapshot = self.collection.document(document_id).get()
            if not snapshot.exists:
                return None
            return self._doc_to_dict(snapshot)
        except (google_api_exceptions.GoogleAPICallError, google_api_exceptions.RetryError) as exc:
            raise self._wrap_firestore_error(exc) from exc

    def update(self, document_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        try:
            doc_ref = self.collection.document(document_id)
            snapshot = doc_ref.get()
            if not snapshot.exists:
                return None

            payload = {**data}
            payload["updated_at"] = utcnow()
            doc_ref.update(payload)
            return self.get(document_id)
        except (google_api_exceptions.GoogleAPICallError, google_api_exceptions.RetryError) as exc:
            raise self._wrap_firestore_error(exc) from exc

    def delete(self, document_id: str) -> bool:
        try:
            snapshot = self.collection.document(document_id).get()
            if not snapshot.exists:
                return False
            snapshot.reference.delete()
            return True
        except (google_api_exceptions.GoogleAPICallError, google_api_exceptions.RetryError) as exc:
            raise self._wrap_firestore_error(exc) from exc

    def list(
        self,
        filters: list[tuple[str, str, Any]] | None = None,
        order_by: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        try:
            query = self._apply_filters(self.collection, filters)

            if order_by:
                direction = Query.ASCENDING
                field_name = order_by
                if order_by.startswith("-"):
                    field_name = order_by[1:]
                    direction = Query.DESCENDING
                query = query.order_by(field_name, direction=direction)
            if limit is not None:
                query = query.limit(limit)

            return [self._doc_to_dict(doc) for doc in query.stream()]
        except (google_api_exceptions.GoogleAPICallError, google_api_exceptions.RetryError) as exc:
            raise self._wrap_firestore_error(exc) from exc

    def count(self, filters: list[tuple[str, str, Any]] | None = None) -> int:
        try:
            query = self._apply_filters(self.collection, filters)
            fallback_reason: str | None = None
            if hasattr(query, "count"):
                try:
                    aggregation_query = query.count(alias="total")
                except (AttributeError, TypeError):
                    fallback_reason = "query.count() is unavailable"
                else:
                    result = aggregation_query.get()
                    try:
                        return self._aggregation_count_value(result)
                    except (TypeError, ValueError):
                        fallback_reason = "aggregation result shape is unsupported"
            else:
                fallback_reason = "query has no count() support"

            if fallback_reason:
                logger.debug(
                    "Falling back to streaming count for collection '%s': %s",
                    getattr(self, "collection_name", "<unknown>"),
                    fallback_reason,
                )

            return sum(1 for _ in query.stream())
        except (google_api_exceptions.GoogleAPICallError, google_api_exceptions.RetryError) as exc:
            raise self._wrap_firestore_error(exc) from exc

    def list_by_document_id_prefix(self, prefix: str, limit: int | None = None) -> list[dict[str, Any]]:
        try:
            document_id_field = FieldPath.document_id()
            start_key = self.collection.document(prefix)
            end_key = self.collection.document(f"{prefix}\uf8ff")
            query = self.collection.where(document_id_field, ">=", start_key).where(
                document_id_field,
                "<",
                end_key,
            )
            if limit is not None:
                query = query.limit(limit)
            return [self._doc_to_dict(doc) for doc in query.stream()]
        except (google_api_exceptions.GoogleAPICallError, google_api_exceptions.RetryError) as exc:
            raise self._wrap_firestore_error(exc) from exc
