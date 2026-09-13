"""Utility helpers: media probing, ffmpeg invocation, json io, misc."""
import json, os, re, subprocess, sys, time, uuid, hashlib, shlex
from . import paths

_FF_RESOLVED = None


def ffmpeg_path() -> str:
    """Resolve the ffmpeg binary: env AVP_FFMPEG > PATH > imageio-ffmpeg."""
    global _FF_RESOLVED
    if _FF_RESOLVED:
        return _FF_RESOLVED
    p = os.environ.get("AVP_FFMPEG")
    if p and os.path.exists(p):
        _FF_RESOLVED = p
        return p
    import shutil
    p = shutil.which("ffmpeg")
    if p:
        _FF_RESOLVED = p
        return p
    try:
        import imageio_ffmpeg
        _FF_RESOLVED = imageio_ffmpeg.get_ffmpeg_exe()
        return _FF_RESOLVED
    except Exception:
        raise RuntimeError("ffmpeg not found. Run ./setup.sh")


FFMPEG = "ffmpeg"  # legacy alias; call util.ffmpeg_path() for the real binary


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"


def short_hash(*parts) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:10]


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


_DUR_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)")
_STREAM_RE = re.compile(r"Stream #\d+:\d+(?:\[\w+\])?(?:\([^)]*\))?:\s*(\w+):.*?(?:,\s*(\d+)x(\d+))?", re.S)


def probe(path: str) -> dict:
    """Probe media with `ffmpeg -i` stderr parsing (works without ffprobe)."""
    out = {"exists": os.path.exists(path), "duration": 0.0, "width": 0, "height": 0,
           "has_video": False, "has_audio": False, "vcodec": None, "acodec": None}
    if not out["exists"]:
        return out
    try:
        p = subprocess.run([ffmpeg_path(), "-hide_banner", "-i", path], capture_output=True, text=True, timeout=30)
        err = p.stderr or ""
        m = _DUR_RE.search(err)
        if m:
            out["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        for line in err.splitlines():
            if "Stream #" in line:
                if "Video:" in line:
                    out["has_video"] = True
                    vm = re.search(r"Video: (\w+)", line)
                    if vm:
                        out["vcodec"] = vm.group(1)
                    dm = re.search(r", (\d{2,5})x(\d{2,5})", line)
                    if dm:
                        out["width"], out["height"] = int(dm.group(1)), int(dm.group(2))
                    fr = re.search(r"([\d.]+)\s*fps", line)
                    if fr:
                        out["fps"] = float(fr.group(1))
                elif "Audio:" in line:
                    out["has_audio"] = True
                    am = re.search(r"Audio: (\w+)", line)
                    if am:
                        out["acodec"] = am.group(1)
    except Exception as e:
        out["error"] = str(e)
    return out


def run(cmd: list, timeout: int = 1800, log_path: str = None, quiet=False):
    """Run a subprocess; raise with tail of stderr on failure."""
    if not quiet:
        print("[cmd]", " ".join(shlex.quote(c) for c in cmd[:24]), "..." if len(cmd) > 24 else "", file=sys.stderr)
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if log_path:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(proc.stderr or "")
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").splitlines()[-25:])
        raise RuntimeError(f"command failed ({proc.returncode}) after {time.time()-t0:.1f}s:\n{tail}")
    return proc


def ffmpeg(args: list, timeout: int = 1800, log_path: str = None):
    return run([ffmpeg_path(), "-hide_banner", "-nostdin", "-y"] + args, timeout=timeout, log_path=log_path)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def lerp(a, b, t):
    return a + (b - a) * t


def fmt_ts(seconds: float, comma=False) -> str:
    """H:MM:SS.mmm for ASS/ffmpeg."""
    ms = int(round((seconds % 1) * 1000))
    s = int(seconds)
    sep = "," if comma else "."
    return f"{s//3600}:{(s%3600)//60:02d}:{s%60:02d}{sep}{ms:03d}"


def human_time(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s//60}:{s%60:02d}"


def safe_name(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_\- ]", "", name).strip().replace(" ", "_")
    return name[:60] or "untitled"


def strip_ext(name: str) -> str:
    return os.path.splitext(os.path.basename(name))[0]


def words_of(text: str):
    return re.findall(r"[A-Za-z0-9']+", text)


def sentence_split(text: str):
    """Split text into sentences keeping trailing punctuation."""
    parts = re.split(r"(?<=[.!?…])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]
