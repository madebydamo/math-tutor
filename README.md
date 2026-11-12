# Mathe-Trainer

A personal maths coach for one student and their coach. It started as exam prep for the Swiss HF module "Mathematik II" (polynomials, trigonometry and oscillations, exponential functions, differential and integral calculus, vectors). The engine is course-agnostic, so you can fork it for any maths course. The UI and the tutor are in German.

It is built for **accuracy**. An AI tutor explains, gives hints and corrects photos of handwritten work, but whether a final answer is right is always decided by a SymPy-based checker, never by the language model.

It ships as a plugin for **[Neo](https://github.com/madebydamo/neo)**, a NixOS homeserver, and also runs on its own with Python (see [Run without Neo](#run-without-neo)).

---

## Features

**For the student**
- Dashboard with progress over time and KPIs: streak, accuracy trend, an "exam-ready" score, a daily goal, three daily missions, combos and medals.
- Ranks from Rekrut to Oberstleutnant (Swiss civil-protection ranks) with an optional avatar that changes with the rank. Promotion needs XP **and** proven mastery.
- Exercise player with a maths keyboard (MathLive) and three graded hints per sub-task.
- Animated step-by-step solutions: one transformation per line, the applied rule shown as a chip (📐 *Kettenregel*), and a 💬 button per step that asks the tutor about exactly that step.
- Photo correction of handwritten work: the tutor transcribes the page, checks every line, names the first error and its category, and the checker confirms the final results.
- **Revanche**: failed exercises come back after 1, 3 and 7 days until solved twice in a row.
- Exam simulation with a timer, typed answers plus photographed working, graded to exam standard.
- Tutor chat with voice input (browser speech recognition), camera, interactive plots with sliders (JSXGraph) and drawings made with Python.
- Formula collection (chapter → topic → card, every symbol defined, printable), formula trainer (flashcards with spaced repetition, quick drill, 60-second sprint) and optional basics chapters (fractions, powers, equations, triangle trigonometry, …).
- "Fehler melden" on every exercise, and a feedback button on every page that records a screenshot, the current page, recent errors and the app version.

**For the coach** (`/admin`)
- A skill heatmap, the weakest topics with their error types and the student's actual inputs, and a teacher view of every failed exercise with its solution.
- A printable session briefing with an optional AI analysis, plus a session mode, assignments, history with grade overrides, the student's tutor chats and a coach assistant.
- Error reports and feedback with screenshots and a "copy for developer" export. Exercises can be taken out of rotation.
- Telegram messages: daily summary, struggle alerts, session reminders and promotions.

## How it works

| Part | What it does |
|------|--------------|
| `app/mathtutor/checker.py` | Parses student input (LaTeX from MathLive, ASCII, `x^2`, `\frac{}{}`, `(2\|3)`, `L={…}`, …) and compares it with the expected answer: symbolic or numeric equivalence, tolerances, sets, tuples, choices |
| `app/mathtutor/generators*.py` | About 100 parameterised exercise generators. The numbers and solutions are computed with SymPy, so the supply of correct exercises is unlimited |
| `app/mathtutor/progress.py`, `engage.py` | Mastery per skill, XP, ranks, Revanche scheduling, missions, medals and formula-card repetition |
| `app/mathtutor/tutor.py`, `agent_server.py`, `mcp_math.py` | The AI tutor. The web app sends one turn to an agent container, which runs **Claude Code** headless (`claude -p`) with only maths tools (Python/SymPy sandbox, answer checker, plot validator, structured correction). There is no shell, no file access and no network access to other services |
| `app/mathtutor/static/` | No-build frontend (Preact + htm, KaTeX, MathLive, JSXGraph, math.js); all libraries are vendored |
| `content/` | Curriculum, formula cards, theory and the formula sheet as Markdown/JSON (format in [`content/SCHEMA.md`](content/SCHEMA.md)) |
| `modules/` | The Neo plugin (Nix): options, containers, reverse proxy, secrets, Hermes skill; the image is built with nix2container |

Everything lives in one SQLite database plus a photo folder in the data directory.

## What is (not) in this repository

The repository contains the code, the curriculum, all generators, the formula cards and the basics chapters, all written for this project.

The **course material itself is not included**: exercises transcribed from the course's exercise collection and tests, their figures, the practice exams, and the theory and formula sheets derived from the course script. That material belongs to its author.

To use the app with your own course, add your material in the formats below. On the server it goes into the data directory (`<data>/content`), not into git (see [Bring your own course](#bring-your-own-course)).

Without any course material the app still works: every chapter has generated exercises, and the formula cards and basics are included.

## Install on Neo

`settings.toml` on the homeserver:

```toml
[core.plugins.mathtutor]
url = "github:madebydamo/math-tutor"

[services.mathtutor]
enabled = true
studentUser = "<login of the student>"   # a tinyauth user
studentName = "<First name>"             # optional, used by the app and the tutor
adminUsers = ["<your login>"]            # coaches: see /admin
agentToken = "…"                         # web UI → Generate (internal secret between app and tutor)
claudeToken = "…"                        # `claude setup-token` (Claude subscription) …
# anthropicApiKey = "sk-ant-…"           # … or an API key
# model = "claude-opus-5-5"              # default
# telegramBotToken / telegramChatId      # default: the Hermes Telegram bot and its first user
```

Then:

1. Add a tinyauth user for the student, and optionally restrict them to this app: `[services.tinyauth.access.<user>] allow = ["mathtutor"]`.
2. Activate. The site is `https://mathe.<domain>` and the coach dashboard is `https://mathe.<domain>/admin`.
3. Optional: copy your course material to `<appdata>/mathtutor/app/content/` and the avatar images to `<appdata>/mathtutor/app/avatar/`, then restart `docker-mathtutor`.

**Tutor sign-in:** set `claudeToken` (created with `claude setup-token`) or `anthropicApiKey`. Alternatively, run `docker exec -it mathtutor-agent claude` and `/login` once; the login is kept in appdata.

## Run without Neo

```bash
nix build .#mathtutor-python            # or any Python ≥ 3.11 with: fastapi uvicorn httpx python-multipart pillow mcp sympy numpy scipy matplotlib
export PYTHONPATH=$PWD/app MT_DATA_DIR=$PWD/data MT_AGENT_TOKEN=change-me-1234567890
export MT_DEV_USER=student MT_STUDENT_USER=student MT_ADMIN_USERS=coach   # dev only: no login in front
python -m mathtutor.agent_server &      # tutor; uses the Claude Code login of this machine
python -m mathtutor.main                # http://localhost:8080
```

`/dev/as/<name>` switches the user in dev mode (e.g. `/dev/as/coach` opens the dashboard). In production, put a reverse proxy with authentication in front of it that sets the `Remote-User` header (tinyauth, Authelia, oauth2-proxy, …), and never set `MT_DEV_USER`.

The Docker image (`nix build .#mathtutor-image`) runs the web app with `MT_ROLE=app` and the tutor with `MT_ROLE=agent`. Put the agent on its own network that only the app can reach.

| Variable | Meaning |
|----------|---------|
| `MT_STUDENT_USER`, `MT_STUDENT_NAME` | Login and first name of the student |
| `MT_ADMIN_USERS` | Comma-separated coach logins |
| `MT_DATA_DIR` | SQLite, photos, `content/` (course material) and `avatar/` |
| `MT_AGENT_URL`, `MT_AGENT_TOKEN` | Where the tutor runs and the shared secret |
| `MT_MODEL` | Claude model for the tutor |
| `MT_TELEGRAM_TOKEN`, `MT_TELEGRAM_CHAT` | Coach notifications |
| `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` | Tutor sign-in (agent container) |

## Bring your own course

1. **Curriculum:** edit `content/curriculum.json`: chapters, skills (the unit of mastery) and error categories. Chapters with `"optional": true` are practice-only and don't count for ranks.
2. **Exercises:** add `content/exercises/*.json` as described in [`content/SCHEMA.md`](content/SCHEMA.md). Each exercise has parts with a checkable answer spec (`expr`, `number`, `set`, `tuple`, `choice`, or `text` for sketches), three hints, a worked solution and a `steps` list for the animated solution.
3. **Check it:** `python -I content/tools/validate.py --require-steps` validates the structure and parses every answer with SymPy. `node content/tools/katexcheck.js` renders every formula with the app's KaTeX.
4. **Theory, formula sheet, cards:** `content/theory/<chapter>.md`, `content/formeln/<chapter>.md` and `content/formula-cards/<chapter>.json`.
5. **Exams:** `content/exams.json` lists timed simulations made of exercise ids.
6. **Generators:** add a function with `@gen(...)` in `app/mathtutor/generators.py` that builds an exercise with SymPy. Every generator must pass its own expected answer through the checker for many seeds; test that before you add it.

**Transcribing printed material:** the original content was transcribed from PDFs with AI agents, page images included. Every answer was then recomputed with SymPy, which caught a dozen errors in the source solutions; these are kept as `note` fields. If you do the same, keep the "recompute every answer" step.

## Avatar

Put twelve PNGs named after the ranks (`rekrut, sdt, gfr, kpl, wm, four, hptfw, lt, oblt, hptm, maj, oberstlt`) with transparent backgrounds into `<data>/avatar/`. Any image generator works if you describe one consistent character and change only outfit and props per rank. Images with a personal likeness belong in the data directory, not in git.

## Development

```bash
nix fmt && nix flake check                                # format, flake checks
nix build .#checks.x86_64-linux.neo-plugin-instances      # the plugin can be added twice (prefixes)
nix build .#mathtutor-image                               # OCI image
```

Development rules for the Neo plugin are in [`AGENTS.md`](AGENTS.md).

## License

MIT, see [LICENSE](LICENSE). Vendored libraries keep their own licenses (KaTeX MIT, MathLive MIT, JSXGraph LGPL/MIT, math.js Apache-2.0, Preact/htm MIT, marked MIT, DOMPurify Apache-2.0/MPL, html2canvas MIT). The rank insignia images come from Annex 1 of the Bernese Zivilschutzverordnung (BSG 521.11).
