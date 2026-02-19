import os
import sqlite3

from flask import Flask, abort, jsonify, redirect, render_template_string, request, url_for

import bot
from env_utils import load_env_file


load_env_file()

app = Flask(__name__)
app.secret_key = os.getenv("ADMIN_SECRET_KEY", "change-me")

DB_PATH = os.getenv("BOT_DB_PATH", bot.DB_PATH)
ADMIN_PANEL_TOKEN = os.getenv("ADMIN_PANEL_TOKEN", "").strip()
ADMIN_PORT = int(os.getenv("ADMIN_PORT", "8080"))
YK_WEBHOOK_SECRET = os.getenv("YK_WEBHOOK_SECRET", "").strip()
YK_WEBHOOK_ALLOW_INSECURE = os.getenv("YK_WEBHOOK_ALLOW_INSECURE", "0").strip() == "1"
YK_WEBHOOK_TRUST_X_FORWARDED_FOR = (
    os.getenv("YK_WEBHOOK_TRUST_X_FORWARDED_FOR", "0").strip() == "1"
)
YK_WEBHOOK_TRUSTED_PROXIES = {
    ip.strip() for ip in os.getenv("YK_WEBHOOK_TRUSTED_PROXIES", "").split(",") if ip.strip()
}
YK_WEBHOOK_ALLOWED_IPS = {
    ip.strip() for ip in os.getenv("YK_WEBHOOK_ALLOWED_IPS", "").split(",") if ip.strip()
}


HTML = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Bot Admin</title>
  <style>
    body { font-family: Arial, sans-serif; background: #111; color: #f4f4f4; margin: 0; padding: 16px; }
    .wrap { max-width: 1200px; margin: 0 auto; }
    .cards { display: grid; grid-template-columns: repeat(4, minmax(150px, 1fr)); gap: 10px; margin-bottom: 14px; }
    .card { background: #1b1b1b; border: 1px solid #333; border-radius: 10px; padding: 10px; }
    .label { font-size: 12px; color: #aaa; margin-bottom: 4px; }
    .val { font-size: 24px; font-weight: 700; }
    table { width: 100%; border-collapse: collapse; background: #1b1b1b; border: 1px solid #333; border-radius: 10px; overflow: hidden; }
    th, td { padding: 8px; border-bottom: 1px solid #2a2a2a; font-size: 13px; vertical-align: top; }
    th { background: #202020; text-align: left; position: sticky; top: 0; }
    tr:hover { background: #1f1f1f; }
    .ok { color: #48d66f; font-weight: 700; }
    .no { color: #ff6b6b; font-weight: 700; }
    .actions form { display: inline-block; margin: 2px 4px 2px 0; }
    button { background: #2a2a2a; color: #fff; border: 1px solid #444; border-radius: 8px; padding: 6px 8px; cursor: pointer; font-size: 12px; }
    button:hover { background: #353535; }
    .pill { display: inline-block; padding: 3px 8px; border-radius: 999px; border: 1px solid #444; }
    .free { color: #67b0ff; }
    .pro { color: #73f29e; }
    .filters { margin: 0 0 10px 0; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    select, input[type=text] { background: #1d1d1d; color: #fff; border: 1px solid #444; border-radius: 8px; padding: 6px; }
    input[type=number] { background: #1d1d1d; color: #fff; border: 1px solid #444; border-radius: 8px; padding: 6px; width: 120px; }
    .small { color: #9a9a9a; font-size: 12px; }
  </style>
</head>
<body>
  <div class="wrap">
    <h2>Админка Telegram-бота</h2>
    <div class="small">База: {{ db_path }}</div>
    <div class="cards">
      <div class="card"><div class="label">Пользователей</div><div class="val">{{ stats.total }}</div></div>
      <div class="card"><div class="label">Free</div><div class="val">{{ stats.free }}</div></div>
      <div class="card"><div class="label">Pro</div><div class="val">{{ stats.pro }}</div></div>
      <div class="card"><div class="label">Купили Pro</div><div class="val">{{ stats.paid }}</div></div>
    </div>

    <form class="filters" method="post" action="/settings/pro_price">
      <input type="hidden" name="token" value="{{ token }}" />
      <label>Цена Pro (₽):</label>
      <input type="number" name="pro_price" min="1" max="1000000" step="1" value="{{ pro_price }}" required />
      <button type="submit">Сохранить цену</button>
      <span class="small">Новая цена применяется сразу в кнопке оплаты у бота.</span>
    </form>

    <form class="filters" method="get" action="/">
      <input type="hidden" name="token" value="{{ token }}" />
      <label>План:</label>
      <select name="plan">
        <option value="all" {% if plan_filter == "all" %}selected{% endif %}>Все</option>
        <option value="free" {% if plan_filter == "free" %}selected{% endif %}>Free</option>
        <option value="pro" {% if plan_filter == "pro" %}selected{% endif %}>Pro</option>
      </select>
      <label>Оплата Pro:</label>
      <select name="paid">
        <option value="all" {% if paid_filter == "all" %}selected{% endif %}>Все</option>
        <option value="1" {% if paid_filter == "1" %}selected{% endif %}>Купили</option>
        <option value="0" {% if paid_filter == "0" %}selected{% endif %}>Не купили</option>
      </select>
      <button type="submit">Фильтр</button>
    </form>

    <table>
      <thead>
        <tr>
          <th>User ID</th>
          <th>План</th>
          <th>Купил Pro</th>
          <th>Лимиты</th>
          <th>Срок</th>
          <th>Последняя активация Pro</th>
          <th>Последний обмен</th>
          <th>Действия</th>
        </tr>
      </thead>
      <tbody>
        {% for u in users %}
        <tr>
          <td>{{ u.user_id }}</td>
          <td>
            {% if u.plan_key == "pro" %}
              <span class="pill pro">Pro</span>
            {% else %}
              <span class="pill free">Free</span>
            {% endif %}
          </td>
          <td>
            {% if u.pro_paid == 1 %}
              <span class="ok">Да</span>
            {% else %}
              <span class="no">Нет</span>
            {% endif %}
          </td>
          <td>
            {% if u.plan_key == "pro" %}
              Сообщения: {{ pro_plan.message_daily_limit - u.day_messages_used if pro_plan.message_daily_limit - u.day_messages_used > 0 else 0 }} / {{ pro_plan.message_daily_limit }} в день<br>
              Изобр.: {{ pro_plan.image_limit - u.month_images_used if pro_plan.image_limit - u.month_images_used > 0 else 0 }} / {{ pro_plan.image_limit }} в месяц
            {% else %}
              Сообщения: {{ free_plan.message_daily_limit - u.day_messages_used if free_plan.message_daily_limit - u.day_messages_used > 0 else 0 }} / {{ free_plan.message_daily_limit }} в день<br>
              Изобр.: {{ free_plan.image_limit - u.day_images_used if free_plan.image_limit - u.day_images_used > 0 else 0 }} / {{ free_plan.image_limit }} в день
            {% endif %}
          </td>
          <td>{{ u.plan_expires_at[:10] if u.plan_expires_at else "-" }}</td>
          <td>
            {% if u.last_pro_event_at %}
              {{ u.last_pro_event_at[:19].replace("T", " ") }}<br>
              Период: {{ u.last_pro_period_days }} дн.<br>
              Источник: {{ u.last_pro_source }}<br>
              Сумма: {{ u.last_pro_amount_rub }} ₽
            {% else %}
              -
            {% endif %}
          </td>
          <td>{{ u.last_exchange_at[:19].replace("T", " ") if u.last_exchange_at else "-" }}</td>
          <td class="actions">
            <form method="post" action="/user/{{ u.user_id }}/plan">
              <input type="hidden" name="token" value="{{ token }}" />
              <input type="hidden" name="plan" value="free" />
              <button type="submit">Free</button>
            </form>
            <form method="post" action="/user/{{ u.user_id }}/plan">
              <input type="hidden" name="token" value="{{ token }}" />
              <input type="hidden" name="plan" value="pro" />
              <input type="hidden" name="paid" value="0" />
              <button type="submit">Pro (без оплаты)</button>
            </form>
            <form method="post" action="/user/{{ u.user_id }}/plan">
              <input type="hidden" name="token" value="{{ token }}" />
              <input type="hidden" name="plan" value="pro" />
              <input type="hidden" name="paid" value="1" />
              <button type="submit">Pro (оплачено)</button>
            </form>
            <form method="post" action="/user/{{ u.user_id }}/paid">
              <input type="hidden" name="token" value="{{ token }}" />
              <input type="hidden" name="paid" value="0" />
              <button type="submit">Сброс оплаты</button>
            </form>
            <form method="post" action="/user/{{ u.user_id }}/refund">
              <input type="hidden" name="token" value="{{ token }}" />
              <button type="submit">Возврат → Free</button>
            </form>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</body>
</html>
"""


def check_token() -> str:
    token = (
        request.values.get("token", "").strip()
        or request.headers.get("X-Admin-Token", "").strip()
    )
    if not ADMIN_PANEL_TOKEN:
        abort(503, "ADMIN_PANEL_TOKEN is required in production.")
    if token != ADMIN_PANEL_TOKEN:
        abort(403, "Forbidden. Add ?token=YOUR_ADMIN_PANEL_TOKEN")
    return token


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(
        DB_PATH,
        timeout=max(bot.SQLITE_BUSY_TIMEOUT_MS / 1000.0, 5.0),
    )
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {bot.SQLITE_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def webhook_secret_ok(path_secret: str) -> bool:
    if not YK_WEBHOOK_SECRET:
        return YK_WEBHOOK_ALLOW_INSECURE
    token = (
        path_secret.strip()
        or request.args.get("token", "").strip()
        or request.headers.get("X-YK-Webhook-Secret", "").strip()
        or request.headers.get("X-Webhook-Secret", "").strip()
    )
    return token == YK_WEBHOOK_SECRET


def resolve_request_ip() -> str:
    remote_ip = (request.remote_addr or "").strip()
    forwarded = request.headers.get("X-Forwarded-For", "").strip()
    if (
        YK_WEBHOOK_TRUST_X_FORWARDED_FOR
        and forwarded
        and YK_WEBHOOK_TRUSTED_PROXIES
        and remote_ip in YK_WEBHOOK_TRUSTED_PROXIES
    ):
        return forwarded.split(",")[0].strip()
    return remote_ip


def webhook_ip_ok() -> bool:
    if not YK_WEBHOOK_ALLOWED_IPS:
        return True
    remote_ip = resolve_request_ip()
    return remote_ip in YK_WEBHOOK_ALLOWED_IPS


def get_users(plan_filter: str, paid_filter: str):
    query = """
    SELECT
      u.*,
      (
        SELECT e.event_at
        FROM plan_events e
        WHERE e.user_id = u.user_id
          AND e.event_type LIKE 'pro_activated%'
        ORDER BY e.id DESC
        LIMIT 1
      ) AS last_pro_event_at,
      (
        SELECT e.period_days
        FROM plan_events e
        WHERE e.user_id = u.user_id
          AND e.event_type LIKE 'pro_activated%'
        ORDER BY e.id DESC
        LIMIT 1
      ) AS last_pro_period_days,
      (
        SELECT e.source
        FROM plan_events e
        WHERE e.user_id = u.user_id
          AND e.event_type LIKE 'pro_activated%'
        ORDER BY e.id DESC
        LIMIT 1
      ) AS last_pro_source,
      (
        SELECT e.amount_rub
        FROM plan_events e
        WHERE e.user_id = u.user_id
          AND e.event_type LIKE 'pro_activated%'
        ORDER BY e.id DESC
        LIMIT 1
      ) AS last_pro_amount_rub
    FROM users u
    """
    where = []
    params = []
    if plan_filter in {"free", "pro"}:
        where.append("plan_key = ?")
        params.append(plan_filter)
    if paid_filter in {"0", "1"}:
        where.append("pro_paid = ?")
        params.append(int(paid_filter))
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY created_at DESC"

    conn = db_connect()
    try:
        rows = conn.execute(query, params).fetchall()
        return rows
    finally:
        conn.close()


def get_stats():
    conn = db_connect()
    try:
        total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        free = conn.execute("SELECT COUNT(*) FROM users WHERE plan_key = 'free'").fetchone()[0]
        pro = conn.execute("SELECT COUNT(*) FROM users WHERE plan_key = 'pro'").fetchone()[0]
        paid = conn.execute("SELECT COUNT(*) FROM users WHERE pro_paid = 1").fetchone()[0]
        return {"total": total, "free": free, "pro": pro, "paid": paid}
    finally:
        conn.close()


@app.post("/yk/webhook")
@app.post("/yk/webhook/<path_secret>")
def yk_webhook(path_secret: str = ""):
    bot.init_db()

    if not YK_WEBHOOK_SECRET and not YK_WEBHOOK_ALLOW_INSECURE:
        return jsonify({"ok": False, "error": "webhook_secret_required"}), 503
    if not webhook_secret_ok(path_secret):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    if not webhook_ip_ok():
        return jsonify({"ok": False, "error": "forbidden_ip"}), 403

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "invalid_json"}), 400

    event = str(payload.get("event", "")).strip()
    payment_data = payload.get("object")
    if not isinstance(payment_data, dict) or not payment_data.get("id"):
        if payload.get("id"):
            payment_data = payload
        else:
            return jsonify({"ok": True, "ignored": "no_payment_object", "event": event}), 200

    payment_id = bot.upsert_yk_payment(None, payment_data)
    if not payment_id:
        return jsonify({"ok": True, "ignored": "payment_not_saved", "event": event}), 200

    # Never trust incoming webhook payload blindly: re-verify with YooKassa API.
    ok_fetch, fetch_msg, verified_payment = bot.fetch_yookassa_payment(payment_id)
    if not ok_fetch or verified_payment is None:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "verify_failed",
                    "event": event,
                    "payment_id": payment_id,
                    "message": fetch_msg,
                }
            ),
            502,
        )

    payment_id = bot.upsert_yk_payment(None, verified_payment)
    if not payment_id:
        return jsonify({"ok": False, "error": "verify_saved_failed", "event": event}), 500

    status = str(verified_payment.get("status", "")).strip()
    if status == "succeeded":
        ok, msg, activated, user_id, is_renewal = bot.process_success_payment_once(
            payment_id,
            source="yookassa_webhook",
            note=f"Activated by webhook event: {event or 'unknown'}",
        )
        code = 200 if ok else 500
        return (
            jsonify(
                {
                    "ok": ok,
                    "payment_id": payment_id,
                    "status": status,
                    "event": event,
                    "activated": activated,
                    "user_id": user_id,
                    "renewal": is_renewal,
                    "message": msg,
                }
            ),
            code,
        )

    return jsonify({"ok": True, "payment_id": payment_id, "status": status, "event": event}), 200


@app.get("/")
def admin_index():
    token = check_token()
    bot.init_db()
    plan_filter = request.args.get("plan", "all")
    paid_filter = request.args.get("paid", "all")
    users = get_users(plan_filter, paid_filter)
    stats = get_stats()
    pro_price = bot.get_pro_price_rub()
    return render_template_string(
        HTML,
        users=users,
        stats=stats,
        pro_price=pro_price,
        free_plan=bot.PLANS["free"],
        pro_plan=bot.PLANS["pro"],
        token=token,
        db_path=DB_PATH,
        plan_filter=plan_filter,
        paid_filter=paid_filter,
    )


@app.post("/user/<int:user_id>/plan")
def set_user_plan(user_id: int):
    token = check_token()
    bot.ensure_user(user_id)
    plan = request.form.get("plan", "").strip()
    paid_raw = request.form.get("paid")
    mark_paid = None if paid_raw is None else (paid_raw == "1")
    amount_rub = bot.get_pro_price_rub() if mark_paid else 0
    bot.update_plan(
        user_id,
        plan,
        mark_paid=mark_paid,
        source="admin_panel",
        amount_rub=amount_rub,
        note="Changed from admin panel.",
    )
    return redirect(url_for("admin_index", token=token))


@app.post("/settings/pro_price")
def set_pro_price():
    token = check_token()
    bot.init_db()
    raw_value = request.form.get("pro_price", "").strip()
    try:
        value = int(raw_value)
    except ValueError:
        return redirect(url_for("admin_index", token=token))
    if value < 1 or value > 1000000:
        return redirect(url_for("admin_index", token=token))
    bot.set_setting_value(bot.PRO_PRICE_SETTING_KEY, str(value))
    return redirect(url_for("admin_index", token=token))


@app.post("/user/<int:user_id>/paid")
def set_user_paid(user_id: int):
    token = check_token()
    bot.ensure_user(user_id)
    paid = 1 if request.form.get("paid", "0") == "1" else 0
    conn = db_connect()
    try:
        conn.execute("UPDATE users SET pro_paid = ? WHERE user_id = ?", (paid, user_id))
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("admin_index", token=token))


@app.post("/user/<int:user_id>/refund")
def refund_user(user_id: int):
    token = check_token()
    bot.ensure_user(user_id)
    bot.update_plan(
        user_id,
        "free",
        mark_paid=False,
        source="admin_refund",
        amount_rub=0,
        note="Manual refund: switched to Free.",
    )
    return redirect(url_for("admin_index", token=token))


if __name__ == "__main__":
    bot.init_db()
    app.run(host="0.0.0.0", port=ADMIN_PORT, debug=False)
