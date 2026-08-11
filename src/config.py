from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_ids: list[int] = Field(default_factory=list, alias="TELEGRAM_CHAT_IDS")

    filter_by_keywords: bool = Field(default=False, alias="FILTER_BY_KEYWORDS")
    keywords: list[str] = Field(default_factory=list, alias="KEYWORDS")
    ignore_bots: bool = Field(default=True, alias="IGNORE_BOTS")
    min_message_length: int = Field(default=5, alias="MIN_MESSAGE_LENGTH")

    bitrix_webhook_url: str = Field(..., alias="BITRIX_WEBHOOK_URL")
    bitrix_entity: Literal["lead", "deal"] = Field(default="lead", alias="BITRIX_ENTITY")
    bitrix_deal_category_id: int | None = Field(default=None, alias="BITRIX_DEAL_CATEGORY_ID")
    bitrix_deal_stage_id: str | None = Field(default=None, alias="BITRIX_DEAL_STAGE_ID")
    bitrix_source_id: str | None = Field(default=None, alias="BITRIX_SOURCE_ID")
    bitrix_assigned_by_id: int | None = Field(default=None, alias="BITRIX_ASSIGNED_BY_ID")

    mode: Literal["polling", "webhook"] = Field(default="polling", alias="MODE")
    webhook_url: str | None = Field(default=None, alias="WEBHOOK_URL")
    webhook_host: str = Field(default="0.0.0.0", alias="WEBHOOK_HOST")
    webhook_port: int = Field(default=8080, alias="WEBHOOK_PORT")
    webhook_path: str = Field(default="/telegram", alias="WEBHOOK_PATH")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("telegram_chat_ids", mode="before")
    @classmethod
    def parse_chat_ids(cls, value: object) -> list[int]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [int(v) for v in value]
        if isinstance(value, int):
            return [value]
        text = str(value).strip()
        if not text:
            return []
        return [int(part.strip()) for part in text.split(",") if part.strip()]

    @field_validator("keywords", mode="before")
    @classmethod
    def parse_keywords(cls, value: object) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [str(v).strip().lower() for v in value if str(v).strip()]
        return [part.strip().lower() for part in str(value).split(",") if part.strip()]

    @field_validator("bitrix_webhook_url")
    @classmethod
    def normalize_webhook(cls, value: str) -> str:
        return value.rstrip("/") + "/"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
