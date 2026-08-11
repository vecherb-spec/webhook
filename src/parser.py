from __future__ import annotations

import re
from dataclasses import dataclass, field


PHONE_RE = re.compile(r"(?:\+?\d[\d\-\s()]{8,}\d)")
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
QUIZ_TITLE_RE = re.compile(
    r"(?im)^\s*(?:🎯\s*)?заявка\s+на\s+квиз\s*[«\"']?(?P<quiz>.+?)[»\"']?\s*$"
)
LABELED_RE = re.compile(
    r"(?im)^\s*(имя|фио|name|телефон|phone|тел|email|почта|e-mail|город|city|"
    r"местоположение|локация|location|страница|page|url|сайт|max|whatsapp|telegram|"
    r"комментарий|comment|сообщение|message|услуга|service|источник|source)\s*[:=]\s*(.+?)\s*$"
)
# "Шаг N · вопрос" or "Вопрос (Шаг N · ...)" on one line, answer on next
STEP_HEADER_RE = re.compile(
    r"(?im)^\s*(?P<label>.+?)\s*$"
)
STEP_MARK_RE = re.compile(r"(?i)шаг\s*\d+")


@dataclass
class ParsedLead:
    title: str
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    page_url: str | None = None
    quiz_name: str | None = None
    answers: list[tuple[str, str]] = field(default_factory=list)
    messengers: dict[str, str] = field(default_factory=dict)
    comments: str = ""
    extra: dict[str, str] = field(default_factory=dict)
    raw_text: str = ""


def _clean_phone(raw: str) -> str:
    digits = re.sub(r"[^\d+]", "", raw)
    only = re.sub(r"\D", "", digits)
    if only.startswith("8") and len(only) == 11:
        return "+7" + only[1:]
    if only.startswith("7") and len(only) == 11:
        return "+" + only
    if digits.startswith("+"):
        return "+" + only
    return digits


def _normalize_label(label: str) -> str:
    label = label.strip()
    # Unwrap a single outer "(...)" around the whole label
    if label.startswith("(") and label.endswith(")") and label.count("(") == 1:
        label = label[1:-1].strip()
    label = re.sub(r"\s+", " ", label)
    return label.strip(" ·:-")


def _extract_quiz_answers(lines: list[str]) -> list[tuple[str, str]]:
    """Parse quiz Q/A blocks where question line contains 'Шаг' and answer is next non-empty line."""
    answers: list[tuple[str, str]] = []
    skip_prefixes = (
        "имя:",
        "телефон:",
        "email:",
        "почта:",
        "местоположение:",
        "страница:",
        "max:",
        "whatsapp:",
        "telegram:",
        "согласия",
        "я согласен",
    )
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        lower = line.lower()
        if not line or any(lower.startswith(p) for p in skip_prefixes):
            i += 1
            continue
        if STEP_MARK_RE.search(line):
            question = _normalize_label(line)
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                answer = lines[j].strip()
                ans_lower = answer.lower()
                if answer and not STEP_MARK_RE.search(answer) and not any(
                    ans_lower.startswith(p) for p in skip_prefixes
                ):
                    answers.append((question, answer))
                    i = j + 1
                    continue
        i += 1
    return answers


def _build_comments(lead_bits: dict[str, str | None], answers: list[tuple[str, str]], raw: str) -> str:
    # Comments are not sent to Bitrix — data goes into separate UF fields.
    del lead_bits, answers, raw
    return ""


def _build_title(quiz_name: str | None, name: str | None, answers: list[tuple[str, str]]) -> str:
    who = name or "без имени"
    if quiz_name:
        title = f"Квиз {quiz_name}: {who}"
    else:
        title = f"Заявка из Telegram: {who}"

    # Append short summary from key answers if present
    summary_bits: list[str] = []
    for question, answer in answers:
        q = question.lower()
        if "тип led" in q or "тип экрана" in q:
            summary_bits.append(answer)
        elif "шаг пикселя" in q:
            summary_bits.append(answer.replace(" ", ""))
        elif q.startswith("ширина"):
            summary_bits.append(f"{answer}мм")
        elif q.startswith("высота"):
            # pair with previous width if possible
            if summary_bits and summary_bits[-1].endswith("мм") and "×" not in summary_bits[-1]:
                summary_bits[-1] = f"{summary_bits[-1][:-2]}×{answer}мм"
            else:
                summary_bits.append(f"h{answer}мм")
        elif "монтаж" in q:
            summary_bits.append(answer)
    if summary_bits:
        title = f"{title} — {', '.join(summary_bits[:4])}"
    return title[:255]


def parse_application(text: str, sender_name: str | None = None) -> ParsedLead:
    """Parse free-form, labeled or quiz application text from Telegram."""
    text = (text or "").strip()
    lines = text.splitlines()

    labeled: dict[str, str] = {}
    for match in LABELED_RE.finditer(text):
        key = match.group(1).lower()
        labeled[key] = match.group(2).strip()

    quiz_name = None
    quiz_match = QUIZ_TITLE_RE.search(text)
    if quiz_match:
        quiz_name = quiz_match.group("quiz").strip().strip('«»"\'')

    name = (
        labeled.get("имя")
        or labeled.get("фио")
        or labeled.get("name")
        or sender_name
    )
    phone = labeled.get("телефон") or labeled.get("phone") or labeled.get("тел")
    email = labeled.get("email") or labeled.get("почта") or labeled.get("e-mail")
    city = (
        labeled.get("местоположение")
        or labeled.get("локация")
        or labeled.get("location")
        or labeled.get("город")
        or labeled.get("city")
    )
    page_url = (
        labeled.get("страница")
        or labeled.get("page")
        or labeled.get("url")
        or labeled.get("сайт")
    )

    messengers: dict[str, str] = {}
    for key in ("max", "whatsapp", "telegram"):
        if key in labeled:
            messengers[key] = labeled[key]

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
    if "max" in messengers:
        messengers["max"] = _clean_phone(messengers["max"]) if PHONE_RE.search(messengers["max"] or "") else messengers["max"]

    answers = _extract_quiz_answers(lines)
    title = _build_title(quiz_name, name, answers)
    comments = _build_comments(
        {
            "quiz_name": quiz_name,
            "city": city,
            "page_url": page_url,
            "max": messengers.get("max"),
        },
        answers,
        text,
    )

    return ParsedLead(
        title=title,
        name=name,
        phone=phone,
        email=email,
        city=city,
        page_url=page_url,
        quiz_name=quiz_name,
        answers=answers,
        messengers=messengers,
        comments=comments,
        extra={**labeled, **{f"answer:{q}": a for q, a in answers}},
        raw_text=text,
    )
