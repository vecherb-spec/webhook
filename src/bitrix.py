from __future__ import annotations

import logging
from typing import Any

import httpx

from src.config import Settings
from src.parser import ParsedLead

logger = logging.getLogger(__name__)


class BitrixError(RuntimeError):
    pass


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

    def _fields_from_lead(self, lead: ParsedLead, meta: dict[str, Any]) -> dict[str, Any]:
        comments = lead.comments
        meta_lines = []
        if meta.get("chat_title"):
            meta_lines.append(f"Чат: {meta['chat_title']}")
        if meta.get("chat_id"):
            meta_lines.append(f"Chat ID: {meta['chat_id']}")
        if meta.get("username"):
            meta_lines.append(f"Telegram: @{meta['username']}")
        if meta.get("user_id"):
            meta_lines.append(f"User ID: {meta['user_id']}")
        if meta.get("message_link"):
            meta_lines.append(f"Сообщение: {meta['message_link']}")
        if meta_lines:
            comments = comments + "\n\n---\n" + "\n".join(meta_lines)

        fields: dict[str, Any] = {
            "TITLE": lead.title,
            "COMMENTS": comments,
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

        source_bits = ["Telegram"]
        if lead.quiz_name:
            source_bits.append(f"квиз {lead.quiz_name}")
        if lead.page_url:
            source_bits.append(lead.page_url)
        if self.settings.bitrix_source_id:
            fields["SOURCE_ID"] = self.settings.bitrix_source_id
        else:
            fields["SOURCE_ID"] = "WEBFORM"
        fields["SOURCE_DESCRIPTION"] = " | ".join(source_bits)[:255]

        if self.settings.bitrix_assigned_by_id:
            fields["ASSIGNED_BY_ID"] = self.settings.bitrix_assigned_by_id
        return fields

    async def create_from_parsed(
        self, lead: ParsedLead, meta: dict[str, Any] | None = None
    ) -> int:
        meta = meta or {}
        fields = self._fields_from_lead(lead, meta)

        if self.settings.bitrix_entity == "deal":
            return await self.create_deal(fields)
        return await self.create_lead(fields)

    async def create_lead(self, fields: dict[str, Any]) -> int:
        logger.info("Creating Bitrix lead: %s", fields.get("TITLE"))
        result = await self._call("crm.lead.add", {"fields": fields})
        lead_id = int(result["result"])
        logger.info("Bitrix lead created: id=%s", lead_id)
        return lead_id

    async def create_deal(self, fields: dict[str, Any]) -> int:
        deal_fields: dict[str, Any] = {
            "TITLE": fields.get("TITLE"),
            "COMMENTS": fields.get("COMMENTS"),
            "OPENED": "Y",
        }
        if self.settings.bitrix_deal_category_id is not None:
            deal_fields["CATEGORY_ID"] = self.settings.bitrix_deal_category_id
        if self.settings.bitrix_deal_stage_id:
            deal_fields["STAGE_ID"] = self.settings.bitrix_deal_stage_id
        if self.settings.bitrix_assigned_by_id:
            deal_fields["ASSIGNED_BY_ID"] = self.settings.bitrix_assigned_by_id
        if fields.get("SOURCE_ID"):
            deal_fields["SOURCE_ID"] = fields["SOURCE_ID"]
        if fields.get("SOURCE_DESCRIPTION"):
            deal_fields["SOURCE_DESCRIPTION"] = fields["SOURCE_DESCRIPTION"]

        # For deals, create a contact first if we have contact data
        contact_id = None
        if fields.get("NAME") or fields.get("PHONE") or fields.get("EMAIL"):
            contact_fields: dict[str, Any] = {
                "NAME": fields.get("NAME") or "Telegram",
                "OPENED": "Y",
            }
            if fields.get("LAST_NAME"):
                contact_fields["LAST_NAME"] = fields["LAST_NAME"]
            if fields.get("PHONE"):
                contact_fields["PHONE"] = fields["PHONE"]
            if fields.get("EMAIL"):
                contact_fields["EMAIL"] = fields["EMAIL"]
            contact = await self._call("crm.contact.add", {"fields": contact_fields})
            contact_id = int(contact["result"])
            deal_fields["CONTACT_ID"] = contact_id

        logger.info("Creating Bitrix deal: %s", deal_fields.get("TITLE"))
        result = await self._call("crm.deal.add", {"fields": deal_fields})
        deal_id = int(result["result"])
        logger.info("Bitrix deal created: id=%s contact_id=%s", deal_id, contact_id)
        return deal_id
