"""Mastery, XP, ranks (Zivilschutz), challenges (Revanche) and KPIs."""
from __future__ import annotations

import datetime as dt
import json
import time
from collections import defaultdict
from zoneinfo import ZoneInfo

from . import db
from .config import CFG
from .content import content

TZ = ZoneInfo(CFG.tz)
DAY = 86400

# Dienstgrade im Zivilschutz (Anhang 1, Art. 24/28 ZSV BE, Stand 2017), aufsteigend.
RANKS = [
    {"id": "rekrut", "name": "Rekrut", "abbr": "Rekr", "badge": None, "xp": 0, "req": {}},
    {"id": "sdt", "name": "Soldat", "abbr": "Sdt", "xp": 100, "req": {}},
    {"id": "gfr", "name": "Gefreiter", "abbr": "Gfr", "xp": 300, "req": {"mastered_skills": 3}},
    {"id": "kpl", "name": "Korporal", "abbr": "Kpl", "xp": 700, "req": {"chapters_at": [1, 0.6]}},
    {"id": "wm", "name": "Wachtmeister", "abbr": "Wm", "xp": 1200, "req": {"chapters_at": [2, 0.6]}},
    {"id": "four", "name": "Fourier", "abbr": "Four", "xp": 1800, "req": {"chapters_at": [3, 0.6], "challenges_won": 3}},
    {"id": "hptfw", "name": "Hauptfeldweibel", "abbr": "Hptfw", "xp": 2600, "req": {"chapters_at": [4, 0.6], "challenges_won": 8}},
    {"id": "lt", "name": "Leutnant", "abbr": "Lt", "xp": 3500, "req": {"chapters_at": [6, 0.6]}},
    {"id": "oblt", "name": "Oberleutnant", "abbr": "Oblt", "xp": 4500, "req": {"chapters_at": [6, 0.7], "exam_at": [1, 0.6]}},
    {"id": "hptm", "name": "Hauptmann", "abbr": "Hptm", "xp": 5800, "req": {"chapters_at": [6, 0.75], "exam_at": [1, 0.7]}},
    {"id": "maj", "name": "Major", "abbr": "Maj", "xp": 7200, "req": {"chapters_at": [6, 0.8], "exam_at": [2, 0.75]}},
    {"id": "oberstlt", "name": "Oberstleutnant", "abbr": "Oberstlt", "xp": 9000, "req": {"chapters_at": [6, 0.85], "exam_at": [2, 0.85]}},
]
for r in RANKS:
    r.setdefault("badge", f"/static/badges/{r['id']}.png")

MASTERED = 0.8
LEITNER_DAYS = [1, 3, 7]  # Revanche: due after 1 day, then 3, then 7; beaten after 2 wins in a row
WINS_TO_BEAT = 2


def now() -> float:
    return time.time()


def today(ts: float | None = None) -> str:
    return dt.datetime.fromtimestamp(ts or now(), TZ).date().isoformat()


# ───────────── attempt scoring ─────────────

def attempt_score(correct: bool, status: str, hints: int, solution_shown: bool) -> float:
    if solution_shown:
        return 0.0
    if correct:
        return max(0.4, 1.0 - 0.2 * hints)
    if status == "fast":
        return 0.4
    return 0.0


def xp_for(ex: dict, score: float, correct: bool) -> int:
    base = 10 * int(ex.get("difficulty", 2) or 2)
    if not correct:
        return 1
    return max(2, round(base * score))


def add_xp(user: str, amount: int, reason: str, ref: str = ""):
    if amount:
        db.insert("xp", user=user, amount=amount, reason=reason, ref=ref, created_at=now())


def record_activity(user: str, seconds: int = 0):
    d = today()
    db.ex("INSERT INTO activity(user, day, seconds) VALUES(?,?,?) ON CONFLICT(user, day) DO UPDATE SET seconds=seconds+excluded.seconds",
          user, d, int(seconds))


# ───────────── mastery ─────────────

def _attempt_rows(user: str, until: float | None = None) -> list[dict]:
    sql = "SELECT * FROM attempts WHERE user=? AND status!='format'"
    args = [user]
    if until:
        sql += " AND created_at<=?"
        args.append(until)
    return db.q(sql + " ORDER BY created_at DESC", *args)


def skill_mastery(user: str, until: float | None = None) -> dict[str, dict]:
    """Per skill: mastery 0..1, number of attempts, accuracy, last practice, hints per attempt."""
    rows = _attempt_rows(user, until)
    per: dict[str, list[tuple[float, float, dict]]] = defaultdict(list)
    for r in rows:
        if r["status"] == "manuell" and r["score"] is None:
            continue
        skills = db.loads(r["skills"], [])
        for i, s in enumerate(skills):
            per[s].append((1.0 if i == 0 else 0.5, r["score"] or 0.0, r))
    t_now = until or now()
    out = {}
    for sid in content().skills:
        items = per.get(sid, [])[:10]
        if not items:
            out[sid] = {"mastery": 0.0, "n": 0, "accuracy": None, "last": None, "hints": 0, "level": "neu"}
            continue
        wsum = ssum = 0.0
        for k, (w, s, _) in enumerate(items):
            ww = w * (0.8 ** k)
            wsum += ww
            ssum += ww * s
        acc = ssum / wsum
        n_eff = sum(w for w, _, _ in per[sid])
        conf = min(1.0, n_eff / 4)
        last = items[0][2]["created_at"]
        decay = 0.9 if t_now - last > 21 * DAY else 1.0
        m = acc * conf * decay
        out[sid] = {
            "mastery": round(m, 3),
            "n": len(per[sid]),
            "accuracy": round(sum(1 for _, s, r in per[sid] if r["correct"]) / len(per[sid]), 3),
            "last": last,
            "hints": round(sum(r["hints"] or 0 for _, _, r in per[sid]) / len(per[sid]), 2),
            "level": "sicher" if m >= MASTERED else ("aufbau" if m >= 0.5 else "unsicher"),
        }
    return out


def core_chapters() -> dict:
    """Chapters that count for ranks and exam readiness (the optional Grundlagen do not)."""
    return {cid: c for cid, c in content().chapters.items() if not c.get("optional")}


def core_skill_ids() -> set[str]:
    return {s["id"] for c in core_chapters().values() for s in c["skills"]}


def chapter_mastery(sm: dict[str, dict], include_optional: bool = False) -> dict[str, float]:
    out = {}
    chapters = content().chapters if include_optional else core_chapters()
    for cid, c in chapters.items():
        vals = [sm[s["id"]]["mastery"] for s in c["skills"]]
        out[cid] = round(sum(vals) / len(vals), 3) if vals else 0.0
    return out


# ───────────── XP / ranks ─────────────

def total_xp(user: str) -> int:
    r = db.q1("SELECT COALESCE(SUM(amount),0) AS s FROM xp WHERE user=?", user)
    return int(r["s"])


def exam_results(user: str) -> list[float]:
    rows = db.q("SELECT score, max_score FROM exam_runs WHERE user=? AND finished_at IS NOT NULL AND max_score>0", user)
    return [r["score"] / r["max_score"] for r in rows]


def challenges_won(user: str) -> int:
    return db.q1("SELECT COUNT(*) AS n FROM challenges WHERE user=? AND status='beaten'", user)["n"]


def _req_status(req: dict, xp: int, need_xp: int, sm, cm, won, exams) -> list[dict]:
    checks = [{"text": f"{need_xp} XP", "ok": xp >= need_xp, "progress": min(1, xp / need_xp) if need_xp else 1}]
    if "mastered_skills" in req:
        core = core_skill_ids()
        n = sum(1 for k, v in sm.items() if k in core and v["mastery"] >= MASTERED)
        k = req["mastered_skills"]
        checks.append({"text": f"{k} Themen sicher beherrscht", "ok": n >= k, "progress": min(1, n / k)})
    if "chapters_at" in req:
        k, th = req["chapters_at"]
        n = sum(1 for v in cm.values() if v >= th)
        label = "alle 6 Hauptkapitel" if k == 6 else (f"{k} Kapitel" if k > 1 else "1 Kapitel")
        checks.append({"text": f"{label} zu mindestens {round(th * 100)} % beherrscht", "ok": n >= k, "progress": min(1, n / k)})
    if "challenges_won" in req:
        k = req["challenges_won"]
        checks.append({"text": f"{k} Revanchen gewonnen", "ok": won >= k, "progress": min(1, won / k)})
    if "exam_at" in req:
        k, th = req["exam_at"]
        n = sum(1 for e in exams if e >= th)
        checks.append({"text": f"{k}× Prüfungssimulation mit mindestens {round(th * 100)} %", "ok": n >= k, "progress": min(1, n / k)})
    return checks


def rank_state(user: str, sm=None, cm=None) -> dict:
    sm = sm or skill_mastery(user)
    cm = cm or chapter_mastery(sm)
    xp = total_xp(user)
    won = challenges_won(user)
    exams = exam_results(user)
    current = 0
    for i, r in enumerate(RANKS[1:], start=1):
        checks = _req_status(r["req"], xp, r["xp"], sm, cm, won, exams)
        if all(c["ok"] for c in checks):
            current = i
        else:
            break
    stored = db.get_setting(f"rank:{user}", 0)
    promoted = None
    if current > stored:
        db.set_setting(f"rank:{user}", current)
        promoted = RANKS[current]
        if stored is not None:
            from . import notify
            notify.promotion(user, RANKS[current])
    nxt = RANKS[current + 1] if current + 1 < len(RANKS) else None
    return {
        "xp": xp,
        "index": current,
        "rank": RANKS[current],
        "next": nxt,
        "next_checks": _req_status(nxt["req"], xp, nxt["xp"], sm, cm, won, exams) if nxt else [],
        "promoted": promoted,
        "ranks": [{k: v for k, v in r.items() if k != "req"} | {"checks": _req_status(r["req"], xp, r["xp"], sm, cm, won, exams)} for r in RANKS],
    }


# ───────────── challenges (Revanche) ─────────────

def on_attempt(user: str, ex: dict, part: str, correct: bool, score: float, mode: str, attempt_id: int, error: str | None,
               challenge_id: int | None = None):
    """Keep the Revanche list in sync with a new attempt.

    Generated exercises come back in the Revanche as a fresh variant (same generator, new numbers);
    the variant's attempt then carries the challenge_id of the original."""
    skill = (ex.get("skills") or [None])[0]
    if challenge_id:
        ch = db.q1("SELECT * FROM challenges WHERE id=? AND user=?", challenge_id, user)
        if ch and not correct:
            t = now()
            db.update("challenges", ch["id"], box=0, due_at=t + LEITNER_DAYS[0] * DAY, wins=0, fails=ch["fails"] + 1,
                      last_error=error, updated_at=t)
            return "lost"
    else:
        ch = db.q1("SELECT * FROM challenges WHERE user=? AND exercise_id=? AND part=?", user, ex["id"], part)
    t = now()
    if not correct or score < 0.5:
        if ch:
            db.update("challenges", ch["id"], box=0, due_at=t + LEITNER_DAYS[0] * DAY, wins=0, fails=ch["fails"] + 1,
                      status="open", last_error=error, updated_at=t)
        else:
            db.insert("challenges", user=user, exercise_id=ex["id"], part=part, skill=skill, chapter=ex.get("chapter"),
                      box=0, due_at=t + LEITNER_DAYS[0] * DAY, wins=0, fails=1, status="open",
                      origin_attempt=attempt_id, last_error=error, created_at=t, updated_at=t)
        return None
    if ch and ch["status"] == "open" and mode == "challenge":
        wins = ch["wins"] + 1
        if wins >= WINS_TO_BEAT:
            db.update("challenges", ch["id"], wins=wins, status="beaten", updated_at=t)
            add_xp(user, 30, "Revanche gewonnen", ex["id"])
            return "beaten"
        box = min(ch["box"] + 1, len(LEITNER_DAYS) - 1)
        db.update("challenges", ch["id"], wins=wins, box=box, due_at=t + LEITNER_DAYS[box] * DAY, updated_at=t)
        return "win"
    return None


def challenge_list(user: str, only_due=False) -> list[dict]:
    rows = db.q("SELECT * FROM challenges WHERE user=? ORDER BY status, due_at", user)
    c = content()
    out = []
    for r in rows:
        if only_due and (r["status"] != "open" or r["due_at"] > now()):
            continue
        ex = c.get(r["exercise_id"])
        r["title"] = ex["title"] if ex else r["exercise_id"]
        r["skill_title"] = c.skills.get(r["skill"], {}).get("title", r["skill"])
        r["due"] = r["due_at"] <= now()
        out.append(r)
    return out


# ───────────── KPIs / history ─────────────

def streak(user: str) -> int:
    days = {r["day"] for r in db.q("SELECT day FROM activity WHERE user=?", user)}
    n, d = 0, dt.datetime.now(TZ).date()
    if d.isoformat() not in days:
        d -= dt.timedelta(days=1)
    while d.isoformat() in days:
        n += 1
        d -= dt.timedelta(days=1)
    return n


def week_stats(user: str, start: float, end: float) -> dict:
    rows = db.q("SELECT correct, score, duration_s, exercise_id FROM attempts WHERE user=? AND created_at>=? AND created_at<? AND status!='format'",
                user, start, end)
    n = len(rows)
    return {
        "parts": n,
        "exercises": len({r["exercise_id"] for r in rows}),
        "correct": sum(1 for r in rows if r["correct"]),
        "accuracy": round(sum(1 for r in rows if r["correct"]) / n, 3) if n else None,
        "minutes": round(sum((r["duration_s"] or 0) for r in rows) / 60),
    }


def history(user: str, days: int = 30) -> list[dict]:
    """Overall mastery and activity per day (for the progress chart)."""
    out = []
    end = dt.datetime.now(TZ).replace(hour=23, minute=59, second=59)
    first = db.q1("SELECT MIN(created_at) AS t FROM attempts WHERE user=?", user)["t"]
    for i in range(days - 1, -1, -1):
        d_end = end - dt.timedelta(days=i)
        ts = d_end.timestamp()
        if first is None or ts < first - DAY:
            out.append({"day": d_end.date().isoformat(), "mastery": 0, "solved": 0})
            continue
        sm = skill_mastery(user, until=ts)
        core = core_skill_ids()
        vals = [v["mastery"] for k, v in sm.items() if k in core]
        solved = db.q1("SELECT COUNT(*) AS n FROM attempts WHERE user=? AND correct=1 AND created_at>? AND created_at<=?",
                       user, ts - DAY, ts)["n"]
        out.append({"day": d_end.date().isoformat(), "mastery": round(sum(vals) / len(vals), 3), "solved": solved})
    return out


# Points per chapter in the Probeprüfungen HS 2024 + HS 2025.
DEFAULT_WEIGHTS = {"k1": 5, "k2": 33, "k3": 34, "k4": 59, "k5": 39, "k6": 34}


def exam_readiness(cm: dict[str, float]) -> float:
    weights = db.get_setting("chapter_weights") or DEFAULT_WEIGHTS
    tot = sum(weights.get(c, 1) for c in cm)
    return round(sum(cm[c] * weights.get(c, 1) for c in cm) / tot, 3) if tot else 0.0


def dashboard(user: str) -> dict:
    sm = skill_mastery(user)
    cm = chapter_mastery(sm)
    t = now()
    this_week = week_stats(user, t - 7 * DAY, t)
    last_week = week_stats(user, t - 14 * DAY, t - 7 * DAY)
    rank = rank_state(user, sm, cm)
    c = content()
    core = core_skill_ids()
    weak = sorted(((sid, v) for sid, v in sm.items() if v["n"] > 0 and v["mastery"] < 0.6), key=lambda kv: kv[1]["mastery"])[:4]
    fresh = [sid for sid, v in sm.items() if v["n"] == 0 and sid in core][:3]
    core_sm = {k: v for k, v in sm.items() if k in core}
    due = challenge_list(user, only_due=True)
    return {
        "rank": rank,
        "streak": streak(user),
        "week": this_week,
        "last_week": last_week,
        "skills": sm,
        "chapters": cm,
        "basics": {cid: v for cid, v in chapter_mastery(sm, True).items() if cid not in cm},
        "overall": round(sum(v["mastery"] for v in core_sm.values()) / max(1, len(core_sm)), 3),
        "readiness": exam_readiness(cm),
        "mastered": sum(1 for v in core_sm.values() if v["mastery"] >= MASTERED),
        "skills_total": len(core_sm),
        "challenges_due": len(due),
        "challenges_open": db.q1("SELECT COUNT(*) AS n FROM challenges WHERE user=? AND status='open'", user)["n"],
        "challenges_won": challenges_won(user),
        "recommend": {
            "weak": [{"skill": sid, "title": c.skills[sid]["title"], "mastery": v["mastery"]} for sid, v in weak],
            "new": [{"skill": sid, "title": c.skills[sid]["title"]} for sid in fresh],
        },
        "dates": dates(),
    }


def dates() -> dict:
    sessions = db.get_setting("session_dates") or ["2026-12-04", "2027-01-08", "2027-02-12", "2027-03-12"]
    exam = db.get_setting("exam_date") or "2027-03-19"
    d = dt.datetime.now(TZ).date()
    upcoming = [s for s in sessions if s >= d.isoformat()]
    return {
        "sessions": sessions,
        "next_session": upcoming[0] if upcoming else None,
        "days_to_session": (dt.date.fromisoformat(upcoming[0]) - d).days if upcoming else None,
        "exam": exam,
        "days_to_exam": (dt.date.fromisoformat(exam) - d).days if exam else None,
    }


def error_stats(user: str, since: float = 0) -> dict:
    rows = db.q("SELECT error_category, skills FROM attempts WHERE user=? AND correct=0 AND created_at>=? AND error_category IS NOT NULL",
                user, since)
    cats = defaultdict(int)
    by_skill = defaultdict(lambda: defaultdict(int))
    for r in rows:
        cats[r["error_category"]] += 1
        s = (db.loads(r["skills"], []) or [None])[0]
        by_skill[s][r["error_category"]] += 1
    return {"categories": dict(cats), "by_skill": {k: dict(v) for k, v in by_skill.items()}}


def json_safe(o):
    return json.loads(json.dumps(o, default=str))
