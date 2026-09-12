"""Project system.

Projects persist: original script, narration source type, uploaded narration
reference, generated TTS reference, audio duration, subtitle timing data,
timeline, asset selections, preset, motion graphics, music, effects, render
configuration. On reopen, the stored narration is reused — TTS is NEVER
regenerated unless the user explicitly requests it.
"""
import os, shutil, time
from . import paths, settings, asset_library
from .util import read_json, write_json, new_id, safe_name


def list_projects() -> list:
    out = []
    if not os.path.isdir(paths.PROJECTS_DIR):
        return out
    for pid in sorted(os.listdir(paths.PROJECTS_DIR)):
        meta = read_json(os.path.join(paths.PROJECTS_DIR, pid, "project.json"))
        if meta:
            out.append(_summary(pid, meta))
    out.sort(key=lambda p: -p.get("updated_at", 0))
    return out


def _summary(pid, meta) -> dict:
    final = os.path.join(paths.PROJECTS_DIR, pid, "final.mp4")
    narr = meta.get("narration") or {}
    dur = narr.get("duration", 0) if isinstance(narr, dict) else 0
    return {
        "project_id": pid,
        "title": meta.get("title", pid),
        "created_at": meta.get("created_at"),
        "updated_at": meta.get("updated_at"),
        "narration_source": meta.get("narration_source"),
        "narration_provider": (meta.get("narration") or {}).get("provider"),
        "duration": dur,
        "has_final": os.path.exists(final),
        "final_duration": (meta.get("render_result") or {}).get("duration"),
        "segments": len((meta.get("timeline") or {}).get("segments", [])),
        "review_flags": (meta.get("timeline") or {}).get("review_flags", 0),
        "preset": meta.get("preset"),
    }


def create(title: str, script: str, narration_source: str, preset: str = None,
           project_id: str = None) -> dict:
    pid = project_id or f"{safe_name(title)[:32]}_{new_id('')}"
    d = paths.project_dir(pid)
    os.makedirs(d, exist_ok=True)
    meta = {
        "project_id": pid,
        "title": title,
        "script": script,
        "narration_source": narration_source,   # tts_api | uploaded | project_existing
        "preset": preset,
        "created_at": time.time(),
        "updated_at": time.time(),
        "narration": None,          # {path,duration,provider,timing_mode,word_timestamps,...}
        "uploaded_narration": None, # reference to user-provided file
        "segments": None,           # segmentation result
        "timeline": None,
        "subtitles": None,
        "render_result": None,
        "render_settings": {"resolution": settings.get("render.resolution"),
                            "fps": settings.get("render.fps")},
        "status": "created",
        "events": [],
    }
    write_json(os.path.join(d, "project.json"), meta)
    return meta


def get(project_id: str) -> dict | None:
    d = paths.project_dir(project_id)
    meta = read_json(os.path.join(d, "project.json"))
    if meta:
        meta["dir"] = d
    return meta


def save(meta: dict):
    meta["updated_at"] = time.time()
    d = meta.get("dir") or paths.project_dir(meta["project_id"])
    meta.pop("dir", None)
    write_json(os.path.join(d, "project.json"), meta)
    meta["dir"] = d
    return meta


def log_event(meta: dict, msg: str):
    meta.setdefault("events", []).append({"t": time.time(), "msg": msg})
    if len(meta["events"]) > 400:
        meta["events"] = meta["events"][-400:]
    save(meta)


def delete(project_id: str):
    d = paths.project_dir(project_id)
    if os.path.isdir(d):
        shutil.rmtree(d)


def store_uploaded_narration(meta: dict, src_path: str, kind: str, text: str | None = None) -> dict:
    """Copy user-provided narration/audio into the project and mark it as
    authoritative — prevents any duplicate TTS generation."""
    d = meta["dir"]
    ext = os.path.splitext(src_path)[1].lower() or ".bin"
    name = "narration_audio" + ext if kind == "audio" else "tts_package" + ext
    dest = os.path.join(d, name)
    shutil.copyfile(src_path, dest)
    meta["uploaded_narration"] = {"kind": kind, "file": name, "orig_name": os.path.basename(src_path)}
    if text is not None and kind == "text":
        meta["script"] = text  # pre-generated TTS text is authoritative narration text
    return save(meta)


def project_narration_file(meta: dict) -> str | None:
    n = meta.get("narration") or {}
    p = n.get("path")
    if p and os.path.exists(p):
        return p
    up = meta.get("uploaded_narration") or {}
    if up.get("kind") == "audio":
        p = os.path.join(meta["dir"], up["file"])
        if os.path.exists(p):
            return p
    return None
