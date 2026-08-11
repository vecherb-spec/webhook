from __future__ import annotations

import logging
from typing import Any

from telegram import Message, Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from src.bitrix import BitrixClient, BitrixError
from src.config import Settings, get_settings
from src.parser import is_quiz_application, parse_application


logger = logging.getLogger(__name__)


def _message_text(message: Message) -> str | None:
    if message.text:
        return message.text
    if message.caption:
        return message.caption
    return None


def _should_process(settings: Settings, message: Message, text: str) -> bool:
    if len(text.strip()) < settings.min_message_length:
        logger.debug("Skip short message")
        return False

    chat_ids = settings.telegram_chat_ids
    if chat_ids and message.chat_id not in chat_ids:
        logger.info(
            "Skip message from chat_id=%s (allowed: %s). "
            "Add this chat_id to TELEGRAM_CHAT_IDS if needed.",
            message.chat_id,
            chat_ids,
        )
        return False

    # Quiz-only mode: ignore chat noise / comments / other correspondence
    if settings.only_quiz_applications:
        if not is_quiz_application(text):
            logger.info("Skip non-quiz message chat_id=%s", message.chat_id)
            return False
        return True

    if settings.ignore_bots and message.from_user and message.from_user.is_bot:
        logger.debug("Skip bot message")
        return False

    if settings.filter_by_keywords and settings.keywords:
        lowered = text.lower()
        if not any(keyword in lowered for keyword in settings.keywords):
            logger.debug("Skip: no keywords matched")
            return False

    return True


def _sender_name(message: Message) -> str | None:
    user = message.from_user
    if not user:
        return None
    parts = [user.first_name or "", user.last_name or ""]
    name = " ".join(p for p in parts if p).strip()
    return name or user.username


def _meta(message: Message) -> dict[str, Any]:
    user = message.from_user
    chat = message.chat
    meta: dict[str, Any] = {
        "chat_id": chat.id if chat else None,
        "chat_title": chat.title if chat else None,
    }
    if user:
        meta["user_id"] = user.id
        meta["username"] = user.username
        meta["sender_name"] = _sender_name(message)
    # Public groups/supergroups with username get a link
    if chat and chat.username and message.message_id:
        meta["message_link"] = f"https://t.me/{chat.username}/{message.message_id}"
    return meta


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    bitrix: BitrixClient = context.application.bot_data["bitrix"]

    message = update.effective_message
    if not message:
        return

    # Always log chat id to help with setup
    logger.info(
        "Incoming message chat_id=%s from=%s",
        message.chat_id,
        _sender_name(message),
    )

    text = _message_text(message)
    if not text:
        logger.debug("Skip non-text message")
        return

    if not _should_process(settings, message, text):
        return

    lead = parse_application(text, sender_name=_sender_name(message))
    try:
        entity_id = await bitrix.create_from_parsed(lead, meta=_meta(message))
    except BitrixError as exc:
        logger.error("Bitrix error: %s", exc)
        if settings.reply_in_telegram:
            try:
                await message.reply_text(f"❌ Не удалось создать в Битрикс24: {exc}")
            except Exception:  # noqa: BLE001
                pass
        return
    except Exception:
        logger.exception("Unexpected error while creating Bitrix entity")
        return

    entity = settings.bitrix_entity
    logger.info("Created Bitrix %s #%s", entity, entity_id)
    if not settings.reply_in_telegram:
        return
    try:
        await message.reply_text(f"✅ В Битрикс24 создан {entity} #{entity_id}")
    except Exception:  # noqa: BLE001
        logger.debug("Could not reply in chat (maybe no permission)")


def build_app(settings: Settings | None = None) -> Application:
    settings = settings or get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .build()
    )
    app.bot_data["settings"] = settings
    app.bot_data["bitrix"] = BitrixClient(settings)

    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.CAPTION) & ~filters.COMMAND,
            handle_message,
        )
    )
    return app


def run() -> None:
    settings = get_settings()
    app = build_app(settings)

    if settings.mode == "webhook":
        if not settings.webhook_url:
            raise SystemExit("WEBHOOK_URL is required when MODE=webhook")
        logger.info(
            "Starting webhook mode on %s:%s%s",
            settings.webhook_host,
            settings.webhook_port,
            settings.webhook_path,
        )
        app.run_webhook(
            listen=settings.webhook_host,
            port=settings.webhook_port,
            url_path=settings.webhook_path.lstrip("/"),
            webhook_url=settings.webhook_url,
            drop_pending_updates=True,
        )
    else:
        logger.info("Starting polling mode")
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    run()
