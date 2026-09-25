from __future__ import annotations

import os
from dataclasses import dataclass, field
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


def _parse_field_map(raw: str | None) -> dict[str, str]:
    """Parse ESPO_FIELD_MAP like: quiz_name:cQuiz,тип led:cLedType,ширина:cWidth"""
    out: dict[str, str] = {}
    if not raw or not raw.strip():
        return out
    for part in raw.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        key, value = part.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key and value:
            out[key] = value
    return out


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_chat_ids: list[int]
    filter_by_keywords: bool
    keywords: list[str]
    ignore_bots: bool
    min_message_length: int
    reply_in_telegram: bool
    only_quiz_applications: bool
    marquiz_http_enabled: bool
    marquiz_http_host: str
    marquiz_http_port: int
    bitrix_webhook_url: str | None
    bitrix_enabled: bool
    bitrix_entity: Literal["lead", "deal"]
    bitrix_deal_category_id: int | None
    bitrix_deal_stage_id: str | None
    bitrix_source_id: str | None
    bitrix_assigned_by_id: int | None
    espo_enabled: bool
    espo_url: str | None
    espo_api_key: str | None
    espo_entity: str
    espo_lead_status: str | None
    espo_source: str | None
    espo_assigned_user_id: str | None
    planfix_enabled: bool
    planfix_url: str | None
    planfix_token: str | None
    planfix_contact_template_id: int | None
    planfix_task_template_id: int | None
    planfix_object_id: int | None
    planfix_assignee_user_id: int | None
    espo_field_map: dict[str, str] = field(default_factory=dict)
    mode: Literal["polling", "webhook"] = "polling"
    webhook_url: str | None = None
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8080
    webhook_path: str = "/telegram"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    bitrix = os.getenv("BITRIX_WEBHOOK_URL", "").strip() or None
    espo_url = os.getenv("ESPO_URL", "").strip() or None
    espo_key = os.getenv("ESPO_API_KEY", "").strip() or None
    planfix_url = os.getenv("PLANFIX_URL", "").strip() or None
    planfix_token = os.getenv("PLANFIX_TOKEN", "").strip() or None

    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is required")

    bitrix_enabled = bool(bitrix) and os.getenv("BITRIX_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    espo_enabled = bool(espo_url and espo_key) and os.getenv(
        "ESPO_ENABLED", "true"
    ).strip().lower() in {"1", "true", "yes", "on"}
    planfix_enabled = bool(planfix_url and planfix_token) and os.getenv(
        "PLANFIX_ENABLED", "true"
    ).strip().lower() in {"1", "true", "yes", "on"}

    if not bitrix_enabled and not espo_enabled and not planfix_enabled:
        raise SystemExit(
            "Configure at least one CRM: BITRIX_WEBHOOK_URL, "
            "ESPO_URL+ESPO_API_KEY, and/or PLANFIX_URL+PLANFIX_TOKEN"
        )

    entity = os.getenv("BITRIX_ENTITY", "lead").strip().lower()
    if entity not in {"lead", "deal"}:
        raise SystemExit("BITRIX_ENTITY must be lead or deal")

    mode = os.getenv("MODE", "polling").strip().lower()
    if mode not in {"polling", "webhook"}:
        raise SystemExit("MODE must be polling or webhook")

    deal_cat = os.getenv("BITRIX_DEAL_CATEGORY_ID", "").strip()
    assigned = os.getenv("BITRIX_ASSIGNED_BY_ID", "").strip()
    pf_contact_tpl = os.getenv("PLANFIX_CONTACT_TEMPLATE_ID", "").strip()
    pf_task_tpl = os.getenv("PLANFIX_TASK_TEMPLATE_ID", "").strip()
    pf_object = os.getenv("PLANFIX_OBJECT_ID", "").strip()
    pf_assignee = os.getenv("PLANFIX_ASSIGNEE_USER_ID", "").strip()

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
        only_quiz_applications=os.getenv("ONLY_QUIZ_APPLICATIONS", "true").strip().lower()
        in {"1", "true", "yes", "on"},
        marquiz_http_enabled=os.getenv("MARQUIZ_HTTP_ENABLED", "true").strip().lower()
        in {"1", "true", "yes", "on"},
        marquiz_http_host=os.getenv("MARQUIZ_HTTP_HOST", "127.0.0.1"),
        marquiz_http_port=int(os.getenv("MARQUIZ_HTTP_PORT", "8791") or "8791"),
        bitrix_webhook_url=(bitrix.rstrip("/") + "/") if bitrix else None,
        bitrix_enabled=bitrix_enabled,
        bitrix_entity=entity,  # type: ignore[arg-type]
        bitrix_deal_category_id=int(deal_cat) if deal_cat else None,
        bitrix_deal_stage_id=os.getenv("BITRIX_DEAL_STAGE_ID") or None,
        bitrix_source_id=os.getenv("BITRIX_SOURCE_ID") or None,
        bitrix_assigned_by_id=int(assigned) if assigned else None,
        espo_enabled=espo_enabled,
        espo_url=espo_url,
        espo_api_key=espo_key,
        espo_entity=os.getenv("ESPO_ENTITY", "Lead").strip() or "Lead",
        espo_lead_status=os.getenv("ESPO_LEAD_STATUS") or "New",
        espo_source=os.getenv("ESPO_SOURCE") or "Web Site",
        espo_assigned_user_id=os.getenv("ESPO_ASSIGNED_USER_ID") or None,
        espo_field_map=_parse_field_map(os.getenv("ESPO_FIELD_MAP")),
        planfix_enabled=planfix_enabled,
        planfix_url=planfix_url,
        planfix_token=planfix_token,
        planfix_contact_template_id=int(pf_contact_tpl) if pf_contact_tpl else None,
        planfix_task_template_id=int(pf_task_tpl) if pf_task_tpl else None,
        planfix_object_id=int(pf_object) if pf_object else None,
        planfix_assignee_user_id=int(pf_assignee) if pf_assignee else None,
        mode=mode,  # type: ignore[arg-type]
        webhook_url=os.getenv("WEBHOOK_URL") or None,
        webhook_host=os.getenv("WEBHOOK_HOST", "0.0.0.0"),
        webhook_port=int(os.getenv("WEBHOOK_PORT", "8080") or "8080"),
        webhook_path=os.getenv("WEBHOOK_PATH", "/telegram"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
