from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv


def _split_ints(raw: str | None) -> list[int]:
    if not raw or not raw.strip():
        return []
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def _split_keywords(raw: str | None) -> list[str]:
    if not raw or not raw.strip():
        return []
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_chat_ids: list[int]
    filter_by_keywords: bool
    keywords: list[str]
    ignore_bots: bool
    min_message_length: int
    reply_in_telegram: bool
    bitrix_webhook_url: str
    bitrix_entity: Literal["lead", "deal"]
    bitrix_deal_category_id: int | None
    bitrix_deal_stage_id: str | None
    bitrix_source_id: str | None
    bitrix_assigned_by_id: int | None
    mode: Literal["polling", "webhook"]
    webhook_url: str | None
    webhook_host: str
    webhook_port: int
    webhook_path: str
    log_level: str


@lru_cache
def get_settings() -> Settings:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    bitrix = os.getenv("BITRIX_WEBHOOK_URL", "").strip()
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is required")
    if not bitrix:
        raise SystemExit("BITRIX_WEBHOOK_URL is required")

    entity = os.getenv("BITRIX_ENTITY", "lead").strip().lower()
    if entity not in {"lead", "deal"}:
        raise SystemExit("BITRIX_ENTITY must be lead or deal")

    mode = os.getenv("MODE", "polling").strip().lower()
    if mode not in {"polling", "webhook"}:
        raise SystemExit("MODE must be polling or webhook")

    deal_cat = os.getenv("BITRIX_DEAL_CATEGORY_ID", "").strip()
    assigned = os.getenv("BITRIX_ASSIGNED_BY_ID", "").strip()

    return Settings(
        telegram_bot_token=token,
        telegram_chat_ids=_split_ints(os.getenv("TELEGRAM_CHAT_IDS")),
        filter_by_keywords=os.getenv("FILTER_BY_KEYWORDS", "false").strip().lower()
        in {"1", "true", "yes", "on"},
        keywords=_split_keywords(os.getenv("KEYWORDS")),
        ignore_bots=os.getenv("IGNORE_BOTS", "true").strip().lower()
        in {"1", "true", "yes", "on"},
        min_message_length=int(os.getenv("MIN_MESSAGE_LENGTH", "5") or "5"),
        reply_in_telegram=os.getenv("REPLY_IN_TELEGRAM", "false").strip().lower()
        in {"1", "true", "yes", "on"},
        bitrix_webhook_url=bitrix.rstrip("/") + "/",
        bitrix_entity=entity,  # type: ignore[arg-type]
        bitrix_deal_category_id=int(deal_cat) if deal_cat else None,
        bitrix_deal_stage_id=os.getenv("BITRIX_DEAL_STAGE_ID") or None,
        bitrix_source_id=os.getenv("BITRIX_SOURCE_ID") or None,
        bitrix_assigned_by_id=int(assigned) if assigned else None,
        mode=mode,  # type: ignore[arg-type]
        webhook_url=os.getenv("WEBHOOK_URL") or None,
        webhook_host=os.getenv("WEBHOOK_HOST", "0.0.0.0"),
        webhook_port=int(os.getenv("WEBHOOK_PORT", "8080") or "8080"),
        webhook_path=os.getenv("WEBHOOK_PATH", "/telegram"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
