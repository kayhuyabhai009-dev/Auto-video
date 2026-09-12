"""Effects + generated seed media.

Two jobs:

1. SEED GENERATION (one-time, deterministic): creates the starter kit inside
   assets/ so the system works out of the box —
     background_music/  six procedural noir beds (pulse, documentary, open,
                        sparse, near-silence, resolve) encoded to mp3
     sound_effects/     paper, click, door, riser, impact, page, room tone
     textures/          paper, charcoal gradient, fog, concrete, bokeh
     overlays/          scanlines, light leak (transparent PNGs)
     particles/         dust overlay video (screen-blend), bokeh PNG
   Everything is clearly tagged source=generated (license_status: owned).

2. RENDER-TIME GLOBAL EFFECT CHAIN: converts effect settings into ffmpeg
   filters (grain, vignette, letterbox) that persist over the whole video.
"""
import io, math, os, struct, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from . import paths, settings
from .util import ffmpeg, probe, ffmpeg_path

SR = 44100
rng_global = np.random.default_rng(1907)


# ------------------------------------------------------------------ dsp utils
def _lowpass(x: np.ndarray, cutoff: float, sr: int = SR) -> np.ndarray:
    dt = 1.0 / sr
    rc = 1.0 / (2 * math.pi * cutoff)
    alpha = dt / (rc + dt)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += alpha * (x[i] - acc)
        y[i] = acc
    return y


def _lowpass_fast(x, cutoff, sr=SR):
    """FFT-based lowpass (O(n log n), streaming-safe levels for pads/hiss)."""
    X = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1.0 / sr)
    # smooth rolloff around cutoff
    gain = 1.0 / (1.0 + (freqs / max(1.0, cutoff)) ** 4)
    y = np.fft.irfft(X * gain, n=len(x))
    return y.astype(np.float32)


def _env_ar(n, attack, release, sr=SR, hold=1.0):
    e = np.ones(n, dtype=np.float32)
    a = max(1, int(attack * sr))
    r = max(1, int(release * sr))
    e[:a] = np.linspace(0, 1, a)
    e[-r:] *= np.linspace(1, 0, r)
    return e


def _sine(freq, n, sr=SR, phase=0.0):
    t = np.arange(n) / sr
    return np.sin(2 * math.pi * freq * t + phase).astype(np.float32)


def _noise(n):
    return rng_global.standard_normal(n).astype(np.float32)


def _write_wav(path, stereo):
    """stereo: (2, N) float32 -1..1"""
    data = np.clip(stereo.T, -1, 1)
    pcm = (data * 32000).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def _to_stereo(mono, width=0.15):
    n = len(mono)
    l = mono.copy()
    delay = int(width * SR * 0.01)
    r = np.concatenate([np.zeros(delay, np.float32), mono[:-delay]]) if delay else mono.copy()
    st = np.stack([l, r])
    # slight gain difference for width
    st[1] *= 0.96
    return st


def _pad_chord(freqs, n, level=0.12, lfo_rate=0.05, brightness=0.25, detune=0.0015):
    out = np.zeros(n, np.float32)
    t = np.arange(n) / SR
    lfo = (0.6 + 0.4 * np.sin(2 * math.pi * lfo_rate * t)).astype(np.float32)
    for f in freqs:
        out += _sine(f * (1 - detune), n) + _sine(f * (1 + detune), n)
        if brightness > 0:
            out += brightness * _sine(f * 2, n)
            if brightness > 0.2:
                out += brightness * 0.5 * _sine(f * 3, n)
    out *= lfo * level / max(1, len(freqs))
    return _lowpass_fast(out, 1600)


def _pluck(freq, dur, level=0.2):
    n = int(dur * SR)
    x = _sine(freq, n) + 0.35 * _sine(freq * 2, n) + 0.12 * _sine(freq * 3.01, n)
    env = np.exp(-np.arange(n) / (0.28 * SR)).astype(np.float32)
    a = max(1, int(0.008 * SR))
    env[:a] = np.linspace(0, 1, a)
    return (x * env * level).astype(np.float32)


def _kick(dur=0.45, freq=54.0, level=0.5):
    n = int(dur * SR)
    f = freq * (1 + 0.4 * np.exp(-np.arange(n) / (0.06 * SR)))
    t = np.cumsum(f) / SR
    x = np.sin(2 * math.pi * t).astype(np.float32)
    env = np.exp(-np.arange(n) / (0.13 * SR)).astype(np.float32)
    click = _noise(int(0.004 * SR)) * np.linspace(1, 0, int(0.004 * SR)) * 0.4
    x[: len(click)] += click
    return (x * env * level).astype(np.float32)


def _place(buf, sample, at):
    i = int(at * SR)
    n = sample.shape[-1]
    j = min(buf.shape[1], i + n)
    if j > i and i < buf.shape[1]:
        buf[:, i:j] += sample[..., : j - i]


# ------------------------------------------------------------------ tracks
def gen_noir_pulse(path):
    dur, n = 72.0, int(72 * SR)
    buf = np.zeros((2, n), np.float32)
    pad = _pad_chord([55.0, 82.41, 130.81], n, level=0.16, lfo_rate=0.045)
    buf += _to_stereo(pad, 0.2)
    for t in np.arange(0, dur - 1, 2.0):
        _place(buf, _kick(0.5, 52, 0.5), t)
    # sub swell every 16s
    for t in np.arange(8, dur - 10, 16.0):
        ln = int(7 * SR)
        sw = _sine(36.7, ln) * _env_ar(ln, 2.5, 3.5) * 0.22
        _place(buf, np.stack([sw, sw]), t)
    hiss = _lowpass_fast(_noise(n), 6500) * 0.010
    buf += _to_stereo(hiss, 0.0)
    return _master(path, buf)


def gen_documentary_bed(path):
    dur, n = int(80 * SR), 80.0
    buf = np.zeros((2, int(80 * SR)), np.float32)
    pad = _pad_chord([110.0, 164.81, 220.0], int(80 * SR), level=0.13, lfo_rate=0.03, brightness=0.18)
    buf += _to_stereo(pad, 0.25)
    notes = [220.0, 246.9, 261.6, 329.6, 392.0]
    t = 4.0
    side = 0
    while t < 76:
        pl = _pluck(notes[rng_global.integers(0, len(notes))], 1.6, 0.17)
        st = np.zeros((2, len(pl)), np.float32)
        st[side % 2] = pl * 0.9
        st[(side + 1) % 2] = pl * 0.5
        _place(buf, st, t)
        t += float(rng_global.uniform(3.5, 6.5))
        side += 1
    hiss = _lowpass_fast(_noise(len(buf[0])), 6000) * 0.007
    buf += _to_stereo(hiss, 0.0)
    return _master(path, buf)


def gen_open_tape(path):
    dur = 76.0
    n = int(dur * SR)
    buf = np.zeros((2, n), np.float32)
    pad = _pad_chord([130.81, 164.81, 196.0, 261.63], n, level=0.12, lfo_rate=0.06, brightness=0.3)
    buf += _to_stereo(pad, 0.3)
    notes = [261.6, 293.7, 329.6, 392.0, 440.0, 523.3]
    t = 2.0
    side = 1
    while t < 72:
        pl = _pluck(notes[rng_global.integers(0, len(notes))], 1.3, 0.15)
        st = np.zeros((2, len(pl)), np.float32)
        st[side % 2] = pl
        st[(side + 1) % 2] = pl * 0.55
        _place(buf, st, t)
        t += float(rng_global.uniform(2.5, 4.5))
        side += 1
    hiss = _lowpass_fast(_noise(n), 7000) * 0.006
    buf += _to_stereo(hiss, 0.0)
    return _master(path, buf)


def gen_sparse_tension(path):
    dur = 70.0
    n = int(dur * SR)
    buf = np.zeros((2, n), np.float32)
    tone = _lowpass_fast(_noise(n), 300) * 0.012
    buf += _to_stereo(tone, 0.0)
    for t in np.arange(5, dur - 4, 9.0):
        _place(buf, _kick(0.8, 44, 0.32), t)
    trem_t = np.arange(n) / SR
    air = _sine(1960, n) * ((0.5 + 0.5 * np.sin(2 * math.pi * 0.13 * trem_t)) * 0.006)
    buf += _to_stereo(air.astype(np.float32), 0.4)
    return _master(path, buf, 0.9)


def gen_near_silence(path):
    dur = 60.0
    n = int(dur * SR)
    buf = np.zeros((2, n), np.float32)
    tone = _lowpass_fast(_noise(n), 200) * 0.006
    buf += _to_stereo(tone, 0.0)
    for t in np.arange(14, dur - 8, 17.0):
        ln = int(5 * SR)
        sw = _sine(49.0, ln) * _env_ar(ln, 2.0, 2.8) * 0.10
        _place(buf, np.stack([sw, sw]), t)
    return _master(path, buf, 0.8)


def gen_resolve_warm(path):
    chords = [(130.81, 164.81, 196.0), (174.61, 220.0, 261.63),
              (110.0, 130.81, 164.81), (98.0, 146.83, 196.0)]
    seg = 9.0
    buf = None
    for rep in range(2):
        for ch in chords:
            n = int(seg * SR)
            pad = _pad_chord(ch, n, level=0.14, lfo_rate=0.08, brightness=0.22)
            st = _to_stereo(pad, 0.3)
            if buf is None:
                buf = np.zeros((2, int(seg * 8 * SR)), np.float32)
            at = int((rep * 4 + chords.index(ch)) * seg * SR)
            e = min(len(buf[0]), at + n)
            buf[:, at:e] += st[:, : e - at]
    notes = [261.6, 329.6, 392.0, 523.3]
    for i in range(10):
        at = int((2.0 + i * 6.5 + float(rng_global.uniform(0, 2))) * SR)
        pl = _pluck(notes[rng_global.integers(0, len(notes))], 1.5, 0.13)
        st = np.zeros((2, len(pl)), np.float32)
        st[i % 2] = pl
        st[(i + 1) % 2] = pl * 0.5
        e = min(len(buf[0]), at + len(pl))
        buf[:, at:e] += st[:, : e - at]
    hiss = _lowpass_fast(_noise(len(buf[0])), 6500) * 0.005
    buf += _to_stereo(hiss, 0.0)
    return _master(path, buf)


def gen_hook_pulse(path):
    dur = 44.0
    n = int(dur * SR)
    buf = np.zeros((2, n), np.float32)
    pad = _pad_chord([55.0, 110.0, 116.54], n, level=0.15, lfo_rate=0.12, brightness=0.15)
    buf += _to_stereo(pad, 0.2)
    for t in np.arange(0, dur - 1, 1.0):
        _place(buf, _kick(0.3, 60, 0.34), t)
    t = np.arange(n) / SR
    swell = _lowpass_fast(_noise(n), 900) * (t / dur) * 0.05
    buf += _to_stereo(swell.astype(np.float32), 0.0)
    return _master(path, buf)


def _master(path, buf, gain=1.0):
    buf = buf * gain
    peak = np.max(np.abs(buf)) or 1.0
    if peak > 0.85:
        buf *= 0.85 / peak
    wav = path + ".tmp.wav"
    _write_wav(wav, buf)
    ffmpeg(["-i", wav, "-codec:a", "libmp3lame", "-b:a", "160k", "-y", path], timeout=300)
    os.remove(wav)
    return path


# ------------------------------------------------------------------ sfx
def gen_sfx():
    out = {}
    def save(name, mono, level=1.0):
        m = np.clip(mono * level, -1, 1)
        st = _to_stereo(m, 0.1)
        wav = os.path.join(paths.asset_subdir("sound_effects"), name + ".wav")
        _write_wav(wav, st)
        mp3 = wav[:-4] + ".mp3"
        ffmpeg(["-i", wav, "-codec:a", "libmp3lame", "-b:a", "192k", "-y", mp3], timeout=120)
        os.remove(wav)
        out[name] = mp3

    n = int(0.7 * SR)
    crackle = _noise(n) * (rng_global.random(n) > 0.985).astype(np.float32)
    body = _lowpass_fast(_noise(n), 2600) * _env_ar(n, 0.05, 0.5)
    save("paper", body * 0.8 + crackle * 0.9, 0.9)

    n = int(0.07 * SR)
    click = _sine(1750, n) * np.exp(-np.arange(n) / (0.006 * SR)) * 0.8
    click[: int(0.003 * SR)] += _noise(int(0.003 * SR)) * 0.9
    save("click", click, 0.95)

    n = int(0.6 * SR)
    thud = _kick(0.35, 58, 0.7)
    sweep = _sine(240, int(0.25 * SR)) * np.exp(-np.arange(int(0.25 * SR)) / (0.09 * SR)) * 0.25
    door = np.zeros(n, np.float32)
    door[: len(thud)] += thud
    door[int(0.05 * SR): int(0.05 * SR) + len(sweep)] += _lowpass_fast(sweep, 900)
    save("door", door, 0.9)

    n = int(2.2 * SR)
    t = np.arange(n) / SR
    f = 120 + (t / t[-1]) ** 2 * 700
    ph = 2 * math.pi * np.cumsum(f) / SR
    riser = (np.sin(ph) * 0.5 + _lowpass_fast(_noise(n), 3000) * 0.7) * (t / t[-1]) ** 1.5
    save("riser", riser.astype(np.float32), 0.5)

    n = int(0.7 * SR)
    imp = _kick(0.7, 68, 0.8) + _lowpass_fast(_noise(n), 500) * np.exp(-np.arange(n) / (0.08 * SR)) * 0.6
    save("impact_soft", imp, 0.85)

    n = int(0.35 * SR)
    page = _lowpass_fast(_noise(n), 5000) * np.sin(np.pi * np.arange(n) / n) ** 2
    save("page", page, 0.7)

    n = int(8 * SR)
    save("room_tone", _lowpass_fast(_noise(n), 240) * 0.35, 0.5)
    return out


# ------------------------------------------------------------------ textures & overlays
def gen_textures():
    made = {}
    W, H = 1920, 1080

    def save_img(name, img, subdir="textures"):
        p = os.path.join(paths.asset_subdir(subdir), name)
        img.save(p, quality=88)
        made[name] = p
        return p

    # paper
    noise = rng_global.normal(0.5, 0.05, (H // 2, W // 2))
    img = Image.fromarray((np.clip(noise, 0, 1) * 255).astype(np.uint8)).resize((W, H))
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    arr = np.asarray(img).astype(np.int16)
    streak = (np.sin(np.arange(H) * 0.02) * 6).reshape(-1, 1)
    arr = np.clip(arr + streak + 96, 0, 255).astype(np.uint8)
    save_img("paper_warm.jpg", Image.merge("RGB", [
        Image.fromarray(arr), Image.fromarray(np.clip(arr.astype(int) + 6, 0, 255).astype(np.uint8)),
        Image.fromarray(np.clip(arr.astype(int) - 8, 0, 255).astype(np.uint8))]))

    # charcoal radial
    y, x = np.mgrid[0:H, 0:W]
    cx, cy = W / 2, H * 0.42
    d = np.sqrt(((x - cx) / (W * 0.7)) ** 2 + ((y - cy) / (H * 0.7)) ** 2)
    v = np.clip(0.20 - d * 0.16, 0.02, 0.25) + rng_global.normal(0, 0.008, (H, W))
    g = (np.clip(v, 0, 1) * 255).astype(np.uint8)
    save_img("charcoal_gradient.jpg", Image.merge("RGB", [Image.fromarray(g), Image.fromarray(g),
                                                          Image.fromarray(np.clip(g.astype(int) + 3, 0, 255).astype(np.uint8))]))

    # fog
    small = rng_global.normal(0.5, 0.16, (54, 96))
    fog = Image.fromarray((np.clip(small, 0, 1) * 255).astype(np.uint8)).resize((W, H)).filter(ImageFilter.GaussianBlur(60))
    fa = np.asarray(fog).astype(np.float32) * 0.55 + 20
    base = np.full((H, W), 17, np.float32)
    v = np.clip(base + fa, 0, 255).astype(np.uint8)
    save_img("fog_field.jpg", Image.merge("RGB", [Image.fromarray(v), Image.fromarray(v),
                                                  Image.fromarray(np.clip(v.astype(int) + 4, 0, 255).astype(np.uint8))]))

    # concrete
    conc = rng_global.normal(0.5, 0.09, (H // 2, W // 2))
    ci = Image.fromarray((np.clip(conc, 0, 1) * 255).astype(np.uint8)).resize((W, H)).filter(ImageFilter.GaussianBlur(0.6))
    blobs = rng_global.normal(0.5, 0.12, (24, 42))
    bl = Image.fromarray((np.clip(blobs, 0, 1) * 255).astype(np.uint8)).resize((W, H)).filter(ImageFilter.GaussianBlur(80))
    v = np.clip(0.55 * np.asarray(ci) + 0.45 * np.asarray(bl), 0, 255).astype(np.uint8)
    save_img("concrete_cool.jpg", Image.merge("RGB", [Image.fromarray(v), Image.fromarray(v),
                                                      Image.fromarray(np.clip(v.astype(int) + 5, 0, 255).astype(np.uint8))]))

    # bokeh (transparent)
    bo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bo)
    for _ in range(26):
        r = int(rng_global.uniform(24, 130))
        x, yy = int(rng_global.uniform(0, W)), int(rng_global.uniform(0, H))
        a = int(rng_global.uniform(10, 34))
        bd.ellipse([x - r, yy - r, x + r, yy + r], fill=(224, 218, 205, a))
    bo = bo.filter(ImageFilter.GaussianBlur(6))
    save_img("bokeh_layer.png", bo, "particles")

    # scanlines overlay (transparent)
    sl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sa = np.zeros((H, W, 4), np.uint8)
    sa[::3, :, 3] = 70
    sl = Image.fromarray(sa)
    save_img("scanlines.png", sl, "overlays")

    # light leak (warm, transparent, right side)
    y, x = np.mgrid[0:H, 0:W]
    d = np.sqrt(((x - W * 1.02) / (W * 0.55)) ** 2 + ((y - H * 0.18) / (H * 0.8)) ** 2)
    a = np.clip(1.15 - d, 0, 1) ** 2.1
    warm = np.zeros((H, W, 4), np.uint8)
    warm[:, :, 0] = np.clip(a * 232, 0, 255).astype(np.uint8)
    warm[:, :, 1] = np.clip(a * 172, 0, 255).astype(np.uint8)
    warm[:, :, 2] = np.clip(a * 96, 0, 255).astype(np.uint8)
    warm[:, :, 3] = np.clip(a * 120, 0, 255).astype(np.uint8)
    save_img("light_leak_warm.png", Image.fromarray(warm), "overlays")
    return made


def gen_dust_video():
    """Soft drifting dust for screen blending (black background = no-op)."""
    path = os.path.join(paths.asset_subdir("particles"), "dust_screen.mp4")
    fw, fh, fps, secs = 960, 540, 24, 12
    n_frames = fps * secs
    # precompute soft round sprites at several radii
    sprites = {}
    for w in range(2, 26):
        ss = 2 * w
        yy, xx = np.mgrid[0:ss, 0:ss]
        d = np.sqrt((xx - w) ** 2 + (yy - w) ** 2) / w
        sprites[w] = (np.clip(1 - d, 0, 1) ** 2.4).astype(np.float32)
    n_parts = 70
    rs = np.random.default_rng(20260912)
    px = rs.uniform(0, fw, n_parts)
    py = rs.uniform(0, fh, n_parts)
    vx = rs.uniform(-6, 10, n_parts)
    vy = rs.uniform(-16, -4, n_parts)
    sz = rs.uniform(2, 22, n_parts)          # sprite radius in px
    al = rs.uniform(0.10, 0.42, n_parts)
    ph = rs.uniform(0, 2 * math.pi, n_parts)
    proc = __import__("subprocess").Popen(
        [ffmpeg_path(), "-hide_banner", "-nostdin", "-y",
         "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{fw}x{fh}", "-r", str(fps), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
         "-pix_fmt", "yuv420p", path], stdin=__import__("subprocess").PIPE,
        stdout=__import__("subprocess").DEVNULL, stderr=__import__("subprocess").DEVNULL)
    frame = np.zeros((fh, fw), np.float32)
    for f_i in range(n_frames):
        frame[:] = 0
        t = f_i / fps
        for i in range(n_parts):
            x = int((px[i] + vx[i] * t) % fw)
            y = int((py[i] + vy[i] * t) % fh)
            w = int(sz[i])
            a = al[i] * (0.6 + 0.4 * math.sin(ph[i] + t * 1.4))
            y0, x0 = max(0, y - w), max(0, x - w)
            y1, x1 = min(fh, y + w), min(fw, x + w)
            if y1 <= y0 or x1 <= x0:
                continue
            sub = sprites[w][y0 - (y - w): y1 - (y - w), x0 - (x - w): x1 - (x - w)]
            frame[y0:y1, x0:x1] += sub * a * 255
        buf = np.clip(frame, 0, 255).astype(np.uint8).tobytes()
        proc.stdin.write(buf)
    proc.stdin.close()
    proc.wait()
    return path


# ------------------------------------------------------------------ seeding
def ensure_seed_assets(force_music=False):
    """Generate any missing starter assets. Returns dict of created counts."""
    created = {"music": 0, "sfx": 0, "textures": 0, "overlays": 0, "particles": 0}
    music_dir = paths.asset_subdir("background_music")
    tracks = {
        "noir_pulse": gen_noir_pulse, "documentary_bed": gen_documentary_bed,
        "open_tape": gen_open_tape, "sparse_tension": gen_sparse_tension,
        "near_silence": gen_near_silence, "resolve_warm": gen_resolve_warm,
        "hook_pulse": gen_hook_pulse,
    }
    for name, fn in tracks.items():
        p = os.path.join(music_dir, name + ".mp3")
        if force_music or not os.path.exists(p):
            fn(p)
            created["music"] += 1
    sfx_dir = paths.asset_subdir("sound_effects")
    needed = {"paper", "click", "door", "riser", "impact_soft", "page", "room_tone"}
    if force_music or not all(os.path.exists(os.path.join(sfx_dir, s + ".mp3")) for s in needed):
        gen_sfx()
        created["sfx"] = len(needed)
    tex_dir = paths.asset_subdir("textures")
    if force_music or not os.path.exists(os.path.join(tex_dir, "charcoal_gradient.jpg")):
        gen_textures()
        created["textures"] = 4
        created["overlays"] = 2
    part_dir = paths.asset_subdir("particles")
    if not os.path.exists(os.path.join(part_dir, "dust_screen.mp4")):
        gen_dust_video()
        created["particles"] += 1
    return created


# ------------------------------------------------------------------ render-time chains
def global_video_filters(fx_cfg=None, W=1920, H=1080) -> list:
    """ffmpeg video filter fragments for the GLOBAL EFFECT layer."""
    cfg = {**settings.get("effects", {}), **(fx_cfg or {})}
    chain = []
    if cfg.get("vignette", {}).get("enabled", True):
        a = float(cfg.get("vignette", {}).get("opacity", 0.55))
        chain.append(f"vignette=PI/5:mode=backward:eval=init")
    if cfg.get("grain", {}).get("enabled", True):
        s = float(cfg.get("grain", {}).get("opacity", 0.10))
        str_ = max(3, min(40, int(s * 42)))
        chain.append(f"noise=alls={str_}:allf=t+u")
    if cfg.get("letterbox", {}).get("enabled", False):
        ratio = float(cfg.get("letterbox", {}).get("ratio", 2.0))
        bar = max(0, int((H - W / ratio) / 2))
        if bar > 2:
            chain.append(
                f"drawbox=x=0:y=0:w={W}:h={bar}:color=black:t=fill")
            chain.append(f"drawbox=x=0:y={H-bar}:w={W}:h={bar}:color=black:t=fill")
    return chain
