"""Runtime configuration from environment variables (set by the Neo module)."""
from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass, field


def _list(v: str | None) -> list[str]:
    return [s.strip() for s in (v or "").split(",") if s.strip()]


@dataclass
class Config:
    data_dir: pathlib.Path = field(default_factory=lambda: pathlib.Path(os.environ.get("MT_DATA_DIR", "./data")))
    content_dir: pathlib.Path = field(default_factory=lambda: pathlib.Path(
        os.environ.get("MT_CONTENT_DIR", str(pathlib.Path(__file__).resolve().parents[2] / "content"))))
    static_dir: pathlib.Path = field(default_factory=lambda: pathlib.Path(
        os.environ.get("MT_STATIC_DIR", str(pathlib.Path(__file__).resolve().parent / "static"))))
    admin_users: list[str] = field(default_factory=lambda: _list(os.environ.get("MT_ADMIN_USERS")))
    student_user: str = field(default_factory=lambda: os.environ.get("MT_STUDENT_USER", ""))
    student_name: str = field(default_factory=lambda: os.environ.get("MT_STUDENT_NAME", "") or os.environ.get("MT_STUDENT_USER", "").capitalize() or "Student")
    # Only for local development without tinyauth in front: act as this user.
    dev_user: str | None = field(default_factory=lambda: os.environ.get("MT_DEV_USER") or None)
    agent_url: str = field(default_factory=lambda: os.environ.get("MT_AGENT_URL", "http://127.0.0.1:8100"))
    agent_token: str = field(default_factory=lambda: os.environ.get("MT_AGENT_TOKEN", ""))
    model: str = field(default_factory=lambda: os.environ.get("MT_MODEL", "claude-opus-5-5"))
    telegram_token: str = field(default_factory=lambda: os.environ.get("MT_TELEGRAM_TOKEN", ""))
    telegram_chat: str = field(default_factory=lambda: os.environ.get("MT_TELEGRAM_CHAT", ""))
    public_url: str = field(default_factory=lambda: os.environ.get("MT_PUBLIC_URL", ""))
    tz: str = field(default_factory=lambda: os.environ.get("TZ", "Europe/Zurich"))

    @property
    def avatar_dir(self) -> pathlib.Path:
        """Avatar images of the student's character (not part of the public repository)."""
        return self.data_dir / "avatar"

    @property
    def db_path(self) -> str:
        return str(self.data_dir / "mathtutor.db")

    @property
    def photo_dir(self) -> pathlib.Path:
        return self.data_dir / "photos"


CFG = Config()
# Course material that must not be published (transcribed exercises, figures, exams, theory) is copied
# by the operator into <data>/content. If it is there, it replaces the bundled public content.
if (CFG.data_dir / "content" / "curriculum.json").exists() and not os.environ.get("MT_CONTENT_DIR_FORCE"):
    CFG.content_dir = CFG.data_dir / "content"
CFG.data_dir.mkdir(parents=True, exist_ok=True)
CFG.photo_dir.mkdir(parents=True, exist_ok=True)
