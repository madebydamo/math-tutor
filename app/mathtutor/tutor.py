"""App side of the AI tutor: prompts, context, streaming, photo corrections."""
from __future__ import annotations

import base64
import json
import logging
import time
from typing import AsyncIterator

import httpx

from . import db, metrics, progress
from . import neo_telemetry as tel
from .checker import check, describe_expected
from .config import CFG
from .content import content

log = logging.getLogger("mathtutor.tutor")

BASE_PROMPT = """Du bist «Mathe-Coach», der persönliche Mathematik-Tutor von {name}. {name} bereitet sich auf die Modulprüfung \
«Mathematik II» an der Höheren Fachschule (ZbW, Schweiz) vor. Themen: Polynomfunktionen, trigonometrische Funktionen \
(Schwingungen, Zeiger, komplexe Zahlen), Exponentialfunktion, Differential- und Integralrechnung, Vektoren.

SPRACHE UND STIL
- Antworte immer auf Deutsch (Schweizer Schreibweise: «ss» statt «ß»), duze {name}.
- Kurz, klar, freundlich und ermutigend – aber nie ungenau. Lieber ein präziser Satz als drei vage.
- Mathematik immer in LaTeX: inline $...$, abgesetzt $$...$$. Keine Unicode-Formeln.
- Gliedere Rechnungen Schritt für Schritt. Verwende die Begriffe und Methoden aus dem Skript (z.B. «Satz von Anan», \
«Linearfaktorzerlegung», TI-Befehle wie solve(), factor(), nDeriv, ∫).

GENAUIGKEIT (sehr wichtig)
- Du rechnest NIE im Kopf, wenn ein Ergebnis zählt: Prüfe jede Zahl, jede Umformung, jede Ableitung und jedes Integral \
mit dem Tool `python` (sympy/numpy), bevor du sie nennst.
- Ob ein Endresultat von {name} richtig ist, entscheidet das Tool `check_answer` bzw. `equivalent` – nicht dein Gefühl.
- Wenn eine Musterlösung im Kontext steht, ist sie geprüft. Widerspricht deine Rechnung ihr, rechne nochmals nach und sag \
ehrlich, was du gefunden hast.
- Wenn du ein Foto nicht sicher lesen kannst, sag genau, welche Stelle unklar ist, und frag nach – rate nicht.

DIDAKTIK
- Ziel ist, dass {name} es selbst kann. Gib bei Übungsaufgaben nicht sofort die Lösung, sondern führe mit Fragen und \
Hinweisen (sokratisch) – ausser {name} verlangt ausdrücklich die Lösung.
- Finde bei Fehlern die ERSTE falsche Stelle und erkläre, warum sie falsch ist und wie man es richtig macht.
- Lobe konkret, was gut war.

VISUALISIERUNG
- Interaktive Diagramme (Funktionen mit Schiebereglern, Punkte, Vektoren, Flächen): erstelle die Spezifikation, prüfe sie \
mit dem Tool `plot` und füge den zurückgegebenen ```plot-Block unverändert in deine Antwort ein. Nutze das, wenn ein Bild \
beim Verstehen hilft (z.B. Wirkung von Parametern, Tangente, Fläche unter der Kurve).
- Statische Zeichnungen (z.B. 3D-Vektoren, Skizzen): mit `python`/matplotlib als PNG in bilder/ speichern und mit \
![Beschreibung](bild:name.png) einbinden.
"""

MODES = {
    "chat": "",
    "hint": "MODUS HINWEIS: {name} steckt bei der Aufgabe fest. Gib GENAU EINEN kurzen, gezielten Hinweis für den nächsten Schritt. "
            "Keine Lösung, kein Endresultat. Höchstens 3 Sätze.",
    "check_step": "MODUS SCHRITT PRÜFEN: {name} zeigt dir seinen bisherigen Lösungsweg. Prüfe jeden Schritt (mit Tools). "
                  "Sag, ob er bis hierher stimmt. Bei einem Fehler: nenne die erste falsche Stelle und warum – aber verrate nicht die Lösung.",
    "explain": "MODUS ERKLÄREN: Erkläre das Thema verständlich mit einem kleinen Beispiel; nutze ein interaktives Diagramm, wenn sinnvoll. "
               "Stelle am Schluss eine kurze Verständnisfrage.",
    "explain_back": "MODUS ERKLÄR'S ZURÜCK: {name} erklärt dir ein Thema in eigenen Worten. Beurteile, was korrekt ist, was fehlt "
                    "und was falsch ist. Stelle 1–2 gezielte Rückfragen, um das Verständnis zu prüfen. Sei ehrlich, aber motivierend.",
    "solution": "MODUS LÖSUNG: {name} möchte die vollständige Lösung sehen. Zeige den Lösungsweg Schritt für Schritt "
                "(gestützt auf die Musterlösung, mit Tools geprüft) und erkläre die entscheidenden Ideen.",
    "correct": "MODUS KORREKTUR: {name} hat seine schriftliche Lösung als Foto oder Text geschickt.\n"
               "1. Lies alles genau und transkribiere es Zeile für Zeile (nummeriert).\n"
               "2. Prüfe jeden Schritt mit den Tools; prüfe jedes Endresultat mit `check_answer` gegen die Antwort-Spezifikation der Teilaufgabe.\n"
               "3. Rufe GENAU EINMAL `submit_review` auf (score 0..1 pro Teilaufgabe: 1 = komplett richtig inkl. Weg; Abzüge für Fehler im Weg; "
               "0 = falsch/fehlt).\n4. Schreib danach eine kurze Rückmeldung an {name}: was gut war, die erste Fehlerstelle mit Erklärung, und wie es richtig geht.",
    "admin": "MODUS LEHRER-ASSISTENT: Du sprichst mit dem Lehrer/Coach von {name} (nicht mit {name}). Hilf bei der Vorbereitung der "
             "Lernsessionen: analysiere die Daten im Kontext genau, nenne konkrete Schwachstellen, typische Fehlvorstellungen und "
             "schlage passende Übungen und Erklärungsstrategien vor. Sei sachlich und präzise.",
}


def system_prompt(mode: str) -> str:
    name = CFG.student_name
    return BASE_PROMPT.format(name=name) + "\n" + MODES.get(mode, "").format(name=name)


def exercise_context(ex: dict, reveal_solution: bool = True) -> str:
    lines = [f"AKTUELLE AUFGABE [{ex['id']}] «{ex['title']}» (Kapitel {ex['chapter']}, Themen: {', '.join(ex.get('skills', []))}, "
             f"Rechner: {ex.get('calculator')}, Schwierigkeit {ex.get('difficulty')})",
             "Aufgabenstellung:", ex["statement"]]
    if ex.get("figures"):
        lines.append(f"(Zur Aufgabe gehören {len(ex['figures'])} Abbildung(en); sie sind als Bild angehängt, falls verfügbar.)")
    for p in ex["parts"]:
        lab = p.get("label") or "–"
        lines.append(f"\nTeilaufgabe {lab}: {p.get('prompt', '')}")
        if reveal_solution:
            lines.append(f"  Antwort-Spezifikation (für check_answer): {json.dumps(p['answer'], ensure_ascii=False)}")
            lines.append(f"  Erwartetes Resultat: {describe_expected(p['answer'])}")
            lines.append(f"  Geprüfte Musterlösung (NICHT einfach verraten, ausser im Lösungsmodus): {p.get('solution', '')}")
    return "\n".join(lines)


def learner_context(user: str) -> str:
    sm = progress.skill_mastery(user)
    c = content()
    weak = sorted(((s, v) for s, v in sm.items() if v["n"] and v["mastery"] < 0.6), key=lambda kv: kv[1]["mastery"])[:5]
    errs = progress.error_stats(user, time.time() - 30 * 86400)["categories"]
    top_errs = sorted(errs.items(), key=lambda kv: -kv[1])[:4]
    parts = []
    if weak:
        parts.append("Schwache Themen: " + "; ".join(f"{c.skills[s]['title']} ({round(v['mastery'] * 100)} %)" for s, v in weak))
    if top_errs:
        parts.append("Häufige Fehlertypen (30 Tage): " + ", ".join(f"{c.error_categories.get(k, k)} ({n}×)" for k, n in top_errs))
    return ("LERNSTAND VON " + CFG.student_name.upper() + ": " + " | ".join(parts)) if parts else ""


def figure_blocks(ex: dict) -> list[dict]:
    out = []
    for f in (ex.get("figures") or [])[:4]:
        p = CFG.content_dir / "figures" / f
        if p.exists():
            mt = "image/png" if f.endswith(".png") else "image/jpeg"
            out.append({"type": "image", "source": {"type": "base64", "media_type": mt, "data": base64.b64encode(p.read_bytes()).decode()}})
    return out


def photo_blocks(photo_ids: list[int], user: str | None = None) -> list[dict]:
    out = []
    for pid in photo_ids:
        r = db.q1("SELECT * FROM photos WHERE id=?", pid)
        if not r or (user and r["user"] != user and user not in CFG.admin_users):
            continue
        data = (CFG.photo_dir / r["path"]).read_bytes()
        out.append({"type": "image", "source": {"type": "base64", "media_type": r["mime"], "data": base64.b64encode(data).decode()}})
    return out


async def run_agent(system: str, content_blocks: list[dict], session: str | None = None) -> AsyncIterator[dict]:
    headers = {"Authorization": f"Bearer {CFG.agent_token}"}
    payload = {"system": system, "content": content_blocks, "session": session, "model": CFG.model}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=10)) as client:
            async with client.stream("POST", f"{CFG.agent_url}/run", json=payload, headers=headers) as resp:
                if resp.status_code != 200:
                    log.error("tutor agent refused the turn", extra={"event": "agent_unreachable", "http_status": resp.status_code})
                    yield {"t": "error", "message": f"Tutor nicht erreichbar (HTTP {resp.status_code}).",
                           "status": "auth" if resp.status_code == 401 else "error"}
                    return
                async for line in resp.aiter_lines():
                    if line.strip():
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            log.warning("tutor agent sent a non-JSON line", extra={"event": "agent_bad_line", "bytes": len(line)})
                            continue
    except httpx.HTTPError as e:
        log.error("tutor agent not reachable", exc_info=True, extra={"event": "agent_unreachable"})
        yield {"t": "error", "message": f"Tutor nicht erreichbar ({type(e).__name__}). Läuft der Agent-Container?",
               "status": tel.classify_error(e)}


def save_images(chat_id: int, images: list[dict]) -> dict[str, int]:
    """Store images the tutor drew; returns name -> photo id."""
    out = {}
    for im in images:
        fn = f"tutor-{chat_id}-{int(time.time() * 1000)}-{im['name']}"
        (CFG.photo_dir / fn).write_bytes(base64.b64decode(im["data"]))
        out[im["name"]] = db.insert("photos", user="tutor", path=fn, mime="image/png", exercise_id=None, created_at=time.time())
    return out


def rewrite_image_refs(text: str, mapping: dict[str, int]) -> str:
    for name, pid in mapping.items():
        text = text.replace(f"(bild:{name})", f"(/api/photo/{pid})")
    return text


async def chat_turn(user: str, chat_id: int, text: str, photo_ids: list[int], mode: str,
                    exercise_id: str | None = None, feature: str | None = None) -> AsyncIterator[dict]:
    """One chat message: store it, stream the tutor's answer, store that.

    Every turn is one AI call in the metrics (provider claude_code, feature = the mode or `feature`)."""
    mode = mode if mode in MODES else "chat"
    feature = feature or metrics.tutor_feature(mode)
    chat = db.q1("SELECT * FROM chats WHERE id=?", chat_id)
    db.insert("messages", chat_id=chat_id, role="user", content=text, attachments=photo_ids,
              meta={"mode": mode, "exercise_id": exercise_id}, created_at=time.time())
    blocks: list[dict] = []
    first_turn = not chat["agent_session"]
    ctx = []
    ex = content().get(exercise_id or chat.get("exercise_id") or "") if (exercise_id or chat.get("exercise_id")) else None
    if ex and (first_turn or exercise_id):
        ctx.append(exercise_context(ex))
        blocks += figure_blocks(ex)
    if first_turn and mode != "admin":
        lc = learner_context(user)
        if lc:
            ctx.append(lc)
    if mode not in ("chat", "admin"):
        ctx.append(f"(Aktueller Modus: {mode})")
    blocks += photo_blocks(photo_ids, user)
    msg = ("[KONTEXT – nur für dich]\n" + "\n\n".join(ctx) + "\n[/KONTEXT]\n\n" if ctx else "") + (text or "(siehe Bild)")
    blocks.append({"type": "text", "text": msg})

    acc, images, review, session, error = [], [], None, chat["agent_session"], None
    started, first_text, done, status = time.monotonic(), None, None, None
    async for ev in run_agent(system_prompt(mode), blocks, chat["agent_session"]):
        t = ev.get("t")
        if t == "text":
            if first_text is None:
                first_text = time.monotonic() - started
            acc.append(ev["d"])
        elif t == "tool":
            metrics.tool_call(ev.get("name", ""))
        elif t == "image":
            images.append(ev)
            continue
        elif t == "review":
            review = ev["data"]
            continue
        elif t == "done":
            done = ev
            session = ev.get("session") or session
            if not acc and ev.get("text"):
                acc.append(ev["text"])
            continue
        elif t == "error":
            error = ev["message"]
            status = ev.get("status") or "error"
        yield ev
    _record_turn(feature, done, status, time.monotonic() - started, first_text, chat_id)
    mapping = save_images(chat_id, images) if images else {}
    final = rewrite_image_refs("".join(acc), mapping)
    if mapping:
        yield {"t": "replace", "text": final}
    mid = db.insert("messages", chat_id=chat_id, role="assistant", content=final or (error or ""),
                    attachments=list(mapping.values()), meta={"mode": mode, "error": error, "review": bool(review)}, created_at=time.time())
    db.update("chats", chat_id, agent_session=session, updated_at=time.time())
    if review is not None:
        yield {"t": "review", "data": review}
    yield {"t": "done", "message_id": mid}


def _record_turn(feature: str, done: dict | None, status: str | None, seconds: float, first_text: float | None,
                 chat_id: int) -> None:
    """AI-call metrics from the agent's `done` line: Claude Code's usage and total_cost_usd."""
    done = done or {}
    status = status or done.get("status") or ("ok" if done else "error")
    tel.record_llm("claude_code", done.get("model") or CFG.model, feature, done.get("usage"), status=status,
                   duration=seconds, cost_usd=done.get("cost"))
    if first_text is not None:
        metrics.FIRST_TEXT.labels(feature).observe(first_text)
    if done.get("turns"):
        metrics.TUTOR_TURNS.labels(feature).observe(done["turns"])
    extra = {"event": "tutor_turn", "feature": feature, "status": status, "chat": chat_id, "seconds": round(seconds, 2),
             "turns": done.get("turns"), "cost": done.get("cost")}
    if status == "ok":
        log.info("tutor turn", extra=extra)
    else:
        log.error("tutor turn failed", extra=extra)


def apply_review(user: str, ex: dict, review: dict, mode: str, review_id: int, exam_run_id: int | None = None,
                 session_id: int | None = None) -> list[dict]:
    """Turn a correction into attempts. The answer checker overrides the AI on final answers when it can parse them."""
    results = []
    by_label = {(p.get("label") or ""): p for p in review.get("parts", [])}
    for p in ex["parts"]:
        lab = p.get("label") or ""
        r = by_label.get(lab) or (review.get("parts", [None])[0] if len(ex["parts"]) == 1 and review.get("parts") else None)
        if r is None:
            continue
        ai_correct = bool(r.get("correct"))
        score = float(r.get("score", 1.0 if ai_correct else 0.0))
        verdict = None
        if p["answer"]["type"] != "text" and r.get("final_answer"):
            verdict = check(p["answer"], r["final_answer"], ex.get("skills"))
            if verdict.status in ("richtig", "falsch", "fast"):
                if verdict.ok and not ai_correct:
                    score = max(score, 0.6)
                if not verdict.ok:
                    score = min(score, 0.4 if verdict.status == "fast" else 0.2)
        correct = verdict.ok if verdict and verdict.status in ("richtig", "falsch", "fast") else ai_correct
        disagreement = verdict is not None and verdict.status in ("richtig", "falsch") and verdict.ok != ai_correct
        metrics.answer(user, mode, ex.get("chapter"), "photo", "richtig" if correct else "falsch", r.get("error_category"))
        if disagreement:
            metrics.DISAGREEMENTS.labels(ex.get("chapter") or "other").inc()
            log.warning("AI and checker disagree", extra={"event": "review_disagreement", "exercise": ex["id"], "part": lab,
                                                          "ai_correct": ai_correct, "checker": verdict.status})
        aid = db.insert("attempts", user=user, exercise_id=ex["id"], part=lab, chapter=ex["chapter"], skills=ex.get("skills", []),
                        mode=mode, input=r.get("final_answer"), status="richtig" if correct else "falsch", score=score,
                        correct=1 if correct else 0, hints=0, solution_shown=0,
                        error_category=None if correct else r.get("error_category"), feedback=r.get("feedback"),
                        source="photo", review_id=review_id, exam_run_id=exam_run_id, session_id=session_id,
                        admin_note="KI und Prüfer uneinig – bitte ansehen" if disagreement else None, created_at=time.time())
        if mode != "exam":
            progress.add_xp(user, progress.xp_for(ex, score, correct), "Korrektur", ex["id"])
            progress.on_attempt(user, ex, lab, correct, score, mode, aid, r.get("error_category"))
        results.append({"label": lab, "correct": correct, "score": score, "feedback": r.get("feedback"),
                        "error_category": r.get("error_category"), "checker": verdict.as_dict() if verdict else None,
                        "disagreement": disagreement})
    return results
