"""
Telegram bot + xAI API with pricing plans and limit protection (aiogram v3).

Run:
1) Install deps:
   pip install aiogram requests

2) Set environment variables:
   PowerShell:
   $env:TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
   $env:XAI_API_KEY="YOUR_XAI_API_KEY"

   Linux/macOS:
   export TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
   export XAI_API_KEY="YOUR_XAI_API_KEY"

   Optional:
   XAI_DEFAULT_MODEL="grok-4-fast-non-reasoning"
   XAI_SMART_MODEL="grok-4-1"
   XAI_IMAGE_MODEL="grok-imagine-image"
   XAI_MAX_OUTPUT_TOKENS="1000"
   XAI_DAILY_HARD_LIMIT="300"

3) Start:
   python bot.py
"""

import asyncio
import base64
from collections import defaultdict, deque
from email.utils import parsedate_to_datetime
import html
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, quote_plus, urlparse
from typing import Any, Optional, Tuple
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandStart
from requests.auth import HTTPBasicAuth
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.types.input_file import FSInputFile
from env_utils import load_env_file


load_env_file()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
XAI_API_KEY = os.getenv("XAI_API_KEY", "").strip()
XAI_BASE_URL = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").rstrip("/")
DB_PATH = os.getenv("BOT_DB_PATH", "bot.sqlite3").strip()

DEFAULT_MODEL = os.getenv("XAI_DEFAULT_MODEL", "grok-4-fast-non-reasoning").strip()
SMART_MODEL = os.getenv("XAI_SMART_MODEL", "grok-4-1").strip()
IMAGE_MODEL = os.getenv("XAI_IMAGE_MODEL", "grok-imagine-image").strip()
SUPPORT_CONTACT = os.getenv("SUPPORT_CONTACT", "@your_support_username").strip()
TERMS_URL = os.getenv("TERMS_URL", "").strip()
TERMS_TEXT = os.getenv(
    "TERMS_TEXT",
    "Условия Pro: 150 сообщений/день и 80 изображений/месяц. "
    "Возврат возможен по обращению в поддержку с проверкой платежа.",
).strip()
FREE_TEXT_MODEL = os.getenv("FREE_TEXT_MODEL", "grok-3-mini").strip()
FREE_IMAGE_MODEL = os.getenv("FREE_IMAGE_MODEL", "grok-imagine-image").strip()
PRO_TEXT_MODEL = os.getenv("PRO_TEXT_MODEL", "grok-4-1-fast-reasoning").strip()
PRO_IMAGE_MODEL = os.getenv("PRO_IMAGE_MODEL", "grok-imagine-image").strip()
XAI_VISION_MODEL = os.getenv("XAI_VISION_MODEL", DEFAULT_MODEL).strip()
FREE_VISION_MODEL = os.getenv("FREE_VISION_MODEL", XAI_VISION_MODEL).strip()
PRO_VISION_MODEL = os.getenv("PRO_VISION_MODEL", XAI_VISION_MODEL).strip()
VISION_FALLBACK_MODEL = os.getenv("VISION_FALLBACK_MODEL", DEFAULT_MODEL).strip()
FREE_MESSAGES_DAILY = int(os.getenv("FREE_MESSAGES_DAILY", "10"))
FREE_IMAGES_DAILY = int(os.getenv("FREE_IMAGES_DAILY", "1"))
PRO_MESSAGES_DAILY = int(os.getenv("PRO_MESSAGES_DAILY", "150"))
PRO_IMAGES_MONTHLY = int(os.getenv("PRO_IMAGES_MONTHLY", "80"))
PRO_CONTEXT_MESSAGES = max(int(os.getenv("PRO_CONTEXT_MESSAGES", "10")), 0)
PRO_CONTEXT_MAX_CHARS = max(int(os.getenv("PRO_CONTEXT_MAX_CHARS", "800")), 200)
PRO_PRICE_RUB = int(os.getenv("PRO_PRICE_RUB", "499"))
PRO_DAYS = int(os.getenv("PRO_DAYS", "30"))
YK_API_BASE = os.getenv("YK_API_BASE", "https://api.yookassa.ru/v3").rstrip("/")
YK_SHOP_ID = os.getenv("YK_SHOP_ID", "").strip()
YK_SHOP_SECRET_KEY = os.getenv("YK_SHOP_SECRET_KEY", os.getenv("YK_SECRET_KEY", "")).strip()
YK_RETURN_URL = os.getenv("YK_RETURN_URL", "https://t.me").strip()
YK_ENABLED = os.getenv("YK_ENABLED", "1").strip() == "1"
YK_PAYOUT_ACCOUNT_ID = os.getenv("YK_PAYOUT_ACCOUNT_ID", "").strip()
YK_PAYOUT_SECRET_KEY = os.getenv("YK_PAYOUT_SECRET_KEY", "").strip()
YK_PAY_MODE = os.getenv("YK_PAY_MODE", "api").strip().lower()  # api | simplepay
YK_SIMPLEPAY_SHOP_ID = os.getenv("YK_SIMPLEPAY_SHOP_ID", "").strip()
YK_SIMPLEPAY_ENDPOINT = os.getenv(
    "YK_SIMPLEPAY_ENDPOINT",
    "https://yookassa.ru/integration/simplepay/payment",
).strip()
YK_CONNECT_TIMEOUT_SEC = float(os.getenv("YK_CONNECT_TIMEOUT_SEC", "8"))
YK_READ_TIMEOUT_SEC = float(os.getenv("YK_READ_TIMEOUT_SEC", "30"))
YK_NETWORK_RETRIES = max(int(os.getenv("YK_NETWORK_RETRIES", "1")), 0)
WELCOME_VIDEO_PATH = os.getenv(
    "WELCOME_VIDEO_PATH",
    r"C:\Users\David\Documents\git\bot_grok\document_5240053494907444059.mp4",
).strip()

MAX_OUTPUT_TOKENS = int(os.getenv("XAI_MAX_OUTPUT_TOKENS", "1000"))
FREE_MAX_OUTPUT_TOKENS = int(os.getenv("FREE_MAX_OUTPUT_TOKENS", "120"))
PRO_MAX_OUTPUT_TOKENS = int(os.getenv("PRO_MAX_OUTPUT_TOKENS", "800"))
DAILY_HARD_LIMIT = int(os.getenv("XAI_DAILY_HARD_LIMIT", "300"))
MAX_USER_PROMPT_CHARS = int(os.getenv("XAI_MAX_USER_PROMPT_CHARS", "3500"))
CONTINUE_MAX_AGE_MINUTES = int(os.getenv("CONTINUE_MAX_AGE_MINUTES", "30"))
XAI_CONNECT_TIMEOUT_SEC = float(os.getenv("XAI_CONNECT_TIMEOUT_SEC", "5"))
XAI_READ_TIMEOUT_SEC = float(os.getenv("XAI_READ_TIMEOUT_SEC", "45"))
MAX_VISION_IMAGE_BYTES = int(os.getenv("XAI_MAX_VISION_IMAGE_BYTES", "5242880"))
RATE_MIN_INTERVAL_SEC = float(os.getenv("RATE_MIN_INTERVAL_SEC", "2"))
RATE_MAX_PER_MINUTE = int(os.getenv("RATE_MAX_PER_MINUTE", "20"))
SQLITE_BUSY_TIMEOUT_MS = max(int(os.getenv("SQLITE_BUSY_TIMEOUT_MS", "5000")), 1000)
AUTO_PAY_CHECK_ENABLED = os.getenv("AUTO_PAY_CHECK_ENABLED", "1").strip() == "1"
AUTO_PAY_CHECK_DELAYS_SEC = os.getenv("AUTO_PAY_CHECK_DELAYS_SEC", "60,180,420").strip()
PAYMENT_CLEANUP_WINDOW = max(int(os.getenv("PAYMENT_CLEANUP_WINDOW", "250")), 0)
FAQ_DEFAULT_CITY = os.getenv("FAQ_DEFAULT_CITY", "").strip()
FAQ_ADDRESS_USER_AGENT = os.getenv(
    "FAQ_ADDRESS_USER_AGENT",
    "askora-ai-bot/1.0 (+https://t.me)",
).strip()
FAQ_NEWS_DEFAULT_QUERY = os.getenv("FAQ_NEWS_DEFAULT_QUERY", "главные новости").strip()
FAQ_NEWS_ITEMS_LIMIT = max(min(int(os.getenv("FAQ_NEWS_ITEMS_LIMIT", "3")), 5), 1)
SYSTEM_PROMPT = os.getenv(
    "XAI_SYSTEM_PROMPT",
    "Отвечай на русском кратко и по делу: 1-2 предложения, если пользователь не просил подробно. "
    "Не выдумывай факты, даты и актуальные новости: при нехватке данных честно сообщай об ограничении.",
).strip()
MSK_TZ = timezone(timedelta(hours=3))

@dataclass(frozen=True)
class Plan:
    key: str
    title: str
    message_daily_limit: int
    image_limit: int
    image_period: str  # day | month
    text_model: str
    image_model: str


PLANS = {
    "free": Plan(
        "free",
        "Free",
        FREE_MESSAGES_DAILY,
        FREE_IMAGES_DAILY,
        "day",
        FREE_TEXT_MODEL,
        FREE_IMAGE_MODEL,
    ),
    "pro": Plan(
        "pro",
        "Pro",
        PRO_MESSAGES_DAILY,
        PRO_IMAGES_MONTHLY,
        "month",
        PRO_TEXT_MODEL,
        PRO_IMAGE_MODEL,
    ),
}

DEFAULT_PLAN_KEY = "free"
user_locks: dict[int, asyncio.Lock] = {}
PRO_PRICE_SETTING_KEY = "pro_price_rub"
user_minute_events: dict[int, deque[float]] = defaultdict(deque)
user_last_request_ts: dict[int, float] = {}
background_tasks: set[asyncio.Task] = set()

logger = logging.getLogger("bot")
api_logger = logging.getLogger("api")

_thread_local_state = threading.local()


def get_http_session() -> requests.Session:
    session = getattr(_thread_local_state, "http_session", None)
    if session is None:
        session = requests.Session()
        _thread_local_state.http_session = session
    return session


def get_yk_session() -> requests.Session:
    session = getattr(_thread_local_state, "yk_session", None)
    if session is None:
        session = requests.Session()
        _thread_local_state.yk_session = session
    return session

FAQ_INTENT_WEATHER = "weather"
FAQ_INTENT_FX = "fx"
FAQ_INTENT_TIME = "time"
FAQ_INTENT_ADDRESS = "address"
FAQ_INTENT_NEWS = "news"

WEATHER_CODE_MAP = {
    0: "ясно",
    1: "в основном ясно",
    2: "переменная облачность",
    3: "пасмурно",
    45: "туман",
    48: "туман с изморозью",
    51: "слабая морось",
    53: "морось",
    55: "сильная морось",
    56: "ледяная морось",
    57: "сильная ледяная морось",
    61: "слабый дождь",
    63: "дождь",
    65: "сильный дождь",
    66: "ледяной дождь",
    67: "сильный ледяной дождь",
    71: "слабый снег",
    73: "снег",
    75: "сильный снег",
    77: "снежная крупа",
    80: "ливень",
    81: "ливень",
    82: "сильный ливень",
    85: "снегопад",
    86: "сильный снегопад",
    95: "гроза",
    96: "гроза с градом",
    99: "сильная гроза с градом",
}

CURRENCY_ALIASES = {
    "usd": "USD",
    "доллар": "USD",
    "доллара": "USD",
    "доллары": "USD",
    "бакс": "USD",
    "бакса": "USD",
    "баксы": "USD",
    "eur": "EUR",
    "евро": "EUR",
    "rub": "RUB",
    "rur": "RUB",
    "руб": "RUB",
    "рубль": "RUB",
    "рубля": "RUB",
    "рубли": "RUB",
    "₽": "RUB",
    "cny": "CNY",
    "юань": "CNY",
    "юаня": "CNY",
    "kzt": "KZT",
    "тенге": "KZT",
    "gbp": "GBP",
    "фунт": "GBP",
    "фунта": "GBP",
    "jpy": "JPY",
    "иена": "JPY",
    "йена": "JPY",
    "aed": "AED",
    "дирхам": "AED",
    "try": "TRY",
    "лира": "TRY",
    "uah": "UAH",
    "гривна": "UAH",
    "byn": "BYN",
}


def pro_days_left(row: sqlite3.Row) -> int:
    dt = parse_iso_ts(row["plan_expires_at"])
    if dt is None:
        return 0
    expires_date = dt.astimezone(MSK_TZ).date()
    now_date = utc_now().astimezone(MSK_TZ).date()
    return max((expires_date - now_date).days, 0)


def build_terms_button() -> InlineKeyboardButton:
    if TERMS_URL:
        return InlineKeyboardButton(text="◆ Условия", url=TERMS_URL)
    return InlineKeyboardButton(text="◆ Условия", callback_data="home_terms")


def build_home_keyboard(row: sqlite3.Row) -> InlineKeyboardMarkup:
    plan_key = plan_for_row(row).key
    if plan_key == "pro":
        keyboard = [
            [
                InlineKeyboardButton(
                    text=f"◆ Pro до: {format_pro_until_date(row)}",
                    callback_data="home_pro_until",
                ),
            ],
            [InlineKeyboardButton(text="◈ Создать изображение", callback_data="home_img_create")],
            [InlineKeyboardButton(text="🧠 Очистить память AI", callback_data="home_clear_history")],
        ]
        if pro_days_left(row) <= 3:
            keyboard.append(
                [InlineKeyboardButton(text="◆ Продлить Pro", callback_data="home_renew")]
            )
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◆ Купить Pro", callback_data="home_buy")],
            [InlineKeyboardButton(text="◈ Создать изображение", callback_data="home_img_create")],
        ]
    )


def build_buy_keyboard() -> InlineKeyboardMarkup:
    current_price = get_pro_price_rub()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"◆ Оплатить {current_price} ₽ / {PRO_DAYS} дней",
                    callback_data="pay_pro",
                )
            ]
        ]
    )


def build_images_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◈ Создать", callback_data="img_create")],
            [InlineKeyboardButton(text="× Отмена", callback_data="img_cancel")],
        ]
    )


def build_cabinet_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💳 Баланс", callback_data="cab_balance"),
                InlineKeyboardButton(text="📦 Режимы", callback_data="cab_tariffs"),
            ],
            [
                InlineKeyboardButton(text="🟦 Free", callback_data="plan_free"),
                InlineKeyboardButton(text="🟩 Pro", callback_data="plan_pro"),
            ],
            [InlineKeyboardButton(text="🖼 Изображения", callback_data="open_images")],
        ]
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def msk_day_key(dt: datetime) -> str:
    return dt.astimezone(MSK_TZ).date().isoformat()


def msk_month_key(dt: datetime) -> str:
    return dt.astimezone(MSK_TZ).strftime("%Y-%m")


def parse_delay_list(value: str) -> list[float]:
    delays: list[float] = []
    for part in value.split(","):
        raw = part.strip()
        if not raw:
            continue
        try:
            sec = float(raw)
        except ValueError:
            continue
        if sec > 0:
            delays.append(sec)
    if not delays:
        delays = [60.0, 180.0, 420.0]
    return delays


AUTO_PAY_DELAYS = parse_delay_list(AUTO_PAY_CHECK_DELAYS_SEC)


def check_rate_limit(user_id: int) -> Tuple[bool, str]:
    now = time.monotonic()
    last = user_last_request_ts.get(user_id, 0.0)
    if RATE_MIN_INTERVAL_SEC > 0 and now - last < RATE_MIN_INTERVAL_SEC:
        wait_sec = max(RATE_MIN_INTERVAL_SEC - (now - last), 0.0)
        return False, f"Слишком часто. Подождите {wait_sec:.1f} сек."

    dq = user_minute_events[user_id]
    while dq and now - dq[0] > 60:
        dq.popleft()
    if RATE_MAX_PER_MINUTE > 0 and len(dq) >= RATE_MAX_PER_MINUTE:
        return False, f"Лимит скорости: не более {RATE_MAX_PER_MINUTE} запросов в минуту."

    dq.append(now)
    user_last_request_ts[user_id] = now
    return True, ""


def _on_background_task_done(task: asyncio.Task) -> None:
    background_tasks.discard(task)
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    if exc is not None:
        logger.exception("Background task failed: %s", exc)


def start_background_task(coro: Any) -> None:
    task = asyncio.create_task(coro)
    background_tasks.add(task)
    task.add_done_callback(_on_background_task_done)


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=max(SQLITE_BUSY_TIMEOUT_MS / 1000.0, 5.0))
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = db_connect()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                plan_key TEXT NOT NULL,
                pro_paid INTEGER NOT NULL DEFAULT 0,
                plan_started_at TEXT NOT NULL,
                plan_expires_at TEXT NOT NULL,
                month_messages_used INTEGER NOT NULL DEFAULT 0,
                month_images_used INTEGER NOT NULL DEFAULT 0,
                day_key TEXT NOT NULL,
                month_key TEXT NOT NULL DEFAULT '',
                day_messages_used INTEGER NOT NULL DEFAULT 0,
                day_images_used INTEGER NOT NULL DEFAULT 0,
                extra_messages INTEGER NOT NULL DEFAULT 0,
                extra_images INTEGER NOT NULL DEFAULT 0,
                mode TEXT NOT NULL DEFAULT 'normal',
                pending_image_action TEXT NOT NULL DEFAULT '',
                pending_faq_intent TEXT NOT NULL DEFAULT '',
                last_prompt TEXT NOT NULL DEFAULT '',
                last_response TEXT NOT NULL DEFAULT '',
                last_model TEXT NOT NULL DEFAULT '',
                last_exchange_at TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plan_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                event_at TEXT NOT NULL,
                plan_key TEXT NOT NULL,
                period_days INTEGER NOT NULL DEFAULT 0,
                plan_started_at TEXT NOT NULL DEFAULT '',
                plan_expires_at TEXT NOT NULL DEFAULT '',
                amount_rub INTEGER NOT NULL DEFAULT 0,
                payment_ref TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payment_ui_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                deleted INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS yk_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                amount_rub INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                confirmation_url TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                paid_at TEXT NOT NULL DEFAULT '',
                processed INTEGER NOT NULL DEFAULT 0,
                raw_json TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_plan_events_user_id ON plan_events(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_plan_events_event_at ON plan_events(event_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_yk_payments_user_id ON yk_payments(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_yk_payments_status ON yk_payments(status)"
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversation_messages_user_id
            ON conversation_messages(user_id, id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_payment_ui_messages_user
            ON payment_ui_messages(user_id, deleted)
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO app_settings(key, value)
            VALUES (?, ?)
            """,
            (PRO_PRICE_SETTING_KEY, str(PRO_PRICE_RUB)),
        )
        columns = {
            col["name"]
            for col in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "last_exchange_at" not in columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN last_exchange_at TEXT NOT NULL DEFAULT ''"
            )
        if "day_images_used" not in columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN day_images_used INTEGER NOT NULL DEFAULT 0"
            )
        if "month_key" not in columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN month_key TEXT NOT NULL DEFAULT ''"
            )
            now = utc_now()
            conn.execute(
                "UPDATE users SET month_key = ? WHERE month_key = ''",
                (msk_month_key(now),),
            )
        if "pro_paid" not in columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN pro_paid INTEGER NOT NULL DEFAULT 0"
            )
        if "pending_faq_intent" not in columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN pending_faq_intent TEXT NOT NULL DEFAULT ''"
            )
        conn.commit()
    finally:
        conn.close()


def get_setting_value(key: str, default: str = "") -> str:
    conn = db_connect()
    try:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return default
        return str(row["value"])
    finally:
        conn.close()


def set_setting_value(key: str, value: str) -> None:
    conn = db_connect()
    try:
        conn.execute(
            """
            INSERT INTO app_settings(key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def get_pro_price_rub() -> int:
    raw = get_setting_value(PRO_PRICE_SETTING_KEY, str(PRO_PRICE_RUB)).strip()
    try:
        value = int(raw)
    except ValueError:
        return PRO_PRICE_RUB
    if value <= 0:
        return PRO_PRICE_RUB
    return value


def build_welcome_text(row: sqlite3.Row) -> str:
    free = PLANS["free"]
    if plan_for_row(row).key == "pro":
        pro = PLANS["pro"]
        return (
            "✨ Привет! Я Askora AI.\n\n"
            "Что умею:\n"
            "🧠 отвечать и объяснять\n"
            "✍️ тексты: написать/улучшить\n"
            "💻 код: подсказать/починить\n"
            "🎨 изображения: создать по описанию\n\n"
            f"⭐ Pro: {pro.message_daily_limit} сообщений/день + {pro.image_limit} изображений/месяц.\n"
            "Пиши запрос 👇"
        )
    return (
        "✨ Привет! Я Askora AI.\n\n"
        "Что умею:\n"
        "🧠 отвечать и объяснять\n"
        "✍️ тексты: написать/улучшить\n"
        "💻 код: подсказать/починить\n"
        "🎨 изображения: создать по описанию\n\n"
        f"Free: {free.message_daily_limit} сообщений + {free.image_limit} изображение/день.\n"
        "Пиши запрос 👇"
    )


def add_payment_ui_message(user_id: int, chat_id: int, message_id: int) -> None:
    conn = db_connect()
    try:
        conn.execute(
            """
            INSERT INTO payment_ui_messages(user_id, chat_id, message_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, chat_id, message_id, utc_now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_pending_payment_ui_messages(user_id: int, limit: int = 100) -> list[sqlite3.Row]:
    conn = db_connect()
    try:
        rows = conn.execute(
            """
            SELECT id, chat_id, message_id
            FROM payment_ui_messages
            WHERE user_id = ? AND deleted = 0
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return list(rows)
    finally:
        conn.close()


def mark_payment_ui_messages_deleted(ids: list[int]) -> None:
    if not ids:
        return
    conn = db_connect()
    try:
        conn.executemany(
            "UPDATE payment_ui_messages SET deleted = 1 WHERE id = ?",
            [(i,) for i in ids],
        )
        conn.commit()
    finally:
        conn.close()


async def send_payment_message(
    target_message: Message,
    user_id: int,
    text: str,
    **kwargs: Any,
) -> Message:
    sent = await target_message.answer(text, **kwargs)
    add_payment_ui_message(user_id, sent.chat.id, sent.message_id)
    return sent


async def clear_payment_ui_messages(bot: Bot, user_id: int) -> None:
    rows = get_pending_payment_ui_messages(user_id)
    if not rows:
        return
    deleted_ids: list[int] = []
    for row in rows:
        msg_id = int(row["message_id"])
        chat_id = int(row["chat_id"])
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass
        deleted_ids.append(int(row["id"]))
    mark_payment_ui_messages_deleted(deleted_ids)


async def clear_recent_chat_messages(
    bot: Bot,
    chat_id: int,
    anchor_message_id: int,
    window: int,
) -> None:
    if anchor_message_id <= 0 or window <= 0:
        return
    first_message_id = max(anchor_message_id - window + 1, 1)
    for msg_id in range(anchor_message_id, first_message_id - 1, -1):
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            continue


async def cleanup_after_paid_activation(
    bot: Bot,
    user_id: int,
    chat_id: int,
    anchor_message_id: Optional[int] = None,
) -> None:
    rows = get_pending_payment_ui_messages(user_id, limit=300)
    tracked_ids = [int(r["id"]) for r in rows]
    candidate_message_ids = [int(r["message_id"]) for r in rows]
    if anchor_message_id and anchor_message_id > 0:
        candidate_message_ids.append(int(anchor_message_id))

    if candidate_message_ids and PAYMENT_CLEANUP_WINDOW > 0:
        anchor = max(candidate_message_ids)
        await clear_recent_chat_messages(bot, chat_id, anchor, PAYMENT_CLEANUP_WINDOW)
    else:
        await clear_payment_ui_messages(bot, user_id)

    if tracked_ids:
        mark_payment_ui_messages_deleted(tracked_ids)


async def send_home_welcome(bot: Bot, chat_id: int, user_id: int) -> None:
    row = reset_periods_if_needed(user_id)
    set_start_defaults(user_id)
    welcome_text = build_welcome_text(row)
    welcome_kb = build_home_keyboard(row)

    if WELCOME_VIDEO_PATH:
        try:
            await bot.send_video(
                chat_id=chat_id,
                video=FSInputFile(WELCOME_VIDEO_PATH),
                caption=welcome_text,
                reply_markup=welcome_kb,
            )
            return
        except Exception as exc:
            logger.warning("Failed to send welcome video: %s", exc)

    await bot.send_message(chat_id, welcome_text, reply_markup=welcome_kb)


def ensure_user(user_id: int) -> None:
    now = utc_now()
    day_key = msk_day_key(now)
    month_key = msk_month_key(now)
    started = now.isoformat()
    expires = (now + timedelta(days=30)).isoformat()
    conn = db_connect()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO users
            (user_id, plan_key, plan_started_at, plan_expires_at, day_key, month_key, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, DEFAULT_PLAN_KEY, started, expires, day_key, month_key, started),
        )
        conn.commit()
    finally:
        conn.close()


def get_user(user_id: int) -> sqlite3.Row:
    ensure_user(user_id)
    conn = db_connect()
    try:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            raise RuntimeError("User record missing after ensure_user.")
        return row
    finally:
        conn.close()


def reset_periods_if_needed(user_id: int) -> sqlite3.Row:
    now = utc_now()
    today = msk_day_key(now)
    current_month = msk_month_key(now)
    conn = db_connect()
    try:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            ensure_user(user_id)
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        changed = False

        plan_expires_at = datetime.fromisoformat(row["plan_expires_at"])
        if now >= plan_expires_at:
            new_started = now.isoformat()
            current_plan = plan_for_row(row).key
            next_plan = "free" if current_plan == "pro" else current_plan
            new_expires = (now + timedelta(days=PRO_DAYS)).isoformat()
            new_day_key = msk_day_key(now)
            new_month_key = msk_month_key(now)
            conn.execute(
                """
                UPDATE users
                SET plan_key = ?,
                    plan_started_at = ?,
                    plan_expires_at = ?,
                    day_key = ?,
                    month_key = ?,
                    day_messages_used = 0,
                    day_images_used = 0,
                    month_messages_used = 0,
                    month_images_used = 0
                WHERE user_id = ?
                """,
                (next_plan, new_started, new_expires, new_day_key, new_month_key, user_id),
            )
            if current_plan == "pro" and next_plan == "free":
                updated_row = conn.execute(
                    "SELECT plan_key, plan_started_at, plan_expires_at FROM users WHERE user_id = ?",
                    (user_id,),
                ).fetchone()
                if updated_row is not None:
                    log_plan_event(
                        conn,
                        user_id,
                        "pro_expired_to_free",
                        "auto_expire",
                        updated_row,
                        note="Pro period ended automatically.",
                    )
            changed = True

        if row["day_key"] != today:
            conn.execute(
                "UPDATE users SET day_key = ?, day_messages_used = 0, day_images_used = 0 WHERE user_id = ?",
                (today, user_id),
            )
            changed = True

        row_month_key = str(row["month_key"] or "")
        if row_month_key != current_month:
            conn.execute(
                "UPDATE users SET month_key = ?, month_messages_used = 0, month_images_used = 0 WHERE user_id = ?",
                (current_month, user_id),
            )
            changed = True

        if changed:
            conn.commit()
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row
    finally:
        conn.close()


def plan_for_row(row: sqlite3.Row) -> Plan:
    plan_key = row["plan_key"]
    legacy_map = {"start": "free", "max": "free"}
    plan_key = legacy_map.get(plan_key, plan_key)
    return PLANS.get(plan_key, PLANS[DEFAULT_PLAN_KEY])


def is_complex_question(text: str) -> bool:
    low = text.lower()
    keywords = [
        "analyze",
        "compare",
        "architecture",
        "algorithm",
        "why",
        "explain step by step",
        "optimize",
        "debug",
        "design",
        "security",
    ]
    if len(text) >= 240:
        return True
    return any(word in low for word in keywords)


def monthly_message_left(row: sqlite3.Row) -> int:
    plan = plan_for_row(row)
    return max(plan.message_daily_limit - row["day_messages_used"], 0)


def monthly_image_left(row: sqlite3.Row) -> int:
    plan = plan_for_row(row)
    if plan.image_period == "month":
        return max(plan.image_limit - row["month_images_used"], 0)
    return max(plan.image_limit - row["day_images_used"], 0)


def daily_message_limit(row: sqlite3.Row) -> int:
    plan = plan_for_row(row)
    return min(plan.message_daily_limit, DAILY_HARD_LIMIT)


def consume_text_quota(user_id: int) -> Tuple[bool, str]:
    row = reset_periods_if_needed(user_id)
    plan = plan_for_row(row)

    conn = db_connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            """
            UPDATE users
            SET day_messages_used = day_messages_used + 1
            WHERE user_id = ? AND day_messages_used < ?
            """,
            (user_id, plan.message_daily_limit),
        )
        if cur.rowcount != 1:
            conn.rollback()
            return False, f"Лимит {plan.title}: {plan.message_daily_limit} сообщений в день."
        conn.commit()
        return True, ""
    finally:
        conn.close()


def consume_image_quota(user_id: int) -> Tuple[bool, str]:
    row = reset_periods_if_needed(user_id)
    plan = plan_for_row(row)

    conn = db_connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if plan.image_period == "month":
            cur = conn.execute(
                """
                UPDATE users
                SET month_images_used = month_images_used + 1
                WHERE user_id = ? AND month_images_used < ?
                """,
                (user_id, plan.image_limit),
            )
            if cur.rowcount != 1:
                conn.rollback()
                return False, f"Лимит {plan.title}: {plan.image_limit} изображений в месяц."
        else:
            cur = conn.execute(
                """
                UPDATE users
                SET day_images_used = day_images_used + 1
                WHERE user_id = ? AND day_images_used < ?
                """,
                (user_id, plan.image_limit),
            )
            if cur.rowcount != 1:
                conn.rollback()
                if plan.image_limit == 1:
                    return False, f"Лимит {plan.title}: 1 изображение в день."
                return False, f"Лимит {plan.title}: {plan.image_limit} изображений в день."
        conn.commit()
        return True, ""
    finally:
        conn.close()


def set_user_mode(user_id: int, mode: str) -> None:
    conn = db_connect()
    try:
        conn.execute("UPDATE users SET mode = ? WHERE user_id = ?", (mode, user_id))
        conn.commit()
    finally:
        conn.close()


def set_pending_image_action(user_id: int, action: str) -> None:
    conn = db_connect()
    try:
        conn.execute(
            "UPDATE users SET pending_image_action = ?, pending_faq_intent = '' WHERE user_id = ?",
            (action, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_pending_faq_intent(user_id: int, intent: str) -> None:
    conn = db_connect()
    try:
        conn.execute(
            "UPDATE users SET pending_faq_intent = ?, pending_image_action = '' WHERE user_id = ?",
            (intent, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_start_defaults(user_id: int) -> None:
    conn = db_connect()
    try:
        conn.execute(
            """
            UPDATE users
            SET mode = 'normal',
                pending_image_action = '',
                pending_faq_intent = ''
            WHERE user_id = ?
            """,
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


def get_user_lock(user_id: int) -> asyncio.Lock:
    lock = user_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        user_locks[user_id] = lock
    return lock


def parse_iso_ts(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def save_last_exchange(user_id: int, prompt: str, response: str, model: str) -> None:
    now = utc_now().isoformat()
    conn = db_connect()
    try:
        conn.execute(
            """
            UPDATE users
            SET last_prompt = ?, last_response = ?, last_model = ?, last_exchange_at = ?
            WHERE user_id = ?
            """,
            (prompt, response, model, now, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def clear_user_history(user_id: int) -> None:
    conn = db_connect()
    try:
        conn.execute("DELETE FROM conversation_messages WHERE user_id = ?", (user_id,))
        conn.execute(
            """
            UPDATE users
            SET last_prompt = '',
                last_response = '',
                last_model = '',
                last_exchange_at = ''
            WHERE user_id = ?
            """,
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


def refund_text_quota(user_id: int) -> None:
    conn = db_connect()
    try:
        conn.execute(
            """
            UPDATE users
            SET day_messages_used = CASE
                WHEN day_messages_used > 0 THEN day_messages_used - 1
                ELSE 0
            END
            WHERE user_id = ?
            """,
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


def refund_image_quota(user_id: int, image_period: str) -> None:
    column = "month_images_used" if image_period == "month" else "day_images_used"
    conn = db_connect()
    try:
        conn.execute(
            f"""
            UPDATE users
            SET {column} = CASE
                WHEN {column} > 0 THEN {column} - 1
                ELSE 0
            END
            WHERE user_id = ?
            """,
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _truncate_context_text(text: str) -> str:
    normalized = _normalize_spaces(text)
    if len(normalized) <= PRO_CONTEXT_MAX_CHARS:
        return normalized
    return normalized[:PRO_CONTEXT_MAX_CHARS].rstrip() + "..."


def add_conversation_message(user_id: int, role: str, content: str) -> None:
    role = role.strip().lower()
    if role not in {"user", "assistant"}:
        return
    clean_content = _truncate_context_text(content)
    if not clean_content:
        return
    conn = db_connect()
    try:
        conn.execute(
            """
            INSERT INTO conversation_messages(user_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, role, clean_content, utc_now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def trim_conversation_history(user_id: int, keep_limit: int) -> None:
    if keep_limit <= 0:
        conn = db_connect()
        try:
            conn.execute("DELETE FROM conversation_messages WHERE user_id = ?", (user_id,))
            conn.commit()
        finally:
            conn.close()
        return

    conn = db_connect()
    try:
        conn.execute(
            """
            DELETE FROM conversation_messages
            WHERE user_id = ?
              AND id NOT IN (
                SELECT id
                FROM conversation_messages
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
              )
            """,
            (user_id, user_id, keep_limit),
        )
        conn.commit()
    finally:
        conn.close()


def get_recent_conversation_messages(user_id: int, limit: int) -> list[dict[str, str]]:
    if limit <= 0:
        return []
    conn = db_connect()
    try:
        rows = conn.execute(
            """
            SELECT role, content
            FROM conversation_messages
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()

    messages: list[dict[str, str]] = []
    for row in reversed(rows):
        role = str(row["role"]).strip().lower()
        content = str(row["content"]).strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    return messages


def build_pro_context_messages(user_id: int, user_text: str) -> list[dict[str, str]]:
    if PRO_CONTEXT_MESSAGES <= 0:
        return [{"role": "user", "content": user_text}]
    history = get_recent_conversation_messages(user_id, PRO_CONTEXT_MESSAGES)
    history.append({"role": "user", "content": _truncate_context_text(user_text)})
    return history


def save_pro_conversation_turn(user_id: int, user_text: str, assistant_text: str) -> None:
    add_conversation_message(user_id, "user", user_text)
    add_conversation_message(user_id, "assistant", assistant_text)
    trim_conversation_history(user_id, max(PRO_CONTEXT_MESSAGES * 4, 40))


def _clean_slot_text(value: str) -> str:
    cleaned = value.strip().strip(".,:;!?")
    cleaned = re.sub(r"^[\-\u2014]+", "", cleaned).strip()
    return _normalize_spaces(cleaned)


def _currency_code_from_token(token: str) -> Optional[str]:
    raw = token.strip().lower().replace("ё", "е")
    raw = raw.strip(".,:;!?()[]{}\"'`")
    if not raw:
        return None
    alias = CURRENCY_ALIASES.get(raw)
    if alias:
        return alias
    if re.fullmatch(r"[a-z]{3}", raw):
        return raw.upper()
    return None


def _is_generic_news_query(value: str) -> bool:
    low = _normalize_spaces(value.lower().replace("ё", "е"))
    generic_values = {
        "",
        "новости",
        "последние новости",
        "главные новости",
        "свежие новости",
        "сегодня",
        "на сегодня",
        "сейчас",
        "сегодняшние новости",
    }
    return low in generic_values


def detect_faq_intent(text: str) -> Optional[str]:
    low = text.lower().replace("ё", "е")
    has_fx_pair = bool(re.search(r"\b[a-z]{3}\s*(?:/|к|в|to)\s*[a-z]{3}\b", low))
    has_currency_word = any(key in low for key in CURRENCY_ALIASES.keys())
    has_fx_word = any(word in low for word in ("курс", "валют", "конверт", "сколько стоит"))
    news_patterns = (
        r"^\s*(?:последние|главные|свежие)\s+новост\w*",
        r"^\s*новост\w*(?:\s|$)",
        r"\bчто\s+нового\b",
        r"\bновост\w*\s+на\s+сегодня\b",
    )
    has_news_request = any(re.search(pattern, low) for pattern in news_patterns)
    weather_patterns = (
        r"^\s*(?:погода|погоду|погоде|температура)\b",
        r"\b(?:погода|погоду|погоде|температура)\s*(?:в|во|на)\s+[a-zа-я]",
        r"^\s*(?:какая|какой|какую|как(?:ая)?|что\s+с)\s+(?:сегодня\s+|сейчас\s+)?(?:погода|температура)\b",
        r"\bсколько\s+градус\w*\b",
    )
    has_weather_request = any(re.search(pattern, low) for pattern in weather_patterns)

    if has_news_request:
        return FAQ_INTENT_NEWS
    if has_weather_request:
        return FAQ_INTENT_WEATHER
    if has_fx_pair or (has_currency_word and has_fx_word):
        return FAQ_INTENT_FX
    if any(word in low for word in ("сколько времени", "который час", "время в", "время во")):
        return FAQ_INTENT_TIME
    if any(
        word in low
        for word in ("адрес", "координат", "где находится", "найди на карте", "найди адрес")
    ):
        return FAQ_INTENT_ADDRESS
    return None


def extract_news_query(text: str, from_pending: bool = False) -> str:
    if from_pending:
        return _clean_slot_text(text)

    cleaned = _clean_slot_text(text)
    patterns = [
        r"(?:новост\w*|что нового)\s*(?:про|о|об|по)\s+(.+)$",
        r"^\s*(?:новост\w*)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            query = _clean_slot_text(match.group(1))
            if query and not _is_generic_news_query(query):
                return query

    if _is_generic_news_query(cleaned):
        return FAQ_NEWS_DEFAULT_QUERY or "главные новости"

    if "новост" in cleaned.lower().replace("ё", "е") or "что нового" in cleaned.lower().replace("ё", "е"):
        return FAQ_NEWS_DEFAULT_QUERY or "главные новости"
    return ""


def extract_weather_city(text: str, from_pending: bool = False) -> str:
    if from_pending:
        return _clean_slot_text(text)
    patterns = [
        r"(?:погода|погоду|погоде|температура)\s*(?:в|во|на)\s+(.+)$",
        r"^\s*(?:погода|погоду|погоде|температура)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            city = _clean_slot_text(match.group(1))
            if city:
                return city
    if FAQ_DEFAULT_CITY and ("погод" in text.lower() or "температур" in text.lower()):
        return FAQ_DEFAULT_CITY
    return ""


def _looks_like_city_query(value: str) -> bool:
    normalized = _normalize_city_query(value)
    return bool(re.search(r"[A-Za-zА-Яа-яЁё]", normalized))


def _normalize_city_query(text: str) -> str:
    city = _clean_slot_text(text)
    city = re.sub(r"^(?:в|во|на)\s+", "", city, flags=re.IGNORECASE).strip()
    city = re.sub(r"\b(?:сегодня|сейчас|пожалуйста)\b", "", city, flags=re.IGNORECASE).strip()
    return _normalize_spaces(city)


def _append_city_candidate(candidates: list[str], value: str) -> None:
    clean = _normalize_spaces(value.strip())
    if clean and clean not in candidates:
        candidates.append(clean)


def _city_lookup_candidates(city: str) -> list[str]:
    normalized = _normalize_city_query(city)
    if not normalized:
        return []

    candidates: list[str] = []
    _append_city_candidate(candidates, normalized)

    words = normalized.split()
    if not words:
        return candidates

    last = words[-1]
    lower_last = last.lower()

    def with_last(new_last: str) -> str:
        return " ".join(words[:-1] + [new_last]).strip()

    if len(last) >= 3:
        if lower_last.endswith("е"):
            _append_city_candidate(candidates, with_last(last[:-1]))
            _append_city_candidate(candidates, with_last(last[:-1] + "а"))
        if lower_last.endswith("и"):
            _append_city_candidate(candidates, with_last(last[:-1]))
            _append_city_candidate(candidates, with_last(last[:-1] + "ь"))
            _append_city_candidate(candidates, with_last(last[:-1] + "я"))
        if lower_last.endswith("у"):
            _append_city_candidate(candidates, with_last(last[:-1] + "а"))
        if lower_last.endswith("ю"):
            _append_city_candidate(candidates, with_last(last[:-1] + "я"))
        if lower_last.endswith("ом") or lower_last.endswith("ем"):
            _append_city_candidate(candidates, with_last(last[:-2]))
            _append_city_candidate(candidates, with_last(last[:-2] + "а"))

    return candidates


def _geocode_city_open_meteo(city_query: str) -> tuple[bool, str, dict[str, Any]]:
    try:
        response = get_http_session().get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city_query, "count": 1, "language": "ru", "format": "json"},
            timeout=(XAI_CONNECT_TIMEOUT_SEC, XAI_READ_TIMEOUT_SEC),
        )
    except requests.RequestException as exc:
        return False, f"Сервис геокодирования недоступен: {exc}", {}
    if response.status_code >= 400:
        return False, f"Геокодирование недоступно (HTTP {response.status_code}).", {}
    try:
        data = response.json()
    except ValueError:
        return False, "Геокодирование вернуло некорректный ответ.", {}
    results = data.get("results") or []
    if not results:
        return False, "", {}
    first = results[0]
    if not isinstance(first, dict):
        return False, "Не удалось прочитать данные города.", {}
    return True, "", first


def extract_time_city(text: str, from_pending: bool = False) -> str:
    if from_pending:
        return _clean_slot_text(text)
    patterns = [
        r"(?:сколько времени|который час|время)\s*(?:в|во|на)\s+(.+)$",
        r"(?:время)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            city = _clean_slot_text(match.group(1))
            if city:
                return city
    if FAQ_DEFAULT_CITY and "время" in text.lower():
        return FAQ_DEFAULT_CITY
    return ""


def extract_address_query(text: str, from_pending: bool = False) -> str:
    if from_pending:
        return _clean_slot_text(text)
    patterns = [
        r"(?:адрес|координаты)\s+(.+)$",
        r"(?:где находится|найди адрес|найди на карте)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            query = _clean_slot_text(match.group(1))
            if query:
                return query
    return ""


def extract_fx_pair(text: str) -> Optional[tuple[str, str]]:
    match = re.search(r"\b([A-Za-z]{3})\s*(?:/|к|в|to)\s*([A-Za-z]{3})\b", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).upper(), match.group(2).upper()

    tokens = re.findall(r"[A-Za-zА-Яа-яЁё₽]+", text)
    codes: list[str] = []
    for token in tokens:
        code = _currency_code_from_token(token)
        if code and code not in codes:
            codes.append(code)
    if len(codes) >= 2:
        return codes[0], codes[1]
    if len(codes) == 1:
        base = codes[0]
        quote = "RUB" if base != "RUB" else "USD"
        return base, quote
    return None


def parse_faq_request(intent: str, text: str, from_pending: bool = False) -> tuple[bool, dict[str, str], str]:
    if intent == FAQ_INTENT_NEWS:
        query = extract_news_query(text, from_pending=from_pending)
        if not query:
            query = FAQ_NEWS_DEFAULT_QUERY or "главные новости"
        return True, {"query": _normalize_spaces(query)[:120]}, ""

    if intent == FAQ_INTENT_WEATHER:
        city = extract_weather_city(text, from_pending=from_pending)
        if not city or not _looks_like_city_query(city):
            return False, {}, "Укажите город для погоды.\nПример: «Погода в Москве»."
        return True, {"city": city}, ""

    if intent == FAQ_INTENT_FX:
        pair = extract_fx_pair(text)
        if not pair:
            return (
                False,
                {},
                "Укажите валютную пару.\nПример: «USD/RUB» или «курс доллара к рублю».",
            )
        base, quote = pair
        return True, {"base": base, "quote": quote}, ""

    if intent == FAQ_INTENT_TIME:
        city = extract_time_city(text, from_pending=from_pending)
        if not city:
            return False, {}, "Укажите город для времени.\nПример: «Время в Токио»."
        return True, {"city": city}, ""

    if intent == FAQ_INTENT_ADDRESS:
        query = extract_address_query(text, from_pending=from_pending)
        if not query:
            return False, {}, "Уточните адрес или место.\nПример: «Адрес Красной площади»."
        return True, {"query": query}, ""

    return False, {}, ""


def geocode_city(city: str) -> tuple[bool, str, dict[str, Any]]:
    candidates = _city_lookup_candidates(city)
    if not candidates:
        return False, "Укажите город.", {}

    last_error = ""
    for candidate in candidates:
        ok, err, payload = _geocode_city_open_meteo(candidate)
        if ok:
            return True, "", payload
        if err:
            last_error = err

    if last_error:
        return False, last_error, {}
    return False, "Не нашел такой город. Уточните название.", {}


def faq_weather(city: str) -> tuple[bool, str]:
    ok_geo, geo_err, geo = geocode_city(city)
    if not ok_geo:
        return False, geo_err

    lat = geo.get("latitude")
    lon = geo.get("longitude")
    if lat is None or lon is None:
        return False, "Не удалось получить координаты города."

    name = str(geo.get("name", city)).strip() or city
    country = str(geo.get("country", "")).strip()
    label = f"{name}, {country}" if country else name

    try:
        response = get_http_session().get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": "true",
                "timezone": "auto",
            },
            timeout=(XAI_CONNECT_TIMEOUT_SEC, XAI_READ_TIMEOUT_SEC),
        )
    except requests.RequestException as exc:
        return False, f"Сервис погоды недоступен: {exc}"
    if response.status_code >= 400:
        return False, f"Сервис погоды недоступен (HTTP {response.status_code})."
    try:
        data = response.json()
    except ValueError:
        return False, "Сервис погоды вернул некорректный ответ."

    current = data.get("current_weather") or {}
    temperature = current.get("temperature")
    windspeed = current.get("windspeed")
    weather_code_raw = current.get("weathercode")
    weather_time = str(current.get("time", "")).strip()

    if temperature is None or windspeed is None:
        return False, f"Не удалось получить текущую погоду для {label}."
    try:
        weather_code = int(weather_code_raw) if weather_code_raw is not None else -1
    except (TypeError, ValueError):
        weather_code = -1
    weather_desc = WEATHER_CODE_MAP.get(weather_code, "без уточнения")

    parts = [
        f"🌤 Погода в {label}: {float(temperature):+.1f}°C, {weather_desc}.",
        f"Ветер: {float(windspeed):.1f} м/с.",
    ]
    if weather_time:
        parts.append(f"Обновлено: {weather_time}.")
    return True, " ".join(parts)


def faq_time(city: str) -> tuple[bool, str]:
    ok_geo, geo_err, geo = geocode_city(city)
    if not ok_geo:
        return False, geo_err

    tz_name = str(geo.get("timezone", "")).strip()
    city_name = str(geo.get("name", city)).strip() or city
    country = str(geo.get("country", "")).strip()
    label = f"{city_name}, {country}" if country else city_name

    if not tz_name:
        now = utc_now().astimezone(MSK_TZ)
        return True, f"🕒 Время в {label}: {now.strftime('%H:%M')}, {now.strftime('%d.%m.%Y')} (МСК)."
    try:
        now = datetime.now(ZoneInfo(tz_name))
    except ZoneInfoNotFoundError:
        now = utc_now().astimezone(MSK_TZ)
        return True, f"🕒 Время в {label}: {now.strftime('%H:%M')}, {now.strftime('%d.%m.%Y')} (МСК)."
    return True, f"🕒 Время в {label}: {now.strftime('%H:%M')}, {now.strftime('%d.%m.%Y')} ({tz_name})."


def faq_fx(base: str, quote: str) -> tuple[bool, str]:
    base_code = base.strip().upper()
    quote_code = quote.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", base_code) or not re.fullmatch(r"[A-Z]{3}", quote_code):
        return False, "Некорректный код валюты. Используйте формат вроде USD/RUB."

    try:
        response = get_http_session().get(
            f"https://open.er-api.com/v6/latest/{base_code}",
            timeout=(XAI_CONNECT_TIMEOUT_SEC, XAI_READ_TIMEOUT_SEC),
        )
    except requests.RequestException as exc:
        return False, f"Сервис курсов недоступен: {exc}"
    if response.status_code >= 400:
        return False, f"Сервис курсов недоступен (HTTP {response.status_code})."

    try:
        data = response.json()
    except ValueError:
        return False, "Сервис курсов вернул некорректный ответ."

    if str(data.get("result", "")).lower() != "success":
        return False, "Не удалось получить курс валют для этой пары."
    rates = data.get("rates") or {}
    if quote_code not in rates:
        return False, f"Валюта {quote_code} не найдена в ответе сервиса."

    try:
        rate = float(rates[quote_code])
    except (TypeError, ValueError):
        return False, "Не удалось прочитать курс из ответа сервиса."

    update_ts = data.get("time_last_update_unix")
    if isinstance(update_ts, (int, float)):
        updated_dt = datetime.fromtimestamp(float(update_ts), tz=timezone.utc).astimezone(MSK_TZ)
        updated_str = updated_dt.strftime("%d.%m.%Y %H:%M МСК")
    else:
        updated_str = "время обновления неизвестно"

    return True, f"💱 Курс {base_code}/{quote_code}: {rate:.4f}. Обновлено: {updated_str}."


def faq_address(query: str) -> tuple[bool, str]:
    try:
        response = get_http_session().get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": query,
                "format": "jsonv2",
                "limit": 1,
                "addressdetails": 1,
                "accept-language": "ru",
            },
            headers={"User-Agent": FAQ_ADDRESS_USER_AGENT},
            timeout=(XAI_CONNECT_TIMEOUT_SEC, XAI_READ_TIMEOUT_SEC),
        )
    except requests.RequestException as exc:
        return False, f"Сервис адресов недоступен: {exc}"
    if response.status_code >= 400:
        return False, f"Сервис адресов недоступен (HTTP {response.status_code})."

    try:
        data = response.json()
    except ValueError:
        return False, "Сервис адресов вернул некорректный ответ."
    if not isinstance(data, list) or not data:
        return False, "Не нашел такой адрес/место. Уточните запрос."

    first = data[0]
    display_name = str(first.get("display_name", "")).strip()
    lat = str(first.get("lat", "")).strip()
    lon = str(first.get("lon", "")).strip()
    if not display_name:
        return False, "Адрес найден, но не удалось прочитать описание."
    if lat and lon:
        return True, f"📍 {display_name}\nКоординаты: {lat}, {lon}"
    return True, f"📍 {display_name}"


def _format_news_pub_date(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        return raw
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MSK_TZ).strftime("%d.%m.%Y %H:%M МСК")


def faq_news(query: str) -> tuple[bool, str]:
    normalized_query = _normalize_spaces(query.strip())
    if not normalized_query:
        normalized_query = FAQ_NEWS_DEFAULT_QUERY or "главные новости"

    if _is_generic_news_query(normalized_query):
        rss_url = "https://news.google.com/rss?hl=ru&gl=RU&ceid=RU:ru"
    else:
        encoded_query = quote_plus(normalized_query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ru&gl=RU&ceid=RU:ru"

    try:
        response = get_http_session().get(
            rss_url,
            headers={"User-Agent": FAQ_ADDRESS_USER_AGENT},
            timeout=(XAI_CONNECT_TIMEOUT_SEC, XAI_READ_TIMEOUT_SEC),
        )
    except requests.RequestException as exc:
        return False, f"Сервис новостей недоступен: {exc}"
    if response.status_code >= 400:
        return False, f"Сервис новостей недоступен (HTTP {response.status_code})."

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError:
        return False, "Сервис новостей вернул некорректный ответ."

    items = root.findall(".//item")
    if not items:
        return False, "Не нашел свежих новостей по этой теме. Попробуйте другой запрос."

    lines: list[str] = []
    shown = 0
    for item in items:
        if shown >= FAQ_NEWS_ITEMS_LIMIT:
            break
        title_raw = str(item.findtext("title", "")).strip()
        title = _normalize_spaces(html.unescape(title_raw))
        if not title:
            continue
        source = _normalize_spaces(html.unescape(str(item.findtext("source", "")).strip()))
        pub_date = _format_news_pub_date(str(item.findtext("pubDate", "")).strip())
        link = str(item.findtext("link", "")).strip()

        shown += 1
        line = f"{shown}. {title}"
        meta_parts: list[str] = []
        if source:
            meta_parts.append(source)
        if pub_date:
            meta_parts.append(pub_date)
        if meta_parts:
            line += f" ({', '.join(meta_parts)})"
        if link:
            line += f"\n{link}"
        lines.append(line)

    if not lines:
        return False, "Не удалось прочитать новости из ответа сервиса."

    stamp = utc_now().astimezone(MSK_TZ).strftime("%d.%m.%Y %H:%M МСК")
    return True, f"📰 Актуальные новости (обновлено: {stamp}):\n" + "\n".join(lines)


def run_faq_intent(intent: str, payload: dict[str, str]) -> tuple[bool, str]:
    if intent == FAQ_INTENT_NEWS:
        return faq_news(payload.get("query", ""))
    if intent == FAQ_INTENT_WEATHER:
        return faq_weather(payload.get("city", ""))
    if intent == FAQ_INTENT_FX:
        return faq_fx(payload.get("base", ""), payload.get("quote", ""))
    if intent == FAQ_INTENT_TIME:
        return faq_time(payload.get("city", ""))
    if intent == FAQ_INTENT_ADDRESS:
        return faq_address(payload.get("query", ""))
    return False, "Неизвестный FAQ-интент."


def log_plan_event(
    conn: sqlite3.Connection,
    user_id: int,
    event_type: str,
    source: str,
    row: sqlite3.Row,
    amount_rub: int = 0,
    payment_ref: str = "",
    note: str = "",
) -> None:
    period_days = 0
    started = row["plan_started_at"]
    expires = row["plan_expires_at"]
    dt_started = parse_iso_ts(started)
    dt_expires = parse_iso_ts(expires)
    if dt_started is not None and dt_expires is not None:
        period_days = max((dt_expires.date() - dt_started.date()).days, 0)
    conn.execute(
        """
        INSERT INTO plan_events
        (user_id, event_type, source, event_at, plan_key, period_days, plan_started_at, plan_expires_at, amount_rub, payment_ref, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            event_type,
            source,
            utc_now().isoformat(),
            row["plan_key"],
            period_days,
            started,
            expires,
            int(amount_rub),
            payment_ref,
            note,
        ),
    )


def update_plan(
    user_id: int,
    plan_key: str,
    mark_paid: Optional[bool] = None,
    source: str = "system",
    amount_rub: int = 0,
    payment_ref: str = "",
    note: str = "",
) -> Optional[str]:
    if plan_key not in PLANS:
        return "Неизвестный режим."
    now = utc_now()
    conn = db_connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if mark_paid is None:
            conn.execute(
                """
                UPDATE users
                SET plan_key = ?,
                    plan_started_at = ?,
                    plan_expires_at = ?
                WHERE user_id = ?
                """,
                (
                    plan_key,
                    now.isoformat(),
                    (now + timedelta(days=PRO_DAYS)).isoformat(),
                    user_id,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE users
                SET plan_key = ?,
                    pro_paid = ?,
                    plan_started_at = ?,
                    plan_expires_at = ?
                WHERE user_id = ?
                """,
                (
                    plan_key,
                    1 if mark_paid else 0,
                    now.isoformat(),
                    (now + timedelta(days=PRO_DAYS)).isoformat(),
                    user_id,
                ),
            )
        updated_row = conn.execute(
            "SELECT plan_key, plan_started_at, plan_expires_at FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if updated_row is not None:
            if plan_key == "pro":
                if mark_paid is True:
                    event_type = "pro_activated_paid"
                elif mark_paid is False:
                    event_type = "pro_activated_unpaid"
                else:
                    event_type = "pro_activated_manual"
                log_plan_event(
                    conn,
                    user_id,
                    event_type,
                    source,
                    updated_row,
                    amount_rub=amount_rub,
                    payment_ref=payment_ref,
                    note=note,
                )
            elif plan_key == "free":
                log_plan_event(
                    conn,
                    user_id,
                    "plan_set_free",
                    source,
                    updated_row,
                    amount_rub=0,
                    payment_ref=payment_ref,
                    note=note,
                )
        conn.commit()
        return None
    finally:
        conn.close()


def yk_is_configured() -> bool:
    return YK_ENABLED and bool(YK_SHOP_ID) and bool(YK_SHOP_SECRET_KEY)


def yk_auth() -> HTTPBasicAuth:
    return HTTPBasicAuth(YK_SHOP_ID, YK_SHOP_SECRET_KEY)


def yk_request_with_retry(
    method: str,
    url: str,
    *,
    session: Optional[requests.Session] = None,
    **kwargs: Any,
) -> requests.Response:
    timeout = kwargs.pop("timeout", (YK_CONNECT_TIMEOUT_SEC, YK_READ_TIMEOUT_SEC))
    request_fn = session.request if session is not None else requests.request
    last_exc: Optional[Exception] = None
    for attempt in range(YK_NETWORK_RETRIES + 1):
        try:
            return request_fn(method, url, timeout=timeout, **kwargs)
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exc = exc
            if attempt >= YK_NETWORK_RETRIES:
                raise
            api_logger.warning(
                "yk_network_retry method=%s attempt=%s url=%s error=%s",
                method.upper(),
                attempt + 1,
                url,
                str(exc)[:300],
            )
            time.sleep(min(1.5 * (attempt + 1), 3.0))
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("yk_request_with_retry failed unexpectedly")


def amount_value_to_rub(value: str) -> int:
    try:
        return int(Decimal(value))
    except (InvalidOperation, ValueError):
        return 0


def yk_simplepay_shop_id() -> str:
    return YK_SIMPLEPAY_SHOP_ID or YK_SHOP_ID


def yk_simplepay_is_configured() -> bool:
    return YK_ENABLED and bool(yk_simplepay_shop_id()) and bool(YK_SIMPLEPAY_ENDPOINT)


def extract_payment_user_id(payment_data: dict[str, Any]) -> int:
    metadata = payment_data.get("metadata")
    if isinstance(metadata, dict):
        raw = str(metadata.get("user_id", "")).strip()
        if raw:
            try:
                uid = int(raw)
                if uid > 0:
                    return uid
            except ValueError:
                return 0
    return 0


def upsert_yk_payment(user_id: Optional[int], payment_data: dict[str, Any]) -> Optional[str]:
    payment_id = str(payment_data.get("id", "")).strip()
    if not payment_id:
        return None

    amount_value = str(payment_data.get("amount", {}).get("value", "0")).strip()
    amount_rub = amount_value_to_rub(amount_value)
    status = str(payment_data.get("status", "")).strip() or "unknown"
    confirmation_url = str(
        payment_data.get("confirmation", {}).get("confirmation_url", "")
    ).strip()
    created_at = str(payment_data.get("created_at", "")).strip() or utc_now().isoformat()
    paid_at = str(payment_data.get("paid_at", "")).strip()
    raw_json = json.dumps(payment_data, ensure_ascii=False)

    conn = db_connect()
    try:
        requested_user_id = int(user_id or 0)
        metadata_user_id = extract_payment_user_id(payment_data)
        existing = conn.execute(
            "SELECT user_id, processed FROM yk_payments WHERE payment_id = ?",
            (payment_id,),
        ).fetchone()

        if existing is None:
            if metadata_user_id > 0:
                effective_user_id = metadata_user_id
                if requested_user_id > 0 and requested_user_id != metadata_user_id:
                    api_logger.warning(
                        "yk_upsert_owner_mismatch payment_id=%s requested_user_id=%s metadata_user_id=%s",
                        payment_id,
                        requested_user_id,
                        metadata_user_id,
                    )
            else:
                effective_user_id = requested_user_id
            if effective_user_id <= 0:
                api_logger.error(
                    "yk_upsert_skip payment_id=%s reason=no_user_id",
                    payment_id,
                )
                return None
            conn.execute(
                """
                INSERT INTO yk_payments
                (payment_id, user_id, amount_rub, status, confirmation_url, created_at, paid_at, processed, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    payment_id,
                    effective_user_id,
                    amount_rub,
                    status,
                    confirmation_url,
                    created_at,
                    paid_at,
                    raw_json,
                ),
            )
        else:
            try:
                stored_user_id = int(existing["user_id"])
            except (TypeError, ValueError):
                stored_user_id = 0
            if stored_user_id <= 0:
                effective_user_id = metadata_user_id if metadata_user_id > 0 else requested_user_id
            else:
                effective_user_id = stored_user_id
            if metadata_user_id > 0 and effective_user_id > 0 and metadata_user_id != effective_user_id:
                api_logger.warning(
                    "yk_upsert_metadata_conflict payment_id=%s stored_user_id=%s metadata_user_id=%s",
                    payment_id,
                    effective_user_id,
                    metadata_user_id,
                )
            if requested_user_id > 0 and effective_user_id > 0 and requested_user_id != effective_user_id:
                api_logger.warning(
                    "yk_upsert_request_conflict payment_id=%s requested_user_id=%s stored_user_id=%s",
                    payment_id,
                    requested_user_id,
                    effective_user_id,
                )
            conn.execute(
                """
                UPDATE yk_payments
                SET user_id = ?,
                    amount_rub = ?,
                    status = ?,
                    confirmation_url = CASE
                        WHEN confirmation_url = '' THEN ?
                        ELSE confirmation_url
                    END,
                    paid_at = CASE
                        WHEN ? != '' THEN ?
                        ELSE paid_at
                    END,
                    raw_json = ?
                WHERE payment_id = ?
                """,
                (
                    effective_user_id if effective_user_id > 0 else 0,
                    amount_rub,
                    status,
                    confirmation_url,
                    paid_at,
                    paid_at,
                    raw_json,
                    payment_id,
                ),
            )
        conn.commit()
        return payment_id
    finally:
        conn.close()


def process_success_payment_once(
    payment_id: str,
    source: str,
    note: str = "",
) -> tuple[bool, str, bool, int, bool]:
    pid = payment_id.strip()
    if not pid:
        return False, "Пустой payment_id.", False, 0, False

    conn = db_connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM yk_payments WHERE payment_id = ?",
            (pid,),
        ).fetchone()
        if row is None:
            conn.rollback()
            return False, "Платеж не найден в базе.", False, 0, False

        status = str(row["status"]).strip()
        if status != "succeeded":
            conn.rollback()
            return True, f"Статус платежа: {status}", False, int(row["user_id"]), False

        if int(row["processed"]) == 1:
            conn.rollback()
            return True, "Оплата уже обработана.", False, int(row["user_id"]), False

        user_id = int(row["user_id"])
        if user_id <= 0:
            conn.rollback()
            return False, "В платеже отсутствует user_id (metadata.user_id).", False, 0, False

        now = utc_now()
        started_dt = now
        expires_dt = now + timedelta(days=PRO_DAYS)
        day_key = msk_day_key(now)
        month_key = msk_month_key(now)

        existing_user = conn.execute(
            "SELECT plan_key, plan_expires_at FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        is_renewal = False
        if existing_user is not None and str(existing_user["plan_key"]) == "pro":
            old_expires = parse_iso_ts(str(existing_user["plan_expires_at"] or ""))
            if old_expires is not None and old_expires > now:
                is_renewal = True
                # Renewal extends from current active expiry.
                started_dt = old_expires
                expires_dt = old_expires + timedelta(days=PRO_DAYS)

        started = started_dt.isoformat()
        expires = expires_dt.isoformat()

        conn.execute(
            """
            INSERT OR IGNORE INTO users
            (user_id, plan_key, plan_started_at, plan_expires_at, day_key, month_key, created_at)
            VALUES (?, 'free', ?, ?, ?, ?, ?)
            """,
            (user_id, started, expires, day_key, month_key, started),
        )
        conn.execute(
            """
            UPDATE users
            SET plan_key = 'pro',
                pro_paid = 1,
                plan_started_at = ?,
                plan_expires_at = ?
            WHERE user_id = ?
            """,
            (started, expires, user_id),
        )
        updated_row = conn.execute(
            "SELECT plan_key, plan_started_at, plan_expires_at FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if updated_row is None:
            conn.rollback()
            return False, "Пользователь платежа не найден.", False, user_id, is_renewal

        amount_rub = int(row["amount_rub"] or 0)
        log_plan_event(
            conn,
            user_id,
            "pro_activated_paid",
            source,
            updated_row,
            amount_rub=amount_rub,
            payment_ref=pid,
            note=note or "Activated from YooKassa payment status.",
        )
        conn.execute(
            """
            UPDATE yk_payments
            SET processed = 1,
                paid_at = CASE
                    WHEN paid_at = '' THEN ?
                    ELSE paid_at
                END
            WHERE payment_id = ?
            """,
            (utc_now().isoformat(), pid),
        )
        conn.commit()
        return True, "Оплата подтверждена.", True, user_id, is_renewal
    except sqlite3.Error as exc:
        conn.rollback()
        return False, f"DB error: {exc}", False, 0, False
    finally:
        conn.close()


def get_yk_payment_record(payment_id: str) -> Optional[sqlite3.Row]:
    conn = db_connect()
    try:
        return conn.execute(
            "SELECT * FROM yk_payments WHERE payment_id = ?",
            (payment_id,),
        ).fetchone()
    finally:
        conn.close()


def mark_yk_payment_processed(payment_id: str) -> None:
    conn = db_connect()
    try:
        conn.execute(
            "UPDATE yk_payments SET processed = 1 WHERE payment_id = ?",
            (payment_id,),
        )
        conn.commit()
    finally:
        conn.close()


def create_yookassa_payment(
    user_id: int,
    amount_rub: int,
    description: str,
) -> Tuple[bool, str, Optional[str], Optional[dict[str, Any]]]:
    if not yk_is_configured():
        return False, "ЮKassa не настроена (YK_SHOP_ID/YK_SHOP_SECRET_KEY).", None, None
    if (
        YK_PAYOUT_SECRET_KEY
        and YK_SHOP_SECRET_KEY == YK_PAYOUT_SECRET_KEY
        and (not YK_PAYOUT_ACCOUNT_ID or YK_SHOP_ID != YK_PAYOUT_ACCOUNT_ID)
    ):
        return (
            False,
            "В .env указан одинаковый секрет для payments и payouts. "
            "Для YK_SHOP_ID нужен отдельный shop-ключ (YK_SHOP_SECRET_KEY), "
            "а payout-ключ оставьте только в YK_PAYOUT_SECRET_KEY.",
            None,
            None,
        )

    headers = {
        "Content-Type": "application/json",
        "Idempotence-Key": str(uuid.uuid4()),
    }
    payload = {
        "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": YK_RETURN_URL},
        "description": description,
        "metadata": {
            "user_id": str(user_id),
            "plan_key": "pro",
            "period_days": str(PRO_DAYS),
        },
    }

    try:
        request_started = time.perf_counter()
        response = yk_request_with_retry(
            "POST",
            f"{YK_API_BASE}/payments",
            session=get_yk_session(),
            auth=yk_auth(),
            headers=headers,
            data=json.dumps(payload),
        )
        latency_ms = int((time.perf_counter() - request_started) * 1000)
        api_logger.info("yk_create_payment status=%s latency_ms=%s", response.status_code, latency_ms)
    except requests.RequestException as exc:
        api_logger.error("yk_create_payment_network_error error=%s", str(exc)[:500])
        return False, f"Сетевая ошибка ЮKassa: {exc}", None, None

    try:
        data = response.json()
    except ValueError:
        return False, f"Ошибка ЮKassa {response.status_code}: {response.text}", None, None

    if response.status_code >= 400:
        if (
            response.status_code == 401
            and str(data.get("code", "")).strip() == "invalid_credentials"
            and "Authentication type is not allowed" in str(data.get("description", ""))
        ):
            return (
                False,
                "ЮKassa отклонила ключ: похоже, это payout-only ключ/шлюз. "
                "Для кнопки оплаты нужен платежный Shop ID и секрет (YK_SHOP_ID/YK_SHOP_SECRET_KEY).",
                None,
                data,
            )
        return False, f"Ошибка ЮKassa {response.status_code}: {data}", None, data

    payment_id = upsert_yk_payment(user_id, data)
    confirmation_url = str(
        data.get("confirmation", {}).get("confirmation_url", "")
    ).strip()
    if not payment_id or not confirmation_url:
        return False, "ЮKassa не вернула payment_id или confirmation_url.", None, data
    return True, "", payment_id, data


def fetch_yookassa_payment(payment_id: str) -> Tuple[bool, str, Optional[dict[str, Any]]]:
    if not yk_is_configured():
        return False, "ЮKassa не настроена (YK_SHOP_ID/YK_SHOP_SECRET_KEY).", None
    try:
        request_started = time.perf_counter()
        response = yk_request_with_retry(
            "GET",
            f"{YK_API_BASE}/payments/{payment_id}",
            session=get_yk_session(),
            auth=yk_auth(),
        )
        latency_ms = int((time.perf_counter() - request_started) * 1000)
        api_logger.info(
            "yk_fetch_payment payment_id=%s status=%s latency_ms=%s",
            payment_id,
            response.status_code,
            latency_ms,
        )
    except requests.RequestException as exc:
        api_logger.error("yk_fetch_payment_network_error payment_id=%s error=%s", payment_id, str(exc)[:500])
        return False, f"Сетевая ошибка ЮKassa: {exc}", None

    try:
        data = response.json()
    except ValueError:
        return False, f"Ошибка ЮKassa {response.status_code}: {response.text}", None

    if response.status_code >= 400:
        return False, f"Ошибка ЮKassa {response.status_code}: {data}", None

    return True, "", data


def create_simplepay_link(
    user_id: int,
    amount_rub: int,
    description: str,
) -> Tuple[bool, str, Optional[str], Optional[str]]:
    if not yk_simplepay_is_configured():
        return False, "SimplePay не настроен (YK_SIMPLEPAY_SHOP_ID или YK_SHOP_ID).", None, None

    payload = {
        "shopId": yk_simplepay_shop_id(),
        "sum": str(amount_rub),
        "customerNumber": f"{description} | user:{user_id}",
    }
    try:
        request_started = time.perf_counter()
        response = yk_request_with_retry(
            "POST",
            YK_SIMPLEPAY_ENDPOINT,
            data=payload,
            allow_redirects=False,
        )
        latency_ms = int((time.perf_counter() - request_started) * 1000)
        api_logger.info("yk_simplepay_link status=%s latency_ms=%s", response.status_code, latency_ms)
    except requests.RequestException as exc:
        api_logger.error("yk_simplepay_link_network_error error=%s", str(exc)[:500])
        return False, f"Сетевая ошибка SimplePay: {exc}", None, None

    if response.status_code not in {301, 302, 303, 307, 308}:
        return (
            False,
            f"SimplePay вернул HTTP {response.status_code}.",
            None,
            None,
        )

    payment_url = str(response.headers.get("Location", "")).strip()
    if not payment_url:
        return False, "SimplePay не вернул ссылку оплаты.", None, None

    order_id = ""
    try:
        parsed = urlparse(payment_url)
        order_id = (parse_qs(parsed.query).get("orderId") or [""])[0]
    except Exception:
        order_id = ""
    if not order_id:
        order_id = f"sp_{uuid.uuid4().hex[:16]}"

    return True, "", order_id, payment_url


def build_payment_link_keyboard(confirmation_url: str, payment_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◆ Перейти к оплате", url=confirmation_url)],
            [InlineKeyboardButton(text="◉ Проверить оплату", callback_data=f"check_pay:{payment_id}")],
        ]
    )


def build_simplepay_keyboard(pay_url: str, order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◆ Перейти к оплате", url=pay_url)],
            [InlineKeyboardButton(text="◉ Проверить оплату", callback_data=f"sp_check:{order_id}")],
        ]
    )


async def auto_check_payment_until_done(
    bot: Bot,
    user_id: int,
    chat_id: int,
    payment_id: str,
    source: str,
) -> None:
    if not AUTO_PAY_CHECK_ENABLED:
        return
    for delay in AUTO_PAY_DELAYS:
        await asyncio.sleep(delay)
        lock = get_user_lock(user_id)
        async with lock:
            ensure_user(user_id)
            ok, err_msg, payment_data = await asyncio.to_thread(fetch_yookassa_payment, payment_id)
            if not ok or payment_data is None:
                logger.warning(
                    "Auto-check payment failed user=%s payment=%s err=%s",
                    user_id,
                    payment_id,
                    err_msg,
                )
                continue

            upsert_yk_payment(user_id, payment_data)
            status = str(payment_data.get("status", "")).strip()
            payment_id_real = str(payment_data.get("id", "")).strip() or payment_id

            if status == "succeeded":
                ok_process, process_msg, activated, processed_user_id, is_renewal = await asyncio.to_thread(
                    process_success_payment_once,
                    payment_id_real,
                    source,
                    "Activated by automatic payment polling.",
                )
                if not ok_process:
                    logger.error(
                        "Auto-check activate failed user=%s payment=%s err=%s",
                        user_id,
                        payment_id_real,
                        process_msg,
                    )
                    return
                if not activated:
                    return
                target_user_id = processed_user_id if processed_user_id > 0 else user_id
                if is_renewal:
                    await bot.send_message(chat_id, "✅ Продление Pro подтверждено автоматически.")
                else:
                    await cleanup_after_paid_activation(
                        bot=bot,
                        user_id=target_user_id,
                        chat_id=chat_id,
                    )
                    await bot.send_message(chat_id, "✅ Оплата подтверждена автоматически.")
                    await send_home_welcome(bot, chat_id, target_user_id)
                return

            if status in {"canceled", "expired"}:
                return


def schedule_auto_payment_check(
    bot: Bot,
    user_id: int,
    chat_id: int,
    payment_id: str,
    source: str,
) -> None:
    if not AUTO_PAY_CHECK_ENABLED:
        return
    if not payment_id:
        return
    start_background_task(
        auto_check_payment_until_done(
            bot=bot,
            user_id=user_id,
            chat_id=chat_id,
            payment_id=payment_id,
            source=source,
        )
    )


def add_package(user_id: int, add_messages: int = 0, add_images: int = 0) -> None:
    conn = db_connect()
    try:
        conn.execute(
            """
            UPDATE users
            SET extra_messages = extra_messages + ?,
                extra_images = extra_images + ?
            WHERE user_id = ?
            """,
            (add_messages, add_images, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def usage_stats(row: sqlite3.Row) -> tuple[int, int, int, int, str]:
    plan = plan_for_row(row)
    used_text = int(row["day_messages_used"])
    if plan.image_period == "month":
        used_img = int(row["month_images_used"])
    else:
        used_img = int(row["day_images_used"])
    return used_text, plan.message_daily_limit, used_img, plan.image_limit, plan.image_period


def format_pro_until_date(row: sqlite3.Row) -> str:
    dt = parse_iso_ts(row["plan_expires_at"])
    if dt is None:
        return "-"
    return dt.astimezone(MSK_TZ).strftime("%d.%m.%Y")


def build_buy_pro_text() -> str:
    pro = PLANS["pro"]
    current_price = get_pro_price_rub()
    return (
        f"⭐ Pro-доступ на {PRO_DAYS} дней\n\n"
        f"Pro: до {pro.message_daily_limit} запросов в день + {pro.image_limit} изображений в месяц, быстрые ответы, приоритет.\n\n"
        "С Pro ты получаешь:\n"
        f"• до {pro.message_daily_limit} запросов в день\n"
        f"• {pro.image_limit} изображений в месяц\n"
        "• быстрые ответы\n"
        "• приоритет\n\n"
        f"Цена: {current_price} ₽ / {PRO_DAYS} дней\n\n"
        "Нажми кнопку ниже, чтобы оплатить 👇"
    )


def build_renew_pro_text() -> str:
    current_price = get_pro_price_rub()
    return (
        "🔄 Продление Pro\n\n"
        f"Хотите продлить доступ ещё на {PRO_DAYS} дней?\n\n"
        f"Цена: {current_price} ₽ / {PRO_DAYS} дней\n\n"
        "Нажмите кнопку ниже 👇"
    )


def build_free_profile_text(row: sqlite3.Row) -> str:
    used_text, limit_text, used_img, limit_img, _img_period = usage_stats(row)
    return (
        "📊 Ваш профиль\n\n"
        "Режим: Free\n\n"
        "Лимиты на сегодня:\n"
        f"• Сообщения: {used_text}/{limit_text}\n"
        f"• Изображения: {used_img}/{limit_img}\n\n"
        "Лимиты обновятся: в 00:00 по МСК"
    )


def build_pro_limits_text(row: sqlite3.Row) -> str:
    used_text, limit_text, used_img, limit_img, _img_period = usage_stats(row)
    return (
        "📊 Ваш доступ активен\n\n"
        "Режим: Pro\n\n"
        "Лимиты:\n"
        f"• Сообщения (день): {used_text}/{limit_text}\n"
        f"• Изображения (месяц): {used_img}/{limit_img}\n\n"
        f"⏳ Pro действует до: {format_pro_until_date(row)}"
    )


def build_support_text(plan_key: str) -> str:
    if plan_key == "pro":
        return (
            "💬 Техподдержка\n\n"
            "Если бот завис, неправильно считает лимиты или есть вопрос по подписке:\n\n"
            f"📩 {SUPPORT_CONTACT}"
        )
    return (
        "💬 Техподдержка\n\n"
        "Если бот работает неправильно или есть вопрос по оплате, напишите сюда:\n\n"
        f"📩 {SUPPORT_CONTACT}\n\n"
        "(обычно отвечаем быстро)"
    )


def build_terms_text() -> str:
    link_line = f"\n\n📄 Полные условия: {TERMS_URL}" if TERMS_URL else ""
    return (
        "📄 Условия Pro\n\n"
        f"{TERMS_TEXT}\n\n"
        "Лимиты нужны для стабильности и защиты от спама.\n"
        f"💬 Поддержка: {SUPPORT_CONTACT}"
        f"{link_line}"
    )


def build_privacy_text() -> str:
    return (
        "🔐 Конфиденциальность\n\n"
        "Что хранится:\n"
        "• технические данные пользователя (id, план, лимиты)\n"
        "• последний обмен для диагностики\n"
        "• короткий контекст Pro для поддержки диалога\n\n"
        "Что можно сделать:\n"
        "• /clear_history — очистить память AI (для Pro)\n"
        "• /terms — условия и возвраты\n"
        f"• /support — связь с поддержкой ({SUPPORT_CONTACT})"
    )


def build_about_text(plan_key: str) -> str:
    disclaimer = (
        "\n\n⚠️ Бот не является официальным продуктом xAI.\n"
        "Использует модели xAI (семейство Grok) через API."
    )
    if plan_key == "pro":
        pro = PLANS["pro"]
        return (
            "ℹ️ О помощнике\n\n"
            "Вы в режиме Pro ⭐\n\n"
            f"Pro: до {pro.message_daily_limit} запросов в день + {pro.image_limit} изображений в месяц, быстрые ответы, приоритет.\n\n"
            "Доступно:\n"
            f"• до {pro.message_daily_limit} запросов в день\n"
            f"• {pro.image_limit} изображений в месяц\n"
            "• быстрые ответы\n"
            "• приоритет\n\n"
            f"{TERMS_TEXT}"
            f"{disclaimer}"
        )
    free = PLANS["free"]
    pro = PLANS["pro"]
    return (
        "ℹ️ О помощнике\n\n"
        "Я умею:\n"
        "🧠 отвечать и объяснять\n"
        "✍️ писать и редактировать\n"
        "💻 помогать с кодом\n"
        "🎨 создавать изображения\n\n"
        f"Free текст: {PLANS['free'].text_model}\n"
        f"🎁 Free: {free.message_daily_limit} сообщений + {free.image_limit} изображение в день\n"
        f"⭐ Pro: до {pro.message_daily_limit} запросов в день + {pro.image_limit} изображений в месяц, быстрые ответы, приоритет.\n\n"
        f"{TERMS_TEXT}"
        f"{disclaimer}"
    )


def build_balance_text(user_id: int) -> str:
    row = reset_periods_if_needed(user_id)
    plan = plan_for_row(row)
    if plan.key == "free":
        return build_free_profile_text(row)
    return build_pro_limits_text(row)


def build_tariffs_text(user_id: int) -> str:
    return build_buy_pro_text()


def format_payment_check_error_message(err_msg: str) -> str:
    text = (err_msg or "").strip()
    if not text:
        return "Не удалось проверить оплату. Попробуйте еще раз."
    if "Сетевая ошибка ЮKassa" in text:
        return "Временная ошибка связи с YooKassa. Попробуйте снова через 10-20 секунд."
    return text


def extract_message_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n".join(parts).strip()
    return str(content)


def is_unsupported_image_model_error(error_text: str) -> bool:
    low = (error_text or "").lower()
    needles = (
        "image inputs are not supported by this model",
        "not supported by this model",
        "invalid request content",
        "не поддерживает изображения",
    )
    return any(token in low for token in needles)


def build_vision_fallback_candidates(primary_model: str) -> list[str]:
    candidates: list[str] = []
    for raw in (
        VISION_FALLBACK_MODEL,
        PRO_VISION_MODEL,
        XAI_VISION_MODEL,
        DEFAULT_MODEL,
        SMART_MODEL,
        PRO_TEXT_MODEL,
    ):
        candidate = (raw or "").strip()
        if not candidate or candidate == primary_model or candidate in candidates:
            continue
        candidates.append(candidate)
    return candidates


def _extract_api_error_message(error_payload: Any) -> str:
    if isinstance(error_payload, dict):
        for key in ("error", "message", "detail", "code"):
            value = error_payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                nested = _extract_api_error_message(value)
                if nested:
                    return nested
    if isinstance(error_payload, list):
        for item in error_payload:
            nested = _extract_api_error_message(item)
            if nested:
                return nested
    text = str(error_payload or "").strip()
    return text


def _contains_region_block_marker(text: str) -> bool:
    low = text.lower()
    markers = (
        "this service is not available in your region",
        "not available in your region",
        "service unavailable in your region",
    )
    return any(marker in low for marker in markers)


def format_xai_error_message(
    status_code: int,
    error_payload: Optional[Any] = None,
    response_text: str = "",
    image_mode: bool = False,
) -> str:
    payload_text = _extract_api_error_message(error_payload) if error_payload is not None else ""
    text = payload_text or response_text
    if status_code == 403 and _contains_region_block_marker(text):
        return (
            "xAI недоступен из текущего региона сервера (HTTP 403). "
            "Попробуйте позже или смените исходящий IP сервера."
        )
    if status_code == 401:
        return "xAI отклонил авторизацию (HTTP 401). Проверьте XAI_API_KEY."
    if status_code == 403:
        return "Доступ к xAI отклонен (HTTP 403). Проверьте регион/политику доступа."
    if status_code == 429:
        return "xAI вернул лимит запросов (HTTP 429). Попробуйте через несколько секунд."
    if status_code >= 500:
        if image_mode:
            return "Сервис генерации изображений временно перегружен. Попробуйте еще раз через 10-20 секунд."
        return "Сервис xAI временно недоступен (HTTP 5xx). Попробуйте еще раз."
    if payload_text:
        return f"Ошибка xAI API (HTTP {status_code}): {payload_text}"
    return f"Ошибка xAI API (HTTP {status_code})."


def send_to_grok(
    prompt: str,
    model: Optional[str] = None,
    image_mode: bool = False,
    edit_mode: bool = False,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    source_image_data_uri: Optional[str] = None,
    source_image_urls: Optional[list[str]] = None,
    chat_messages: Optional[list[dict[str, str]]] = None,
) -> Tuple[bool, str]:
    """
    Sends prompt to xAI API and returns:
    (True, response_text_or_image_url) or (False, error_message)
    """
    if not XAI_API_KEY:
        return False, "Переменная XAI_API_KEY не задана."

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {XAI_API_KEY}",
    }
    session = get_http_session()

    request_started = time.perf_counter()
    effective_model = model or (FREE_IMAGE_MODEL if image_mode else FREE_TEXT_MODEL)
    try:
        if image_mode:
            endpoint = f"{XAI_BASE_URL}/images/generations"
            final_prompt = prompt
            if edit_mode and not source_image_data_uri:
                final_prompt = f"Edit image based on instruction: {prompt}"

            payload: dict[str, Any] = {
                "model": effective_model,
                "prompt": final_prompt,
            }
            if source_image_urls:
                payload["image_urls"] = source_image_urls
            elif source_image_data_uri:
                payload["image_url"] = source_image_data_uri
            response = session.post(
                endpoint,
                headers=headers,
                data=json.dumps(payload),
                timeout=(XAI_CONNECT_TIMEOUT_SEC, XAI_READ_TIMEOUT_SEC),
            )
            if response.status_code >= 500:
                # Короткий ретрай при временной ошибке image backend.
                time.sleep(1.0)
                response = session.post(
                    endpoint,
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=(XAI_CONNECT_TIMEOUT_SEC, XAI_READ_TIMEOUT_SEC),
                )
        else:
            endpoint = f"{XAI_BASE_URL}/chat/completions"
            prepared_messages: list[dict[str, str]] = []
            if chat_messages:
                for item in chat_messages:
                    if not isinstance(item, dict):
                        continue
                    role = str(item.get("role", "")).strip().lower()
                    content = str(item.get("content", "")).strip()
                    if role in {"user", "assistant"} and content:
                        prepared_messages.append({"role": role, "content": content})
            if not prepared_messages:
                prepared_messages = [{"role": "user", "content": prompt}]

            payload = {
                "model": effective_model,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *prepared_messages],
                "stream": False,
                "temperature": 0,
                "max_tokens": max_output_tokens,
            }
            response = session.post(
                endpoint,
                headers=headers,
                data=json.dumps(payload),
                timeout=(XAI_CONNECT_TIMEOUT_SEC, XAI_READ_TIMEOUT_SEC),
            )

        latency_ms = int((time.perf_counter() - request_started) * 1000)
        api_logger.info(
            "xai_request mode=%s model=%s status=%s latency_ms=%s has_source_image=%s source_images_count=%s",
            "image" if image_mode else "chat",
            effective_model,
            response.status_code,
            latency_ms,
            "1" if bool(source_image_data_uri) else "0",
            len(source_image_urls) if source_image_urls else 0,
        )

        if response.status_code >= 400:
            # Пример обработки ошибки API: пытаемся разобрать JSON.
            try:
                err_json = response.json()
                api_logger.error(
                    "xai_error mode=%s model=%s status=%s latency_ms=%s error=%s",
                    "image" if image_mode else "chat",
                    effective_model,
                    response.status_code,
                    latency_ms,
                    str(err_json)[:500],
                )
                return False, format_xai_error_message(
                    status_code=response.status_code,
                    error_payload=err_json,
                    image_mode=image_mode,
                )
            except ValueError:
                api_logger.error(
                    "xai_error mode=%s model=%s status=%s latency_ms=%s error=%s",
                    "image" if image_mode else "chat",
                    effective_model,
                    response.status_code,
                    latency_ms,
                    response.text[:500],
                )
                return False, format_xai_error_message(
                    status_code=response.status_code,
                    response_text=response.text,
                    image_mode=image_mode,
                )

        data = response.json()

        if image_mode:
            image_url = data["data"][0]["url"]
            return True, image_url

        content = extract_message_content_text(data["choices"][0]["message"]["content"])
        return True, content

    except requests.RequestException as exc:
        latency_ms = int((time.perf_counter() - request_started) * 1000)
        api_logger.error(
            "xai_network_error mode=%s model=%s latency_ms=%s error=%s",
            "image" if image_mode else "chat",
            effective_model,
            latency_ms,
            str(exc)[:500],
        )
        return False, f"Сетевая ошибка при вызове xAI API: {exc}"
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        latency_ms = int((time.perf_counter() - request_started) * 1000)
        api_logger.error(
            "xai_parse_error mode=%s model=%s latency_ms=%s error=%s",
            "image" if image_mode else "chat",
            effective_model,
            latency_ms,
            str(exc)[:500],
        )
        return False, f"Некорректный формат ответа API: {exc}"


def send_to_grok_with_photo(
    prompt: str,
    image_bytes: bytes,
    model: Optional[str] = None,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
) -> Tuple[bool, str]:
    if not XAI_API_KEY:
        return False, "Переменная XAI_API_KEY не задана."
    if not image_bytes:
        return False, "Пустое изображение."

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {XAI_API_KEY}",
    }
    session = get_http_session()
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    image_data_url = f"data:image/jpeg;base64,{image_b64}"

    payload = {
        "model": model or FREE_TEXT_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            },
        ],
        "stream": False,
        "temperature": 0,
        "max_tokens": max_output_tokens,
    }

    request_started = time.perf_counter()
    effective_model = model or FREE_TEXT_MODEL
    try:
        response = session.post(
            f"{XAI_BASE_URL}/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=(XAI_CONNECT_TIMEOUT_SEC, XAI_READ_TIMEOUT_SEC),
        )
        latency_ms = int((time.perf_counter() - request_started) * 1000)
        api_logger.info(
            "xai_request mode=vision model=%s status=%s latency_ms=%s",
            effective_model,
            response.status_code,
            latency_ms,
        )
        if response.status_code >= 400:
            try:
                err_json = response.json()
                api_logger.error(
                    "xai_error mode=vision model=%s status=%s latency_ms=%s error=%s",
                    effective_model,
                    response.status_code,
                    latency_ms,
                    str(err_json)[:500],
                )
                return False, format_xai_error_message(
                    status_code=response.status_code,
                    error_payload=err_json,
                    image_mode=False,
                )
            except ValueError:
                api_logger.error(
                    "xai_error mode=vision model=%s status=%s latency_ms=%s error=%s",
                    effective_model,
                    response.status_code,
                    latency_ms,
                    response.text[:500],
                )
                return False, format_xai_error_message(
                    status_code=response.status_code,
                    response_text=response.text,
                    image_mode=False,
                )

        data = response.json()
        content = extract_message_content_text(data["choices"][0]["message"]["content"])
        return True, content
    except requests.RequestException as exc:
        latency_ms = int((time.perf_counter() - request_started) * 1000)
        api_logger.error(
            "xai_network_error mode=vision model=%s latency_ms=%s error=%s",
            effective_model,
            latency_ms,
            str(exc)[:500],
        )
        return False, f"Сетевая ошибка при вызове xAI API: {exc}"
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        latency_ms = int((time.perf_counter() - request_started) * 1000)
        api_logger.error(
            "xai_parse_error mode=vision model=%s latency_ms=%s error=%s",
            effective_model,
            latency_ms,
            str(exc)[:500],
        )
        return False, f"Некорректный формат ответа API: {exc}"


async def try_handle_faq_request(
    message: Message,
    user_id: int,
    row: sqlite3.Row,
    text: str,
) -> bool:
    pending_intent = str(row["pending_faq_intent"] or "").strip().lower()
    consumed_quota = False
    if pending_intent and text.lower() in {"отмена", "стоп", "cancel"}:
        await asyncio.to_thread(set_pending_faq_intent, user_id, "")
        await message.answer("Ок, отменил уточнение. Напишите новый запрос.")
        return True

    intent = pending_intent or detect_faq_intent(text)
    if not intent:
        return False

    ready, payload, ask_text = parse_faq_request(
        intent,
        text,
        from_pending=bool(pending_intent),
    )
    if not ready:
        await asyncio.to_thread(set_pending_faq_intent, user_id, intent)
        if ask_text:
            await message.answer(ask_text)
        return True

    ok_rate, rate_msg = check_rate_limit(user_id)
    if not ok_rate:
        await message.answer(rate_msg)
        return True

    ok_quota, quota_msg = await asyncio.to_thread(consume_text_quota, user_id)
    if not ok_quota:
        await message.answer(f"Нельзя обработать запрос: {quota_msg}")
        return True
    consumed_quota = True

    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    ok, result = await asyncio.to_thread(run_faq_intent, intent, payload)
    if ok:
        await asyncio.to_thread(set_pending_faq_intent, user_id, "")
        await asyncio.to_thread(save_last_exchange, user_id, text, result, f"faq:{intent}")
        if plan_for_row(row).key == "pro":
            await asyncio.to_thread(save_pro_conversation_turn, user_id, text, result)
        await message.answer(result)
    else:
        await asyncio.to_thread(set_pending_faq_intent, user_id, intent)
        if consumed_quota:
            await asyncio.to_thread(refund_text_quota, user_id)
        followup_map = {
            FAQ_INTENT_NEWS: "Уточните тему новостей одним сообщением (например, «новости про ИИ»).",
            FAQ_INTENT_WEATHER: "Уточните город одним сообщением.",
            FAQ_INTENT_TIME: "Уточните город одним сообщением.",
            FAQ_INTENT_ADDRESS: "Уточните адрес/место одним сообщением.",
            FAQ_INTENT_FX: "Уточните валютную пару (например, USD/RUB).",
        }
        followup = followup_map.get(intent, "")
        if followup:
            await message.answer(f"{result}\n{followup}")
        else:
            await message.answer(result)
    return True


dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user_id = message.from_user.id
    ensure_user(user_id)
    await send_home_welcome(message.bot, message.chat.id, user_id)


@dp.message(Command("support"))
async def cmd_support(message: Message) -> None:
    user_id = message.from_user.id
    ensure_user(user_id)
    row = reset_periods_if_needed(user_id)
    plan = plan_for_row(row)
    await message.answer(build_support_text(plan.key))


@dp.message(Command("terms"))
async def cmd_terms(message: Message) -> None:
    user_id = message.from_user.id
    ensure_user(user_id)
    await message.answer(build_terms_text())


@dp.message(Command("privacy"))
async def cmd_privacy(message: Message) -> None:
    user_id = message.from_user.id
    ensure_user(user_id)
    await message.answer(build_privacy_text())


@dp.message(Command("clear_history"))
async def cmd_clear_history(message: Message) -> None:
    user_id = message.from_user.id
    ensure_user(user_id)
    row = reset_periods_if_needed(user_id)
    if plan_for_row(row).key != "pro":
        await message.answer("В Free режиме память AI недоступна.")
        return
    clear_user_history(user_id)
    await message.answer("🧠 Память AI очищена.")


@dp.message(F.voice)
async def voice_handler(message: Message) -> None:
    await message.answer(
        "Голосовые сообщения пока не поддерживаются.\n"
        "Отправьте, пожалуйста, текст."
    )


@dp.message(F.photo)
async def photo_handler(message: Message) -> None:
    user_id = message.from_user.id
    lock = get_user_lock(user_id)

    async with lock:
        await asyncio.to_thread(ensure_user, user_id)
        row = await asyncio.to_thread(reset_periods_if_needed, user_id)

        pending_action = row["pending_image_action"]
        if pending_action == "create":
            await asyncio.to_thread(set_pending_image_action, user_id, "")
            await message.answer(
                "Для создания изображения отправьте текстовый запрос, не фото.\n"
                "Пример: «Нарисуй красный спорткар в стиле киберпанк»."
            )
            return

        prompt = (message.caption or "").strip()
        if not prompt:
            prompt = "Опиши, что изображено на фото, коротко и понятно."
        if len(prompt) > MAX_USER_PROMPT_CHARS:
            await message.answer(
                f"Слишком длинный запрос. Максимум {MAX_USER_PROMPT_CHARS} символов."
            )
            return

        ok_rate, rate_msg = check_rate_limit(user_id)
        if not ok_rate:
            await message.answer(rate_msg)
            return

        if not message.photo:
            await message.answer("Не удалось получить фото. Отправьте изображение еще раз.")
            return

        largest_photo = message.photo[-1]
        try:
            tg_file = await message.bot.get_file(largest_photo.file_id)
            file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{tg_file.file_path}"
            file_response = await asyncio.to_thread(
                requests.get,
                file_url,
                timeout=(XAI_CONNECT_TIMEOUT_SEC, XAI_READ_TIMEOUT_SEC),
            )
        except Exception as exc:
            await message.answer(f"Не удалось скачать фото из Telegram: {exc}")
            return

        if file_response.status_code >= 400:
            await message.answer(f"Не удалось скачать фото из Telegram: HTTP {file_response.status_code}")
            return

        image_bytes = file_response.content
        if not image_bytes:
            await message.answer("Не удалось прочитать фото. Отправьте изображение еще раз.")
            return
        if len(image_bytes) > MAX_VISION_IMAGE_BYTES:
            await message.answer(
                f"Фото слишком большое. Максимум {MAX_VISION_IMAGE_BYTES // (1024 * 1024)} МБ."
            )
            return

        ok_quota, quota_msg = await asyncio.to_thread(consume_text_quota, user_id)
        if not ok_quota:
            await message.answer(f"Нельзя обработать фото: {quota_msg}")
            return

        plan = plan_for_row(row)
        model = FREE_VISION_MODEL if plan.key == "free" else PRO_VISION_MODEL
        if not model:
            model = XAI_VISION_MODEL or DEFAULT_MODEL
        max_tokens = FREE_MAX_OUTPUT_TOKENS if plan.key == "free" else PRO_MAX_OUTPUT_TOKENS
        max_tokens = min(max_tokens, MAX_OUTPUT_TOKENS)
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

        used_model = model
        ok, result = await asyncio.to_thread(
            send_to_grok_with_photo,
            prompt,
            image_bytes,
            model,
            max_tokens,
        )
        if not ok and is_unsupported_image_model_error(result):
            for fallback_model in build_vision_fallback_candidates(model):
                api_logger.warning(
                    "vision_model_fallback first_model=%s fallback_model=%s user_id=%s",
                    model,
                    fallback_model,
                    user_id,
                )
                used_model = fallback_model
                ok, result = await asyncio.to_thread(
                    send_to_grok_with_photo,
                    prompt,
                    image_bytes,
                    fallback_model,
                    max_tokens,
                )
                if ok or not is_unsupported_image_model_error(result):
                    break

        if ok:
            await asyncio.to_thread(save_last_exchange, user_id, "[photo] " + prompt, result, used_model)
            if plan.key == "pro":
                await asyncio.to_thread(save_pro_conversation_turn, user_id, "[photo] " + prompt, result)
            await message.answer(result)
        else:
            await asyncio.to_thread(refund_text_quota, user_id)
            if is_unsupported_image_model_error(result):
                await message.answer(
                    "Фото-анализ сейчас недоступен для текущей конфигурации модели.\n"
                    "Лимит не списан. Проверьте XAI_VISION_MODEL/FREE_VISION_MODEL в .env."
                )
                return
            await message.answer(
                "Не удалось проанализировать фото.\n"
                f"{result}"
            )


@dp.message(F.text)
async def text_handler(message: Message) -> None:
    user_id = message.from_user.id
    text = (message.text or "").strip()
    if not text:
        return

    lock = get_user_lock(user_id)
    async with lock:
        await asyncio.to_thread(ensure_user, user_id)
        row = await asyncio.to_thread(reset_periods_if_needed, user_id)

        if text in {"Старт", "🚀 Старт", "/start"}:
            await send_home_welcome(message.bot, message.chat.id, user_id)
            return

        if text in {"🔥 Купить", "Купить", "◆ Купить Pro", "Купить Pro"}:
            await send_payment_message(
                message,
                user_id,
                build_buy_pro_text(),
                reply_markup=build_buy_keyboard(),
            )
            return

        if text in {"💬 Техподдержка", "Техподдержка"}:
            plan = plan_for_row(row)
            await message.answer(build_support_text(plan.key))
            return

        if text in {"ℹ️ О AI-помощнике", "О AI-помощнике"}:
            plan = plan_for_row(row)
            await message.answer(build_about_text(plan.key))
            return

        if text in {"📄 Условия", "◆ Условия", "Условия"}:
            await message.answer(build_terms_text())
            return

        if text in {"🔐 Конфиденциальность", "Конфиденциальность"}:
            await message.answer(build_privacy_text())
            return

        if text in {
            "🧠 Очистить память AI",
            "Очистить память AI",
            "🧹 Очистить историю",
            "Очистить историю",
        }:
            if plan_for_row(row).key != "pro":
                await message.answer("В Free режиме память AI недоступна.")
                return
            await asyncio.to_thread(clear_user_history, user_id)
            await message.answer("🧠 Память AI очищена.")
            return

        if text in {"💳 Баланс", "Баланс"}:
            await message.answer(build_balance_text(user_id))
            return

        if text in {"📦 Тарифы", "Тарифы"}:
            await send_payment_message(
                message,
                user_id,
                build_buy_pro_text(),
                reply_markup=build_buy_keyboard(),
            )
            return

        if text in {"💬 Задать вопрос", "🧠 Сменить режим", "🖼 Изображения", "👤 Кабинет"}:
            await message.answer("Обновите меню: отправьте /start")
            return

        pending_action = row["pending_image_action"]

        if pending_action == "create":
            if len(text) > MAX_USER_PROMPT_CHARS:
                await message.answer(
                    f"Слишком длинный запрос. Максимум {MAX_USER_PROMPT_CHARS} символов."
                )
                return
            ok_rate, rate_msg = check_rate_limit(user_id)
            if not ok_rate:
                await message.answer(rate_msg)
                return
            ok_quota, quota_msg = await asyncio.to_thread(consume_image_quota, user_id)
            if not ok_quota:
                await message.answer(f"Нельзя сгенерировать изображение: {quota_msg}")
                return
            await message.bot.send_chat_action(
                chat_id=message.chat.id,
                action=ChatAction.UPLOAD_PHOTO,
            )
            plan = plan_for_row(row)
            image_model = plan.image_model
            ok, result = await asyncio.to_thread(
                send_to_grok,
                text,
                image_model,
                True,
                False,
                MAX_OUTPUT_TOKENS,
            )
            await asyncio.to_thread(set_pending_image_action, user_id, "")
            if ok:
                await asyncio.to_thread(save_last_exchange, user_id, text, result, image_model)
                try:
                    await message.answer_photo(result)
                except Exception:
                    await message.answer(result)
            else:
                await asyncio.to_thread(refund_image_quota, user_id, plan.image_period)
                await message.answer(f"Не удалось сгенерировать изображение.\n{result}")
            return

        faq_handled = await try_handle_faq_request(message, user_id, row, text)
        if faq_handled:
            return

        if len(text) > MAX_USER_PROMPT_CHARS:
            await message.answer(
                f"Слишком длинный запрос. Максимум {MAX_USER_PROMPT_CHARS} символов."
            )
            return

        ok_rate, rate_msg = check_rate_limit(user_id)
        if not ok_rate:
            await message.answer(rate_msg)
            return

        ok_quota, quota_msg = await asyncio.to_thread(consume_text_quota, user_id)
        if not ok_quota:
            await message.answer(f"Нельзя обработать запрос: {quota_msg}")
            return

        plan = plan_for_row(row)
        model = plan.text_model
        max_tokens = FREE_MAX_OUTPUT_TOKENS if plan.key == "free" else PRO_MAX_OUTPUT_TOKENS
        max_tokens = min(max_tokens, MAX_OUTPUT_TOKENS)
        chat_messages: Optional[list[dict[str, str]]] = None
        if plan.key == "pro":
            chat_messages = await asyncio.to_thread(build_pro_context_messages, user_id, text)
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

        ok, result = await asyncio.to_thread(
            send_to_grok,
            prompt=text,
            model=model,
            image_mode=False,
            edit_mode=False,
            max_output_tokens=max_tokens,
            chat_messages=chat_messages,
        )
        if ok:
            await asyncio.to_thread(save_last_exchange, user_id, text, result, model)
            if plan.key == "pro":
                await asyncio.to_thread(save_pro_conversation_turn, user_id, text, result)
            await message.answer(result)
        else:
            await asyncio.to_thread(refund_text_quota, user_id)
            await message.answer(f"Не удалось получить ответ.\n{result}")


@dp.callback_query(F.data)
async def callback_handler(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return

    user_id = callback.from_user.id
    data = callback.data or ""
    lock = get_user_lock(user_id)

    async with lock:
        await asyncio.to_thread(ensure_user, user_id)
        row = await asyncio.to_thread(reset_periods_if_needed, user_id)

        if data.startswith("check_pay:"):
            payment_id = data.split(":", 1)[1].strip()
            if not payment_id:
                await callback.answer("Некорректный payment id")
                return

            ok, err_msg, payment_data = await asyncio.to_thread(fetch_yookassa_payment, payment_id)
            if not ok or payment_data is None:
                await callback.message.answer(
                    "Не удалось проверить оплату.\n"
                    f"{format_payment_check_error_message(err_msg)}"
                )
                await callback.answer("Ошибка проверки")
                return

            await asyncio.to_thread(upsert_yk_payment, user_id, payment_data)
            status = str(payment_data.get("status", "")).strip()

            if status == "succeeded":
                ok_process, process_msg, activated, processed_user_id, is_renewal = await asyncio.to_thread(
                    process_success_payment_once,
                    payment_id,
                    "yookassa_payment",
                    "Activated after successful YooKassa payment.",
                )
                if not ok_process:
                    await callback.message.answer(f"Ошибка активации:\n{process_msg}")
                    await callback.answer("Ошибка активации")
                    return
                if not activated:
                    await callback.message.answer("✅ Оплата уже подтверждена. Pro уже активен.")
                    await callback.answer("Уже обработано")
                    return

                await callback.answer("Оплата подтверждена")
                target_user_id = processed_user_id if processed_user_id > 0 else user_id
                if is_renewal:
                    row_after = await asyncio.to_thread(reset_periods_if_needed, target_user_id)
                    await callback.message.answer("✅ Продление Pro подтверждено.")
                    await callback.message.answer(build_pro_limits_text(row_after))
                else:
                    await cleanup_after_paid_activation(
                        bot=callback.bot,
                        user_id=target_user_id,
                        chat_id=callback.message.chat.id,
                        anchor_message_id=callback.message.message_id,
                    )
                    await send_home_welcome(callback.bot, callback.message.chat.id, target_user_id)
                return

            if status in {"pending", "waiting_for_capture"}:
                await callback.message.answer(
                    "⏳ Платеж еще не завершен.\n"
                    "Завершите оплату и нажмите «Проверить оплату» снова."
                )
                await callback.answer("Еще не оплачено")
                return

            if status == "canceled":
                details = payment_data.get("cancellation_details") or {}
                reason = details.get("reason", "unknown")
                party = details.get("party", "unknown")
                await callback.message.answer(
                    "❌ Платеж отменен.\n"
                    f"Причина: {reason}\n"
                    f"Сторона: {party}"
                )
                await callback.answer("Платеж отменен")
                return

            await callback.message.answer(f"Статус платежа: {status}")
            await callback.answer("Статус обновлен")
            return

        if data.startswith("sp_check:") or data.startswith("sp_done:"):
            order_id = data.split(":", 1)[1].strip() or f"sp_{uuid.uuid4().hex[:8]}"
            if not yk_is_configured():
                await callback.message.answer(
                    "Проверка оплаты сейчас недоступна (не настроены API-ключи магазина).\n"
                    "Подписка не активирована. Если уже оплатили, напишите в техподдержку."
                )
                await callback.answer("Не подтверждено")
                return

            ok, err_msg, payment_data = await asyncio.to_thread(fetch_yookassa_payment, order_id)
            if not ok or payment_data is None:
                await callback.message.answer(
                    "Не удалось проверить оплату из-за временной сетевой ошибки.\n"
                    "Подписка будет активирована, как только проверка пройдет.\n"
                    "Нажмите «Проверить оплату» еще раз через 10-20 секунд.\n"
                    f"{format_payment_check_error_message(err_msg)}"
                )
                await callback.answer("Не подтверждено")
                return

            await asyncio.to_thread(upsert_yk_payment, user_id, payment_data)
            status = str(payment_data.get("status", "")).strip()
            payment_id = str(payment_data.get("id", "")).strip() or order_id

            if status == "succeeded":
                ok_process, process_msg, activated, processed_user_id, is_renewal = await asyncio.to_thread(
                    process_success_payment_once,
                    payment_id,
                    "simplepay_payment_check",
                    "Activated after SimplePay payment status check.",
                )
                if not ok_process:
                    await callback.message.answer(f"Ошибка активации:\n{process_msg}")
                    await callback.answer("Ошибка активации")
                    return
                if not activated:
                    await callback.message.answer("✅ Оплата уже подтверждена. Pro уже активен.")
                    await callback.answer("Уже обработано")
                    return

                await callback.answer("Оплата подтверждена")
                target_user_id = processed_user_id if processed_user_id > 0 else user_id
                if is_renewal:
                    row_after = await asyncio.to_thread(reset_periods_if_needed, target_user_id)
                    await callback.message.answer("✅ Продление Pro подтверждено.")
                    await callback.message.answer(build_pro_limits_text(row_after))
                else:
                    await cleanup_after_paid_activation(
                        bot=callback.bot,
                        user_id=target_user_id,
                        chat_id=callback.message.chat.id,
                        anchor_message_id=callback.message.message_id,
                    )
                    await send_home_welcome(callback.bot, callback.message.chat.id, target_user_id)
                return

            if status in {"pending", "waiting_for_capture"}:
                await callback.message.answer(
                    "⏳ Платеж еще не завершен.\n"
                    "Завершите оплату и нажмите «Проверить оплату» снова."
                )
                await callback.answer("Еще не оплачено")
                return

            if status == "canceled":
                details = payment_data.get("cancellation_details") or {}
                reason = details.get("reason", "unknown")
                party = details.get("party", "unknown")
                await callback.message.answer(
                    "❌ Платеж отменен.\n"
                    f"Причина: {reason}\n"
                    f"Сторона: {party}"
                )
                await callback.answer("Платеж отменен")
                return

            await callback.message.answer(f"Статус платежа: {status}")
            await callback.answer("Статус обновлен")
            return

        if data == "home_buy":
            await send_payment_message(
                callback.message,
                user_id,
                build_buy_pro_text(),
                reply_markup=build_buy_keyboard(),
            )
            await callback.answer("Тарифы")
            return

        if data == "home_renew":
            await send_payment_message(
                callback.message,
                user_id,
                build_renew_pro_text(),
                reply_markup=build_buy_keyboard(),
            )
            await callback.answer("Продление")
            return

        if data == "home_profile":
            if plan_for_row(row).key == "free":
                await callback.message.answer(build_free_profile_text(row))
            else:
                await callback.message.answer(build_pro_limits_text(row))
            await callback.answer("Профиль")
            return

        if data == "home_limits":
            if plan_for_row(row).key == "pro":
                await callback.message.answer(build_pro_limits_text(row))
            else:
                await callback.message.answer(build_free_profile_text(row))
            await callback.answer("Лимиты")
            return

        if data == "home_pro_until":
            if plan_for_row(row).key == "pro":
                await callback.message.answer(build_pro_limits_text(row))
            else:
                await callback.message.answer(build_free_profile_text(row))
            await callback.answer("Статус Pro")
            return

        if data == "home_support":
            plan = plan_for_row(row)
            await callback.message.answer(build_support_text(plan.key))
            await callback.answer("Техподдержка")
            return

        if data == "home_terms":
            await callback.message.answer(build_terms_text())
            await callback.answer("Условия")
            return

        if data == "home_clear_history":
            if plan_for_row(row).key != "pro":
                await callback.message.answer("В Free режиме память AI недоступна.")
                await callback.answer("Недоступно")
                return
            await asyncio.to_thread(clear_user_history, user_id)
            await callback.message.answer("🧠 Память AI очищена.")
            await callback.answer("Очищено")
            return

        if data == "home_img_create":
            await asyncio.to_thread(set_pending_image_action, user_id, "create")
            await callback.message.answer(
                "🖼 Напишите текст для новой картинки."
            )
            await callback.answer("Создание изображения")
            return

        if data == "home_start":
            await send_home_welcome(callback.bot, callback.message.chat.id, user_id)
            await callback.answer("Старт")
            return

        if data == "home_about":
            plan = plan_for_row(row)
            await callback.message.answer(build_about_text(plan.key))
            await callback.answer("О помощнике")
            return

        if data == "mode_normal":
            await asyncio.to_thread(update_plan, user_id, "free", source="legacy_mode_normal")
            await asyncio.to_thread(set_pending_image_action, user_id, "")
            await callback.message.answer("🆓 Режим: Free")
            await callback.answer("Free")
            return

        if data == "mode_smart":
            await send_payment_message(
                callback.message,
                user_id,
                "⭐ Pro включается только через оплату.\n"
                "Нажмите кнопку покупки ниже.",
                reply_markup=build_buy_keyboard(),
            )
            await callback.answer("Требуется оплата")
            return

        if data == "open_images":
            await callback.message.answer("🖼 Изображения:", reply_markup=build_images_keyboard())
            await callback.answer("Изображения")
            return

        if data == "open_cabinet":
            await callback.message.answer("👤 Кабинет:", reply_markup=build_cabinet_keyboard())
            await callback.answer("Кабинет")
            return

        if data == "img_create":
            await asyncio.to_thread(set_pending_image_action, user_id, "create")
            await callback.message.answer("🖼 Отправьте запрос.")
            await callback.answer("Режим: создание")
            return

        if data == "img_edit":
            await asyncio.to_thread(set_pending_image_action, user_id, "")
            await callback.message.answer("Редактирование изображений отключено.")
            await callback.answer("Отключено")
            return

        if data == "img_cancel":
            await asyncio.to_thread(set_pending_image_action, user_id, "")
            await callback.message.answer("Режим изображений отменен.")
            await callback.answer("Отменено")
            return

        if data == "cab_balance":
            await callback.message.answer(build_balance_text(user_id))
            await callback.answer("Баланс")
            return

        if data == "cab_tariffs":
            await send_payment_message(
                callback.message,
                user_id,
                build_buy_pro_text(),
                reply_markup=build_buy_keyboard(),
            )
            await callback.answer("Тарифы")
            return

        if data == "plan_pro":
            await send_payment_message(
                callback.message,
                user_id,
                build_buy_pro_text(),
                reply_markup=build_buy_keyboard(),
            )
            await callback.answer("Требуется оплата")
            return

        if data == "plan_free":
            err = await asyncio.to_thread(update_plan, user_id, "free", source="legacy_plan_free")
            await callback.message.answer("🟦 Режим Free включен." if not err else err)
            await callback.message.answer(build_balance_text(user_id))
            await callback.answer("Режим обновлен")
            return

        if data == "pay_pro":
            current_price = get_pro_price_rub()
            if YK_PAY_MODE == "simplepay":
                sp_ok, sp_msg, order_id, pay_url = await asyncio.to_thread(
                    create_simplepay_link,
                    user_id,
                    current_price,
                    f"Подписка Askora AI Pro на {PRO_DAYS} дней",
                )
                if not sp_ok or not order_id or not pay_url:
                    await callback.message.answer(f"Не удалось создать платеж (SimplePay).\n{sp_msg}")
                    await callback.answer("Ошибка платежа")
                    return

                await send_payment_message(
                    callback.message,
                    user_id,
                    "💳 Ссылка оплаты (SimplePay) готова.\n"
                    "1) Нажмите «Перейти к оплате»\n"
                    "2) После успешной оплаты нажмите «Проверить оплату»"
                )
                await send_payment_message(
                    callback.message,
                    user_id,
                    f"Заказ: `{order_id}`",
                    reply_markup=build_simplepay_keyboard(pay_url, order_id),
                    parse_mode="Markdown",
                )
                schedule_auto_payment_check(
                    callback.bot,
                    user_id,
                    callback.message.chat.id,
                    order_id,
                    source="auto_poll_simplepay",
                )
                await callback.answer("Ссылка создана")
                return

            ok, err_msg, payment_id, payment_data = await asyncio.to_thread(
                create_yookassa_payment,
                user_id,
                current_price,
                f"Pro-подписка на {PRO_DAYS} дней",
            )
            if not ok or not payment_id or payment_data is None:
                if yk_simplepay_is_configured():
                    sp_ok, sp_msg, order_id, pay_url = await asyncio.to_thread(
                        create_simplepay_link,
                        user_id,
                        current_price,
                        f"Подписка Askora AI Pro на {PRO_DAYS} дней",
                    )
                    if sp_ok and order_id and pay_url:
                        await send_payment_message(
                            callback.message,
                            user_id,
                            "API-оплата сейчас недоступна, переключили на SimplePay.\n"
                            "1) Нажмите «Перейти к оплате»\n"
                            "2) После успешной оплаты нажмите «Проверить оплату»"
                        )
                        await send_payment_message(
                            callback.message,
                            user_id,
                            f"Заказ: `{order_id}`",
                            reply_markup=build_simplepay_keyboard(pay_url, order_id),
                            parse_mode="Markdown",
                        )
                        schedule_auto_payment_check(
                            callback.bot,
                            user_id,
                            callback.message.chat.id,
                            order_id,
                            source="auto_poll_simplepay_fallback",
                        )
                        await callback.answer("Ссылка создана")
                        return
                    await callback.message.answer(
                        "Не удалось создать платеж через API и SimplePay.\n"
                        f"API: {err_msg}\nSimplePay: {sp_msg}"
                    )
                    await callback.answer("Ошибка платежа")
                    return
                await callback.message.answer(f"Не удалось создать платеж.\n{err_msg}")
                await callback.answer("Ошибка платежа")
                return

            confirmation_url = str(
                payment_data.get("confirmation", {}).get("confirmation_url", "")
            ).strip()
            if not confirmation_url:
                await callback.message.answer(
                    "Не удалось получить ссылку на оплату. Попробуйте еще раз."
                )
                await callback.answer("Ошибка платежа")
                return

            await send_payment_message(
                callback.message,
                user_id,
                "💳 Ссылка на оплату создана.\n"
                "1) Нажмите «Перейти к оплате»\n"
                "2) После оплаты нажмите «Проверить оплату»"
            )
            await send_payment_message(
                callback.message,
                user_id,
                f"Платеж: `{payment_id}`",
                reply_markup=build_payment_link_keyboard(confirmation_url, payment_id),
                parse_mode="Markdown",
            )
            schedule_auto_payment_check(
                callback.bot,
                user_id,
                callback.message.chat.id,
                payment_id,
                source="auto_poll_api",
            )
            await callback.answer("Ссылка создана")
            return

        await callback.answer()


async def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Переменная TELEGRAM_BOT_TOKEN не задана.")
    if not XAI_API_KEY:
        raise RuntimeError("Переменная XAI_API_KEY не задана.")
    init_db()
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Старт"),
            BotCommand(command="support", description="Техподдержка"),
            BotCommand(command="terms", description="Условия"),
            BotCommand(command="privacy", description="Конфиденциальность"),
            BotCommand(command="clear_history", description="Очистить память AI"),
        ]
    )
    await dp.start_polling(bot)


def setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    root.addHandler(console)

    app_file = RotatingFileHandler(
        "bot.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    app_file.setLevel(logging.INFO)
    app_file.setFormatter(formatter)
    root.addHandler(app_file)

    api_logger.handlers.clear()
    api_logger.setLevel(logging.INFO)
    api_logger.propagate = False
    api_file = RotatingFileHandler(
        "api.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    api_file.setLevel(logging.INFO)
    api_file.setFormatter(formatter)
    api_logger.addHandler(api_file)
    api_logger.addHandler(console)


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())
