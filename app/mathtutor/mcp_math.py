"""MCP server with the tutor's math tools. Started by Claude Code (stdio) inside the agent container.

Tools:
  python         run Python (sympy, numpy, scipy, matplotlib) – the tutor's calculator and drawing board
  check_answer   the same answer checker the app uses (authoritative for final answers)
  equivalent     are two expressions mathematically equal?
  plot           validate an interactive diagram and get the block to put into the answer
  submit_review  hand in the structured result of a correction (photo / written work)
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys

import sympy as sp
from mcp.server.fastmcp import FastMCP

from .checker import ParseError, check, parse

mcp = FastMCP("math")
RUN_DIR = pathlib.Path(os.environ.get("MT_RUN_DIR", "/tmp/mt-run"))
REVIEW_OUT = os.environ.get("MT_REVIEW_OUT")
ERROR_CATEGORIES = {
    "vorzeichen", "rechenfehler", "algebra", "regel", "konzept", "ansatz", "aufgabe-gelesen",
    "einheiten", "rechner", "runden", "notation", "interpretation",
}

PRELUDE = """
import math, cmath, fractions
import numpy as np
import sympy as sp
from sympy import *
x, y, z, t, a, b, c, k, r, s, u, v, w = symbols('x y z t a b c k r s u v w')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'figure.dpi': 110, 'axes.grid': True})
"""


@mcp.tool()
def python(code: str) -> str:
    """Run Python 3 code and return stdout/stderr. sympy (also `from sympy import *`), numpy as np, scipy and
    matplotlib.pyplot as plt are available; symbols x,y,z,t,a,b,c,k,r,s,u,v,w are predefined.
    Use print() for results. To draw a static figure for the student, save it with
    plt.savefig('bilder/<name>.png', bbox_inches='tight') and reference it in your answer as ![Beschreibung](bild:<name>.png).
    No network access. Timeout 30 s."""
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    (RUN_DIR / "bilder").mkdir(exist_ok=True)
    env = {"PATH": os.environ.get("PATH", "/bin"), "HOME": str(RUN_DIR), "MPLBACKEND": "Agg",
           "MPLCONFIGDIR": str(RUN_DIR / ".mpl"), "PYTHONPATH": os.environ.get("MT_PY_PATH", "")}
    try:
        p = subprocess.run([sys.executable, "-c", PRELUDE + "\n" + code], cwd=RUN_DIR, env=env,
                           capture_output=True, text=True, timeout=30)
        out = (p.stdout or "") + (("\n[stderr]\n" + p.stderr[-3000:]) if p.returncode else "")
    except subprocess.TimeoutExpired:
        out = "Abgebrochen: Zeitlimit 30 s überschritten."
    return out[-8000:] or "(keine Ausgabe – benutze print())"


@mcp.tool()
def check_answer(answer_spec: str, student_input: str, skills: str = "") -> str:
    """Check a student's final answer against an answer spec (JSON object as in the exercise data, e.g.
    {"type":"number","value":"sqrt(2)/2","rel":0.005} or {"type":"expr","value":"3*x**2","var":"x"}).
    Returns the checker verdict as JSON. This verdict is authoritative for final answers."""
    try:
        spec = json.loads(answer_spec)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"answer_spec ist kein JSON: {e}"})
    return json.dumps(check(spec, student_input, [s for s in skills.split(",") if s]).as_dict(), ensure_ascii=False)


@mcp.tool()
def equivalent(expr_a: str, expr_b: str, variables: str = "x") -> str:
    """Are two expressions mathematically equivalent (symbolic + numeric test)? Accepts ASCII math or LaTeX."""
    vs = tuple(v.strip() for v in variables.split(",") if v.strip())
    try:
        a, b = parse(expr_a, vs), parse(expr_b, vs)
    except ParseError as e:
        return f"Nicht lesbar: {e}"
    res = check({"type": "expr", "value": sp.sstr(b), "var": ",".join(vs)}, sp.sstr(a))
    return json.dumps({"equivalent": res.ok, "a": sp.sstr(a), "b": sp.sstr(b),
                       "a_minus_b_simplified": sp.sstr(sp.simplify(a - b))}, ensure_ascii=False)


@mcp.tool()
def plot(spec: str) -> str:
    """Validate an interactive diagram for the student and return the exact block to paste into your answer.
    spec (JSON):
    {"title": "...", "x": [-5, 5], "y": [-4, 4],
     "functions": [{"expr": "a*sin(b*(x-c))+d", "label": "f", "color": "#2563eb"}],
     "sliders": [{"name": "a", "min": -3, "max": 3, "value": 1, "step": 0.1, "label": "Amplitude"}],
     "points": [{"x": 1, "y": 2, "label": "P"}],          # x/y may be expressions in slider names
     "vectors": [{"from": [0, 0], "to": [2, 1], "label": "a"}],
     "areas": [{"expr": "x^2", "from": 0, "to": 2, "expr2": "0"}],
     "tangent": {"expr": "x^2", "at": "p"}}
    Expressions use x and slider names; ^ for powers; sin, cos, tan, exp, log (ln), sqrt, abs, pi, e."""
    try:
        s = json.loads(spec)
    except json.JSONDecodeError as e:
        return f"Fehler: kein gültiges JSON ({e})"
    names = {sl["name"] for sl in s.get("sliders", [])}
    problems = []

    def chk(expr, where):
        try:
            parse(str(expr), ("x",) + tuple(names))
        except Exception as e:  # noqa: BLE001
            problems.append(f"{where}: {e}")

    for i, f in enumerate(s.get("functions", [])):
        chk(f.get("expr", ""), f"functions[{i}]")
    for i, a in enumerate(s.get("areas", [])):
        chk(a.get("expr", ""), f"areas[{i}]")
        chk(a.get("expr2", "0"), f"areas[{i}].expr2")
        chk(a.get("from", 0), f"areas[{i}].from")
        chk(a.get("to", 1), f"areas[{i}].to")
    for i, p in enumerate(s.get("points", [])):
        chk(p.get("x", 0), f"points[{i}].x")
        chk(p.get("y", 0), f"points[{i}].y")
    for sl in s.get("sliders", []):
        if not re.fullmatch(r"[a-zA-Z]\w*", sl.get("name", "")) or sl["name"] in ("x", "e", "pi"):
            problems.append(f"Ungültiger Slider-Name {sl.get('name')!r}")
    if problems:
        return "Fehler im Diagramm:\n" + "\n".join(problems)
    return "OK. Füge GENAU diesen Block in deine Antwort ein:\n```plot\n" + json.dumps(s, ensure_ascii=False) + "\n```"


@mcp.tool()
def submit_review(review: str) -> str:
    """Hand in the correction of the student's written work (required in correction mode, call exactly once).
    review (JSON):
    {"readable": true,
     "transcription": "Was der Student geschrieben hat, Zeile für Zeile, in Markdown/LaTeX (Zeilen nummeriert 1., 2., …)",
     "parts": [{"label": "a", "final_answer": "Endresultat des Studenten als ASCII-Mathe oder '' wenn keins",
                "correct": true, "score": 1.0, "method_ok": true, "first_error_line": null,
                "error_category": null, "feedback": "kurz, präzise, auf Deutsch"}],
     "summary": "Gesamtrückmeldung an den Studenten (ermutigend, konkret)",
     "next_step": "Was er als Nächstes üben sollte"}
    error_category ∈ vorzeichen, rechenfehler, algebra, regel, konzept, ansatz, aufgabe-gelesen, einheiten, rechner, runden, notation, interpretation."""
    try:
        r = json.loads(review)
    except json.JSONDecodeError as e:
        return f"Fehler: kein gültiges JSON ({e}). Bitte korrigieren und nochmals senden."
    errs = []
    if not isinstance(r.get("parts"), list):
        errs.append("parts fehlt")
    for p in r.get("parts", []):
        ec = p.get("error_category")
        if ec and ec not in ERROR_CATEGORIES:
            errs.append(f"unbekannte error_category {ec!r}")
        if not isinstance(p.get("score", 0), (int, float)):
            errs.append("score muss eine Zahl 0..1 sein")
    if errs:
        return "Fehler: " + "; ".join(errs)
    if REVIEW_OUT:
        pathlib.Path(REVIEW_OUT).write_text(json.dumps(r, ensure_ascii=False))
    return "Korrektur gespeichert. Schreibe jetzt eine kurze Rückmeldung an den Studenten."


def main():
    mcp.run()


if __name__ == "__main__":
    main()
