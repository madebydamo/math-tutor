"""Parameterised exercise generators.

Every generator builds an exercise in the same format as content/exercises/*.json.
All numbers and solutions are computed with SymPy, so a generated exercise is
correct by construction; the LLM never invents the expected answer.

An exercise id is "gen-<generator>-<seed>", so the same exercise can be rebuilt
from its id at any time (history, challenge mode, admin view).
"""
from __future__ import annotations

import math
import random
from typing import Callable

import sympy as sp

x, t = sp.symbols("x t")
L = sp.latex

REGISTRY: dict[str, dict] = {}


def gen(gid: str, chapter: str, skills: list[str], title: str, calculator="ohne", difficulty=2, minutes=5):
    def deco(fn: Callable[[random.Random], dict]):
        REGISTRY[gid] = dict(fn=fn, chapter=chapter, skills=skills, title=title,
                             calculator=calculator, difficulty=difficulty, minutes=minutes)
        return fn
    return deco


def part(prompt, answer, solution, hints, label=""):
    assert len(hints) == 3
    return {"label": label, "prompt": prompt, "answer": answer, "solution": solution, "hints": hints}


def build(gid: str, seed: int) -> dict:
    meta = REGISTRY[gid]
    rng = random.Random(f"{gid}:{seed}")
    body = meta["fn"](rng)
    ex = {
        "id": f"gen-{gid}-{seed}",
        "source": {"doc": "Generiert", "ref": meta["title"]},
        "chapter": meta["chapter"],
        "skills": meta["skills"],
        "title": meta["title"],
        "calculator": meta["calculator"],
        "difficulty": meta["difficulty"],
        "minutes": meta["minutes"],
        "figures": [],
        "verified": True,
        "generated": True,
    }
    ex.update(body)
    return ex


def parse_id(eid: str) -> tuple[str, int] | None:
    if not eid.startswith("gen-"):
        return None
    rest = eid[4:]
    gid, _, seed = rest.rpartition("-")
    if gid in REGISTRY and seed.isdigit():
        return gid, int(seed)
    return None


def for_skill(skill: str) -> list[str]:
    return [g for g, m in REGISTRY.items() if skill in m["skills"]]


def _nz(rng, lo, hi, exclude=(0,)):
    while True:
        v = rng.randint(lo, hi)
        if v not in exclude:
            return v


def _distinct(rng, k, lo, hi):
    return sorted(rng.sample([v for v in range(lo, hi + 1)], k))


def fmt_num(v, digits=4):
    v = float(v)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.{digits}g}"


# ───────────────────────── Kapitel 1: Polynomfunktionen ─────────────────────────

@gen("poly-faktor", "k1", ["poly-faktorisieren"], "Nullstellen durch Faktorisieren", "ohne", 2, 6)
def _poly_faktor(rng):
    a = rng.choice([1, -1, 2, -2, 3, -3])
    r = _distinct(rng, 2, -6, 6)
    use_x = rng.random() < 0.6
    roots = ([0] if use_x else []) + r
    f = sp.expand(a * sp.prod([x - ri for ri in roots]))
    fac = sp.factor(f)
    sol = (f"Zuerst {('$x$' if use_x else 'den Faktor')} ausklammern, dann die quadratische Klammer faktorisieren "
           f"(Vieta oder Mitternachtsformel):\n\n$$f(x)={L(f)}={L(fac)}$$\n\n"
           f"Satz vom Nullprodukt: Nullstellen $x\\in\\{{{', '.join(map(str, sorted(set(roots))))}\\}}$.")
    return {
        "statement": f"Gegeben ist $f(x)={L(f)}$. Bestimme alle Nullstellen durch Faktorisieren (ohne Rechner).",
        "parts": [part("Nullstellen (getrennt mit ;)", {"type": "set", "value": [str(v) for v in sorted(set(roots))]}, sol, [
            "Kannst du einen gemeinsamen Faktor ausklammern?",
            "Klammere aus und zerlege die verbleibende quadratische Klammer in zwei Linearfaktoren (Vieta: Produkt und Summe der Nullstellen).",
            f"Nach dem Ausklammern bleibt {'$' + L(sp.factor(f / (a * x))) + '$' if use_x else 'eine quadratische Klammer'}. Ein Produkt ist 0, wenn ein Faktor 0 ist.",
        ])],
    }


@gen("poly-produktform", "k1", ["poly-produktform"], "Polynom aus Nullstellen und Punkt", "ohne", 2, 6)
def _poly_produkt(rng):
    roots = _distinct(rng, 3, -5, 6)
    a = sp.Rational(rng.choice([1, -1, 2, -2, 3, -3, 1, -1]), rng.choice([1, 1, 1, 2, 4]))
    px = rng.choice([v for v in range(-4, 6) if v not in roots])
    g = sp.prod([x - r for r in roots])
    py = a * g.subs(x, px)
    f = a * g
    gv = g.subs(x, px)
    sol = (f"Ansatz in Produktform: $y=a\\,{L(g)}$.\n\nPunkt $P({px}\\mid {L(py)})$ einsetzen (Satz von Anan): "
           f"${L(py)}=a\\cdot({L(gv)})\\Rightarrow a={L(a)}$.\n\n$$y={L(a)}\\,{L(g)}$$")
    return {
        "statement": (f"Eine Polynomfunktion 3. Grades hat die Nullstellen $x_1={roots[0]}$, $x_2={roots[1]}$, $x_3={roots[2]}$ "
                      f"und geht durch den Punkt $P({px}\\mid {L(py)})$. Bestimme die Funktionsgleichung."),
        "parts": [part("$y(x)=$", {"type": "expr", "value": sp.sstr(f)}, sol, [
            "Wie lautet der Ansatz, wenn alle Nullstellen bekannt sind?",
            f"Ansatz: $y=a\\,{L(g)}$. Wie findest du den Streckfaktor $a$?",
            f"Setze $x={px}$ und $y={L(py)}$ ein und löse nach $a$ auf.",
        ])],
    }


@gen("poly-anan", "k1", ["poly-anan"], "Polynom durch vier Punkte", "mit", 2, 8)
def _poly_anan(rng):
    co = [_nz(rng, -3, 3), rng.randint(-4, 4), rng.randint(-5, 5), rng.randint(-6, 6)]
    f = co[0] * x**3 + co[1] * x**2 + co[2] * x + co[3]
    xs = _distinct(rng, 4, -3, 3)
    pts = [(xi, f.subs(x, xi)) for xi in xs]
    ptxt = ", ".join(f"P_{i + 1}({xi}\\mid {yi})" for i, (xi, yi) in enumerate(pts))
    eqs = "\\\\".join(f"{yi}&=a_3\\cdot({xi})^3+a_2\\cdot({xi})^2+a_1\\cdot({xi})+a_0" for xi, yi in pts)
    sol = (f"Ansatz $y=a_3x^3+a_2x^2+a_1x+a_0$. Punkte einsetzen gibt ein lineares Gleichungssystem:\n\n"
           f"$$\\begin{{aligned}}{eqs}\\end{{aligned}}$$\n\nMit dem Rechner lösen (`solve({{…}},{{a3,a2,a1,a0}})`):\n\n"
           f"$a_3={co[0]},\\ a_2={co[1]},\\ a_1={co[2]},\\ a_0={co[3]}$, also $$y={L(f)}$$")
    return {
        "statement": f"Bestimme die Polynomfunktion 3. Grades durch die Punkte ${ptxt}$.",
        "parts": [part("$y(x)=$", {"type": "expr", "value": sp.sstr(f)}, sol, [
            "Welcher allgemeine Ansatz passt für ein Polynom 3. Grades?",
            "Ansatz $y=a_3x^3+a_2x^2+a_1x+a_0$: Jeder Punkt liefert eine Gleichung (Satz von Anan).",
            "Du erhältst 4 Gleichungen mit 4 Unbekannten – löse das System mit dem Rechner.",
        ])],
    }


@gen("poly-verhalten", "k1", ["poly-verhalten", "poly-skizze"], "Globalverlauf und y-Achsenabschnitt", "ohne", 1, 4)
def _poly_verhalten(rng):
    n = rng.choice([2, 3, 4, 5])
    a = _nz(rng, -4, 4)
    rest = sum(rng.randint(-6, 6) * x**k for k in range(n))
    f = a * x**n + rest
    d = f.subs(x, 0)
    left = "+\\infty" if (a > 0) == (n % 2 == 0) else "-\\infty"
    right = "+\\infty" if a > 0 else "-\\infty"
    opts = ["links oben → rechts oben", "links unten → rechts oben", "links oben → rechts unten", "links unten → rechts unten"]
    idx = {("+\\infty", "+\\infty"): 0, ("-\\infty", "+\\infty"): 1, ("+\\infty", "-\\infty"): 2, ("-\\infty", "-\\infty"): 3}[(left, right)]
    sol = (f"Für grosse $|x|$ dominiert der Summand mit der höchsten Potenz: $f(x)\\approx {L(a * x**n)}$.\n\n"
           f"Grad $n={n}$ ({'gerade' if n % 2 == 0 else 'ungerade'}), Leitkoeffizient ${a}$ ({'positiv' if a > 0 else 'negativ'}).\n\n"
           f"$x\\to-\\infty: f(x)\\to {left}$, $\\quad x\\to+\\infty: f(x)\\to {right}$ → **{opts[idx]}**.")
    return {
        "statement": f"Gegeben ist $f(x)={L(sp.expand(f))}$.",
        "parts": [
            part("Wie verläuft der Graph für sehr kleine und sehr grosse $x$?", {"type": "choice", "value": idx, "options": opts}, sol, [
                "Welcher Summand bestimmt das Verhalten, wenn $x$ sehr gross wird?",
                "Schau nur auf den Summanden mit der höchsten Potenz: Ist der Grad gerade oder ungerade? Ist der Koeffizient positiv oder negativ?",
                f"Betrachte $f(x)\\approx {L(a * x**n)}$ und setze in Gedanken $x=\\pm 100$ ein.",
            ], "a"),
            part("Wo schneidet der Graph die $y$-Achse? $y=$", {"type": "number", "value": str(d)}, f"$f(0)={d}$ (konstantes Glied).", [
                "Welchen $x$-Wert haben alle Punkte auf der $y$-Achse?",
                "Setze $x=0$ ein.",
                "Alle Summanden mit $x$ fallen weg – übrig bleibt das konstante Glied.",
            ], "b"),
        ],
    }


@gen("poly-mehrfach", "k1", ["poly-mehrfach"], "Mehrfache Nullstellen deuten", "ohne", 2, 4)
def _poly_mehrfach(rng):
    r = _distinct(rng, 3, -4, 4)
    m = [rng.choice([1, 2, 3]) for _ in r]
    if 1 not in m:
        m[0] = 1
    if 2 not in m and 3 not in m:
        m[1] = 2
    f = sp.prod([(x - ri) ** mi for ri, mi in zip(r, m)])
    touch = sorted(ri for ri, mi in zip(r, m) if mi % 2 == 0)
    if not touch:
        m[2] = 2
        f = sp.prod([(x - ri) ** mi for ri, mi in zip(r, m)])
        touch = sorted(ri for ri, mi in zip(r, m) if mi % 2 == 0)
    sol = ("Eine Nullstelle mit **gerader** Vielfachheit (doppelt, vierfach) ist eine Berührstelle (kein Vorzeichenwechsel), "
           "eine mit **ungerader** Vielfachheit wird geschnitten (dreifach: Sattelpunkt / Flachpunkt).\n\n" +
           "\n".join(f"- $x={ri}$: {mi}-fach → {'berührt' if mi % 2 == 0 else 'schneidet'}" for ri, mi in zip(r, m)))
    return {
        "statement": f"Gegeben ist $f(x)={L(f)}$.",
        "parts": [
            part("An welchen Stellen **berührt** der Graph die $x$-Achse (ohne sie zu schneiden)?",
                 {"type": "set", "value": [str(v) for v in touch]}, sol, [
                     "Schau auf die Exponenten der Linearfaktoren.",
                     "Gerade Vielfachheit ↔ kein Vorzeichenwechsel ↔ Berührpunkt.",
                     "Nimm die Nullstellen, deren Faktor quadriert (oder mit gerader Potenz) vorkommt.",
                 ]),
            part("Welchen Grad hat $f$?", {"type": "number", "value": str(sum(m))}, f"Grad = Summe der Vielfachheiten $= {'+'.join(map(str, m))} = {sum(m)}$.", [
                "Wie hängt der Grad mit den Linearfaktoren zusammen?",
                "Jeder Linearfaktor $(x-a)^k$ trägt $k$ zum Grad bei.",
                "Addiere alle Exponenten.",
            ], "b"),
        ],
    }


@gen("poly-optimierung-schachtel", "k1", ["poly-optimierung", "diff-optimierung"], "Optimierung: offene Schachtel", "mit", 2, 10)
def _poly_schachtel(rng):
    a = rng.choice([12, 16, 18, 20, 24, 30, 36, 40])
    b = rng.choice([a, a, a + 6, a + 10])
    V = (a - 2 * x) * (b - 2 * x) * x
    dV = sp.diff(V, x)
    crit = [c for c in sp.solve(dV, x) if c.is_real and 0 < c < min(a, b) / 2]
    xc = crit[0]
    vmax = V.subs(x, xc)
    sol = (f"Ausschneiden von Quadraten der Seitenlänge $x$ an den Ecken.\n\n"
           f"Zielfunktion: $V(x)=({a}-2x)({b}-2x)\\,x$, Definitionsbereich $D=\\left]0;{L(sp.Rational(min(a, b), 2))}\\right[$.\n\n"
           f"$V'(x)={L(sp.expand(dV))}=0 \\Rightarrow x={L(sp.nsimplify(xc))}\\approx {fmt_num(xc)}$ cm (die andere Lösung liegt ausserhalb von $D$).\n\n"
           f"$V_{{max}}=V({fmt_num(xc)})\\approx {fmt_num(vmax, 5)}\\,\\text{{cm}}^3$.")
    return {
        "statement": (f"Aus einem rechteckigen Karton ({a} cm × {b} cm) soll eine oben offene Schachtel entstehen: "
                      f"An allen vier Ecken werden gleich grosse Quadrate ausgeschnitten und die Seiten hochgefaltet."),
        "parts": [
            part("Seitenlänge $x$ der Quadrate für maximales Volumen (in cm)", {"type": "number", "value": sp.sstr(xc), "rel": 0.005, "unit": "cm"}, sol, [
                "Wie gross sind Länge, Breite und Höhe der Schachtel, wenn du Quadrate der Seite $x$ ausschneidest?",
                f"Zielfunktion $V(x)=({a}-2x)({b}-2x)\\,x$. Welcher Definitionsbereich ist sinnvoll?",
                "Bestimme das Maximum: $V'(x)=0$ setzen (oder grafisch mit dem Rechner) und die Lösung im Definitionsbereich wählen.",
            ], "a"),
            part("Maximales Volumen (in cm³)", {"type": "number", "value": sp.sstr(vmax), "rel": 0.005, "unit": "cm^3"}, sol, [
                "Du hast die optimale Seitenlänge schon – was fehlt noch?",
                "Setze das optimale $x$ in die Zielfunktion ein.",
                f"$V(x)=({a}-2x)({b}-2x)\\,x$ an der Stelle $x\\approx {fmt_num(xc)}$ auswerten.",
            ], "b"),
        ],
    }


@gen("poly-regression", "k1", ["poly-regression"], "Lineare Regression", "mit", 2, 6)
def _poly_regression(rng):
    import numpy as np
    m = rng.choice([-2.5, -1.5, -0.8, 0.6, 1.2, 2.4, 3.1])
    q = rng.randint(-5, 20)
    xs = list(range(1, 8))
    ys = [round(m * xi + q + rng.uniform(-1.5, 1.5), 1) for xi in xs]
    mm, qq = np.polyfit(xs, ys, 1)
    table = "| $x$ | " + " | ".join(map(str, xs)) + " |\n|---|" + "---|" * len(xs) + "\n| $y$ | " + " | ".join(map(str, ys)) + " |"
    xp = 12
    yp = mm * xp + qq
    sol = (f"Mit dem Rechner: Listen eingeben, `LinReg` (lineare Regression $y=mx+q$).\n\n"
           f"$m\\approx {mm:.4f}$, $q\\approx {qq:.4f}$.\n\nPrognose: $y(12)\\approx {mm:.4f}\\cdot 12 + {qq:.4f}\\approx {yp:.3f}$.")
    return {
        "statement": f"Gegeben sind die Messdaten:\n\n{table}\n\nBestimme die Regressionsgerade $y=mx+q$.",
        "parts": [
            part("Steigung $m$", {"type": "number", "value": f"{mm:.6f}", "tol": 0.01}, sol, [
                "Welches Rechnerwerkzeug liefert die beste Gerade durch viele Punkte?",
                "Gib die Daten als Listen ein und wähle die lineare Regression.",
                "Die Steigung ist der Koeffizient vor $x$ im Resultat der Regression.",
            ], "a"),
            part("Achsenabschnitt $q$", {"type": "number", "value": f"{qq:.6f}", "tol": 0.02}, sol, [
                "Gleiche Regression wie bei a).",
                "$q$ ist der konstante Term der Regressionsgeraden.",
                "Lies den zweiten Koeffizienten aus dem Regressionsresultat ab.",
            ], "b"),
            part("Prognose für $x=12$", {"type": "number", "value": f"{yp:.6f}", "tol": 0.1}, sol, [
                "Wie benutzt du die Gerade für eine Vorhersage?",
                "Setze $x=12$ in $y=mx+q$ ein.",
                "Rechne mit den ungerundeten Werten von $m$ und $q$.",
            ], "c"),
        ],
    }


# ───────────────────────── Kapitel 2: Trigonometrie ─────────────────────────

def _sin_params(rng):
    A = rng.choice([1, 2, 3, 4, sp.Rational(1, 2), sp.Rational(3, 2)])
    b = rng.choice([1, 2, 3, sp.Rational(1, 2), sp.pi, sp.pi / 2])
    c = rng.choice([0, 1, -1, 2, sp.pi / 4, -sp.pi / 2, sp.pi / 3])
    d = rng.choice([0, 0, 1, -1, 2, -2])
    return A, b, c, d


@gen("trig-parameter", "k2", ["trig-allg-sinus", "trig-nullstellen"], "Allgemeine Sinusfunktion: Kenngrössen", "ohne", 1, 5)
def _trig_param(rng):
    A, b, c, d = _sin_params(rng)
    f = A * sp.sin(b * (x - c)) + d
    T = sp.simplify(2 * sp.pi / b)
    sol = (f"Form $y=A\\sin(b(x-c))+d$ mit $A={L(A)}$, $b={L(b)}$, $c={L(c)}$, $d={L(d)}$.\n\n"
           f"- Amplitude $|A|={L(abs(A))}$\n- Periode $T=\\frac{{2\\pi}}{{b}}={L(T)}$\n"
           f"- Verschiebung um ${L(c)}$ nach {'rechts' if c >= 0 else 'links'}, um ${L(d)}$ in $y$-Richtung\n"
           f"- Wertebereich $W=[{L(d - abs(A))};\\,{L(d + abs(A))}]$")
    return {
        "statement": f"Gegeben ist $y={L(f)}$.",
        "parts": [
            part("Amplitude", {"type": "number", "value": sp.sstr(abs(A))}, sol, [
                "Welcher Parameter streckt die Sinuskurve in $y$-Richtung?",
                "Die Amplitude ist der Betrag des Faktors vor dem Sinus.",
                f"Faktor vor $\\sin$: ${L(A)}$.",
            ], "a"),
            part("Periode $T$", {"type": "number", "value": sp.sstr(T)}, sol, [
                "Nach welcher Länge wiederholt sich die Kurve?",
                "$T=\\frac{2\\pi}{b}$, wobei $b$ der Faktor vor der Klammer $(x-c)$ ist.",
                f"$b={L(b)}$ einsetzen.",
            ], "b"),
            part("Grösster Funktionswert", {"type": "number", "value": sp.sstr(d + abs(A))}, sol, [
                "Zwischen welchen Werten schwankt $\\sin$?",
                "Der Sinus liegt zwischen $-1$ und $1$; danach strecken und verschieben.",
                "Maximum $= d+|A|$.",
            ], "c"),
        ],
    }


@gen("trig-aus-graph", "k2", ["trig-gleichung-aus-graph"], "Sinusfunktion aus Kenngrössen aufstellen", "ohne", 2, 6)
def _trig_aus_graph(rng):
    A = rng.choice([1, 2, 3, 4])
    T = sp.sympify(rng.choice([2 * sp.pi, sp.pi, 4 * sp.pi, 4, 2, 8]))
    b = sp.simplify(2 * sp.pi / T)
    c = rng.choice([0, T / 4, T / 2, -T / 4]) if T.has(sp.pi) else rng.choice([0, 1, -1])
    d = rng.choice([0, 1, -1, 2])
    f = A * sp.sin(b * (x - c)) + d
    sol = (f"Mittellinie $y=d={d}$, Amplitude $A={A}$ (Abstand Maximum–Mittellinie), Periode $T={L(T)}\\Rightarrow b=\\frac{{2\\pi}}{{T}}={L(b)}$.\n\n"
           f"Der Graph steigt bei $x={L(c)}$ durch die Mittellinie (\"Sinus-Start\") $\\Rightarrow c={L(c)}$.\n\n$$y={L(f)}$$")
    return {
        "statement": (f"Eine Sinuskurve hat ihr Maximum ${A + d}$ und ihr Minimum ${d - A}$, die Periode ist $T={L(T)}$. "
                      f"Sie schneidet ihre Mittellinie bei $x={L(c)}$ **steigend**. Bestimme $y=A\\sin(b(x-c))+d$."),
        "parts": [part("$y=$", {"type": "expr", "value": sp.sstr(f)}, sol, [
            "Aus Maximum und Minimum kannst du zwei Parameter direkt bestimmen. Welche?",
            "Mittellinie $d=\\frac{\\max+\\min}{2}$, Amplitude $A=\\frac{\\max-\\min}{2}$, und $b=\\frac{2\\pi}{T}$.",
            "Die Sinusfunktion startet steigend auf der Mittellinie – dort liegt $c$.",
        ])],
    }


@gen("trig-schwingung", "k2", ["schwingung-modell"], "Harmonische Schwingung", "mit", 2, 6)
def _trig_schwingung(rng):
    A = rng.choice([2, 3, 5, 8, 10, 12])
    f_hz = rng.choice([0.5, 2, 2.5, 4, 5, 50])
    phi = rng.choice([0, sp.pi / 6, sp.pi / 4, sp.pi / 2, -sp.pi / 3])
    w = 2 * sp.pi * sp.nsimplify(f_hz)
    tt = rng.choice([0.1, 0.05, 0.3, 0.02])
    y = A * sp.sin(w * t + phi)
    yv = y.subs(t, tt)
    sol = (f"$\\omega=2\\pi f={L(w)}\\,\\text{{s}}^{{-1}}$, Periodendauer $T=\\frac1f={fmt_num(1 / f_hz)}$ s.\n\n"
           f"$y(t)={L(y)}$ (cm). Bogenmass! $y({tt})={A}\\sin({L(w)}\\cdot {tt}{'+' + L(phi) if phi != 0 else ''})\\approx {fmt_num(yv, 5)}$ cm.")
    return {
        "statement": (f"Ein Federpendel schwingt harmonisch mit Amplitude {A} cm und Frequenz {f_hz} Hz. "
                      f"Die Nullphase ist $\\varphi={L(phi)}$, also $y(t)=A\\sin(\\omega t+\\varphi)$."),
        "parts": [
            part("Periodendauer $T$ (in s)", {"type": "number", "value": str(1 / f_hz)}, sol, [
                "Wie hängen Frequenz und Periodendauer zusammen?",
                "$T=\\frac1f$.",
                f"$T=1/{f_hz}$.",
            ], "a"),
            part("Kreisfrequenz $\\omega$ (in s⁻¹)", {"type": "number", "value": sp.sstr(w)}, sol, [
                "Welche Formel verbindet $\\omega$ mit $f$?",
                "$\\omega=2\\pi f$.",
                f"$2\\pi\\cdot {f_hz}$ rechnen.",
            ], "b"),
            part(f"Auslenkung zur Zeit $t={tt}$ s (in cm)", {"type": "number", "value": sp.sstr(yv), "tol": 0.01}, sol, [
                "Setze $t$ in die Schwingungsgleichung ein.",
                "Rechner auf **Bogenmass** (RAD) stellen!",
                f"$y({tt})={A}\\sin(\\omega\\cdot{tt}+\\varphi)$.",
            ], "c"),
        ],
    }


@gen("trig-nullstellen", "k2", ["trig-nullstellen"], "Nullstellen einer Sinusfunktion", "ohne", 2, 6)
def _trig_null(rng):
    b = rng.choice([1, 2, 3, sp.Rational(1, 2)])
    c = rng.choice([0, sp.pi / 4, sp.pi / 2, sp.pi / 6, -sp.pi / 3])
    A = rng.choice([1, 2, 3, -2])
    f = A * sp.sin(b * (x - c))
    T = 2 * sp.pi / b
    zs = sorted({sp.nsimplify(c + k * T / 2) for k in range(-6, 12)}, key=lambda v: float(v))
    zs = [z for z in zs if 0 <= z < 2 * sp.pi]
    sol = (f"$\\sin(u)=0 \\iff u=k\\pi$. Also ${L(b)}(x-{L(c)})=k\\pi \\Rightarrow x={L(c)}+k\\cdot{L(sp.pi / b)}$.\n\n"
           f"Im Intervall $[0;2\\pi[$: $x\\in\\{{{', '.join(L(z) for z in zs)}\\}}$")
    return {
        "statement": f"Bestimme alle Nullstellen von $f(x)={L(f)}$ im Intervall $[0;\\,2\\pi[$.",
        "parts": [part("Nullstellen (getrennt mit ;)", {"type": "set", "value": [sp.sstr(z) for z in zs], "tol": 0.002}, sol, [
            "Wann ist der Sinus gleich null?",
            "$\\sin(u)=0$ genau für $u=k\\pi$ ($k$ ganzzahlig). Setze das Argument gleich $k\\pi$.",
            f"Löse ${L(b)}(x-{L(c)})=k\\pi$ nach $x$ und probiere $k=0,\\pm1,\\pm2,\\dots$ – nur Werte in $[0;2\\pi[$.",
        ])],
    }


@gen("komplex-polar", "k2", ["komplex-grundlagen"], "Komplexe Zahl in Polarform", "mit", 2, 5)
def _komplex_polar(rng):
    a = _nz(rng, -6, 6)
    b = _nz(rng, -6, 6)
    z = a + b * sp.I
    r = sp.sqrt(a**2 + b**2)
    phi = math.degrees(math.atan2(b, a))
    quadrant = {(True, True): "I", (False, True): "II", (False, False): "III", (True, False): "IV"}[(a > 0, b > 0)]
    sol = (f"$r=|z|=\\sqrt{{{a}^2+({b})^2}}={L(r)}\\approx {fmt_num(r)}$.\n\n$z$ liegt im {quadrant}. Quadranten. "
           f"$\\varphi=\\arctan2({b},{a})\\approx {phi:.2f}^\\circ$ (Achtung: $\\arctan(b/a)$ allein liefert nur Winkel im I./IV. Quadranten).")
    return {
        "statement": f"Schreibe $z={L(z)}$ in Polarform $z=r\\,e^{{i\\varphi}}$ bzw. $r\\angle\\varphi$ mit $-180^\\circ<\\varphi\\le180^\\circ$.",
        "parts": [part("$(r;\\ \\varphi$ in Grad$)$", {"type": "tuple", "value": [sp.sstr(r), f"{phi:.6f}"], "tol": 0.02, "names": ["r", "φ"]}, sol, [
            "Zeichne $z$ in der Gauss'schen Zahlenebene: In welchem Quadranten liegt sie?",
            "$r=\\sqrt{a^2+b^2}$ und für den Winkel $\\tan\\varphi=\\frac{b}{a}$ – Quadrant beachten!",
            "Liegt $z$ links der imaginären Achse, musst du zu $\\arctan(b/a)$ noch $\\pm180^\\circ$ addieren.",
        ])],
    }


@gen("komplex-rechnen", "k2", ["komplex-grundlagen"], "Rechnen mit komplexen Zahlen", "ohne", 2, 5)
def _komplex_rechnen(rng):
    z1 = _nz(rng, -5, 5) + _nz(rng, -5, 5) * sp.I
    z2 = _nz(rng, -5, 5) + _nz(rng, -5, 5) * sp.I
    prod = sp.expand(z1 * z2)
    quo = sp.simplify(sp.expand(z1 * sp.conjugate(z2)) / sp.expand(z2 * sp.conjugate(z2)))
    return {
        "statement": f"Gegeben sind $z_1={L(z1)}$ und $z_2={L(z2)}$.",
        "parts": [
            part("$z_1\\cdot z_2$ (Form $a+bi$)", {"type": "number", "value": sp.sstr(prod), "tol": 1e-6},
                 f"Ausmultiplizieren mit $i^2=-1$: $z_1z_2={L(prod)}$.", [
                     "Multipliziere wie zwei Klammern aus.",
                     "Jeder Term mit jedem – und dann $i^2=-1$ verwenden.",
                     "Fasse Realteile und Imaginärteile getrennt zusammen.",
                 ], "a"),
            part("$\\dfrac{z_1}{z_2}$ (Form $a+bi$)", {"type": "number", "value": sp.sstr(quo), "tol": 1e-3},
                 f"Mit dem konjugiert Komplexen erweitern: $\\frac{{z_1}}{{z_2}}=\\frac{{z_1\\overline{{z_2}}}}{{|z_2|^2}}={L(quo)}$.", [
                     "Wie wird man das $i$ im Nenner los?",
                     f"Erweitere mit $\\overline{{z_2}}={L(sp.conjugate(z2))}$.",
                     "Im Nenner steht dann $a^2+b^2$ (reell). Zähler ausmultiplizieren und Real-/Imaginärteil trennen.",
                 ], "b"),
        ],
    }


# ───────────────────────── Kapitel 3: Exponentialfunktion ─────────────────────────

@gen("exp-prozent", "k3", ["exp-funktion-aufstellen", "exp-logarithmus"], "Wachstum mit Prozentsatz", "mit", 2, 6)
def _exp_prozent(rng):
    N0 = rng.choice([500, 1200, 2500, 8000, 15000, 40000])
    p = rng.choice([1.5, 2, 2.5, 3, 4, 5, 6, 8, -3, -5, -8, -12])
    a = 1 + p / 100
    n = rng.choice([5, 8, 10, 12, 15])
    target = N0 * (2 if p > 0 else 0.5)
    tz = math.log(target / N0) / math.log(a)
    Nn = N0 * a**n
    word = "wächst" if p > 0 else "nimmt ab"
    sol = (f"Wachstumsfaktor $a=1{'+' if p > 0 else '-'}\\frac{{{abs(p)}}}{{100}}={a:g}$, also $N(t)={N0}\\cdot{a:g}^t$.\n\n"
           f"$N({n})={N0}\\cdot {a:g}^{{{n}}}\\approx {Nn:.2f}$\n\n"
           f"${target:g}={N0}\\cdot{a:g}^t \\Rightarrow t=\\frac{{\\ln({target / N0:g})}}{{\\ln({a:g})}}\\approx {tz:.3f}$ Jahre.")
    return {
        "statement": f"Ein Bestand von {N0} Einheiten {word} jährlich um {abs(p)} %.",
        "parts": [
            part("Funktionsgleichung $N(t)=$ ($t$ in Jahren)", {"type": "expr", "value": f"{N0}*{a}**t", "var": "t"}, sol, [
                "Um welchen Faktor ändert sich der Bestand pro Jahr?",
                f"Wachstumsfaktor $a=1\\pm\\frac{{p}}{{100}}$; Ansatz $N(t)=N_0\\cdot a^t$.",
                f"$N_0={N0}$, $a={a:g}$.",
            ], "a"),
            part(f"Bestand nach {n} Jahren", {"type": "number", "value": str(Nn), "rel": 0.002}, sol, [
                "Setze in deine Funktionsgleichung ein.",
                f"$t={n}$ einsetzen.",
                f"${N0}\\cdot{a:g}^{{{n}}}$ berechnen.",
            ], "b"),
            part(f"Nach wie vielen Jahren ist der Bestand {'verdoppelt' if p > 0 else 'halbiert'}?", {"type": "number", "value": str(tz), "rel": 0.002}, sol, [
                "Welche Gleichung musst du lösen?",
                f"${target:g}={N0}\\cdot{a:g}^t$ – teile durch ${N0}$.",
                "Logarithmieren: $t=\\frac{\\ln(\\text{Faktor})}{\\ln(a)}$.",
            ], "c"),
        ],
    }


@gen("exp-halbwert", "k3", ["exp-halbwertszeit", "exp-basis-e"], "Halbwertszeit und Zerfallskonstante", "mit", 2, 6)
def _exp_halbwert(rng):
    TH = rng.choice([5.27, 8.02, 12.3, 30.1, 5730, 1600, 3.8, 24])
    N0 = rng.choice([100, 250, 400, 1000])
    k = math.log(2) / TH
    tt = round(TH * rng.choice([0.5, 1.5, 2.3, 3, 4.2]), 2)
    Nt = N0 * math.exp(-k * tt)
    sol = (f"$N(t)=N_0e^{{-\\lambda t}}$ mit $\\lambda=\\frac{{\\ln 2}}{{T_{{1/2}}}}=\\frac{{\\ln2}}{{{TH}}}\\approx{k:.6g}$.\n\n"
           f"$N({tt})={N0}\\,e^{{-{k:.6g}\\cdot{tt}}}\\approx{Nt:.4g}$ mg.")
    return {
        "statement": f"Ein radioaktives Isotop hat die Halbwertszeit $T_{{1/2}}={TH}$ (Zeiteinheiten). Anfangsmenge: {N0} mg.",
        "parts": [
            part("Zerfallskonstante $\\lambda$ in $N(t)=N_0e^{-\\lambda t}$", {"type": "number", "value": str(k), "rel": 0.003}, sol, [
                "Was gilt nach genau einer Halbwertszeit?",
                "$\\frac{N_0}{2}=N_0e^{-\\lambda T_{1/2}}$ – kürze $N_0$ und logarithmiere.",
                "$\\lambda=\\frac{\\ln2}{T_{1/2}}$.",
            ], "a"),
            part(f"Restmenge nach $t={tt}$ (in mg)", {"type": "number", "value": str(Nt), "rel": 0.003}, sol, [
                "Setze $t$ in das Zerfallsgesetz ein.",
                "Verwende den ungerundeten Wert von $\\lambda$.",
                f"${N0}\\,e^{{-\\lambda\\cdot {tt}}}$.",
            ], "b"),
        ],
    }


@gen("exp-basis-umrechnen", "k3", ["exp-basis-e"], "Basis umrechnen: $a^x$ ↔ $e^{kx}$", "mit", 1, 3)
def _exp_basis(rng):
    a = rng.choice([1.03, 1.08, 1.25, 0.9, 0.75, 2, 3, 0.5])
    k = math.log(a)
    return {
        "statement": f"Schreibe $f(x)=5\\cdot {a:g}^x$ in der Form $f(x)=5\\cdot e^{{kx}}$.",
        "parts": [part("$k=$", {"type": "number", "value": str(k), "rel": 0.002},
                       f"$a^x=e^{{x\\ln a}}$, also $k=\\ln({a:g})\\approx{k:.5f}$. {'Wachstum' if k > 0 else 'Abnahme'} ({'k>0' if k > 0 else 'k<0'}).", [
                           "Wie kann man jede positive Zahl als Potenz von $e$ schreiben?",
                           "$a=e^{\\ln a}$, also $a^x=e^{x\\ln a}$.",
                           f"$k=\\ln({a:g})$.",
                       ])],
    }


@gen("exp-begrenzt", "k3", ["exp-begrenzt"], "Beschränktes Wachstum: Abkühlung / Laden", "mit", 2, 6)
def _exp_begrenzt(rng):
    S = rng.choice([20, 22, 25])
    T0 = rng.choice([80, 90, 95, 70])
    k = rng.choice([0.05, 0.08, 0.1, 0.12, 0.15])
    tt = rng.choice([5, 10, 15, 20])
    Tt = S + (T0 - S) * math.exp(-k * tt)
    targ = S + (T0 - S) * rng.choice([0.5, 0.3, 0.2])
    tz = -math.log((targ - S) / (T0 - S)) / k
    sol = (f"Abkühlungsgesetz: $T(t)=T_U+(T_0-T_U)e^{{-kt}}={S}+{T0 - S}e^{{-{k}t}}$.\n\n"
           f"$T({tt})\\approx{Tt:.3f}$ °C.\n\n${targ:g}={S}+{T0 - S}e^{{-{k}t}}\\Rightarrow t=-\\frac{{1}}{{{k}}}\\ln\\frac{{{targ - S:g}}}{{{T0 - S}}}\\approx{tz:.3f}$ min.")
    return {
        "statement": f"Ein Kaffee mit {T0} °C kühlt in einem Raum mit {S} °C ab: $T(t)={S}+{T0 - S}\\,e^{{-{k}t}}$ ($t$ in min).",
        "parts": [
            part(f"Temperatur nach {tt} min (in °C)", {"type": "number", "value": str(Tt), "tol": 0.05}, sol, [
                "Einsetzen genügt.",
                f"$t={tt}$ in die Funktion einsetzen.",
                f"Berechne zuerst $e^{{-{k}\\cdot{tt}}}$.",
            ], "a"),
            part(f"Wann ist der Kaffee auf {targ:g} °C abgekühlt? (in min)", {"type": "number", "value": str(tz), "rel": 0.003}, sol, [
                "Stelle eine Gleichung auf und isoliere die Potenz.",
                f"Zuerst ${S}$ subtrahieren und durch ${T0 - S}$ teilen.",
                "Dann logarithmieren (ln) und durch $-k$ teilen.",
            ], "b"),
        ],
    }


@gen("exp-aus-zwei-punkten", "k3", ["exp-funktion-aufstellen"], "Exponentialfunktion durch zwei Punkte", "mit", 2, 6)
def _exp_zwei(rng):
    c = rng.choice([2, 3, 5, 10, 50, 100])
    a = rng.choice([2, 3, sp.Rational(1, 2), sp.Rational(3, 2), sp.Rational(1, 3)])
    x1, x2 = sorted(rng.sample([0, 1, 2, 3, 4], 2))
    y1, y2 = c * a**x1, c * a**x2
    f = c * a**x
    sol = (f"Ansatz $y=c\\cdot a^x$. Gleichungen dividieren: $\\frac{{{L(y2)}}}{{{L(y1)}}}=a^{{{x2 - x1}}}\\Rightarrow a={L(a)}$, "
           f"dann $c={L(c)}$.\n\n$$y={L(f)}$$")
    return {
        "statement": f"Die Exponentialfunktion $y=c\\cdot a^x$ geht durch $P({x1}\\mid{L(y1)})$ und $Q({x2}\\mid{L(y2)})$.",
        "parts": [part("$y=$", {"type": "expr", "value": sp.sstr(f)}, sol, [
            "Setze beide Punkte in den Ansatz ein.",
            "Teile die beiden Gleichungen durcheinander – dann fällt $c$ weg.",
            f"$a^{{{x2 - x1}}}=\\frac{{y_Q}}{{y_P}}$, dann $c$ aus einer Gleichung.",
        ])],
    }


# ───────────────────────── Kapitel 4: Differentialrechnung ─────────────────────────

def _rand_poly(rng, deg, lo=-5, hi=5):
    return sum((_nz(rng, lo, hi) if k == deg else rng.randint(lo, hi)) * x**k for k in range(deg + 1))


@gen("diff-polynom", "k4", ["diff-potenzregel"], "Ableiten: Polynome und Potenzen", "ohne", 1, 3)
def _diff_poly(rng):
    kind = rng.random()
    if kind < 0.5:
        f = _rand_poly(rng, rng.choice([3, 4, 5]))
    else:
        f = rng.choice([3, -2, 4, 5]) * x ** sp.Rational(rng.choice([1, 3, 5]), rng.choice([2, 3])) + rng.choice([2, -1, 3]) / x ** rng.choice([1, 2, 3]) + rng.randint(-5, 5) * x
    d = sp.diff(f, x)
    return {
        "statement": f"Leite ab: $f(x)={L(f)}$",
        "parts": [part("$f'(x)=$", {"type": "expr", "value": sp.sstr(d)},
                       f"Potenzregel $(x^n)'=n\\,x^{{n-1}}$ gliedweise (Summen- und Faktorregel):\n\n$$f'(x)={L(d)}$$", [
                           "Welche Regel gilt für $x^n$?",
                           "$(x^n)'=n\\cdot x^{n-1}$ – auch für negative und gebrochene $n$. Schreibe Wurzeln und Brüche zuerst als Potenzen.",
                           "Leite jeden Summanden einzeln ab; Konstanten fallen weg.",
                       ])],
    }


@gen("diff-kette", "k4", ["diff-kettenregel", "diff-spezielle"], "Ableiten mit Kettenregel", "ohne", 2, 4)
def _diff_kette(rng):
    inner = rng.choice([rng.randint(2, 5) * x + rng.randint(-4, 4), x**2 + rng.randint(1, 5), rng.randint(2, 4) * x**2 - x])
    outer = rng.choice(["sin", "cos", "exp", "pow", "ln", "sqrt"])
    k = rng.choice([1, 2, 3, -2])
    if outer == "sin":
        f = k * sp.sin(inner)
    elif outer == "cos":
        f = k * sp.cos(inner)
    elif outer == "exp":
        f = k * sp.exp(inner)
    elif outer == "pow":
        f = k * inner ** rng.choice([2, 3, 4])
    elif outer == "ln":
        f = k * sp.log(inner) if inner.has(x**2) else k * sp.log(x**2 + 1)
    else:
        f = k * sp.sqrt(inner) if inner.has(x**2) else k * sp.sqrt(x**2 + 4)
    d = sp.diff(f, x)
    return {
        "statement": f"Leite ab: $f(x)={L(f)}$",
        "parts": [part("$f'(x)=$", {"type": "expr", "value": sp.sstr(d)},
                       f"Kettenregel: äussere Ableitung × innere Ableitung.\n\n$$f'(x)={L(d)}$$", [
                           "Ist das eine verkettete Funktion? Was ist innen, was aussen?",
                           "Kettenregel: $(u(v(x)))'=u'(v(x))\\cdot v'(x)$.",
                           "Leite die äussere Funktion ab (Inneres unverändert lassen) und multipliziere mit der Ableitung des Inneren.",
                       ])],
    }


@gen("diff-tangente", "k4", ["diff-tangente"], "Tangentengleichung", "ohne", 2, 5)
def _diff_tangente(rng):
    f = _rand_poly(rng, rng.choice([2, 3]), -3, 3)
    x0 = rng.randint(-2, 3)
    y0, m = f.subs(x, x0), sp.diff(f, x).subs(x, x0)
    tg = sp.expand(m * (x - x0) + y0)
    sol = (f"Berührpunkt: $f({x0})={y0}$. Steigung: $f'(x)={L(sp.diff(f, x))}$, $m=f'({x0})={m}$.\n\n"
           f"Punkt-Steigungs-Form: $y={m}(x-({x0}))+({y0})$, also $$t(x)={L(tg)}$$")
    return {
        "statement": f"Bestimme die Gleichung der Tangente an $f(x)={L(f)}$ an der Stelle $x_0={x0}$.",
        "parts": [part("$t(x)=$", {"type": "expr", "value": sp.sstr(tg)}, sol, [
            "Was brauchst du für eine Geradengleichung?",
            "Einen Punkt ($x_0$, $f(x_0)$) und die Steigung $m=f'(x_0)$.",
            "Setze in $t(x)=m(x-x_0)+f(x_0)$ ein und vereinfache.",
        ])],
    }


@gen("diff-extrema", "k4", ["diff-kurvendiskussion"], "Kurvendiskussion: Extrempunkte", "ohne", 2, 8)
def _diff_extrema(rng):
    r1, r2 = _distinct(rng, 2, -4, 4)
    a = rng.choice([1, -1, 2, -2, 3])
    fp = 3 * a * (x - r1) * (x - r2)
    f = sp.integrate(fp, x) + rng.randint(-5, 5)
    f = sp.expand(f)
    if any(c.q != 1 for c in sp.Poly(f, x).coeffs() if c.is_Rational):
        f = sp.expand(2 * f)
        fp = sp.diff(f, x)
    fpp = sp.diff(f, x, 2)
    xs = sorted(sp.solve(sp.diff(f, x), x))
    maxima = [xi for xi in xs if fpp.subs(x, xi) < 0]
    minima = [xi for xi in xs if fpp.subs(x, xi) > 0]
    xh, xt = maxima[0], minima[0]
    w = sp.solve(fpp, x)[0]
    sol = (f"$f'(x)={L(sp.factor(sp.diff(f, x)))}$, $f''(x)={L(fpp)}$.\n\n$f'(x)=0\\Rightarrow x\\in\\{{{', '.join(map(L, xs))}\\}}$.\n\n"
           f"- $f''({L(xh)})={L(fpp.subs(x, xh))}<0$ → Hochpunkt $H({L(xh)}\\mid{L(f.subs(x, xh))})$\n"
           f"- $f''({L(xt)})={L(fpp.subs(x, xt))}>0$ → Tiefpunkt $T({L(xt)}\\mid{L(f.subs(x, xt))})$\n\n"
           f"Wendepunkt: $f''(x)=0\\Rightarrow x={L(w)}$, $W({L(w)}\\mid{L(f.subs(x, w))})$.")
    hints_common = [
        "Was gilt für die Steigung in einem Hoch- oder Tiefpunkt?",
        "Setze $f'(x)=0$ und löse; mit $f''$ (oder Vorzeichenwechsel von $f'$) entscheidest du Hoch/Tief.",
    ]
    return {
        "statement": f"Gegeben ist $f(x)={L(f)}$.",
        "parts": [
            part("Hochpunkt $H(x\\mid y)$", {"type": "tuple", "value": [sp.sstr(xh), sp.sstr(f.subs(x, xh))], "names": ["x", "y"]}, sol,
                 hints_common + ["$f''(x)<0$ → Hochpunkt. Den $y$-Wert mit $f$ (nicht $f'$!) berechnen."], "a"),
            part("Tiefpunkt $T(x\\mid y)$", {"type": "tuple", "value": [sp.sstr(xt), sp.sstr(f.subs(x, xt))], "names": ["x", "y"]}, sol,
                 hints_common + ["$f''(x)>0$ → Tiefpunkt. $y$-Wert mit $f$ berechnen."], "b"),
            part("Wendepunkt $W(x\\mid y)$", {"type": "tuple", "value": [sp.sstr(w), sp.sstr(f.subs(x, w))], "names": ["x", "y"]}, sol, [
                "Was ändert sich in einem Wendepunkt?",
                "Die Krümmung wechselt: $f''(x)=0$.",
                "Löse $f''(x)=0$ und setze das $x$ in $f$ ein.",
            ], "c"),
        ],
    }


@gen("diff-steckbrief", "k4", ["diff-steckbrief"], "Steckbriefaufgabe", "mit", 3, 10)
def _diff_steckbrief(rng):
    while True:
        a3, a2, a1, a0 = _nz(rng, -2, 2), rng.randint(-3, 3), rng.randint(-4, 4), rng.randint(-4, 4)
        f = a3 * x**3 + a2 * x**2 + a1 * x + a0
        crit = [c for c in sp.solve(sp.diff(f, x), x) if c.is_rational]
        if crit:
            break
    xe = crit[0]
    p = rng.choice([v for v in range(-3, 4) if v != xe])
    q = rng.choice([v for v in range(-3, 4) if v not in (xe, p)])
    kind = "Hochpunkt" if sp.diff(f, x, 2).subs(x, xe) < 0 else ("Tiefpunkt" if sp.diff(f, x, 2).subs(x, xe) > 0 else "Sattelpunkt")
    a, b, c, d = sp.symbols("a b c d")
    sol = (f"Ansatz $f(x)=ax^3+bx^2+cx+d$, $f'(x)=3ax^2+2bx+c$.\n\nBedingungen:\n"
           f"- $f({L(xe)})={L(f.subs(x, xe))}$\n- $f'({L(xe)})=0$\n- $f({p})={f.subs(x, p)}$\n- $f({q})={f.subs(x, q)}$\n\n"
           f"Gleichungssystem lösen: $a={a3}, b={a2}, c={a1}, d={a0}$, also $$f(x)={L(f)}$$")
    return {
        "statement": (f"Gesucht ist eine Polynomfunktion 3. Grades. Ihr Graph hat einen {kind} in "
                      f"$E({L(xe)}\\mid{L(f.subs(x, xe))})$ und geht durch $P({p}\\mid{f.subs(x, p)})$ und $Q({q}\\mid{f.subs(x, q)})$."),
        "parts": [part("$f(x)=$", {"type": "expr", "value": sp.sstr(f)}, sol, [
            "Wie viele Unbekannte hat ein Polynom 3. Grades – und wie viele Bedingungen brauchst du?",
            "Ein Extrempunkt liefert zwei Bedingungen: $f(x_E)=y_E$ und $f'(x_E)=0$.",
            "Stelle 4 Gleichungen für $a,b,c,d$ auf und löse das System mit dem Rechner.",
        ])],
    }


@gen("diff-kinematik", "k4", ["diff-kinematik"], "Bewegung: Weg, Geschwindigkeit, Beschleunigung", "ohne", 2, 5)
def _diff_kin(rng):
    c3 = rng.choice([sp.Rational(1, 3), 1, -1, sp.Rational(-1, 3), 2])
    c2, c1 = rng.randint(-6, 6), rng.randint(0, 10)
    s = c3 * t**3 + c2 * t**2 + c1 * t
    v, a = sp.diff(s, t), sp.diff(s, t, 2)
    t0 = rng.randint(1, 4)
    return {
        "statement": f"Ein Körper bewegt sich nach dem Weg-Zeit-Gesetz $s(t)={L(s)}$ ($s$ in m, $t$ in s).",
        "parts": [
            part("Geschwindigkeit $v(t)=$", {"type": "expr", "value": sp.sstr(v), "var": "t"}, f"$v(t)=s'(t)={L(v)}$", [
                "Wie hängen Weg und Geschwindigkeit zusammen?",
                "Die Geschwindigkeit ist die Ableitung des Weges nach der Zeit.",
                "Leite $s(t)$ mit der Potenzregel nach $t$ ab.",
            ], "a"),
            part(f"Beschleunigung zur Zeit $t={t0}$ s (in m/s²)", {"type": "number", "value": sp.sstr(a.subs(t, t0))},
                 f"$a(t)=v'(t)={L(a)}$, $a({t0})={a.subs(t, t0)}$ m/s².", [
                     "Die Beschleunigung ist die Ableitung von …?",
                     "$a(t)=v'(t)=s''(t)$.",
                     f"Leite $v(t)$ ab und setze $t={t0}$ ein.",
                 ], "b"),
        ],
    }


# ───────────────────────── Kapitel 5: Integralrechnung ─────────────────────────

@gen("int-stammfunktion", "k5", ["int-stammfunktion"], "Stammfunktion bestimmen", "ohne", 1, 3)
def _int_stamm(rng):
    choice = rng.random()
    if choice < 0.4:
        f = _rand_poly(rng, rng.choice([2, 3]), -6, 6)
    elif choice < 0.7:
        f = rng.choice([2, 3, -4]) * sp.sqrt(x) + rng.choice([1, 2, -3]) / x**2
    else:
        k = rng.choice([2, 3, sp.Rational(1, 2)])
        f = rng.choice([sp.sin(k * x), sp.cos(k * x), sp.exp(k * x)]) * rng.choice([1, 2, 4]) + rng.randint(1, 5)
    F = sp.integrate(f, x)
    return {
        "statement": f"Bestimme eine Stammfunktion von $f(x)={L(f)}$ (ohne Integrationskonstante).",
        "parts": [part("$F(x)=$", {"type": "expr", "value": sp.sstr(F), "up_to_constant": True},
                       f"Grundintegrale gliedweise anwenden: $\\int x^n\\,dx=\\frac{{x^{{n+1}}}}{{n+1}}$, $\\int e^{{kx}}dx=\\frac1k e^{{kx}}$, $\\int\\sin(kx)dx=-\\frac1k\\cos(kx)$.\n\n$$F(x)={L(F)}+C$$\n\nProbe: $F'(x)=f(x)$.", [
                           "Welche Funktion hat abgeleitet genau $f$?",
                           "Schreibe Wurzeln und Brüche als Potenzen; dann $\\int x^n\\,dx=\\frac{x^{n+1}}{n+1}$. Bei $\\sin(kx)$, $e^{kx}$: durch $k$ teilen!",
                           "Mache die Probe: Leite dein Resultat ab – kommt $f$ heraus?",
                       ])],
    }


@gen("int-bestimmt", "k5", ["int-bestimmt"], "Bestimmtes Integral berechnen", "ohne", 2, 4)
def _int_best(rng):
    f = _rand_poly(rng, rng.choice([1, 2, 3]), -4, 4)
    a, b = sorted(rng.sample(range(-2, 4), 2))
    F = sp.integrate(f, x)
    val = sp.integrate(f, (x, a, b))
    return {
        "statement": f"Berechne $\\displaystyle\\int_{{{a}}}^{{{b}}}\\left({L(f)}\\right)dx$ ohne Rechner.",
        "parts": [part("Wert", {"type": "number", "value": sp.sstr(val), "tol": 1e-3},
                       f"$F(x)={L(F)}$. Hauptsatz: $\\int_a^b f\\,dx=F(b)-F(a)={L(F.subs(x, b))}-({L(F.subs(x, a))})={L(val)}$.", [
                           "Welcher Satz verbindet bestimmtes Integral und Stammfunktion?",
                           "Hauptsatz: $\\int_a^b f(x)\\,dx=F(b)-F(a)$.",
                           "Stammfunktion bilden, obere Grenze einsetzen, untere Grenze einsetzen, subtrahieren (Klammern!).",
                       ])],
    }


@gen("int-flaeche-xachse", "k5", ["int-flaeche-xachse"], "Fläche zwischen Graph und x-Achse", "mit", 2, 7)
def _int_flaeche(rng):
    r = _distinct(rng, 2, -3, 4)
    a = rng.choice([1, -1, sp.Rational(1, 2)])
    f = sp.expand(a * (x - r[0]) * (x - r[1]))
    use_three = rng.random() < 0.5
    if use_three:
        r3 = rng.choice([v for v in range(-3, 5) if v not in r])
        f = sp.expand(a * (x - r[0]) * (x - r[1]) * (x - r3))
        rs = sorted([r[0], r[1], r3])
    else:
        rs = sorted(r)
    pieces = [sp.integrate(f, (x, rs[i], rs[i + 1])) for i in range(len(rs) - 1)]
    A = sum(abs(p) for p in pieces)
    sol = (f"Nullstellen: $x\\in\\{{{', '.join(map(str, rs))}\\}}$. Zwischen den Nullstellen einzeln integrieren und Beträge addieren:\n\n" +
           "\n".join(f"- $\\int_{{{rs[i]}}}^{{{rs[i + 1]}}} f\\,dx={L(p)}$" for i, p in enumerate(pieces)) +
           f"\n\n$A={' + '.join(L(abs(p)) for p in pieces)}={L(A)}\\approx{fmt_num(A, 5)}$")
    return {
        "statement": f"Berechne die Fläche, die der Graph von $f(x)={L(f)}$ mit der $x$-Achse einschliesst.",
        "parts": [part("Fläche $A$", {"type": "number", "value": sp.sstr(A), "rel": 0.002}, sol, [
            "Wo beginnt und endet die Fläche?",
            "Bestimme die Nullstellen – sie sind die Integrationsgrenzen. Liegt Fläche unter der $x$-Achse, ist das Integral negativ!",
            "Integriere von Nullstelle zu Nullstelle einzeln und addiere die Beträge.",
        ])],
    }


@gen("int-zwei", "k5", ["int-flaeche-zwei"], "Fläche zwischen zwei Kurven", "mit", 2, 8)
def _int_zwei(rng):
    r = _distinct(rng, 2, -3, 4)
    a = rng.choice([1, -1, 2])
    g = rng.randint(-2, 2) * x + rng.randint(-3, 3)
    f = sp.expand(g + a * (x - r[0]) * (x - r[1]))
    A = abs(sp.integrate(f - g, (x, r[0], r[1])))
    sol = (f"Schnittstellen: $f(x)=g(x)\\iff {L(sp.factor(f - g))}=0\\Rightarrow x={r[0]},\\ x={r[1]}$.\n\n"
           f"$A=\\left|\\int_{{{r[0]}}}^{{{r[1]}}}(f(x)-g(x))\\,dx\\right|={L(A)}\\approx{fmt_num(A, 5)}$")
    return {
        "statement": f"Berechne die Fläche zwischen $f(x)={L(f)}$ und $g(x)={L(g)}$.",
        "parts": [part("Fläche $A$", {"type": "number", "value": sp.sstr(A), "rel": 0.002}, sol, [
            "Wo begrenzen sich die Kurven gegenseitig?",
            "Schnittstellen aus $f(x)=g(x)$ bestimmen – das sind die Grenzen.",
            "Integriere die Differenz $f(x)-g(x)$ zwischen den Schnittstellen und nimm den Betrag.",
        ])],
    }


@gen("int-mittelwert", "k5", ["int-mittelwert"], "Linearer Mittelwert", "mit", 2, 5)
def _int_mittel(rng):
    f = _rand_poly(rng, 2, -3, 4)
    a, b = sorted(rng.sample(range(0, 6), 2))
    m = sp.integrate(f, (x, a, b)) / (b - a)
    return {
        "statement": f"Berechne den linearen Mittelwert von $f(x)={L(f)}$ im Intervall $[{a};{b}]$.",
        "parts": [part("$\\bar m=$", {"type": "number", "value": sp.sstr(m), "rel": 0.002},
                       f"$\\bar m=\\frac{{1}}{{b-a}}\\int_a^b f(x)\\,dx=\\frac{{1}}{{{b - a}}}\\cdot {L(sp.integrate(f, (x, a, b)))}={L(m)}$", [
                           "Wie ist der Mittelwert einer Funktion definiert?",
                           "$\\bar m=\\frac{1}{b-a}\\int_a^b f(x)\\,dx$ – Fläche geteilt durch Intervallbreite.",
                           "Bestimmtes Integral berechnen und durch $b-a$ teilen.",
                       ])],
    }


@gen("int-rotation", "k5", ["int-rotation"], "Volumen eines Rotationskörpers", "mit", 2, 6)
def _int_rot(rng):
    kind = rng.choice(["sqrt", "lin", "quad"])
    if kind == "sqrt":
        f = rng.choice([1, 2, 3]) * sp.sqrt(x)
    elif kind == "lin":
        f = sp.Rational(rng.choice([1, 2, 3]), rng.choice([1, 2])) * x + rng.randint(0, 3)
    else:
        f = sp.Rational(1, rng.choice([2, 4])) * x**2 + 1
    a, b = 0, rng.choice([2, 3, 4])
    V = sp.pi * sp.integrate(f**2, (x, a, b))
    return {
        "statement": f"Der Graph von $f(x)={L(f)}$ rotiert im Intervall $[{a};{b}]$ um die $x$-Achse. Berechne das Volumen.",
        "parts": [part("$V=$", {"type": "number", "value": sp.sstr(V), "rel": 0.002},
                       f"$V=\\pi\\int_a^b f(x)^2\\,dx=\\pi\\int_{{{a}}}^{{{b}}}{L(sp.expand(f**2))}\\,dx={L(V)}\\approx{fmt_num(V, 5)}$", [
                           "Welche Formel gilt für Rotation um die $x$-Achse?",
                           "$V=\\pi\\int_a^b f(x)^2\\,dx$ – Scheibchen mit Radius $f(x)$.",
                           "Zuerst $f(x)^2$ ausrechnen, dann integrieren, dann mit $\\pi$ multiplizieren.",
                       ])],
    }


@gen("int-riemann", "k5", ["int-riemann"], "Untersumme und Obersumme", "mit", 2, 6)
def _int_riemann(rng):
    f = rng.choice([x**2, x**2 + 1, sp.Rational(1, 2) * x**2, x**3 / 4 + 1])
    b = rng.choice([2, 3, 4])
    n = rng.choice([4, 5, 6])
    h = sp.Rational(b, n)
    U = sum(h * f.subs(x, k * h) for k in range(n))
    O = sum(h * f.subs(x, (k + 1) * h) for k in range(n))
    return {
        "statement": f"$f(x)={L(f)}$ ist auf $[0;{b}]$ steigend. Teile das Intervall in $n={n}$ gleich breite Streifen.",
        "parts": [
            part("Untersumme $U_{" + str(n) + "}$", {"type": "number", "value": sp.sstr(U), "rel": 0.001},
                 f"Breite $\\Delta x={L(h)}$. Steigende Funktion → Untersumme nimmt linke Ränder: $U=\\Delta x\\sum_{{k=0}}^{{{n - 1}}} f(k\\Delta x)={L(U)}\\approx{fmt_num(U, 5)}$", [
                     "Wie breit ist ein Streifen?",
                     "Bei steigender Funktion ist der kleinste Wert im Streifen am linken Rand.",
                     "Summiere $\\Delta x\\cdot f(\\text{linker Rand})$ über alle Streifen.",
                 ], "a"),
            part("Obersumme $O_{" + str(n) + "}$", {"type": "number", "value": sp.sstr(O), "rel": 0.001},
                 f"Rechte Ränder: $O=\\Delta x\\sum_{{k=1}}^{{{n}}} f(k\\Delta x)={L(O)}\\approx{fmt_num(O, 5)}$", [
                     "Wo ist bei steigender Funktion der grösste Wert im Streifen?",
                     "Am rechten Rand.",
                     "Summiere $\\Delta x\\cdot f(\\text{rechter Rand})$.",
                 ], "b"),
        ],
    }


# ───────────────────────── Kapitel 6: Vektoren ─────────────────────────

def _vec(rng, n=3, lo=-6, hi=6):
    while True:
        v = sp.Matrix([rng.randint(lo, hi) for _ in range(n)])
        if any(v):
            return v


def _vl(v):
    return "\\begin{pmatrix}" + "\\\\".join(L(c) for c in v) + "\\end{pmatrix}"


@gen("vek-betrag", "k6", ["vek-koordinaten"], "Verbindungsvektor, Betrag, Einheitsvektor", "ohne", 1, 4)
def _vek_betrag(rng):
    A, B = _vec(rng), _vec(rng)
    AB = B - A
    n = sp.sqrt(AB.dot(AB))
    return {
        "statement": f"Gegeben: $A({', '.join(map(str, A))})$ und $B({', '.join(map(str, B))})$.",
        "parts": [
            part("$\\overrightarrow{AB}$", {"type": "tuple", "value": [str(c) for c in AB]},
                 f"„Spitze minus Fuss“: $\\overrightarrow{{AB}}=\\vec b-\\vec a={_vl(AB)}$", [
                     "Wie berechnest du den Vektor von $A$ nach $B$?",
                     "Endpunkt minus Anfangspunkt.",
                     "Komponentenweise $B-A$ rechnen.",
                 ], "a"),
            part("$|\\overrightarrow{AB}|$", {"type": "number", "value": sp.sstr(n)},
                 f"$|\\overrightarrow{{AB}}|=\\sqrt{{{'+'.join(f'({c})^2' for c in AB)}}}={L(n)}\\approx{fmt_num(n)}$", [
                     "Wie berechnet man die Länge eines Vektors?",
                     "Pythagoras im Raum: $\\sqrt{x^2+y^2+z^2}$.",
                     "Quadriere die drei Komponenten, addiere, ziehe die Wurzel.",
                 ], "b"),
            part("Einheitsvektor $\\vec e_{AB}$", {"type": "tuple", "value": [sp.sstr(c / n) for c in AB], "tol": 0.002},
                 f"$\\vec e=\\frac{{1}}{{|\\overrightarrow{{AB}}|}}\\overrightarrow{{AB}}=\\frac{{1}}{{{L(n)}}}{_vl(AB)}$", [
                     "Ein Einheitsvektor hat welche Länge?",
                     "Teile den Vektor durch seine Länge.",
                     "Jede Komponente durch $|\\overrightarrow{AB}|$ teilen.",
                 ], "c"),
        ],
    }


@gen("vek-skalar-winkel", "k6", ["vek-skalarprodukt", "vek-winkel"], "Skalarprodukt und Zwischenwinkel", "mit", 2, 5)
def _vek_winkel(rng):
    a, b = _vec(rng, 3, -5, 5), _vec(rng, 3, -5, 5)
    sk = a.dot(b)
    ang = math.degrees(math.acos(float(sk / (sp.sqrt(a.dot(a)) * sp.sqrt(b.dot(b))))))
    return {
        "statement": f"Gegeben sind $\\vec a={_vl(a)}$ und $\\vec b={_vl(b)}$.",
        "parts": [
            part("$\\vec a\\cdot\\vec b$", {"type": "number", "value": str(sk)},
                 f"$\\vec a\\cdot\\vec b={'+'.join(f'({p})({q})' for p, q in zip(a, b))}={sk}$", [
                     "Wie rechnet man das Skalarprodukt in Komponenten?",
                     "Komponentenweise multiplizieren und addieren.",
                     "$a_xb_x+a_yb_y+a_zb_z$.",
                 ], "a"),
            part("Zwischenwinkel $\\varphi$ (in Grad)", {"type": "number", "value": f"{ang:.8f}", "tol": 0.05, "unit": "°"},
                 f"$\\cos\\varphi=\\frac{{\\vec a\\cdot\\vec b}}{{|\\vec a||\\vec b|}}=\\frac{{{sk}}}{{{L(sp.sqrt(a.dot(a)))}\\cdot{L(sp.sqrt(b.dot(b)))}}}\\Rightarrow\\varphi\\approx{ang:.2f}^\\circ$", [
                     "Welche Formel verbindet Skalarprodukt und Winkel?",
                     "$\\cos\\varphi=\\frac{\\vec a\\cdot\\vec b}{|\\vec a|\\,|\\vec b|}$.",
                     "Beträge berechnen, einsetzen, $\\arccos$ – Rechner auf Grad (DEG).",
                 ], "b"),
        ],
    }


@gen("vek-orthogonal", "k6", ["vek-orthogonal"], "Orthogonalität: Parameter bestimmen", "ohne", 2, 4)
def _vek_orth(rng):
    a = _vec(rng, 3, -4, 4)
    while a[2] == 0:
        a = _vec(rng, 3, -4, 4)
    b1, b2 = rng.randint(-4, 4), rng.randint(-4, 4)
    tval = sp.Rational(-(a[0] * b1 + a[1] * b2), a[2])
    return {
        "statement": f"Für welchen Wert von $t$ stehen $\\vec a={_vl(a)}$ und $\\vec b=\\begin{{pmatrix}}{b1}\\\\{b2}\\\\t\\end{{pmatrix}}$ senkrecht aufeinander?",
        "parts": [part("$t=$", {"type": "number", "value": sp.sstr(tval)},
                       f"Orthogonal $\\iff\\vec a\\cdot\\vec b=0$: ${a[0]}\\cdot{b1}+{a[1]}\\cdot{b2}+{a[2]}t=0\\Rightarrow t={L(tval)}$", [
                           "Was gilt für das Skalarprodukt senkrechter Vektoren?",
                           "$\\vec a\\cdot\\vec b=0$.",
                           "Skalarprodukt mit $t$ aufschreiben, gleich null setzen, nach $t$ auflösen.",
                       ])],
    }


@gen("vek-kreuz", "k6", ["vek-vektorprodukt"], "Vektorprodukt und Dreiecksfläche", "mit", 2, 6)
def _vek_kreuz(rng):
    A, B, C = _vec(rng, 3, -4, 4), _vec(rng, 3, -4, 4), _vec(rng, 3, -4, 4)
    u, v = B - A, C - A
    n = u.cross(v)
    if not any(n):
        C = C + sp.Matrix([1, 2, 0])
        v = C - A
        n = u.cross(v)
    area = sp.sqrt(n.dot(n)) / 2
    return {
        "statement": f"Gegeben ist das Dreieck $A({', '.join(map(str, A))})$, $B({', '.join(map(str, B))})$, $C({', '.join(map(str, C))})$.",
        "parts": [
            part("$\\overrightarrow{AB}\\times\\overrightarrow{AC}$", {"type": "tuple", "value": [str(c) for c in n]},
                 f"$\\overrightarrow{{AB}}={_vl(u)}$, $\\overrightarrow{{AC}}={_vl(v)}$.\n\n$\\overrightarrow{{AB}}\\times\\overrightarrow{{AC}}={_vl(n)}$", [
                     "Bestimme zuerst die beiden Kantenvektoren.",
                     "$\\vec u\\times\\vec v=\\begin{pmatrix}u_yv_z-u_zv_y\\\\u_zv_x-u_xv_z\\\\u_xv_y-u_yv_x\\end{pmatrix}$.",
                     "Rechne Komponente für Komponente – auf die Vorzeichen achten!",
                 ], "a"),
            part("Fläche des Dreiecks", {"type": "number", "value": sp.sstr(area), "rel": 0.002},
                 f"$A_\\triangle=\\frac12|\\overrightarrow{{AB}}\\times\\overrightarrow{{AC}}|=\\frac12{L(sp.sqrt(n.dot(n)))}\\approx{fmt_num(area, 5)}$", [
                     "Was bedeutet der Betrag des Vektorprodukts geometrisch?",
                     "$|\\vec u\\times\\vec v|$ ist die Fläche des Parallelogramms.",
                     "Dreieck = halbes Parallelogramm.",
                 ], "b"),
        ],
    }


@gen("vek-gerade-punkt", "k6", ["vek-gerade"], "Gerade: Parameterform und Punktprobe", "ohne", 1, 5)
def _vek_gerade(rng):
    P, Q = _vec(rng, 3, -5, 5), _vec(rng, 3, -5, 5)
    r = Q - P
    on = rng.random() < 0.5
    lam = rng.choice([-2, -1, 2, 3, sp.Rational(1, 2)])
    T = P + lam * r if on else P + lam * r + sp.Matrix([0, 1, 0])
    opts = ["Ja, der Punkt liegt auf der Geraden", "Nein, der Punkt liegt nicht auf der Geraden"]
    sol = (f"$g:\\ \\vec r=\\vec p+\\lambda\\,\\overrightarrow{{PQ}}={_vl(P)}+\\lambda{_vl(r)}$.\n\n"
           f"Punktprobe mit $T$: drei Gleichungen für $\\lambda$. " +
           (f"Alle ergeben $\\lambda={L(lam)}$ → $T$ liegt auf $g$." if on else "Die Gleichungen liefern verschiedene $\\lambda$ (Widerspruch) → $T$ liegt nicht auf $g$."))
    return {
        "statement": f"Die Gerade $g$ geht durch $P({', '.join(map(str, P))})$ und $Q({', '.join(map(str, Q))})$.",
        "parts": [
            part("Richtungsvektor $\\overrightarrow{PQ}$", {"type": "tuple", "value": [str(c) for c in r]}, sol, [
                "Wie bekommst du die Richtung der Geraden?",
                "Verbindungsvektor zweier Punkte: Endpunkt minus Anfangspunkt.",
                "$Q-P$ komponentenweise.",
            ], "a"),
            part(f"Liegt $T({', '.join(map(L, T))})$ auf $g$?", {"type": "choice", "value": 0 if on else 1, "options": opts}, sol, [
                "Wie prüfst du, ob ein Punkt auf einer Geraden liegt?",
                "Setze $T$ für $\\vec r$ ein: Gibt es ein $\\lambda$, das alle drei Komponenten erfüllt?",
                "Löse jede Komponentengleichung nach $\\lambda$ – sind alle gleich?",
            ], "b"),
        ],
    }


@gen("vek-abstand", "k6", ["vek-abstand"], "Abstand Punkt–Gerade", "mit", 3, 8)
def _vek_abstand(rng):
    P, r, Q = _vec(rng, 3, -4, 4), _vec(rng, 3, -3, 3), _vec(rng, 3, -5, 5)
    d = sp.sqrt((Q - P).cross(r).dot((Q - P).cross(r))) / sp.sqrt(r.dot(r))
    if d == 0:
        Q = Q + sp.Matrix([1, 0, 1])
        d = sp.sqrt((Q - P).cross(r).dot((Q - P).cross(r))) / sp.sqrt(r.dot(r))
    return {
        "statement": f"Berechne den Abstand des Punktes $Q({', '.join(map(str, Q))})$ von der Geraden $g:\\ \\vec r={_vl(P)}+\\lambda{_vl(r)}$.",
        "parts": [part("Abstand $d$", {"type": "number", "value": sp.sstr(d), "rel": 0.002},
                       f"$d=\\frac{{|\\overrightarrow{{PQ}}\\times\\vec r|}}{{|\\vec r|}}$ mit $\\overrightarrow{{PQ}}={_vl(Q - P)}$:\n\n$d={L(sp.simplify(d))}\\approx{fmt_num(d, 5)}$\n\n(Alternativ: Lotfusspunkt $F$ mit $\\overrightarrow{{FQ}}\\cdot\\vec r=0$.)", [
                           "Welche zwei Wege kennst du (Lotfusspunkt oder Vektorprodukt)?",
                           "$d=\\frac{|\\overrightarrow{PQ}\\times\\vec r|}{|\\vec r|}$, wobei $P$ der Stützpunkt ist.",
                           "Erst $\\overrightarrow{PQ}$, dann das Vektorprodukt mit $\\vec r$, dann beide Beträge.",
                       ])],
    }


@gen("vek-linearkombination", "k6", ["vek-linearkombination"], "Linearkombination in der Ebene", "ohne", 2, 5)
def _vek_lk(rng):
    while True:
        a, b = _vec(rng, 2, -4, 4), _vec(rng, 2, -4, 4)
        if a[0] * b[1] - a[1] * b[0] != 0:
            break
    s, u = rng.randint(-3, 3), rng.randint(-3, 3)
    c = s * a + u * b
    return {
        "statement": f"Stelle $\\vec c={_vl(c)}$ als Linearkombination $\\vec c=s\\,\\vec a+t\\,\\vec b$ mit $\\vec a={_vl(a)}$, $\\vec b={_vl(b)}$ dar.",
        "parts": [part("$(s;\\ t)$", {"type": "tuple", "value": [str(s), str(u)], "names": ["s", "t"]},
                       f"Komponentenweise: ${c[0]}={a[0]}s+{b[0]}t$ und ${c[1]}={a[1]}s+{b[1]}t$. Lösen: $s={s},\\ t={u}$.", [
                           "Schreibe die Vektorgleichung komponentenweise auf.",
                           "Du erhältst zwei Gleichungen mit zwei Unbekannten $s$ und $t$.",
                           "Löse das Gleichungssystem (Einsetzen oder Addition).",
                       ])],
    }


@gen("vek-gerade-lage", "k6", ["vek-gerade-lage"], "Gegenseitige Lage zweier Geraden", "mit", 3, 10)
def _vek_lage(rng):
    P, r = _vec(rng, 3, -4, 4), _vec(rng, 3, -3, 3)
    kind = rng.choice(["schneidend", "schneidend", "parallel", "windschief"])
    lam, mu = rng.randint(-2, 2), rng.randint(-2, 2)
    if kind == "parallel":
        s = rng.choice([2, -1, 3]) * r
        Q = P + sp.Matrix([1, 1, 0]) if (sp.Matrix([1, 1, 0])).cross(r) != sp.zeros(3, 1) else P + sp.Matrix([0, 1, 1])
    else:
        while True:
            s = _vec(rng, 3, -3, 3)
            if any(r.cross(s)):
                break
        S_ = P + lam * r
        Q = S_ - mu * s
        if kind == "windschief":
            n = r.cross(s)
            Q = Q + n / sp.gcd(list(n)) if sp.gcd(list(n)) else Q + n
    opts = ["schneidend", "parallel (verschieden)", "identisch", "windschief"]
    idx = {"schneidend": 0, "parallel": 1, "windschief": 3}[kind]
    a, b = sp.symbols("lambda mu")
    if kind == "schneidend":
        S_ = P + lam * r
        sol = (f"Richtungsvektoren nicht kollinear. Gleichsetzen $\\vec p+\\lambda\\vec r=\\vec q+\\mu\\vec s$ gibt ein LGS "
               f"mit Lösung $\\lambda={lam},\\ \\mu={mu}$ (alle drei Gleichungen erfüllt) → Schnittpunkt $S({', '.join(map(L, S_))})$.")
    elif kind == "parallel":
        sol = "$\\vec s$ ist ein Vielfaches von $\\vec r$ → parallel. Punktprobe: $Q$ liegt nicht auf $g$ → echt parallel (nicht identisch)."
    else:
        sol = "Richtungsvektoren nicht kollinear, aber das LGS $\\vec p+\\lambda\\vec r=\\vec q+\\mu\\vec s$ ist widersprüchlich → kein Schnittpunkt → windschief."
    parts = [part("Wie liegen $g$ und $h$ zueinander?", {"type": "choice", "value": idx, "options": opts}, sol, [
        "Vergleiche zuerst die Richtungsvektoren: Sind sie Vielfache voneinander?",
        "Nicht kollinear: Setze die Geraden gleich und löse das LGS mit zwei Gleichungen; prüfe mit der dritten.",
        "Widerspruch in der dritten Gleichung → windschief; sonst schneidend. Kollinear: Punktprobe → identisch oder parallel.",
    ], "a")]
    if kind == "schneidend":
        S_ = P + lam * r
        parts.append(part("Schnittpunkt $S$", {"type": "tuple", "value": [sp.sstr(c) for c in S_]}, sol, [
            "Du brauchst $\\lambda$ (oder $\\mu$) aus dem Gleichungssystem.",
            "Löse zwei der drei Komponentengleichungen nach $\\lambda$ und $\\mu$.",
            "Setze $\\lambda$ in die Gleichung von $g$ ein.",
        ], "b"))
    return {
        "statement": f"Gegeben sind $g:\\ \\vec r={_vl(P)}+\\lambda{_vl(r)}$ und $h:\\ \\vec r={_vl(Q)}+\\mu{_vl(s)}$.",
        "parts": parts,
    }


@gen("komplex-wechselstrom", "k2", ["komplex-wechselstrom"], "Komplexe Impedanz (RL / RC in Serie)", "mit", 2, 6)
def _komplex_ac(rng):
    R = rng.choice([10, 22, 47, 100, 220, 330])
    f = rng.choice([50, 100, 1000])
    kind = rng.choice(["L", "C"])
    if kind == "L":
        Lh = rng.choice([0.01, 0.05, 0.1, 0.2, 0.5])
        X = 2 * math.pi * f * Lh
        comp, Ztxt = f"Spule $L={Lh}$ H", f"X_L=\\omega L=2\\pi\\cdot{f}\\cdot{Lh}\\approx{X:.3f}\\,\\Omega"
    else:
        C = rng.choice([1e-6, 4.7e-6, 10e-6, 47e-6, 100e-6])
        X = -1 / (2 * math.pi * f * C)
        comp, Ztxt = f"Kondensator $C={C * 1e6:g}\\,\\mu$F", f"X_C=-\\frac{{1}}{{\\omega C}}\\approx{X:.3f}\\,\\Omega"
    U = rng.choice([12, 24, 230])
    Zabs = math.hypot(R, X)
    phi = math.degrees(math.atan2(X, R))
    I = U / Zabs
    sol = (f"$\\omega=2\\pi f$. ${Ztxt}$.\n\n$\\underline Z=R+jX={R}{X:+.3f}j\\,\\Omega$, $|\\underline Z|=\\sqrt{{R^2+X^2}}\\approx{Zabs:.3f}\\,\\Omega$, "
           f"$\\varphi=\\arctan\\frac{{X}}{{R}}\\approx{phi:.2f}^\\circ$.\n\n$I=\\frac{{U}}{{|\\underline Z|}}\\approx{I:.4f}$ A.")
    return {
        "statement": f"Ein Widerstand $R={R}\\,\\Omega$ und eine {comp} sind in Serie an $U={U}$ V, $f={f}$ Hz angeschlossen.",
        "parts": [
            part("Impedanz $\\underline Z$ als $(|\\underline Z|;\\ \\varphi$ in Grad$)$", {"type": "tuple", "value": [str(Zabs), str(phi)], "tol": 0.05, "names": ["|Z|", "φ"]}, sol, [
                "Welche Impedanz hat die Spule bzw. der Kondensator?",
                "$\\underline Z_L=j\\omega L$, $\\underline Z_C=\\frac{1}{j\\omega C}=-\\frac{j}{\\omega C}$; in Serie addieren sich die Impedanzen.",
                "$|\\underline Z|=\\sqrt{R^2+X^2}$, $\\varphi=\\arctan(X/R)$.",
            ], "a"),
            part("Stromstärke $I$ (in A)", {"type": "number", "value": str(I), "rel": 0.003, "unit": "A"}, sol, [
                "Ohmsches Gesetz im Wechselstromkreis.",
                "$I=U/|\\underline Z|$.",
                "Nimm den Betrag der Impedanz aus a).",
            ], "b"),
        ],
    }


def catalogue() -> list[dict]:
    return [{"id": g, **{k: v for k, v in m.items() if k != "fn"}} for g, m in REGISTRY.items()]


from . import generators_basics  # noqa: E402,F401  (registers basics)
