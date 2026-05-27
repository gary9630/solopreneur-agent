from __future__ import annotations

from typing import Any, Protocol

from pydantic import ValidationError

from deal_agent.nim_client import NimClientError
from deal_agent.tool_models import BusinessCardContact


class VisionBusinessCardClient(Protocol):
    def extract_business_card(self, image_base64: str, mime_type: str) -> Any:
        ...


class BusinessCardExtractionError(Exception):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class BusinessCardExtractor:
    def __init__(self, client: VisionBusinessCardClient, *, minimum_confidence: float = 0.4) -> None:
        self._client = client
        self._minimum_confidence = minimum_confidence

    def extract(self, image_base64: str, mime_type: str) -> BusinessCardContact:
        try:
            payload = self._client.extract_business_card(image_base64, mime_type)
            contact = BusinessCardContact.model_validate(payload)
        except NimClientError as exc:
            raise BusinessCardExtractionError(str(exc), retryable=exc.retryable) from exc
        except ValidationError as exc:
            raise BusinessCardExtractionError("Business card output failed validation", retryable=False) from exc

        if contact.confidence is not None and contact.confidence < self._minimum_confidence:
            raise BusinessCardExtractionError("Business card confidence was too low", retryable=False)
        if not any([contact.name, contact.email, contact.phone, contact.company]):
            raise BusinessCardExtractionError("Business card did not include usable contact details", retryable=False)
        return contact
