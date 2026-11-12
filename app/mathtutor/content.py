"""Course content: curriculum, exercises, theory, Formelsammlung, exams."""
from __future__ import annotations

import json
import random
from functools import lru_cache

from . import generators
from .config import CFG


class Content:
    def __init__(self):
        root = CFG.content_dir
        self.curriculum = json.loads((root / "curriculum.json").read_text())
        self.chapters = {c["id"]: c for c in self.curriculum["chapters"]}
        self.skills = {}
        for c in self.curriculum["chapters"]:
            for s in c["skills"]:
                self.skills[s["id"]] = {**s, "chapter": c["id"]}
        self.error_categories = {e["id"]: e["title"] for e in self.curriculum["error_categories"]}
        self.exercises: dict[str, dict] = {}
        for f in sorted((root / "exercises").glob("*.json")):
            try:
                for ex in json.loads(f.read_text()):
                    ex["_file"] = f.stem
                    self.exercises[ex["id"]] = ex
            except Exception as e:  # noqa: BLE001
                print(f"content: skipping {f.name}: {e}")
        self.by_skill: dict[str, list[str]] = {}
        for ex in self.exercises.values():
            for s in ex.get("skills", []):
                self.by_skill.setdefault(s, []).append(ex["id"])
        self.cards: dict[str, dict] = {}
        for f in sorted((root / "formula-cards").glob("*.json")) if (root / "formula-cards").exists() else []:
            try:
                for k in json.loads(f.read_text()):
                    self.cards[k["id"]] = k
            except Exception as e:  # noqa: BLE001
                print(f"content: skipping cards {f.name}: {e}")
        self.theory = {c: _read(root / "theory" / f"{c}.md") for c in self.chapters}
        self.formeln = {c: _read(root / "formeln" / f"{c}.md") for c in self.chapters}
        self.exams = json.loads(_read(root / "exams.json") or "[]")
        self.exam_info = _read(root / "exam-info.md")

    def get(self, eid: str) -> dict | None:
        if eid in self.exercises:
            return self.exercises[eid]
        p = generators.parse_id(eid)
        if p:
            return _gen_cached(*p)
        return None

    def skill_sources(self, skill: str) -> dict:
        return {"course": len(self.by_skill.get(skill, [])), "generators": generators.for_skill(skill)}

    def pick(self, skill: str | None = None, chapter: str | None = None, prefer: str = "mix",
             exclude: set[str] | None = None, rng: random.Random | None = None,
             calculator: str | None = None, difficulty: int | None = None) -> dict | None:
        """Choose an exercise: course exercises first (unseen), generated ones as endless supply."""
        rng = rng or random.Random()
        disabled = set(disabled_ids())
        exclude = (exclude or set()) | disabled
        skills = [skill] if skill else [s for s, v in self.skills.items() if not chapter or v["chapter"] == chapter]
        course = [e for s in skills for e in self.by_skill.get(s, []) if e not in exclude]
        course = [e for e in course if (not calculator or self.exercises[e].get("calculator") == calculator)
                  and (not difficulty or self.exercises[e].get("difficulty") == difficulty)]
        gens = sorted({g for s in skills for g in generators.for_skill(s) if f"gen:{g}" not in disabled})
        if calculator:
            gens = [g for g in gens if generators.REGISTRY[g]["calculator"] == calculator] or gens
        use_course = course and (prefer == "course" or (prefer == "mix" and (not gens or rng.random() < 0.55)))
        if use_course:
            return self.exercises[rng.choice(course)]
        if gens:
            g = rng.choice(gens)
            return _gen_cached(g, rng.randint(1, 10**6))
        if course:
            return self.exercises[rng.choice(course)]
        return None


def disabled_ids() -> list[str]:
    """Exercise ids (and "gen:<generator>") the coach took out of rotation after an error report."""
    from . import db

    try:
        return db.get_setting("disabled_exercises", []) or []
    except Exception:  # noqa: BLE001  (db not initialised, e.g. in tests)
        return []


def _read(p):
    try:
        return p.read_text()
    except FileNotFoundError:
        return ""


@lru_cache(maxsize=2048)
def _gen_cached(gid: str, seed: int) -> dict:
    return generators.build(gid, seed)


_CONTENT: Content | None = None


def content() -> Content:
    global _CONTENT
    if _CONTENT is None:
        _CONTENT = Content()
    return _CONTENT


def reload():
    global _CONTENT
    _CONTENT = Content()


def public_exercise(ex: dict, reveal: bool = False) -> dict:
    """The exercise as the student sees it (no answers, solutions or hints unless revealed)."""
    out = {k: v for k, v in ex.items() if not k.startswith("_") and k not in ("parts",)}
    parts = []
    for p in ex["parts"]:
        a = p["answer"]
        pa = {"type": a["type"]}
        for k in ("unit", "options", "names", "var"):
            if k in a:
                pa[k] = a[k]
        if a["type"] in ("set", "tuple"):
            pa["count"] = len(a["value"])
        item = {"label": p.get("label", ""), "prompt": p.get("prompt", ""), "answer": pa, "hint_count": len(p.get("hints", []))}
        if reveal:
            from .steps import payload
            item["solution"] = p.get("solution")
            pl = payload(p, ex)
            item["steps"] = pl["steps"]
            item["formulas"] = pl.get("formulas")
            item["expected"] = a.get("value")
            item["hints"] = p.get("hints", [])
        parts.append(item)
    out["parts"] = parts
    return out
