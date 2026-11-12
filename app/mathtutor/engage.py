"""Things that keep the student coming back: daily goal, daily quests, combo, medals, formula cards (spaced repetition)."""
from __future__ import annotations

import datetime as dt
import random
import time

from . import db, progress
from .content import content

DAY = 86400
CARD_DAYS = [0, 1, 3, 7, 16, 35]  # Leitner boxes for formula cards

db.SCHEMA += """
CREATE TABLE IF NOT EXISTS cards (
  user TEXT, card_id TEXT, box INTEGER DEFAULT 0, due_at REAL, reviews INTEGER DEFAULT 0, lapses INTEGER DEFAULT 0,
  last_at REAL, PRIMARY KEY(user, card_id)
);
CREATE TABLE IF NOT EXISTS card_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, card_id TEXT, grade TEXT, kind TEXT, created_at REAL
);
CREATE TABLE IF NOT EXISTS medals (user TEXT, medal TEXT, created_at REAL, PRIMARY KEY(user, medal));
"""


def _day_bounds(day: str | None = None) -> tuple[float, float]:
    d = dt.date.fromisoformat(day) if day else dt.datetime.now(progress.TZ).date()
    start = dt.datetime.combine(d, dt.time(0, 0), progress.TZ).timestamp()
    return start, start + DAY


# ───────────── daily goal ─────────────

def daily_goal(user: str) -> dict:
    goal = int(db.get_setting("daily_goal", 10))
    a, b = _day_bounds()
    done = db.q1("SELECT COUNT(*) AS n FROM attempts WHERE user=? AND correct=1 AND created_at>=? AND created_at<?", user, a, b)["n"]
    reached = done >= goal
    if reached and db.once(f"goal:{user}:{progress.today()}"):
        progress.add_xp(user, 25, "Tagesziel erreicht", progress.today())
    return {"goal": goal, "done": done, "reached": reached}


# ───────────── combo ─────────────

def combo(user: str) -> int:
    """Correct answers in a row today (format errors ignored)."""
    a, _ = _day_bounds()
    n = 0
    for r in db.q("SELECT correct FROM attempts WHERE user=? AND created_at>=? AND status!='format' ORDER BY id DESC LIMIT 60", user, a):
        if not r["correct"]:
            break
        n += 1
    return n


# ───────────── daily quests ─────────────

QUEST_POOL = [
    ("solve5", "Löse 5 Teilaufgaben richtig", 5),
    ("solve12", "Löse 12 Teilaufgaben richtig", 12),
    ("nohint3", "Löse 3 Aufgaben ohne Hinweis", 3),
    ("cards10", "Wiederhole 10 Formelkarten", 10),
    ("photo1", "Lass einen Lösungsweg per Foto korrigieren", 1),
    ("challenge1", "Spiele eine Revanche", 1),
    ("weak2", "Löse 2 Aufgaben aus deinem schwächsten Thema", 2),
    ("explainback1", "Erklär dem Tutor ein Thema in eigenen Worten", 1),
    ("new1", "Probiere ein neues Thema aus", 1),
    ("calc_free3", "Löse 3 Aufgaben «ohne Rechner»", 3),
]


def _quest_progress(user: str, qid: str, a: float, b: float) -> int:
    if qid.startswith("solve"):
        return db.q1("SELECT COUNT(*) AS n FROM attempts WHERE user=? AND correct=1 AND created_at BETWEEN ? AND ?", user, a, b)["n"]
    if qid == "nohint3":
        return db.q1("SELECT COUNT(*) AS n FROM attempts WHERE user=? AND correct=1 AND hints=0 AND solution_shown=0 AND created_at BETWEEN ? AND ?", user, a, b)["n"]
    if qid == "cards10":
        return db.q1("SELECT COUNT(*) AS n FROM card_log WHERE user=? AND created_at BETWEEN ? AND ?", user, a, b)["n"]
    if qid == "photo1":
        return db.q1("SELECT COUNT(*) AS n FROM reviews WHERE user=? AND created_at BETWEEN ? AND ?", user, a, b)["n"]
    if qid == "challenge1":
        return db.q1("SELECT COUNT(*) AS n FROM attempts WHERE user=? AND mode='challenge' AND created_at BETWEEN ? AND ?", user, a, b)["n"]
    if qid == "weak2":
        sm = progress.skill_mastery(user, until=a)
        weak = [k for k, v in sorted(sm.items(), key=lambda kv: kv[1]["mastery"]) if v["n"]][:2]
        rows = db.q("SELECT skills FROM attempts WHERE user=? AND correct=1 AND created_at BETWEEN ? AND ?", user, a, b)
        return sum(1 for r in rows if (db.loads(r["skills"], []) or [None])[0] in weak)
    if qid == "explainback1":
        return db.q1("SELECT COUNT(*) AS n FROM messages m JOIN chats c ON c.id=m.chat_id WHERE c.user=? AND m.role='user' "
                     "AND m.meta LIKE '%explain_back%' AND m.created_at BETWEEN ? AND ?", user, a, b)["n"]
    if qid == "new1":
        rows = db.q("SELECT skills, created_at FROM attempts WHERE user=? ORDER BY id", user)
        seen_before = {(db.loads(r["skills"], []) or [None])[0] for r in rows if r["created_at"] < a}
        today = {(db.loads(r["skills"], []) or [None])[0] for r in rows if a <= r["created_at"] < b}
        return len(today - seen_before)
    if qid == "calc_free3":
        rows = db.q("SELECT exercise_id FROM attempts WHERE user=? AND correct=1 AND created_at BETWEEN ? AND ?", user, a, b)
        c = content()
        return sum(1 for r in rows if (c.get(r["exercise_id"]) or {}).get("calculator") == "ohne")
    return 0


def quests(user: str) -> list[dict]:
    day = progress.today()
    rng = random.Random(f"{user}:{day}")
    chosen = [QUEST_POOL[0]] + rng.sample(QUEST_POOL[2:], 2)
    if rng.random() < 0.3:
        chosen[0] = QUEST_POOL[1]
    a, b = _day_bounds()
    out = []
    for qid, title, target in chosen:
        n = _quest_progress(user, qid, a, b)
        done = n >= target
        if done and db.once(f"quest:{user}:{day}:{qid}"):
            progress.add_xp(user, 20, f"Tagesmission: {title}", qid)
        out.append({"id": qid, "title": title, "target": target, "progress": min(n, target), "done": done, "xp": 20})
    return out


# ───────────── medals ─────────────

def _medal_defs(user: str) -> list[tuple[str, str, str, bool]]:
    n_ok = db.q1("SELECT COUNT(*) AS n FROM attempts WHERE user=? AND correct=1", user)["n"]
    streak = progress.streak(user)
    best_streak = max(streak, int(db.get_setting(f"best_streak:{user}", 0) or 0))
    if best_streak > int(db.get_setting(f"best_streak:{user}", 0) or 0):
        db.set_setting(f"best_streak:{user}", best_streak)
    won = progress.challenges_won(user)
    photos = db.q1("SELECT COUNT(*) AS n FROM reviews WHERE user=?", user)["n"]
    cards = db.q1("SELECT COUNT(*) AS n FROM card_log WHERE user=?", user)["n"]
    exams = db.q1("SELECT COUNT(*) AS n FROM exam_runs WHERE user=? AND finished_at IS NOT NULL", user)["n"]
    hours = [dt.datetime.fromtimestamp(r["created_at"], progress.TZ).hour for r in db.q("SELECT created_at FROM attempts WHERE user=? AND correct=1", user)]
    sm = progress.skill_mastery(user)
    cm = progress.chapter_mastery(sm)
    best_combo = int(db.get_setting(f"best_combo:{user}", 0) or 0)
    defs = [
        ("first", "🥇", "Erste richtige Aufgabe", n_ok >= 1),
        ("n50", "📗", "50 Aufgaben gelöst", n_ok >= 50),
        ("n100", "📘", "100 Aufgaben gelöst", n_ok >= 100),
        ("n250", "📙", "250 Aufgaben gelöst", n_ok >= 250),
        ("n500", "📕", "500 Aufgaben gelöst", n_ok >= 500),
        ("n1000", "🏛️", "1000 Aufgaben gelöst", n_ok >= 1000),
        ("streak3", "🔥", "3 Tage in Folge geübt", best_streak >= 3),
        ("streak7", "🔥", "7 Tage in Folge geübt", best_streak >= 7),
        ("streak21", "☄️", "21 Tage in Folge geübt", best_streak >= 21),
        ("combo10", "⚡", "10 richtige Antworten in Folge", best_combo >= 10),
        ("combo25", "🌩️", "25 richtige Antworten in Folge", best_combo >= 25),
        ("revanche1", "🎯", "Erste Revanche gewonnen", won >= 1),
        ("revanche10", "🏹", "10 Revanchen gewonnen", won >= 10),
        ("photo10", "📸", "10 Lösungswege korrigieren lassen", photos >= 10),
        ("cards100", "🧠", "100 Formelkarten wiederholt", cards >= 100),
        ("exam1", "📝", "Erste Prüfungssimulation", exams >= 1),
        ("night", "🦉", "Nach 22 Uhr eine Aufgabe gelöst", any(h >= 22 for h in hours)),
        ("early", "🐓", "Vor 7 Uhr eine Aufgabe gelöst", any(h < 7 for h in hours)),
    ]
    for i, (cid, v) in enumerate(cm.items()):
        title = content().chapters[cid]["title"]
        defs.append((f"chapter-{cid}", "⭐", f"Kapitel «{title}» sicher (≥ 80 %)", v >= 0.8))
    return defs


def medals(user: str) -> dict:
    """All medals with earned flag; newly earned ones are stored and returned in `new`."""
    have = {r["medal"]: r["created_at"] for r in db.q("SELECT medal, created_at FROM medals WHERE user=?", user)}
    out, new = [], []
    for mid, icon, title, ok in _medal_defs(user):
        if ok and mid not in have:
            db.ex("INSERT OR IGNORE INTO medals(user, medal, created_at) VALUES(?,?,?)", user, mid, time.time())
            have[mid] = time.time()
            new.append({"id": mid, "icon": icon, "title": title})
            progress.add_xp(user, 15, f"Medaille: {title}", mid)
        out.append({"id": mid, "icon": icon, "title": title, "earned": mid in have, "at": have.get(mid)})
    return {"medals": out, "new": new}


def after_attempt(user: str, correct: bool) -> dict:
    """Engagement info to send back after each answer."""
    c = combo(user) if correct else 0
    if c > int(db.get_setting(f"best_combo:{user}", 0) or 0):
        db.set_setting(f"best_combo:{user}", c)
    bonus = 0
    if correct and c >= 5 and c % 5 == 0:
        bonus = 10
        progress.add_xp(user, bonus, f"Combo ×{c}", "")
    g = daily_goal(user)
    m = medals(user)
    return {"combo": c, "combo_bonus": bonus, "goal": g, "new_medals": m["new"]}


# ───────────── formula cards ─────────────

def card_state(user: str) -> dict[str, dict]:
    return {r["card_id"]: r for r in db.q("SELECT * FROM cards WHERE user=?", user)}


def decks(user: str) -> list[dict]:
    c = content()
    st = card_state(user)
    t = time.time()
    out = []
    for cid, ch in c.chapters.items():
        cards = [k for k in c.cards.values() if k["chapter"] == cid]
        if not cards:
            continue
        due = sum(1 for k in cards if k["id"] not in st or st[k["id"]]["due_at"] <= t)
        learned = sum(1 for k in cards if k["id"] in st and st[k["id"]]["box"] >= 3)
        out.append({"chapter": cid, "title": ch["title"], "icon": ch.get("icon"), "optional": bool(ch.get("optional")),
                    "total": len(cards), "due": due, "learned": learned,
                    "new": sum(1 for k in cards if k["id"] not in st)})
    return out


def session_cards(user: str, chapter: str | None = None, skill: str | None = None, limit: int = 20) -> list[dict]:
    c = content()
    st = card_state(user)
    t = time.time()
    pool = [k for k in c.cards.values() if (not chapter or k["chapter"] == chapter) and (not skill or skill in k.get("skills", []))]
    due = [k for k in pool if k["id"] in st and st[k["id"]]["due_at"] <= t]
    due.sort(key=lambda k: st[k["id"]]["due_at"])
    new = [k for k in pool if k["id"] not in st]
    random.shuffle(new)
    later = [k for k in pool if k["id"] in st and st[k["id"]]["due_at"] > t]
    later.sort(key=lambda k: st[k["id"]]["box"])
    chosen = (due + new[: max(5, limit - len(due))] + later)[:limit]
    return [public_card(k, st.get(k["id"])) for k in chosen]


def public_card(k: dict, state: dict | None = None) -> dict:
    out = {key: k.get(key) for key in ("id", "chapter", "skills", "topic", "name", "formula", "symbols", "explain", "example", "pitfall")}
    out["drill"] = [{"prompt": d["prompt"], "answer": {kk: vv for kk, vv in d["answer"].items() if kk != "value"} |
                     ({"count": len(d["answer"]["value"])} if isinstance(d["answer"].get("value"), list) else {})}
                    for d in k.get("drill", [])]
    if state:
        out["box"] = state["box"]
    return out


def rate_card(user: str, card_id: str, grade: str, kind: str = "flip") -> dict:
    """grade: again | hard | good | easy"""
    st = db.q1("SELECT * FROM cards WHERE user=? AND card_id=?", user, card_id)
    box = st["box"] if st else 0
    lapses = st["lapses"] if st else 0
    if grade == "again":
        box, lapses = 0, lapses + 1
        due = time.time() + 600
    else:
        box = min(len(CARD_DAYS) - 1, box + {"hard": 0, "good": 1, "easy": 2}.get(grade, 1))
        due = time.time() + max(1, CARD_DAYS[box]) * DAY * (0.6 if grade == "hard" else 1)
    db.ex("INSERT INTO cards(user, card_id, box, due_at, reviews, lapses, last_at) VALUES(?,?,?,?,1,?,?) "
          "ON CONFLICT(user, card_id) DO UPDATE SET box=excluded.box, due_at=excluded.due_at, reviews=reviews+1, lapses=excluded.lapses, last_at=excluded.last_at",
          user, card_id, box, due, lapses, time.time())
    db.insert("card_log", user=user, card_id=card_id, grade=grade, kind=kind, created_at=time.time())
    xp = {"again": 0, "hard": 1, "good": 2, "easy": 2}.get(grade, 1)
    today_card_xp = db.q1("SELECT COALESCE(SUM(amount),0) AS s FROM xp WHERE user=? AND reason='Formelkarte' AND created_at>=?",
                          user, _day_bounds()[0])["s"]
    if today_card_xp < 80:
        progress.add_xp(user, xp, "Formelkarte", card_id)
    else:
        xp = 0
    return {"box": box, "due_at": due, "xp": xp}


def formulas_for(ex: dict) -> list[dict]:
    c = content()
    skills = ex.get("skills", [])
    cards = [k for k in c.cards.values() if set(k.get("skills", [])) & set(skills)]
    cards.sort(key=lambda k: min(skills.index(s) for s in k["skills"] if s in skills))
    return [public_card(k) for k in cards[:8]]
