"""Step-by-step solutions.

Course exercises carry hand-checked `steps` (one transformation per line).
Generated exercises only have a Markdown `solution`; `auto_steps` splits it into
steps: display math is broken at implications and line breaks, prose becomes a note.
"""
from __future__ import annotations

import re

_SPLIT_IMPL = re.compile(r"\s*(?:\\quad|\\qquad|\\;|\\,)*\s*(\\Rightarrow|\\Longrightarrow|\\implies|⇒)\s*(?:\\quad|\\qquad)*\s*")


def _split_top(s: str, sep_re: re.Pattern) -> list[str]:
    """Split at a separator only outside {...} and \\left(...\\right)."""
    out, depth, last = [], 0, 0
    for m in re.finditer(r"[{}]|" + sep_re.pattern, s):
        tok = m.group(0)
        if tok == "{":
            depth += 1
        elif tok == "}":
            depth -= 1
        elif depth == 0:
            out.append(s[last:m.start()])
            last = m.end()
    out.append(s[last:])
    return [p.strip() for p in out if p.strip()]


def _math_lines(tex: str) -> list[str]:
    tex = tex.strip()
    tex = re.sub(r"\\begin\{(aligned|align\*?|gathered|array)\}(\{[^}]*\})?", "", tex)
    tex = re.sub(r"\\end\{(aligned|align\*?|gathered|array)\}", "", tex)
    lines = []
    for row in re.split(r"\\\\", tex):
        row = row.replace("&", "").strip()
        if not row:
            continue
        lines += _split_top(row, _SPLIT_IMPL)
    return lines


def _is_formula(m: str) -> bool:
    """Inline math worth its own line (an equation or a longer expression, not just «$x$»)."""
    return len(m) > 14 or bool(re.search(r"=|\\Rightarrow|\\approx|<|>", m))


def _inline_steps(text: str) -> list[dict]:
    """Prose with inline math: every formula-like $…$ becomes its own math line, the text before it its note."""
    segs = re.split(r"(?<!\\)\$(.+?)(?<!\\)\$", text)
    steps: list[dict] = []
    note = ""
    for i, seg in enumerate(segs):
        if i % 2 == 0:
            note += seg
            continue
        if not _is_formula(seg):
            note += f"${seg}$"
            continue
        clean = re.sub(r"[\s,;:.]+$", "", note.strip())
        clean = re.sub(r"^[\s,;:.]+", "", clean)
        for j, ln in enumerate(_math_lines(seg)):
            steps.append({"note": clean if j == 0 else "", "math": ln})
        note = ""
    tail = re.sub(r"^[\s,;:.]+|[\s,;:.]+$", "", note.strip())
    if tail:
        if steps and len(tail) <= 20 and "$" not in tail:
            steps[-1]["math"] += f"\\ \\text{{{tail}}}"
        else:
            steps.append({"note": tail})
    return steps


def auto_steps(md: str | None) -> list[dict]:
    if not md:
        return []
    steps: list[dict] = []
    for para in re.split(r"\n\s*\n|\n(?=\s*[-*]\s)|\n(?=\d+\.\s)", md.strip()):
        para = para.strip()
        if not para:
            continue
        pieces = re.split(r"\$\$(.+?)\$\$", para, flags=re.S)
        note_buf = ""
        for i, piece in enumerate(pieces):
            if i % 2 == 0:
                txt = re.sub(r"^\s*[-*]\s+", "", piece).strip()
                if txt:
                    note_buf = (note_buf + " " + txt).strip()
            else:
                lines = _math_lines(piece)
                for j, ln in enumerate(lines):
                    steps.append({"note": note_buf if j == 0 else "", "math": ln})
                note_buf = ""
        if note_buf:
            steps += _inline_steps(note_buf)
    if steps:
        last_math = max((i for i, s in enumerate(steps) if s.get("math")), default=len(steps) - 1)
        steps[last_math]["result"] = True
        if last_math < len(steps) - 1 and "$" in steps[-1].get("note", ""):
            steps[-1]["result"] = True
    return steps


def payload(part: dict, ex: dict | None = None) -> dict:
    """What the client gets for a revealed solution: steps (with rule chips) and the formulas of the topic."""
    from .content import content

    cards = content().cards
    steps = [dict(s) for s in (part.get("steps") or auto_steps(part.get("solution")))]
    for st in steps:
        k = cards.get(st.get("card") or "")
        if k:
            st.setdefault("rule", k.get("name"))
            if not st.get("rule_formula"):
                st["rule_formula"] = k.get("formula", "").replace("$$", "").strip("$ ")
    out = {"md": part.get("solution"), "steps": steps}
    if ex is not None and not any(st.get("rule") for st in steps):
        skills = ex.get("skills", [])
        rel = [k for k in cards.values() if set(k.get("skills", [])) & set(skills)][:4]
        out["formulas"] = [{"id": k["id"], "name": k.get("name"), "formula": k.get("formula")} for k in rel]
    return out
