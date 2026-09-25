from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.parser import ParsedLead, PHONE_RE, _build_title, _clean_phone

logger = logging.getLogger(__name__)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_marquiz_payload(data: dict[str, Any]) -> ParsedLead:
    """Convert Marquiz webhook JSON into ParsedLead."""
    contacts = data.get("contacts") if isinstance(data.get("contacts"), dict) else {}
    quiz_meta = data.get("quiz") if isinstance(data.get("quiz"), dict) else {}
    extra = data.get("extra") if isinstance(data.get("extra"), dict) else {}

    quiz_name = _text(quiz_meta.get("name") or quiz_meta.get("title") or data.get("name")) or "LED"
    name = _text(contacts.get("name") or contacts.get("fio"))
    phone = _text(contacts.get("phone") or contacts.get("tel"))
    email = _text(contacts.get("email"))
    city = _text(
        contacts.get("city")
        or data.get("city")
        or extra.get("city")
        or contacts.get("address")
    )
    page_url = _text(extra.get("href") or extra.get("url") or data.get("href") or data.get("url"))

    messengers: dict[str, str] = {}
    for key in ("telegram", "whatsapp", "max", "vk", "viber"):
        value = _text(contacts.get(key))
        if value:
            messengers[key] = value

    # Some Marquiz setups put messengers in contacts as free-form keys
    for key, value in contacts.items():
        lk = str(key).lower()
        if lk in messengers or not _text(value):
            continue
        if lk in {"telegram", "tg", "whatsapp", "wa", "max", "vk", "viber"}:
            messengers["telegram" if lk == "tg" else ("whatsapp" if lk == "wa" else lk)] = _text(value)

    if phone:
        phone = _clean_phone(phone)
    elif not phone:
        found = PHONE_RE.search(" ".join(str(v) for v in contacts.values()))
        if found:
            phone = _clean_phone(found.group(0))

    answers: list[tuple[str, str]] = []
    raw_answers = data.get("answers")
    if isinstance(raw_answers, list):
        for item in raw_answers:
            if not isinstance(item, dict):
                continue
            q = _text(item.get("q") or item.get("question"))
            a = item.get("a") if "a" in item else item.get("answer")
            if isinstance(a, list):
                a = ", ".join(_text(x) for x in a if _text(x))
            else:
                a = _text(a)
            if q and a:
                answers.append((q, a))

    # Infer city from answers if missing
    if not city:
        for q, a in answers:
            if "местополож" in q.lower() or "город" in q.lower():
                city = a
                break

    title = _build_title(quiz_name, name or None, answers)
    return ParsedLead(
        title=title,
        name=name or None,
        phone=phone or None,
        email=email or None,
        city=city or None,
        page_url=page_url or None,
        quiz_name=quiz_name,
        answers=answers,
        messengers=messengers,
        comments="",
        extra={f"answer:{q}": a for q, a in answers},
        raw_text=json.dumps(data, ensure_ascii=False),
    )


def lead_from_telegram_text(text: str) -> ParsedLead:
    from src.parser import parse_application

    return parse_application(text)
