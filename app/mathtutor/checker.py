"""Answer checking with SymPy.

Student input comes from a MathLive field (ASCII-math or LaTeX) or a plain text box.
The expected answer comes from the exercise JSON (see content/SCHEMA.md).
The LLM never decides whether a final answer is right: this module does.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)

FUNCS = {
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "cot": sp.cot,
    "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
    "arcsin": sp.asin, "arccos": sp.acos, "arctan": sp.atan,
    "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
    "sqrt": sp.sqrt, "exp": sp.exp, "log": sp.log, "ln": sp.log, "lg": lambda a: sp.log(a, 10),
    "abs": sp.Abs, "Abs": sp.Abs, "root": sp.root,
    "pi": sp.pi, "E": sp.E, "I": sp.I, "oo": sp.oo,
}


class ParseError(ValueError):
    pass


def _latex_to_ascii(s: str) -> str:
    """Translate the LaTeX subset MathLive produces into something parse_expr reads."""
    if "\\" not in s and "{" not in s:
        return s
    rep = [
        (r"\left", ""), (r"\right", ""), (r"\cdot", "*"), (r"\times", "*"), (r"\div", "/"),
        (r"\pi", " pi "), (r"\infty", " oo "), (r"\ln", " ln "), (r"\log", " log "),
        (r"\sin", " sin "), (r"\cos", " cos "), (r"\tan", " tan "), (r"\arcsin", " asin "),
        (r"\arccos", " acos "), (r"\arctan", " atan "), (r"\exponentialE", "E"), (r"\mathrm{e}", "E"),
        (r"\operatorname{e}", "E"), (r"\imaginaryI", "I"), (r"\mathrm{i}", "I"),
        (r"\,", ""), (r"\;", ""), (r"\!", ""), (r"\ ", " "), ("\\degree", "°"), (r"^{\circ}", "°"), (r"^\circ", "°"),
        (r"\lbrack", "("), (r"\rbrack", ")"), (r"\lbrace", "("), (r"\rbrace", ")"),
        (r"\vert", "|"), (r"\mid", "|"),
    ]
    for a, b in rep:
        s = s.replace(a, b)

    def group(i: int) -> tuple[str, int]:
        # returns content of {...} or single token starting at i
        while i < len(s) and s[i] == " ":
            i += 1
        if i < len(s) and s[i] == "{":
            depth, j = 0, i
            while j < len(s):
                if s[j] == "{":
                    depth += 1
                elif s[j] == "}":
                    depth -= 1
                    if depth == 0:
                        return s[i + 1 : j], j + 1
                j += 1
            raise ParseError("Klammern { } stimmen nicht")
        return (s[i], i + 1) if i < len(s) else ("", i)

    out, i = [], 0
    while i < len(s):
        if s.startswith(r"\frac", i) or s.startswith(r"\dfrac", i) or s.startswith(r"\tfrac", i):
            i += 5 if s.startswith(r"\frac", i) else 6
            a, i = group(i)
            b, i = group(i)
            out.append(f"(({_latex_to_ascii(a)})/({_latex_to_ascii(b)}))")
        elif s.startswith(r"\sqrt", i):
            i += 5
            n = None
            if i < len(s) and s[i] == "[":
                j = s.index("]", i)
                n, i = s[i + 1 : j], j + 1
            a, i = group(i)
            a = _latex_to_ascii(a)
            out.append(f"root(({a}),({n}))" if n else f"sqrt({a})")
        elif s[i] in "^_" and i + 1 < len(s) and s[i + 1] == "{":
            op = s[i]
            a, i = group(i + 1)
            if op == "^":
                out.append(f"**({_latex_to_ascii(a)})")
            else:
                out.append(f"_{re.sub(r'[^A-Za-z0-9]', '', a)}")
        elif s[i] == "{":
            out.append("(")
            i += 1
        elif s[i] == "}":
            out.append(")")
            i += 1
        elif s[i] == "\\":
            m = re.match(r"\\([A-Za-z]+)", s[i:])
            if m:
                out.append(" " + m.group(1) + " ")
                i += len(m.group(0))
            else:
                i += 1
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def _normalise(raw: str) -> str:
    s = (raw or "").strip()
    s = _latex_to_ascii(s)
    table = {
        "−": "-", "–": "-", "⋅": "*", "·": "*", "×": "*", "÷": "/", "π": "pi", "√": "sqrt",
        "²": "^2", "³": "^3", "∞": "oo", "e^": "E^", "\u2009": "", "\u00a0": " ",
    }
    for a, b in table.items():
        s = s.replace(a, b)
    s = re.sub(r"\bE\^", "E^", s)
    # Euler e as a lone letter (e.g. "2e^x", "e*3") -> E. Not inside words (sec, exp...).
    s = re.sub(r"(?<![A-Za-z_])e(?![A-Za-z_])", "E", s)
    # imaginary j or i as a lone letter -> I
    s = re.sub(r"(?<![A-Za-z_])[ij](?![A-Za-z_])", "I", s)
    # decimal comma between digits (only used when not a list, the caller splits lists first)
    s = re.sub(r"(\d),(\d)", r"\1.\2", s)
    # drop "y =", "f(x) =", "x_1 =" etc. on the left side
    if "=" in s:
        s = s.split("=")[-1]
    s = s.replace("°", "")
    # |x| -> Abs(x) (simple, non nested)
    s = re.sub(r"\|([^|]+)\|", r"Abs(\1)", s)
    return s.strip()


def parse(raw: str, var_names: tuple[str, ...] = ("x",), unit: str | None = None) -> sp.Expr:
    s = _normalise(raw)
    if unit:
        u = unit.replace("^", "").replace("²", "2").replace("³", "3")
        s2 = s.replace("**", "^")
        for cand in {unit, u, unit.replace("^", "**")}:
            if cand and s2.rstrip().endswith(cand):
                s = s2[: -len(cand)].replace("^", "**")
                break
    if not s:
        raise ParseError("Leere Eingabe")
    local = dict(FUNCS)
    for v in var_names:
        local[v] = sp.Symbol(v)
    # "gT" or "ab" typed without "*": split a name into a product when every letter is a declared variable
    single = {v for v in var_names if len(v) == 1}
    if single:
        def _split_name(m):
            w = m.group(0)
            if w in local or hasattr(sp, w) or len(w) < 2 or not all(ch in single or ch in "eE" for ch in w):
                return w
            return "*".join("E" if ch in "eE" and ch not in single else ch for ch in w)
        s = re.sub(r"(?<![A-Za-z_])[A-Za-z]+(?![A-Za-z_(])", _split_name, s)
    # any other bare names become symbols too (t, a, r, …)
    for name in set(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", s)):
        if name not in local and not hasattr(sp, name):
            local[name] = sp.Symbol(name)
    try:
        return parse_expr(s, local_dict=local, transformations=TRANSFORMS, evaluate=True)
    except Exception as e:  # noqa: BLE001
        raise ParseError(f"Eingabe nicht lesbar: {raw!r}") from e


def parse_expected(v, var_names=("x",)) -> sp.Expr:
    if isinstance(v, (int, float)):
        return sp.nsimplify(v) if isinstance(v, int) else sp.Float(v)
    return parse(str(v), var_names)


def _num(e: sp.Expr) -> complex:
    return complex(sp.N(e, 30))


def _close(a: complex, b: complex, tol: float | None, rel: float | None) -> bool:
    d = abs(a - b)
    if tol is not None:
        return d <= tol + 1e-12
    r = 0.005 if rel is None else rel
    return d <= max(r * abs(b), 1e-9)


def _strip_enclosing(s: str) -> str:
    """Remove bracket pairs that enclose the whole input, e.g. "(1; sqrt(2))" -> "1; sqrt(2)".
    Brackets that belong to an item ("1; sqrt(3)") stay untouched."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    while len(s) >= 2 and s[0] in pairs and s[-1] == pairs[s[0]]:
        depth = 0
        for i, ch in enumerate(s):
            if ch in pairs:
                depth += 1
            elif ch in pairs.values():
                depth -= 1
                if depth == 0 and i != len(s) - 1:
                    return s  # the first bracket closes before the end: not enclosing
        s = s[1:-1].strip()
    return s


def _split_list(raw: str) -> list[str]:
    s = raw.strip()
    if "\\begin" in s:
        s = re.sub(r"\\(begin|end)\{[a-zA-Z*]*\}", "", s)
        s = s.replace("\\\\", ";").replace("&", ";")
    s = s.replace("\\left", "").replace("\\right", "").replace("\\mid", "|").replace("\\vert", "|")
    s = s.replace("\\{", "{").replace("\\}", "}")
    # "P(2|3)", "L = {1; 2}", "x = (1, 2)": drop a leading name before the enclosing bracket
    s = re.sub(r"^\s*(?:[A-Za-z]\w*(?:_\{?\w+\}?)?\s*=\s*|[A-Z](?:_\{?\w+\}?)?\s*(?=[(\[]))(?=[({\[])", "", s).strip()
    s = _strip_enclosing(s)
    if ";" in s:
        parts = s.split(";")
    elif "\\\\" in s:
        parts = s.split("\\\\")
    elif "|" in s and "Abs" not in s:
        parts = s.split("|")
    else:
        parts = s.split(",")
    parts = [p.strip() for p in parts]
    parts = [re.sub(r"^\s*[A-Za-z]\w*(_\{?\w+\}?)?\s*=\s*", "", p) for p in parts]
    return [p for p in parts if p and p.lower() not in ("und", "oder")]


@dataclass
class Result:
    ok: bool
    status: str  # "richtig" | "falsch" | "format" | "manuell" | "fast"
    message: str
    parsed: str | None = None
    details: dict = field(default_factory=dict)

    def as_dict(self):
        return {"ok": self.ok, "status": self.status, "message": self.message, "parsed": self.parsed, **self.details}


def _expr_equal(student: sp.Expr, expected: sp.Expr, syms: list[sp.Symbol], up_to_constant=False, rel=None) -> bool:
    diff = student - expected
    if not up_to_constant:
        try:
            if sp.simplify(diff) == 0:
                return True
        except Exception:  # noqa: BLE001
            pass
    # numeric sampling at random points (works for decimals, trig identities, etc.)
    free = sorted(student.free_symbols | expected.free_symbols, key=str)
    rnd = random.Random(42)
    good, tried = 0, 0
    ref = None
    for _ in range(40):
        pt = {s: sp.Float(rnd.uniform(0.3, 2.7)) for s in free}
        try:
            a, b = _num(student.subs(pt)), _num(expected.subs(pt))
        except Exception:  # noqa: BLE001
            continue
        if any(map(lambda z: z != z or abs(z) == float("inf"), (a, b))):
            continue
        tried += 1
        if up_to_constant:
            c = a - b
            if ref is None:
                ref = c
                good += 1
                continue
            if abs(c - ref) <= max((rel or 1e-6) * max(abs(a), abs(b), 1), 1e-8):
                good += 1
            else:
                return False
        else:
            if abs(a - b) <= max((rel or 1e-7) * max(abs(b), 1), 1e-9):
                good += 1
            else:
                return False
        if tried >= 8:
            break
    return tried >= 3 and good == tried


def check(answer: dict, raw, skills: list[str] | None = None) -> Result:
    """Compare a student's raw input to an answer spec from the exercise JSON."""
    t = answer.get("type")
    tol, rel = answer.get("tol"), answer.get("rel")
    unit = answer.get("unit")
    if t == "text":
        return Result(False, "manuell", "Wird vom Tutor beurteilt.")
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return Result(False, "format", "Bitte gib eine Antwort ein.")
    try:
        if t == "choice":
            ok = int(raw) == int(answer["value"])
            return Result(ok, "richtig" if ok else "falsch", "Richtig!" if ok else "Leider nicht richtig.")

        if t == "expr":
            var = answer.get("var", "x")
            vars_ = tuple(v.strip() for v in var.split(",")) if isinstance(var, str) else tuple(var)
            exp = parse_expected(answer["value"], vars_)
            stu = parse(str(raw), vars_)
            syms = [sp.Symbol(v) for v in vars_]
            upc = bool(answer.get("up_to_constant")) or bool(skills and skills[0] == "int-stammfunktion")
            if sp.Symbol("C") in stu.free_symbols and sp.Symbol("C") not in exp.free_symbols:
                upc = True
            if upc:
                stu = stu.subs(sp.Symbol("C"), 0)
            extra = {str(s) for s in stu.free_symbols} - {str(s) for s in exp.free_symbols} - set(vars_)
            if extra:
                return Result(False, "falsch", f"Deine Antwort enthält unerwartete Variablen: {', '.join(sorted(extra))}.", parsed=sp.sstr(stu))
            ok = _expr_equal(stu, exp, syms, up_to_constant=upc, rel=rel)
            if ok:
                return Result(True, "richtig", "Richtig!", parsed=sp.sstr(stu))
            return Result(False, "falsch", "Das stimmt noch nicht.", parsed=sp.sstr(stu))

        if t == "number":
            exp = _num(parse_expected(answer["value"]))
            stu_e = parse(str(raw), (), unit)
            if stu_e.free_symbols:
                return Result(False, "format", "Bitte gib eine Zahl ein (ohne Variablen).", parsed=sp.sstr(stu_e))
            stu = _num(stu_e)
            if _close(stu, exp, tol, rel):
                return Result(True, "richtig", "Richtig!", parsed=_fmt(stu))
            if _close(stu, exp, None, 0.03):
                return Result(False, "fast", "Knapp daneben – prüfe Rundung und Zwischenresultate.", parsed=_fmt(stu))
            if _close(-stu, exp, tol, rel):
                return Result(False, "falsch", "Fast: Vorzeichen prüfen!", parsed=_fmt(stu), details={"hint_tag": "vorzeichen"})
            return Result(False, "falsch", "Das stimmt noch nicht.", parsed=_fmt(stu))

        if t in ("set", "tuple"):
            items = raw if isinstance(raw, list) else _split_list(str(raw))
            exp = [_num(parse_expected(v)) for v in answer["value"]]
            stu = []
            for it in items:
                e = parse(str(it), (), unit)
                if e.free_symbols:
                    return Result(False, "format", "Bitte nur Zahlen eingeben.")
                stu.append(_num(e))
            parsed = "; ".join(_fmt(z) for z in stu)
            if len(stu) != len(exp):
                msg = f"Erwartet werden {len(exp)} Werte, du hast {len(stu)} angegeben."
                return Result(False, "falsch", msg, parsed=parsed)
            if t == "tuple":
                wrong = [i for i, (a, b) in enumerate(zip(stu, exp)) if not _close(a, b, tol, rel)]
                if not wrong:
                    return Result(True, "richtig", "Richtig!", parsed=parsed)
                names = answer.get("names")
                which = ", ".join(names[i] if names and i < len(names) else f"Komponente {i + 1}" for i in wrong)
                return Result(False, "falsch", f"Nicht korrekt: {which}.", parsed=parsed, details={"wrong": wrong})
            remaining = list(exp)
            for a in stu:
                m = next((b for b in remaining if _close(a, b, tol, rel)), None)
                if m is None:
                    return Result(False, "falsch", "Mindestens ein Wert stimmt nicht.", parsed=parsed)
                remaining.remove(m)
            return Result(True, "richtig", "Richtig!", parsed=parsed)
    except ParseError as e:
        return Result(False, "format", str(e) + " Tipp: Schreibe z.B. 3*x^2 - 2 oder sqrt(2)/2.")
    except Exception as e:  # noqa: BLE001
        return Result(False, "format", f"Konnte die Eingabe nicht auswerten ({type(e).__name__}).")
    return Result(False, "format", f"Unbekannter Antworttyp {t}")


def _fmt(z: complex) -> str:
    if abs(z.imag) < 1e-12:
        x = z.real
        return f"{x:.6g}"
    return f"{z.real:.6g}{z.imag:+.6g}i"


def describe_expected(answer: dict) -> str:
    """Human readable (plain text) expected answer, for solutions and the admin view."""
    t = answer.get("type")
    v = answer.get("value")
    if t in ("set", "tuple"):
        return "; ".join(map(str, v))
    if t == "choice":
        opts = answer.get("options", [])
        return opts[v] if isinstance(v, int) and v < len(opts) else str(v)
    return f"{v} {answer.get('unit', '')}".strip()
