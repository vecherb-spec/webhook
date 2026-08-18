from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.bitrix import BitrixClient, BitrixError
from src.config import Settings
from src.espo import EspoClient, EspoError
from src.parser import ParsedLead

logger = logging.getLogger(__name__)


@dataclass
class CrmResult:
    bitrix_id: int | None = None
    espo_id: str | None = None
    errors: list[str] | None = None


class CrmRouter:
    """Write leads to Bitrix24 and/or EspoCRM."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bitrix = BitrixClient(settings) if settings.bitrix_enabled else None
        self.espo = EspoClient(settings) if settings.espo_enabled else None
        if not self.bitrix and not self.espo:
            raise SystemExit("Configure at least one CRM: BITRIX_WEBHOOK_URL or ESPO_URL+ESPO_API_KEY")

    async def create_from_parsed(
        self, lead: ParsedLead, meta: dict[str, Any] | None = None
    ) -> CrmResult:
        meta = meta or {}
        result = CrmResult(errors=[])

        if self.bitrix:
            try:
                result.bitrix_id = await self.bitrix.create_from_parsed(lead, meta=meta)
            except (BitrixError, Exception) as exc:  # noqa: BLE001
                logger.exception("Bitrix create failed")
                result.errors.append(f"bitrix: {exc}")

        if self.espo:
            try:
                result.espo_id = await self.espo.create_from_parsed(lead)
            except (EspoError, Exception) as exc:  # noqa: BLE001
                logger.exception("EspoCRM create failed")
                result.errors.append(f"espo: {exc}")

        if result.bitrix_id is None and result.espo_id is None:
            raise RuntimeError("; ".join(result.errors or ["CRM create failed"]))
        return result
