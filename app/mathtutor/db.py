"""SQLite storage. One file in the data directory (appdata)."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager

from .config import CFG

SCHEMA = """
PRAGMA journal_mode=DELETE;
CREATE TABLE IF NOT EXISTS attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user TEXT NOT NULL,
  exercise_id TEXT NOT NULL,
  part TEXT NOT NULL DEFAULT '',
  chapter TEXT,
  skills TEXT,               -- json list, first = main skill
  mode TEXT NOT NULL,        -- practice | challenge | exam | session
  input TEXT,
  status TEXT,               -- richtig | falsch | fast | format | manuell
  score REAL,                -- 0..1 (after hint/solution penalties)
  correct INTEGER,           -- 1 if the answer itself was right
  hints INTEGER DEFAULT 0,
  solution_shown INTEGER DEFAULT 0,
  error_category TEXT,
  feedback TEXT,
  source TEXT DEFAULT 'auto',  -- auto | photo | tutor | admin
  review_id INTEGER,
  duration_s INTEGER,
  session_id INTEGER,
  exam_run_id INTEGER,
  admin_note TEXT,
  created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS attempts_user ON attempts(user, created_at);
CREATE INDEX IF NOT EXISTS attempts_ex ON attempts(exercise_id);

CREATE TABLE IF NOT EXISTS hints (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user TEXT, exercise_id TEXT, part TEXT, level INTEGER, kind TEXT, created_at REAL
);

CREATE TABLE IF NOT EXISTS photos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user TEXT, path TEXT, mime TEXT, exercise_id TEXT, created_at REAL
);

CREATE TABLE IF NOT EXISTS reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user TEXT, exercise_id TEXT, photo_ids TEXT, result TEXT, status TEXT,
  mode TEXT, chat_id INTEGER, created_at REAL, admin_override TEXT
);

CREATE TABLE IF NOT EXISTS chats (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user TEXT, title TEXT, agent_session TEXT, exercise_id TEXT, kind TEXT DEFAULT 'chat',
  created_at REAL, updated_at REAL
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id INTEGER, role TEXT, content TEXT, attachments TEXT, meta TEXT, created_at REAL
);
CREATE INDEX IF NOT EXISTS messages_chat ON messages(chat_id, id);

CREATE TABLE IF NOT EXISTS xp (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user TEXT, amount INTEGER, reason TEXT, ref TEXT, created_at REAL
);

CREATE TABLE IF NOT EXISTS challenges (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user TEXT, exercise_id TEXT, part TEXT, skill TEXT, chapter TEXT,
  box INTEGER DEFAULT 0, due_at REAL, wins INTEGER DEFAULT 0, fails INTEGER DEFAULT 1,
  status TEXT DEFAULT 'open',  -- open | beaten
  origin_attempt INTEGER, last_error TEXT,
  created_at REAL, updated_at REAL,
  UNIQUE(user, exercise_id, part)
);

CREATE TABLE IF NOT EXISTS assignments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT, description TEXT, skills TEXT, exercise_ids TEXT, target INTEGER,
  due_at REAL, created_at REAL, archived INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT, date TEXT, notes TEXT, plan TEXT, briefing TEXT,
  started_at REAL, ended_at REAL, created_at REAL
);

CREATE TABLE IF NOT EXISTS exam_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user TEXT, exam_id TEXT, part_index INTEGER, exercise_ids TEXT, started_at REAL, deadline REAL,
  finished_at REAL, score REAL, max_score REAL, details TEXT
);

CREATE TABLE IF NOT EXISTS activity (
  user TEXT, day TEXT, seconds INTEGER DEFAULT 0, PRIMARY KEY(user, day)
);

CREATE TABLE IF NOT EXISTS reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user TEXT, exercise_id TEXT, part TEXT, kind TEXT, comment TEXT, context TEXT,
  status TEXT DEFAULT 'offen',   -- offen | erledigt | abgelehnt
  admin_note TEXT, created_at REAL, resolved_at REAL
);

CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user TEXT, kind TEXT, text TEXT, photo_ids TEXT, context TEXT,
  status TEXT DEFAULT 'neu',   -- neu | in_arbeit | erledigt
  admin_note TEXT, created_at REAL, updated_at REAL
);

CREATE TABLE IF NOT EXISTS server_errors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user TEXT, method TEXT, path TEXT, error TEXT, traceback TEXT, created_at REAL
);

CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS sent (key TEXT PRIMARY KEY, created_at REAL);
"""

_local = threading.local()
_lock = threading.Lock()


def conn() -> sqlite3.Connection:
    c = getattr(_local, "c", None)
    if c is None:
        c = sqlite3.connect(CFG.db_path, timeout=30, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        _local.c = c
    return c


def init():
    with _lock:
        c = conn()
        c.executescript(SCHEMA)
        c.commit()


@contextmanager
def tx():
    c = conn()
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise


def q(sql, *args) -> list[dict]:
    return [dict(r) for r in conn().execute(sql, args).fetchall()]


def q1(sql, *args) -> dict | None:
    r = conn().execute(sql, args).fetchone()
    return dict(r) if r else None


def ex(sql, *args) -> int:
    with tx() as c:
        cur = c.execute(sql, args)
        return cur.lastrowid


def insert(table: str, **kw) -> int:
    kw = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in kw.items()}
    cols = ",".join(kw)
    qs = ",".join("?" * len(kw))
    return ex(f"INSERT INTO {table} ({cols}) VALUES ({qs})", *kw.values())


def update(table: str, rid: int, **kw):
    kw = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in kw.items()}
    sets = ",".join(f"{k}=?" for k in kw)
    ex(f"UPDATE {table} SET {sets} WHERE id=?", *kw.values(), rid)


def get_setting(key, default=None):
    r = q1("SELECT value FROM settings WHERE key=?", key)
    if not r:
        return default
    try:
        return json.loads(r["value"])
    except Exception:  # noqa: BLE001
        return r["value"]


def set_setting(key, value):
    ex("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
       key, json.dumps(value, ensure_ascii=False))


def once(key: str) -> bool:
    """True the first time a key is seen (for notifications that must not repeat)."""
    try:
        ex("INSERT INTO sent(key, created_at) VALUES(?,?)", key, time.time())
        return True
    except sqlite3.IntegrityError:
        return False


def loads(v, default=None):
    if v is None:
        return default
    try:
        return json.loads(v)
    except Exception:  # noqa: BLE001
        return default
