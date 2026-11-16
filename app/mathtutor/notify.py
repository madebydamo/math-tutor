"""Telegram nudges for the coach (admin). The student gets none."""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import threading
import time

import httpx

from . import db, metrics, progress
from . import neo_telemetry as tel
from .config import CFG
from .content import content

log = logging.getLogger("mathtutor.notify")


def enabled() -> bool:
    return bool(CFG.telegram_token and CFG.telegram_chat) and db.get_setting("notify_enabled", True)


def send(text: str) -> bool:
    """Send a message to the coach. Blocking (call it with asyncio.to_thread from async code).

    Failures are logged (status and Telegram's description, never the token or the text) and counted."""
    if not enabled():
        return False
    try:
        r = httpx.post(f"https://api.telegram.org/bot{CFG.telegram_token}/sendMessage",
                       json={"chat_id": CFG.telegram_chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
                       timeout=15)
    except httpx.HTTPError as e:
        metrics.TELEGRAM.labels("exception").inc()
        # the exception text holds the URL with the bot token: log the type only
        log.error("telegram message failed", extra={"event": "telegram_failed", "error": type(e).__name__})
        return False
    if r.status_code != 200:
        metrics.TELEGRAM.labels("http_error").inc()
        try:
            desc = str(r.json().get("description", ""))[:200]
        except ValueError:
            desc = ""
        log.error("telegram refused the message", extra={"event": "telegram_failed", "http_status": r.status_code,
                                                         "description": desc})
        return False
    metrics.TELEGRAM.labels("ok").inc()
    return True


def link(path: str) -> str:
    return f"{CFG.public_url.rstrip('/')}{path}" if CFG.public_url else path


def promotion(user: str, rank: dict):
    if user == CFG.student_user and db.once(f"promo:{user}:{rank['id']}"):
        # called from request handlers on the event loop: send in a thread, never block it
        threading.Thread(target=send, args=(f"🎖️ {CFG.student_name} wurde befördert: <b>{rank['name']}</b>",),
                         name="telegram-promotion", daemon=True).start()


def struggle(user: str, skill: str):
    """Three wrong answers in a row on one skill today → tell the coach once per skill and day."""
    if user != CFG.student_user:
        return
    rows = db.q("SELECT correct, skills FROM attempts WHERE user=? AND status!='format' ORDER BY id DESC LIMIT 12", user)
    streak = 0
    for r in rows:
        if (db.loads(r["skills"], []) or [None])[0] != skill:
            continue
        if r["correct"]:
            break
        streak += 1
    if streak >= 3 and db.once(f"struggle:{skill}:{progress.today()}"):
        title = content().skills.get(skill, {}).get("title", skill)
        send(f"⚠️ {CFG.student_name} kämpft gerade mit <b>{title}</b> ({streak} Fehlversuche in Folge).\n{link('/admin#/schwachstellen')}")


def daily_summary():
    u = CFG.student_user
    d = progress.today()
    t0 = time.time() - 86400
    rows = db.q("SELECT correct, skills FROM attempts WHERE user=? AND created_at>=? AND status!='format'", u, t0)
    if not rows or not db.once(f"daily:{d}"):
        return
    ok = sum(1 for r in rows if r["correct"])
    skills = {}
    for r in rows:
        s = (db.loads(r["skills"], []) or [None])[0]
        skills.setdefault(s, [0, 0])
        skills[s][0] += 1
        skills[s][1] += r["correct"] or 0
    c = content()
    worst = sorted(((s, v) for s, v in skills.items() if v[0] >= 2), key=lambda kv: kv[1][1] / kv[1][0])[:2]
    lines = [f"📊 {CFG.student_name} heute: {len(rows)} Teilaufgaben, {ok} richtig ({round(100 * ok / len(rows))} %)."]
    if worst:
        lines.append("Schwierig: " + ", ".join(f"{c.skills.get(s, {}).get('title', s)} ({v[1]}/{v[0]})" for s, v in worst))
    rs = progress.rank_state(u)
    lines.append(f"Rang: {rs['rank']['name']} · {rs['xp']} XP")
    send("\n".join(lines))


def session_reminder():
    dates = progress.dates()
    if dates["days_to_session"] == 1 and db.once(f"session-reminder:{dates['next_session']}"):
        send(f"📅 Morgen Lernsession mit {CFG.student_name}. Briefing: {link('/admin#/briefing')}")
    if dates["days_to_session"] == 7 and db.once(f"session-week:{dates['next_session']}"):
        n = db.q1("SELECT COUNT(*) AS n FROM attempts WHERE user=? AND created_at>=?", CFG.student_user, time.time() - 7 * 86400)["n"]
        if n == 0:
            send(f"💤 {CFG.student_name} hat seit einer Woche nicht geübt – Session in 7 Tagen.")


def _tick():
    now = dt.datetime.now(progress.TZ)
    if now.hour == 20:
        daily_summary()
    if now.hour == 18:
        session_reminder()


async def loop():
    """Every 10 minutes: daily summary at 20:00, session reminders at 18:00 (job `notifications`)."""
    while True:
        try:
            with tel.job("notifications"):
                await asyncio.to_thread(_tick)
        except Exception:  # noqa: BLE001 - logged and counted by tel.job; keep the loop alive
            pass
        await asyncio.sleep(600)
