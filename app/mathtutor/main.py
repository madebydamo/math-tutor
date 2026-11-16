"""Mathe-Trainer web app: student pages, coach (admin) pages and the JSON/SSE API."""
from __future__ import annotations

import asyncio
import hmac
import io
import json
import os
import random
import time
import uuid

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import db, engage, generators, notify, progress, steps, tutor
from .checker import check, describe_expected
from .config import CFG
from .content import content, public_exercise, reload

app = FastAPI(title="Mathe-Trainer", docs_url=None, redoc_url=None)

# SWAG sends this secret with every proxied request (X-Neo-Proxy-Secret). Without it the identity
# headers (Remote-User) are ignored: other containers (the tutor agent on the sandbox network) can
# reach this port directly and must not pass as the student or a coach.
PROXY_SECRET = os.environ.get("NEO_PROXY_SECRET", "")


def _app_version() -> str:
    """Short hash over the app code and content, so a report says exactly which build was running."""
    import hashlib

    h = hashlib.sha1()
    root = CFG.static_dir.parent
    for p in sorted(list(root.rglob("*.py")) + list(CFG.static_dir.glob("js/*.js"))):
        h.update(p.read_bytes())
    for p in sorted(CFG.content_dir.rglob("*.json")):
        h.update(p.name.encode())
        h.update(str(p.stat().st_size).encode())
    return h.hexdigest()[:10]


APP_VERSION = _app_version()


@app.middleware("http")
async def _log_server_errors(request: Request, call_next):
    """Unhandled exceptions are stored (path, user, traceback) for the coach's Feedback page."""
    import traceback

    try:
        return await call_next(request)
    except Exception as e:  # noqa: BLE001
        try:
            user = _identity(request)
            db.insert("server_errors", user=user, method=request.method, path=str(request.url.path) + (f"?{request.url.query}" if request.url.query else ""),
                      error=f"{type(e).__name__}: {e}"[:500], traceback=traceback.format_exc()[-6000:], created_at=time.time())
        except Exception:  # noqa: BLE001
            pass
        return JSONResponse({"error": "Interner Fehler – er wurde protokolliert.", "kind": "server"}, status_code=500)


@app.on_event("startup")
async def _startup():
    db.init()  # engage extends the schema on import
    content()
    asyncio.create_task(notify.loop())


# ───────────── auth ─────────────

class Who(dict):
    @property
    def user(self) -> str:
        return self["user"]

    @property
    def admin(self) -> bool:
        return self["admin"]


def _from_proxy(request: Request) -> bool:
    """The request came through SWAG: it carries the proxy secret (compared in constant time)."""
    sent = request.headers.get("X-Neo-Proxy-Secret") or ""
    return bool(PROXY_SECRET) and hmac.compare_digest(sent.encode(), PROXY_SECRET.encode())


def _identity(request: Request) -> str:
    """Signed-in user name, or "" (anonymous). Remote-User counts only on requests from SWAG."""
    u = (request.headers.get("Remote-User") or "").strip().lower() if _from_proxy(request) else ""
    if not u and CFG.dev_user:  # local development only: switch user with /dev/as/<name>
        u = (request.cookies.get("mt_dev_user") or CFG.dev_user).strip().lower()
    return u


def who(request: Request) -> Who:
    u = _identity(request)
    if not u:
        raise HTTPException(401, "Nicht angemeldet")
    admin = u in [a.lower() for a in CFG.admin_users]
    if not admin and u != CFG.student_user.lower():
        raise HTTPException(403, "Kein Zugriff")
    return Who(user=u, admin=admin)


def admin_only(w: Who = Depends(who)) -> Who:
    if not w.admin:
        raise HTTPException(403, "Nur für den Coach")
    return w


def sse(gen):
    async def wrap():
        try:
            async for ev in gen:
                yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:  # noqa: BLE001
            yield f"data: {json.dumps({'t': 'error', 'message': str(e)})}\n\n"
    return StreamingResponse(wrap(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ───────────── pages ─────────────

@app.get("/dev/as/{name}")
def dev_as(name: str):
    if not CFG.dev_user:
        raise HTTPException(404)
    from fastapi.responses import RedirectResponse
    r = RedirectResponse("/admin" if name.lower() in [a.lower() for a in CFG.admin_users] else "/")
    r.set_cookie("mt_dev_user", name.lower())
    return r


@app.get("/health")
def health():
    return {"ok": True, "exercises": len(content().exercises)}


@app.get("/", response_class=HTMLResponse)
def index(w: Who = Depends(who)):
    return FileResponse(CFG.static_dir / "index.html")


@app.get("/admin", response_class=HTMLResponse)
def admin_page(w: Who = Depends(admin_only)):
    return FileResponse(CFG.static_dir / "admin.html")


app.mount("/static", StaticFiles(directory=str(CFG.static_dir)), name="static")


@app.middleware("http")
async def _no_stale_code(request: Request, call_next):
    """Scripts and styles change with every update: browsers revalidate them (ETag) instead of caching."""
    resp = await call_next(request)
    path = request.url.path
    if (path.endswith((".js", ".css", ".html")) or path in ("/", "/admin")) and "/vendor/" not in path:
        resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.get("/figures/{name}")
def figure(name: str, w: Who = Depends(who)):
    p = (CFG.content_dir / "figures" / name).resolve()
    if not str(p).startswith(str((CFG.content_dir / "figures").resolve())) or not p.exists():
        raise HTTPException(404)
    return FileResponse(p, headers={"Cache-Control": "max-age=86400"})


# ───────────── student API ─────────────

@app.get("/api/me")
def me(w: Who = Depends(who)):
    return {"user": w.user, "admin": w.admin, "student": CFG.student_name, "preview": w.admin and w.user != CFG.student_user,
            "version": APP_VERSION}


# ───────────── feedback (bugs, wishes, questions) ─────────────

FEEDBACK_KINDS = {"bug": "Etwas ist kaputt", "wunsch": "Verbesserungsvorschlag", "frage": "Frage", "lob": "Lob"}


@app.post("/api/feedback")
async def feedback(request: Request, w: Who = Depends(who)):
    b = await request.json()
    kind = b.get("kind") if b.get("kind") in FEEDBACK_KINDS else "bug"
    ctx = b.get("context") or {}
    ctx["server"] = {"version": APP_VERSION, "user": w.user,
                     "recent_server_errors": db.q("SELECT id, method, path, error, created_at FROM server_errors WHERE user=? AND created_at>? ORDER BY id DESC LIMIT 5",
                                                  w.user, time.time() - 3600)}
    photos = [int(p) for p in (b.get("photo_ids") or [])][:8]
    fid = db.insert("feedback", user=w.user, kind=kind, text=(b.get("text") or "")[:5000], photo_ids=photos, context=ctx,
                    status="neu", created_at=time.time(), updated_at=time.time())
    if w.user == CFG.student_user:
        page = (ctx.get("page") or {}).get("hash") or ""
        await asyncio.to_thread(notify.send, f"📮 Feedback von {CFG.student_name} ({FEEDBACK_KINDS[kind]}){' · ' + str(len(photos)) + ' Bild(er)' if photos else ''}\n"
                                f"{(b.get('text') or '')[:300]}\nSeite: {page}\n{notify.link('/admin#/feedback')}")
    return {"id": fid, "message": "Danke! Dein Feedback ist angekommen."}


@app.get("/api/admin/feedback")
def admin_feedback(w: Who = Depends(admin_only)):
    rows = db.q("SELECT * FROM feedback ORDER BY status='erledigt', id DESC LIMIT 300")
    for r in rows:
        r["context"] = db.loads(r["context"], {})
        r["photo_ids"] = db.loads(r["photo_ids"], [])
        r["kind_title"] = FEEDBACK_KINDS.get(r["kind"], r["kind"])
    errors = db.q("SELECT * FROM server_errors ORDER BY id DESC LIMIT 100")
    return {"items": rows, "server_errors": errors, "version": APP_VERSION,
            "open": sum(1 for r in rows if r["status"] != "erledigt")}


@app.post("/api/admin/feedback/{fid}")
async def admin_feedback_update(fid: int, request: Request, w: Who = Depends(admin_only)):
    b = await request.json()
    fields = {k: b[k] for k in ("status", "admin_note") if k in b}
    if fields:
        db.update("feedback", fid, updated_at=time.time(), **fields)
    return {"ok": True}


@app.post("/api/admin/server_errors/clear")
def admin_clear_errors(w: Who = Depends(admin_only)):
    db.ex("DELETE FROM server_errors")
    return {"ok": True}


@app.get("/api/dashboard")
def dashboard(w: Who = Depends(who)):
    progress.record_activity(w.user)
    d = progress.dashboard(w.user)
    d["assignments"] = assignments_for(w.user)
    d["goal"] = engage.daily_goal(w.user)
    d["quests"] = engage.quests(w.user)
    d["combo"] = engage.combo(w.user)
    return progress.json_safe(d)


@app.get("/api/medals")
def medals(w: Who = Depends(who)):
    return engage.medals(w.user)


@app.get("/api/avatar")
def avatar(w: Who = Depends(who)):
    d = CFG.avatar_dir
    files = {p.stem: f"/avatar/{p.name}?v={int(p.stat().st_mtime)}" for p in d.glob("*.png")} if d.exists() else {}
    return {"images": files}


@app.get("/avatar/{name}")
def avatar_file(name: str, w: Who = Depends(who)):
    p = (CFG.avatar_dir / name).resolve()
    if p.parent != CFG.avatar_dir.resolve() or p.suffix != ".png" or not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/png", headers={"Cache-Control": "max-age=86400"})


# ───────────── formula trainer ─────────────

@app.get("/api/cards")
def cards_decks(w: Who = Depends(who)):
    return {"decks": engage.decks(w.user), "total": len(content().cards)}


@app.get("/api/cards/session")
def cards_session(chapter: str | None = None, skill: str | None = None, limit: int = 20, w: Who = Depends(who)):
    return engage.session_cards(w.user, chapter, skill, min(limit, 60))


@app.post("/api/cards/{card_id}/rate")
async def cards_rate(card_id: str, request: Request, w: Who = Depends(who)):
    b = await request.json()
    if card_id not in content().cards:
        raise HTTPException(404)
    return engage.rate_card(w.user, card_id, b.get("grade", "good"), b.get("kind", "flip"))


@app.post("/api/cards/{card_id}/drill")
async def cards_drill(card_id: str, request: Request, w: Who = Depends(who)):
    b = await request.json()
    k = content().cards.get(card_id)
    if not k:
        raise HTTPException(404)
    i = int(b.get("index", 0))
    d = k["drill"][i]
    res = check(d["answer"], b.get("input"), k.get("skills"))
    out = res.as_dict()
    if res.status != "format":
        out["expected"] = describe_expected(d["answer"])
    return out


@app.get("/api/exercise/{eid}/formulas")
def exercise_formulas(eid: str, w: Who = Depends(who)):
    ex = content().get(eid)
    if not ex:
        raise HTTPException(404)
    c = content()
    return {"cards": engage.formulas_for(ex), "chapter": ex["chapter"], "chapter_title": c.chapters[ex["chapter"]]["title"],
            "skills": [{"id": s, "title": c.skills[s]["title"], "skript": c.skills[s].get("skript")} for s in ex.get("skills", []) if s in c.skills]}


@app.get("/api/history")
def hist(days: int = 30, w: Who = Depends(who)):
    return progress.history(w.user, min(days, 120))


@app.get("/api/rank")
def rank(w: Who = Depends(who)):
    return progress.rank_state(w.user)


@app.get("/api/curriculum")
def curriculum(w: Who = Depends(who)):
    c = content()
    sm = progress.skill_mastery(w.user)
    cm = progress.chapter_mastery(sm, include_optional=True)
    out = []
    for ch in c.curriculum["chapters"]:
        out.append({**ch, "mastery": cm[ch["id"]],
                    "skills": [{**s, **sm[s["id"]], "course": len(c.by_skill.get(s["id"], [])),
                                "generators": len(generators.for_skill(s["id"]))} for s in ch["skills"]],
                    "exercises": sum(1 for e in c.exercises.values() if e["chapter"] == ch["id"])})
    return {"chapters": out, "error_categories": c.error_categories, "exam_info": c.exam_info}


def exercise_status(user: str) -> dict[str, str]:
    st = {}
    for r in db.q("SELECT exercise_id, MAX(correct) AS ok, COUNT(*) AS n FROM attempts WHERE user=? GROUP BY exercise_id", user):
        st[r["exercise_id"]] = "geloest" if r["ok"] else "offen"
    return st


@app.get("/api/chapter/{cid}")
def chapter(cid: str, w: Who = Depends(who)):
    c = content()
    if cid not in c.chapters:
        raise HTTPException(404)
    sm = progress.skill_mastery(w.user)
    st = exercise_status(w.user)
    exs = [{"id": e["id"], "title": e["title"], "source": e["source"], "skills": e["skills"], "difficulty": e.get("difficulty"),
            "calculator": e.get("calculator"), "status": st.get(e["id"], "neu"), "minutes": e.get("minutes")}
           for e in c.exercises.values() if e["chapter"] == cid]
    ch = c.chapters[cid]
    return {"chapter": {**ch, "skills": [{**s, **sm[s["id"]]} for s in ch["skills"]]},
            "theory": c.theory[cid], "formeln": c.formeln[cid], "exercises": exs}


@app.get("/api/formeln")
def formeln(w: Who = Depends(who)):
    """Formelsammlung: chapters → topics → formula cards (with symbol definitions), plus the full sheet."""
    c = content()
    out = []
    for cid, ch in c.chapters.items():
        cards = [k for k in c.cards.values() if k["chapter"] == cid]
        topics: dict[str, dict] = {}
        for k in cards:
            t = k.get("topic") or "Allgemein"
            topics.setdefault(t, {"title": t, "order": k.get("topic_order", 99), "cards": []})["cards"].append(
                {key: k.get(key) for key in ("id", "name", "formula", "symbols", "explain", "example", "pitfall", "skills")})
        out.append({"id": cid, "title": ch["title"], "nr": ch["nr"], "icon": ch.get("icon"), "optional": bool(ch.get("optional")),
                    "md": c.formeln[cid], "topics": sorted(topics.values(), key=lambda t: (t["order"], t["title"]))})
    return out


@app.get("/api/exercise/next")
def next_exercise(skill: str | None = None, chapter: str | None = None, prefer: str = "mix",
                  calculator: str | None = None, w: Who = Depends(who)):
    c = content()
    seen = {r["exercise_id"] for r in db.q("SELECT DISTINCT exercise_id FROM attempts WHERE user=? AND correct=1", w.user)}
    if not skill and not chapter:
        sm = progress.skill_mastery(w.user)
        weights = {s: (1.2 - v["mastery"]) ** 2 + 0.05 for s, v in sm.items()}
        skill = random.choices(list(weights), weights=list(weights.values()))[0]
    ex = c.pick(skill=skill, chapter=chapter, prefer=prefer, exclude=seen, calculator=calculator)
    if not ex:
        raise HTTPException(404, "Keine Aufgabe gefunden")
    return public_exercise(ex)


@app.get("/api/exercise/{eid}")
def get_exercise(eid: str, reveal: bool = False, w: Who = Depends(who)):
    ex = content().get(eid)
    if not ex:
        raise HTTPException(404)
    out = public_exercise(ex, reveal=reveal and w.admin)
    out["attempts"] = db.q("SELECT part, status, correct, input, hints, created_at FROM attempts WHERE user=? AND exercise_id=? ORDER BY id",
                           w.user, eid)
    return out


@app.get("/api/exercise/{eid}/similar")
def similar(eid: str, w: Who = Depends(who)):
    ex = content().get(eid)
    if not ex:
        raise HTTPException(404)
    p = generators.parse_id(eid)
    if p:
        return public_exercise(generators.build(p[0], random.randint(1, 10**6)))
    nxt = content().pick(skill=ex["skills"][0], exclude={eid})
    if not nxt:
        raise HTTPException(404)
    return public_exercise(nxt)


def _part(ex, label):
    for p in ex["parts"]:
        if (p.get("label") or "") == (label or ""):
            return p
    raise HTTPException(404, "Teilaufgabe nicht gefunden")


@app.post("/api/exercise/{eid}/check")
async def check_answer(eid: str, request: Request, w: Who = Depends(who)):
    body = await request.json()
    ex = content().get(eid)
    if not ex:
        raise HTTPException(404)
    part = _part(ex, body.get("part", ""))
    res = check(part["answer"], body.get("input"), ex.get("skills"))
    mode = body.get("mode", "practice")
    out = res.as_dict()
    if res.status == "format":
        return out
    if mode == "exam":
        return {"ok": None, "status": "gespeichert", "message": "Antwort gespeichert."}
    hints = int(body.get("hints", 0))
    shown = bool(body.get("solution_shown"))
    score = progress.attempt_score(res.ok, res.status, hints, shown)
    error = res.details.get("hint_tag") if hasattr(res, "details") else None
    aid = db.insert("attempts", user=w.user, exercise_id=eid, part=part.get("label") or "", chapter=ex["chapter"],
                    skills=ex.get("skills", []), mode=mode, input=str(body.get("input")), status=res.status, score=score,
                    correct=1 if res.ok else 0, hints=hints, solution_shown=1 if shown else 0,
                    error_category=error or body.get("error_category"), source="auto",
                    duration_s=int(body.get("duration_s") or 0), session_id=body.get("session_id"), created_at=time.time())
    xp = progress.xp_for(ex, score, res.ok) if not shown else 0
    previously = db.q1("SELECT COUNT(*) AS n FROM attempts WHERE user=? AND exercise_id=? AND part=? AND correct=1 AND id<?",
                       w.user, eid, part.get("label") or "", aid)["n"]
    if previously:
        xp = max(1, xp // 5)
    progress.add_xp(w.user, xp, "Aufgabe", eid)
    progress.record_activity(w.user, int(body.get("duration_s") or 0))
    ch = progress.on_attempt(w.user, ex, part.get("label") or "", res.ok, score, mode, aid, error, body.get("challenge_id"))
    if not res.ok:
        await asyncio.to_thread(notify.struggle, w.user, ex["skills"][0])
    rank = progress.rank_state(w.user)
    eng = engage.after_attempt(w.user, res.ok)
    out.update({"xp": xp, "attempt_id": aid, "challenge": ch, "promoted": rank["promoted"],
                "rank": {"name": rank["rank"]["name"], "xp": rank["xp"]}, **eng})
    if res.ok or shown:
        out["solution"] = steps.payload(part, ex)
    return out


@app.post("/api/exercise/{eid}/hint")
async def hint(eid: str, request: Request, w: Who = Depends(who)):
    body = await request.json()
    ex = content().get(eid)
    if not ex:
        raise HTTPException(404)
    part = _part(ex, body.get("part", ""))
    level = int(body.get("level", 1))
    hints = part.get("hints", [])
    if not 1 <= level <= len(hints):
        raise HTTPException(400, "Keine weiteren Hinweise")
    db.insert("hints", user=w.user, exercise_id=eid, part=part.get("label") or "", level=level, kind="static", created_at=time.time())
    return {"level": level, "text": hints[level - 1], "more": level < len(hints)}


@app.post("/api/exercise/{eid}/solution")
async def solution(eid: str, request: Request, w: Who = Depends(who)):
    body = await request.json()
    ex = content().get(eid)
    if not ex:
        raise HTTPException(404)
    part = _part(ex, body.get("part", ""))
    lab = part.get("label") or ""
    solved = db.q1("SELECT 1 FROM attempts WHERE user=? AND exercise_id=? AND part=? AND correct=1", w.user, eid, lab)
    if not solved and body.get("mode") != "exam":
        aid = db.insert("attempts", user=w.user, exercise_id=eid, part=lab, chapter=ex["chapter"], skills=ex.get("skills", []),
                        mode=body.get("mode", "practice"), input=None, status="falsch", score=0.0, correct=0,
                        hints=int(body.get("hints", 0)), solution_shown=1, error_category=None, source="auto",
                        duration_s=int(body.get("duration_s") or 0), created_at=time.time())
        progress.on_attempt(w.user, ex, lab, False, 0.0, body.get("mode", "practice"), aid, None, body.get("challenge_id"))
    return {"solution": steps.payload(part, ex), "expected": describe_expected(part["answer"])}


# ───────────── photos ─────────────

@app.post("/api/photo")
async def upload_photo(file: UploadFile = File(...), exercise_id: str | None = None, w: Who = Depends(who)):
    from PIL import Image, ImageOps

    raw = await file.read()
    if len(raw) > 25_000_000:
        raise HTTPException(413, "Bild zu gross")
    try:
        im = Image.open(io.BytesIO(raw))
        im = ImageOps.exif_transpose(im).convert("RGB")
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "Kein lesbares Bild") from None
    im.thumbnail((2000, 2000))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    fn = f"{w.user}-{uuid.uuid4().hex}.jpg"
    (CFG.photo_dir / fn).write_bytes(buf.getvalue())
    pid = db.insert("photos", user=w.user, path=fn, mime="image/jpeg", exercise_id=exercise_id, created_at=time.time())
    return {"id": pid, "url": f"/api/photo/{pid}"}


@app.get("/api/photo/{pid}")
def get_photo(pid: int, w: Who = Depends(who)):
    r = db.q1("SELECT * FROM photos WHERE id=?", pid)
    if not r or (r["user"] not in (w.user, "tutor") and not w.admin):
        raise HTTPException(404)
    return FileResponse(CFG.photo_dir / r["path"], media_type=r["mime"], headers={"Cache-Control": "max-age=86400"})


@app.post("/api/exercise/{eid}/review")
async def review(eid: str, request: Request, w: Who = Depends(who)):
    """Correct handwritten work (photos) or typed work: streams the tutor's feedback, then records attempts."""
    body = await request.json()
    ex = content().get(eid)
    if not ex:
        raise HTTPException(404)
    photo_ids = [int(p) for p in body.get("photo_ids", [])]
    mode = body.get("mode", "practice")
    chat_id = db.insert("chats", user=w.user, title=f"Korrektur: {ex['title']}", exercise_id=eid, kind="review",
                        created_at=time.time(), updated_at=time.time())
    text = body.get("text") or "Bitte korrigiere meine Lösung."

    async def gen():
        review_data = None
        async for ev in tutor.chat_turn(w.user, chat_id, text, photo_ids, "correct", eid):
            if ev.get("t") == "review":
                review_data = ev["data"]
                continue
            yield ev
        if review_data:
            rid = db.insert("reviews", user=w.user, exercise_id=eid, photo_ids=photo_ids, result=review_data, status="ok",
                            mode=mode, chat_id=chat_id, created_at=time.time())
            results = tutor.apply_review(w.user, ex, review_data, mode, rid, session_id=body.get("session_id"))
            if mode != "exam":
                progress.add_xp(w.user, 5, "Lösung fotografiert", eid)
            rank = progress.rank_state(w.user)
            yield {"t": "result", "review": review_data, "results": results, "review_id": rid, "promoted": rank["promoted"],
                   "solutions": {(p.get("label") or ""): steps.payload(p, ex) for p in ex["parts"]}}
        else:
            yield {"t": "result", "review": None, "results": [], "message": "Der Tutor konnte keine strukturierte Korrektur erstellen."}
    return sse(gen())


# ───────────── chat ─────────────

@app.get("/api/chats")
def chats(w: Who = Depends(who)):
    return db.q("SELECT id, title, exercise_id, kind, updated_at FROM chats WHERE user=? AND kind!='admin' ORDER BY updated_at DESC LIMIT 50", w.user)


@app.post("/api/chats")
async def new_chat(request: Request, w: Who = Depends(who)):
    body = await request.json()
    kind = "admin" if body.get("kind") == "admin" and w.admin else "chat"
    cid = db.insert("chats", user=w.user, title=body.get("title") or "Neues Gespräch", exercise_id=body.get("exercise_id"),
                    kind=kind, created_at=time.time(), updated_at=time.time())
    return {"id": cid}


def _own_chat(cid: int, w: Who) -> dict:
    ch = db.q1("SELECT * FROM chats WHERE id=?", cid)
    if not ch or (ch["user"] != w.user and not w.admin):
        raise HTTPException(404)
    return ch


@app.get("/api/chats/{cid}")
def get_chat(cid: int, w: Who = Depends(who)):
    ch = _own_chat(cid, w)
    msgs = db.q("SELECT id, role, content, attachments, meta, created_at FROM messages WHERE chat_id=? ORDER BY id", cid)
    for m in msgs:
        m["attachments"] = db.loads(m["attachments"], [])
        m["meta"] = db.loads(m["meta"], {})
    return {"chat": ch, "messages": msgs}


@app.post("/api/chats/{cid}/send")
async def send(cid: int, request: Request, w: Who = Depends(who)):
    ch = _own_chat(cid, w)
    body = await request.json()
    text = (body.get("text") or "").strip()
    mode = body.get("mode", "chat")
    if ch["kind"] == "admin":
        mode = "admin"
        if not db.q1("SELECT 1 FROM messages WHERE chat_id=?", cid):
            text = "[DATEN ZUM LERNSTAND – JSON]\n" + json.dumps(briefing_data(), ensure_ascii=False, default=str)[:60000] + "\n\n" + text
    elif mode == "admin":
        mode = "chat"
    if ch["title"] == "Neues Gespräch" and text:
        db.update("chats", cid, title=text[:60])
    return sse(tutor.chat_turn(w.user, cid, text, [int(p) for p in body.get("photo_ids", [])], mode, body.get("exercise_id")))


# ───────────── challenges (Revanche) ─────────────

@app.get("/api/challenges")
def challenges(w: Who = Depends(who)):
    return {"items": progress.challenge_list(w.user), "won": progress.challenges_won(w.user)}


@app.get("/api/challenges/next")
def challenge_next(w: Who = Depends(who)):
    from .content import disabled_ids
    off = set(disabled_ids())
    due = [c for c in progress.challenge_list(w.user, only_due=True) if c["exercise_id"] not in off and _exercise_key(c["exercise_id"]) not in off]
    if not due:
        raise HTTPException(404, "Keine Revanche fällig")
    ch = due[0]
    ex = content().get(ch["exercise_id"])
    if not ex:
        raise HTTPException(404)
    p = generators.parse_id(ex["id"])
    if p:  # generated: same kind of exercise, new numbers
        ex = generators.build(p[0], random.randint(1, 10**6))
    out = public_exercise(ex)
    out["challenge"] = {"id": ch["id"], "part": ch["part"], "wins": ch["wins"], "need": progress.WINS_TO_BEAT, "fails": ch["fails"]}
    return out


# ───────────── assignments ─────────────

def assignments_for(user: str) -> list[dict]:
    rows = db.q("SELECT * FROM assignments WHERE archived=0 ORDER BY due_at")
    out = []
    for a in rows:
        skills = db.loads(a["skills"], [])
        exids = db.loads(a["exercise_ids"], [])
        done = 0
        if skills:
            for r in db.q("SELECT skills FROM attempts WHERE user=? AND correct=1 AND created_at>=?", user, a["created_at"]):
                if (db.loads(r["skills"], []) or [None])[0] in skills:
                    done += 1
        if exids:
            done += db.q1(f"SELECT COUNT(DISTINCT exercise_id) AS n FROM attempts WHERE user=? AND correct=1 AND exercise_id IN ({','.join('?' * len(exids))})",
                          user, *exids)["n"]
        out.append({**a, "skills": skills, "exercise_ids": exids, "done": done})
    return out


# ───────────── exam simulation ─────────────

@app.get("/api/exams")
def exams(w: Who = Depends(who)):
    runs = db.q("SELECT id, exam_id, part_index, started_at, finished_at, score, max_score FROM exam_runs WHERE user=? ORDER BY id DESC", w.user)
    return {"exams": content().exams, "runs": runs, "info": content().exam_info}


def _points(ex: dict) -> float:
    return float(ex.get("points") or 5 * len(ex["parts"]))


@app.post("/api/exams/start")
async def exam_start(request: Request, w: Who = Depends(who)):
    body = await request.json()
    c = content()
    if body.get("exam_id") == "mix":
        rng = random.Random()
        calc = body.get("calculator", "ohne")
        ids = []
        for cid in c.chapters:
            ex = c.pick(chapter=cid, calculator=calc, rng=rng, prefer="course")
            if ex:
                ids.append(ex["id"])
        minutes = int(body.get("minutes", 45))
        title = f"Gemischte Prüfung ({'ohne' if calc == 'ohne' else 'mit'} Rechner)"
    else:
        exam = next((e for e in c.exams if e["id"] == body.get("exam_id")), None)
        if not exam:
            raise HTTPException(404)
        part = exam["parts"][int(body.get("part_index", 0))]
        ids, minutes, title = part["exercises"], part["minutes"], f"{exam['title']} – {part['title']}"
    t = time.time()
    rid = db.insert("exam_runs", user=w.user, exam_id=body.get("exam_id"), part_index=int(body.get("part_index", 0)),
                    exercise_ids=ids, started_at=t, deadline=t + minutes * 60, details={"title": title, "answers": {}})
    return {"id": rid, "title": title, "deadline": t + minutes * 60, "minutes": minutes,
            "exercises": [public_exercise(c.get(i)) for i in ids if c.get(i)]}


@app.get("/api/exam_runs/{rid}")
def exam_run(rid: int, w: Who = Depends(who)):
    r = db.q1("SELECT * FROM exam_runs WHERE id=?", rid)
    if not r or (r["user"] != w.user and not w.admin):
        raise HTTPException(404)
    r["details"] = db.loads(r["details"], {})
    r["exercise_ids"] = db.loads(r["exercise_ids"], [])
    if r["finished_at"]:
        c = content()
        r["solutions"] = {i: public_exercise(c.get(i), reveal=True) for i in r["exercise_ids"] if c.get(i)}
    else:
        r["exercises"] = [public_exercise(content().get(i)) for i in r["exercise_ids"] if content().get(i)]
    return r


@app.post("/api/exam_runs/{rid}/submit")
async def exam_submit(rid: int, request: Request, w: Who = Depends(who)):
    body = await request.json()
    r = db.q1("SELECT * FROM exam_runs WHERE id=? AND user=?", rid, w.user)
    if not r or r["finished_at"]:
        raise HTTPException(404)
    answers = body.get("answers", {})   # {exercise_id: {part: input}}
    photos = body.get("photos", {})     # {exercise_id: [photo ids]}
    c = content()
    details = db.loads(r["details"], {})
    details.update({"answers": answers, "photos": photos, "grading": {}})
    total = maxs = 0.0
    pending = []
    for eid in db.loads(r["exercise_ids"], []):
        ex = c.get(eid)
        if not ex:
            continue
        pts = _points(ex)
        maxs += pts
        per = pts / len(ex["parts"])
        if photos.get(eid):
            pending.append(eid)
            details["grading"][eid] = {"status": "pending", "points": 0, "max": pts}
            continue
        got, parts = 0.0, {}
        for p in ex["parts"]:
            lab = p.get("label") or ""
            inp = (answers.get(eid) or {}).get(lab)
            if p["answer"]["type"] == "text" or inp in (None, ""):
                res = {"ok": False, "status": "leer" if inp in (None, "") else "manuell"}
            else:
                res = check(p["answer"], inp, ex.get("skills")).as_dict()
            ok = bool(res.get("ok"))
            got += per if ok else 0
            parts[lab] = {**res, "input": inp}
            db.insert("attempts", user=w.user, exercise_id=eid, part=lab, chapter=ex["chapter"], skills=ex.get("skills", []),
                      mode="exam", input=None if inp is None else str(inp), status="richtig" if ok else "falsch",
                      score=1.0 if ok else 0.0, correct=1 if ok else 0, hints=0, solution_shown=0, source="auto",
                      exam_run_id=rid, created_at=time.time())
        total += got
        details["grading"][eid] = {"status": "done", "points": round(got, 2), "max": pts, "parts": parts}
    db.update("exam_runs", rid, finished_at=time.time(), score=total, max_score=maxs, details=details)
    if pending:
        asyncio.create_task(_grade_photos(rid, w.user, pending, photos))
    progress.add_xp(w.user, 50, "Prüfungssimulation", str(rid))
    return {"id": rid, "pending": pending}


async def _grade_photos(rid: int, user: str, eids: list[str], photos: dict):
    c = content()
    for eid in eids:
        ex = c.get(eid)
        chat_id = db.insert("chats", user=user, title=f"Prüfung: {ex['title']}", exercise_id=eid, kind="review",
                            created_at=time.time(), updated_at=time.time())
        review_data = None
        async for ev in tutor.chat_turn(user, chat_id, "Prüfungsmodus: Bitte korrigiere streng nach Prüfungsmassstab "
                                        "(Lösungsweg muss ersichtlich sein).", [int(p) for p in photos[eid]], "correct", eid):
            if ev.get("t") == "review":
                review_data = ev["data"]
        r = db.q1("SELECT * FROM exam_runs WHERE id=?", rid)
        details = db.loads(r["details"], {})
        pts = _points(ex)
        if review_data:
            revid = db.insert("reviews", user=user, exercise_id=eid, photo_ids=photos[eid], result=review_data, status="ok",
                              mode="exam", chat_id=chat_id, created_at=time.time())
            results = tutor.apply_review(user, ex, review_data, "exam", revid, exam_run_id=rid)
            got = pts * sum(x["score"] for x in results) / max(1, len(ex["parts"]))
            details["grading"][eid] = {"status": "done", "points": round(got, 2), "max": pts, "review_id": revid, "results": results}
        else:
            got = 0
            details["grading"][eid] = {"status": "fehler", "points": 0, "max": pts}
        db.update("exam_runs", rid, score=(r["score"] or 0) + got, details=details)


# ───────────── admin API ─────────────

def S() -> str:
    return CFG.student_user


@app.get("/api/admin/overview")
def admin_overview(w: Who = Depends(admin_only)):
    u = S()
    d = progress.dashboard(u)
    last = db.q1("SELECT MAX(created_at) AS t FROM attempts WHERE user=?", u)["t"]
    act = db.q("SELECT day, seconds FROM activity WHERE user=? ORDER BY day DESC LIMIT 60", u)
    hint_rows = db.q("SELECT exercise_id, COUNT(*) AS n FROM hints WHERE user=? GROUP BY exercise_id", u)
    d.update({"last_activity": last, "activity": act, "errors": progress.error_stats(u),
              "hints_total": sum(r["n"] for r in hint_rows), "student": CFG.student_name,
              "chat_count": db.q1("SELECT COUNT(*) AS n FROM chats WHERE user=?", u)["n"],
              "disagreements": db.q1("SELECT COUNT(*) AS n FROM attempts WHERE user=? AND admin_note IS NOT NULL", u)["n"],
              "exam_runs": db.q("SELECT id, exam_id, started_at, score, max_score, details FROM exam_runs WHERE user=? AND finished_at IS NOT NULL ORDER BY id DESC", u)})
    for r in d["exam_runs"]:
        r["title"] = db.loads(r.pop("details"), {}).get("title")
    return progress.json_safe(d)


@app.get("/api/admin/history")
def admin_history(days: int = 45, w: Who = Depends(admin_only)):
    return progress.history(S(), min(days, 120))


@app.get("/api/admin/attempts")
def admin_attempts(skill: str | None = None, only_wrong: bool = False, limit: int = 100, offset: int = 0,
                   w: Who = Depends(admin_only)):
    rows = db.q("SELECT * FROM attempts WHERE user=? ORDER BY id DESC LIMIT ? OFFSET ?", S(), 2000, 0)
    c = content()
    out = []
    for r in rows:
        r["skills"] = db.loads(r["skills"], [])
        if skill and (not r["skills"] or r["skills"][0] != skill):
            continue
        if only_wrong and r["correct"]:
            continue
        ex = c.get(r["exercise_id"])
        r["title"] = ex["title"] if ex else r["exercise_id"]
        out.append(r)
    return out[offset: offset + limit]


@app.get("/api/admin/attempt/{aid}")
def admin_attempt(aid: int, w: Who = Depends(admin_only)):
    r = db.q1("SELECT * FROM attempts WHERE id=?", aid)
    if not r:
        raise HTTPException(404)
    r["skills"] = db.loads(r["skills"], [])
    ex = content().get(r["exercise_id"])
    out = {"attempt": r, "exercise": public_exercise(ex, reveal=True) if ex else None}
    if r["review_id"]:
        rv = db.q1("SELECT * FROM reviews WHERE id=?", r["review_id"])
        rv["result"] = db.loads(rv["result"], {})
        rv["photo_ids"] = db.loads(rv["photo_ids"], [])
        out["review"] = rv
    out["hints"] = db.q("SELECT level, created_at FROM hints WHERE user=? AND exercise_id=? AND part=?", r["user"], r["exercise_id"], r["part"])
    out["chats"] = db.q("SELECT id, title, kind, updated_at FROM chats WHERE user=? AND exercise_id=?", r["user"], r["exercise_id"])
    return out


@app.post("/api/admin/attempt/{aid}/override")
async def admin_override(aid: int, request: Request, w: Who = Depends(admin_only)):
    body = await request.json()
    r = db.q1("SELECT * FROM attempts WHERE id=?", aid)
    if not r:
        raise HTTPException(404)
    correct = bool(body.get("correct"))
    db.update("attempts", aid, correct=1 if correct else 0, score=float(body.get("score", 1.0 if correct else 0.0)),
              status="richtig" if correct else "falsch", error_category=None if correct else body.get("error_category"),
              admin_note=body.get("note") or f"vom Coach korrigiert ({w.user})", source=r["source"])
    return {"ok": True}


@app.get("/api/admin/struggles")
def admin_struggles(w: Who = Depends(admin_only)):
    u = S()
    c = content()
    sm = progress.skill_mastery(u)
    es = progress.error_stats(u)
    wrong = db.q("SELECT exercise_id, part, input, error_category, feedback, skills, created_at, id FROM attempts "
                 "WHERE user=? AND correct=0 ORDER BY id DESC LIMIT 400", u)
    by_skill: dict[str, list] = {}
    for r in wrong:
        s = (db.loads(r["skills"], []) or [None])[0]
        by_skill.setdefault(s, []).append(r)
    skills = []
    for sid, v in sm.items():
        if not v["n"]:
            continue
        ws = by_skill.get(sid, [])
        repeat = {}
        for r in ws:
            repeat[r["exercise_id"]] = repeat.get(r["exercise_id"], 0) + 1
        skills.append({"skill": sid, "title": c.skills[sid]["title"], "chapter": c.skills[sid]["chapter"], **v,
                       "wrong": len(ws), "errors": es["by_skill"].get(sid, {}),
                       "recent_wrong": [{**r, "title": (c.get(r["exercise_id"]) or {}).get("title")} for r in ws[:5]],
                       "repeat_fail": [k for k, n in repeat.items() if n >= 2]})
    skills.sort(key=lambda s: s["mastery"])
    chall = progress.challenge_list(u)
    for ch in chall:
        ex = c.get(ch["exercise_id"])
        ch["exercise"] = public_exercise(ex, reveal=True) if ex else None
        ch["inputs"] = db.q("SELECT input, status, error_category, feedback, source, review_id, created_at FROM attempts "
                            "WHERE user=? AND exercise_id=? AND part=? ORDER BY id", u, ch["exercise_id"], ch["part"])
    return {"skills": skills, "errors": es["categories"], "error_titles": c.error_categories, "challenges": chall}


def briefing_data(since: float | None = None) -> dict:
    u = S()
    c = content()
    last_session = db.q1("SELECT * FROM sessions WHERE ended_at IS NOT NULL ORDER BY ended_at DESC LIMIT 1")
    since = since or (last_session["ended_at"] if last_session else time.time() - 21 * 86400)
    rows = db.q("SELECT * FROM attempts WHERE user=? AND created_at>=? ORDER BY id", u, since)
    sm_now = progress.skill_mastery(u)
    sm_then = progress.skill_mastery(u, until=since)
    changes = []
    for sid, v in sm_now.items():
        d = v["mastery"] - sm_then[sid]["mastery"]
        if abs(d) >= 0.05 or (v["n"] and v["mastery"] < 0.5):
            changes.append({"skill": sid, "title": c.skills[sid]["title"], "before": sm_then[sid]["mastery"], "now": v["mastery"], "n": v["n"]})
    changes.sort(key=lambda x: x["now"])
    wrong = [r for r in rows if not r["correct"] and r["status"] != "format"]
    failed = {}
    for r in wrong:
        k = (r["exercise_id"], r["part"])
        ex = c.get(r["exercise_id"])
        failed.setdefault(k, {"exercise_id": r["exercise_id"], "part": r["part"], "title": ex["title"] if ex else r["exercise_id"],
                              "skill": (db.loads(r["skills"], []) or [None])[0], "inputs": [], "errors": [], "feedback": []})
        failed[k]["inputs"].append(r["input"])
        if r["error_category"]:
            failed[k]["errors"].append(r["error_category"])
        if r["feedback"]:
            failed[k]["feedback"].append(r["feedback"])
    weakest = [x for x in sorted(sm_now.items(), key=lambda kv: kv[1]["mastery"]) if x[1]["n"]][:3]
    if len(weakest) < 3:
        weakest += [x for x in sm_now.items() if not x[1]["n"]][: 3 - len(weakest)]
    suggestions = []
    rng = random.Random(int(since))
    for sid, _ in weakest:
        for _ in range(2):
            ex = c.pick(skill=sid, prefer="course", rng=rng)
            if ex and ex["id"] not in [s["id"] for s in suggestions]:
                suggestions.append({"id": ex["id"], "title": ex["title"], "skill": sid, "skill_title": c.skills[sid]["title"]})
    chats = db.q("SELECT id, title, kind, updated_at FROM chats WHERE user=? AND updated_at>=? ORDER BY updated_at DESC", u, since)
    explain_back = db.q("SELECT m.content, m.created_at FROM messages m JOIN chats ch ON ch.id=m.chat_id "
                        "WHERE ch.user=? AND m.created_at>=? AND m.role='user' AND m.meta LIKE '%explain_back%'", u, since)
    return {
        "since": since,
        "student": CFG.student_name,
        "dates": progress.dates(),
        "stats": {"parts": len(rows), "correct": sum(1 for r in rows if r["correct"]),
                  "minutes": round(sum(r["duration_s"] or 0 for r in rows) / 60),
                  "days_active": len({progress.today(r["created_at"]) for r in rows}),
                  "hints": db.q1("SELECT COUNT(*) AS n FROM hints WHERE user=? AND created_at>=?", u, since)["n"],
                  "solutions_shown": sum(1 for r in rows if r["solution_shown"])},
        "skill_changes": changes,
        "errors": progress.error_stats(u, since)["categories"],
        "error_titles": c.error_categories,
        "failed": list(failed.values())[:30],
        "challenges_open": [{"title": ch["title"], "skill": ch["skill_title"], "fails": ch["fails"], "wins": ch["wins"]}
                            for ch in progress.challenge_list(u) if ch["status"] == "open"],
        "suggestions": suggestions,
        "chats": chats,
        "explain_back": explain_back[:10],
        "chapters": progress.chapter_mastery(sm_now),
        "readiness": progress.exam_readiness(progress.chapter_mastery(sm_now)),
    }


@app.get("/api/admin/briefing")
def admin_briefing(w: Who = Depends(admin_only)):
    return progress.json_safe(briefing_data())


@app.get("/api/admin/sessions")
def admin_sessions(w: Who = Depends(admin_only)):
    rows = db.q("SELECT * FROM sessions ORDER BY date")
    for r in rows:
        if r["started_at"]:
            end = r["ended_at"] or time.time()
            r["stats"] = db.q1("SELECT COUNT(*) AS n, SUM(correct) AS ok FROM attempts WHERE user=? AND created_at BETWEEN ? AND ?",
                               S(), r["started_at"], end)
    return rows


@app.post("/api/admin/sessions")
async def admin_session_upsert(request: Request, w: Who = Depends(admin_only)):
    b = await request.json()
    fields = {k: b[k] for k in ("title", "date", "notes", "plan") if k in b}
    if b.get("action") == "start":
        fields["started_at"] = time.time()
    if b.get("action") == "end":
        fields["ended_at"] = time.time()
    if b.get("id"):
        db.update("sessions", int(b["id"]), **fields)
        return {"id": b["id"]}
    return {"id": db.insert("sessions", created_at=time.time(), **fields)}


@app.get("/api/admin/assignments")
def admin_assignments(w: Who = Depends(admin_only)):
    return assignments_for(S())


@app.post("/api/admin/assignments")
async def admin_assignment_upsert(request: Request, w: Who = Depends(admin_only)):
    b = await request.json()
    fields = {k: b[k] for k in ("title", "description", "skills", "exercise_ids", "target", "due_at", "archived") if k in b}
    if b.get("id"):
        db.update("assignments", int(b["id"]), **fields)
        return {"id": b["id"]}
    return {"id": db.insert("assignments", created_at=time.time(), **fields)}


@app.get("/api/admin/settings")
def admin_settings(w: Who = Depends(admin_only)):
    return {"dates": progress.dates(), "notify_enabled": db.get_setting("notify_enabled", True),
            "telegram": bool(CFG.telegram_token and CFG.telegram_chat),
            "chapter_weights": db.get_setting("chapter_weights") or progress.DEFAULT_WEIGHTS,
            "daily_goal": db.get_setting("daily_goal", 10),
            "student": CFG.student_user, "model": CFG.model}


@app.post("/api/admin/settings")
async def admin_settings_set(request: Request, w: Who = Depends(admin_only)):
    b = await request.json()
    for k in ("session_dates", "exam_date", "notify_enabled", "chapter_weights", "daily_goal"):
        if k in b:
            db.set_setting(k, b[k])
    if b.get("test_telegram"):
        notify.send("✅ Testnachricht vom Mathe-Trainer.")
    return {"ok": True}


# ───────────── error reports ("Fehler melden") ─────────────

REPORT_KINDS = {
    "aufgabe": "Aufgabe unklar oder fehlerhaft",
    "loesung": "Lösung / Lösungsweg falsch",
    "antwort": "Richtige Antwort wird nicht akzeptiert",
    "darstellung": "Darstellung / Formel kaputt",
    "abbildung": "Abbildung fehlt oder falsch",
    "anderes": "Anderes",
}


def _report_target(eid: str) -> dict | None:
    """An exercise, or a formula card reported as "card:<id>" (shaped like an exercise without parts)."""
    if eid.startswith("card:"):
        k = content().cards.get(eid[5:])
        return {"id": eid, "title": f"Formelkarte «{k['name']}»", "parts": [], "source": {"doc": "Formelkarte", "ref": k.get("topic")}} if k else None
    return content().get(eid)


def _exercise_key(eid: str) -> str:
    p = generators.parse_id(eid)
    return f"gen:{p[0]}" if p else eid


@app.post("/api/exercise/{eid}/report")
async def report_error(eid: str, request: Request, w: Who = Depends(who)):
    b = await request.json()
    ex = _report_target(eid)
    if not ex:
        raise HTTPException(404)
    kind = b.get("kind") if b.get("kind") in REPORT_KINDS else "anderes"
    part = b.get("part") or ""
    last = db.q("SELECT part, input, status, created_at FROM attempts WHERE user=? AND exercise_id=? ORDER BY id DESC LIMIT 5", w.user, eid)
    context = {"attempts": last, "client": b.get("context") or {}, "source": ex.get("source"), "title": ex.get("title")}
    if kind == "antwort":
        for p in ex["parts"]:
            if (p.get("label") or "") == part or (not part and len(ex["parts"]) == 1):
                inp = (b.get("context") or {}).get("input") or next((a["input"] for a in last if a["part"] == (p.get("label") or "")), None)
                context["expected"] = describe_expected(p["answer"])
                if inp:
                    context["checker"] = check(p["answer"], inp, ex.get("skills")).as_dict()
                    context["input"] = inp
    rid = db.insert("reports", user=w.user, exercise_id=eid, part=part, kind=kind, comment=(b.get("comment") or "")[:2000],
                    context=context, status="offen", created_at=time.time())
    if w.user == CFG.student_user:
        await asyncio.to_thread(notify.send, f"🐞 {CFG.student_name} meldet einen Fehler: <b>{ex['title']}</b>{f' ({part})' if part else ''}\n"
                                f"{REPORT_KINDS[kind]}{': ' + b['comment'][:200] if b.get('comment') else ''}\n{notify.link('/admin#/fehler')}")
    return {"id": rid, "message": "Danke! Die Meldung ist beim Coach angekommen."}


@app.get("/api/admin/reports")
def admin_reports(w: Who = Depends(admin_only)):
    c = content()
    disabled = set(db.get_setting("disabled_exercises", []) or [])
    rows = db.q("SELECT * FROM reports ORDER BY status='offen' DESC, id DESC LIMIT 300")
    for r in rows:
        r["context"] = db.loads(r["context"], {})
        ex = _report_target(r["exercise_id"])
        r["title"] = ex["title"] if ex else r["exercise_id"]
        r["kind_title"] = REPORT_KINDS.get(r["kind"], r["kind"])
        r["disabled"] = _exercise_key(r["exercise_id"]) in disabled
        r["generated"] = r["exercise_id"].startswith("gen-")
    return {"items": rows, "kinds": REPORT_KINDS, "open": sum(1 for r in rows if r["status"] == "offen")}


@app.post("/api/admin/reports/{rid}")
async def admin_report_update(rid: int, request: Request, w: Who = Depends(admin_only)):
    b = await request.json()
    r = db.q1("SELECT * FROM reports WHERE id=?", rid)
    if not r:
        raise HTTPException(404)
    fields = {}
    if b.get("status") in ("offen", "erledigt", "abgelehnt"):
        fields["status"] = b["status"]
        fields["resolved_at"] = time.time() if b["status"] != "offen" else None
    if "admin_note" in b:
        fields["admin_note"] = b["admin_note"]
    if fields:
        db.update("reports", rid, **fields)
    if "disable" in b:
        key = _exercise_key(r["exercise_id"])
        cur = set(db.get_setting("disabled_exercises", []) or [])
        cur = cur | {key} if b["disable"] else cur - {key}
        db.set_setting("disabled_exercises", sorted(cur))
    return {"ok": True}


@app.get("/api/admin/chats")
def admin_chats(w: Who = Depends(admin_only)):
    return db.q("SELECT c.id, c.title, c.kind, c.exercise_id, c.updated_at, COUNT(m.id) AS n FROM chats c "
                "LEFT JOIN messages m ON m.chat_id=c.id WHERE c.user=? GROUP BY c.id ORDER BY c.updated_at DESC LIMIT 200", S())


@app.get("/api/admin/coach_chats")
def admin_coach_chats(w: Who = Depends(admin_only)):
    return db.q("SELECT id, title, updated_at FROM chats WHERE user=? AND kind='admin' ORDER BY updated_at DESC", w.user)


@app.get("/api/admin/exercises")
def admin_exercises(q: str = "", chapter: str | None = None, skill: str | None = None, w: Who = Depends(admin_only)):
    c = content()
    st = exercise_status(S())
    out = []
    for e in c.exercises.values():
        if chapter and e["chapter"] != chapter:
            continue
        if skill and skill not in e.get("skills", []):
            continue
        if q and q.lower() not in (e["title"] + " " + e["statement"] + " " + e["id"]).lower():
            continue
        out.append({"id": e["id"], "title": e["title"], "source": e["source"], "chapter": e["chapter"], "skills": e["skills"],
                    "difficulty": e.get("difficulty"), "calculator": e.get("calculator"), "status": st.get(e["id"], "neu"),
                    "note": e.get("note")})
    return {"items": out[:500], "generators": generators.catalogue(), "total": len(out)}


@app.post("/api/admin/reload")
def admin_reload(w: Who = Depends(admin_only)):
    reload()
    return {"exercises": len(content().exercises)}


@app.exception_handler(HTTPException)
async def http_exc(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/") or exc.status_code not in (401, 403):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
    return Response(f"<h1>{exc.status_code}</h1><p>{exc.detail}</p>", status_code=exc.status_code, media_type="text/html")


def run():
    import uvicorn
    # No proxy headers: the app never needs the client address, and trusting X-Forwarded-* from every
    # peer would let any container spoof it.
    uvicorn.run("mathtutor.main:app", host="0.0.0.0", port=int(os.environ.get("MT_PORT", "8080")),
                proxy_headers=False, log_level="info")


if __name__ == "__main__":
    run()
