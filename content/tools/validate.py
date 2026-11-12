#!/usr/bin/env python3
"""Validate content/exercises/*.json against content/SCHEMA.md.

Usage: python validate.py [file.json ...]   (default: all exercise files)
Exit code 1 on errors. Prints one line per problem.
"""
import json
import pathlib
import re
import sys

import sympy as sp

ROOT = pathlib.Path(__file__).resolve().parents[1]
CUR = json.loads((ROOT / "curriculum.json").read_text())
SKILLS = {s["id"]: c["id"] for c in CUR["chapters"] for s in c["skills"]}
TYPES = {"expr", "number", "set", "tuple", "choice", "text"}
NS = {"E": sp.E, "I": sp.I, "pi": sp.pi, "e": sp.E}


def parse(s, var="x"):
    if isinstance(s, (int, float)):
        return sp.Float(s)
    s = str(s).replace("^", "**").replace("π", "pi").replace("√", "sqrt")
    syms = {v: sp.Symbol(v) for v in re.findall(r"[A-Za-z_]\w*", s) if v not in dir(sp) and v not in NS}
    return sp.sympify(s, locals={**syms, **NS})


def check_file(path, seen):
    errs = []
    try:
        data = json.loads(path.read_text())
    except Exception as e:  # noqa: BLE001
        return [f"{path.name}: invalid JSON: {e}"]
    if not isinstance(data, list):
        return [f"{path.name}: top level must be a list"]
    for ex in data:
        eid = ex.get("id", "?")
        p = f"{path.name}:{eid}"
        if not re.fullmatch(r"[a-z0-9-]+", str(eid)):
            errs.append(f"{p}: bad id")
        if eid in seen:
            errs.append(f"{p}: duplicate id (also in {seen[eid]})")
        seen[eid] = path.name
        for k in ("source", "chapter", "skills", "title", "calculator", "difficulty", "statement", "parts"):
            if k not in ex:
                errs.append(f"{p}: missing {k}")
        if ex.get("chapter") not in {c["id"] for c in CUR["chapters"]}:
            errs.append(f"{p}: bad chapter {ex.get('chapter')}")
        for s in ex.get("skills", []):
            if s not in SKILLS:
                errs.append(f"{p}: unknown skill {s}")
        if ex.get("calculator") not in ("ohne", "mit"):
            errs.append(f"{p}: calculator must be ohne|mit")
        for f in ex.get("figures", []) or []:
            if not (ROOT / "figures" / f).exists():
                errs.append(f"{p}: missing figure {f}")
        for i, part in enumerate(ex.get("parts", [])):
            pp = f"{p}[{part.get('label') or i}]"
            a = part.get("answer") or {}
            t = a.get("type")
            if t not in TYPES:
                errs.append(f"{pp}: bad answer type {t}")
                continue
            if not part.get("solution"):
                errs.append(f"{pp}: missing solution")
            steps = part.get("steps")
            if steps is not None:
                if not isinstance(steps, list) or not steps:
                    errs.append(f"{pp}: steps must be a non-empty list")
                else:
                    for k, st in enumerate(steps):
                        if not isinstance(st, dict) or not (st.get("math") or st.get("note") or st.get("calc")):
                            errs.append(f"{pp}: step {k + 1} empty")
                        elif "$" in (st.get("math") or ""):
                            errs.append(f"{pp}: step {k + 1} math must not contain $")
                        elif (st.get("math") or "").count("{") != (st.get("math") or "").count("}"):
                            errs.append(f"{pp}: step {k + 1} unbalanced braces")
                    if not any(st.get("result") for st in steps if isinstance(st, dict)):
                        errs.append(f"{pp}: no step marked result")
            elif "--require-steps" in sys.argv:
                errs.append(f"{pp}: missing steps")
            if len(part.get("hints", [])) != 3:
                errs.append(f"{pp}: need exactly 3 hints")
            try:
                v = a.get("value")
                if t == "expr":
                    parse(v, a.get("var", "x"))
                elif t == "number":
                    complex(sp.N(parse(v)))
                elif t in ("set", "tuple"):
                    assert isinstance(v, list) and v, "value must be a non-empty list"
                    for x in v:
                        complex(sp.N(parse(x)))
                elif t == "choice":
                    assert isinstance(v, int) and 0 <= v < len(a.get("options", [])), "choice index/options"
                elif t == "text":
                    assert isinstance(v, str) and v, "text needs a model answer"
            except Exception as e:  # noqa: BLE001
                errs.append(f"{pp}: answer does not parse: {e!r} (value={a.get('value')!r})")
    return errs


def main():
    files = [pathlib.Path(f) for f in sys.argv[1:] if not f.startswith("--")] or sorted((ROOT / "exercises").glob("*.json"))
    seen, errs, n = {}, [], 0
    for f in files:
        errs += check_file(f, seen)
        try:
            n += len(json.loads(f.read_text()))
        except Exception:  # noqa: BLE001
            pass
    for e in errs:
        print(e)
    print(f"{len(files)} files, {n} exercises, {len(errs)} problems")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
