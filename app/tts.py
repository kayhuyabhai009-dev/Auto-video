"""TTS engine.

Providers:
  openai            – OpenAI-compatible /v1/audio/speech endpoint
  elevenlabs        – ElevenLabs API (supports word timestamps)
  generic_http      – any HTTP endpoint returning audio bytes, JSON {url},
                      or JSON {audio_base64}; optional word_timings JSON
  piper_local       – local Piper voice model (models/piper/*.onnx)
  espeak_offline    – bundled espeak-ng via ctypes (fully offline)
  timed_placeholder – silent timing bed for pipeline demos (CLEARLY flagged)

Secrets: API keys are only read from environment variables — never stored.
The narration audio is the MASTER TIMELINE: whatever this module produces or
adopts determines total video duration.
"""
import base64, ctypes, json, math, os, re, struct, subprocess, tempfile, time, wave
import httpx
from . import settings, paths
from .util import probe, ffmpeg, new_id, sentence_split

class TTSError(RuntimeError):
    pass


# ------------------------------------------------------------------ helpers
def _key():
    return settings.tts_api_key()


def _post(url, *, headers=None, json_body=None, data=None, timeout=None, expect="bytes"):
    timeout = timeout or settings.get("tts.timeout", 180)
    with httpx.Client(timeout=timeout) as cli:
        r = cli.post(url, headers=headers or {}, json=json_body, data=data)
        if r.status_code >= 300:
            raise TTSError(f"TTS HTTP {r.status_code}: {r.text[:300]}")
        if expect == "bytes":
            return r.content
        return r.json()


def estimate_word_timings(text: str, total_duration: float, start: float = 0.0) -> list:
    """Distribute real audio duration across words weighted by length + pauses."""
    tokens = re.findall(r"[\w']+|[.,!?;:…]", text)
    if not tokens:
        return []
    words = []   # [weight, token]
    for t in tokens:
        if re.fullmatch(r"[.,!?;:…]", t):
            if words:
                words[-1][0] += 2.2 if t in "!?.…" else 1.2
            continue
        words.append([max(1.4, min(len(t), 14)), t])
    if not words:
        return []
    total_w = sum(w for w, _ in words)
    timings, tpos = [], start
    for w, tok in words:
        dur = w / total_w * total_duration
        timings.append({"word": tok, "start": round(tpos, 3), "end": round(tpos + dur, 3), "estimated": True})
        tpos += dur
    return timings


def _apply_pitch_speed(in_path, out_path, speed=1.0, pitch=0.0):
    """Post-process tempo/pitch when the provider lacks native support."""
    if abs(speed - 1.0) < 0.01 and abs(pitch) < 0.01:
        if os.path.abspath(in_path) != os.path.abspath(out_path):
            os.replace(in_path, out_path)
        return
    filters = []
    if abs(speed - 1.0) >= 0.01:
        filters.append(f"atempo={max(0.5, min(2.0, speed)):.4f}")
    if abs(pitch) >= 0.01:
        # asetrate shifts pitch+speed; compensate tempo
        f = 2 ** (pitch / 12.0)
        filters = [f"asetrate=22050*{f:.5f}", f"aresample=22050"] + filters
    ffmpeg(["-i", in_path, "-af", ",".join(filters), "-ar", "22050", out_path], timeout=120)


# ------------------------------------------------------------------ providers
def _synth_openai(text, out_path, cfg):
    key = _key()
    if not key:
        raise TTSError("TTS_API_KEY environment variable is not set (provider=openai)")
    endpoint = cfg.get("endpoint") or "https://api.openai.com/v1/audio/speech"
    resp = _post(endpoint, headers={"Authorization": f"Bearer {key}"},
                 json_body={"model": cfg.get("model", "tts-1"), "voice": cfg.get("voice", "onyx"),
                            "input": text, "speed": float(cfg.get("speed", 1.0)),
                            "response_format": "mp3"})
    tmp = out_path + ".raw.mp3"
    with open(tmp, "wb") as f:
        f.write(resp)
    _apply_pitch_speed(tmp, out_path, 1.0, float(cfg.get("pitch", 0)))
    if os.path.exists(tmp):
        os.remove(tmp)
    return {"timing_mode": "estimated"}


def _synth_elevenlabs(text, out_path, cfg, want_timestamps=True):
    key = _key()
    if not key:
        raise TTSError("TTS_API_KEY environment variable is not set (provider=elevenlabs)")
    endpoint = cfg.get("endpoint") or "https://api.elevenlabs.io/v1"
    voice = cfg.get("voice", "21m00Tcm4TlvDq8ikWAM")
    model = cfg.get("model", "eleven_multilingual_v2")
    body = {"text": text, "model_id": model}
    if want_timestamps:
        data = _post(f"{endpoint}/text-to-speech/{voice}/with-timestamps",
                     headers={"xi-api-key": key}, json_body=body, expect="json")
        ab = base64.b64decode(data.get("audio_base64", ""))
        tmp = out_path + ".raw.mp3"
        with open(tmp, "wb") as f:
            f.write(ab)
        _apply_pitch_speed(tmp, out_path, 1.0, float(cfg.get("pitch", 0)))
        os.remove(tmp)
        chars = data.get("character_alignments") or []
        words, buf, buf_start = [], "", None
        for c in chars:
            if c["character"].isspace():
                if buf:
                    words.append({"word": buf, "start": buf_start, "end": c["start_time"], "estimated": False})
                    buf, buf_start = "", None
            else:
                if buf_start is None:
                    buf_start = c["start_time"]
                buf += c["character"]
        if buf:
            words.append({"word": buf, "start": buf_start, "end": chars[-1]["end_time"], "estimated": False})
        return {"timing_mode": "word_timestamps", "word_timestamps": words}
    else:
        resp = _post(f"{endpoint}/text-to-speech/{voice}", headers={"xi-api-key": key}, json_body=body)
        with open(out_path + ".raw.mp3", "wb") as f:
            f.write(resp)
        _apply_pitch_speed(out_path + ".raw.mp3", out_path, 1.0, float(cfg.get("pitch", 0)))
        return {"timing_mode": "estimated"}


def _synth_generic(text, out_path, cfg):
    endpoint = cfg.get("endpoint")
    if not endpoint:
        raise TTSError("generic_http provider needs tts.endpoint in settings")
    headers = {}
    key = _key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body = {"text": text, "input": text, "voice": cfg.get("voice"), "model": cfg.get("model"),
            "speed": cfg.get("speed"), "pitch": cfg.get("pitch"),
            "format": cfg.get("format", "mp3"), "sample_rate": cfg.get("sample_rate")}
    body = {k: v for k, v in body.items() if v is not None}
    resp = _post(endpoint, headers=headers, json_body=body, expect="bytes")
    ctype = ""
    try:
        j = json.loads(resp)
        # JSON response: audio url / base64 / optional word timings
        audio_ref = j.get("url") or j.get("audio_url")
        words = j.get("word_timestamps") or j.get("words")
        if j.get("audio_base64"):
            audio_ref = None
            raw = base64.b64decode(j["audio_base64"])
            with open(out_path + ".raw", "wb") as f:
                f.write(raw)
        elif audio_ref:
            with httpx.Client(timeout=cfg.get("timeout", 180)) as cli:
                rr = cli.get(audio_ref, headers=headers)
                rr.raise_for_status()
                with open(out_path + ".raw", "wb") as f:
                    f.write(rr.content)
        else:
            raise TTSError("generic_http JSON response had no audio url/audio_base64")
        res = {"timing_mode": "estimated"}
        if words:
            try:
                res = {"timing_mode": "word_timestamps",
                       "word_timestamps": [{"word": w["word"], "start": float(w["start"]),
                                            "end": float(w["end"]), "estimated": False} for w in words]}
            except Exception:
                pass
        _apply_pitch_speed(out_path + ".raw", out_path, float(cfg.get("speed", 1.0)), float(cfg.get("pitch", 0)))
        if os.path.exists(out_path + ".raw"):
            os.remove(out_path + ".raw")
        return res
    except json.JSONDecodeError:
        pass
    with open(out_path + ".raw", "wb") as f:
        f.write(resp)
    _apply_pitch_speed(out_path + ".raw", out_path, float(cfg.get("speed", 1.0)), float(cfg.get("pitch", 0)))
    if os.path.exists(out_path + ".raw"):
        os.remove(out_path + ".raw")
    return {"timing_mode": "estimated"}


def _synth_piper(text, out_path, cfg):
    model = cfg.get("piper_model") or "models/piper/voice.onnx"
    model = model if os.path.isabs(model) else os.path.join(paths.ROOT, model)
    if not os.path.exists(model):
        raise TTSError(f"Piper model not found: {model}. Drop a .onnx + .onnx.json into models/piper/")
    try:
        from piper import PiperVoice
        voice = PiperVoice.load(model)
    except Exception as e:
        raise TTSError(f"Piper load failed: {e}")
    raw = out_path + ".raw.wav"
    with wave.open(raw, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(22050)
        try:
            voice.synthesize(text, wf)
        except TypeError:
            import piper.config as pconf
            cfgobj = pconf.PiperConfig() if hasattr(pconf, "PiperConfig") else None
            voice.synthesize(text, wf, cfgobj)
    _apply_pitch_speed(raw, out_path, float(cfg.get("speed", 1.0)), float(cfg.get("pitch", 0)))
    if os.path.exists(raw):
        os.remove(raw)
    return {"timing_mode": "estimated"}


# espeak-ng via bundled lib (ctypes)
_espeak = {"lib": None}

def _espeak_lib():
    if _espeak["lib"]:
        return _espeak["lib"]
    import espeakng_loader
    lib = ctypes.CDLL(espeakng_loader.get_library_path())
    data_path = espeakng_loader.get_data_path().encode()
    # AUDIO_OUTPUT_RETRIEVAL = 1
    r = lib.espeak_Initialize(1, 0, data_path, 0)
    if r < 0:
        raise TTSError("espeak_Initialize failed")
    _espeak["lib"] = lib
    return lib


def _synth_espeak(text, out_path, cfg):
    lib = _espeak_lib()
    voice = (cfg.get("espeak_voice") or "en-us+f3").encode()
    lib.espeak_SetVoiceByName(voice)
    rate = int((cfg.get("espeak_rate") or 168) * float(cfg.get("speed", 1.0)))
    lib.espeak_SetParameter(1, max(80, min(450, rate)), 0)     # espeakRATE
    pitch = 50 + float(cfg.get("pitch", 0)) * 4                # semitones → espeak 0-100
    lib.espeak_SetParameter(2, max(10, min(90, int(pitch))), 0)  # espeakPITCH
    lib.espeak_SetParameter(5, 100, 0)                         # espeakVOLUME
    SR = int(cfg.get("sample_rate") or 22050)
    lib.espeak_SetParameter(3, 0, 0)                           # espeakPUNCTUATION none? 1=none
    samples = []
    SynthCB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p)
    def cb(wav, numsamples, events):
        if numsamples > 0:
            samples.append(bytes(ctypes.string_at(wav, numsamples * 2)))
        return 0
    holder = SynthCB(cb)
    lib.espeak_SetSynthCallback(holder)
    # espeak default sample rate is 22050; set output sample rate via espeak_Initialize param already fixed
    btext = text.encode("utf-8")
    lib.espeak_Synth(btext, len(btext) + 1, 0, 0, 0, 0, None, None)
    lib.espeak_Synchronize()
    data = b"".join(samples)
    if len(data) < 800:
        raise TTSError("espeak produced no audio")
    tmp = out_path + ".raw.wav"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
        w.writeframes(data)
    _apply_pitch_speed(tmp, out_path, 1.0, 0.0)
    if os.path.exists(tmp):
        os.remove(tmp)
    return {"timing_mode": "estimated"}


def _synth_placeholder(text, out_path, cfg):
    """Silent timing bed (offline demo): exact estimated duration, near-silence.
    The UI must label this clearly — it is NOT narration."""
    words = max(1, len(re.findall(r"[\w']+", text)))
    est = words / 2.55  # ~153 wpm
    ffmpeg(["-f", "lavfi", "-i", f"anoisesrc=color=brown:amplitude=0.0035:duration={est:.2f}",
            "-af", "lowpass=f=400", "-ar", "22050", out_path], timeout=120)
    return {"timing_mode": "estimated", "placeholder": True}


_PROVIDERS = {
    "openai": _synth_openai,
    "elevenlabs": _synth_elevenlabs,
    "generic_http": _synth_generic,
    "piper_local": _synth_piper,
    "espeak_offline": _synth_espeak,
    "timed_placeholder": _synth_placeholder,
}


def provider_status() -> dict:
    cfg = settings.get("tts", {})
    st = {"provider": cfg.get("provider"), "key_present": bool(_key()),
          "key_var": cfg.get("env_key_var", "TTS_API_KEY"), "providers": {}}
    st["providers"]["espeak_offline"] = True
    st["providers"]["timed_placeholder"] = True
    st["providers"]["openai"] = bool(_key())
    st["providers"]["elevenlabs"] = bool(_key())
    st["providers"]["generic_http"] = bool(cfg.get("endpoint"))
    pm = cfg.get("piper_model") or "models/piper/voice.onnx"
    pm = pm if os.path.isabs(pm) else os.path.join(paths.ROOT, pm)
    st["providers"]["piper_local"] = os.path.exists(pm)
    return st


def synthesize(text: str, out_path: str, lang: str = None, force_provider: str = None) -> dict:
    """Generate narration audio. Returns {path,duration,provider,timing_mode,word_timestamps?}."""
    cfg = dict(settings.get("tts", {}))
    provider = force_provider or cfg.get("provider", "espeak_offline")
    fn = _PROVIDERS.get(provider)
    if not fn:
        raise TTSError(f"unknown TTS provider: {provider}")
    text = text.strip()
    if not text:
        raise TTSError("empty script")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    kwargs = {}
    if provider == "elevenlabs":
        kwargs["want_timestamps"] = True
    meta = fn(text, out_path, cfg, **kwargs)
    info = probe(out_path)
    if not info.get("duration"):
        raise TTSError("TTS produced unreadable audio")
    out = {"path": out_path, "duration": round(info["duration"], 3), "provider": provider,
           "timing_mode": meta.get("timing_mode", "estimated"),
           "word_timestamps": meta.get("word_timestamps"),
           "placeholder": bool(meta.get("placeholder")), "text": text}
    if out["timing_mode"] == "estimated" or not out.get("word_timestamps"):
        out["word_timestamps"] = estimate_word_timings(text, out["duration"])
        out["timing_mode"] = meta.get("timing_mode", "estimated")
    return out


# ------------------------------------------------------- pre-generated TTS
def parse_tts_package(txt_path: str, project_dir: str) -> dict:
    """Parse a PRE-GENERATED TTS package (.txt designation).

    Supported forms:
      1. Plain narration text -> authoritative narration text (audio via settings
         only if user explicitly regenerates; duration needs audio).
      2. Package header referencing audio:
            # PRE-GENERATED TTS
            audio: narration.mp3 | ./narration.wav | https://...
      3. JSON file: {"text": ..., "audio": ..., "word_timestamps": [...]}
    Returns {text, audio_path (or None), word_timestamps, mode}.
    """
    with open(txt_path, "r", encoding="utf-8") as f:
        raw = f.read()
    body, audio_ref, words, text = raw, None, None, None
    stripped = raw.strip()
    if stripped.startswith("{"):
        try:
            j = json.loads(stripped)
            text = j.get("text") or j.get("script") or ""
            audio_ref = j.get("audio") or j.get("audio_path")
            words = j.get("word_timestamps") or j.get("words")
        except Exception:
            pass
    if text is None:
        m = re.search(r"^\s*(?:#|//)\s*PRE-GEN(?:ERATED)?\s*TTS.*$", stripped, re.M | re.I)
        if m:
            am = re.search(r"^\s*(?:#|//)\s*audio\s*:\s*(.+?)\s*$", stripped, re.M | re.I)
            if am:
                audio_ref = am.group(1).strip().strip('%"')
            # narration = everything except header/meta lines
            lines = [l for l in raw.splitlines()
                     if not re.match(r"^\s*(#|//)", l) and not re.match(r"^\s*(audio|text|voice|model)\s*:", l, re.I)]
            body = "\n".join(lines).strip()
    # resolve local audio path relative to txt or project
    audio_path = None
    if audio_ref:
        cands = [audio_ref,
                 os.path.join(os.path.dirname(txt_path), audio_ref),
                 os.path.join(project_dir, audio_ref),
                 os.path.join(project_dir, "narration" + os.path.splitext(audio_ref)[1])]
        for c in cands:
            if os.path.isfile(c):
                audio_path = c
                break
    return {"text": text if text is not None else body, "audio_path": audio_path,
            "word_timestamps": words, "audio_ref": audio_ref, "mode":
            "audio+text" if audio_path else ("text_only" if body.strip() else "empty")}


def adopt_audio(audio_path: str, project_dir: str, word_timestamps=None, text=None) -> dict:
    """Use user-provided audio as MASTER narration (never re-synthesize)."""
    ext = os.path.splitext(audio_path)[1].lower() or ".wav"
    dest = os.path.join(project_dir, "narration" + ext)
    if os.path.abspath(audio_path) != os.path.abspath(dest):
        with open(audio_path, "rb") as src, open(dest, "wb") as dst:
            dst.write(src.read())
    info = probe(dest)
    if not info.get("duration"):
        raise TTSError(f"unreadable narration audio: {audio_path}")
    if not text:
        raise TTSError("narration text required alongside audio for subtitle alignment")
    ts = word_timestamps or estimate_word_timings(text, info["duration"])
    return {"path": dest, "duration": round(info["duration"], 3), "provider": "user_provided",
            "timing_mode": "word_timestamps" if word_timestamps else "estimated",
            "word_timestamps": ts, "placeholder": False, "text": text}
