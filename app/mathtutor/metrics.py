"""Mathe-Trainer metrics: the standard Neo app telemetry (neo_telemetry) plus app numbers.

Served on $NEO_METRICS_PORT (Neo sets it only while monitoring collects); see main.run().
Labels are small fixed sets: unknown values become "other", never user input.

Features (neo_app_feature_used_total{feature}), the fixed list:
  next_exercise, similar_exercise, answer_checked, hint, solution_shown, formula_drill, card_rated,
  photo_uploaded, photo_review, chat_started, tutor_message, challenge_started,
  exam_started, exam_submitted, error_reported, feedback_sent,
  coach_briefing, coach_override, coach_settings_saved, telegram_test
AI calls (neo_app_llm_*{provider="claude_code", feature}): one per tutor turn, feature = tutor mode
  (chat, hint, check_step, explain, explain_back, solution, correct, coach) or grade (exam grading).
Jobs (neo_app_job_*{job}): grading (one exam exercise graded from photos), notifications (Telegram tick).
"""
from __future__ import annotations

import logging
import threading
import time

import httpx
from prometheus_client import REGISTRY, Counter, Histogram
from prometheus_client.core import GaugeMetricFamily

from . import neo_telemetry as tel
from .config import CFG

log = logging.getLogger("mathtutor.metrics")

FEATURES = {
    "next_exercise", "similar_exercise", "answer_checked", "hint", "solution_shown", "formula_drill", "card_rated",
    "photo_uploaded", "photo_review", "chat_started", "tutor_message", "challenge_started",
    "exam_started", "exam_submitted", "error_reported", "feedback_sent",
    "coach_briefing", "coach_override", "coach_settings_saved", "telegram_test",
}
TUTOR_FEATURES = {"chat", "hint", "check_step", "explain", "explain_back", "solution", "correct", "coach", "grade"}
MODES = {"practice", "challenge", "exam", "session"}
TOOLS = {"python", "check_answer", "equivalent", "plot", "submit_review"}
RESULTS = {"richtig": "correct", "falsch": "wrong", "fast": "close"}

ANSWERS = Counter("mathtutor_answers", "Answers checked (typed or corrected from a photo).",
                  ["role", "mode", "chapter", "source", "result"])
WRONG = Counter("mathtutor_wrong_answers", "Wrong answers by mistake type.", ["chapter", "error_category"])
DISAGREEMENTS = Counter("mathtutor_review_disagreements", "Photo corrections where the AI and the SymPy checker disagree.",
                        ["chapter"])
REVIEWS = Counter("mathtutor_reviews", "Photo corrections by outcome (structured = the tutor handed in a result).",
                  ["kind", "outcome"])
TOOL_CALLS = Counter("mathtutor_tutor_tool_calls", "Maths tools the tutor used.", ["tool"])
FIRST_TEXT = Histogram("mathtutor_tutor_first_text_seconds", "Time until the tutor's first words.", ["feature"],
                       buckets=(1, 2, 3, 5, 8, 13, 20, 30, 60, 120))
TUTOR_TURNS = Histogram("mathtutor_tutor_turn_steps", "Model steps (turns) per tutor answer; 25 is the limit.", ["feature"],
                        buckets=(1, 2, 4, 8, 12, 16, 20, 25))
PRACTICE = Counter("mathtutor_practice_seconds", "Practice time reported by the browser.", ["role"])
TELEGRAM = Counter("mathtutor_telegram_messages", "Telegram messages to the coach by result.", ["result"])


def role(user: str) -> str:
    return "student" if user and user == (CFG.student_user or "").lower() else "coach"


def feature(name: str) -> None:
    tel.feature(name if name in FEATURES else "other")


def answer(user: str, mode: str, chapter: str | None, source: str, status: str, error_category: str | None = None) -> None:
    result = RESULTS.get(status)
    if result is None:
        return
    chapter = chapter or "other"
    ANSWERS.labels(role(user), mode if mode in MODES else "other", chapter, source, result).inc()
    if result != "correct" and role(user) == "student":
        from .content import content
        cat = error_category if error_category in content().error_categories else ("none" if not error_category else "other")
        WRONG.labels(chapter, cat).inc()


def tool_call(name: str) -> None:
    TOOL_CALLS.labels(name if name in TOOLS else "other").inc()


def tutor_feature(mode: str) -> str:
    f = "coach" if mode == "admin" else mode
    return f if f in TUTOR_FEATURES else "chat"


# ───────────── state gauges, computed at scrape time from SQLite ─────────────

class StateCollector:
    """How the student stands (mastery, readiness, dates) and what waits (gradings, reports). Cached 60 s."""

    TTL = 60

    def __init__(self):
        self._lock = threading.Lock()
        self._at = 0.0
        self._cache: list = []

    def describe(self):
        return []  # computed lazily; keeps registration free of DB access

    def collect(self):
        with self._lock:
            if time.time() - self._at > self.TTL:
                try:
                    self._cache = list(self._compute())
                except Exception:  # noqa: BLE001
                    log.exception("computing state metrics failed", extra={"event": "metrics_failed"})
                    self._cache = []
                self._at = time.time()
            return list(self._cache)

    @staticmethod
    def _g(name: str, doc: str, value, labels: dict | None = None):
        g = GaugeMetricFamily(name, doc, labels=list(labels) if labels else None)
        if value is not None:
            g.add_metric(list(labels.values()) if labels else [], float(value))
        return g

    def _compute(self):
        from . import db, progress
        g = self._g
        t = time.time()

        # Waiting work, for every user.
        pending = 0
        for r in db.q("SELECT details FROM exam_runs WHERE finished_at IS NOT NULL AND details LIKE '%\"pending\"%'"):
            pending += sum(1 for v in (db.loads(r["details"], {}).get("grading") or {}).values() if v.get("status") == "pending")
        yield g("mathtutor_exam_gradings_pending", "Exam exercises whose photo grading has not finished.", pending)
        yield g("mathtutor_reports_open", "Exercise error reports the coach has not handled.",
                db.q1("SELECT COUNT(*) AS n FROM reports WHERE status='offen'")["n"])
        yield g("mathtutor_feedback_open", "Feedback messages the coach has not handled.",
                db.q1("SELECT COUNT(*) AS n FROM feedback WHERE status!='erledigt'")["n"])
        yield g("mathtutor_tutor_signed_in", "1 when the tutor container has Claude credentials.", self._tutor_signed_in())
        yield g("mathtutor_telegram_configured", "1 when Telegram messages to the coach are set up.",
                1 if CFG.telegram_token and CFG.telegram_chat else 0)

        dates = progress.dates()
        yield g("mathtutor_days_to_exam", "Days until the exam.", dates.get("days_to_exam"))
        yield g("mathtutor_days_to_session", "Days until the next study session with the coach.", dates.get("days_to_session"))

        u = (CFG.student_user or "").lower()
        if not u:
            return
        sm = progress.skill_mastery(u)
        cm = progress.chapter_mastery(sm)
        core = progress.core_skill_ids()
        core_sm = [v for k, v in sm.items() if k in core]
        yield g("mathtutor_exam_readiness_ratio", "Exam readiness: chapter mastery weighted by exam points (0..1).",
                progress.exam_readiness(cm))
        yield g("mathtutor_overall_mastery_ratio", "Average mastery of the exam topics (0..1).",
                sum(v["mastery"] for v in core_sm) / max(1, len(core_sm)))
        yield g("mathtutor_skills_mastered", "Exam topics mastered.", sum(1 for v in core_sm if v["mastery"] >= progress.MASTERED))
        yield g("mathtutor_skills_total", "Exam topics.", len(core_sm))
        chap = GaugeMetricFamily("mathtutor_chapter_mastery_ratio", "Mastery per chapter (0..1).", labels=["chapter"])
        for cid, v in progress.chapter_mastery(sm, include_optional=True).items():
            chap.add_metric([cid], v)
        yield chap
        skill = GaugeMetricFamily("mathtutor_skill_mastery_ratio", "Mastery per practised topic (0..1).",
                                  labels=["chapter", "skill"])
        from .content import content
        skills = content().skills
        for sid, v in sm.items():
            if v["n"]:
                skill.add_metric([skills.get(sid, {}).get("chapter", "other"), sid], v["mastery"])
        yield skill
        week = progress.week_stats(u, t - 7 * progress.DAY, t)
        yield g("mathtutor_accuracy_7d_ratio", "Share of the student's answers that were right in the last 7 days.",
                week["accuracy"])
        yield g("mathtutor_answers_7d", "The student's answers in the last 7 days.", week["parts"])
        yield g("mathtutor_student_xp", "The student's XP.", progress.total_xp(u))
        yield g("mathtutor_streak_days", "Days in a row the student practised.", progress.streak(u))
        last = db.q1("SELECT MAX(created_at) AS t FROM attempts WHERE user=?", u)["t"]
        yield g("mathtutor_last_practice_timestamp_seconds", "When the student last answered an exercise.", last)
        ch = GaugeMetricFamily("mathtutor_challenges", "Revanche re-tests by state.", labels=["state"])
        ch.add_metric(["open"], db.q1("SELECT COUNT(*) AS n FROM challenges WHERE user=? AND status='open'", u)["n"])
        ch.add_metric(["due"], db.q1("SELECT COUNT(*) AS n FROM challenges WHERE user=? AND status='open' AND due_at<=?", u, t)["n"])
        ch.add_metric(["won"], progress.challenges_won(u))
        yield ch
        ex = db.q1("SELECT score, max_score, details FROM exam_runs WHERE user=? AND finished_at IS NOT NULL "
                   "AND details NOT LIKE '%\"pending\"%' ORDER BY id DESC LIMIT 1", u)
        yield g("mathtutor_last_exam_score_ratio", "Score of the last finished exam simulation (0..1).",
                (ex["score"] or 0) / ex["max_score"] if ex and ex["max_score"] else None)

    @staticmethod
    def _tutor_signed_in():
        try:
            r = httpx.get(f"{CFG.agent_url}/health", timeout=3)
            return 1 if r.json().get("auth") else 0
        except (httpx.HTTPError, ValueError) as e:
            log.warning("tutor health check failed", extra={"event": "agent_unreachable", "error": type(e).__name__})
            return None


def start(version: str) -> bool:
    """Metrics endpoint (only when Neo set NEO_METRICS_PORT) and the state collector."""
    if not tel.start_metrics():
        return False
    tel.build_info(version)
    REGISTRY.register(StateCollector())
    return True
