"""Asset Library: scans assets/ tree, builds a metadata index, provides
semantic search and weighted relevance scoring.

Every asset carries: asset_id, filename, type, duration, width, height,
aspect_ratio, tags (auto + manual), semantic_tags, category, orientation,
source, license_status, usage_count, quality, enabled.
Manual edits persist to a sidecar .json next to the media file.
"""
import os, re, time, threading
from PIL import Image
from . import paths, settings
from .util import probe, read_json, write_json, strip_ext, new_id, words_of

_lock = threading.RLock()
_index = None          # {asset_id: asset_dict}
_by_path = {}


def _auto_tags(name: str, category: str) -> list:
    tags = set(words_of(name.lower()))
    tags.discard("img"); tags.discard("vid"); tags.discard("mp4"); tags.discard("jpg")
    tags.discard("png"); tags.discard("jpeg"); tags.discard("webm"); tags.discard("mov")
    from .lexicon import CONCEPT_LEXICON
    known = set(CONCEPT_LEXICON.keys())
    semantic = sorted(t for t in tags if t in known)
    return sorted(tags), semantic


def _classify(category: str, has_video: bool, has_audio: bool) -> str:
    if category == "stock_videos":
        return "video"
    if category == "stock_images":
        return "image"
    if category == "background_music":
        return "music"
    if category == "sound_effects":
        return "sfx"
    if category == "fonts":
        return "font"
    if category in ("textures", "overlays", "particles", "transitions"):
        return category[:-1] if category.endswith("s") else category
    return "image"


def scan(progress_cb=None) -> dict:
    """Scan all asset directories, (re)build index, preserve manual metadata."""
    global _index, _by_path
    with _lock:
        old = _index or read_json(paths.LIBRARY_INDEX, {}) or {}
        by_path_old = {a["path"]: a for a in old.values()}
        fresh = {}
        root = paths.ASSETS_DIR
        for category in sorted(os.listdir(root)):
            cdir = os.path.join(root, category)
            if not os.path.isdir(cdir):
                continue
            for fn in sorted(os.listdir(cdir)):
                path = os.path.join(cdir, fn)
                if not os.path.isfile(path):
                    continue
                ext = os.path.splitext(fn)[1].lower()
                if ext == ".json" or fn.startswith("."):
                    continue
                prev = by_path_old.get(path) or read_json(os.path.splitext(path)[0] + ".json") or {}
                asset = _build_asset(path, category, ext, prev)
                if asset:
                    fresh[asset["asset_id"]] = asset
                if progress_cb:
                    progress_cb(fn)
        _index = fresh
        _by_path = {a["path"]: a for a in fresh.values()}
        write_json(paths.LIBRARY_INDEX, fresh)
        return {"total": len(fresh)}


def _build_asset(path, category, ext, prev) -> dict | None:
    if ext in paths.VIDEO_EXT:
        atype = "video"
    elif ext in paths.AUDIO_EXT:
        atype = "music" if category == "background_music" else ("sfx" if category == "sound_effects" else "audio")
    elif ext in paths.IMAGE_EXT:
        atype = "image"
    elif ext in paths.FONT_EXT:
        atype = "font"
    elif ext == ".json":
        atype = "meta"
    else:
        return None
    stat = os.stat(path)
    a = {
        "asset_id": (prev.get("asset_id") or f"as_{strip_ext(fn_key(path))}_{os.path.getsize(path):x}"[:22]),
        "filename": os.path.basename(path),
        "path": path,
        "rel_path": os.path.relpath(path, paths.ROOT),
        "type": atype,
        "category": category,
        "duration": round(prev.get("duration") or 0.0, 3),
        "width": prev.get("width") or 0,
        "height": prev.get("height") or 0,
        "aspect_ratio": prev.get("aspect_ratio") or "",
        "orientation": prev.get("orientation") or "",
        "fps": prev.get("fps"),
        "tags": sorted(set(prev.get("tags") or [])),
        "semantic_tags": sorted(set(prev.get("semantic_tags") or [])),
        "source": prev.get("source") or "local",
        "license_status": prev.get("license_status") or "unknown",
        "notes": prev.get("notes") or "",
        "usage_count": int(prev.get("usage_count") or 0),
        "quality": float(prev.get("quality") or 0.7),
        "enabled": bool(prev.get("enabled", True)),
        "file_size": stat.st_size,
        "mtime": stat.st_mtime,
        "added_at": prev.get("added_at") or time.time(),
    }
    if atype == "font":
        return a
    info = probe(path)
    if info.get("duration"):
        a["duration"] = round(info["duration"], 3)
    if atype in ("image", "video", "texture", "overlay", "particle", "transition") and info.get("width"):
        a["width"], a["height"] = info["width"], info["height"]
        ar = info["width"] / max(1, info["height"])
        a["aspect_ratio"] = f"{ar:.2f}"
        a["orientation"] = "landscape" if ar > 1.15 else ("portrait" if ar < 0.87 else "square")
    if info.get("fps"):
        a["fps"] = info["fps"]
    if atype in ("image", "video"):
        auto, semantic = _auto_tags(a["filename"], category)
        a["tags"] = sorted(set(a["tags"]) | set(auto))
        a["semantic_tags"] = sorted(set(a["semantic_tags"]) | set(semantic))
    # recompute orientation for audio-less media done above
    return a


def fn_key(path):
    return re.sub(r"[^a-z0-9]", "", strip_ext(path).lower())[:16]


def index() -> dict:
    global _index
    if _index is None:
        _index = read_json(paths.LIBRARY_INDEX, {}) or {}
    return _index


def get(asset_id: str) -> dict | None:
    return index().get(asset_id)


def get_by_path(path: str) -> dict | None:
    if _by_path and path in _by_path:
        return _by_path[path]
    for a in index().values():
        if a["path"] == path or a["rel_path"] == path:
            return a
    return None


def all_assets(kind: str = None, enabled_only=True) -> list:
    out = []
    for a in index().values():
        if enabled_only and not a.get("enabled", True):
            continue
        if kind and a["type"] != kind:
            continue
        out.append(a)
    out.sort(key=lambda a: a["filename"])
    return out


def save_manual_meta(asset_id: str, patch: dict) -> dict:
    """Persist manual tags / license / quality / enabled to sidecar + index."""
    with _lock:
        a = index().get(asset_id)
        if not a:
            raise KeyError(asset_id)
        for key in ("tags", "semantic_tags", "license_status", "quality", "enabled", "notes", "source"):
            if key in patch:
                a[key] = patch[key]
        if isinstance(a.get("tags"), list):
            a["tags"] = sorted(set(a["tags"]))
        if isinstance(a.get("semantic_tags"), list):
            a["semantic_tags"] = sorted(set(a["semantic_tags"]))
        sidecar = os.path.splitext(a["path"])[0] + ".json"
        write_json(sidecar, {k: a[k] for k in
                             ("asset_id", "tags", "semantic_tags", "license_status", "quality", "enabled", "notes", "source")})
        write_json(paths.LIBRARY_INDEX, index())
        return a


def mark_used(asset_id: str):
    with _lock:
        a = index().get(asset_id)
        if a:
            a["usage_count"] = int(a.get("usage_count", 0)) + 1
            write_json(paths.LIBRARY_INDEX, index())


def fonts() -> list:
    return [a for a in all_assets(kind="font")]


def font_file(family: str) -> str | None:
    for a in all_assets(kind="font", enabled_only=False):
        if family.lower() in a["filename"].lower():
            return a["path"]
    return None


# ---------------------------------------------------------------- scoring
def semantic_score(asset: dict, concepts: list, role: str) -> float:
    if not concepts:
        return 0.35
    sem = set(asset.get("semantic_tags") or [])
    tags = set(asset.get("tags") or [])
    fname_words = set(w.lower() for w in words_of(asset["filename"]))
    s = 0.0
    for i, c in enumerate(concepts[:8]):
        w = 1.0 if i == 0 else (0.6 if i < 3 else 0.35)
        if c in sem:
            s += w
        elif c in tags or c in fname_words:
            s += w * 0.7
        elif any(c in t for t in sem | tags):
            s += w * 0.45
    return min(1.0, s / 1.6)


def scene_score(asset: dict, role: str) -> float:
    from .lexicon import ROLE_TREATMENT
    treat = ROLE_TREATMENT.get(role, {})
    preferred = set(treat.get("scene") or [])
    tags = set(asset.get("semantic_tags") or []) | set(asset.get("tags") or [])
    cat = asset.get("category")
    base = 0.4
    if cat in ("textures", "overlays"):
        base = 0.25
    overlap = len(preferred & tags)
    return min(1.0, base + overlap * 0.3)


def format_score(asset: dict, target_ar: float) -> float:
    try:
        if asset.get("width"):
            ar = asset["width"] / max(1, asset["height"])
            return max(0.0, 1.0 - abs(ar - target_ar) / 1.2)
    except Exception:
        pass
    return 0.5


def duration_score(asset: dict, beat: float) -> float:
    if asset["type"] == "image":
        return 0.95
    d = asset.get("duration") or 0
    if d <= 0:
        return 0.4
    if d >= beat:
        return max(0.3, 1.0 - (d / beat - 1.0) * 0.15)
    loops = beat / d
    if loops <= 3:
        return 0.8
    return max(0.2, 0.8 - (loops - 3) * 0.12)


def diversity_score(asset: dict, usage: dict) -> float:
    n = usage.get(asset["asset_id"], 0)
    return max(0.0, 1.0 - n * 0.34)


def score_asset(asset: dict, concepts: list, role: str, beat: float, target_ar: float,
                usage: dict, last_used_pos: dict, position: int) -> tuple:
    w = settings.get("scoring", {})
    s_sem = semantic_score(asset, concepts, role)
    s_scene = scene_score(asset, role)
    s_fmt = format_score(asset, target_ar)
    s_dur = duration_score(asset, beat)
    s_div = diversity_score(asset, usage)
    s_q = float(asset.get("quality", 0.7))
    score = (s_sem * w.get("semantic_match", .45) + s_scene * w.get("scene_match", .20) +
             s_fmt * w.get("format_match", .10) + s_dur * w.get("duration_match", .10) +
             s_div * w.get("diversity", .10) + s_q * w.get("quality", .05))
    # penalties
    gap = settings.get("repetition.min_gap_segments", 4)
    last = last_used_pos.get(asset["asset_id"])
    if last is not None and position - last < gap:
        score -= w.get("recent_use_penalty", .35)
    score -= usage.get(asset["asset_id"], 0) * w.get("reuse_penalty", .15)
    return score, {
        "semantic": round(s_sem, 3), "scene": round(s_scene, 3), "format": round(s_fmt, 3),
        "duration": round(s_dur, 3), "diversity": round(s_div, 3), "quality": round(s_q, 3),
    }


def candidates(concepts: list, role: str, beat: float, target_ar: float,
               usage: dict, last_used_pos: dict, position: int,
               kinds=("image", "video"), exclude=None,
               categories=("stock_images", "stock_videos")) -> list:
    """Ranked candidate list [(score, breakdown, asset)] for a segment.
    Scene selection draws only from photographic/video categories — overlays,
    particles and transitions are LAYER materials, never scene content."""
    reps = settings.get("repetition.max_reuse", 3)
    out = []
    for a in all_assets():
        if a["type"] not in kinds:
            continue
        if categories and a["category"] not in categories:
            continue
        if exclude and a["asset_id"] in exclude:
            continue
        if usage.get(a["asset_id"], 0) >= reps:
            continue
        score, br = score_asset(a, concepts, role, beat, target_ar, usage, last_used_pos, position)
        out.append((score, br, a))
    out.sort(key=lambda x: -x[0])
    return out


def search(query: str = "", kind: str = None, tag: str = None, limit: int = 200) -> list:
    ql = (query or "").lower().split()
    out = []
    for a in all_assets(kind=kind, enabled_only=False):
        tags = set(t.lower() for t in (a.get("tags") or [])) | set(t.lower() for t in (a.get("semantic_tags") or []))
        hay = " ".join([a["filename"].lower(), a["category"], a.get("license_status", ""), " ".join(tags)])
        if tag and tag.lower() not in tags:
            continue
        if ql and not all(q in hay for q in ql):
            continue
        out.append(a)
    return out[:limit]


def all_tags() -> list:
    tags = set()
    for a in index().values():
        tags |= set(a.get("tags") or [])
    return sorted(tags)
