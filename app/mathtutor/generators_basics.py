"""Generatoren für die optionalen Grundlagen-Kapitel G1–G3.

Gleiches Format wie in generators.py: Jede Aufgabe wird mit SymPy berechnet,
alle Antworten sind exakt (sp.Rational) oder numerisch aus einer Formel.
Wird am Ende von generators.py importiert, damit sich alles im REGISTRY einträgt.
"""
from __future__ import annotations

import math

import sympy as sp

from .generators import L, _distinct, _nz, fmt_num, gen, part, x  # noqa: F401

y, z = sp.symbols("y z")
a_, b_ = sp.symbols("a b")
R = sp.Rational


# ───────────────────────── Hilfsfunktionen ─────────────────────────

def _sg(v) -> str:
    """Vorzeichenbehafteter Summand für die Anzeige: '+ 3', '- \\frac{1}{2}'."""
    v = sp.sympify(v)
    return f"+ {L(v)}" if v >= 0 else f"- {L(-v)}"


def _co(c, var="x") -> str:
    """Koeffizient vor einer Variablen am Anfang: 1→x, -1→-x, 3→3x."""
    c = sp.sympify(c)
    if c == 1:
        return var
    if c == -1:
        return f"-{var}"
    return f"{L(c)}{var}"


def _sco(c, var="x") -> str:
    """Vorzeichenbehafteter Term mit Variable: '+ 3x', '- x'."""
    c = sp.sympify(c)
    return ("+ " + _co(c, var)) if c >= 0 else ("- " + _co(-c, var))


def _sterm(c, inner: str) -> str:
    """'+ 3\\left(…\\right)', '- \\left(…\\right)'."""
    c = sp.sympify(c)
    k = abs(c)
    k_txt = "" if k == 1 else L(k)
    return f"{'+' if c > 0 else '-'} {k_txt}\\left({inner}\\right)"


def _pw(base: str, e) -> str:
    return base if e == 1 else f"{base}^{{{e}}}"


def _lin(cs, names) -> str:
    """Linearer Term aus Koeffizienten, z.B. 2x - y + 3z (Nullen weglassen)."""
    out = ""
    for c, n in zip(cs, names):
        if c == 0:
            continue
        out += (_co(c, n) if not out else " " + _sco(c, n))
    return out or "0"


def _num(v) -> str:
    """Zahl für die Anzeige (Dezimalpunkt, ohne unnötige Nullen)."""
    v = sp.nsimplify(v) if not isinstance(v, (int, sp.Integer, sp.Rational)) else sp.sympify(v)
    if v.is_Integer:
        return str(int(v))
    f = float(v)
    s = f"{f:.10f}".rstrip("0").rstrip(".")
    return s


def _chf(v) -> str:
    """Geldbetrag mit 2 Nachkommastellen und Tausender-Apostroph."""
    return f"{float(v):,.2f}".replace(",", "'")


def _dec(s: str) -> sp.Rational:
    return sp.Rational(s)


# ═════════════════════════ G1: Rechnen & Terme ═════════════════════════

# ───────────── Bruchrechnen ─────────────

def _rand_fracs(rng, n, dens=(2, 3, 4, 5, 6, 8, 9, 10, 12, 15), maxnum=None):
    fr = []
    while len(fr) < n:
        d = rng.choice(dens)
        zz = rng.randint(1, (maxnum or 2 * d - 1))
        r = R(zz, d)
        if r.q > 1 and r not in fr:
            fr.append(r)
    return fr


@gen("gb-bruch-addieren", "g1", ["g-brueche"], "Brüche addieren und subtrahieren", "ohne", 1, 4)
def _bruch_add(rng):
    n = rng.choice([2, 3, 3])
    fr = _rand_fracs(rng, n)
    ops = [1] + [rng.choice([1, -1]) for _ in range(n - 1)]
    res = sum(o * f for o, f in zip(ops, fr))
    H = sp.ilcm(*[f.q for f in fr])
    term = L(fr[0]) + "".join((" + " if o > 0 else " - ") + L(f) for o, f in zip(ops[1:], fr[1:]))
    ext = f"\\frac{{{fr[0].p * (H // fr[0].q)}}}{{{H}}}" + "".join(
        (" + " if o > 0 else " - ") + f"\\frac{{{f.p * (H // f.q)}}}{{{H}}}" for o, f in zip(ops[1:], fr[1:]))
    num = sum(o * f.p * (H // f.q) for o, f in zip(ops, fr))
    dens = ", ".join(str(f.q) for f in fr)
    raw = f"\\frac{{{num}}}{{{H}}}"
    kuerz = "" if R(num, H).q == H else f"\n\nKürzen: ${raw}={L(res)}$."
    sol = (f"Hauptnenner $=\\operatorname{{kgV}}({dens})={H}$. Jeden Bruch auf den Nenner ${H}$ erweitern:\n\n"
           f"$${term}={ext}={raw}$${kuerz}\n\nResultat: $${L(res)}$$")
    return {
        "statement": f"Berechne ohne Rechner und gib das Resultat als vollständig gekürzten Bruch an: ${term}$",
        "parts": [part("Resultat", {"type": "number", "value": sp.sstr(res)}, sol, [
            "Brüche kann man nur addieren oder subtrahieren, wenn sie den gleichen Nenner haben.",
            f"Suche das kleinste gemeinsame Vielfache (kgV) der Nenner ${dens}$ – das ist der Hauptnenner.",
            f"Der Hauptnenner ist ${H}$. Erweitere jeden Bruch auf diesen Nenner, verrechne die Zähler und kürze am Schluss.",
        ])],
    }


@gen("gb-bruch-mult-div", "g1", ["g-brueche"], "Brüche multiplizieren und dividieren", "ohne", 1, 4)
def _bruch_mult(rng):
    kind = rng.choice(["md", "md", "klammer", "punkt"])
    f1, f2, f3 = _rand_fracs(rng, 3, dens=(2, 3, 4, 5, 6, 7, 8, 9, 10), maxnum=9)
    if kind == "md":
        res = f1 * f2 / f3
        term = f"{L(f1)}\\cdot{L(f2)}:{L(f3)}"
        sol = (f"Durch einen Bruch dividieren heisst mit seinem **Kehrwert** multiplizieren:\n\n"
               f"$${term}={L(f1)}\\cdot{L(f2)}\\cdot{L(1 / f3)}=\\frac{{{f1.p}\\cdot{f2.p}\\cdot{f3.q}}}{{{f1.q}\\cdot{f2.q}\\cdot{f3.p}}}={L(res)}$$\n\n"
               "Tipp: Vor dem Ausmultiplizieren über Kreuz kürzen, dann bleiben die Zahlen klein.")
        hints = ["Wie dividiert man durch einen Bruch?",
                 "Ersetze $:\\,\\frac{a}{b}$ durch $\\cdot\\,\\frac{b}{a}$ (Kehrwert). Dann Zähler mal Zähler, Nenner mal Nenner.",
                 f"Rechne ${L(f1)}\\cdot{L(f2)}\\cdot{L(1 / f3)}$ und kürze (am besten schon vor dem Multiplizieren)."]
    elif kind == "klammer":
        s = rng.choice([1, -1])
        inner = f1 + s * f2
        res = inner * f3
        term = f"\\left({L(f1)}{' + ' if s > 0 else ' - '}{L(f2)}\\right)\\cdot{L(f3)}"
        sol = (f"Zuerst die Klammer (gleichnamig machen):\n\n$${L(f1)}{' + ' if s > 0 else ' - '}{L(f2)}={L(inner)}$$\n\n"
               f"Dann multiplizieren: $${L(inner)}\\cdot{L(f3)}={L(res)}$$")
        hints = ["Was wird zuerst gerechnet: die Klammer oder die Multiplikation?",
                 "Mache die Brüche in der Klammer gleichnamig (Hauptnenner) und fasse sie zusammen.",
                 f"Die Klammer ergibt ${L(inner)}$. Multipliziere nun mit ${L(f3)}$ und kürze."]
    else:
        s = rng.choice([1, -1])
        prod = f2 * f3
        res = f1 + s * prod
        term = f"{L(f1)}{' + ' if s > 0 else ' - '}{L(f2)}\\cdot{L(f3)}"
        sol = (f"**Punkt vor Strich:** zuerst das Produkt ${L(f2)}\\cdot{L(f3)}={L(prod)}$.\n\n"
               f"Dann $${L(f1)}{' + ' if s > 0 else ' - '}{L(prod)}={L(res)}$$")
        hints = ["Achtung Reihenfolge: Welche Rechenart hat Vorrang?",
                 "Punkt vor Strich: Rechne zuerst das Produkt aus.",
                 f"${L(f2)}\\cdot{L(f3)}={L(prod)}$. Jetzt noch mit ${L(f1)}$ verrechnen (Hauptnenner)."]
    return {
        "statement": f"Berechne ohne Rechner (Resultat als gekürzter Bruch): ${term}$",
        "parts": [part("Resultat", {"type": "number", "value": sp.sstr(res)}, sol, hints)],
    }


@gen("gb-bruch-kuerzen-term", "g1", ["g-brueche", "g-terme"], "Bruchterme kürzen", "ohne", 2, 5)
def _bruch_kuerzen(rng):
    c, p, q = rng.sample([v for v in range(-6, 7) if v != 0], 3)
    k = rng.choice([1, 1, 2, 3, -1])
    num = sp.expand(k * (x - c) * (x - p))
    den = sp.expand((x - c) * (x - q))
    ans = k * (x - p) / (x - q)
    sol = (f"Zähler und Nenner faktorisieren (Ausklammern, binomische Formel oder Vieta):\n\n"
           f"$$\\frac{{{L(num)}}}{{{L(den)}}}=\\frac{{{L(sp.factor(num))}}}{{{L(sp.factor(den))}}}$$\n\n"
           f"Den gemeinsamen Faktor $({L(x - c)})$ kürzen (für $x\\neq{c}$):\n\n$$={L(ans)}$$")
    return {
        "statement": f"Kürze den Bruchterm so weit wie möglich: $\\frac{{{L(num)}}}{{{L(den)}}}$",
        "parts": [part("Gekürzter Term", {"type": "expr", "value": sp.sstr(ans), "var": "x"}, sol, [
            "Kürzen darf man nur gemeinsame **Faktoren**, nie einzelne Summanden!",
            "Zerlege Zähler und Nenner in Linearfaktoren $(x-x_1)(x-x_2)$ – z.B. mit Vieta: Produkt und Summe der Nullstellen.",
            f"Beide enthalten den Faktor $({L(x - c)})$. Kürze ihn weg.",
        ])],
    }


@gen("gb-doppelbruch", "g1", ["g-brueche"], "Doppelbrüche vereinfachen", "ohne", 2, 6)
def _doppelbruch(rng):
    kind = rng.choice(["v1", "v2", "num"])
    if kind == "num":
        f1, f2, f3 = _rand_fracs(rng, 3, dens=(2, 3, 4, 5, 6, 8), maxnum=7)
        while f1 == f2:
            f1, f2, f3 = _rand_fracs(rng, 3, dens=(2, 3, 4, 5, 6, 8), maxnum=7)
        top = f1 - f2
        res = top / f3
        term = f"\\frac{{{L(f1)}-{L(f2)}}}{{{L(f3)}}}"
        sol = (f"Zuerst den Zähler zusammenfassen: ${L(f1)}-{L(f2)}={L(top)}$.\n\n"
               f"Doppelbruch = Zähler **mal Kehrwert** des Nenners:\n\n$${L(top)}\\cdot{L(1 / f3)}={L(res)}$$")
        return {
            "statement": f"Berechne ohne Rechner: $${term}$$",
            "parts": [part("Resultat (gekürzter Bruch)", {"type": "number", "value": sp.sstr(res)}, sol, [
                "Ein Doppelbruch ist eine Division: oberer Bruch geteilt durch unteren Bruch.",
                "Fasse zuerst den Zähler zu einem einzigen Bruch zusammen.",
                f"Der Zähler ist ${L(top)}$. Multipliziere ihn mit dem Kehrwert von ${L(f3)}$.",
            ])],
        }
    k = rng.randint(2, 6)
    if kind == "v1":
        term = f"\\frac{{1-\\frac{{{k * k}}}{{x^{{2}}}}}}{{1+\\frac{{{k}}}{{x}}}}"
        ans = (x - k) / x
        sol = (f"Zähler und Nenner je auf einen Bruchstrich bringen:\n\n"
               f"$$1-\\frac{{{k * k}}}{{x^2}}=\\frac{{x^2-{k * k}}}{{x^2}}=\\frac{{(x-{k})(x+{k})}}{{x^2}},\\qquad 1+\\frac{{{k}}}{{x}}=\\frac{{x+{k}}}{{x}}$$\n\n"
               f"Mit dem Kehrwert des Nenners multiplizieren:\n\n"
               f"$$\\frac{{(x-{k})(x+{k})}}{{x^2}}\\cdot\\frac{{x}}{{x+{k}}}=\\frac{{x-{k}}}{{x}}$$")
        h3 = f"Zähler: $\\frac{{(x-{k})(x+{k})}}{{x^2}}$ (3. binomische Formel), Nenner: $\\frac{{x+{k}}}{{x}}$. Jetzt mal Kehrwert und kürzen."
    else:
        term = f"\\frac{{\\frac{{1}}{{x}}+\\frac{{1}}{{{k}}}}}{{\\frac{{1}}{{x^{{2}}}}-\\frac{{1}}{{{k * k}}}}}"
        ans = k * x / (k - x)
        sol = (f"Zähler und Nenner je auf einen Bruchstrich bringen:\n\n"
               f"$$\\frac{{1}}{{x}}+\\frac{{1}}{{{k}}}=\\frac{{{k}+x}}{{{k}x}},\\qquad \\frac{{1}}{{x^2}}-\\frac{{1}}{{{k * k}}}=\\frac{{{k * k}-x^2}}{{{k * k}x^2}}=\\frac{{({k}-x)({k}+x)}}{{{k * k}x^2}}$$\n\n"
               f"Mit dem Kehrwert des Nenners multiplizieren und kürzen:\n\n"
               f"$$\\frac{{{k}+x}}{{{k}x}}\\cdot\\frac{{{k * k}x^2}}{{({k}-x)({k}+x)}}=\\frac{{{k}x}}{{{k}-x}}$$")
        h3 = f"Zähler: $\\frac{{{k}+x}}{{{k}x}}$, Nenner: $\\frac{{({k}-x)({k}+x)}}{{{k * k}x^2}}$. Jetzt mal Kehrwert und kürzen."
    return {
        "statement": f"Vereinfache den Doppelbruch so weit wie möglich: $${term}$$",
        "parts": [part("Vereinfachter Term", {"type": "expr", "value": sp.sstr(ans), "var": "x"}, sol, [
            "Ein Doppelbruch ist «Bruch durch Bruch». Wie dividiert man durch einen Bruch?",
            "Bringe zuerst Zähler und Nenner je auf einen einzigen Bruchstrich (Hauptnenner), dann mal Kehrwert.",
            h3,
        ])],
    }


@gen("gb-bruch-hauptnenner", "g1", ["g-brueche", "g-terme"], "Bruchterme gleichnamig machen", "ohne", 2, 5)
def _bruch_hn(rng):
    k, m = rng.sample([v for v in range(-6, 7) if v != 0], 2)
    a, b = _nz(rng, 1, 6), _nz(rng, 1, 6)
    s = rng.choice([1, -1])
    d1, d2 = x - k, x + m
    num = sp.expand(a * d2 + s * b * d1)
    if num == 0 or d1 == d2:
        s = 1
        num = sp.expand(a * d2 + b * d1)
    lhs = f"\\frac{{{a}}}{{{L(d1)}}}{' + ' if s > 0 else ' - '}\\frac{{{b}}}{{{L(d2)}}}"
    den = f"\\left({L(d1)}\\right)\\left({L(d2)}\\right)"
    sol = (f"Hauptnenner ist das Produkt ${den}$. Jeden Bruch mit dem fehlenden Faktor erweitern:\n\n"
           f"$${lhs}=\\frac{{{a}\\left({L(d2)}\\right){' + ' if s > 0 else ' - '}{b}\\left({L(d1)}\\right)}}{{{den}}}$$\n\n"
           f"Zähler ausmultiplizieren und zusammenfassen: $${a}({L(d2)}){' + ' if s > 0 else ' - '}{b}({L(d1)})={L(num)}$$")
    return {
        "statement": f"Fasse zu einem Bruch zusammen: $${lhs}=\\frac{{\\ldots}}{{{den}}}$$",
        "parts": [part("Zähler (ausmultipliziert und zusammengefasst)", {"type": "expr", "value": sp.sstr(num), "var": "x"}, sol, [
            "Mit welchem Faktor musst du jeden Bruch erweitern, damit unten der Hauptnenner steht?",
            f"Erweitere $\\frac{{{a}}}{{{L(d1)}}}$ mit $({L(d2)})$ und $\\frac{{{b}}}{{{L(d2)}}}$ mit $({L(d1)})$.",
            f"Zähler: ${a}({L(d2)}){' + ' if s > 0 else ' - '}{b}({L(d1)})$ – Achtung auf das Vorzeichen vor der zweiten Klammer!",
        ])],
    }


# ───────────── Potenzen ─────────────

def _pot_item(rng, kind):
    if kind == "neg":
        b = rng.randint(2, 5)
        m = rng.randint(1, 3 if b <= 3 else 2)
        val = R(1, b ** m)
        expr = f"{b}^{{-{m}}}"
        sol = f"Negativer Exponent = Kehrwert: ${expr}=\\frac{{1}}{{{b}^{{{m}}}}}={L(val)}$."
        hints = ["Was bedeutet ein negativer Exponent?", "$a^{-n}=\\frac{1}{a^n}$.", f"Berechne zuerst ${b}^{{{m}}}$ und nimm davon den Kehrwert."]
    elif kind == "bruchneg":
        p, q = rng.sample([1, 2, 3, 4, 5], 2)
        while math.gcd(p, q) != 1:
            p, q = rng.sample([1, 2, 3, 4, 5], 2)
        m = rng.choice([1, 2, 2, 3]) if max(p, q) <= 3 else rng.choice([1, 2])
        val = R(q, p) ** m
        expr = f"\\left({L(R(p, q))}\\right)^{{-{m}}}"
        sol = f"Negativer Exponent: Bruch umdrehen. ${expr}=\\left({L(R(q, p))}\\right)^{{{m}}}={L(val)}$."
        hints = ["Was macht ein negativer Exponent mit einem Bruch?", "$\\left(\\frac{a}{b}\\right)^{-n}=\\left(\\frac{b}{a}\\right)^{n}$.",
                 f"Drehe den Bruch um und potenziere Zähler und Nenner je mit ${m}$."]
    elif kind == "prod":
        b = rng.choice([2, 3])
        while True:
            e1, e2 = rng.randint(3, 8), rng.randint(-7, -1)
            if 0 <= e1 + e2 <= (5 if b == 2 else 3):
                break
        val = sp.Integer(b) ** (e1 + e2)
        expr = f"{b}^{{{e1}}}\\cdot {b}^{{{e2}}}"
        sol = f"Gleiche Basis: Exponenten addieren. ${expr}={b}^{{{e1}+({e2})}}={b}^{{{e1 + e2}}}={L(val)}$."
        hints = ["Beide Potenzen haben die gleiche Basis.", "$a^m\\cdot a^n=a^{m+n}$.", f"Addiere die Exponenten ${e1}$ und ${e2}$."]
    elif kind == "quot":
        b = rng.choice([2, 3, 5, 10])
        while True:
            e1, e2 = rng.randint(-3, 7), rng.randint(-3, 7)
            d = e1 - e2
            if e1 != e2 and -2 <= d <= (4 if b == 2 else 2) and e2 != 0 and e1 != 0:
                break
        val = sp.Integer(b) ** d
        expr = f"\\frac{{{b}^{{{e1}}}}}{{{b}^{{{e2}}}}}"
        sol = f"Gleiche Basis: Exponenten subtrahieren. ${expr}={b}^{{{e1}-({e2})}}={b}^{{{d}}}={L(val)}$."
        hints = ["Zähler und Nenner haben die gleiche Basis.", "$\\frac{a^m}{a^n}=a^{m-n}$.", f"Rechne den Exponenten ${e1}-({e2})$ aus (Klammer beachten!)."]
    elif kind == "minus":
        b = rng.choice([2, 3])
        n = rng.choice([2, 3, 4]) if b == 2 else rng.choice([2, 3])
        if rng.random() < 0.5:
            expr = f"\\left(-{b}\\right)^{{{n}}}"
            val = sp.Integer(-b) ** n
            sol = f"Die Klammer gehört zur Basis: ${expr}=" + "\\cdot".join([f"(-{b})"] * n) + f"={val}$."
        else:
            expr = f"-{b}^{{{n}}}"
            val = -sp.Integer(b) ** n
            sol = f"Ohne Klammer gilt der Exponent nur für die ${b}$: ${expr}=-({b}^{{{n}}})={val}$."
        hints = ["Gehört das Minuszeichen zur Basis oder nicht?", "$(-a)^n$: Klammer → das Minus wird mitpotenziert. $-a^n$: zuerst $a^n$, dann das Minus davor.",
                 "Bei geradem Exponenten wird $(-a)^n$ positiv, bei ungeradem negativ."]
    elif kind == "null":
        a, b = rng.randint(2, 9), rng.randint(2, 6)
        val = 1 + R(1, b)
        expr = f"{a}^{{0}}+{b}^{{-1}}"
        sol = f"$a^0=1$ (für $a\\neq0$) und $a^{{-1}}=\\frac{{1}}{{a}}$: ${expr}=1+\\frac{{1}}{{{b}}}={L(val)}$."
        hints = ["Was ergibt eine Zahl hoch $0$?", "$a^0=1$, $a^{-1}=\\frac1a$.", f"Rechne $1+\\frac{{1}}{{{b}}}$."]
    else:  # pot
        b = rng.choice([2, 3])
        while True:
            m, n = rng.choice([-2, -1, 2, 3]), rng.choice([2, 3])
            if abs(m * n) <= (6 if b == 2 else 4):
                break
        val = sp.Integer(b) ** (m * n)
        expr = f"\\left({b}^{{{m}}}\\right)^{{{n}}}"
        sol = f"Potenz einer Potenz: Exponenten multiplizieren. ${expr}={b}^{{{m}\\cdot{n}}}={b}^{{{m * n}}}={L(val)}$."
        hints = ["Hier wird eine Potenz nochmals potenziert.", "$(a^m)^n=a^{m\\cdot n}$.", f"Multipliziere die Exponenten ${m}$ und ${n}$."]
    return expr, val, sol, hints


@gen("gb-potenz-zahl", "g1", ["g-potenzen"], "Potenzen berechnen (auch negative Exponenten)", "ohne", 1, 4)
def _pot_zahl(rng):
    kinds = rng.sample(["neg", "bruchneg", "prod", "quot", "minus", "null", "pot"], 3)
    parts = []
    for lab, kind in zip("abc", kinds):
        expr, val, sol, hints = _pot_item(rng, kind)
        parts.append(part(f"${expr}=$", {"type": "number", "value": sp.sstr(val)}, sol, hints, lab))
    return {"statement": "Berechne ohne Rechner (Brüche gekürzt angeben):", "parts": parts}


@gen("gb-potenz-vereinfachen", "g1", ["g-potenzen"], "Potenzterme vereinfachen", "ohne", 2, 5)
def _pot_vereinf(rng):
    a, b = a_, b_
    if rng.random() < 0.5:
        while True:
            m, n, k = rng.randint(1, 3), rng.choice([-2, -1, 1, 2, 3]), rng.choice([2, 3])
            ea, eb = rng.randint(-2, 4), rng.choice([-3, -2, -1, 1, 2, 3])
            p, q = m * k - ea, n * k - eb
            if p != 0 and q != 0 and abs(p) <= 9 and abs(q) <= 9 and ea != 0:
                break
        ans = a ** ea * b ** eb
        term = f"\\frac{{\\left({_pw('a', m)} {_pw('b', n)}\\right)^{{{k}}}}}{{{_pw('a', p)} {_pw('b', q)}}}"
        sol = (f"1. Klammer potenzieren (jeden Faktor, Exponenten multiplizieren): "
               f"$\\left({_pw('a', m)} {_pw('b', n)}\\right)^{{{k}}}=a^{{{m * k}}}b^{{{n * k}}}$.\n\n"
               f"2. Gleiche Basen dividieren (Exponenten subtrahieren): "
               f"$a^{{{m * k}-({p})}}\\,b^{{{n * k}-({q})}}=a^{{{ea}}}b^{{{eb}}}$.\n\n$$={L(ans)}$$")
        hints = ["Beginne mit der Klammer: Wie potenziert man ein Produkt?",
                 "$(a^m b^n)^k=a^{mk}b^{nk}$, danach $\\frac{a^r}{a^s}=a^{r-s}$ für jede Basis separat.",
                 f"Nach dem Auflösen der Klammer hast du $a^{{{m * k}}}b^{{{n * k}}}$ im Zähler. Subtrahiere nun die Exponenten des Nenners."]
    else:
        while True:
            c2, r = rng.randint(2, 6), rng.choice([2, 3, 4, 5, R(1, 2), R(1, 3)])
            c1 = sp.Integer(c2) * r
            p1, q1, p2, q2 = rng.randint(-2, 6), rng.randint(-3, 5), rng.randint(-3, 4), rng.randint(-2, 5)
            ea, eb = p1 - p2, q1 - q2
            if c1.q == 1 and 0 not in (p1, q1, p2, q2, ea, eb):
                break
        c1 = int(c1)
        ans = r * a ** ea * b ** eb
        term = f"\\frac{{{c1}\\,{_pw('a', p1)} {_pw('b', q1)}}}{{{c2}\\,{_pw('a', p2)} {_pw('b', q2)}}}"
        sol = (f"Zahlen, $a$-Potenzen und $b$-Potenzen getrennt behandeln:\n\n"
               f"$$\\frac{{{c1}}}{{{c2}}}={L(r)},\\quad a^{{{p1}-({p2})}}=a^{{{ea}}},\\quad b^{{{q1}-({q2})}}=b^{{{eb}}}$$\n\n$$={L(ans)}$$")
        hints = ["Behandle die Zahlen und jede Variable einzeln.",
                 "Zahlen kürzen, und für jede Basis gilt $\\frac{a^r}{a^s}=a^{r-s}$.",
                 f"Rechne die Exponenten aus: für $a$: ${p1}-({p2})$, für $b$: ${q1}-({q2})$."]
    return {
        "statement": f"Vereinfache so weit wie möglich ($a,b>0$; negative Exponenten sind im Resultat erlaubt): $${term}$$",
        "parts": [part("Vereinfachter Term", {"type": "expr", "value": sp.sstr(ans), "var": "a,b"}, sol, hints)],
    }


@gen("gb-potenz-exponent", "g1", ["g-potenzen"], "Als eine Potenz schreiben", "ohne", 1, 3)
def _pot_exp(rng):
    kind = rng.choice(["A", "B", "C"])
    while True:
        if kind == "A":
            m, n, k = rng.randint(-4, 7), rng.randint(-5, 6), rng.randint(-4, 6)
            if 0 in (m, n, k):
                continue
            r = m + n - k
            term = f"\\frac{{x^{{{m}}}\\cdot x^{{{n}}}}}{{x^{{{k}}}}}"
            steps = f"x^{{{m}+({n})-({k})}}"
        elif kind == "B":
            m, n, k = rng.choice([-3, -2, 2, 3, 4]), rng.choice([-2, 2, 3]), rng.randint(-6, 6)
            if k == 0:
                continue
            r = m * n + k
            term = f"\\left(x^{{{m}}}\\right)^{{{n}}}\\cdot x^{{{k}}}"
            steps = f"x^{{{m}\\cdot({n})+({k})}}"
        else:
            m, n, k = rng.randint(1, 5), rng.randint(-3, 6), rng.randint(2, 3)
            if n == 0:
                continue
            r = m + n - 2 * k
            term = f"\\frac{{1}}{{x^{{-{m}}}}}\\cdot\\frac{{x^{{{n}}}}}{{\\left(x^{{2}}\\right)^{{{k}}}}}"
            steps = f"x^{{{m}}}\\cdot x^{{{n}}}\\cdot x^{{-{2 * k}}}=x^{{{m}+({n})-{2 * k}}}"
        if r != 0:
            break
    sol = f"Potenzgesetze anwenden: $${term}={steps}=x^{{{r}}}$$\n\nAlso $r={r}$."
    return {
        "statement": f"Schreibe als eine einzige Potenz $x^r$ ($x\\neq0$) und gib den Exponenten $r$ an: $${term}$$",
        "parts": [part("$r=$", {"type": "number", "value": str(r)}, sol, [
            "Alle Faktoren haben die Basis $x$ – du musst nur noch mit den Exponenten rechnen.",
            "$x^m\\cdot x^n=x^{m+n}$, $\\frac{x^m}{x^n}=x^{m-n}$, $(x^m)^n=x^{mn}$, $\\frac{1}{x^{-m}}=x^{m}$.",
            "Schreibe jeden Faktor als $x^{\\text{Zahl}}$ und addiere bzw. subtrahiere die Exponenten. Achtung bei Minuszeichen!",
        ])],
    }


@gen("gb-potenz-basis", "g1", ["g-potenzen"], "Potenzen mit gleichen Exponenten", "ohne", 2, 4)
def _pot_basis(rng):
    kind = rng.choice(["A", "B", "C"])
    if kind == "A":
        p, q = rng.choice([(2, 5), (2, 3), (3, 5), (2, 5)])
        n = rng.randint(3, 7)
        k = rng.choice([1, 2]) if p * q <= 10 else 1
        m = n - k
        val = sp.Integer(p * q) ** k
        term = f"\\frac{{{p}^{{{n}}}\\cdot {q}^{{{n}}}}}{{{p * q}^{{{m}}}}}"
        sol = (f"Gleiche Exponenten: $a^n\\cdot b^n=(ab)^n$, also ${p}^{{{n}}}\\cdot{q}^{{{n}}}={p * q}^{{{n}}}$.\n\n"
               f"$$\\frac{{{p * q}^{{{n}}}}}{{{p * q}^{{{m}}}}}={p * q}^{{{n}-{m}}}={p * q}^{{{k}}}={val}$$")
        h3 = f"${p}^{{{n}}}\\cdot{q}^{{{n}}}={p * q}^{{{n}}}$. Jetzt hast du Zähler und Nenner mit gleicher Basis."
    elif kind == "B":
        p, q = rng.choice([(2, 3), (3, 2), (4, 3), (2, 5), (3, 4), (5, 2), (4, 5)])
        n = rng.choice([2, 3]) if q <= 4 else 2
        if q ** n > 125:
            n = 2
        val = sp.Integer(q) ** n
        term = f"\\frac{{{p * q}^{{{n}}}}}{{{p}^{{{n}}}}}"
        sol = f"Gleiche Exponenten: $\\frac{{a^n}}{{b^n}}=\\left(\\frac{{a}}{{b}}\\right)^n$.\n\n$${term}=\\left(\\frac{{{p * q}}}{{{p}}}\\right)^{{{n}}}={q}^{{{n}}}={val}$$"
        h3 = f"Rechne zuerst $\\frac{{{p * q}}}{{{p}}}$ und potenziere dann mit ${n}$."
    else:
        p, q = rng.choice([(2, 3), (2, 5), (3, 2), (4, 2), (5, 2), (2, 2), (3, 3)])
        n = rng.choice([2, 3, 4]) if q <= 3 else rng.choice([2, 3])
        val = sp.Integer(q) ** n
        term = f"\\left(\\frac{{1}}{{{p}}}\\right)^{{{n}}}\\cdot {p * q}^{{{n}}}"
        sol = f"Gleiche Exponenten: $a^n\\cdot b^n=(a\\cdot b)^n$.\n\n$${term}=\\left(\\frac{{1}}{{{p}}}\\cdot {p * q}\\right)^{{{n}}}={q}^{{{n}}}={val}$$"
        h3 = f"Rechne zuerst $\\frac{{1}}{{{p}}}\\cdot{p * q}$ und potenziere dann mit ${n}$."
    return {
        "statement": f"Berechne geschickt ohne Rechner: $${term}$$",
        "parts": [part("Resultat", {"type": "number", "value": sp.sstr(val)}, sol, [
            "Nicht alles einzeln ausrechnen – schau auf die Exponenten!",
            "Bei gleichen Exponenten darf man die Basen zusammennehmen: $a^n\\cdot b^n=(ab)^n$ und $\\frac{a^n}{b^n}=\\left(\\frac ab\\right)^n$.",
            h3,
        ])],
    }


# ───────────── Wurzeln ─────────────

@gen("gb-wurzel-teilweise", "g1", ["g-wurzeln"], "Wurzeln teilweise ziehen", "ohne", 1, 5)
def _wurzel_teil(rng):
    m = rng.choice([2, 3, 5, 6, 7, 10])
    k = rng.randint(2, 7)
    while k * k * m > 300:
        k -= 1
    N = k * k * m
    pa = part(f"$\\sqrt{{{N}}}=$", {"type": "number", "value": f"{k}*sqrt({m})"},
              f"Grösste Quadratzahl als Faktor suchen: ${N}={k * k}\\cdot{m}$.\n\n$$\\sqrt{{{N}}}=\\sqrt{{{k * k}}}\\cdot\\sqrt{{{m}}}={k}\\sqrt{{{m}}}$$", [
                  "Zerlege die Zahl unter der Wurzel in ein Produkt, das eine Quadratzahl enthält.",
                  "$\\sqrt{a\\cdot b}=\\sqrt a\\cdot\\sqrt b$. Quadratzahlen: 4, 9, 16, 25, 36, 49, …",
                  f"${N}={k * k}\\cdot{m}$ – ziehe die Wurzel aus ${k * k}$.",
              ], "a")
    m2 = rng.choice([2, 3, 5, 6])
    while True:
        p, q, r = rng.randint(1, 5), rng.randint(1, 5), rng.randint(1, 5)
        c = p + q - r
        if c != 0 and len({p, q, r}) >= 2:
            break

    def rt(u):
        return f"\\sqrt{{{u * u * m2}}}"
    term = f"{rt(p)}+{rt(q)}-{rt(r)}"
    pb = part(f"${term}=$", {"type": "number", "value": f"{c}*sqrt({m2})"},
              f"Jede Wurzel teilweise ziehen:\n\n$${rt(p)}={p}\\sqrt{{{m2}}},\\ {rt(q)}={q}\\sqrt{{{m2}}},\\ {rt(r)}={r}\\sqrt{{{m2}}}$$\n\n"
              f"Gleiche Wurzeln zusammenfassen: $({p}+{q}-{r})\\sqrt{{{m2}}}={L(c * sp.sqrt(m2))}$", [
                  "Wurzeln mit verschiedenen Radikanden kann man nicht direkt addieren. Kann man sie gleich machen?",
                  f"Ziehe jede Wurzel teilweise, sodass überall $\\sqrt{{{m2}}}$ übrig bleibt.",
                  f"Danach zusammenfassen wie $3a+2a-a$, mit $a=\\sqrt{{{m2}}}$.",
              ], "b")
    m3 = rng.choice([2, 3, 5])
    u, v = rng.randint(1, 4), rng.randint(2, 5)
    A, B = u * u * m3, v * v * m3
    val = u * v * m3
    pc = part(f"$\\sqrt{{{A}}}\\cdot\\sqrt{{{B}}}=$", {"type": "number", "value": str(val)},
              f"$$\\sqrt{{{A}}}\\cdot\\sqrt{{{B}}}=\\sqrt{{{A}\\cdot{B}}}=\\sqrt{{{A * B}}}={val}$$\n\n(oder: ${u}\\sqrt{{{m3}}}\\cdot{v}\\sqrt{{{m3}}}={u * v}\\cdot{m3}={val}$)", [
                  "Wurzeln darf man multiplizieren, indem man die Radikanden multipliziert.",
                  "$\\sqrt a\\cdot\\sqrt b=\\sqrt{a\\cdot b}$.",
                  f"Berechne ${A}\\cdot{B}$ – das Resultat ist eine Quadratzahl.",
              ], "c")
    return {"statement": "Vereinfache ohne Rechner (Resultat in der Form $a\\sqrt{b}$ oder als ganze Zahl, z.B. `3*sqrt(2)`):",
            "parts": [pa, pb, pc]}


@gen("gb-wurzel-potenz", "g1", ["g-wurzeln", "g-potenzen"], "Wurzeln als Potenzen schreiben", "ohne", 2, 4)
def _wurzel_potenz(rng):
    kind = rng.choice(["A", "B", "C", "D"])
    while True:
        if kind == "A":
            n, a = rng.choice([3, 4, 5]), rng.randint(1, 4)
            r = R(a, n) + R(1, 2)
            term = f"\\sqrt[{n}]{{x^{{{a}}}}}\\cdot\\sqrt{{x}}"
            st = f"x^{{\\frac{{{a}}}{{{n}}}}}\\cdot x^{{\\frac{{1}}{{2}}}}=x^{{\\frac{{{a}}}{{{n}}}+\\frac{{1}}{{2}}}}"
        elif kind == "B":
            n, a, m, b = rng.choice([2, 3, 4]), rng.randint(1, 5), rng.choice([2, 3, 4, 5]), rng.randint(1, 3)
            if n == m:
                continue
            r = R(a, n) - R(b, m)
            term = f"\\frac{{{('\\sqrt[' + str(n) + ']') if n != 2 else '\\sqrt'}{{x^{{{a}}}}}}}{{{('\\sqrt[' + str(m) + ']') if m != 2 else '\\sqrt'}{{x^{{{b}}}}}}}"
            st = f"\\frac{{x^{{\\frac{{{a}}}{{{n}}}}}}}{{x^{{\\frac{{{b}}}{{{m}}}}}}}=x^{{\\frac{{{a}}}{{{n}}}-\\frac{{{b}}}{{{m}}}}}"
        elif kind == "C":
            n, a = rng.choice([2, 3]), rng.randint(1, 3)
            r = (a + R(1, 2)) / n
            rad = "\\sqrt" if n == 2 else f"\\sqrt[{n}]"
            term = f"{rad}{{x^{{{a}}}\\cdot\\sqrt{{x}}}}"
            st = f"\\left(x^{{{a}}}\\cdot x^{{\\frac{{1}}{{2}}}}\\right)^{{\\frac{{1}}{{{n}}}}}=\\left(x^{{{L(a + R(1, 2))}}}\\right)^{{\\frac{{1}}{{{n}}}}}"
        else:
            n, a = rng.choice([2, 3, 4, 5]), rng.randint(1, 4)
            r = -R(a, n)
            rad = "\\sqrt" if n == 2 else f"\\sqrt[{n}]"
            term = f"\\frac{{1}}{{{rad}{{x^{{{a}}}}}}}"
            st = f"\\frac{{1}}{{x^{{\\frac{{{a}}}{{{n}}}}}}}=x^{{-\\frac{{{a}}}{{{n}}}}}"
        if r != 0:
            break
    sol = f"Umschreiben mit $\\sqrt[n]{{x^m}}=x^{{\\frac mn}}$, dann Potenzgesetze:\n\n$${term}={st}=x^{{{L(r)}}}$$\n\nAlso $r={L(r)}$."
    return {
        "statement": f"Schreibe als eine Potenz $x^r$ ($x>0$) und gib den Exponenten $r$ als Bruch an: $${term}$$",
        "parts": [part("$r=$", {"type": "number", "value": sp.sstr(r)}, sol, [
            "Jede Wurzel lässt sich als Potenz mit gebrochenem Exponenten schreiben.",
            "$\\sqrt[n]{x^m}=x^{\\frac{m}{n}}$, insbesondere $\\sqrt{x}=x^{\\frac12}$. Danach gelten die üblichen Potenzgesetze.",
            "Schreibe alle Wurzeln als Potenzen und addiere/subtrahiere bzw. multipliziere die Exponenten (Hauptnenner!).",
        ])],
    }


@gen("gb-wurzel-exponent-zahl", "g1", ["g-wurzeln"], "Gebrochene Exponenten berechnen", "ohne", 1, 4)
def _wurzel_expzahl(rng):
    parts = []
    used = set()
    for lab in "ab":
        while True:
            b, q = rng.randint(2, 5), rng.choice([2, 3, 4])
            p = rng.choice([1, 2, 3, -1, -2])
            if b ** q <= 625 and math.gcd(abs(p), q) == 1 and (b, q, p) not in used and abs(b ** p) <= 125:
                used.add((b, q, p))
                break
        A = b ** q
        e = R(p, q)
        val = sp.Integer(b) ** p
        term = f"{A}^{{{L(e)}}}"
        sol = (f"$a^{{\\frac pq}}=\\left(\\sqrt[q]{{a}}\\right)^p$: $\\sqrt[{q}]{{{A}}}={b}$, also\n\n"
               f"$${term}={b}^{{{p}}}={L(val)}$$")
        parts.append(part(f"${term}=$", {"type": "number", "value": sp.sstr(val)}, sol, [
            "Der Nenner des Exponenten ist der Wurzelexponent.",
            f"$a^{{\\frac pq}}=\\left(\\sqrt[q]{{a}}\\right)^p$. Berechne zuerst $\\sqrt[{q}]{{{A}}}$.",
            f"$\\sqrt[{q}]{{{A}}}={b}$. Jetzt noch hoch ${p}$ (negativ → Kehrwert).",
        ], lab))
    return {"statement": "Berechne ohne Rechner:", "parts": parts}


# ───────────── Terme ─────────────

@gen("gb-ausmultiplizieren", "g1", ["g-terme"], "Ausmultiplizieren und zusammenfassen", "ohne", 1, 4)
def _ausmult(rng):
    kind = rng.choice(["A", "B", "C"])
    if kind == "A":
        a, b, c, d = _nz(rng, -4, 5), _nz(rng, -7, 7), _nz(rng, -4, 5), _nz(rng, -7, 7)
        k, m = _nz(rng, -5, 5), _nz(rng, -6, 6)
        term = f"\\left({L(a * x + b)}\\right)\\left({L(c * x + d)}\\right) {_sterm(k, L(x - m))}"
        val = (a * x + b) * (c * x + d) + k * (x - m)
        st = f"{L(sp.expand((a * x + b) * (c * x + d)))} + \\left({L(sp.expand(k * (x - m)))}\\right)"
    elif kind == "B":
        a, b, c = _nz(rng, 1, 4), _nz(rng, -5, 5), _nz(rng, -6, 6)
        d, f, g, h = _nz(rng, 1, 4), _nz(rng, -6, 6), _nz(rng, 1, 3), _nz(rng, -6, 6)
        term = f"{_co(a)}\\left({L(b * x + c)}\\right) - \\left({L(d * x + f)}\\right)\\left({L(g * x + h)}\\right)"
        val = a * x * (b * x + c) - (d * x + f) * (g * x + h)
        st = f"{L(sp.expand(a * x * (b * x + c)))} - \\left({L(sp.expand((d * x + f) * (g * x + h)))}\\right)"
    else:
        a, b, c = _nz(rng, -5, 5), _nz(rng, -4, 4), _nz(rng, -6, 6)
        term = f"\\left({L(x + a)}\\right)\\left({L(x**2 + b * x + c)}\\right)"
        val = (x + a) * (x**2 + b * x + c)
        st = f"x\\cdot\\left({L(x**2 + b * x + c)}\\right) {_sterm(a, L(x**2 + b * x + c))}"
    ans = sp.expand(val)
    sol = (f"Jeden Summanden der einen Klammer mit jedem Summanden der anderen multiplizieren, dann gleichartige Terme zusammenfassen:\n\n"
           f"$${term}$$\n\n$$={st}$$\n\n$$={L(ans)}$$")
    return {
        "statement": f"Multipliziere aus und fasse zusammen: $${term}$$",
        "parts": [part("Ausmultiplizierter Term", {"type": "expr", "value": sp.sstr(ans), "var": "x"}, sol, [
            "Löse zuerst die Klammern auf, danach zusammenfassen.",
            "Klammer mal Klammer: jeder Summand mal jeder Summand. Ein Minus vor einer Klammer dreht alle Vorzeichen in der Klammer um.",
            "Ordne das Resultat nach Potenzen von $x$: zuerst $x^3$ bzw. $x^2$, dann $x$, dann die Zahl.",
        ])],
    }


@gen("gb-ausklammern", "g1", ["g-terme"], "Ausklammern (gemeinsamer Faktor)", "ohne", 1, 4)
def _ausklammern(rng):
    while True:
        k, s = rng.choice([1, 2, 3, 4, 5, 6]), rng.choice([0, 1, 1, 2])
        a2, a1, a0 = rng.randint(1, 5), _nz(rng, -7, 7), _nz(rng, -6, 6)
        if math.gcd(math.gcd(a2, a1), a0) == 1 and (k > 1 or s > 0):
            break
    g = k * x**s
    inner = a2 * x**2 + a1 * x + a0
    poly = sp.expand(g * inner)
    sol = (f"Gemeinsamer Zahlenfaktor: ggT der Koeffizienten $={k}$. Gemeinsame $x$-Potenz: die kleinste vorkommende, "
           f"${L(x**s) if s else '1 (kein x in jedem Summanden)'}$.\n\n"
           f"$${L(poly)}={L(g)}\\cdot\\left({L(inner)}\\right)$$\n\n"
           f"Kontrolle: Ausmultiplizieren ergibt wieder den ursprünglichen Term.")
    return {
        "statement": f"Klammere den grössten gemeinsamen Faktor (mit positivem Vorzeichen) aus: $${L(poly)}=\\square\\cdot\\left(\\ldots\\right)$$",
        "parts": [
            part("Ausgeklammerter Faktor $\\square=$", {"type": "expr", "value": sp.sstr(g), "var": "x"}, sol, [
                "Welche Zahl und welche Potenz von $x$ steckt in **jedem** Summanden?",
                "Zahl: grösster gemeinsamer Teiler (ggT) der Koeffizienten. Variable: die kleinste vorkommende Potenz von $x$.",
                f"Der ggT der Koeffizienten ist ${k}$.",
            ], "a"),
            part("Inhalt der Klammer", {"type": "expr", "value": sp.sstr(inner), "var": "x"}, sol, [
                "Was bleibt von jedem Summanden übrig, wenn du den Faktor herausnimmst?",
                "Teile jeden Summanden durch den ausgeklammerten Faktor.",
                f"Rechne z.B. $\\frac{{{L(poly.as_ordered_terms()[0])}}}{{{L(g)}}}$ für den ersten Summanden.",
            ], "b"),
        ],
    }


@gen("gb-faktorisieren-vieta", "g1", ["g-terme", "g-quad-gleichung"], "Faktorisieren mit Vieta", "ohne", 2, 4)
def _vieta(rng):
    a, b = rng.sample([v for v in range(-9, 10) if v != 0], 2)
    poly = sp.expand((x + a) * (x + b))
    p, q = a + b, a * b
    sol = (f"Gesucht sind zwei Zahlen mit **Produkt** ${q}$ und **Summe** ${p}$ (Satz von Vieta): ${a}$ und ${b}$.\n\n"
           f"$$ {L(poly)}=\\left({L(x + a)}\\right)\\left({L(x + b)}\\right)$$\n\n"
           f"Nullstellen (Satz vom Nullprodukt): $x_1={-a}$, $x_2={-b}$.")
    return {
        "statement": f"Zerlege in Linearfaktoren: $${L(poly)}=(x+a)(x+b)$$",
        "parts": [
            part("$a$ und $b$ (getrennt mit ;)", {"type": "set", "value": [str(a), str(b)]}, sol, [
                "Multipliziere $(x+a)(x+b)$ in Gedanken aus. Was entspricht dem Koeffizienten von $x$, was dem konstanten Glied?",
                f"Du suchst zwei ganze Zahlen mit Produkt ${q}$ und Summe ${p}$.",
                f"Liste die Zerlegungen von ${q}$ in zwei Faktoren auf (Vorzeichen beachten!) und prüfe jeweils die Summe.",
            ], "a"),
            part("Nullstellen der Funktion $f(x)=" + L(poly) + "$ (getrennt mit ;)", {"type": "set", "value": [str(-a), str(-b)]}, sol, [
                "Wann ist ein Produkt gleich null?",
                "$(x+a)(x+b)=0$, wenn $x+a=0$ oder $x+b=0$.",
                "Die Nullstellen sind $-a$ und $-b$ – Vorzeichen umdrehen!",
            ], "b"),
        ],
    }


@gen("gb-terme-vereinfachen", "g1", ["g-terme"], "Terme mit Klammern vereinfachen", "ohne", 1, 4)
def _terme_vereinf(rng):
    a, b = a_, b_
    if rng.random() < 0.5:
        c1, c2, c3, c4, c5, c6 = _nz(rng, 1, 7), _nz(rng, -5, 5), _nz(rng, 1, 4), _nz(rng, 1, 6), _nz(rng, -5, 5), _nz(rng, -6, 6)
        term = f"{c1}a {_sterm(c2, L(b - c3 * a))} - \\left({L(c4 * a - c5 * b)}\\right) {_sco(c6, 'b')}"
        val = c1 * a + c2 * (b - c3 * a) - (c4 * a - c5 * b) + c6 * b
    else:
        p, q, r, s, t = rng.randint(2, 4), _nz(rng, -4, 4), _nz(rng, -3, 3), _nz(rng, -4, 4), _nz(rng, -5, 5)
        term = f"{p}a\\left({L(a - q * b)}\\right) {_sterm(r, L(a**2 - s * a * b))} {_sco(t, 'b^{2}')}"
        val = p * a * (a - q * b) + r * (a**2 - s * a * b) + t * b**2
    ans = sp.expand(val)
    if ans == 0:
        ans = sp.expand(val)
    sol = (f"1. Klammern auflösen (Vorzeichen vor der Klammer auf jeden Summanden anwenden).\n\n"
           f"2. Gleichartige Terme zusammenfassen.\n\n$${term}={L(ans)}$$")
    return {
        "statement": f"Vereinfache: $${term}$$",
        "parts": [part("Vereinfachter Term (Produkte mit *, z.B. `3*a*b`)", {"type": "expr", "value": sp.sstr(ans), "var": "a,b"}, sol, [
            "Löse zuerst alle Klammern auf.",
            "Faktor vor der Klammer mit **jedem** Summanden multiplizieren; ein Minus vor der Klammer kehrt alle Vorzeichen um.",
            "Sortiere danach: alle $a^2$-Terme, alle $ab$-Terme, alle $a$-Terme, alle $b$-Terme – und addiere jeweils die Koeffizienten.",
        ])],
    }


# ───────────── Binomische Formeln ─────────────

@gen("gb-binom-vorwaerts", "g1", ["g-binome"], "Binomische Formeln anwenden", "ohne", 1, 4)
def _binom_vor(rng):
    kinds = rng.sample(["plus", "minus", "dritte"], 2)
    parts = []
    for lab, kind in zip("ab", kinds):
        a, b = rng.randint(1, 5), rng.randint(1, 9)
        use_y = rng.random() < 0.4
        Y = y if use_y else 1
        if kind == "plus":
            term = f"\\left({L(a * x + b * Y)}\\right)^{{2}}"
            ans = sp.expand((a * x + b * Y) ** 2)
            f = "(u+v)^2=u^2+2uv+v^2"
        elif kind == "minus":
            term = f"\\left({L(a * x - b * Y)}\\right)^{{2}}"
            ans = sp.expand((a * x - b * Y) ** 2)
            f = "(u-v)^2=u^2-2uv+v^2"
        else:
            term = f"\\left({L(a * x + b * Y)}\\right)\\left({L(a * x - b * Y)}\\right)"
            ans = sp.expand((a * x + b * Y) * (a * x - b * Y))
            f = "(u+v)(u-v)=u^2-v^2"
        u, v = L(a * x), L(b * Y)
        sol = f"Binomische Formel ${f}$ mit $u={u}$, $v={v}$:\n\n$${term}={L(ans)}$$"
        parts.append(part(f"${term}=$", {"type": "expr", "value": sp.sstr(ans), "var": "x,y" if use_y else "x"}, sol, [
            "Welche binomische Formel passt?",
            f"${f}$. Bestimme $u$ und $v$.",
            f"$u={u}$, $v={v}$. Vergiss beim Quadrieren den Faktor vor der Variablen nicht: $({u})^2$." if kind != "dritte" else f"$u={u}$, $v={v}$. Das Resultat hat nur zwei Summanden.",
        ], lab))
    return {"statement": "Multipliziere mit den binomischen Formeln aus (Produkte mit *, z.B. `12*x*y`):", "parts": parts}


@gen("gb-binom-rueckwaerts", "g1", ["g-binome", "g-terme"], "Binomische Formeln rückwärts (faktorisieren)", "ohne", 2, 5)
def _binom_rueck(rng):
    a, b, s = rng.randint(1, 6), rng.randint(1, 9), rng.choice([1, -1])
    sq = sp.expand((a * x + s * b) ** 2)
    pa = part(f"${L(sq)}=\\left(\\ldots\\right)^2$. Was steht in der Klammer? (Koeffizient von $x$ positiv)",
              {"type": "expr", "value": sp.sstr(a * x + s * b), "var": "x"},
              f"$u^2={L(a**2 * x**2)}\\Rightarrow u={L(a * x)}$, $v^2={b * b}\\Rightarrow v={b}$. "
              f"Mittelterm prüfen: $2uv={2 * a * b}x$ ✓, Vorzeichen {'plus' if s > 0 else 'minus'} → "
              f"{'1.' if s > 0 else '2.'} binomische Formel.\n\n$${L(sq)}=\\left({L(a * x + s * b)}\\right)^2$$", [
                  "Erkennst du eine binomische Formel? Schau auf den ersten und den letzten Summanden.",
                  "$u^2\\pm2uv+v^2=(u\\pm v)^2$. Erster Summand $=u^2$, letzter $=v^2$.",
                  f"$u={L(a * x)}$ und $v={b}$. Das Vorzeichen des Mittelterms entscheidet über $+$ oder $-$.",
              ], "a")
    c, d = rng.randint(1, 7), rng.randint(1, 9)
    diff = sp.expand(c**2 * x**2 - d**2)
    given_plus = rng.random() < 0.5
    given = c * x + d if given_plus else c * x - d
    other = c * x - d if given_plus else c * x + d
    pb = part(f"${L(diff)}=\\left({L(given)}\\right)\\cdot\\left(\\ldots\\right)$. Was steht in der zweiten Klammer?",
              {"type": "expr", "value": sp.sstr(other), "var": "x"},
              f"3. binomische Formel $u^2-v^2=(u+v)(u-v)$ mit $u={L(c * x)}$, $v={d}$:\n\n$${L(diff)}=\\left({L(c * x + d)}\\right)\\left({L(c * x - d)}\\right)$$", [
                  "Eine Differenz von zwei Quadraten – welche binomische Formel ist das?",
                  "$u^2-v^2=(u+v)(u-v)$.",
                  f"$u={L(c * x)}$, $v={d}$. Die zweite Klammer hat das andere Vorzeichen.",
              ], "b")
    return {"statement": "Faktorisiere mit den binomischen Formeln.", "parts": [pa, pb]}


@gen("gb-quad-ergaenzung", "g1", ["g-binome", "g-quad-gleichung"], "Quadratische Ergänzung", "ohne", 2, 5)
def _quad_erg(rng):
    bb = rng.choice([v for v in range(-12, 13, 2) if v != 0])
    c = rng.randint(-10, 12)
    d = R(bb, 2)
    k = c - d**2
    poly = x**2 + bb * x + c
    sol = (f"Halbe Zahl vor $x$: $d=\\frac{{{bb}}}{{2}}={L(d)}$. Ergänzen mit $d^2={L(d**2)}$ und gleich wieder abziehen:\n\n"
           f"$${L(poly)}=x^2{_sco(bb)}{_sg(d**2)}{_sg(-d**2)}{_sg(c)}=\\left({L(x + d)}\\right)^2{_sg(k)}$$\n\n"
           f"Also $d={L(d)}$, $k={L(k)}$. Scheitelpunkt $S({L(-d)}\\mid{L(k)})$.")
    return {
        "statement": f"Schreibe $${L(poly)}$$ in der Scheitelform $(x+d)^2+k$.",
        "parts": [
            part("$(d;\\ k)$", {"type": "tuple", "value": [sp.sstr(d), sp.sstr(k)], "names": ["d", "k"]}, sol, [
                "Ziel: die ersten zwei Summanden $x^2+bx$ zu einem Binom $(x+d)^2$ ergänzen.",
                "$(x+d)^2=x^2+2dx+d^2$. Also ist $d$ die Hälfte des Koeffizienten von $x$.",
                f"$d={L(d)}$. Addiere und subtrahiere $d^2={L(d**2)}$, dann bleibt $k=c-d^2$ übrig.",
            ], "a"),
            part("Scheitelpunkt der Parabel $y=" + L(poly) + "$: $S$", {"type": "tuple", "value": [sp.sstr(-d), sp.sstr(k)], "names": ["x_S", "y_S"]}, sol, [
                "Wo liegt der Scheitel der Parabel $y=(x+d)^2+k$?",
                "Der Scheitel ist dort, wo die Klammer null wird.",
                "$S(-d\\mid k)$ – Vorzeichen von $d$ umdrehen!",
            ], "b"),
        ],
    }


# ───────────── Prozent ─────────────

@gen("gb-prozent-grund", "g1", ["g-prozent"], "Prozentwert, Grundwert, Prozentsatz", "ohne", 1, 3)
def _prozent_grund(rng):
    p = _dec(rng.choice(["5", "10", "12.5", "15", "20", "25", "30", "40", "60", "75", "80", "120"]))
    G = 40 * rng.randint(1, 50)
    W = G * p / 100
    kind = rng.choice(["W", "G", "p"])
    if kind == "W":
        st = f"Wie viel sind ${_num(p)}\\,\\%$ von ${_num(G)}$ Fr.?"
        val, unit, prompt = W, "Fr.", "Prozentwert (in Fr.)"
        sol = f"$$W=G\\cdot\\frac{{p}}{{100}}={_num(G)}\\cdot\\frac{{{_num(p)}}}{{100}}={_num(W)}\\text{{ Fr.}}$$"
        h3 = f"Rechne ${_num(G)}\\cdot{_num(p / 100)}$."
    elif kind == "G":
        st = f"${_num(p)}\\,\\%$ eines Betrags sind ${_num(W)}$ Fr. Wie gross ist der ganze Betrag (100 %)?"
        val, unit, prompt = G, "Fr.", "Grundwert (in Fr.)"
        sol = f"$$G=\\frac{{W\\cdot100}}{{p}}=\\frac{{{_num(W)}\\cdot100}}{{{_num(p)}}}={_num(G)}\\text{{ Fr.}}$$\n\n(Dreisatz: ${_num(p)}\\,\\%\\ \\hat=\\ {_num(W)}$, $1\\,\\%\\ \\hat=\\ {_num(W / p)}$, $100\\,\\%\\ \\hat=\\ {_num(G)}$.)"
        h3 = f"Dreisatz: Wie viel Fr. entsprechen $1\\,\\%$? Teile dazu ${_num(W)}$ durch ${_num(p)}$."
    else:
        st = f"Wie viel Prozent sind ${_num(W)}$ Fr. von ${_num(G)}$ Fr.?"
        val, unit, prompt = p, "%", "Prozentsatz (in %)"
        sol = f"$$p=\\frac{{W}}{{G}}\\cdot100\\,\\%=\\frac{{{_num(W)}}}{{{_num(G)}}}\\cdot100\\,\\%={_num(p)}\\,\\%$$"
        h3 = f"Rechne $\\frac{{{_num(W)}}}{{{_num(G)}}}$ und multipliziere mit 100."
    return {
        "statement": st,
        "parts": [part(prompt, {"type": "number", "value": sp.sstr(val), "unit": unit}, sol, [
            "Was ist hier gegeben: Grundwert $G$ (100 %), Prozentwert $W$ oder Prozentsatz $p$? Was ist gesucht?",
            "Grundformel: $W=G\\cdot\\frac{p}{100}$ – nach der gesuchten Grösse umstellen (oder Dreisatz).",
            h3,
        ])],
    }


@gen("gb-prozent-aenderung", "g1", ["g-prozent"], "Prozentuale Änderungen nacheinander", "mit", 2, 5)
def _prozent_aend(rng):
    P0 = rng.choice([80, 120, 150, 200, 250, 400, 480, 600, 750, 1200])
    p, q = rng.choice([5, 8, 10, 12, 15, 20, 25, 30, 40]), rng.choice([5, 8, 10, 12, 15, 20, 25, 30, 40])
    f = (1 + R(p, 100)) * (1 - R(q, 100))
    P2 = P0 * f
    ch = (f - 1) * 100
    sol = (f"Wachstumsfaktoren multiplizieren: $+{p}\\,\\%\\ \\hat=\\ {_num(1 + R(p, 100))}$, $-{q}\\,\\%\\ \\hat=\\ {_num(1 - R(q, 100))}$.\n\n"
           f"$$P_2={P0}\\cdot{_num(1 + R(p, 100))}\\cdot{_num(1 - R(q, 100))}={_num(P2)}\\text{{ Fr.}}$$\n\n"
           f"Gesamtfaktor ${_num(f)}$ → Änderung $({_num(f)}-1)\\cdot100\\,\\%={_num(ch)}\\,\\%$.\n\n"
           f"Achtung: Es sind **nicht** ${p}-{q}={p - q}\\,\\%$, weil sich die zweite Änderung auf den neuen Preis bezieht.")
    return {
        "statement": f"Ein Artikel kostet ${P0}$ Fr. Der Preis wird zuerst um ${p}\\,\\%$ erhöht und danach um ${q}\\,\\%$ gesenkt.",
        "parts": [
            part("Neuer Preis (in Fr.)", {"type": "number", "value": sp.sstr(P2), "tol": 0.01, "unit": "Fr."}, sol, [
                "Eine Erhöhung um $p\\,\\%$ entspricht einer Multiplikation mit einem Faktor. Welchem?",
                f"$+{p}\\,\\%$: Faktor $1+\\frac{{{p}}}{{100}}$; $-{q}\\,\\%$: Faktor $1-\\frac{{{q}}}{{100}}$.",
                "Multipliziere den Anfangspreis mit beiden Faktoren nacheinander.",
            ], "a"),
            part("Gesamte prozentuale Änderung (in %, Abnahme negativ)", {"type": "number", "value": sp.sstr(ch), "tol": 0.01, "unit": "%"}, sol, [
                "Vergleiche den neuen Preis mit dem alten.",
                "Gesamtfaktor = Produkt der beiden Faktoren; Änderung in % $=(\\text{Faktor}-1)\\cdot100$.",
                "Einfach die Prozentzahlen zu addieren/subtrahieren ist falsch!",
            ], "b"),
        ],
    }


@gen("gb-zinseszins", "g1", ["g-prozent"], "Zinseszins", "mit", 2, 6)
def _zinseszins(rng):
    K0 = rng.choice([5000, 8000, 10000, 12000, 15000, 20000, 25000])
    p = _dec(rng.choice(["0.5", "0.75", "1", "1.25", "1.5", "2", "2.5", "3", "3.5"]))
    n = rng.randint(3, 15)
    qf = 1 + p / 100
    Kn = K0 * qf**n
    Z = K0 + rng.choice([500, 1000, 1500, 2000, 3000]) * (K0 // 5000)
    N = 0
    while K0 * qf**N < Z:
        N += 1
    tN = math.log(float(R(Z, K0))) / math.log(float(qf))
    sol_a = (f"Zinseszinsformel: $K_n=K_0\\cdot\\left(1+\\frac{{p}}{{100}}\\right)^n$.\n\n"
             f"$$K_{{{n}}}={K0}\\cdot{_num(qf)}^{{{n}}}\\approx{_chf(Kn)}\\text{{ Fr.}}$$")
    sol_b = (f"$${K0}\\cdot{_num(qf)}^n={Z}\\iff {_num(qf)}^n=\\frac{{{Z}}}{{{K0}}}\\iff n=\\frac{{\\ln\\left(\\frac{{{Z}}}{{{K0}}}\\right)}}{{\\ln({_num(qf)})}}\\approx{tN:.3f}$$\n\n"
             f"Da nur ganze Jahre zählen, wird aufgerundet: nach **{N} Jahren** ist der Betrag erstmals erreicht.")
    return {
        "statement": f"Ein Kapital von ${K0}$ Fr. wird zu einem Jahreszins von ${_num(p)}\\,\\%$ angelegt (Zinseszins, keine Abhebungen).",
        "parts": [
            part(f"Kapital nach ${n}$ Jahren (in Fr.)", {"type": "number", "value": str(float(Kn)), "tol": 0.05, "unit": "Fr."}, sol_a, [
                "Jedes Jahr wird das Kapital mit demselben Faktor multipliziert.",
                f"Wachstumsfaktor $q=1+\\frac{{{_num(p)}}}{{100}}={_num(qf)}$; nach $n$ Jahren: $K_0\\cdot q^n$.",
                f"Rechne ${K0}\\cdot{_num(qf)}^{{{n}}}$ und runde auf Rappen.",
            ], "a"),
            part(f"Nach wie vielen ganzen Jahren beträgt das Kapital erstmals mindestens ${Z}$ Fr.?",
                 {"type": "number", "value": str(N), "tol": 0, "unit": "Jahre"}, sol_b, [
                     "Der Exponent $n$ ist hier unbekannt – wie holt man eine Unbekannte aus dem Exponenten?",
                     f"Setze ${K0}\\cdot{_num(qf)}^n={Z}$, teile durch ${K0}$ und logarithmiere: $n=\\frac{{\\ln(\\ldots)}}{{\\ln({_num(qf)})}}$.",
                     "Das Resultat ist keine ganze Zahl: Runde **auf**, denn vorher ist der Betrag noch nicht erreicht.",
                 ], "b"),
        ],
    }


@gen("gb-prozent-rueckwaerts", "g1", ["g-prozent"], "Prozentrechnung rückwärts (MWST, Rabatt)", "mit", 2, 4)
def _prozent_rueck(rng):
    if rng.random() < 0.5:
        net = 10 * rng.randint(2, 120)
        B = net * _dec("1.081")
        st = f"Ein Velo kostet inklusive ${8.1}\\,\\%$ Mehrwertsteuer ${_chf(B)}$ Fr. Wie hoch ist der Preis ohne MWST?"
        sol = (f"Der Preis inkl. MWST entspricht $108.1\\,\\%$ des Nettopreises:\n\n"
               f"$$P_{{\\text{{netto}}}}=\\frac{{{_chf(B)}}}{{1.081}}={_chf(net)}\\text{{ Fr.}}$$\n\n"
               f"Typischer Fehler: $8.1\\,\\%$ vom Bruttopreis abziehen – das ergibt ${_chf(B * _dec('0.919'))}$ Fr. und ist falsch, "
               f"weil sich die $8.1\\,\\%$ auf den Nettopreis beziehen.")
        val = net
        h = ["Auf welchen Betrag bezieht sich die MWST – auf den Preis mit oder ohne MWST?",
             "Nettopreis $=100\\,\\%$, Bruttopreis $=108.1\\,\\%$ → Faktor $1.081$.",
             f"Teile ${_chf(B)}$ durch $1.081$ (nicht $8.1\\,\\%$ abziehen!)."]
    else:
        O = 20 * rng.randint(3, 60)
        r = rng.choice([10, 15, 20, 25, 30, 40])
        X = O * (1 - R(r, 100))
        st = f"Nach einem Rabatt von ${r}\\,\\%$ kostet eine Jacke noch ${_chf(X)}$ Fr. Wie viel kostete sie vorher?"
        sol = (f"Der neue Preis entspricht $100\\,\\%-{r}\\,\\%={100 - r}\\,\\%$ des alten Preises:\n\n"
               f"$$P_{{\\text{{alt}}}}=\\frac{{{_chf(X)}}}{{{_num(1 - R(r, 100))}}}={_chf(O)}\\text{{ Fr.}}$$\n\n"
               f"Typischer Fehler: ${r}\\,\\%$ zum neuen Preis addieren – die ${r}\\,\\%$ beziehen sich aber auf den alten Preis.")
        val = O
        h = ["Welcher Preis entspricht hier $100\\,\\%$?",
             f"Der alte Preis ist $100\\,\\%$; nach dem Rabatt bleiben ${100 - r}\\,\\%$, also Faktor ${_num(1 - R(r, 100))}$.",
             f"Teile ${_chf(X)}$ durch ${_num(1 - R(r, 100))}$."]
    return {"statement": st, "parts": [part("Preis (in Fr.)", {"type": "number", "value": str(val), "tol": 0.01, "unit": "Fr."}, sol, h)]}


# ═════════════════════════ G2: Gleichungen ═════════════════════════

@gen("gb-lin-einfach", "g2", ["g-lin-gleichung"], "Lineare Gleichung mit Klammern", "ohne", 1, 4)
def _lin_einfach(rng):
    while True:
        x0 = rng.randint(-8, 8)
        a, b, c, d = rng.randint(2, 5), _nz(rng, -6, 6), _nz(rng, -9, 9), rng.randint(-4, 6)
        if d != a:
            break
    e = a * (x0 - b) + c - d * x0
    lhs = f"{a}\\left({L(x - b)}\\right) {_sg(c)}"
    rhs = L(d * x + e)
    sol = (f"Klammer auflösen: ${L(a * x)} {_sg(-a * b)} {_sg(c)} = {rhs}$, also ${L(a * x - a * b + c)} = {rhs}$.\n\n"
           f"$x$-Terme nach links, Zahlen nach rechts: ${_co(a - d)} = {e - (c - a * b)}$\n\n"
           f"$$x=\\frac{{{e - (c - a * b)}}}{{{a - d}}}={x0}$$\n\nProbe: links ${a}({x0}{_sg(-b)}){_sg(c)}={a * (x0 - b) + c}$, rechts ${d * x0 + e}$ ✓")
    return {
        "statement": f"Löse die Gleichung: $${lhs}={rhs}$$",
        "parts": [part("$x=$", {"type": "number", "value": str(x0)}, sol, [
            "Löse zuerst die Klammer auf.",
            "Bringe alle Terme mit $x$ auf eine Seite und alle Zahlen auf die andere (auf beiden Seiten dasselbe rechnen!).",
            f"Nach dem Sortieren steht da ${_co(a - d)}=\\ldots$. Teile durch den Koeffizienten von $x$.",
        ])],
    }


@gen("gb-lin-brueche", "g2", ["g-lin-gleichung", "g-brueche"], "Lineare Gleichung mit Brüchen", "ohne", 2, 5)
def _lin_brueche(rng):
    while True:
        a, c = rng.sample([2, 3, 4, 5, 6], 2)
        b, s = _nz(rng, -6, 6), rng.choice([1, -1])
        x0 = rng.randint(-10, 12)
        coef = R(1, a) + s * R(1, c)
        if coef != 0:
            break
    d = R(x0, a) + s * R(x0 - b, c)
    H = sp.ilcm(a, c)
    lhs = f"\\frac{{x}}{{{a}}}{' + ' if s > 0 else ' - '}\\frac{{{L(x - b)}}}{{{c}}}"
    left_H = sp.expand(H * (x / a + s * (x - b) / c))
    sol = (f"Mit dem Hauptnenner ${H}$ multiplizieren (jeden Summanden!):\n\n"
           f"$${H // a}x{' + ' if s > 0 else ' - '}{H // c}\\left({L(x - b)}\\right)={L(H * d)}$$\n\n"
           f"Klammer auflösen und zusammenfassen: ${L(left_H)}={L(H * d)}$\n\n"
           f"$${_co(left_H.coeff(x))}={L(H * d - left_H.subs(x, 0))}\\Rightarrow x={x0}$$")
    return {
        "statement": f"Löse die Gleichung: $${lhs}={L(d)}$$",
        "parts": [part("$x=$", {"type": "number", "value": str(x0)}, sol, [
            "Brüche stören – wie wirst du sie auf einen Schlag los?",
            f"Multipliziere die ganze Gleichung mit dem Hauptnenner aller Nenner (hier ${H}$).",
            "Achtung: Der Zähler $x-\\ldots$ wirkt wie eine Klammer – das Minus vor dem Bruch gilt für den ganzen Zähler.",
        ])],
    }


@gen("gb-lin-klammern", "g2", ["g-lin-gleichung", "g-binome"], "Gleichung mit Binomen (wird linear)", "ohne", 2, 5)
def _lin_klammern(rng):
    if rng.random() < 0.5:
        while True:
            a, b = _nz(rng, -6, 6), _nz(rng, -6, 6)
            x0 = rng.randint(-6, 6)
            if a + b != 0:
                break
        cc = 2 * (a + b) * x0 + a * a - b * b
        lhs = f"\\left({L(x + a)}\\right)^{{2}}-\\left({L(x - b)}\\right)^{{2}}"
        rhs = str(cc)
        ex = sp.expand((x + a) ** 2 - (x - b) ** 2)
        sol = (f"Binomische Formeln: $({L(x + a)})^2={L(sp.expand((x + a) ** 2))}$, $({L(x - b)})^2={L(sp.expand((x - b) ** 2))}$.\n\n"
               f"Klammer um das zweite Quadrat beachten: $x^2$ fällt weg:\n\n$${L(ex)}={cc}\\Rightarrow {_co(2 * (a + b))}={cc - (a * a - b * b)}\\Rightarrow x={x0}$$")
    else:
        while True:
            a, b, c = _nz(rng, -6, 6), _nz(rng, -6, 6), _nz(rng, -6, 6)
            x0 = rng.randint(-6, 6)
            if x0 + c == 0:
                continue
            dd = R((x0 + a) * (x0 - b), x0 + c) - x0
            if dd.q == 1 and dd != 0 and abs(dd) <= 9 and (a - b) != (c + dd):
                break
        d = int(dd)
        lhs = f"\\left({L(x + a)}\\right)\\left({L(x - b)}\\right)"
        rhs = f"\\left({L(x + c)}\\right)\\left({L(x + d)}\\right)"
        sol = (f"Beide Seiten ausmultiplizieren:\n\n$${L(sp.expand((x + a) * (x - b)))}={L(sp.expand((x + c) * (x + d)))}$$\n\n"
               f"$x^2$ fällt auf beiden Seiten weg: ${_co(a - b - c - d)}={c * d + a * b}\\Rightarrow x={x0}$")
    return {
        "statement": f"Löse die Gleichung: $${lhs}={rhs}$$",
        "parts": [part("$x=$", {"type": "number", "value": str(x0)}, sol, [
            "Multipliziere zuerst alle Klammern aus (binomische Formeln).",
            "Achtung beim Minus vor einem Quadrat bzw. Produkt: zuerst ausrechnen, in Klammern setzen, dann Vorzeichen umdrehen.",
            "Die $x^2$-Terme heben sich auf – übrig bleibt eine lineare Gleichung.",
        ])],
    }


# ───────────── Quadratische Gleichungen ─────────────

def _mitternacht_sol(a, b, c):
    D = b * b - 4 * a * c
    return D, (f"Mitternachtsformel mit $a={a}$, $b={b}$, $c={c}$:\n\n"
               f"$$D=b^2-4ac=({b})^2-4\\cdot({a})\\cdot({c})={D}$$")


@gen("gb-quad-mitternacht", "g2", ["g-quad-gleichung"], "Quadratische Gleichung (Mitternachtsformel)", "ohne", 2, 6)
def _quad_mn(rng):
    while True:
        q1 = rng.choice([1, 1, 2, 3])
        p1 = rng.randint(-7, 7)
        r1 = R(p1, q1)
        r2 = rng.randint(-6, 6)
        m = rng.choice([1, 1, -1, 2]) if q1 == 1 else rng.choice([1, -1])
        if r1 != r2:
            break
    poly = sp.expand(m * q1 * (x - r1) * (x - r2))
    P = sp.Poly(poly, x)
    a, b, c = [int(v) for v in P.all_coeffs()]
    D, s1 = _mitternacht_sol(a, b, c)
    sq = sp.sqrt(D)
    roots = sorted([r1, sp.Integer(r2)])
    sol = (s1 + f"\n\n$$x_{{1,2}}=\\frac{{-b\\pm\\sqrt D}}{{2a}}=\\frac{{{-b}\\pm{L(sq)}}}{{{2 * a}}}$$\n\n"
           f"$x_1={L(roots[0])}$, $x_2={L(roots[1])}$.")
    return {
        "statement": f"Löse ohne Rechner: $${L(poly)}=0$$",
        "parts": [
            part("Diskriminante $D=b^2-4ac$", {"type": "number", "value": str(D)}, s1, [
                "Lies zuerst die Koeffizienten $a$, $b$, $c$ ab (mit Vorzeichen!).",
                "$D=b^2-4ac$. Setze negative Zahlen in Klammern.",
                f"$a={a}$, $b={b}$, $c={c}$.",
            ], "a"),
            part("Lösungsmenge (getrennt mit ;)", {"type": "set", "value": [sp.sstr(r) for r in roots]}, sol, [
                "Wie viele Lösungen gibt es bei $D>0$?",
                "$x_{1,2}=\\frac{-b\\pm\\sqrt{D}}{2a}$.",
                f"$\\sqrt{{D}}={L(sq)}$. Rechne einmal mit $+$ und einmal mit $-$ und kürze.",
            ], "b"),
        ],
    }


@gen("gb-quad-anzahl", "g2", ["g-quad-gleichung"], "Anzahl Lösungen (Diskriminante)", "ohne", 2, 5)
def _quad_anzahl(rng):
    case = rng.choice([0, 1, 2])
    while True:
        if case == 1:
            r0 = R(rng.randint(-6, 6), rng.choice([1, 1, 2]))
            m = rng.choice([1, -1, 2]) if r0.q == 1 else rng.choice([4, -4])
            poly = sp.expand(m * (x - r0) ** 2)
            if any(cf.q != 1 for cf in sp.Poly(poly, x).all_coeffs()):
                continue
        else:
            a, b, c = rng.choice([1, 1, 2, 3, -1, -2]), rng.randint(-7, 7), rng.randint(-9, 9)
            poly = a * x**2 + b * x + c
        a, b, c = [int(v) for v in sp.Poly(poly, x).all_coeffs()]
        D = b * b - 4 * a * c
        if (case == 0 and D < 0) or (case == 1 and D == 0) or (case == 2 and D > 0 and c != 0 and b != 0):
            break
    _, s1 = _mitternacht_sol(a, b, c)
    opts = ["keine reelle Lösung", "genau eine Lösung", "zwei Lösungen"]
    concl = {0: "$D<0$ → **keine reelle Lösung** (die Parabel schneidet die $x$-Achse nicht).",
             1: "$D=0$ → **genau eine Lösung** (doppelte Lösung, die Parabel berührt die $x$-Achse).",
             2: "$D>0$ → **zwei Lösungen**."}[case]
    parts = [part("Wie viele reelle Lösungen hat die Gleichung?", {"type": "choice", "value": case, "options": opts}, s1 + "\n\n" + concl, [
        "Welche Grösse aus der Mitternachtsformel entscheidet über die Anzahl Lösungen?",
        "Die Diskriminante $D=b^2-4ac$: $D>0$ zwei, $D=0$ eine, $D<0$ keine Lösung.",
        f"Berechne $D$ mit $a={a}$, $b={b}$, $c={c}$.",
    ], "a")]
    if case > 0:
        rD = sp.sqrt(D)
        roots = sorted({R(-b, 2 * a) + sg * rD / (2 * a) for sg in (1, -1)}, key=lambda v: float(v))
        rat, irr = R(-b, 2 * a), rD / (2 * a)
        # Wurzelterm zuerst, damit die Eingabe nicht mit ")" endet
        vals = [sp.sstr(roots[0])] if D == 0 else [f"{sp.sstr(sg * irr)} {'+' if rat > 0 else '-'} {sp.sstr(abs(rat))}" for sg in (1, -1)]
        if D > 0 and rD.is_Rational:
            vals = [sp.sstr(r) for r in roots]
        sol = s1 + f"\n\n$$x_{{1,2}}=\\frac{{{-b}\\pm\\sqrt{{{D}}}}}{{{2 * a}}}$$\n\n" + ", ".join(f"$x_{i + 1}={L(r)}$" for i, r in enumerate(roots))
        parts.append(part("Lösung(en) (getrennt mit ;, Wurzeln z.B. als `sqrt(5)`)", {"type": "set", "value": vals}, sol, [
            "Verwende die Mitternachtsformel.",
            "$x_{1,2}=\\frac{-b\\pm\\sqrt{D}}{2a}$.",
            f"$D={D}$ hast du schon. " + ("Bei $D=0$ fällt $\\pm$ weg: $x=-\\frac{b}{2a}$." if D == 0 else "Gib die Lösungen exakt an, z.B. `sqrt(17)/4 - 3/4`."),
        ], "b"))
    return {"statement": f"Gegeben ist die Gleichung $${L(poly)}=0$$", "parts": parts}


@gen("gb-quad-spezial", "g2", ["g-quad-gleichung"], "Quadratische Gleichungen ohne Mitternachtsformel", "ohne", 1, 4)
def _quad_spezial(rng):
    kind = rng.choice(["A", "B", "C"])
    if kind == "A":
        a, b = rng.choice([1, 2, 3, 4, -1, -2]), _nz(rng, -12, 12)
        lhs, rhs = L(a * x**2 + b * x), "0"
        r = R(-b, a)
        roots = sorted([sp.Integer(0), r])
        sol = f"$x$ ausklammern: $x\\left({L(a * x + b)}\\right)=0$. Satz vom Nullprodukt: $x_1=0$ oder ${L(a * x + b)}=0\\Rightarrow x_2={L(r)}$."
        hints = ["Es gibt kein konstantes Glied. Was kannst du ausklammern?", "Klammere $x$ aus und verwende den Satz vom Nullprodukt.",
                 f"$x\\left({L(a * x + b)}\\right)=0$: Ein Faktor muss null sein. Nicht durch $x$ teilen – sonst geht die Lösung $x=0$ verloren!"]
    elif kind == "B":
        a, r0 = rng.choice([1, 2, 3, 4, 5]), rng.randint(1, 9)
        c = a * r0 * r0
        lhs, rhs = L(a * x**2 - c), "0"
        roots = [sp.Integer(-r0), sp.Integer(r0)]
        sol = f"$${L(a * x**2)}={c}\\Rightarrow x^2={r0 * r0}\\Rightarrow x=\\pm{r0}$$"
        hints = ["Es gibt keinen Term mit $x$ (nur $x^2$). Wie isolierst du $x^2$?", "Bringe die Zahl nach rechts und teile durch den Koeffizienten.",
                 "Beim Wurzelziehen gibt es zwei Lösungen: $\\pm$!"]
    else:
        p, qq = rng.randint(-6, 6), rng.randint(1, 7)
        lhs, rhs = f"\\left({L(x - p)}\\right)^{{2}}", str(qq * qq)
        roots = sorted([sp.Integer(p - qq), sp.Integer(p + qq)])
        sol = f"Wurzel ziehen (beide Vorzeichen!): ${L(x - p)}=\\pm{qq}$ → $x={p}\\pm{qq}$, also $x_1={roots[0]}$, $x_2={roots[1]}$."
        hints = ["Nicht ausmultiplizieren – es geht schneller!", "Ziehe auf beiden Seiten die Wurzel. Denke an $\\pm$.",
                 f"${L(x - p)}={qq}$ oder ${L(x - p)}=-{qq}$."]
    return {
        "statement": f"Löse ohne Mitternachtsformel: $${lhs}={rhs}$$",
        "parts": [part("Lösungsmenge (getrennt mit ;)", {"type": "set", "value": [sp.sstr(v) for v in roots]}, sol, hints)],
    }


@gen("gb-quad-biquadratisch", "g2", ["g-quad-gleichung"], "Biquadratische Gleichung (Substitution)", "ohne", 2, 6)
def _quad_biquad(rng):
    s = rng.randint(1, 4)
    u = s * s
    if rng.random() < 0.6:
        t = rng.choice([v for v in range(1, 5) if v != s])
        v = t * t
    else:
        v = -rng.randint(1, 9)
    poly = sp.expand((x**2 - u) * (x**2 - v))
    sols = sorted({sp.Integer(s), sp.Integer(-s)} | ({sp.Integer(int(math.isqrt(v))), -sp.Integer(int(math.isqrt(v)))} if v > 0 else set()))
    zpoly = sp.expand((z - u) * (z - v))
    sol = (f"Substitution $z=x^2$: $${L(zpoly)}=0$$\n\n"
           f"Lösen (Vieta oder Mitternachtsformel): $z_1={u}$, $z_2={v}$.\n\n"
           f"Rücksubstitution $x^2=z$: $x^2={u}\\Rightarrow x=\\pm{s}$; " +
           (f"$x^2={v}\\Rightarrow x=\\pm{int(math.isqrt(v))}$." if v > 0 else f"$x^2={v}<0$ → keine reelle Lösung.") +
           f"\n\nLösungsmenge: $\\{{{'; '.join(map(str, sols))}\\}}$")
    return {
        "statement": f"Löse die Gleichung: $${L(poly)}=0$$",
        "parts": [
            part("Wie viele reelle Lösungen gibt es?", {"type": "number", "value": str(len(sols))}, sol, [
                "Es kommen nur $x^4$ und $x^2$ vor. Welche Substitution macht daraus eine quadratische Gleichung?",
                "Setze $z=x^2$ und löse die quadratische Gleichung in $z$.",
                "Jedes positive $z$ liefert zwei Lösungen $x=\\pm\\sqrt z$, ein negatives $z$ keine.",
            ], "a"),
            part("Lösungsmenge (getrennt mit ;)", {"type": "set", "value": [str(v_) for v_ in sols]}, sol, [
                "Löse zuerst nach $z=x^2$.",
                f"Die quadratische Gleichung in $z$ lautet ${L(zpoly)}=0$.",
                "Rücksubstitution: $x=\\pm\\sqrt{z}$ für jedes $z\\geq0$.",
            ], "b"),
        ],
    }


# ───────────── Lineare Gleichungssysteme ─────────────

@gen("gb-lgs-2x2", "g2", ["g-lgs"], "Lineares Gleichungssystem 2×2", "ohne", 1, 6)
def _lgs2(rng):
    while True:
        x0, y0 = rng.randint(-6, 6), rng.randint(-6, 6)
        a1, b1, a2, b2 = _nz(rng, -5, 5), _nz(rng, -5, 5), _nz(rng, -5, 5), _nz(rng, -5, 5)
        det = a1 * b2 - a2 * b1
        if det != 0:
            break
    c1, c2 = a1 * x0 + b1 * y0, a2 * x0 + b2 * y0
    e1, e2 = f"{_lin([a1, b1], ['x', 'y'])}={c1}", f"{_lin([a2, b2], ['x', 'y'])}={c2}"
    # Additionsverfahren: I·a2 − II·a1 eliminiert x
    yc, rc = b1 * a2 - b2 * a1, c1 * a2 - c2 * a1
    sol = (f"**Additionsverfahren:** $\\text{{I}}\\cdot({a2})-\\text{{II}}\\cdot({a1})$ eliminiert $x$:\n\n"
           f"$$({b1 * a2}-({b2 * a1}))\\,y={c1 * a2}-({c2 * a1})\\ \\Rightarrow\\ {yc}\\,y={rc}\\ \\Rightarrow\\ y={y0}$$\n\n"
           f"In I einsetzen: ${_co(a1)}{_sg(b1 * y0)}={c1}\\Rightarrow {_co(a1)}={c1 - b1 * y0}\\Rightarrow x={x0}$.\n\n"
           f"Probe in II: ${a2}\\cdot({x0})+{b2}\\cdot({y0})={c2}$ ✓\n\n$$(x;\\ y)=({x0};\\ {y0})$$")
    return {
        "statement": f"Löse das Gleichungssystem:\n\nI: ${e1}$\n\nII: ${e2}$",
        "parts": [part("$(x;\\ y)$", {"type": "tuple", "value": [str(x0), str(y0)], "names": ["x", "y"]}, sol, [
            "Ziel: eine Variable eliminieren, damit eine Gleichung mit nur einer Unbekannten übrig bleibt.",
            "Additionsverfahren: Multipliziere die Gleichungen so, dass vor $x$ (oder $y$) entgegengesetzt gleiche Zahlen stehen, und addiere. (Oder: eine Gleichung nach einer Variablen auflösen und einsetzen.)",
            f"Z.B. $\\text{{I}}\\cdot({a2})-\\text{{II}}\\cdot({a1})$ – dann fällt $x$ weg. Danach $y$ in eine Gleichung einsetzen.",
        ])],
    }


@gen("gb-lgs-3x3", "g2", ["g-lgs"], "Lineares Gleichungssystem 3×3", "ohne", 2, 12)
def _lgs3(rng):
    while True:
        s = [rng.randint(-4, 4) for _ in range(3)]
        A = [[rng.choice([1, -1])] + [rng.randint(-3, 3) for _ in range(2)]]
        A += [[rng.randint(-3, 3) for _ in range(3)] for _ in range(2)]
        M = sp.Matrix(A)
        if M.det() == 0 or any(all(v == 0 for v in row) for row in A):
            continue
        # nach Elimination von x: 2x2 in y,z
        k2, k3 = A[1][0] * A[0][0], A[2][0] * A[0][0]
        r2 = [A[1][j] - k2 * A[0][j] for j in range(3)]
        r3 = [A[2][j] - k3 * A[0][j] for j in range(3)]
        if all(abs(v) <= 12 for v in r2 + r3):
            break
    b = [sum(A[i][j] * s[j] for j in range(3)) for i in range(3)]
    rb2, rb3 = b[1] - k2 * b[0], b[2] - k3 * b[0]
    names = ["x", "y", "z"]
    eqs = [f"{_lin(A[i], names)}={b[i]}" for i in range(3)]
    def _elim(nm, k, r, rb):
        if k == 0:
            op, note = f"\\text{{{nm}}}", " (enthält kein $x$, bleibt gleich)"
        else:
            kk = "" if abs(k) == 1 else f"{abs(k)}\\cdot"
            op, note = f"\\text{{{nm}}}{'-' if k > 0 else '+'}{kk}\\text{{I}}", ""
        return f"$\\text{{{nm}}}'={op}:\\quad {_lin(r[1:], ['y', 'z'])}={rb}${note}"
    sol = (f"1. $x$ mit Gleichung I eliminieren:\n\n{_elim('II', k2, r2, rb2)}\n\n{_elim('III', k3, r3, rb3)}\n\n"
           f"2. Das 2×2-System II′, III′ lösen: $y={s[1]}$, $z={s[2]}$.\n\n"
           f"3. In I einsetzen: ${_lin(A[0], names)}={b[0]}\\Rightarrow x={s[0]}$.\n\n"
           f"Probe in II und III ✓\n\n$$(x;\\ y;\\ z)=({s[0]};\\ {s[1]};\\ {s[2]})$$")
    return {
        "statement": f"Löse das Gleichungssystem:\n\nI: ${eqs[0]}$\n\nII: ${eqs[1]}$\n\nIII: ${eqs[2]}$",
        "parts": [part("$(x;\\ y;\\ z)$", {"type": "tuple", "value": [str(v) for v in s], "names": ["x", "y", "z"]}, sol, [
            "Reduziere das System schrittweise: zuerst eine Variable aus zwei Gleichungen eliminieren.",
            "Gleichung I hat vor $x$ den Koeffizienten $\\pm1$ – nutze sie, um $x$ aus II und III zu eliminieren. Es bleibt ein 2×2-System in $y$ und $z$.",
            "Ziehe von II und III passende Vielfache von I ab, sodass $x$ wegfällt. Löse das entstehende 2×2-System in $y,z$ und setze zurück in I ein.",
        ])],
    }


@gen("gb-lgs-text", "g2", ["g-lgs"], "Textaufgabe mit Gleichungssystem", "ohne", 2, 6)
def _lgs_text(rng):
    kind = rng.choice(["kino", "muenzen", "zahlen"])
    if kind == "kino":
        pe, pk = rng.choice([14, 15, 16, 18, 20]), rng.choice([6, 7, 8, 9, 10])
        E, K = rng.randint(20, 120), rng.randint(10, 90)
        n, T = E + K, pe * E + pk * K
        st = (f"Für eine Kinovorstellung wurden ${n}$ Tickets verkauft. Ein Ticket für Erwachsene kostet ${pe}$ Fr., "
              f"eines für Kinder ${pk}$ Fr. Die Einnahmen betragen ${T}$ Fr. Wie viele Erwachsenen- und wie viele Kindertickets wurden verkauft?")
        val, names, prompt = [E, K], ["Erwachsene", "Kinder"], "(Erwachsene; Kinder)"
        sol = (f"Unbekannte: $e$ = Anzahl Erwachsene, $k$ = Anzahl Kinder.\n\n"
               f"I: $e+k={n}$, II: ${pe}e+{pk}k={T}$.\n\n"
               f"Aus I: $k={n}-e$. In II: ${pe}e+{pk}({n}-e)={T}\\Rightarrow {pe - pk}e={T - pk * n}\\Rightarrow e={E}$, $k={K}$.")
        h3 = f"I: $e+k={n}$ (Anzahl), II: ${pe}e+{pk}k={T}$ (Geld). Löse I nach $k$ auf und setze in II ein."
    elif kind == "muenzen":
        A, B = rng.randint(3, 30), rng.randint(3, 30)
        n, T = A + B, 2 * A + 5 * B
        st = f"In einem Kässeli liegen ${n}$ Münzen, nur 2-Franken- und 5-Franken-Stücke, zusammen ${T}$ Fr. Wie viele Münzen von jeder Sorte sind es?"
        val, names, prompt = [A, B], ["2-Fr.-Stücke", "5-Fr.-Stücke"], "(Anzahl 2-Fr.-Stücke; Anzahl 5-Fr.-Stücke)"
        sol = (f"Unbekannte: $a$ = Anzahl 2-Fr.-Stücke, $b$ = Anzahl 5-Fr.-Stücke.\n\n"
               f"I: $a+b={n}$, II: $2a+5b={T}$.\n\n"
               f"$\\text{{II}}-2\\cdot\\text{{I}}$: $3b={T - 2 * n}\\Rightarrow b={B}$, $a={n}-{B}={A}$.")
        h3 = f"I: $a+b={n}$, II: $2a+5b={T}$. Rechne $\\text{{II}}-2\\cdot\\text{{I}}$."
    else:
        u, v = rng.randint(5, 60), rng.randint(-20, 40)
        if u < v:
            u, v = v, u
        if u == v:
            u += 3
        S, D = u + v, u - v
        st = f"Die Summe zweier Zahlen ist ${S}$, ihre Differenz (grössere minus kleinere) ist ${D}$. Bestimme die beiden Zahlen."
        val, names, prompt = [u, v], ["grössere Zahl", "kleinere Zahl"], "(grössere Zahl; kleinere Zahl)"
        sol = (f"I: $a+b={S}$, II: $a-b={D}$.\n\nAddieren: $2a={S + D}\\Rightarrow a={u}$. Einsetzen: $b={S}-{u}={v}$.")
        h3 = f"I: $a+b={S}$, II: $a-b={D}$. Addiere die beiden Gleichungen."
    return {
        "statement": st,
        "parts": [part(prompt, {"type": "tuple", "value": [str(v_) for v_ in val], "names": names}, sol, [
            "Wähle für jede gesuchte Grösse eine Variable.",
            "Übersetze jeden Satz mit einer Angabe in eine Gleichung – du brauchst zwei Gleichungen.",
            h3,
        ])],
    }


# ───────────── Formeln umstellen ─────────────

_FORMELN_EINFACH = [
    ("v=\\frac{s}{t}", "t", "s/v", "v,s,t", "Mit $t$ multiplizieren: $v\\cdot t=s$. Durch $v$ dividieren: $t=\\frac{s}{v}$."),
    ("v=\\frac{s}{t}", "s", "v*t", "v,s,t", "Mit $t$ multiplizieren: $s=v\\cdot t$."),
    ("F=m\\cdot a", "a", "F/m", "F,m,a", "Durch $m$ dividieren: $a=\\frac{F}{m}$."),
    ("A=\\frac{(a+c)\\cdot h}{2}", "h", "2*A/(a+c)", "A,a,c,h", "Mal 2: $2A=(a+c)\\,h$. Durch $(a+c)$ dividieren: $h=\\frac{2A}{a+c}$."),
    ("A=\\frac{(a+c)\\cdot h}{2}", "c", "2*A/h - a", "A,a,c,h", "Mal 2: $2A=(a+c)\\,h$. Durch $h$: $\\frac{2A}{h}=a+c$. Minus $a$: $c=\\frac{2A}{h}-a$."),
    ("y=m\\cdot x+q", "x", "(y-q)/m", "y,m,x,q", "Minus $q$: $y-q=m\\,x$. Durch $m$: $x=\\frac{y-q}{m}$."),
    ("y=m\\cdot x+q", "m", "(y-q)/x", "y,m,x,q", "Minus $q$: $y-q=m\\,x$. Durch $x$: $m=\\frac{y-q}{x}$."),
    ("Z=\\frac{K\\cdot p\\cdot t}{100}", "p", "100*Z/(K*t)", "Z,K,p,t", "Mal 100: $100Z=K\\,p\\,t$. Durch $K\\,t$: $p=\\frac{100Z}{K\\,t}$."),
    ("Z=\\frac{K\\cdot p\\cdot t}{100}", "K", "100*Z/(p*t)", "Z,K,p,t", "Mal 100: $100Z=K\\,p\\,t$. Durch $p\\,t$: $K=\\frac{100Z}{p\\,t}$."),
    ("U=2\\cdot(a+b)", "b", "U/2 - a", "U,a,b", "Durch 2: $\\frac{U}{2}=a+b$. Minus $a$: $b=\\frac{U}{2}-a$."),
    ("p=\\frac{F}{A}", "A", "F/p", "p,F,A", "Mit $A$ multiplizieren: $p\\,A=F$. Durch $p$: $A=\\frac{F}{p}$."),
]

_FORMELN_SCHWER = [
    ("\\frac{1}{f}=\\frac{1}{g}+\\frac{1}{b}", "f", "g*b/(g+b)", "f,g,b",
     "Rechte Seite gleichnamig: $\\frac1f=\\frac{b+g}{g\\,b}$. Kehrwert auf beiden Seiten: $f=\\frac{g\\,b}{g+b}$."),
    ("\\frac{1}{f}=\\frac{1}{g}+\\frac{1}{b}", "b", "f*g/(g-f)", "f,g,b",
     "$\\frac1b=\\frac1f-\\frac1g=\\frac{g-f}{f\\,g}$. Kehrwert: $b=\\frac{f\\,g}{g-f}$."),
    ("P=\\frac{U^2}{R}", "U", "sqrt(P*R)", "P,U,R", "Mal $R$: $U^2=P\\,R$. Wurzel ziehen ($U>0$): $U=\\sqrt{P\\,R}$."),
    ("P=\\frac{U^2}{R}", "R", "U**2/P", "P,U,R", "Mal $R$: $P\\,R=U^2$. Durch $P$: $R=\\frac{U^2}{P}$."),
    ("W=\\frac{m\\cdot v^2}{2}", "v", "sqrt(2*W/m)", "W,m,v", "Mal 2, durch $m$: $v^2=\\frac{2W}{m}$. Wurzel ($v>0$): $v=\\sqrt{\\frac{2W}{m}}$."),
    ("T=2\\pi\\sqrt{\\frac{l}{g}}", "l", "g*T**2/(4*pi**2)", "T,l,g",
     "Durch $2\\pi$: $\\frac{T}{2\\pi}=\\sqrt{\\frac lg}$. Quadrieren: $\\frac{T^2}{4\\pi^2}=\\frac lg$. Mal $g$: $l=\\frac{g\\,T^2}{4\\pi^2}$."),
    ("V=\\pi\\cdot r^2\\cdot h", "r", "sqrt(V/(pi*h))", "V,r,h", "Durch $\\pi h$: $r^2=\\frac{V}{\\pi h}$. Wurzel ($r>0$): $r=\\sqrt{\\frac{V}{\\pi h}}$."),
    ("s=\\frac{a}{2}\\cdot t^2", "t", "sqrt(2*s/a)", "s,a,t", "Mal $\\frac2a$: $t^2=\\frac{2s}{a}$. Wurzel ($t>0$): $t=\\sqrt{\\frac{2s}{a}}$."),
    ("v=\\sqrt{2\\cdot g\\cdot h}", "h", "v**2/(2*g)", "v,g,h", "Quadrieren: $v^2=2gh$. Durch $2g$: $h=\\frac{v^2}{2g}$."),
    ("y=\\frac{a\\cdot x+b}{x+c}", "x", "(b-c*y)/(y-a)", "y,a,b,c,x",
     "Mal $(x+c)$: $y\\,x+c\\,y=a\\,x+b$. $x$-Terme links: $y\\,x-a\\,x=b-c\\,y$. Ausklammern: $x\\,(y-a)=b-c\\,y$. Durch $(y-a)$: $x=\\frac{b-c\\,y}{y-a}$."),
]


def _formel(rng, cat, hard):
    tex, tgt, ans, var, steps = rng.choice(cat)
    hints = [f"Ziel: ${tgt}$ allein auf eine Seite bringen. Rechne auf beiden Seiten immer dasselbe.",
             "Mache die Operationen rückwärts rückgängig: zuerst Brüche wegschaffen (multiplizieren), dann Summanden verschieben, dann dividieren." if not hard else
             "Reihenfolge: Brüche wegschaffen bzw. gleichnamig machen, Quadrate durch Wurzelziehen (und Wurzeln durch Quadrieren) auflösen, zuletzt dividieren.",
             "Kontrolle: Setze dein Resultat in die Formel ein – es muss eine wahre Aussage ergeben."]
    return {
        "statement": f"Stelle die Formel $${tex}$$ nach ${tgt}$ um (alle Grössen positiv).",
        "parts": [part(f"${tgt}=$ (Produkte mit *, z.B. `2*A/h`)", {"type": "expr", "value": ans, "var": var},
                       steps, hints)],
    }


@gen("gb-formel-einfach", "g2", ["g-formeln-umstellen"], "Formel umstellen (einfach)", "ohne", 1, 3)
def _formel_einfach(rng):
    return _formel(rng, _FORMELN_EINFACH, False)


@gen("gb-formel-schwer", "g2", ["g-formeln-umstellen"], "Formel umstellen (Wurzeln, Kehrwerte)", "ohne", 2, 5)
def _formel_schwer(rng):
    return _formel(rng, _FORMELN_SCHWER, True)


# ───────────── Logarithmen ─────────────

def _log_item(rng, kind):
    if kind == "int":
        b = rng.choice([2, 3, 5, 10])
        k = rng.randint(1, {2: 7, 3: 4, 5: 3, 10: 5}[b])
        arg = sp.Integer(b) ** k
        tex = f"\\lg\\left({arg}\\right)" if b == 10 else f"\\log_{{{b}}}\\left({arg}\\right)"
        val = sp.Integer(k)
    elif kind == "neg":
        b = rng.choice([2, 3, 10])
        k = rng.randint(1, {2: 5, 3: 3, 10: 3}[b])
        arg = R(1, b**k)
        argtex = L(arg) if b != 10 else _num(arg)
        tex = f"\\lg\\left({argtex}\\right)" if b == 10 else f"\\log_{{{b}}}\\left({argtex}\\right)"
        val = sp.Integer(-k)
    elif kind == "wurzel":
        b = rng.choice([2, 3, 5, 7])
        n = rng.choice([2, 3])
        tex = f"\\log_{{{b}}}\\left({'\\sqrt' if n == 2 else '\\sqrt[3]'}{{{b}}}\\right)"
        val = R(1, n)
    else:  # ln
        k = rng.choice([2, 3, 4, -1, -2, R(1, 2)])
        tex = f"\\ln\\left(e^{{{L(k)}}}\\right)" if k != R(1, 2) else "\\ln\\left(\\sqrt{e}\\right)"
        val = sp.sympify(k)
    return tex, val


@gen("gb-log-berechnen", "g2", ["g-logarithmen"], "Logarithmen berechnen", "ohne", 1, 4)
def _log_ber(rng):
    kinds = rng.sample(["int", "neg", "wurzel", "ln"], 3)
    parts = []
    for lab, k in zip("abc", kinds):
        tex, val = _log_item(rng, k)
        sol = (f"$\\log_b(a)$ ist der Exponent, mit dem man $b$ potenzieren muss, um $a$ zu erhalten. "
               f"Hier: ${tex}={L(val)}$, weil die Basis hoch ${L(val)}$ genau das Argument ergibt.")
        parts.append(part(f"${tex}=$", {"type": "number", "value": sp.sstr(val)}, sol, [
            "Frage dich: Basis hoch **wie viel** ergibt das Argument?",
            "Schreibe das Argument als Potenz der Basis. $\\lg=\\log_{10}$, $\\ln=\\log_e$. Brüche → negative Exponenten, Wurzeln → gebrochene Exponenten.",
            "Dann gilt $\\log_b\\left(b^k\\right)=k$.",
        ], lab))
    return {"statement": "Berechne ohne Rechner:", "parts": parts}


@gen("gb-log-gesetze", "g2", ["g-logarithmen"], "Logarithmengesetze anwenden", "ohne", 2, 5)
def _log_gesetze(rng):
    kind = rng.choice(["A", "B", "C"])
    if kind == "A":
        k = rng.randint(2, 4)
        divs = [d for d in range(2, 10**k) if (10**k) % d == 0 and d not in (10, 100, 1000) and (10**k // d) not in (10, 100, 1000)]
        A = rng.choice(divs)
        B = 10**k // A
        tex = f"\\lg\\left({A}\\right)+\\lg\\left({B}\\right)"
        val = k
        sol = f"Summe von Logarithmen = Logarithmus des Produkts: $${tex}=\\lg\\left({A}\\cdot{B}\\right)=\\lg\\left({10**k}\\right)={k}$$"
        h3 = f"Rechne ${A}\\cdot{B}$."
    elif kind == "B":
        b = rng.choice([2, 3])
        Bv = rng.choice([v for v in [3, 5, 6, 7, 10, 12] if v % b != 0] or [5])
        k = rng.randint(2, 4 if b == 2 else 3)
        A = Bv * b**k
        tex = f"\\log_{{{b}}}\\left({A}\\right)-\\log_{{{b}}}\\left({Bv}\\right)"
        val = k
        sol = f"Differenz von Logarithmen = Logarithmus des Quotienten: $${tex}=\\log_{{{b}}}\\left(\\frac{{{A}}}{{{Bv}}}\\right)=\\log_{{{b}}}\\left({b**k}\\right)={k}$$"
        h3 = f"Rechne $\\frac{{{A}}}{{{Bv}}}$ und schreibe das Resultat als Potenz von ${b}$."
    else:
        b, p, q = rng.choice([(6, 2, 3), (10, 2, 5), (6, 3, 2), (10, 5, 2), (12, 3, 4)])
        j = rng.choice([1, 1, 2]) if b == 6 else 1
        A, Bv = p**j, q**(2 * j)
        tex = f"2\\log_{{{b}}}\\left({A}\\right)+\\log_{{{b}}}\\left({Bv}\\right)"
        val = 2 * j
        sol = (f"Faktor vor dem Logarithmus als Exponent: $2\\log_{{{b}}}({A})=\\log_{{{b}}}({A}^2)=\\log_{{{b}}}({A * A})$.\n\n"
               f"$$\\log_{{{b}}}\\left({A * A}\\cdot{Bv}\\right)=\\log_{{{b}}}\\left({A * A * Bv}\\right)=\\log_{{{b}}}\\left({b}^{{{2 * j}}}\\right)={2 * j}$$")
        h3 = f"$2\\log_{{{b}}}({A})=\\log_{{{b}}}({A * A})$. Fasse danach die Summe zu einem einzigen Logarithmus zusammen."
    return {
        "statement": f"Berechne ohne Rechner mit den Logarithmengesetzen: $${tex}$$",
        "parts": [part("Resultat", {"type": "number", "value": str(val)}, sol, [
            "Einzeln lassen sich die Logarithmen nicht ohne Rechner bestimmen – fasse sie zuerst zusammen.",
            "$\\log(u)+\\log(v)=\\log(u\\cdot v)$, $\\log(u)-\\log(v)=\\log\\left(\\frac uv\\right)$, $k\\cdot\\log(u)=\\log(u^k)$.",
            h3,
        ])],
    }


@gen("gb-log-zerlegen", "g2", ["g-logarithmen"], "Logarithmus eines Terms zerlegen", "ohne", 2, 4)
def _log_zerlegen(rng):
    ax = rng.randint(1, 4)
    n = rng.choice([2, 3])
    my = rng.choice([1, 1, 2])
    cz = rng.randint(1, 3)
    rad = "\\sqrt" if n == 2 else f"\\sqrt[{n}]"
    ytex = _pw("y", my)
    tex = f"\\ln\\left(\\frac{{{_pw('x', ax)}\\cdot{rad}{{{ytex}}}}}{{{_pw('z', cz)}}}\\right)"
    cy = R(my, n)
    vals = [sp.Integer(ax), cy, sp.Integer(-cz)]
    sol = (f"$$\\ln\\left(\\frac{{u\\cdot v}}{{w}}\\right)=\\ln u+\\ln v-\\ln w,\\qquad \\ln\\left(u^k\\right)=k\\ln u,\\qquad {rad}{{{ytex}}}=y^{{{L(cy)}}}$$\n\n"
           f"$${tex}={ax}\\ln x+{L(cy)}\\ln y-{cz}\\ln z$$")
    return {
        "statement": f"Zerlege mit den Logarithmengesetzen ($x,y,z>0$) in die Form $\\alpha\\ln x+\\beta\\ln y+\\gamma\\ln z$: $${tex}$$",
        "parts": [part("$(\\alpha;\\ \\beta;\\ \\gamma)$", {"type": "tuple", "value": [sp.sstr(v) for v in vals], "names": ["α", "β", "γ"]}, sol, [
            "Produkt → Summe, Quotient → Differenz, Potenz → Faktor.",
            f"Schreibe die Wurzel als Potenz: ${rad}{{{ytex}}}=y^{{{L(cy)}}}$.",
            "Was im Nenner steht, bekommt ein Minus.",
        ])],
    }


@gen("gb-exp-gleichung", "g2", ["g-logarithmen"], "Exponentialgleichung (gleiche Basis)", "ohne", 1, 4)
def _exp_gl(rng):
    kind = rng.choice(["A", "B"])
    if kind == "A":
        b = rng.choice([2, 3, 5])
        while True:
            m, n, k = rng.choice([1, 2, 3, -1]), rng.randint(-3, 3), rng.randint(-3, {2: 7, 3: 4, 5: 3}[b])
            if k != n:
                break
        rhs = sp.Integer(b) ** k
        x0 = R(k - n, m)
        ex = L(m * x + n)
        tex = f"{b}^{{{ex}}}={L(rhs)}"
        sol = (f"Rechte Seite als Potenz von ${b}$ schreiben: ${L(rhs)}={b}^{{{k}}}$.\n\n"
               f"Gleiche Basis → Exponenten gleichsetzen: $${ex}={k}\\Rightarrow x={L(x0)}$$")
        h3 = f"${L(rhs)}={b}^{{{k}}}$. Setze die Exponenten gleich: ${ex}={k}$."
    else:
        u, (p, q) = rng.choice([2, 3]), rng.choice([(2, 3), (3, 2), (2, 1), (4, 3), (3, 4), (1, 2)])
        # (u^p)^x = u^q  → x = q/p
        A, Bv = u**p, u**q
        if A == Bv:
            p, q = 2, 3
            A, Bv = u**p, u**q
        x0 = R(q, p)
        tex = f"{A}^{{x}}={Bv}"
        sol = (f"Beide Seiten als Potenz von ${u}$: ${A}={u}^{{{p}}}$, ${Bv}={u}^{{{q}}}$.\n\n"
               f"$${u}^{{{p}x}}={u}^{{{q}}}\\Rightarrow {p}x={q}\\Rightarrow x={L(x0)}$$")
        h3 = f"${A}={u}^{{{p}}}$ und ${Bv}={u}^{{{q}}}$. Dann Exponenten vergleichen."
    return {
        "statement": f"Löse ohne Rechner: $${tex}$$",
        "parts": [part("$x=$", {"type": "number", "value": sp.sstr(x0)}, sol, [
            "Kannst du beide Seiten als Potenz derselben Basis schreiben?",
            "Wenn $b^{u}=b^{v}$, dann ist $u=v$ (Exponentenvergleich).",
            h3,
        ])],
    }


@gen("gb-exp-gleichung-log", "g2", ["g-logarithmen"], "Exponentialgleichung mit Logarithmus", "mit", 2, 5)
def _exp_gl_log(rng):
    if rng.random() < 0.6:
        a = rng.choice([2, 3, 5, 50, 200, 1000])
        b = _dec(rng.choice(["1.05", "1.08", "1.2", "1.5", "2", "3", "0.8", "0.9"]))
        c = a * rng.choice([3, 5, 7, 10, 20]) if b > 1 else R(a, rng.choice([2, 3, 4, 10]))
        x0 = sp.log(sp.nsimplify(c) / a) / sp.log(b)
        tex = f"{a}\\cdot {_num(b)}^{{x}}={_num(c)}"
        sol = (f"Durch ${a}$ teilen: ${_num(b)}^x={L(sp.nsimplify(c) / a)}$. Logarithmieren:\n\n"
               f"$$x=\\frac{{\\ln\\left({L(sp.nsimplify(c) / a)}\\right)}}{{\\ln({_num(b)})}}\\approx{float(x0):.4f}$$")
        h3 = f"Nach dem Teilen: ${_num(b)}^x={L(sp.nsimplify(c) / a)}$. Dann $x=\\frac{{\\ln(\\ldots)}}{{\\ln({_num(b)})}}$."
    else:
        k = _dec(rng.choice(["0.2", "0.5", "1.5", "2", "-0.3", "-0.05"]))
        a = rng.choice([1, 2, 4, 10])
        c = a * rng.choice([3, 5, 8, 12]) if k > 0 else R(a, rng.choice([2, 4, 5]))
        x0 = sp.log(sp.nsimplify(c) / a) / k
        tex = f"{'' if a == 1 else str(a) + '\\cdot '}e^{{{_num(k)}x}}={_num(c)}"
        sol = (f"{'Durch ' + str(a) + ' teilen: ' if a != 1 else ''}$e^{{{_num(k)}x}}={L(sp.nsimplify(c) / a)}$. Mit $\\ln$ logarithmieren:\n\n"
               f"$${_num(k)}x=\\ln\\left({L(sp.nsimplify(c) / a)}\\right)\\Rightarrow x=\\frac{{\\ln\\left({L(sp.nsimplify(c) / a)}\\right)}}{{{_num(k)}}}\\approx{float(x0):.4f}$$")
        h3 = "Isoliere die Potenz $e^{\\ldots}$ und wende auf beiden Seiten $\\ln$ an: $\\ln(e^u)=u$."
    return {
        "statement": f"Löse die Gleichung (auf 4 Nachkommastellen): $${tex}$$",
        "parts": [part("$x\\approx$", {"type": "number", "value": str(float(x0)), "rel": 0.001}, sol, [
            "Die Unbekannte steht im Exponenten – welches Werkzeug holt sie dort heraus?",
            "Zuerst die Potenz allein auf eine Seite bringen, dann logarithmieren: $\\ln(b^x)=x\\cdot\\ln b$.",
            h3,
        ])],
    }


# ═════════════════════════ G3: Geometrie & Funktionen ═════════════════════════

_TRIPLES = [(3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25), (20, 21, 29), (9, 40, 41), (6, 8, 10)]


@gen("gb-pyth-seite", "g3", ["g-pythagoras"], "Pythagoras: fehlende Seite", "ohne", 1, 3)
def _pyth_seite(rng):
    a, b, c = rng.choice(_TRIPLES)
    k = rng.choice([1, 1, 2, 3, R(1, 2)])
    a, b, c = a * k, b * k, c * k
    if rng.random() < 0.5:
        a, b = b, a
    ask = rng.choice(["c", "a", "b"])
    vals = {"a": a, "b": b, "c": c}
    given = [n for n in "abc" if n != ask]
    gtxt = " und ".join(f"${n}={_num(vals[n])}$ cm" for n in given)
    if ask == "c":
        sol = f"$$c=\\sqrt{{a^2+b^2}}=\\sqrt{{{_num(a)}^2+{_num(b)}^2}}=\\sqrt{{{_num(a * a + b * b)}}}={_num(c)}\\text{{ cm}}$$"
        h3 = "Gesucht ist die Hypotenuse: $c^2=a^2+b^2$."
    else:
        o = "b" if ask == "a" else "a"
        sol = f"$${ask}=\\sqrt{{c^2-{o}^2}}=\\sqrt{{{_num(c)}^2-{_num(vals[o])}^2}}=\\sqrt{{{_num(c * c - vals[o] ** 2)}}}={_num(vals[ask])}\\text{{ cm}}$$"
        h3 = f"Gesucht ist eine Kathete: ${ask}^2=c^2-{o}^2$ (Minus, nicht Plus!)."
    return {
        "statement": f"In einem rechtwinkligen Dreieck mit Hypotenuse $c$ (rechter Winkel bei $C$) sind {gtxt} gegeben. Berechne ${ask}$.",
        "parts": [part(f"${ask}=$ (in cm)", {"type": "number", "value": sp.sstr(vals[ask]), "unit": "cm"}, sol, [
            "Welcher Satz verbindet die drei Seiten eines rechtwinkligen Dreiecks?",
            "Pythagoras: $a^2+b^2=c^2$, wobei $c$ die Hypotenuse (gegenüber dem rechten Winkel) ist.",
            h3,
        ])],
    }


@gen("gb-pyth-abstand", "g3", ["g-pythagoras", "g-geraden"], "Abstand zweier Punkte", "ohne", 1, 3)
def _pyth_abstand(rng):
    while True:
        x1, y1, x2, y2 = [rng.randint(-6, 8) for _ in range(4)]
        if (x1, y1) != (x2, y2) and x1 != x2 and y1 != y2:
            break
    dx, dy = x2 - x1, y2 - y1
    d2 = dx * dx + dy * dy
    d = sp.sqrt(d2)
    sol = (f"Die Verbindungsstrecke ist die Hypotenuse eines rechtwinkligen Dreiecks mit den Katheten $\\Delta x={dx}$ und $\\Delta y={dy}$:\n\n"
           f"$$d=\\sqrt{{(\\Delta x)^2+(\\Delta y)^2}}=\\sqrt{{({dx})^2+({dy})^2}}=\\sqrt{{{d2}}}={L(d)}$$")
    return {
        "statement": f"Berechne den Abstand der Punkte $P({x1}\\mid {y1})$ und $Q({x2}\\mid {y2})$ (exakt, z.B. `sqrt(29)` oder `2*sqrt(5)`).",
        "parts": [part("$d=$", {"type": "number", "value": sp.sstr(d)}, sol, [
            "Zeichne das Steigungsdreieck zwischen $P$ und $Q$.",
            "Die Katheten sind die Differenzen der $x$- und der $y$-Koordinaten, der Abstand ist die Hypotenuse.",
            f"$\\Delta x={dx}$, $\\Delta y={dy}$. Pythagoras anwenden.",
        ])],
    }


@gen("gb-pyth-anwendung", "g3", ["g-pythagoras"], "Pythagoras in Anwendungen", "mit", 2, 5)
def _pyth_anw(rng):
    kind = rng.choice(["leiter", "raum", "gleichschenklig", "rechteck"])
    if kind == "leiter":
        Lg = _dec(rng.choice(["3.5", "4", "4.5", "5", "6", "7.2"]))
        d = _dec(rng.choice(["0.8", "1", "1.2", "1.5", "1.8"]))
        val = sp.sqrt(Lg**2 - d**2)
        st = f"Eine ${_num(Lg)}$ m lange Leiter steht ${_num(d)}$ m von einer senkrechten Wand entfernt. In welcher Höhe berührt sie die Wand?"
        sol = f"Leiter = Hypotenuse, Abstand und Höhe = Katheten:\n\n$$h=\\sqrt{{{_num(Lg)}^2-{_num(d)}^2}}\\approx{float(val):.3f}\\text{{ m}}$$"
        prompt, unit, h3 = "Höhe (in m)", "m", "Die Leiter ist die Hypotenuse: $h^2=L^2-d^2$."
    elif kind == "raum":
        a, b, c = [rng.randint(2, 12) for _ in range(3)]
        val = sp.sqrt(a * a + b * b + c * c)
        st = f"Ein Quader hat die Kantenlängen $a={a}$ cm, $b={b}$ cm, $c={c}$ cm. Berechne die Länge der Raumdiagonale."
        sol = (f"Zuerst die Flächendiagonale der Grundfläche: $d^2=a^2+b^2={a * a + b * b}$. "
               f"Dann bilden $d$, $c$ und die Raumdiagonale ein rechtwinkliges Dreieck:\n\n$$D=\\sqrt{{a^2+b^2+c^2}}=\\sqrt{{{a * a + b * b + c * c}}}\\approx{float(val):.3f}\\text{{ cm}}$$")
        prompt, unit, h3 = "Raumdiagonale (in cm)", "cm", "Zwei Mal Pythagoras: $D^2=d^2+c^2=a^2+b^2+c^2$."
    elif kind == "gleichschenklig":
        g = rng.randint(4, 16)
        s = rng.randint(g // 2 + 2, g + 6)
        val = sp.sqrt(s * s - R(g, 2) ** 2)
        st = f"Ein gleichschenkliges Dreieck hat die Basis $g={g}$ cm und die Schenkel $s={s}$ cm. Berechne die Höhe auf die Basis."
        sol = (f"Die Höhe halbiert die Basis. Rechtwinkliges Dreieck mit Hypotenuse $s$ und Kathete $\\frac g2={_num(R(g, 2))}$:\n\n"
               f"$$h=\\sqrt{{s^2-\\left(\\tfrac g2\\right)^2}}=\\sqrt{{{s}^2-{_num(R(g, 2))}^2}}\\approx{float(val):.3f}\\text{{ cm}}$$")
        prompt, unit, h3 = "Höhe (in cm)", "cm", "Die Höhe teilt das Dreieck in zwei rechtwinklige Dreiecke mit Kathete $\\frac g2$ und Hypotenuse $s$."
    else:
        l, w = rng.randint(3, 25), rng.randint(2, 20)
        val = sp.sqrt(l * l + w * w)
        st = f"Ein rechteckiges Feld ist ${l}$ m lang und ${w}$ m breit. Wie lang ist die Diagonale?"
        sol = f"$$d=\\sqrt{{{l}^2+{w}^2}}=\\sqrt{{{l * l + w * w}}}\\approx{float(val):.3f}\\text{{ m}}$$"
        prompt, unit, h3 = "Diagonale (in m)", "m", "Die Diagonale ist die Hypotenuse, Länge und Breite sind die Katheten."
    return {
        "statement": st,
        "parts": [part(prompt, {"type": "number", "value": str(float(val)), "rel": 0.002, "unit": unit}, sol, [
            "Mach eine Skizze und suche ein rechtwinkliges Dreieck.",
            "Welche Strecke liegt dem rechten Winkel gegenüber (Hypotenuse)?",
            h3,
        ])],
    }


# ───────────── Trigonometrie im rechtwinkligen Dreieck ─────────────

_DREIECK = "Im rechtwinkligen Dreieck $ABC$ mit $\\gamma=90^\\circ$ liegt $a$ gegenüber von $\\alpha$, $b$ ist die Ankathete von $\\alpha$ und $c$ die Hypotenuse."


@gen("gb-trig-seite", "g3", ["g-trig-dreieck"], "Seite im rechtwinkligen Dreieck berechnen", "mit", 1, 4)
def _trig_seite(rng):
    al = rng.choice([v for v in range(12, 79) if v not in (30, 45, 60)])
    g = rng.choice(["a", "b", "c"])
    gv = _dec(str(rng.randint(20, 150) / 10))
    ask = rng.choice([n for n in "abc" if n != g])
    A = math.radians(al)
    c = {"c": float(gv), "a": float(gv) / math.sin(A), "b": float(gv) / math.cos(A)}[g]
    vals = {"a": c * math.sin(A), "b": c * math.cos(A), "c": c}
    val = vals[ask]
    if ask == "a" and g == "c":
        f, comp = "\\sin\\alpha=\\frac ac", f"a=c\\cdot\\sin\\alpha={_num(gv)}\\cdot\\sin({al}^\\circ)"
    elif ask == "b" and g == "c":
        f, comp = "\\cos\\alpha=\\frac bc", f"b=c\\cdot\\cos\\alpha={_num(gv)}\\cdot\\cos({al}^\\circ)"
    elif ask == "c" and g == "a":
        f, comp = "\\sin\\alpha=\\frac ac", f"c=\\frac{{a}}{{\\sin\\alpha}}=\\frac{{{_num(gv)}}}{{\\sin({al}^\\circ)}}"
    elif ask == "c" and g == "b":
        f, comp = "\\cos\\alpha=\\frac bc", f"c=\\frac{{b}}{{\\cos\\alpha}}=\\frac{{{_num(gv)}}}{{\\cos({al}^\\circ)}}"
    elif ask == "a" and g == "b":
        f, comp = "\\tan\\alpha=\\frac ab", f"a=b\\cdot\\tan\\alpha={_num(gv)}\\cdot\\tan({al}^\\circ)"
    else:
        f, comp = "\\tan\\alpha=\\frac ab", f"b=\\frac{{a}}{{\\tan\\alpha}}=\\frac{{{_num(gv)}}}{{\\tan({al}^\\circ)}}"
    sol = f"Gegeben ${g}$, gesucht ${ask}$ → Formel ${f}$ (SOH-CAH-TOA).\n\n$${comp}\\approx{val:.3f}\\text{{ cm}}$$\n\nRechner im Grad-Modus (DEG)!"
    return {
        "statement": f"{_DREIECK} Gegeben: $\\alpha={al}^\\circ$, ${g}={_num(gv)}$ cm. Berechne ${ask}$.",
        "parts": [part(f"${ask}=$ (in cm)", {"type": "number", "value": str(val), "rel": 0.002, "unit": "cm"}, sol, [
            "Bestimme, welche Seite bezüglich $\\alpha$ Gegenkathete, Ankathete bzw. Hypotenuse ist.",
            "$\\sin\\alpha=\\frac{\\text{GK}}{\\text{H}}$, $\\cos\\alpha=\\frac{\\text{AK}}{\\text{H}}$, $\\tan\\alpha=\\frac{\\text{GK}}{\\text{AK}}$. Wähle die Funktion, die gegebene und gesuchte Seite verbindet.",
            f"Verwende ${f}$ und stelle nach ${ask}$ um. Rechner auf Grad (DEG) stellen.",
        ])],
    }


@gen("gb-trig-winkel", "g3", ["g-trig-dreieck"], "Winkel im rechtwinkligen Dreieck berechnen", "mit", 1, 4)
def _trig_winkel(rng):
    pair = rng.choice([("a", "c"), ("b", "c"), ("a", "b")])
    while True:
        u, v = rng.randint(15, 120) / 10, rng.randint(15, 120) / 10
        if pair[1] == "c" and u >= v:
            continue
        if abs(u - v) > 0.2:
            break
    u, v = _dec(str(u)), _dec(str(v))
    if pair == ("a", "c"):
        ang, fn = math.degrees(math.asin(float(u / v))), f"\\alpha=\\arcsin\\left(\\frac{{a}}{{c}}\\right)=\\arcsin\\left(\\frac{{{_num(u)}}}{{{_num(v)}}}\\right)"
    elif pair == ("b", "c"):
        ang, fn = math.degrees(math.acos(float(u / v))), f"\\alpha=\\arccos\\left(\\frac{{b}}{{c}}\\right)=\\arccos\\left(\\frac{{{_num(u)}}}{{{_num(v)}}}\\right)"
    else:
        ang, fn = math.degrees(math.atan(float(u / v))), f"\\alpha=\\arctan\\left(\\frac{{a}}{{b}}\\right)=\\arctan\\left(\\frac{{{_num(u)}}}{{{_num(v)}}}\\right)"
    sol = f"$${fn}\\approx{ang:.2f}^\\circ$$\n\nUmkehrfunktion auf dem Rechner: `sin⁻¹`, `cos⁻¹`, `tan⁻¹` (Grad-Modus). Der zweite spitze Winkel ist $\\beta=90^\\circ-\\alpha\\approx{90 - ang:.2f}^\\circ$."
    return {
        "statement": f"{_DREIECK} Gegeben: ${pair[0]}={_num(u)}$ cm, ${pair[1]}={_num(v)}$ cm. Berechne den Winkel $\\alpha$.",
        "parts": [part("$\\alpha=$ (in Grad)", {"type": "number", "value": str(ang), "tol": 0.05, "unit": "°"}, sol, [
            "Welche Seiten sind bezüglich $\\alpha$ gegeben: Gegenkathete, Ankathete, Hypotenuse?",
            "Stelle das passende Verhältnis auf ($\\sin$, $\\cos$ oder $\\tan$) und verwende die Umkehrfunktion.",
            f"Hier passt ${'\\sin' if pair == ('a', 'c') else '\\cos' if pair == ('b', 'c') else '\\tan'}\\alpha=\\frac{{{pair[0]}}}{{{pair[1]}}}$. Rechne mit `{'sin' if pair == ('a', 'c') else 'cos' if pair == ('b', 'c') else 'tan'}⁻¹` im Grad-Modus.",
        ])],
    }


_EXAKT = {
    ("sin", 0): "0", ("sin", 30): "1/2", ("sin", 45): "sqrt(2)/2", ("sin", 60): "sqrt(3)/2", ("sin", 90): "1",
    ("cos", 0): "1", ("cos", 30): "sqrt(3)/2", ("cos", 45): "sqrt(2)/2", ("cos", 60): "1/2", ("cos", 90): "0",
    ("tan", 0): "0", ("tan", 30): "sqrt(3)/3", ("tan", 45): "1", ("tan", 60): "sqrt(3)",
}


@gen("gb-trig-exakt", "g3", ["g-trig-dreieck"], "Exakte Werte von sin, cos, tan", "ohne", 2, 3)
def _trig_exakt(rng):
    keys = rng.sample([k for k in _EXAKT if k[1] in (30, 45, 60)], 2) + [rng.choice([k for k in _EXAKT if k[1] in (0, 90)])]
    parts = []
    for lab, (fn, ang) in zip("abc", keys):
        val = sp.sympify(_EXAKT[(fn, ang)])
        sol = (f"${'\\' + fn}({ang}^\\circ)={L(val)}$.\n\n"
               + ("Herleitung am halben gleichseitigen Dreieck (Seite 2, Höhe $\\sqrt3$): Gegenkathete zu $30^\\circ$ ist 1, zu $60^\\circ$ ist $\\sqrt3$, Hypotenuse 2."
                  if ang in (30, 60) else
                  "Herleitung am halben Quadrat (Katheten 1, Diagonale $\\sqrt2$): $\\sin45^\\circ=\\cos45^\\circ=\\frac{1}{\\sqrt2}=\\frac{\\sqrt2}{2}$, $\\tan45^\\circ=1$."
                  if ang == 45 else
                  "Am Einheitskreis: Der Punkt zu $0^\\circ$ ist $(1\\mid0)$, zu $90^\\circ$ ist $(0\\mid1)$; $\\cos$ = $x$-Koordinate, $\\sin$ = $y$-Koordinate, $\\tan=\\frac{\\sin}{\\cos}$."))
        parts.append(part(f"${'\\' + fn}({ang}^\\circ)=$", {"type": "number", "value": _EXAKT[(fn, ang)]}, sol, [
            "Diese Werte solltest du ohne Rechner kennen (oder schnell herleiten können).",
            "Merkhilfe: $\\sin(0^\\circ,30^\\circ,45^\\circ,60^\\circ,90^\\circ)=\\frac{\\sqrt0}{2},\\frac{\\sqrt1}{2},\\frac{\\sqrt2}{2},\\frac{\\sqrt3}{2},\\frac{\\sqrt4}{2}$; beim $\\cos$ ist die Reihenfolge umgekehrt.",
            "$\\tan\\alpha=\\frac{\\sin\\alpha}{\\cos\\alpha}$.",
        ], lab))
    return {"statement": "Gib den exakten Wert an (ohne Rechner, z.B. `sqrt(3)/2`):", "parts": parts}


@gen("gb-trig-steigung", "g3", ["g-trig-dreieck"], "Steigung in Prozent und Steigungswinkel", "mit", 2, 5)
def _trig_steigung(rng):
    p = rng.choice([4, 6, 8, 10, 12, 15, 18, 20, 25, 30])
    s = rng.choice([200, 350, 500, 800, 1000, 1200, 1500])
    ang = math.degrees(math.atan(p / 100))
    h = s * math.sin(math.atan(p / 100))
    sol_a = f"Steigung $=\\tan\\alpha=\\frac{{\\text{{Höhendifferenz}}}}{{\\text{{horizontale Distanz}}}}={_num(R(p, 100))}$.\n\n$$\\alpha=\\arctan({_num(R(p, 100))})\\approx{ang:.2f}^\\circ$$"
    sol_b = f"Die Strasse selbst ist die Hypotenuse ($s={s}$ m), die Höhendifferenz die Gegenkathete:\n\n$$h=s\\cdot\\sin\\alpha={s}\\cdot\\sin({ang:.3f}^\\circ)\\approx{h:.2f}\\text{{ m}}$$"
    return {
        "statement": f"Eine Strasse hat eine Steigung von ${p}\\,\\%$ (d.h. ${p}$ m Höhe auf $100$ m horizontale Distanz).",
        "parts": [
            part("Steigungswinkel $\\alpha$ (in Grad)", {"type": "number", "value": str(ang), "tol": 0.05, "unit": "°"}, sol_a, [
                "Die Steigung ist ein Verhältnis zweier Katheten. Welche Winkelfunktion passt?",
                "$\\tan\\alpha=\\frac{\\text{Gegenkathete}}{\\text{Ankathete}}=\\frac{\\text{Höhe}}{\\text{horizontale Distanz}}$.",
                f"$\\alpha=\\arctan\\left(\\frac{{{p}}}{{100}}\\right)$ im Grad-Modus. Achtung: nicht $\\alpha={p}^\\circ$!",
            ], "a"),
            part(f"Höhenunterschied nach ${s}$ m Fahrt **auf der Strasse** (in m)", {"type": "number", "value": str(h), "rel": 0.002, "unit": "m"}, sol_b, [
                "Ist die gefahrene Strecke eine Kathete oder die Hypotenuse?",
                "Die gefahrene Strecke ist die Hypotenuse, die Höhe die Gegenkathete zu $\\alpha$.",
                "$h=s\\cdot\\sin\\alpha$ mit dem Winkel aus a).",
            ], "b"),
        ],
    }


# ───────────── Bogenmass ─────────────

@gen("gb-grad-bogen", "g3", ["g-bogenmass"], "Grad und Bogenmass (exakt)", "ohne", 1, 4)
def _grad_bogen(rng):
    deg = rng.choice([15, 30, 45, 60, 90, 120, 135, 150, 180, 210, 225, 240, 270, 300, 315, 330, 360, 720])
    rad = sp.Rational(deg, 180) * sp.pi
    deg2 = rng.choice([v for v in [30, 45, 60, 90, 120, 135, 150, 210, 240, 270, 300, 330, 18, 36, 72] if v != deg])
    rad2 = sp.Rational(deg2, 180) * sp.pi
    return {
        "statement": "Rechne ohne Rechner um. Es gilt $180^\\circ\\ \\hat=\\ \\pi$.",
        "parts": [
            part(f"${deg}^\\circ$ im Bogenmass (exakt, z.B. `3*pi/4`)", {"type": "number", "value": sp.sstr(rad)},
                 f"$$x={deg}^\\circ\\cdot\\frac{{\\pi}}{{180^\\circ}}={L(rad)}$$", [
                     "Welcher Winkel in Grad entspricht $\\pi$?",
                     "Grad → Bogenmass: mit $\\frac{\\pi}{180^\\circ}$ multiplizieren.",
                     f"Kürze $\\frac{{{deg}}}{{180}}$ und schreibe $\\pi$ dazu.",
                 ], "a"),
            part(f"${L(rad2)}$ in Grad", {"type": "number", "value": str(deg2), "unit": "°"},
                 f"$$\\alpha={L(rad2)}\\cdot\\frac{{180^\\circ}}{{\\pi}}={deg2}^\\circ$$", [
                     "Ersetze $\\pi$ durch $180^\\circ$.",
                     "Bogenmass → Grad: mit $\\frac{180^\\circ}{\\pi}$ multiplizieren.",
                     f"Rechne ${L(rad2 / sp.pi)}\\cdot180^\\circ$.",
                 ], "b"),
        ],
    }


@gen("gb-bogen-dezimal", "g3", ["g-bogenmass"], "Grad und Bogenmass (Dezimalzahlen)", "mit", 1, 3)
def _bogen_dez(rng):
    deg = rng.choice([v for v in range(5, 355) if v % 15 != 0])
    rad = _dec(str(rng.randint(5, 60) / 10))
    r1 = math.radians(deg)
    d2 = math.degrees(float(rad))
    return {
        "statement": "Rechne um (auf 3 Nachkommastellen).",
        "parts": [
            part(f"${deg}^\\circ$ im Bogenmass", {"type": "number", "value": str(r1), "rel": 0.001},
                 f"$$x={deg}\\cdot\\frac{{\\pi}}{{180}}\\approx{r1:.4f}$$", [
                     "Wie hängen $180^\\circ$ und $\\pi$ zusammen?",
                     "Grad → Bogenmass: $x=\\alpha\\cdot\\frac{\\pi}{180^\\circ}$.",
                     f"Rechne ${deg}\\cdot\\pi/180$.",
                 ], "a"),
            part(f"$x={_num(rad)}$ (Bogenmass) in Grad", {"type": "number", "value": str(d2), "rel": 0.001, "unit": "°"},
                 f"$$\\alpha={_num(rad)}\\cdot\\frac{{180^\\circ}}{{\\pi}}\\approx{d2:.3f}^\\circ$$", [
                     "Umgekehrt wie in a).",
                     "Bogenmass → Grad: $\\alpha=x\\cdot\\frac{180^\\circ}{\\pi}$.",
                     f"Rechne ${_num(rad)}\\cdot180/\\pi$. Kontrolle: $1\\approx57.3^\\circ$.",
                 ], "b"),
        ],
    }


@gen("gb-bogenlaenge", "g3", ["g-bogenmass"], "Kreisbogen und Kreissektor", "mit", 2, 5)
def _bogenlaenge(rng):
    r = rng.choice([2, 3, 4, 5, 6, 8, 10, 12, 15])
    deg = rng.choice([v for v in range(20, 340, 5) if v not in (90, 180)])
    phi = math.radians(deg)
    b = r * phi
    A = r * r * phi / 2
    sol_a = f"Winkel ins Bogenmass: $\\varphi={deg}\\cdot\\frac{{\\pi}}{{180}}\\approx{phi:.4f}$.\n\n$$b=r\\cdot\\varphi={r}\\cdot{phi:.4f}\\approx{b:.3f}\\text{{ cm}}$$"
    sol_b = f"$$A=\\frac{{r^2\\cdot\\varphi}}{{2}}=\\frac{{{r}^2\\cdot{phi:.4f}}}{{2}}\\approx{A:.3f}\\text{{ cm}}^2$$\n\n(Kontrolle mit Grad: $A=\\pi r^2\\cdot\\frac{{{deg}^\\circ}}{{360^\\circ}}$.)"
    return {
        "statement": f"Ein Kreissektor hat den Radius $r={r}$ cm und den Mittelpunktswinkel $\\varphi={deg}^\\circ$.",
        "parts": [
            part("Bogenlänge $b$ (in cm)", {"type": "number", "value": str(b), "rel": 0.002, "unit": "cm"}, sol_a, [
                "Die einfache Formel für die Bogenlänge gilt nur im Bogenmass.",
                "$b=r\\cdot\\varphi$ mit $\\varphi$ im Bogenmass.",
                f"Rechne zuerst ${deg}^\\circ$ ins Bogenmass um.",
            ], "a"),
            part("Fläche $A$ des Sektors (in cm²)", {"type": "number", "value": str(A), "rel": 0.002, "unit": "cm^2"}, sol_b, [
                "Welcher Anteil des ganzen Kreises ist der Sektor?",
                "Im Bogenmass: $A=\\frac12r^2\\varphi$. (In Grad: $A=\\pi r^2\\cdot\\frac{\\varphi}{360^\\circ}$.)",
                "Setze $r$ und das $\\varphi$ (Bogenmass) aus a) ein.",
            ], "b"),
        ],
    }


# ───────────── Geraden ─────────────

@gen("gb-gerade-2punkte", "g3", ["g-geraden"], "Gerade durch zwei Punkte", "ohne", 1, 5)
def _gerade_2p(rng):
    while True:
        x1, x2 = rng.sample(range(-6, 8), 2)
        y1, y2 = rng.randint(-8, 8), rng.randint(-8, 8)
        m = R(y2 - y1, x2 - x1)
        if m != 0 and m.q in (1, 2, 3, 4):
            break
    q = y1 - m * x1
    sol_a = f"$$m=\\frac{{y_2-y_1}}{{x_2-x_1}}=\\frac{{{y2}-({y1})}}{{{x2}-({x1})}}=\\frac{{{y2 - y1}}}{{{x2 - x1}}}={L(m)}$$"
    sol_b = (sol_a + f"\n\n$P$ einsetzen in $y=mx+q$: ${y1}={L(m)}\\cdot({x1})+q\\Rightarrow q={L(q)}$.\n\n$$y={L(m * x + q)}$$")
    return {
        "statement": f"Eine Gerade geht durch die Punkte $P({x1}\\mid {y1})$ und $Q({x2}\\mid {y2})$.",
        "parts": [
            part("Steigung $m=$", {"type": "number", "value": sp.sstr(m)}, sol_a, [
                "Steigung = Höhenunterschied durch Horizontalunterschied.",
                "$m=\\frac{\\Delta y}{\\Delta x}=\\frac{y_2-y_1}{x_2-x_1}$.",
                "Achte auf die Reihenfolge: oben und unten denselben Punkt zuerst nehmen.",
            ], "a"),
            part("Geradengleichung $y=$", {"type": "expr", "value": sp.sstr(m * x + q), "var": "x"}, sol_b, [
                "Allgemeine Form: $y=mx+q$. $m$ kennst du schon.",
                "Setze einen der beiden Punkte ein, um den $y$-Achsenabschnitt $q$ zu bestimmen.",
                f"${y1}={L(m)}\\cdot({x1})+q$ nach $q$ auflösen.",
            ], "b"),
        ],
    }


@gen("gb-gerade-ablesen", "g3", ["g-geraden"], "Steigung und y-Achsenabschnitt bestimmen", "ohne", 1, 3)
def _gerade_ablesen(rng):
    while True:
        a, b, c = _nz(rng, -6, 6), _nz(rng, -5, 5), rng.randint(-12, 12)
        if math.gcd(math.gcd(abs(a), abs(b)), abs(c)) == 1 and b not in (1,):
            break
    m, q = R(-a, b), R(c, b)
    eq = f"{_lin([a, b], ['x', 'y'])}={c}"
    sol = (f"Nach $y$ auflösen: ${_co(b, 'y')}={L(-a * x + c)}$, durch ${b}$ teilen:\n\n$$y={L(m * x + q)}$$\n\n"
           f"Also $m={L(m)}$, $q={L(q)}$ (Schnittpunkt mit der $y$-Achse $(0\\mid{L(q)})$).")
    return {
        "statement": f"Gegeben ist die Gerade $${eq}$$",
        "parts": [part("$(m;\\ q)$ in $y=mx+q$", {"type": "tuple", "value": [sp.sstr(m), sp.sstr(q)], "names": ["m", "q"]}, sol, [
            "Die Steigung und den Achsenabschnitt kann man erst ablesen, wenn die Gleichung in der Form $y=mx+q$ steht.",
            "Bringe den $x$-Term auf die rechte Seite und teile durch den Koeffizienten von $y$.",
            f"${_co(b, 'y')}={L(-a * x + c)}$ – jetzt durch ${b}$ teilen (jeden Summanden!).",
        ])],
    }


@gen("gb-gerade-schnitt", "g3", ["g-geraden", "g-lin-gleichung"], "Schnittpunkt zweier Geraden", "ohne", 1, 4)
def _gerade_schnitt(rng):
    while True:
        xs, ys = rng.randint(-5, 5), rng.randint(-6, 6)
        m1, m2 = [sp.sympify(v) for v in rng.sample([-3, -2, -1, R(-1, 2), R(1, 2), 1, 2, 3], 2)]
        q1, q2 = ys - m1 * xs, ys - m2 * xs
        if q1.q == 1 and q2.q == 1:
            break
    g1, g2 = m1 * x + q1, m2 * x + q2
    step = f"{_co(m1 - m2)}={L(q2 - q1)}" + ("" if m1 - m2 == 1 else f"\\Rightarrow x={xs}")
    sol = (f"Gleichsetzen: $${L(g1)}={L(g2)}$$\n\n$x$-Terme auf eine Seite, Zahlen auf die andere: $${step}$$\n\n"
           f"In $g$ einsetzen: $y={L(m1)}\\cdot({xs}){_sg(q1)}={ys}$. Schnittpunkt $S({xs}\\mid{ys})$.")
    return {
        "statement": f"Berechne den Schnittpunkt der Geraden $g:\\ y={L(g1)}$ und $h:\\ y={L(g2)}$.",
        "parts": [part("$S$", {"type": "tuple", "value": [str(xs), str(ys)], "names": ["x_S", "y_S"]}, sol, [
            "Im Schnittpunkt haben beide Geraden denselben $y$-Wert.",
            "Setze die beiden Funktionsterme gleich und löse nach $x$ auf.",
            "Mit dem gefundenen $x$ den $y$-Wert in einer der beiden Gleichungen berechnen.",
        ])],
    }


@gen("gb-gerade-senkrecht", "g3", ["g-geraden"], "Parallele und senkrechte Geraden", "ohne", 2, 4)
def _gerade_senkrecht(rng):
    m = sp.sympify(rng.choice([-4, -3, -2, -1, R(-1, 2), R(-2, 3), R(1, 3), R(1, 2), 1, 2, 3, R(3, 2)]))
    q = rng.randint(-5, 5)
    px, py = rng.randint(-4, 4), rng.randint(-6, 6)
    kind = rng.choice(["senkrecht", "parallel"])
    mn = -1 / m if kind == "senkrecht" else m
    qn = py - mn * px
    ans = mn * x + qn
    sol = (("Senkrecht: $m_1\\cdot m_2=-1$, also $m_2=-\\frac{1}{m_1}=" + L(mn) + "$." if kind == "senkrecht"
            else f"Parallel: gleiche Steigung $m={L(mn)}$.") +
           f"\n\n$P({px}\\mid{py})$ einsetzen: ${py}={L(mn)}\\cdot({px})+q\\Rightarrow q={L(qn)}$.\n\n$$y={L(ans)}$$")
    return {
        "statement": f"Bestimme die Gerade $h$, die durch $P({px}\\mid {py})$ geht und {'senkrecht' if kind == 'senkrecht' else 'parallel'} zu $g:\\ y={L(m * x + q)}$ ist.",
        "parts": [part("$h:\\ y=$", {"type": "expr", "value": sp.sstr(ans), "var": "x"}, sol, [
            "Welche Steigung muss $h$ haben?",
            "Parallel: gleiche Steigung. Senkrecht: $m_h=-\\frac{1}{m_g}$ (Kehrwert mit umgekehrtem Vorzeichen).",
            f"Mit der Steigung ${L(mn)}$ und dem Punkt $P$ den Achsenabschnitt $q$ berechnen.",
        ])],
    }


# ───────────── Einheiten & Zehnerpotenzen ─────────────

_UMRECHNUNG = [
    ("cm^2", "m^2", R(1, 10**4), "1\\text{ m}^2=100\\text{ cm}\\cdot100\\text{ cm}=10^4\\text{ cm}^2"),
    ("m^2", "cm^2", sp.Integer(10**4), "1\\text{ m}^2=10^4\\text{ cm}^2"),
    ("mm^2", "cm^2", R(1, 100), "1\\text{ cm}^2=10\\text{ mm}\\cdot10\\text{ mm}=100\\text{ mm}^2"),
    ("dm^3", "cm^3", sp.Integer(1000), "1\\text{ dm}^3=10^3\\text{ cm}^3=1000\\text{ cm}^3"),
    ("cm^3", "m^3", R(1, 10**6), "1\\text{ m}^3=(100\\text{ cm})^3=10^6\\text{ cm}^3"),
    ("l", "cm^3", sp.Integer(1000), "1\\text{ l}=1\\text{ dm}^3=1000\\text{ cm}^3"),
    ("ml", "l", R(1, 1000), "1\\text{ l}=1000\\text{ ml}"),
    ("m^3", "l", sp.Integer(1000), "1\\text{ m}^3=1000\\text{ dm}^3=1000\\text{ l}"),
    ("km/h", "m/s", R(1, 1) / R(36, 10), "1\\text{ km/h}=\\frac{1000\\text{ m}}{3600\\text{ s}}=\\frac{1}{3.6}\\text{ m/s}"),
    ("m/s", "km/h", R(36, 10), "1\\text{ m/s}=3.6\\text{ km/h}"),
    ("g/cm^3", "kg/m^3", sp.Integer(1000), "1\\text{ g/cm}^3=\\frac{10^{-3}\\text{ kg}}{10^{-6}\\text{ m}^3}=1000\\text{ kg/m}^3"),
    ("h", "s", sp.Integer(3600), "1\\text{ h}=60\\text{ min}=3600\\text{ s}"),
    ("ha", "m^2", sp.Integer(10**4), "1\\text{ ha}=100\\text{ m}\\cdot100\\text{ m}=10^4\\text{ m}^2"),
    ("km^2", "m^2", sp.Integer(10**6), "1\\text{ km}^2=(1000\\text{ m})^2=10^6\\text{ m}^2"),
]


def _utex(u: str) -> str:
    if "^" in u:
        base, e = u.split("^")
        return f"\\text{{ {base}}}^{e}"
    return f"\\text{{ {u}}}"


@gen("gb-einheiten-umrechnen", "g3", ["g-einheiten"], "Einheiten umrechnen (Flächen, Volumen, Geschwindigkeit)", "ohne", 1, 3)
def _einh_umr(rng):
    parts = []
    for lab, (fu, tu, fac, why) in zip("ab", rng.sample(_UMRECHNUNG, 2)):
        if fu == "km/h":
            v = sp.Integer(rng.choice([18, 36, 54, 72, 90, 108, 120]))
        elif fu == "m/s":
            v = _dec(rng.choice(["5", "12.5", "15", "20", "25", "30"]))
        elif fu in ("h",):
            v = _dec(rng.choice(["1.5", "2.25", "0.75", "3"]))
        else:
            v = _dec(rng.choice(["2.5", "4", "12", "0.35", "150", "7.2", "0.08", "36"]))
        val = v * fac
        sol = f"$${why}$$\n\n$${_num(v)}{_utex(fu)}={_num(v)}\\cdot{L(fac) if fac.q != 1 else _num(fac)}{_utex(tu)}={_num(val)}{_utex(tu)}$$"
        parts.append(part(f"${_num(v)}{_utex(fu)}=\\ ?{_utex(tu)}$", {"type": "number", "value": sp.sstr(val), "rel": 1e-6}, sol, [
            "Wie viele der kleineren Einheiten passen in eine grössere?",
            "Bei Flächen wird der Längenfaktor quadriert, bei Volumen hoch 3 genommen (z.B. $1\\text{ m}=100\\text{ cm}\\Rightarrow1\\text{ m}^2=10\\,000\\text{ cm}^2$).",
            f"Es gilt ${why}$.",
        ], lab))
    return {"statement": "Rechne in die verlangte Einheit um (Zehnerpotenzen z.B. als `3.5*10^(-4)` eingeben):", "parts": parts}


_PRAEFIX = [("k", 3, "Kilo"), ("M", 6, "Mega"), ("G", 9, "Giga"), ("m", -3, "Milli"), ("\\mu", -6, "Mikro"), ("n", -9, "Nano")]
_GROESSEN = [("\\Omega", "Ω"), ("F", "F"), ("W", "W"), ("m", "m"), ("Hz", "Hz"), ("A", "A"), ("V", "V")]


@gen("gb-wiss-schreibweise", "g3", ["g-einheiten", "g-potenzen"], "Wissenschaftliche Schreibweise und Vorsätze", "ohne", 1, 4)
def _wiss(rng):
    # a) Zahl in wissenschaftlicher Schreibweise
    mant = _dec(rng.choice(["1.5", "2.4", "3.7", "4.2", "5.06", "6.8", "7.25", "8.1", "9.3"]))
    ex = rng.choice([-7, -6, -5, -4, -3, 3, 4, 5, 6, 7])
    num = mant * sp.Integer(10) ** ex
    ntxt = f"{float(num):.10f}".rstrip("0").rstrip(".") if ex < 0 else str(int(num))
    pa = part(f"Schreibe ${ntxt}$ in der Form $a\\cdot10^n$ mit $1\\le a<10$. Gib $(a;\\ n)$ an.",
              {"type": "tuple", "value": [sp.sstr(mant), str(ex)], "names": ["a", "n"]},
              f"Das Komma um ${abs(ex)}$ Stellen nach {'rechts' if ex < 0 else 'links'} schieben, bis genau eine Ziffer ungleich 0 davor steht:\n\n$${ntxt}={_num(mant)}\\cdot10^{{{ex}}}$$", [
                  "Wie viele Stellen musst du das Komma verschieben, damit eine Zahl zwischen 1 und 10 entsteht?",
                  "Komma nach links verschieben → positiver Exponent; nach rechts → negativer Exponent.",
                  f"Die Mantisse ist $a={_num(mant)}$. Zähle die Stellen für den Exponenten.",
              ], "a")
    # b) Rechnen mit Zehnerpotenzen
    e1, e2 = rng.randint(-8, 9), rng.randint(-9, 6)
    if rng.random() < 0.5:
        a1, a2 = rng.choice([2, 3, 4, 5, 6, 8]), _dec(rng.choice(["2", "3", "4", "5", "1.5"]))
        mres = a1 * a2
        val = mres * sp.Integer(10) ** (e1 + e2)
        tex = f"\\left({a1}\\cdot10^{{{e1}}}\\right)\\cdot\\left({_num(a2)}\\cdot10^{{{e2}}}\\right)"
        sol = (f"Mantissen multiplizieren, Exponenten addieren:\n\n"
               f"$${tex}={_num(mres)}\\cdot10^{{{e1}+({e2})}}={_num(mres)}\\cdot10^{{{e1 + e2}}}$$")
    else:
        a1, a2 = rng.choice([(3, "2"), (6, "4"), (9, "2"), (3, "1.5"), (6, "1.5"), (8, "5"), (2, "4"), (7, "2")])
        a2 = _dec(a2)
        mres = a1 / a2
        val = mres * sp.Integer(10) ** (e1 - e2)
        tex = f"\\frac{{{a1}\\cdot10^{{{e1}}}}}{{{_num(a2)}\\cdot10^{{{e2}}}}}"
        sol = (f"Mantissen dividieren, Exponenten subtrahieren:\n\n"
               f"$${tex}={_num(mres)}\\cdot10^{{{e1}-({e2})}}={_num(mres)}\\cdot10^{{{e1 - e2}}}$$")
    pb = part(f"${tex}=$", {"type": "number", "value": sp.sstr(val)}, sol, [
        "Rechne Mantissen und Zehnerpotenzen getrennt.",
        "$10^m\\cdot10^n=10^{m+n}$, $\\frac{10^m}{10^n}=10^{m-n}$.",
        "Eingabe z.B. als `1.2*10^(-5)` (nicht mit `e`).",
    ], "b")
    # c) Vorsatz
    pre, pe, pname = rng.choice(_PRAEFIX)
    gt, gname = rng.choice(_GROESSEN)
    if gname == "m" and pre == "m":
        pre, pe, pname = "k", 3, "Kilo"
    v = _dec(rng.choice(["2.2", "4.7", "10", "33", "0.5", "150", "6.8"]))
    val_c = v * sp.Integer(10) ** pe
    unit_tex = gt if gt.startswith("\\") else f"\\mathrm{{{gt}}}"
    pre_tex = "\\mu" if pre == "\\mu" else f"\\mathrm{{{pre}}}"
    full_tex = f"{pre_tex}{unit_tex}"
    pc = part(f"${_num(v)}\\,{full_tex}$ in ${unit_tex}$ (ohne Vorsatz)",
              {"type": "number", "value": sp.sstr(val_c), "rel": 1e-6},
              f"{pname}: ${pre_tex}\\ \\hat=\\ 10^{{{pe}}}$.\n\n"
              f"$${_num(v)}\\,{full_tex}={_num(v)}\\cdot10^{{{pe}}}\\,{unit_tex}$$", [
                  "Jeder Vorsatz steht für eine Zehnerpotenz.",
                  "k $=10^3$, M $=10^6$, G $=10^9$, m $=10^{-3}$, µ $=10^{-6}$, n $=10^{-9}$.",
                  f"{pname} bedeutet $10^{{{pe}}}$. Ersetze den Vorsatz durch diese Zehnerpotenz.",
              ], "c")
    return {"statement": "Zehnerpotenzen und Vorsätze:", "parts": [pa, pb, pc]}
