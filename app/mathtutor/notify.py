"""Telegram nudges for the coach (admin). The student gets none."""
from __future__ import annotations

import asyncio
import datetime as dt
import time

import httpx

from . import db, progress
from .config import CFG
from .content import content


def enabled() -> bool:
    return bool(CFG.telegram_token and CFG.telegram_chat) and db.get_setting("notify_enabled", True)


def send(text: str):
    if not enabled():
        return
    try:
        httpx.post(f"https://api.telegram.org/bot{CFG.telegram_token}/sendMessage",
                   json={"chat_id": CFG.telegram_chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
                   timeout=15)
    except httpx.HTTPError:
        pass


def link(path: str) -> str:
    return f"{CFG.public_url.rstrip('/')}{path}" if CFG.public_url else path


def promotion(user: str, rank: dict):
    if user == CFG.student_user and db.once(f"promo:{user}:{rank['id']}"):
        send(f"🎖️ {CFG.student_name} wurde befördert: <b>{rank['name']}</b>")


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


async def loop():
    while True:
        try:
            now = dt.datetime.now(progress.TZ)
            if now.hour == 20:
                await asyncio.to_thread(daily_summary)
            if now.hour == 18:
                await asyncio.to_thread(session_reminder)
        except Exception as e:  # noqa: BLE001
            print("notify loop:", e)
        await asyncio.sleep(600)
