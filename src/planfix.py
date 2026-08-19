from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from src.config import Settings
from src.parser import ParsedLead

logger = logging.getLogger(__name__)


class PlanfixError(RuntimeError):
    pass


# MediaLive object «Сделка» (id=24) custom fields — same idea as Bitrix UF_* map
FIELD_CURRENCY = 111910
FIELD_DELIVERY_DATE = 111912
FIELD_INSTALL_PLACE = 111914
FIELD_DEAL_AMOUNT = 111920
FIELD_SCREEN_TYPE = 111922
FIELD_SCREEN_SIZE = 111924
FIELD_PAYMENT_STATUS = 111926
FIELD_SUCCESS = 111928
FIELD_MANAGER = 111930
FIELD_LEAD_SOURCE = 111932

# Quiz fields created via REST (customfield_add) in set «Сделка» (6380)
FIELD_QUIZ = 112002
FIELD_EXEC_TYPE = 112004
FIELD_PIXEL_PITCH = 112006
FIELD_WIDTH = 112008
FIELD_HEIGHT = 112010
FIELD_MOUNT = 112012
FIELD_PAGE_URL = 112014
FIELD_MAX = 112016
FIELD_TELEGRAM = 112018

# All deal custom field ids (for GET fields=... verification)
DEAL_FIELD_IDS = (
    FIELD_CURRENCY,
    FIELD_DELIVERY_DATE,
    FIELD_INSTALL_PLACE,
    FIELD_DEAL_AMOUNT,
    FIELD_SCREEN_TYPE,
    FIELD_SCREEN_SIZE,
    FIELD_PAYMENT_STATUS,
    FIELD_SUCCESS,
    FIELD_MANAGER,
    FIELD_LEAD_SOURCE,
    FIELD_QUIZ,
    FIELD_EXEC_TYPE,
    FIELD_PIXEL_PITCH,
    FIELD_WIDTH,
    FIELD_HEIGHT,
    FIELD_MOUNT,
    FIELD_PAGE_URL,
    FIELD_MAX,
    FIELD_TELEGRAM,
)

SCREEN_TYPE_ENUM = ("Уличный", "Внутренний", "Мобильный", "Прозрачный")


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

    def _answer(self, lead: ParsedLead, *needles: str) -> str | None:
        for question, answer in lead.answers:
            q = question.lower()
            if any(n in q for n in needles):
                return answer.strip()
        return None

    def _normalize_screen_type(self, raw: str | None) -> str | None:
        if not raw:
            return None
        text = raw.strip()
        lower = text.lower()
        for option in SCREEN_TYPE_ENUM:
            if option.lower() in lower or lower in option.lower():
                return option
        return None

    def _screen_size(self, lead: ParsedLead) -> str | None:
        width = self._answer(lead, "ширина")
        height = self._answer(lead, "высота")
        pitch = self._answer(lead, "шаг пикселя", "пикселя")
        exec_type = self._answer(lead, "тип исполнения", "исполнения")
        mount = self._answer(lead, "монтаж")
        parts: list[str] = []
        if width and height:
            w = re.sub(r"[^\d.,]", "", width) or width
            h = re.sub(r"[^\d.,]", "", height) or height
            parts.append(f"{w} x {h} мм")
        elif width:
            parts.append(f"ширина {width}")
        elif height:
            parts.append(f"высота {height}")
        if pitch:
            parts.append(pitch)
        if exec_type:
            parts.append(exec_type)
        if mount:
            parts.append(mount)
        return ", ".join(parts) if parts else None

    def _description(self, lead: ParsedLead) -> str:
        """Full quiz dump for the deal description (like Bitrix comments)."""
        lines: list[str] = []
        if lead.quiz_name:
            lines.append(f"Квиз: {lead.quiz_name}")
        if lead.name:
            lines.append(f"Имя: {lead.name}")
        if lead.phone:
            lines.append(f"Телефон: {lead.phone}")
        if lead.email:
            lines.append(f"Email: {lead.email}")
        for key, value in lead.messengers.items():
            lines.append(f"{key}: {value}")

        # Prefer stable labels for known LED quiz steps
        labeled = [
            ("Тип экрана", self._answer(lead, "тип led", "тип экрана")),
            ("Тип исполнения", self._answer(lead, "тип исполнения", "исполнения")),
            ("Шаг пикселя", self._answer(lead, "шаг пикселя", "пикселя")),
            ("Ширина", self._answer(lead, "ширина")),
            ("Высота", self._answer(lead, "высота")),
            ("Монтаж", self._answer(lead, "монтаж")),
        ]
        used_answers = {v for _, v in labeled if v}
        for label, value in labeled:
            if value:
                lines.append(f"{label}: {value}")
        for question, answer in lead.answers:
            if answer in used_answers:
                continue
            lines.append(f"{question}: {answer}")

        if lead.city:
            lines.append(f"Местоположение: {lead.city}")
        if lead.page_url:
            lines.append(f"Страница: {lead.page_url}")
        return "\n".join(lines) or lead.title

    def _custom_field_data(self, lead: ParsedLead) -> list[dict[str, Any]]:
        """Map quiz → object «Сделка» fields (MediaLive defaults)."""
        fields: list[dict[str, Any]] = [
            {"field": {"id": FIELD_CURRENCY}, "value": "RUB"},
            {"field": {"id": FIELD_PAYMENT_STATUS}, "value": "Не выставлен счет"},
            {"field": {"id": FIELD_LEAD_SOURCE}, "value": "Сайт"},
            {"field": {"id": FIELD_SUCCESS}, "value": False},
        ]

        screen_type = self._normalize_screen_type(
            self._answer(lead, "тип led", "тип экрана")
        )
        if screen_type:
            fields.append({"field": {"id": FIELD_SCREEN_TYPE}, "value": screen_type})

        size = self._screen_size(lead)
        if size:
            fields.append({"field": {"id": FIELD_SCREEN_SIZE}, "value": size})

        if lead.city:
            fields.append({"field": {"id": FIELD_INSTALL_PLACE}, "value": lead.city})

        manager_id = self.settings.planfix_assignee_user_id or 1
        fields.append(
            {
                "field": {"id": FIELD_MANAGER},
                "value": {"id": f"user:{manager_id}"},
            }
        )

        # Dedicated quiz fields (Bitrix-like)
        if lead.quiz_name:
            fields.append({"field": {"id": FIELD_QUIZ}, "value": lead.quiz_name})
        exec_type = self._answer(lead, "тип исполнения", "исполнения")
        if exec_type:
            fields.append({"field": {"id": FIELD_EXEC_TYPE}, "value": exec_type})
        pitch = self._answer(lead, "шаг пикселя", "пикселя")
        if pitch:
            fields.append({"field": {"id": FIELD_PIXEL_PITCH}, "value": pitch})
        width = self._answer(lead, "ширина")
        if width:
            fields.append({"field": {"id": FIELD_WIDTH}, "value": width})
        height = self._answer(lead, "высота")
        if height:
            fields.append({"field": {"id": FIELD_HEIGHT}, "value": height})
        mount = self._answer(lead, "монтаж")
        if mount:
            fields.append({"field": {"id": FIELD_MOUNT}, "value": mount})
        if lead.page_url:
            fields.append({"field": {"id": FIELD_PAGE_URL}, "value": lead.page_url})
        if lead.messengers.get("max"):
            fields.append({"field": {"id": FIELD_MAX}, "value": lead.messengers["max"]})
        if lead.messengers.get("telegram"):
            fields.append(
                {"field": {"id": FIELD_TELEGRAM}, "value": lead.messengers["telegram"]}
            )
        return fields

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

    def _deal_title(self, lead: ParsedLead) -> str:
        """Visible title with key quiz attrs (falls back if custom fields fail)."""
        parts: list[str] = []
        if lead.quiz_name:
            parts.append(lead.quiz_name)
        screen = self._normalize_screen_type(
            self._answer(lead, "тип led", "тип экрана")
        )
        if screen:
            parts.append(screen)
        width = self._answer(lead, "ширина")
        height = self._answer(lead, "высота")
        if width and height:
            w = re.sub(r"[^\d.,]", "", width) or width
            h = re.sub(r"[^\d.,]", "", height) or height
            parts.append(f"{w} x {h}")
        who = lead.name or lead.phone
        if who:
            parts.append(who)
        if parts:
            return " / ".join(parts)[:250]
        return (lead.title or "Заявка квиз")[:250]

    def _task_payload(
        self, lead: ParsedLead, contact_id: int | None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self._deal_title(lead),
            "description": self._description(lead),
            "priority": "NotUrgent",
        }
        # User object "Сделка" — without object id Planfix creates a plain task
        object_id = self.settings.planfix_object_id
        if object_id:
            payload["object"] = {"id": object_id}
            payload["customFieldData"] = self._custom_field_data(lead)
        tpl_id = self.settings.planfix_task_template_id
        if tpl_id:
            payload["template"] = {"id": tpl_id}
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
        payload = self._task_payload(lead, contact_id)
        # Planfix may ignore customFieldData on create for custom objects —
        # create first, then force-update fields.
        create_payload = {
            k: v for k, v in payload.items() if k != "customFieldData"
        }
        result = await self._request("POST", "task/", create_payload)
        task_id = result.get("id")
        if task_id is None and isinstance(result.get("task"), dict):
            task_id = result["task"].get("id")
        if task_id is None:
            raise PlanfixError(f"Planfix task create returned no id: {result}")
        task_id = int(task_id)

        custom = payload.get("customFieldData")
        if custom:
            try:
                await self._request(
                    "POST",
                    f"task/{task_id}",
                    {
                        "name": payload["name"],
                        "description": payload["description"],
                        "customFieldData": custom,
                    },
                )
            except PlanfixError as exc:
                # New quiz fields may not yet be placed on the object form.
                msg = str(exc)
                if "not permitted" in msg.lower() or "Custom fields not permitted" in msg:
                    core_ids = {
                        FIELD_CURRENCY,
                        FIELD_DELIVERY_DATE,
                        FIELD_INSTALL_PLACE,
                        FIELD_DEAL_AMOUNT,
                        FIELD_SCREEN_TYPE,
                        FIELD_SCREEN_SIZE,
                        FIELD_PAYMENT_STATUS,
                        FIELD_SUCCESS,
                        FIELD_MANAGER,
                        FIELD_LEAD_SOURCE,
                    }
                    core = [
                        item
                        for item in custom
                        if int(item["field"]["id"]) in core_ids
                    ]
                    logger.warning(
                        "Planfix quiz fields not on object form yet; "
                        "writing core deal fields only: %s",
                        msg,
                    )
                    await self._request(
                        "POST",
                        f"task/{task_id}",
                        {
                            "name": payload["name"],
                            "description": payload["description"],
                            "customFieldData": core,
                        },
                    )
                else:
                    logger.exception(
                        "Planfix custom fields update failed for task id=%s", task_id
                    )
        return task_id

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
