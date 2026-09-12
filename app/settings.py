"""Global application settings.

Non-secret settings persist to data/settings.json.
Secrets are NEVER persisted — they are read from environment variables only.
"""
import os
from threading import RLock
from . import paths

_lock = RLock()

DEFAULTS = {
    "tts": {
        # provider: openai | elevenlabs | generic_http | piper_local | espeak_offline | timed_placeholder
        "provider": "espeak_offline",
        # endpoint/model/voice are configurable; API keys only via env vars below
        "endpoint": "",                      # full URL for generic_http or override for others
        "model": "tts-1",
        "voice": "onyx",
        "speed": 1.0,
        "pitch": 0.0,                        # semitones (applied post if provider lacks it)
        "format": "mp3",
        "sample_rate": 22050,
        "language": "en",
        "env_key_var": "TTS_API_KEY",        # name of env var holding the API key (never the key itself)
        "espeak_rate": 168,
        "espeak_voice": "en-us+f3",
        "piper_model": "models/piper/voice.onnx",
        "timeout": 180,
    },
    "render": {
        "resolution": "1920x1080",
        "fps": 30,
        "crf": 20,
        "preset": "medium",
        "audio_bitrate": "192k",
        "transition_mode": "filter",         # filter (timing-exact) | xfade (true crossfades)
    },
    "scoring": {                              # asset relevance weights (must roughly sum to 1)
        "semantic_match": 0.45,
        "scene_match": 0.20,
        "format_match": 0.10,
        "duration_match": 0.10,
        "diversity": 0.10,
        "quality": 0.05,
        "recent_use_penalty": 0.35,          # applied when asset used within min_gap
        "reuse_penalty": 0.15,               # per prior usage in project
    },
    "repetition": {
        "min_gap_segments": 4,               # min segments before an asset may repeat
        "max_reuse": 3,                      # max times one asset in a project
        "same_category_limit": 3,            # max consecutive picks from one category
        "allow_user_override": True,
    },
    "rhythm": {                               # editing rhythm ranges (seconds)
        "FIRST30": [0.7, 2.5],
        "HOOK_SIGNAL": [0.7, 2.5],
        "PROBLEM": [2.5, 5.0],
        "PROMISE": [2.5, 5.0],
        "DEFINITION": [4.0, 8.0],
        "SOURCE": [4.0, 8.0],
        "EXAMPLE": [2.0, 6.0],
        "MECHANISM": [4.0, 8.0],
        "COUNTEREXAMPLE": [5.0, 10.0],
        "EMOTIONAL_RECOGNITION": [6.0, 12.0],
        "PRACTICAL_MOVE": [4.0, 8.0],
        "LIMITATION": [4.0, 8.0],
        "RECAP": [5.0, 9.0],
        "NEXT_WATCH": [4.0, 8.0],
        "DEFAULT": [2.5, 6.0],
    },
    "transitions": {                          # weighted pool when a cut IS motivated
        "weights": {
            "hard_cut": 50, "fade": 20, "dissolve": 0, "zoom": 10, "slide": 10,
            "blur": 5, "flash": 2, "glitch": 1, "light_leak": 1, "evidence_pivot": 8,
        },
        "max_duration": 0.6,
        "complex_requires_state_change": True,
    },
    "subtitles": {
        "mode": "selective",                 # selective | full | off
        "max_chars": 42,
        "max_lines": 2,
        "position": "bottom",                # top | center | bottom | custom
        "custom_x": 0.5, "custom_y": 0.82,
        "font": "DejaVu Sans",
        "size": 54,
        "bold": True,
        "italic": False,
        "underline": False,
        "letter_spacing": 0,
        "line_spacing": 1.15,
        "animation": "fade",                 # fade | pop | typewriter | slide | word_highlight
        "accent_colors": True,               # semantic word colorization
    },
    "motion_graphics": {
        "enabled": True,
        "min_gap_seconds": 8.0,              # min gap between generated graphics
        "max_per_video": 14,
    },
    "effects": {
        "grain": {"enabled": True, "opacity": 0.10, "speed": 1.0},
        "vignette": {"enabled": True, "opacity": 0.55},
        "dust": {"enabled": True, "opacity": 0.28, "speed": 1.0, "loop": True},
        "letterbox": {"enabled": True, "opacity": 1.0, "ratio": 2.0},
        "scanlines": {"enabled": False, "opacity": 0.10},
    },
    "music": {
        "mode": "auto",                      # auto | fixed | random | off
        "fixed_track": "",
        "base_volume": 0.28,
        "ducking": {"enabled": True, "threshold": 0.02, "ratio": 8, "attack": 120, "release": 900},
        "fade_in": 2.0, "fade_out": 3.5,
    },
    "sfx": {
        "enabled": True,
        "volume": 0.5,
        "min_gap_seconds": 6.0,
    },
    "assets": {
        "auto_scan_on_start": True,
    },
    "paths": {
        "assets": paths.ASSETS_DIR,
        "projects": paths.PROJECTS_DIR,
        "scripts": paths.SCRIPTS_DIR,
    },
}

_settings = None


def _deep_merge(base, override):
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load(force=False) -> dict:
    global _settings
    with _lock:
        if _settings is None or force:
            stored = {}
            if os.path.exists(paths.SETTINGS_FILE):
                from .util import read_json
                stored = read_json(paths.SETTINGS_FILE, {}) or {}
            _settings = _deep_merge(DEFAULTS, stored)
        return _settings


def save():
    with _lock:
        from .util import write_json
        write_json(paths.SETTINGS_FILE, _settings)


def get(path: str, default=None):
    s = load()
    for part in path.split("."):
        if not isinstance(s, dict) or part not in s:
            return default
        s = s[part]
    return s


def update(patch: dict) -> dict:
    """Deep-merge a patch into settings, persist, return full settings."""
    global _settings
    with _lock:
        s = load()
        _settings = _deep_merge(s, patch)
        save()
        return _settings


def tts_api_key() -> str:
    """Read the API key from the env var named in settings.env_key_var."""
    var = get("tts.env_key_var", "TTS_API_KEY") or "TTS_API_KEY"
    return os.environ.get(var, "")
