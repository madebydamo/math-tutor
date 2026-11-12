"""Agent runner: a small HTTP service inside the isolated agent container.

The web app sends one tutor turn; this service runs Claude Code headless
(`claude -p`) with only the math MCP tools enabled (no shell, no files, no web),
and streams the result back as NDJSON lines:

  {"t": "text", "d": "..."}                 text delta
  {"t": "tool", "name": "python"}            a tool started (UI shows "rechnet…")
  {"t": "image", "name": "...", "data": "<base64 png>"}
  {"t": "review", "data": {...}}             correction result (submit_review)
  {"t": "done", "session": "...", "text": "...", "cost": 0.01}
  {"t": "error", "message": "..."}
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import pathlib
import shutil
import sys
import tempfile
import uuid

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

TOKEN = os.environ.get("MT_AGENT_TOKEN", "")
CLAUDE = os.environ.get("MT_CLAUDE_BIN", "claude")
WORK = pathlib.Path(os.environ.get("MT_AGENT_WORK", "/tmp/mt-agent"))
MAX_PARALLEL = int(os.environ.get("MT_AGENT_PARALLEL", "2"))
TOOLS = ["mcp__math__python", "mcp__math__check_answer", "mcp__math__equivalent", "mcp__math__plot", "mcp__math__submit_review"]

app = FastAPI(title="mathtutor-agent")
sem = asyncio.Semaphore(MAX_PARALLEL)


def _auth(tok: str | None):
    if not TOKEN or tok != f"Bearer {TOKEN}":
        raise HTTPException(401, "unauthorized")


@app.get("/health")
async def health():
    return {"ok": True, "auth": bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")
                                     or (pathlib.Path.home() / ".claude" / ".credentials.json").exists())}


@app.post("/run")
async def run(request: Request, authorization: str | None = Header(None)):
    _auth(authorization)
    body = await request.json()
    return StreamingResponse(_run(body), media_type="application/x-ndjson")


def _line(obj) -> bytes:
    return (json.dumps(obj, ensure_ascii=False) + "\n").encode()


async def _run(body: dict):
    async with sem:
        run_dir = pathlib.Path(tempfile.mkdtemp(prefix="run-", dir=WORK if WORK.exists() else None))
        review_path = run_dir / "review.json"
        mcp_cfg = run_dir / "mcp.json"
        mcp_cfg.write_text(json.dumps({"mcpServers": {"math": {
            "type": "stdio", "command": sys.executable, "args": ["-m", "mathtutor.mcp_math"],
            "env": {"MT_RUN_DIR": str(run_dir / "py"), "MT_REVIEW_OUT": str(review_path),
                    "PYTHONPATH": os.environ.get("PYTHONPATH", ""), "PATH": os.environ.get("PATH", "")},
        }}}))
        args = [CLAUDE, "-p", "--verbose", "--output-format", "stream-json", "--input-format", "stream-json",
                "--include-partial-messages", "--model", body.get("model") or "claude-opus-5-5",
                "--mcp-config", str(mcp_cfg), "--strict-mcp-config",
                "--tools", "", "--allowedTools", ",".join(TOOLS),
                "--permission-mode", "dontAsk", "--setting-sources", "",
                "--max-turns", str(body.get("max_turns", 25)),
                "--system-prompt", body.get("system", "")]
        if body.get("session"):
            args += ["--resume", body["session"]]
        else:
            args += ["--session-id", str(uuid.uuid4())]
        msg = {"type": "user", "message": {"role": "user", "content": body.get("content") or []}}
        env = {k: v for k, v in os.environ.items() if k not in ("MT_AGENT_TOKEN",)}
        env.update({"DISABLE_AUTOUPDATER": "1", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "DISABLE_TELEMETRY": "1"})
        try:
            proc = await asyncio.create_subprocess_exec(*args, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.PIPE, cwd=run_dir, env=env, limit=2**24)
        except FileNotFoundError:
            yield _line({"t": "error", "message": "Claude Code ist im Agent-Container nicht installiert."})
            return
        proc.stdin.write((json.dumps(msg) + "\n").encode())
        await proc.stdin.drain()
        proc.stdin.close()
        session, final_text, cost, got_text = body.get("session"), "", None, False
        streamed = []
        try:
            async for raw in proc.stdout:
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                typ = ev.get("type")
                if typ == "system" and ev.get("session_id"):
                    session = ev["session_id"]
                elif typ == "stream_event":
                    e = ev.get("event", {})
                    if e.get("type") == "content_block_delta" and e.get("delta", {}).get("type") == "text_delta":
                        got_text = True
                        streamed.append(e["delta"]["text"])
                        yield _line({"t": "text", "d": e["delta"]["text"]})
                    elif e.get("type") == "content_block_start" and e.get("content_block", {}).get("type") == "tool_use":
                        yield _line({"t": "tool", "name": e["content_block"].get("name", "").replace("mcp__math__", "")})
                    elif e.get("type") == "message_start" and streamed:
                        # a new assistant message after tool use: separate paragraphs
                        streamed.append("\n\n")
                        yield _line({"t": "text", "d": "\n\n"})
                elif typ == "assistant" and not got_text:
                    for block in ev.get("message", {}).get("content", []):
                        if block.get("type") == "text":
                            streamed.append(block["text"])
                            yield _line({"t": "text", "d": block["text"]})
                elif typ == "result":
                    session = ev.get("session_id", session)
                    final_text = ev.get("result") or ""
                    cost = ev.get("total_cost_usd")
                    if ev.get("is_error") or "not logged in" in final_text.lower():
                        yield _line({"t": "error", "message": _explain(final_text or ev.get("subtype", "Fehler"))})
            await proc.wait()
            if proc.returncode and not final_text:
                err = (await proc.stderr.read()).decode(errors="replace")[-1500:]
                yield _line({"t": "error", "message": _explain(err)})
            imgs = run_dir / "py" / "bilder"
            if imgs.exists():
                for f in sorted(imgs.glob("*.png"))[:8]:
                    if f.stat().st_size < 3_000_000:
                        yield _line({"t": "image", "name": f.name, "data": base64.b64encode(f.read_bytes()).decode()})
            if review_path.exists():
                try:
                    yield _line({"t": "review", "data": json.loads(review_path.read_text())})
                except json.JSONDecodeError:
                    pass
            yield _line({"t": "done", "session": session, "text": "".join(streamed) or final_text, "cost": cost})
        finally:
            if proc.returncode is None:
                proc.kill()
            shutil.rmtree(run_dir, ignore_errors=True)


def _explain(stderr: str) -> str:
    low = stderr.lower()
    if "login" in low or "logged in" in low or "auth" in low or "401" in low or "api key" in low:
        return "Der Tutor ist nicht angemeldet. Bitte im Neo-Admin den Claude-Token hinterlegen."
    return "Der Tutor hatte einen Fehler: " + stderr.strip()[-400:]


@app.exception_handler(HTTPException)
async def _http_exc(_, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


def main():
    import uvicorn
    WORK.mkdir(parents=True, exist_ok=True)
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("MT_AGENT_PORT", "8100")), log_level="info")


if __name__ == "__main__":
    main()
