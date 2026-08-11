from __future__ import annotations

import logging
from typing import Any

import httpx

from src.config import Settings
from src.parser import ParsedLead

logger = logging.getLogger(__name__)


class BitrixError(RuntimeError):
    pass


# Default UF fields created for MediaLive LED quiz
DEFAULT_QUIZ_FIELD_MAP: dict[str, str] = {
    "quiz_name": "UF_CRM_QUIZ_NAME",
    "тип led": "UF_CRM_LED_TYPE",
    "тип экрана": "UF_CRM_LED_TYPE",
    "тип исполнения": "UF_CRM_LED_EXEC",
    "шаг пикселя": "UF_CRM_LED_PITCH",
    "ширина": "UF_CRM_LED_WIDTH",
    "высота": "UF_CRM_LED_HEIGHT",
    "монтаж": "UF_CRM_LED_MOUNT",
    "city": "UF_CRM_LED_CITY",
    "page_url": "UF_CRM_LED_PAGE",
    "max": "UF_CRM_LED_MAX",
}


class BitrixClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.bitrix_webhook_url

    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{method}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=params)
            response.raise_for_status()
            data = response.json()

        if "error" in data:
            raise BitrixError(
                f"{data.get('error')}: {data.get('error_description', data)}"
            )
        return data

    def _quiz_custom_fields(self, lead: ParsedLead) -> dict[str, str]:
        """Map quiz answers / contacts into Bitrix UF_* lead fields."""
        out: dict[str, str] = {}
        fmap = DEFAULT_QUIZ_FIELD_MAP

        if lead.quiz_name and fmap.get("quiz_name"):
            out[fmap["quiz_name"]] = lead.quiz_name
        if lead.city and fmap.get("city"):
            out[fmap["city"]] = lead.city
        if lead.messengers.get("max") and fmap.get("max"):
            out[fmap["max"]] = lead.messengers["max"]

        for question, answer in lead.answers:
            q = question.lower()
            matched_code = None
            for needle, code in fmap.items():
                if needle in {"quiz_name", "city", "page_url", "max"}:
                    continue
                if needle in q:
                    matched_code = code
                    break
            if matched_code:
                out[matched_code] = answer
        return out

    def _contact_fields(self, lead: ParsedLead) -> dict[str, Any] | None:
        if not (lead.name or lead.phone or lead.email):
            return None
        fields: dict[str, Any] = {"OPENED": "Y", "TYPE_ID": "CLIENT"}
        if lead.name:
            parts = lead.name.split(None, 1)
            fields["NAME"] = parts[0]
            if len(parts) > 1:
                fields["LAST_NAME"] = parts[1]
        else:
            fields["NAME"] = "Клиент Telegram"
        if lead.phone:
            fields["PHONE"] = [{"VALUE": lead.phone, "VALUE_TYPE": "WORK"}]
        if lead.email:
            fields["EMAIL"] = [{"VALUE": lead.email, "VALUE_TYPE": "WORK"}]
        if lead.messengers.get("max"):
            fields["IM"] = [{"VALUE": f"max: {lead.messengers['max']}", "VALUE_TYPE": "OTHER"}]
        if self.settings.bitrix_assigned_by_id:
            fields["ASSIGNED_BY_ID"] = self.settings.bitrix_assigned_by_id
        return fields

    async def find_contact_id_by_phone(self, phone: str) -> int | None:
        try:
            result = await self._call(
                "crm.duplicate.findByComm",
                {
                    "entity_type": "CONTACT",
                    "type": "PHONE",
                    "values": [phone],
                },
            )
        except BitrixError as exc:
            logger.warning("Duplicate search failed: %s", exc)
            return None
        contact_ids = (result.get("result") or {}).get("CONTACT") or []
        if contact_ids:
            return int(contact_ids[0])
        return None

    async def ensure_contact(self, lead: ParsedLead) -> int | None:
        contact_fields = self._contact_fields(lead)
        if not contact_fields:
            return None

        if lead.phone:
            existing = await self.find_contact_id_by_phone(lead.phone)
            if existing:
                logger.info("Reusing Bitrix contact id=%s by phone", existing)
                return existing

        result = await self._call("crm.contact.add", {"fields": contact_fields})
        contact_id = int(result["result"])
        logger.info("Bitrix contact created: id=%s", contact_id)
        return contact_id

    def _fields_from_lead(
        self, lead: ParsedLead, meta: dict[str, Any], contact_id: int | None = None
    ) -> dict[str, Any]:
        del meta
        fields: dict[str, Any] = {
            "TITLE": lead.title,
            "OPENED": "Y",
        }
        if lead.name:
            parts = lead.name.split(None, 1)
            fields["NAME"] = parts[0]
            if len(parts) > 1:
                fields["LAST_NAME"] = parts[1]
        if lead.phone:
            fields["PHONE"] = [{"VALUE": lead.phone, "VALUE_TYPE": "WORK"}]
        if lead.email:
            fields["EMAIL"] = [{"VALUE": lead.email, "VALUE_TYPE": "WORK"}]
        if lead.city:
            fields["ADDRESS"] = lead.city
        if lead.messengers.get("max"):
            fields["IM"] = [{"VALUE": f"max: {lead.messengers['max']}", "VALUE_TYPE": "OTHER"}]
        if contact_id:
            fields["CONTACT_ID"] = contact_id

        # Avoid Bitrix default SOURCE=CALL
        fields["SOURCE_ID"] = self.settings.bitrix_source_id or "WEBFORM"

        if self.settings.bitrix_assigned_by_id:
            fields["ASSIGNED_BY_ID"] = self.settings.bitrix_assigned_by_id

        fields.update(self._quiz_custom_fields(lead))
        return fields

    async def create_from_parsed(
        self, lead: ParsedLead, meta: dict[str, Any] | None = None
    ) -> int:
        meta = meta or {}
        contact_id = await self.ensure_contact(lead)
        fields = self._fields_from_lead(lead, meta, contact_id=contact_id)

        if self.settings.bitrix_entity == "deal":
            return await self.create_deal(fields, contact_id=contact_id)
        return await self.create_lead(fields)

    async def create_lead(self, fields: dict[str, Any]) -> int:
        logger.info(
            "Creating Bitrix lead: %s contact_id=%s",
            fields.get("TITLE"),
            fields.get("CONTACT_ID"),
        )
        result = await self._call("crm.lead.add", {"fields": fields})
        lead_id = int(result["result"])
        logger.info("Bitrix lead created: id=%s", lead_id)
        return lead_id

    async def create_deal(
        self, fields: dict[str, Any], contact_id: int | None = None
    ) -> int:
        deal_fields: dict[str, Any] = {
            "TITLE": fields.get("TITLE"),
            "OPENED": "Y",
        }
        if self.settings.bitrix_deal_category_id is not None:
            deal_fields["CATEGORY_ID"] = self.settings.bitrix_deal_category_id
        if self.settings.bitrix_deal_stage_id:
            deal_fields["STAGE_ID"] = self.settings.bitrix_deal_stage_id
        if self.settings.bitrix_assigned_by_id:
            deal_fields["ASSIGNED_BY_ID"] = self.settings.bitrix_assigned_by_id
        if contact_id:
            deal_fields["CONTACT_ID"] = contact_id

        logger.info("Creating Bitrix deal: %s contact_id=%s", deal_fields.get("TITLE"), contact_id)
        result = await self._call("crm.deal.add", {"fields": deal_fields})
        deal_id = int(result["result"])
        logger.info("Bitrix deal created: id=%s", deal_id)
        return deal_id
