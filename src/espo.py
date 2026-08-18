from __future__ import annotations

import logging
from typing import Any

import httpx

from src.config import Settings
from src.parser import ParsedLead

logger = logging.getLogger(__name__)


class EspoError(RuntimeError):
    pass


class EspoClient:
    """EspoCRM REST client (API Key auth)."""

    def __init__(self, settings: Settings) -> None:
        if not settings.espo_url or not settings.espo_api_key:
            raise ValueError("ESPO_URL and ESPO_API_KEY are required")
        self.settings = settings
        self.base = settings.espo_url.rstrip("/")
        if not self.base.endswith("/api/v1"):
            self.base = f"{self.base}/api/v1"
        self.api_key = settings.espo_api_key
        self.entity = settings.espo_entity

    def _headers(self) -> dict[str, str]:
        return {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, url, headers=self._headers(), json=payload)
            if response.status_code >= 400:
                raise EspoError(f"HTTP {response.status_code}: {response.text[:500]}")
            if not response.content:
                return {}
            data = response.json()
            if isinstance(data, dict) and data.get("errorCode"):
                raise EspoError(str(data))
            return data if isinstance(data, dict) else {"result": data}

    def _description(self, lead: ParsedLead) -> str:
        lines: list[str] = []
        if lead.quiz_name:
            lines.append(f"Квиз: {lead.quiz_name}")
        for question, answer in lead.answers:
            lines.append(f"{question}: {answer}")
        if lead.city:
            lines.append(f"Местоположение: {lead.city}")
        for key, value in lead.messengers.items():
            lines.append(f"{key}: {value}")
        if lead.page_url:
            lines.append(f"Страница: {lead.page_url}")
        return "\n".join(lines)

    def _payload_from_lead(self, lead: ParsedLead) -> dict[str, Any]:
        first_name = None
        last_name = None
        if lead.name:
            parts = lead.name.split(None, 1)
            first_name = parts[0]
            if len(parts) > 1:
                last_name = parts[1]
        else:
            first_name = "Клиент"

        payload: dict[str, Any] = {
            "firstName": first_name,
            "status": self.settings.espo_lead_status or "New",
            "source": self.settings.espo_source or "Web Site",
            "description": self._description(lead) or lead.title,
        }
        if last_name:
            payload["lastName"] = last_name
        else:
            # Espo often requires lastName
            payload["lastName"] = lead.quiz_name or "Quiz"
        if lead.phone:
            payload["phoneNumber"] = lead.phone
        if lead.email:
            payload["emailAddress"] = lead.email
        if lead.city:
            payload["addressCity"] = lead.city
        # Optional assigned user
        if self.settings.espo_assigned_user_id:
            payload["assignedUserId"] = self.settings.espo_assigned_user_id

        # Optional custom field map: ESPO_FIELD_MAP=quiz_name:cQuizName,тип led:cLedType
        for needle, field_name in self.settings.espo_field_map.items():
            value = None
            if needle == "quiz_name":
                value = lead.quiz_name
            elif needle == "city":
                value = lead.city
            elif needle in lead.messengers:
                value = lead.messengers[needle]
            else:
                for question, answer in lead.answers:
                    if needle in question.lower():
                        value = answer
                        break
            if value:
                payload[field_name] = value
        return payload

    async def create_from_parsed(self, lead: ParsedLead) -> str:
        payload = self._payload_from_lead(lead)
        logger.info("Creating EspoCRM %s: %s", self.entity, lead.title)
        result = await self._request("POST", self.entity, payload)
        record_id = str(result.get("id") or "")
        if not record_id:
            raise EspoError(f"EspoCRM create returned no id: {result}")
        logger.info("EspoCRM %s created: id=%s", self.entity, record_id)
        return record_id
