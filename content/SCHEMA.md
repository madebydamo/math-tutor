# Content format

All learner-facing text is **German (Swiss spelling: "ss" instead of "ß")**. Math is LaTeX inside `$…$` (inline) or `$$…$$` (display), rendered with KaTeX.

## Exercises: `content/exercises/<source-slug>.json`

A JSON array of exercises:

```json
{
  "id": "rt01-a2",
  "source": {"doc": "Reptest 1 Polynomfunktionen", "ref": "Aufgabe 2"},
  "chapter": "k1",
  "skills": ["poly-produktform"],
  "title": "Polynomfunktion in Produktform",
  "calculator": "ohne",
  "difficulty": 2,
  "minutes": 6,
  "statement": "Bestimme die Funktionsgleichung der Polynomfunktion in Produktform, wenn die Nullstellen $x_1=1$, $x_2=-1$, $x_3=6$ gegeben sind und der Punkt $P(2\\mid 36)$ auf dem Graphen liegt.",
  "figures": ["rt01-a2-1.png"],
  "parts": [
    {
      "label": "",
      "prompt": "Funktionsgleichung $y(x)=\\,?$",
      "answer": {"type": "expr", "value": "-3*(x-1)*(x+1)*(x-6)", "var": "x"},
      "solution": "Ansatz: $y=a(x-1)(x+1)(x-6)$. $P(2\\mid36)$ einsetzen: $36=a\\cdot1\\cdot3\\cdot(-4)=-12a \\Rightarrow a=-3$.\n\n$$y=-3(x-1)(x+1)(x-6)$$",
      "hints": [
        "Wie sieht der Ansatz in Produktform aus, wenn du die Nullstellen kennst?",
        "Ansatz $y=a(x-1)(x+1)(x-6)$ – der Faktor $a$ fehlt noch. Was weisst du über den Punkt $P$?",
        "Setze $x=2$ und $y=36$ ein und löse nach $a$ auf."
      ]
    }
  ],
  "verified": true
}
```

Fields:

- `id`: unique, lowercase, `[a-z0-9-]`. Prefix per source (see the prompt you were given).
- `chapter`: `k1`…`k6`. `skills`: 1–3 ids from `content/curriculum.json` (first = main skill).
- `calculator`: `"ohne"` (by hand) or `"mit"` (calculator needed). Use what the source says; otherwise judge.
- `difficulty`: 1 (Grundlagen) · 2 (Prüfungsniveau) · 3 (anspruchsvoll).
- `minutes`: realistic time for a student.
- `statement`: the shared task text. `figures`: file names in `content/figures/` (PNG/JPG) that the task needs (graphs, sketches, tables as image). Only figures that are needed to solve or understand the task.
- `parts`: one per sub-question (a, b, c…). Single-question tasks have one part with `label: ""`.
  - `prompt`: what is asked in this part.
  - `answer`: how the final result is checked automatically:

| type | value | extra keys | checked as |
|------|-------|-----------|------------|
| `expr` | SymPy string, e.g. `"0.25*(x+3)*(x+1)*(x-2)"`, `"3*cos(3*x)"` | `var` (default `x`) | symbolic / numeric equivalence |
| `number` | SymPy string or decimal: `"sqrt(2)/2"`, `"12.57"` | `tol` (absolute) or `rel` (relative, default 0.005 = 0.5 %), `unit` (text, e.g. `"cm^3"`) | numeric within tolerance |
| `set` | list of SymPy strings: `["0","5","-2"]` | `tol`/`rel` | same numbers, any order |
| `tuple` | list, ordered: vectors `["1","-2","3"]`, points `["2","-3"]`, parameters `["2","3","1"]` | `tol`/`rel`, `names` (e.g. `["a","b","c"]`) | component-wise |
| `choice` | index of the correct option (int) | `options`: list of strings | exact |
| `text` | short model answer | — | graded by the AI tutor against `solution` (sketches, explanations, proofs, "skizziere", "begründe") |

  Prefer a checkable type. Use `text` only when the result really is a sketch, explanation or description.
  SymPy names: `sqrt`, `pi`, `E` (Euler) or `exp(…)`, `log` (= ln), `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `I` (imaginary unit), `**` for powers. Angles in degrees: give the number in degrees and write `"unit": "°"`.
  - `solution`: complete worked solution (Lösungsweg) in German with LaTeX, step by step, as a teacher would write it. Include the calculator commands (TI style: `solve(…, x)`, `factor(…)`) where the original does.
  - `hints`: exactly 3 hints, from gentle nudge → method → concrete next step. Never give the final answer in a hint.
- `verified`: `true` only if you checked the final answer yourself with SymPy/NumPy (see below). If the source solution and your check disagree, trust a careful recomputation, and add `"note": "Quelle gibt … an; korrigiert"`.

## Theory: `content/theory/<chapter>.md`

One file per chapter (`k1.md` … `k6.md`). Markdown with LaTeX. For each Skript section (1.1, 1.2, …): `## 1.2 Polynomfunktion` heading, a short, clear explanation (what, why, how), the key formulas, one fully worked example, and typical mistakes ("Typische Fehler"). Aim for what a student needs to understand the topic in 10 minutes per section. Cite the Skript section numbers.

## Formelsammlung: `content/formeln/<chapter>.md`

Compact: only formulas and rules, grouped by topic with `###` headings, each as a short line or table. Include calculator commands where the course uses them.

## Formula cards: `content/formula-cards/<chapter>.json`

For the formula trainer (flashcards + quick recall) and the "Formeln zu dieser Aufgabe" drawer in exercises. A JSON array:

```json
{
  "id": "k4-kettenregel",
  "chapter": "k4",
  "skills": ["diff-kettenregel"],
  "topic": "Ableitungsregeln",
  "name": "Kettenregel",
  "formula": "$$\\big(f(g(x))\\big)' = f'(g(x))\\cdot g'(x)$$",
  "explain": "Äussere Ableitung (Inneres stehen lassen) mal innere Ableitung.",
  "example": "$(\\sin(3x^2))' = \\cos(3x^2)\\cdot 6x$",
  "pitfall": "Die innere Ableitung vergessen.",
  "drill": [
    {"prompt": "$\\frac{d}{dx}\\,e^{5x}=\;?$", "answer": {"type": "expr", "value": "5*exp(5*x)"}},
    {"prompt": "$\\frac{d}{dx}\\,(2x+1)^3=\;?$", "answer": {"type": "expr", "value": "6*(2*x+1)**2"}}
  ]
}
```

- `formula`: the formula itself (LaTeX), as on a Formelsammlung. `name` short. `topic` groups cards.
- `explain`: one or two sentences in plain German, when/how to use it. `example`: one worked mini example. `pitfall`: the most common mistake (optional).
- `drill`: 2–4 quick recall questions solvable in under a minute, with checkable answers (same answer spec as exercises; never `text`). Verify every drill answer with SymPy.

## Solution steps (`parts[].steps`)

Every part has, next to `solution`, a list `steps`: the worked solution with **one mathematical step per entry**, shown line by line, each with a «Frage zu diesem Schritt» button.

```json
"steps": [
  {"note": "Ansatz in Produktform (Nullstellen bekannt)", "math": "y = a\\,(x-1)(x+1)(x-6)"},
  {"note": "Punkt $P(2\\mid 36)$ einsetzen (Satz von Anan)", "math": "36 = a\\cdot(2-1)(2+1)(2-6)"},
  {"note": "Klammern ausrechnen", "math": "36 = a\\cdot 1\\cdot 3\\cdot(-4) = -12a"},
  {"note": "durch $-12$ teilen", "math": "a = -3"},
  {"note": "Resultat", "math": "y = -3\\,(x-1)(x+1)(x-6)", "result": true}
]
```

- `math`: exactly **one** line of LaTeX (no `$`), one transformation. Do not chain several transformations in one line (split `a = b \Rightarrow c = d` into two steps). A short chain of plain equalities that belong together (`= 1\cdot3\cdot(-4) = -12a`) is fine.
- `note`: short German explanation of what happens in this step (plain text, inline `$…$` allowed). Can be empty. A step may also have only a `note` (a sentence without formula, e.g. «Der Graph berührt die x-Achse bei $x=2$.»), or a `calc` field with a calculator command (e.g. `solve(x^3-4x=0, x)`).
- `result: true` on the final answer step(s).
- `rule` / `rule_formula` / `card` (optional): when a step applies a rule or formula: its short name («Kettenregel»), the general formula (LaTeX, no `$`) and the id of the matching formula card. Shown as a chip on the step.
- Every step must be mathematically correct and follow from the previous one.
