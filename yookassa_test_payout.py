import argparse
import json
import os
import sys
import time
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

import requests
from requests.auth import HTTPBasicAuth

from env_utils import load_env_file


load_env_file()


API_BASE = os.getenv("YK_API_BASE", "https://api.yookassa.ru/v3").rstrip("/")
ACCOUNT_ID = os.getenv("YK_PAYOUT_ACCOUNT_ID", os.getenv("YK_ACCOUNT_ID", "")).strip()
SECRET_KEY = os.getenv("YK_PAYOUT_SECRET_KEY", os.getenv("YK_SECRET_KEY", "")).strip()
REQUEST_TIMEOUT = (8, 30)


def fail(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def require_creds() -> HTTPBasicAuth:
    if not ACCOUNT_ID:
        fail("Переменная YK_PAYOUT_ACCOUNT_ID (или YK_ACCOUNT_ID) не задана.")
    if not SECRET_KEY:
        fail("Переменная YK_PAYOUT_SECRET_KEY (или YK_SECRET_KEY) не задана.")
    return HTTPBasicAuth(ACCOUNT_ID, SECRET_KEY)


def pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def api_get(path: str, auth: HTTPBasicAuth) -> requests.Response:
    return requests.get(f"{API_BASE}{path}", auth=auth, timeout=REQUEST_TIMEOUT)


def api_post(path: str, payload: dict[str, Any], auth: HTTPBasicAuth) -> requests.Response:
    headers = {
        "Content-Type": "application/json",
        "Idempotence-Key": str(uuid.uuid4()),
    }
    return requests.post(
        f"{API_BASE}{path}",
        auth=auth,
        headers=headers,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )


def parse_amount(value: str) -> str:
    try:
        amount = Decimal(value).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        fail("Некорректная сумма. Пример: 2.00")
    if amount <= 0:
        fail("Сумма должна быть больше нуля.")
    return format(amount, "f")


def cmd_me(auth: HTTPBasicAuth) -> None:
    r = api_get("/me", auth)
    print(f"HTTP {r.status_code}")
    try:
        data = r.json()
    except ValueError:
        print(r.text)
        return
    print(pretty(data))


def cmd_balance(auth: HTTPBasicAuth) -> None:
    r = api_get("/me", auth)
    print(f"HTTP {r.status_code}")
    try:
        data = r.json()
    except ValueError:
        print(r.text)
        return
    print(
        pretty(
            {
                "account_id": data.get("account_id"),
                "test": data.get("test"),
                "payout_methods": data.get("payout_methods"),
                "payout_balance": data.get("payout_balance"),
            }
        )
    )


def cmd_payout(
    auth: HTTPBasicAuth,
    amount: str,
    wallet: str,
    order_id: str,
    description: str,
    poll_seconds: int,
) -> None:
    payload = {
        "amount": {"value": parse_amount(amount), "currency": "RUB"},
        "payout_destination_data": {
            "type": "yoo_money",
            "account_number": wallet,
        },
        "description": description,
        "metadata": {"order_id": order_id},
    }

    r = api_post("/payouts", payload, auth)
    print(f"HTTP {r.status_code}")
    try:
        data = r.json()
    except ValueError:
        print(r.text)
        return
    print(pretty(data))

    if r.status_code >= 400:
        return

    payout_id = data.get("id")
    status = data.get("status")
    if not payout_id:
        return
    if status in {"succeeded", "canceled"}:
        return

    deadline = time.time() + poll_seconds
    while time.time() < deadline:
        time.sleep(2)
        g = api_get(f"/payouts/{payout_id}", auth)
        print(f"[poll] HTTP {g.status_code}")
        try:
            gd = g.json()
        except ValueError:
            print(g.text)
            continue
        print(pretty(gd))
        if g.status_code >= 400:
            return
        status = gd.get("status")
        if status in {"succeeded", "canceled"}:
            return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Проверка тестовых выплат ЮKassa (v3 API)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("me", help="Проверить подключение и параметры шлюза.")
    sub.add_parser("balance", help="Показать баланс выплат и методы выплат.")

    p = sub.add_parser("payout", help="Создать тестовую выплату на кошелек ЮMoney.")
    p.add_argument("--amount", default="2.00", help="Сумма выплаты в RUB, например 2.00")
    p.add_argument(
        "--wallet",
        default="4100116075156746",
        help="Номер кошелька ЮMoney для теста.",
    )
    p.add_argument("--order-id", default=f"test-{uuid.uuid4().hex[:8]}")
    p.add_argument(
        "--description",
        default="Тестовая выплата из bot_grok",
        help="Описание выплаты",
    )
    p.add_argument(
        "--poll-seconds",
        type=int,
        default=20,
        help="Сколько секунд опрашивать payout, если он не сразу завершен.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    auth = require_creds()

    if args.command == "me":
        cmd_me(auth)
        return
    if args.command == "balance":
        cmd_balance(auth)
        return
    if args.command == "payout":
        cmd_payout(
            auth=auth,
            amount=args.amount,
            wallet=args.wallet,
            order_id=args.order_id,
            description=args.description,
            poll_seconds=args.poll_seconds,
        )
        return

    fail("Неизвестная команда.", code=2)


if __name__ == "__main__":
    main()
