# Telegram AI Bot (xAI / Grok)

Telegram-бот на `aiogram` с тарифами `Free/Pro`, дневными лимитами, генерацией изображений и веб-админкой для управления пользователями.

## Что умеет бот

- Общение с пользователем через xAI API (`/chat/completions`).
- Анализ фото пользователя (мультимодальный запрос в `/chat/completions`).
- Генерация изображений через xAI API (`/images/generations`).
- FAQ-слоты без LLM для частых запросов: погода, курс валют, время в городе, поиск адреса, актуальные новости.
- Два тарифа:
  - `Free`: 10 сообщений/день, 1 изображение/день.
  - `Pro`: 150 сообщений/день, 80 изображений/месяц.
- Для `Pro` включена короткая память контекста (последние сообщения диалога).
- Покупка `Pro` через ЮKassa (`api` или `simplepay`) с подтверждением статуса оплаты.
- Авто-проверка оплаты после создания платежа (фоновый polling по таймеру).
- Webhook ЮKassa для автоматической активации Pro (идемпотентная обработка `payment_id`).
- Кнопочное меню для `Free` и `Pro`.
- В меню `Free` и `Pro` есть кнопка `◈ Создать изображение`.
- В системном меню команд доступны `/support`, `/terms`, `/privacy`, `/clear_history`.
- В `Pro` показывается кнопка `Продлить Pro`, только если до конца подписки осталось `<= 3` дней.
- После первой успешной оплаты бот удаляет служебные сообщения оплаты и отправляет новое приветствие (при продлении Pro сообщения не удаляются).
- Команда `/start` добавляется в меню команд Telegram (описание: `Старт`).
- Простая админка (Flask): список пользователей, фильтры, переключение плана, отметка оплаты.
- Аудит событий плана (`plan_events`): фиксация активации Pro (дата/время/период/источник/сумма).
- Ротация логов и запись latency/ошибок API в `api.log`.

## Стек

- Python 3.10+
- `aiogram` (бот)
- `requests` (xAI API)
- `sqlite3` (локальная БД)
- `Flask` (админка)

## Структура проекта

- `bot.py` — Telegram-бот, тарифы, лимиты, интеграция с xAI.
- `admin_app.py` — веб-админка.
- `bot.sqlite3` — рабочая БД.
- `bot_test.sqlite3` — тестовая БД (если используется).

## Быстрый старт

### 1) Установка зависимостей

```bash
pip install aiogram requests flask
```

### 2) Переменные окружения

Бот и админка автоматически читают переменные из файла `.env` в корне проекта.
Шаблон: `.env.example`.

```bash
cp .env.example .env
```

#### Обязательные

- `TELEGRAM_BOT_TOKEN` — токен Telegram-бота.
- `XAI_API_KEY` — ключ xAI API.

#### Рекомендуемые

- `ADMIN_PANEL_TOKEN` — токен доступа к админке (сильно рекомендуется).
- `SUPPORT_CONTACT` — контакт саппорта в боте (например, `@my_support`).
- `YK_SHOP_ID` и `YK_SHOP_SECRET_KEY` — ключи ЮKassa для кнопки оплаты в боте.

#### Полный список переменных

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | `""` | Токен Telegram-бота |
| `XAI_API_KEY` | `""` | API-ключ xAI |
| `XAI_BASE_URL` | `https://api.x.ai/v1` | Базовый URL xAI |
| `BOT_DB_PATH` | `bot.sqlite3` | Путь к SQLite |
| `SUPPORT_CONTACT` | `@your_support_username` | Контакт техподдержки |
| `FREE_TEXT_MODEL` | `grok-3-mini` | Текстовая модель Free |
| `FREE_IMAGE_MODEL` | `grok-imagine-image` | Модель изображений Free |
| `PRO_TEXT_MODEL` | `grok-4-1-fast-reasoning` | Текстовая модель Pro |
| `PRO_IMAGE_MODEL` | `grok-imagine-image` | Модель изображений Pro |
| `XAI_VISION_MODEL` | `grok-4-fast-non-reasoning` | Базовая модель для анализа фото |
| `FREE_VISION_MODEL` | `XAI_VISION_MODEL` | Отдельная vision-модель для Free (опционально) |
| `PRO_VISION_MODEL` | `XAI_VISION_MODEL` | Отдельная vision-модель для Pro (опционально) |
| `VISION_FALLBACK_MODEL` | `grok-4-fast-non-reasoning` | Резервная модель при ошибке “model does not support image” |
| `TERMS_URL` | `""` | Публичная ссылка на оферту/условия |
| `TERMS_TEXT` | текст условий по умолчанию | Короткие условия Pro и возврата в боте |
| `WELCOME_VIDEO_PATH` | `""` | Локальный путь к welcome-видео для `/start` |
| `FREE_MESSAGES_DAILY` | `10` | Лимит сообщений Free в день |
| `FREE_IMAGES_DAILY` | `1` | Лимит изображений Free в день |
| `PRO_MESSAGES_DAILY` | `150` | Лимит сообщений Pro в день |
| `PRO_IMAGES_MONTHLY` | `80` | Лимит изображений Pro в месяц |
| `PRO_CONTEXT_MESSAGES` | `10` | Сколько последних сообщений хранить в контексте Pro |
| `PRO_CONTEXT_MAX_CHARS` | `800` | Обрезка длины одного сообщения в контексте Pro |
| `PRO_PRICE_RUB` | `499` | Цена Pro |
| `FAQ_DEFAULT_CITY` | `""` | Город по умолчанию для коротких FAQ по погоде/времени |
| `FAQ_ADDRESS_USER_AGENT` | `askora-ai-bot/1.0 (+https://t.me)` | User-Agent для геокодинга адресов |
| `FAQ_NEWS_DEFAULT_QUERY` | `главные новости` | Тема по умолчанию для FAQ новостей |
| `FAQ_NEWS_ITEMS_LIMIT` | `3` | Сколько заголовков новостей показывать в ответе (1-5) |
| `PRO_DAYS` | `30` | Срок Pro (дней) |
| `XAI_MAX_OUTPUT_TOKENS` | `1000` | Глобальный потолок токенов ответа |
| `FREE_MAX_OUTPUT_TOKENS` | `120` | Лимит токенов ответа для Free |
| `PRO_MAX_OUTPUT_TOKENS` | `800` | Лимит токенов ответа для Pro |
| `XAI_DAILY_HARD_LIMIT` | `300` | Жесткий дневной лимит (в текущей логике не используется) |
| `XAI_MAX_USER_PROMPT_CHARS` | `3500` | Макс. длина запроса пользователя |
| `XAI_MAX_VISION_IMAGE_BYTES` | `5242880` | Макс. размер фото для анализа (байт) |
| `RATE_MIN_INTERVAL_SEC` | `2` | Минимальная пауза между запросами одного пользователя |
| `RATE_MAX_PER_MINUTE` | `20` | Максимум запросов от пользователя за минуту |
| `SQLITE_BUSY_TIMEOUT_MS` | `5000` | Ожидание блокировки SQLite (busy timeout, мс) |
| `CONTINUE_MAX_AGE_MINUTES` | `30` | Резерв (в текущей логике не используется) |
| `XAI_CONNECT_TIMEOUT_SEC` | `5` | Таймаут соединения к xAI |
| `XAI_READ_TIMEOUT_SEC` | `45` | Таймаут ожидания ответа xAI |
| `AUTO_PAY_CHECK_ENABLED` | `1` | Включить фоновую автопроверку статуса оплаты |
| `AUTO_PAY_CHECK_DELAYS_SEC` | `60,180,420` | Задержки (сек) для фоновых проверок оплаты |
| `PAYMENT_CLEANUP_WINDOW` | `250` | Сколько последних сообщений чистить после успешной оплаты |
| `XAI_SYSTEM_PROMPT` | короткий русский системный промпт | Системная инструкция модели |
| `ADMIN_SECRET_KEY` | `change-me` | Flask secret key |
| `ADMIN_PANEL_TOKEN` | `""` | Токен админки |
| `ADMIN_PORT` | `8080` | Порт админки |
| `YK_ENABLED` | `1` | Включить интеграцию оплаты ЮKassa в боте |
| `YK_PAY_MODE` | `api` | Режим оплаты: `api` или `simplepay` |
| `YK_API_BASE` | `https://api.yookassa.ru/v3` | Базовый URL API ЮKassa |
| `YK_CONNECT_TIMEOUT_SEC` | `8` | Таймаут соединения к YooKassa/SimplePay |
| `YK_READ_TIMEOUT_SEC` | `30` | Таймаут чтения ответа YooKassa/SimplePay |
| `YK_NETWORK_RETRIES` | `1` | Кол-во повторов при timeout/connection error к YooKassa |
| `YK_SHOP_ID` | `""` | Shop ID для платежей (`/v3/payments`) |
| `YK_SHOP_SECRET_KEY` | `""` | Секретный ключ Shop для платежей |
| `YK_RETURN_URL` | `https://t.me` | Return URL для редиректа после оплаты |
| `YK_SIMPLEPAY_SHOP_ID` | `""` | Shop ID для SimplePay формы |
| `YK_SIMPLEPAY_ENDPOINT` | `https://yookassa.ru/integration/simplepay/payment` | Endpoint SimplePay формы |
| `YK_WEBHOOK_SECRET` | `""` | Секрет webhook (путь/токен) для `POST /yk/webhook` |
| `YK_WEBHOOK_ALLOW_INSECURE` | `0` | Разрешить webhook без секрета (только для локальной отладки) |
| `YK_WEBHOOK_TRUST_X_FORWARDED_FOR` | `0` | Доверять `X-Forwarded-For` только при работе за trusted reverse proxy |
| `YK_WEBHOOK_TRUSTED_PROXIES` | `""` | Список IP reverse proxy через запятую; обязателен для `X-Forwarded-For` |
| `YK_WEBHOOK_ALLOWED_IPS` | `""` | Опциональный allowlist IP через запятую для webhook |
| `YK_PAYOUT_ACCOUNT_ID` | `""` | Account/Agent ID для payout-тестов (`/v3/payouts`) |
| `YK_PAYOUT_SECRET_KEY` | `""` | Секрет payout-шлюза для payout-тестов |

### 3) Примеры экспорта переменных

#### PowerShell (Windows)

```powershell
$env:TELEGRAM_BOT_TOKEN="<YOUR_TELEGRAM_BOT_TOKEN>"
$env:XAI_API_KEY="<YOUR_XAI_API_KEY>"
$env:SUPPORT_CONTACT="@my_support"
$env:ADMIN_PANEL_TOKEN="change_me_long_random_token"
$env:YK_SHOP_ID="YOUR_YOOKASSA_SHOP_ID"
$env:YK_SHOP_SECRET_KEY="YOUR_YOOKASSA_SHOP_SECRET_KEY"
$env:YK_RETURN_URL="https://t.me/your_bot_username"
$env:YK_PAYOUT_ACCOUNT_ID="YOUR_YOOKASSA_PAYOUT_ACCOUNT_ID"
$env:YK_PAYOUT_SECRET_KEY="YOUR_YOOKASSA_PAYOUT_SECRET_KEY"
```

#### Linux/macOS

```bash
export TELEGRAM_BOT_TOKEN="<YOUR_TELEGRAM_BOT_TOKEN>"
export XAI_API_KEY="<YOUR_XAI_API_KEY>"
export SUPPORT_CONTACT="@my_support"
export ADMIN_PANEL_TOKEN="change_me_long_random_token"
export YK_SHOP_ID="YOUR_YOOKASSA_SHOP_ID"
export YK_SHOP_SECRET_KEY="YOUR_YOOKASSA_SHOP_SECRET_KEY"
export YK_RETURN_URL="https://t.me/your_bot_username"
export YK_PAYOUT_ACCOUNT_ID="YOUR_YOOKASSA_PAYOUT_ACCOUNT_ID"
export YK_PAYOUT_SECRET_KEY="YOUR_YOOKASSA_PAYOUT_SECRET_KEY"
```

### 4) Запуск бота

```bash
python bot.py
```

### 5) Запуск админки

```bash
python admin_app.py
```

Открыть в браузере:

- `http://127.0.0.1:8080/?token=<ADMIN_PANEL_TOKEN>`

### VPS (Ubuntu 22.04): только бот, без фронта

Если на VPS должен работать только Telegram-бот, запускайте только `bot.py`.
`admin_app.py` (фронт/админка) на VPS не поднимайте.

1. Подготовьте окружение:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
cd /opt/bot_grok
chmod +x scripts/bootstrap_vps_backend.sh scripts/run_bot_backend.sh
./scripts/bootstrap_vps_backend.sh
```

2. Проверьте ручной запуск только бэкенда:

```bash
./scripts/run_bot_backend.sh
```

3. Настройте автозапуск через `systemd` (только бот):

```bash
sudo cp deploy/systemd/bot-backend.service.example /etc/systemd/system/bot-backend.service
sudo nano /etc/systemd/system/bot-backend.service
```

Проверьте в unit-файле:
- `User` (например, `ubuntu`)
- `WorkingDirectory` (например, `/opt/bot_grok`)
- `EnvironmentFile` (путь к `.env`)
- `ExecStart` (путь к `.venv/bin/python` и `bot.py`)

Далее:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bot-backend
sudo systemctl status bot-backend
journalctl -u bot-backend -f
```

Итог: на VPS работает только бот, фронт/админка остается на вашей локальной машине.

### Команды в меню Telegram

- `/start` — стартовое сообщение
- `/support` — техподдержка
- `/terms` — условия Pro
- `/privacy` — политика хранения данных
- `/clear_history` — очистка памяти AI (только `Pro`)

### 6) Тестирование выплат ЮKassa (test gateway)

В проект добавлен CLI-скрипт: `yookassa_test_payout.py`.

Сначала задайте креды тестового шлюза:

#### PowerShell

```powershell
$env:YK_PAYOUT_ACCOUNT_ID="YOUR_TEST_ACCOUNT_ID"
$env:YK_PAYOUT_SECRET_KEY="YOUR_TEST_SECRET_KEY"
```

#### Linux/macOS

```bash
export YK_PAYOUT_ACCOUNT_ID="YOUR_TEST_ACCOUNT_ID"
export YK_PAYOUT_SECRET_KEY="YOUR_TEST_SECRET_KEY"
```

Проверка подключения к шлюзу:

```bash
python yookassa_test_payout.py me
```

Проверка доступных методов выплат и баланса:

```bash
python yookassa_test_payout.py balance
```

Тестовая выплата на ЮMoney-кошелек:

```bash
python yookassa_test_payout.py payout --amount 2.00 --wallet 4100116075156746
```

Скрипт использует `POST /v3/payouts` с `payout_destination_data` и выводит полный ответ API.
Если статус не финальный, скрипт автоматически опрашивает `GET /v3/payouts/{id}`.

### 7) Тест кнопки `Купить Pro` в Telegram

1. Убедитесь, что заданы:
   - `YK_SHOP_ID`,
   - `YK_SHOP_SECRET_KEY`,
   - `YK_RETURN_URL`.
2. В боте нажмите `◆ Купить Pro` → `◆ Оплатить ...`.
3. Бот создаст платеж и отправит:
   - кнопку `Перейти к оплате`,
   - кнопку `Проверить оплату`.
4. После успешной оплаты нажмите `Проверить оплату`:
   - при `status=succeeded` включается Pro,
   - запись об активации попадает в `plan_events` с `payment_ref=<payment_id>`,
   - при первой покупке служебные и недавние сообщения чата удаляются, бот отправляет новое приветствие.
   - при продлении Pro сообщения не удаляются.
   - при продлении срок считается от текущего `plan_expires_at` (дни добавляются к действующему сроку).
5. Если пользователь не нажал `Проверить оплату`, бот делает фоновые автопроверки по таймеру (`AUTO_PAY_CHECK_DELAYS_SEC`) и активирует Pro автоматически при `status=succeeded`.

### 8) Webhook ЮKassa

Поддержан endpoint в `admin_app.py`:

- `POST /yk/webhook`
- `POST /yk/webhook/<YK_WEBHOOK_SECRET>`

Рекомендация:

1. Задайте `YK_WEBHOOK_SECRET` в `.env` (иначе webhook отклоняется; fail-closed).
2. В ЮKassa укажите URL с секретом в пути.
3. (Опционально) задайте `YK_WEBHOOK_ALLOWED_IPS` для фильтрации по IP.
4. Если используете reverse proxy, включайте `YK_WEBHOOK_TRUST_X_FORWARDED_FOR=1` только вместе с `YK_WEBHOOK_TRUSTED_PROXIES`.

Webhook идемпотентен: один и тот же `payment_id` активирует Pro только один раз (`processed=1`).
Перед активацией webhook дополнительно проверяет статус платежа через API ЮKassa (`GET /payments/{id}`).

## Логика меню

### Free

Кнопки:

- `◆ Купить Pro`
- `◈ Создать изображение`

### Pro

Кнопки:

- `◆ Pro до: DD.MM.YYYY`
- `◈ Создать изображение`
- `🧠 Очистить память AI`
- `◆ Продлить Pro` — только если до окончания `<= 3` дней.

### Оплата в боте (кнопка `◆ Оплатить`)

Режим `YK_PAY_MODE=api`:

1. Бот создает платеж в ЮKassa (`POST /v3/payments`).
2. Пользователь получает кнопку `Перейти к оплате`.
3. После оплаты пользователь нажимает `Проверить оплату`.
4. Если статус платежа `succeeded`, бот активирует Pro, удаляет служебные сообщения оплаты и фиксирует `payment_ref` в `plan_events`.
5. Дополнительно запускается фоновый auto-polling (без участия пользователя).

Режим `YK_PAY_MODE=simplepay`:

1. Бот создает ссылку через SimplePay (`/integration/simplepay/payment`).
2. Пользователь нажимает `Перейти к оплате`.
3. После оплаты нажимает `Проверить оплату`.
4. Бот запрашивает статус платежа и активирует Pro только при `status=succeeded`.
5. Если статус не подтвержден, Pro не активируется.
6. Дополнительно запускается фоновый auto-polling (если доступен `payments` API).

## Лимиты

- Списываются по факту обработанного запроса (включая локальные FAQ-ответы).
- Если FAQ требует уточнение (город/пара/адрес), уточняющий шаг не списывает лишний лимит.
- Сообщения: `day_messages_used` (для `Free` и `Pro`, в день).
- Изображения `Free`: `day_images_used` (в день).
- Изображения `Pro`: `month_images_used` (в месяц).
- При превышении лимита бот не отправляет запрос в xAI.
- Смена плана в админке (`Free/Pro/Refund`) не сбрасывает счетчики вручную.
- Списание лимитов выполняется атомарным `UPDATE ... WHERE < лимит` (без гонок при параллельных апдейтах).

## Антиспам и скорость

- Ограничение частоты: не чаще `RATE_MIN_INTERVAL_SEC` на пользователя.
- Ограничение окна: не больше `RATE_MAX_PER_MINUTE` в минуту на пользователя.
- При превышении бот возвращает понятное сообщение и не тратит лимиты/API.

## FAQ-слоты

Локально (без вызова xAI) обрабатываются запросы:

- погода по городу,
- курс валют,
- время в городе,
- поиск адреса/координат,
- актуальные новости.

Если в запросе не хватает данных (например, город/валютная пара), бот задает уточняющий вопрос и ждет следующий ответ пользователя.

## Память диалога

- `Free`: без контекстной памяти (в модель уходит только текущее сообщение).
- `Pro`: короткая память (последние `PRO_CONTEXT_MESSAGES` сообщений), чтобы поддерживать нить разговора.
- Для фото-анализа в модель отправляется системный промпт + текст запроса + изображение.

В БД сохраняются:

- последний обмен (`last_prompt`, `last_response`, `last_model`),
- короткая история Pro в `conversation_messages`.

## Админка

Возможности:

- Просмотр всех пользователей и фильтрация по `Free/Pro` и флагу оплаты.
- Быстрый перевод пользователя:
  - в `Free`,
  - в `Pro (без оплаты)`,
  - в `Pro (оплачено)`.
- Сброс флага оплаты `pro_paid`.
- Кнопка `Возврат → Free` (ручной возврат с фиксацией события).
- Изменение цены Pro (₽) прямо из админки, без правки `.env`.
- В таблице видна последняя активация Pro:
  - дата/время,
  - период (дни),
  - источник активации,
  - сумма.

Важно:

- Админка построена на встроенном Flask-сервере и подходит для MVP/внутреннего использования.
- Для продакшена лучше запускать через WSGI (gunicorn/uvicorn + reverse proxy).

## База данных (основные поля `users`)

- `user_id` — Telegram user id.
- `plan_key` — `free`/`pro`.
- `pro_paid` — флаг покупки Pro.
- `plan_started_at`, `plan_expires_at` — период плана.
- `day_key`, `day_messages_used`, `day_images_used` — дневные счетчики.
- `month_key`, `month_images_used` — месячный счетчик изображений для Pro.
- `pending_faq_intent` — ожидаемое уточнение для FAQ-слота (если бот задал уточняющий вопрос).
- `last_prompt`, `last_response`, `last_model`, `last_exchange_at` — последний диалог.

Дополнительно используются таблицы:

- `app_settings` (`pro_price_rub`) — текущая цена Pro, редактируется из админки.
- `yk_payments` — статусы платежей ЮKassa и флаг обработки.
- `payment_ui_messages` — служебные сообщения оплаты для последующей очистки после успешной оплаты.
- `conversation_messages` — короткая история диалога для Pro-контекста.

## Аудит активаций Pro (`plan_events`)

Для споров/возвратов и финансового учета фиксируются события плана:

- `user_id`
- `event_type` (`pro_activated_paid`, `pro_activated_unpaid`, `pro_activated_manual`, `pro_expired_to_free`, `plan_set_free`)
- `source` (например, `bot_pay_button`, `admin_panel`, `admin_refund`)
- `event_at` (дата/время UTC)
- `plan_started_at`, `plan_expires_at`
- `period_days`
- `amount_rub`
- `payment_ref` (если добавите внешний платежный id)
- `note`

Это дает формальный след: когда именно Pro активирован, на какой срок и из какого источника.

## План при споре/возврате

1. Найти пользователя в админке по `user_id`.
2. Проверить блок `Последняя активация Pro` (дата/время/период/источник/сумма).
3. Сверить с платежной системой (по `payment_ref`, когда подключите вебхук).
4. Если возврат подтвержден:
   - нажать `Возврат → Free`,
   - зафиксировать причину возврата в внутреннем журнале/CRM.
5. Сохранить артефакты спора:
   - скрин платежа/чека,
   - запись события из `plan_events`,
   - переписку пользователя.

## НДС и правовой чеклист (RU)

Текущая версия бота **не определяет автоматически ваш налоговый режим** и не может юридически гарантировать отсутствие НДС-рисков. Перед запуском проверьте:

1. Ваш режим налогообложения (УСН/НПД/ОСНО/и т.д.) у бухгалтера.
2. Нужно ли вам выставлять НДС на цифровую подписку в вашей модели работы.
3. Ограничения вашего банка/эквайринга/платежного провайдера для digital-подписок.
4. Наличие публичной оферты, политики возвратов и пользовательского соглашения.
5. Процедуру обработки чарджбеков и возвратов (кто, в какие сроки, какие доказательства).

Официальные стартовые источники для проверки (актуализируйте перед запуском):

- НПД (ФНС): условия, ограничения и ставки — https://npd.nalog.ru/
- ФНС: НДС при УСН (письмо и методические рекомендации) — https://www.nalog.gov.ru/rn77/taxation/taxes/nds_usn/15318056/
- ЮKassa: условия работы (комиссия/НДС в расчетах сервиса) — https://yookassa.ru/docs/support/payments/conditions
- ЮKassa: возвраты (процедуры, частичный/полный, причины) — https://yookassa.ru/docs/support/merchant/payments/refunds

## Проверка и отладка

Проверка синтаксиса:

```bash
python -m py_compile bot.py admin_app.py
```

Полезные точки диагностики:

- Проверьте переменные `TELEGRAM_BOT_TOKEN` и `XAI_API_KEY`.
- Проверьте, что сеть до `https://api.x.ai` доступна.
- Для медленных ответов уменьшайте `FREE_MAX_OUTPUT_TOKENS`.
- `bot.log` — общий лог приложения (с ротацией).
- `api.log` — отдельный лог API-вызовов (status/latency/errors для xAI и ЮKassa).
- SQLite работает в `WAL` + `busy_timeout`, что снижает ошибки блокировок при параллельных запросах.

## Известные ограничения текущей версии

- Подтверждение оплаты работает через кнопку `Проверить оплату`, фоновый polling и webhook, но для webhook нужно корректно выставить публичный URL и секрет.
- Для кнопки оплаты нужны ключи ЮKassa именно с правом `payments`; payout-only ключи не подходят.
- Голосовые сообщения не поддерживаются (бот просит отправить текст).
- Память диалога ограничена коротким контекстом только для Pro (без долгосрочной "бесконечной" памяти).
- Редактирование изображений отключено; доступна только генерация по тексту.
- SQLite подходит для MVP, но при большом трафике лучше перейти на PostgreSQL.

## Рекомендации для продакшена

- Обязательно задать `ADMIN_PANEL_TOKEN` и сложный `ADMIN_SECRET_KEY`.
- Не хранить ключи в коде и не публиковать их в чатах/скриншотах.
- Проверить, что webhook ЮKassa закрыт секретом и (по возможности) IP allowlist.
- Перенести хранение и логи в managed-инфраструктуру.
- Включить мониторинг ошибок и алерты.
