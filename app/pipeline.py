"""Pipeline orchestrator.

Implements the master workflow:

  LOAD SCRIPT → GENERATE TTS → ANALYZE AUDIO → SEGMENT SCRIPT →
  SELECT EXISTING ASSETS → BUILD TIMELINE → ADD SUBTITLES →
  ADD MOTION GRAPHICS → ADD TRANSITIONS → ADD GLOBAL EFFECTS →
  ADD MUSIC → RENDER → EXPORT MP4

Narration source priority (never generate TTS twice):
  1. user-provided narration audio      (adopted as-is, MASTER)
  2. user-provided pre-generated TTS    (audio inside package, or text)
  3. existing project narration         (reused on reopen)
  4. TTS API generation                 (only when explicitly selected)
"""
import os, time
from . import paths, settings, tts, segmentation, decision_engine, asset_library, projects, renderer
from .util import probe, read_json


def resolve_narration(meta: dict, options: dict | None = None, log=print) -> dict:
    """Determine the authoritative narration. Returns narration dict and
    updates project. Raises on unusable configuration."""
    options = options or {}
    source = options.get("narration_source") or meta.get("narration_source") or "tts_api"

    # 1) explicit regenerate request
    if options.get("regenerate_tts"):
        log("narration: REGENERATE requested — calling TTS provider")
        return _synthesize(meta, options, log)

    # 2) user-provided narration audio (master)
    up = meta.get("uploaded_narration")
    if up and up.get("kind") == "audio":
        p = os.path.join(meta["dir"], up["file"])
        if os.path.exists(p):
            log("narration: using UPLOADED narration audio (never re-synthesizing)")
            text = options.get("script") or meta.get("script") or ""
            return tts.adopt_audio(p, meta["dir"], text=text)

    # 3) pre-generated TTS package
    if up and up.get("kind") == "text":
        p = os.path.join(meta["dir"], up["file"])
        if os.path.exists(p):
            pkg = tts.parse_tts_package(p, meta["dir"])
            if pkg.get("text"):
                # the supplied TXT is the AUTHORITATIVE narration text — adopt it
                # as the project script (never rewritten or paraphrased)
                if (meta.get("script") or "").strip() != pkg["text"].strip():
                    meta["script"] = pkg["text"]
                    projects.save(meta)
                    log("narration: package text adopted as authoritative script")
            if pkg.get("audio_path"):
                log("narration: using PRE-GENERATED TTS package audio")
                return tts.adopt_audio(pkg["audio_path"], meta["dir"],
                                       word_timestamps=pkg.get("word_timestamps"), text=pkg["text"])
            if pkg.get("audio_ref") and not pkg.get("audio_path"):
                raise RuntimeError(
                    f"pre-generated TTS package references audio '{pkg['audio_ref']}' "
                    f"but the file was not found — upload it via [ NARRATION AUDIO ]")
            if pkg.get("text") and source in ("pregenerated_tts_text", "uploaded", "auto"):
                log("narration: pre-generated TTS is text-only — synthesizing once from package text")
                return _synthesize(meta, options, log, override_text=pkg["text"])

    # 4) existing project narration (reuse on reopen)
    existing = projects.project_narration_file(meta)
    if existing and (meta.get("narration") or {}).get("duration") and source != "tts_api":
        if source in ("uploaded", "project_existing", "auto"):
            log("narration: reusing EXISTING project narration")
            return meta["narration"]

    # 5) generate
    if source in ("tts_api", "auto", "pregenerated_tts_text"):
        return _synthesize(meta, options, log)
    raise RuntimeError(f"no usable narration source for mode '{source}'")


def _synthesize(meta, options, log, override_text=None):
    text = override_text if override_text is not None else (options.get("script") or meta.get("script"))
    if not text:
        raise RuntimeError("no script text to synthesize")
    provider = options.get("tts_provider") or settings.get("tts.provider", "espeak_offline")
    out = os.path.join(meta["dir"], "narration_generated.wav")
    log(f"narration: generating TTS via '{provider}'")
    res = tts.synthesize(text, out, force_provider=provider)
    res["source"] = "tts_api"
    if res.get("placeholder"):
        log("WARNING: TTS produced a TIMING PLACEHOLDER (silent bed) — clearly flagged for review")
    return res


def analyze_and_segment(meta: dict, narration: dict, log=print):
    log(f"audio: {narration['duration']:.1f}s master timeline "
        f"(timing mode: {narration.get('timing_mode')})")
    segments = segmentation.segment_script(meta["script"], narration)
    log(f"segmentation: {len(segments)} semantic segments "
        f"(avg {sum(s['duration'] for s in segments)/max(1,len(segments)):.1f}s)")
    return segments


def build_timeline(meta: dict, segments: list, log=print):
    seed = int(options_seed(meta))
    tl = decision_engine.build_timeline(segments, meta["project_id"], seed=seed,
                                        options={"narration": meta.get("narration") or {}})
    n_assets = sum(1 for s in tl["segments"] if s.get("asset_id"))
    n_mg = sum(1 for s in tl["segments"] if s.get("motion_graphic"))
    n_typo = sum(1 for s in tl["segments"] if s.get("fallback") == "__typography__")
    log(f"timeline: {len(tl['segments'])} segments · {n_assets} library assets · "
        f"{n_mg} motion graphics · {n_typo} typography fallbacks · "
        f"{tl['review_flags']} review flags")
    return tl


def options_seed(meta):
    import hashlib
    return int(hashlib.sha1((meta["project_id"] + str(meta.get("updated_at", 0))).encode()).hexdigest()[:8], 16)


def generate_video(project_id: str, options: dict | None = None, log_cb=print) -> dict:
    """The big button: full pipeline from script to MP4."""
    options = options or {}
    meta = projects.get(project_id)
    if not meta:
        raise KeyError(project_id)
    if options.get("script"):
        meta["script"] = options["script"]
    if options.get("preset"):
        apply_preset(options["preset"])
        meta["preset"] = options["preset"]

    meta["status"] = "narration"
    projects.save(meta)
    narration = resolve_narration(meta, options, log_cb)
    meta["narration"] = narration
    meta["narration_source"] = ("uploaded" if narration.get("provider") == "user_provided"
                                else ("tts_api" if not narration.get("source") else narration["source"]))
    projects.log_event(meta, f"narration resolved: {narration.get('provider')} "
                             f"{narration['duration']:.1f}s ({narration.get('timing_mode')})")

    meta["status"] = "segmentation"
    segments = analyze_and_segment(meta, narration, log_cb)
    meta["segments"] = segments

    meta["status"] = "timeline"
    tl = build_timeline(meta, segments, log_cb)
    meta["timeline"] = tl
    projects.save(meta)

    meta["status"] = "render"
    result = renderer.render_project(meta, log_cb=log_cb)
    meta["render_result"] = result
    meta["status"] = "done"
    projects.save(meta)
    # usage bookkeeping
    for s in tl["segments"]:
        if s.get("asset_id"):
            asset_library.mark_used(s["asset_id"])
    log_cb(f"done: {result['file']} ({result['size_mb']} MB)")
    return {"project": {k: v for k, v in meta.items() if k != "dir"}, "render": result}


def regenerate_scene(project_id: str, segment_id: str, log_cb=print):
    """REGENERATE SCENE without regenerating the project."""
    meta = projects.get(project_id)
    if not meta or not meta.get("timeline"):
        raise KeyError(project_id)
    seg = decision_engine.regenerate_segment(meta["timeline"]["segments"], segment_id)
    projects.save(meta)
    log_cb(f"scene {segment_id} regenerated → {seg.get('asset_name') or seg.get('fallback')}")
    return seg


def apply_preset(name: str):
    from .util import read_json
    p = os.path.join(paths.PRESETS_DIR, name + ".json")
    if not os.path.exists(p):
        raise KeyError(f"preset not found: {name}")
    preset = read_json(p, {})
    patch = {}
    for key in ("render", "subtitles", "music", "transitions", "effects", "motion_graphics"):
        if key in preset:
            patch[key] = preset[key]
    if "asset_rules" in preset:
        patch["repetition"] = preset["asset_rules"].get("repetition", {})
        patch["scoring"] = preset["asset_rules"].get("scoring", {})
    if "tts" in preset:
        patch["tts"] = {**settings.get("tts", {}), **preset["tts"]}
    settings.update(patch)
    return preset


def list_presets() -> list:
    out = []
    for fn in sorted(os.listdir(paths.PRESETS_DIR)):
        if fn.endswith(".json"):
            data = read_json(os.path.join(paths.PRESETS_DIR, fn), {})
            out.append({"name": fn[:-5], "description": data.get("description", ""),
                        "style": data.get("style", {})})
    return out
