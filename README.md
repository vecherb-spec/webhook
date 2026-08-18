# Telegram → Bitrix24 / EspoCRM

Скрипт для VPS: заявки из Telegram-чата (и webhook Marquiz) создают **лиды** в Битрикс24 и/или EspoCRM.

## Как это работает

1. В нужный Telegram-чат добавляется бот (или Marquiz шлёт на `/marquiz`).
2. Парсятся имя / телефон / ответы квиза.
3. Через `CrmRouter` заявка пишется в настроенные CRM:
   - Bitrix24 (`BITRIX_WEBHOOK_URL`)
   - EspoCRM (`ESPO_URL` + `ESPO_API_KEY`)
4. Можно включить обе CRM сразу — лид создаётся и там, и там.

Режим по умолчанию — **polling** (HTTPS-домен не нужен).

---

## 1. Telegram-бот

1. Открой [@BotFather](https://t.me/BotFather) → `/newbot` → получи токен.
2. Добавь бота в чат с заявками.
3. Дай боту право читать сообщения:
   - для групп: BotFather → `/setprivacy` → **Disable** (иначе бот видит только команды и ответы себе).
4. Напиши в чат любое сообщение — после запуска сервиса в логах появится `chat_id=...`.  
   Этот ID нужно прописать в `.env` (`TELEGRAM_CHAT_IDS`).

Узнать chat_id можно и так: перешли сообщение из чата боту [@userinfobot](https://t.me/userinfobot) / [@getidsbot](https://t.me/getidsbot).

---

## 2. Входящий вебхук Битрикс24

1. Битрикс24 → **Разработчикам** → **Другое** → **Входящий вебхук**.
2. Права: **CRM**.
3. Скопируй URL вида:
   ```
   https://your-domain.bitrix24.ru/rest/1/xxxxxxxxxxxxxxxx/
   ```

По умолчанию создаётся **лид** (`crm.lead.add`).  
Чтобы создавать сделки — в `.env` поставь `BITRIX_ENTITY=deal`.

Можно оставить Bitrix выключенным (`BITRIX_ENABLED=false`), если нужен только EspoCRM.

---

## 2b. EspoCRM API

1. EspoCRM → **Administration** → **API Users** → Create.
2. Auth method: **API Key**, права на создание **Lead**.
3. В `.env`:
   ```env
   ESPO_URL=https://your-espo.example.com
   ESPO_API_KEY=...
   ESPO_ENTITY=Lead
   ESPO_LEAD_STATUS=New
   ESPO_SOURCE=Web Site
   ```

Опционально: `ESPO_FIELD_MAP=quiz_name:cQuizName,тип led:cLedType` — ответы квиза в кастомные поля.

---

## 3. Установка на VPS (Ubuntu)

```bash
# клонируй репозиторий
git clone <url-этого-репо> /tmp/tg-bitrix-src
cd /tmp/tg-bitrix-src

sudo bash scripts/install.sh
sudo nano /opt/tg-bitrix/.env
```

Заполни минимум:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_IDS=-1001234567890
BITRIX_WEBHOOK_URL=https://xxx.bitrix24.ru/rest/1/xxxxx/
BITRIX_ENTITY=lead
ESPO_URL=https://crm.example.com
ESPO_API_KEY=...
MODE=polling
```

Запуск:

```bash
sudo systemctl start tg-bitrix
sudo systemctl status tg-bitrix
journalctl -u tg-bitrix -f
```

Проверка: напиши в чат сообщение вроде:

```text
Имя: Иван
Телефон: +79001234567
Нужен расчёт
```

В Битрикс24 должен появиться лид, в чате — ответ с номером.

---

## 4. Запуск без systemd (вручную)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# отредактируй .env
python main.py
```

Или через Docker:

```bash
cp .env.example .env
# отредактируй .env
docker compose up -d --build
docker compose logs -f
```

---

## Настройки фильтрации

| Переменная | Смысл |
|---|---|
| `TELEGRAM_CHAT_IDS` | Только эти чаты (через запятую). Пусто = все чаты, куда добавлен бот |
| `FILTER_BY_KEYWORDS=true` | Создавать лиды только если в тексте есть слова из `KEYWORDS` |
| `KEYWORDS` | Например: `заявка,телефон,имя` |
| `IGNORE_BOTS=true` | Игнорировать сообщения от ботов |
| `MIN_MESSAGE_LENGTH` | Минимальная длина текста |

Если заявки приходят из другого бота/интеграции и выглядят шаблонно — включи `FILTER_BY_KEYWORDS` или оставь выключенным, чтобы падало всё.

---

## Что попадает в CRM

**Bitrix:** TITLE, NAME/PHONE/EMAIL, кастомные UF-поля квиза, SOURCE=WEBFORM.

**EspoCRM Lead:** firstName/lastName, phoneNumber, emailAddress, addressCity, description (ответы квиза), status/source из `.env`.

Поддерживаемые подписи в тексте заявки:

`Имя`, `ФИО`, `Телефон`, `Тел`, `Email`, `Почта`, `Город`, `Комментарий`, `Услуга`, `Источник`, messengers (`vk`/`telegram`/`max`)

---

## Режим webhook (опционально)

Если нужен webhook вместо polling:

```env
MODE=webhook
WEBHOOK_URL=https://your-domain.com/telegram
WEBHOOK_PORT=8080
WEBHOOK_PATH=/telegram
```

Перед ботом должен стоять nginx/caddy с HTTPS, проксирующий на `127.0.0.1:8080`.

---

## Обновление

```bash
cd /path/to/repo
git pull
sudo bash scripts/install.sh
sudo systemctl restart tg-bitrix
```

---

## Частые проблемы

**Бот молчит в группе**  
Privacy mode включён. Выключи через BotFather: `/setprivacy` → Disable, затем удали и снова добавь бота в чат.

**В логах `Skip message from chat_id=...`**  
Добавь этот ID в `TELEGRAM_CHAT_IDS`.

**Ошибка Bitrix `insufficient_scope` / `ACCESS_DENIED`**  
У вебхука нет права CRM — пересоздай вебхук с нужными правами.

**Дубли лидов**  
Не запускай два экземпляра бота с одним токеном одновременно.
