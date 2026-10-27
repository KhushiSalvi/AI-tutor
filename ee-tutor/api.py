"""FastAPI backend for the React UI.  Run from the project root:  uvicorn api:app --port 8000"""
import json
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import uuid

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from core.answer_extras import search_images


import os
from pathlib import Path


def _load_env(path=Path(__file__).parent / ".env"):
    """Read KEY=VALUE lines from .env into os.environ (real environment variables win)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        val = val.strip()
        if val[:1] in "\"'" and val[-1:] == val[:1] and len(val) > 1:
            val = val[1:-1]
        else:
            val = val.split(" #")[0].strip()
        os.environ.setdefault(key.strip(), val)


_load_env()

from core import llm, tutor

CHATS_FILE = Path("data/chats.json")
MAX_CHATS = 30
LOCK = threading.Lock()
CANCELLED = set()  # request ids the user pressed Stop on


def load():
    try:
        return json.loads(CHATS_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return []


def save(chats):
    CHATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHATS_FILE.write_text(json.dumps(chats[:MAX_CHATS], ensure_ascii=False, default=str), encoding="utf-8")


@asynccontextmanager
async def lifespan(app):
    print("Loading search models...")
    tutor.get_retriever()
    print("Ready.")
    yield


app = FastAPI(lifespan=lifespan)


class ChatIn(BaseModel):
    chat_id: int | None = None
    content: str | None = None
    level: str = "beginner"
    regenerate: bool = False
    rid: str | None = None  # id of this request, lets the UI cancel it


@app.get("/api/status")
def status():
    ok = llm.llm_ready()
    model = ""
    if ok:
        model = llm.GEMINI_MODEL if llm.PROVIDER == "gemini" else llm.OLLAMA_MODEL
    return {"llm_ready": ok, "provider": llm.PROVIDER, "model": model, "help": "" if ok else llm.llm_help()}


@app.get("/api/chats")
def list_chats():
    with LOCK:
        return [{"id": c["id"], "title": c["title"], "ts": c["ts"]} for c in load() if c["messages"]]


@app.get("/api/chats/{cid}")
def get_chat(cid: int):
    with LOCK:
        c = next((x for x in load() if x["id"] == cid), None)
    if not c:
        raise HTTPException(404, "Chat not found")
    return c


@app.delete("/api/chats/{cid}")
def delete_chat(cid: int):
    with LOCK:
        save([c for c in load() if c["id"] != cid])
    return {"ok": True}


@app.post("/api/chat")
def chat(body: ChatIn):
    text = (body.content or "").strip()
    with LOCK:
        chats = load()
        c = next((x for x in chats if x["id"] == body.chat_id), None)
        if c is None:
            if body.regenerate or not text:
                raise HTTPException(400, "Nothing to answer")
            c = {"id": int(time.time() * 1000), "title": text[:50], "ts": "", "messages": []}
            chats.insert(0, c)
        if body.regenerate:
            while c["messages"] and c["messages"][-1]["role"] == "assistant":
                c["messages"].pop()
            if not c["messages"]:
                raise HTTPException(400, "Nothing to regenerate")
        elif text:
            c["messages"].append({"role": "user", "content": text})
        else:
            raise HTTPException(400, "Empty message")
        save(chats)
        cid, msgs = c["id"], list(c["messages"])

    try:  # slow part runs outside the lock
        res = tutor.respond(msgs, body.level)
    except Exception as e:
        msg = f"Something failed: {e}"
        if "429" in str(e) or "quota" in str(e).lower():
            msg += " (looks like a free-tier rate limit; wait a minute and ask again)"
        res = {"mode": "error", "error": msg}

    if body.rid and body.rid in CANCELLED:  # user pressed Stop: throw the answer (and the question) away
        CANCELLED.discard(body.rid)
        with LOCK:
            chats = load()
            c = next((x for x in chats if x["id"] == cid), None)
            if c is not None and text and not body.regenerate:
                for i in range(len(c["messages"]) - 1, -1, -1):
                    if c["messages"][i]["role"] == "user" and c["messages"][i]["content"] == text:
                        del c["messages"][i]
                        break
                save(chats)
        return {"chat_id": cid, "cancelled": True}

    message = {"role": "assistant", "res": res}
    with LOCK:
        chats = load()
        c = next((x for x in chats if x["id"] == cid), None)
        if c is not None:
            c["messages"].append(message)
            c["ts"] = time.strftime("%d %b %H:%M")
            chats.remove(c)
            chats.insert(0, c)
            save(chats)
    return {"chat_id": cid, "message": message}


class CancelIn(BaseModel):
    rid: str


@app.post("/api/chat/cancel")
def cancel_chat(body: CancelIn):
    CANCELLED.add(body.rid)
    if len(CANCELLED) > 200:  # keep it tiny
        CANCELLED.clear()
        CANCELLED.add(body.rid)
    return {"ok": True}


@app.get("/api/figure")
def figure(source_id: str, fig: str, near: int):
    pdf = tutor.find_pdf(source_id)
    out = tutor.crop_figure(pdf, fig, near, tutor.info(source_id)["offset"]) if pdf else None
    if not out:
        raise HTTPException(404, "Figure not found")
    return Response(out["png"], media_type="image/png", headers={"Cache-Control": "max-age=86400"})


@app.get("/api/page")
def page(source_id: str, pdf_page: int):
    pdf = tutor.find_pdf(source_id)
    if not pdf:
        raise HTTPException(404, "PDF not found")
    return Response(tutor.page_image(pdf, pdf_page), media_type="image/png")


class VideoIn(BaseModel):
    content: str
    level: str = "beginner"
    chat_id: int | None = None


@app.post("/api/video")
def create_video(body: VideoIn):
    text = (body.content or "").strip()
    if not text:
        raise HTTPException(400, "Empty topic")
    job_id = uuid.uuid4().hex[:12]
    thread = threading.Thread(target=tutor.start_video_job, args=(job_id, text, body.level), daemon=True)
    thread.start()
    with LOCK:  # save the request + video card into chat history so it survives refresh/restart
        chats = load()
        c = next((x for x in chats if x["id"] == body.chat_id), None)
        if c is None:
            c = {"id": int(time.time() * 1000), "title": text[:50], "ts": "", "messages": []}
            chats.insert(0, c)
        c["messages"].append({"role": "user", "content": text})
        c["messages"].append({"role": "assistant", "video": {"jobId": job_id, "topic": text}})
        c["ts"] = time.strftime("%d %b %H:%M")
        chats.remove(c)
        chats.insert(0, c)
        save(chats)
    return {"job_id": job_id, "chat_id": c["id"]}


@app.get("/api/video/{job_id}")
def video_status(job_id: str):
    status = tutor.get_video_job(job_id)
    if status is None:
        raise HTTPException(404, "No such video job")
    result = dict(status)
    if result["status"] == "done":
        result["url"] = f"/api/video/{job_id}/file"
    return result


@app.get("/api/video/{job_id}/file")
def video_file(job_id: str):
    path = tutor.VIDEO_DIR / f"{job_id}.mp4"
    if not path.exists():
        raise HTTPException(404, "Video not ready")
    return FileResponse(path, media_type="video/mp4")

from core.answer_extras import search_images


@app.get("/api/webimages")
def webimages(q: str):
    return search_images(q)