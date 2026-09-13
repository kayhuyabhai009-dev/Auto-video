"""Auto Video Producer — API server."""
import json as _json
import os, re, threading, time, traceback, urllib.parse
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import paths, settings, asset_library, tts, pipeline, projects, renderer, subtitles as subs_engine
from . import motion_graphics as mg
from .util import read_json, write_json, probe, new_id

app = FastAPI(title="Auto Video Producer", version="1.0")

JOBS = {}          # project_id -> {"stage","lines":[],"done","ok","error","started"}
_jobs_lock = threading.Lock()


@app.on_event("startup")
def startup():
    paths.ensure_dirs()
    settings.load()
    if settings.get("assets.auto_scan_on_start", True):
        threading.Thread(target=asset_library.scan, daemon=True).start()


# ------------------------------------------------------------------ static
@app.get("/")
def index():
    return FileResponse(os.path.join(paths.STATIC_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=paths.STATIC_DIR), name="static")


def _serve_media(path: str, content_type: str = None):
    if not os.path.isfile(path):
        raise HTTPException(404)
    ct = content_type or {
        ".mp4": "video/mp4", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".webp": "image/webp", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ass": "text/plain; charset=utf-8",
        ".txt": "text/plain; charset=utf-8", ".json": "application/json", ".srt": "text/plain; charset=utf-8",
    }.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
    return FileResponse(path, media_type=ct)


@app.get("/media/{path:path}")
def media(path: str, request: Request):
    path = os.path.normpath(urllib.parse.unquote(path)).replace("\\", "/")
    if path.startswith(("..", "/")):
        raise HTTPException(403)
    full = os.path.join(paths.ROOT, path)
    if not os.path.isfile(full):
        raise HTTPException(404)
    ct = {"mp4": "video/mp4", "m4v": "video/mp4", "webm": "video/webm", "jpg": "image/jpeg",
          "jpeg": "image/jpeg", "png": "image/png", "mp3": "audio/mpeg", "wav": "audio/wav",
          "m4a": "audio/mp4", "flac": "audio/flac", "ogg": "audio/ogg",
          "ass": "text/plain; charset=utf-8", "srt": "text/plain; charset=utf-8",
          "txt": "text/plain; charset=utf-8", "json": "application/json"}.get(
        os.path.splitext(full)[1].lower().lstrip("."), "application/octet-stream")
    range_header = request.headers.get("range")
    if range_header and ct.startswith(("video/", "audio/")):
        m = re.search(r"bytes=(\d*)-(\d*)", range_header)
        size = os.path.getsize(full)
        start = int(m.group(1) or 0)
        end = int(m.group(2) or size - 1)
        end = min(end, size - 1)
        chunk = 2 * 1024 * 1024
        end = min(end, start + chunk - 1)
        with open(full, "rb") as f:
            f.seek(start)
            data = f.read(end - start + 1)
        return Response(data, status_code=206, media_type=ct, headers={
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Accept-Ranges": "bytes", "Content-Length": str(len(data))})
    return FileResponse(full, media_type=ct, headers={"Accept-Ranges": "bytes"})


# ------------------------------------------------------------------ library
@app.post("/api/library/scan")
def scan_library():
    t0 = time.time()
    res = asset_library.scan()
    return {"ok": True, "total": res["total"], "seconds": round(time.time() - t0, 1)}


@app.get("/api/assets")
def list_assets(kind: str = None, tag: str = None, q: str = "", limit: int = 500):
    items = asset_library.search(q, kind=kind, tag=tag, limit=limit)
    slim = [{k: a.get(k) for k in ("asset_id", "filename", "type", "category", "duration", "width",
                                   "height", "aspect_ratio", "orientation", "tags", "semantic_tags",
                                   "source", "license_status", "usage_count", "quality", "enabled")}
            | {"rel_path": a["rel_path"]} for a in items]
    return {"assets": slim, "total": len(slim), "all_tags": asset_library.all_tags()}


@app.get("/api/assets/{asset_id}")
def get_asset(asset_id: str):
    a = asset_library.get(asset_id)
    if not a:
        raise HTTPException(404)
    return a


@app.patch("/api/assets/{asset_id}")
def patch_asset(asset_id: str, body: dict):
    try:
        a = asset_library.save_manual_meta(asset_id, body)
    except KeyError:
        raise HTTPException(404)
    return a


@app.get("/api/assets/{asset_id}/thumb")
def asset_thumb(asset_id: str):
    a = asset_library.get(asset_id)
    if not a:
        raise HTTPException(404)
    thumb_dir = os.path.join(paths.DATA_DIR, "thumbs")
    os.makedirs(thumb_dir, exist_ok=True)
    tp = os.path.join(thumb_dir, asset_id + ".jpg")
    if not os.path.exists(tp):
        try:
            from .util import ffmpeg
            if a["type"] == "video":
                ffmpeg(["-ss", "1", "-i", a["path"], "-frames:v", "1", "-vf", "scale=480:-2", tp], timeout=60)
            elif a["type"] == "image":
                from PIL import Image
                im = Image.open(a["path"])
                im.thumbnail((480, 480))
                im.convert("RGB").save(tp, quality=80)
            else:
                raise HTTPException(404)
        except Exception:
            raise HTTPException(404)
    return FileResponse(tp, media_type="image/jpeg")


@app.post("/api/library/upload")
async def upload_asset(files: list[UploadFile] = File(...), category: str = Form("stock_images")):
    import shutil
    dest_dir = paths.asset_subdir(category if category in paths.ASSET_SUBDIRS else "stock_images")
    saved = []
    for f in files:
        dest = os.path.join(dest_dir, os.path.basename(f.filename or f"asset_{new_id()}"))
        with open(dest, "wb") as out:
            shutil.copyfileobj(f.file, out)
        saved.append(os.path.basename(dest))
    asset_library.scan()
    return {"ok": True, "saved": saved, "category": dest_dir and os.path.basename(dest_dir)}


# ------------------------------------------------------------------ settings
@app.get("/api/settings")
def get_settings():
    s = settings.load()
    st = tts.provider_status()
    return {"settings": s, "tts_status": st,
            "secrets_note": "API keys are read only from environment variables (never stored)."}


@app.post("/api/settings")
def set_settings(body: dict):
    s = settings.update(body)
    return {"ok": True, "settings": s}


@app.post("/api/tts/test")
def tts_test(body: dict):
    text = body.get("text", "Human Systems Noir. This is a voice test.")
    out = os.path.join(paths.DATA_DIR, "tts_test.wav")
    res = tts.synthesize(text, out, force_provider=body.get("provider"))
    return {"ok": True, "duration": res["duration"], "provider": res["provider"],
            "url": "/media/" + os.path.relpath(out, paths.ROOT).replace(os.sep, "/"),
            "placeholder": res.get("placeholder", False)}


# ------------------------------------------------------------------ scripts
@app.post("/api/scripts")
async def upload_script(file: UploadFile = File(None), name: str = Form(""), text: str = Form("")):
    if file is not None:
        raw = (await file.read()).decode("utf-8", "replace")
        name = name or os.path.basename(file.filename or "script")
    else:
        raw = text
        name = name or "untitled"
    name = os.path.splitext(os.path.basename(name))[0]
    dest = os.path.join(paths.SCRIPTS_DIR, name + ".txt")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(raw)
    return {"ok": True, "name": name, "path": dest, "words": len(raw.split())}


@app.get("/api/scripts")
def list_scripts():
    out = []
    for fn in sorted(os.listdir(paths.SCRIPTS_DIR)):
        if fn.endswith(".txt"):
            p = os.path.join(paths.SCRIPTS_DIR, fn)
            txt = open(p, encoding="utf-8", errors="replace").read()
            out.append({"name": fn[:-4], "path": p, "words": len(txt.split()),
                        "chars": len(txt), "has_evidence_tags": "[[SOURCE" in txt})
    return {"scripts": out}


@app.get("/api/scripts/{name}")
def get_script(name: str):
    p = os.path.join(paths.SCRIPTS_DIR, os.path.basename(name) + ".txt")
    if not os.path.exists(p):
        raise HTTPException(404)
    return {"name": name, "text": open(p, encoding="utf-8", errors="replace").read()}


# ------------------------------------------------------------------ presets
@app.get("/api/presets")
def get_presets():
    return {"presets": pipeline.list_presets()}


@app.post("/api/presets/{name}/apply")
def apply_preset(name: str):
    preset = pipeline.apply_preset(name)
    return {"ok": True, "applied": name, "settings": settings.load()}


@app.post("/api/presets")
def save_preset(body: dict):
    name = body.get("name", "Custom")
    data = {"name": name, "description": body.get("description", "Custom preset"),
            "style": body.get("style", {})}
    for key in ("render", "subtitles", "music", "transitions", "effects", "motion_graphics",
                "asset_rules", "animation", "tts"):
        if key in body:
            data[key] = body[key]
    write_json(os.path.join(paths.PRESETS_DIR, name + ".json"), data)
    return {"ok": True, "saved": name}


# ------------------------------------------------------------------ motion graphics
@app.get("/api/motion_graphics/templates")
def mg_templates():
    return {"templates": mg.list_templates()}


@app.get("/api/motion_graphics/preview/{template}")
def mg_preview(template: str, title: str = "Sample headline for this card", kicker: str = ""):
    img = mg.render_graphic(template, {"title": title, "kicker": kicker or None})
    buf = _png_bytes(img)
    return Response(buf, media_type="image/png")


def _png_bytes(img):
    import io
    from PIL import Image
    b = io.BytesIO()
    bg = Image.new("RGB", img.size, (17, 19, 21))
    bg.paste(img, (0, 0), img)
    bg.save(b, "PNG")
    return b.getvalue()


# ------------------------------------------------------------------ projects
@app.post("/api/projects")
async def create_project(body: dict):
    title = body.get("title") or "untitled"
    script = body.get("script", "")
    source = body.get("narration_source", "tts_api")
    preset = body.get("preset")
    meta = projects.create(title, script, source, preset)
    if body.get("save_script") and script:
        with open(os.path.join(paths.SCRIPTS_DIR, os.path.basename(title)[:40] + ".txt"), "w") as f:
            f.write(script)
    return {"ok": True, "project": _proj_public(meta)}


def _proj_public(meta):
    m = {k: v for k, v in meta.items() if k != "dir"}
    m["final_url"] = "/media/projects/" + meta["project_id"] + "/final.mp4"
    m["poster_url"] = "/media/projects/" + meta["project_id"] + "/poster.jpg"
    m["subtitles_url"] = "/media/projects/" + meta["project_id"] + "/subtitles.ass"
    for s in (m.get("timeline") or {}).get("segments", []):
        s["preview_url"] = "/media/projects/" + meta["project_id"] + "/previews/scene_" + s["segment_id"] + ".jpg"
    if m.get("narration") and m["narration"].get("path"):
        m["narration"]["url"] = "/media/" + os.path.relpath(m["narration"]["path"], paths.ROOT).replace(os.sep, "/")
    return m


@app.get("/api/projects")
def list_projects():
    return {"projects": projects.list_projects()}


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    meta = projects.get(pid)
    if not meta:
        raise HTTPException(404)
    return _proj_public(meta)


@app.delete("/api/projects/{pid}")
def del_project(pid: str):
    projects.delete(pid)
    return {"ok": True}


@app.post("/api/projects/{pid}/script")
async def set_script(pid: str, body: dict):
    meta = projects.get(pid)
    if not meta:
        raise HTTPException(404)
    meta["script"] = body.get("script", meta.get("script", ""))
    if body.get("invalidate_narration"):
        meta["narration"] = None
    projects.save(meta)
    return {"ok": True}


@app.post("/api/projects/{pid}/narration_upload")
async def upload_narration(pid: str, file: UploadFile = File(...), kind: str = Form("auto")):
    """Upload PRE-GENERATED TTS (txt) or narration audio (wav/mp3/m4a/flac).
    The uploaded narration becomes MASTER — no TTS API call will be made."""
    import shutil
    meta = projects.get(pid)
    if not meta:
        raise HTTPException(404)
    ext = os.path.splitext(file.filename or "")[1].lower()
    tmp = os.path.join("/tmp", f"narr_{new_id()}" + ext)
    with open(tmp, "wb") as out:
        shutil.copyfileobj(file.file, out)
    if ext in (".txt", ".md", ".json") or kind == "text":
        kind_final = "text"
    elif ext in (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".opus") or kind == "audio":
        kind_final = "audio"
    else:
        raise HTTPException(400, f"unsupported narration file type: {ext}")
    projects.store_uploaded_narration(meta, tmp, kind_final)
    os.remove(tmp)
    return {"ok": True, "kind": kind_final, "project": _proj_public(meta)}


@app.post("/api/projects/{pid}/generate")
def generate(pid: str, body: dict = None):
    body = body or {}
    with _jobs_lock:
        if JOBS.get(pid, {}).get("running"):
            raise HTTPException(409, "generation already running for this project")
        JOBS[pid] = {"running": True, "stage": "starting", "lines": [], "done": False, "ok": None}

    def log(msg):
        job = JOBS.get(pid)
        if job is not None:
            job["lines"].append(f"{time.strftime('%H:%M:%S')}  {msg}")
            job["stage"] = msg if not msg.startswith(("unit", "render", "final", "assembled")) else job["stage"]
            job["lines"] = job["lines"][-500:]

    def run():
        try:
            res = pipeline.generate_video(pid, body, log_cb=log)
            JOBS[pid].update({"done": True, "ok": True, "result": res, "running": False, "stage": "done"})
        except Exception as e:
            log("ERROR: " + str(e))
            log(traceback.format_exc()[-1500:])
            JOBS[pid].update({"done": True, "ok": False, "error": str(e), "running": False,
                              "stage": "error"})
    threading.Thread(target=run, daemon=True).start()
    return {"ok": True, "job": "started"}


@app.get("/api/projects/{pid}/progress")
def progress(pid: str):
    with _jobs_lock:
        job = JOBS.get(pid) or {"running": False, "lines": [], "done": True, "ok": None, "stage": "idle"}
        return {"stage": job.get("stage"), "running": job.get("running", False),
                "done": job.get("done", False), "ok": job.get("ok"),
                "error": job.get("error"), "lines": job.get("lines", [])[-80:]}


@app.post("/api/projects/{pid}/regenerate_scene/{sid}")
def regen_scene(pid: str, sid: str, body: dict = None):
    meta = projects.get(pid)
    if not meta:
        raise HTTPException(404)
    seg = pipeline.regenerate_scene(pid, sid)
    # refresh that scene preview from the full render if available
    final = os.path.join(meta["dir"], "final.mp4")
    pv_dir = os.path.join(meta["dir"], "previews")
    os.makedirs(pv_dir, exist_ok=True)
    if os.path.exists(final):
        mid = (seg["start"] + seg["end"]) / 2
        from .util import ffmpeg
        try:
            ffmpeg(["-ss", f"{mid:.2f}", "-i", final, "-frames:v", "1", "-q:v", "4",
                    os.path.join(pv_dir, f"scene_{sid}.jpg")], timeout=120)
        except Exception:
            pass
    return {"ok": True, "segment": seg}


@app.post("/api/projects/{pid}/rebuild_timeline")
def rebuild_timeline(pid: str, body: dict = None):
    """Re-run segmentation + decision engine (keeps narration, no TTS)."""
    body = body or {}
    meta = projects.get(pid)
    if not meta or not meta.get("narration"):
        raise HTTPException(400, "project has no narration yet")
    segments = _segmod.segment_script(meta["script"], meta["narration"])
    tl = pipeline.build_timeline(meta, segments)
    meta["segments"] = segments
    meta["timeline"] = tl
    projects.save(meta)
    return {"ok": True, "project": _proj_public(meta)}


@app.post("/api/projects/{pid}/render")
def rerender(pid: str, body: dict = None):
    """Re-render video from the existing timeline (no TTS, no re-planning)."""
    body = body or {}
    meta = projects.get(pid)
    if not meta or not meta.get("timeline"):
        raise HTTPException(400, "project has no timeline")
    with _jobs_lock:
        if JOBS.get(pid, {}).get("running"):
            raise HTTPException(409, "a job is already running")
        JOBS[pid] = {"running": True, "stage": "render", "lines": [], "done": False, "ok": None}

    def log(msg):
        job = JOBS.get(pid)
        if job is not None:
            job["lines"].append(f"{time.strftime('%H:%M:%S')}  {msg}")
            job["lines"] = job["lines"][-500:]
    def run():
        try:
            # persist timeline edits before render
            for seg in meta["timeline"]["segments"]:
                preview = os.path.join(meta["dir"], "previews", f"scene_{seg['segment_id']}.jpg")
                if os.path.exists(preview):
                    os.remove(preview)
            result = renderer.render_project(meta, log_cb=log)
            meta["render_result"] = result
            meta["status"] = "done"
            projects.save(meta)
            JOBS[pid].update({"done": True, "ok": True, "result": {"render": result}, "running": False,
                              "stage": "done"})
        except Exception as e:
            log("ERROR: " + str(e))
            JOBS[pid].update({"done": True, "ok": False, "error": str(e), "running": False, "stage": "error"})
    threading.Thread(target=run, daemon=True).start()
    return {"ok": True, "job": "started"}


@app.patch("/api/projects/{pid}/segments/{sid}")
def patch_segment(pid: str, sid: str, body: dict):
    meta = projects.get(pid)
    if not meta or not meta.get("timeline"):
        raise HTTPException(404)
    seg = next((s for s in meta["timeline"]["segments"] if s["segment_id"] == sid), None)
    if not seg:
        raise HTTPException(404)
    allowed = ("asset_id", "asset_name", "asset_type", "fallback", "motion", "transition",
               "locked", "human_review_reason", "text_overlay", "text_style", "sfx", "music",
               "role", "emotion", "confidence")
    for k in allowed:
        if k in body:
            seg[k] = body[k]
    if "asset_id" in body and body["asset_id"]:
        a = asset_library.get(body["asset_id"])
        if a:
            seg["asset_id"], seg["asset_name"], seg["asset_type"] = a["asset_id"], a["filename"], a["type"]
            seg["fallback"] = None
    projects.save(meta)
    return {"ok": True, "segment": seg}


@app.get("/api/projects/{pid}/subtitles.ass")
def get_ass(pid: str):
    p = os.path.join(paths.project_dir(pid), "subtitles.ass")
    return _serve_media(p, "text/plain; charset=utf-8")


@app.post("/api/projects/{pid}/subtitles/rebuild")
def rebuild_subs(pid: str, body: dict):
    meta = projects.get(pid)
    if not meta:
        raise HTTPException(404)
    if body.get("subtitle_style"):
        cfg = settings.get("subtitles", {})
        cfg.update(body["subtitle_style"])
        settings.update({"subtitles": cfg})
    ass = os.path.join(meta["dir"], "subtitles.ass")
    res = subs_engine.build_ass(meta["timeline"]["segments"], ass)
    return {"ok": True, **res}


from . import segmentation as _segmod  # noqa: E402


@app.post("/api/segmentation/preview")
def segmentation_preview(body: dict):
    """Dry-run segmentation + roles on arbitrary text (no project needed)."""
    text = body.get("text", "")
    dur = float(body.get("duration", 0) or 0)
    fake = {"duration": dur or max(6.0, len(text.split()) / 2.6),
            "timing_mode": "estimated",
            "word_timestamps": tts.estimate_word_timings(text, dur or max(6.0, len(text.split()) / 2.6))}
    segs = _segmod.segment_script(text, fake)
    out = [{"segment_id": s["segment_id"], "start": s["start"], "end": s["end"], "role": s["role"],
            "confidence": s["role_confidence"], "concepts": s["concepts"][:5],
            "text": s["text"], "mg": [c["template"] for c in s["mg_candidates"]],
            "evidence": s["evidence"]} for s in segs]
    return {"segments": out,
            "structure_hint": structure_hint(dur or fake["duration"])}


def structure_hint(total: float):
    """Default 4–5 min noir structure map."""
    marks = [(0, .05, "SIGNAL / PROBLEM"), (.05, .117, "PROMISE / SCOPE"),
             (.117, .242, "DEFINITION / FRAME"), (.242, .442, "MECHANISM"),
             (.442, .608, "EXAMPLE"), (.608, .692, "COUNTEREXAMPLE"),
             (.692, .917, "PRACTICAL MOVE"), (.917, .967, "RELIEF / RECAP"),
             (.967, 1.0, "NEXT WATCH")]
    return [{"start": round(a * total), "end": round(b * total), "block": c} for a, b, c in marks]
