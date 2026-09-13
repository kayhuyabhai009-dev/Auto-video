"""Central path management for the Auto Video Producer."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

APP_DIR = os.path.join(ROOT, "app")
ASSETS_DIR = os.path.join(ROOT, "assets")
PRESETS_DIR = os.path.join(ROOT, "presets")
SCRIPTS_DIR = os.path.join(ROOT, "scripts")
PROJECTS_DIR = os.path.join(ROOT, "projects")
STATIC_DIR = os.path.join(ROOT, "static")
DATA_DIR = os.path.join(ROOT, "data")
MODELS_DIR = os.path.join(ROOT, "models")
LIBRARY_INDEX = os.path.join(DATA_DIR, "library_index.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

ASSET_SUBDIRS = [
    "stock_images", "stock_videos", "transitions", "particles", "overlays",
    "background_music", "motion_graphics", "sound_effects", "fonts", "textures",
]

# media file classification by extension
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".mpg", ".mpeg"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus", ".aac", ".aiff"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
FONT_EXT = {".ttf", ".otf", ".woff", ".woff2"}
TEXT_EXT = {".txt", ".md", ".json"}

MEDIA_EXT = VIDEO_EXT | AUDIO_EXT | IMAGE_EXT


def ensure_dirs():
    for d in [ASSETS_DIR, PRESETS_DIR, SCRIPTS_DIR, PROJECTS_DIR, STATIC_DIR, DATA_DIR, MODELS_DIR]:
        os.makedirs(d, exist_ok=True)
    for s in ASSET_SUBDIRS:
        os.makedirs(os.path.join(ASSETS_DIR, s), exist_ok=True)


def project_dir(project_id: str) -> str:
    return os.path.join(PROJECTS_DIR, project_id)


def asset_subdir(kind: str) -> str:
    return os.path.join(ASSETS_DIR, kind)
