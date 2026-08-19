from __future__ import annotations

import logging
from typing import Any

import httpx

from src.config import Settings
from src.parser import ParsedLead

logger = logging.getLogger(__name__)


class PlanfixError(RuntimeError):
    pass


class PlanfixClient:
    """Planfix REST API client (Bearer token)."""

    def __init__(self, settings: Settings) -> None:
        if not settings.planfix_url or not settings.planfix_token:
            raise ValueError("PLANFIX_URL and PLANFIX_TOKEN are required")
        self.settings = settings
        self.base = settings.planfix_url.rstrip("/")
        if not self.base.endswith("/rest"):
            # accept https://account.planfix.ru or .../rest/
            self.base = f"{self.base}/rest"
        self.token = settings.planfix_token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"{self.base}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method, url, headers=self._headers(), json=payload
            )
            if response.status_code >= 400:
                raise PlanfixError(
                    f"HTTP {response.status_code}: {response.text[:500]}"
                )
            if not response.content:
                return {}
            data = response.json()
            if isinstance(data, dict) and data.get("result") == "fail":
                raise PlanfixError(
                    f"{data.get('code')}: {data.get('error') or data}"
                )
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
        if lead.phone:
            lines.append(f"Телефон: {lead.phone}")
        if lead.email:
            lines.append(f"Email: {lead.email}")
        return "\n".join(lines) or lead.title

    def _contact_payload(self, lead: ParsedLead) -> dict[str, Any]:
        first = "Клиент"
        last = lead.quiz_name or "Quiz"
        if lead.name:
            parts = lead.name.split(None, 1)
            first = parts[0]
            last = parts[1] if len(parts) > 1 else last

        payload: dict[str, Any] = {
            "name": first,
            "lastname": last,
            "description": self._description(lead),
            "isCompany": False,
        }
        # Planfix requires a contact template; default to 1 (standard contact)
        tpl_id = self.settings.planfix_contact_template_id or 1
        payload["template"] = {"id": tpl_id}
        if lead.email:
            payload["email"] = lead.email
        if lead.phone:
            payload["phones"] = [{"number": lead.phone, "type": 1}]
        if lead.messengers.get("telegram"):
            payload["telegram"] = lead.messengers["telegram"]
        return payload

    def _task_payload(
        self, lead: ParsedLead, contact_id: int | None
    ) -> dict[str, Any]:
        title = lead.title
        if lead.quiz_name:
            title = f"Заявка квиз «{lead.quiz_name}»"
            if lead.name:
                title = f"{title}: {lead.name}"
            elif lead.phone:
                title = f"{title}: {lead.phone}"

        payload: dict[str, Any] = {
            "name": title[:250],
            "description": self._description(lead),
            "priority": "NotUrgent",
        }
        if self.settings.planfix_task_template_id:
            payload["template"] = {"id": self.settings.planfix_task_template_id}
        if contact_id is not None:
            # PersonRequest id is string; counterparty expects contact number
            payload["counterparty"] = {"id": str(contact_id)}
        if self.settings.planfix_assignee_user_id:
            payload["assignees"] = {
                "users": [{"id": f"user:{self.settings.planfix_assignee_user_id}"}]
            }
        return payload

    async def create_contact(self, lead: ParsedLead) -> int:
        result = await self._request("POST", "contact/", self._contact_payload(lead))
        contact_id = result.get("id")
        if contact_id is None and isinstance(result.get("contact"), dict):
            contact_id = result["contact"].get("id")
        if contact_id is None:
            raise PlanfixError(f"Planfix contact create returned no id: {result}")
        return int(contact_id)

    async def create_task(self, lead: ParsedLead, contact_id: int | None) -> int:
        result = await self._request(
            "POST", "task/", self._task_payload(lead, contact_id)
        )
        task_id = result.get("id")
        if task_id is None and isinstance(result.get("task"), dict):
            task_id = result["task"].get("id")
        if task_id is None:
            raise PlanfixError(f"Planfix task create returned no id: {result}")
        return int(task_id)

    async def create_from_parsed(self, lead: ParsedLead) -> int:
        """Create contact (best-effort) + task; return task id."""
        contact_id: int | None = None
        try:
            contact_id = await self.create_contact(lead)
            logger.info("Planfix contact created: id=%s", contact_id)
        except PlanfixError:
            logger.exception("Planfix contact create failed; creating task without contact")

        task_id = await self.create_task(lead, contact_id)
        logger.info("Planfix task created: id=%s contact=%s", task_id, contact_id)
        return task_id
