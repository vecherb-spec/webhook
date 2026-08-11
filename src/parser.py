from __future__ import annotations

import re
from dataclasses import dataclass, field


PHONE_RE = re.compile(
    r"(?:\+?\d[\d\-\s()]{8,}\d)",
)
EMAIL_RE = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
)
# Имя: Иван / Name: Ivan / ФИО: ...
LABELED_RE = re.compile(
    r"(?im)^\s*(имя|фио|name|телефон|phone|тел|email|почта|e-mail|город|city|"
    r"комментарий|comment|сообщение|message|услуга|service|источник|source)\s*[:=]\s*(.+?)\s*$"
)


@dataclass
class ParsedLead:
    title: str
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    comments: str = ""
    extra: dict[str, str] = field(default_factory=dict)
    raw_text: str = ""


def _clean_phone(raw: str) -> str:
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("8") and len(re.sub(r"\D", "", digits)) == 11:
        digits = "+7" + re.sub(r"\D", "", digits)[1:]
    elif digits.startswith("7") and not digits.startswith("+") and len(re.sub(r"\D", "", digits)) == 11:
        digits = "+" + re.sub(r"\D", "", digits)
    return digits


def parse_application(text: str, sender_name: str | None = None) -> ParsedLead:
    """Parse free-form or labeled application text from Telegram."""
    text = (text or "").strip()
    labeled: dict[str, str] = {}
    for match in LABELED_RE.finditer(text):
        key = match.group(1).lower()
        labeled[key] = match.group(2).strip()

    name = (
        labeled.get("имя")
        or labeled.get("фио")
        or labeled.get("name")
        or sender_name
    )
    phone = labeled.get("телефон") or labeled.get("phone") or labeled.get("тел")
    email = labeled.get("email") or labeled.get("почта") or labeled.get("e-mail")

    if not phone:
        found = PHONE_RE.search(text)
        if found:
            phone = found.group(0)
    if not email:
        found = EMAIL_RE.search(text)
        if found:
            email = found.group(0)

    if phone:
        phone = _clean_phone(phone)

    comment_parts: list[str] = []
    for key in ("комментарий", "comment", "сообщение", "message", "услуга", "service", "город", "city", "источник", "source"):
        if key in labeled:
            comment_parts.append(f"{key}: {labeled[key]}")

    # Keep full original text in comments for managers
    comments = text
    if comment_parts and text != "\n".join(comment_parts):
        # still keep raw text — managers need full context
        comments = text

    title_name = name or "без имени"
    title = f"Заявка из Telegram: {title_name}"

    return ParsedLead(
        title=title,
        name=name,
        phone=phone,
        email=email,
        comments=comments,
        extra={k: v for k, v in labeled.items()},
        raw_text=text,
    )
