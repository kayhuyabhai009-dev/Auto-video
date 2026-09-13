"""FFmpeg render pipeline.

MASTER RULE: narration audio is the master timeline. Visual clips, subtitles,
motion graphics, music and effects all adapt to it.

Pipeline stages
  1. collapse hold-chains into render units (no-cut intelligence)
  2. render each unit as a timing-exact clip (image Ken Burns / video
     trim+crop+loop / texture / designed typography card)
  3. assemble (concat demuxer, or true xfade chain in xfade mode —
     crossfades overlap so total duration is preserved)
  4. final pass: burn subtitles (ASS), overlay motion graphics with entrance
     animations, apply global effect chain, build the audio graph
     (narration + evolving ducked music + justified SFX), loudness-normalize
  5. export MP4 + poster + per-scene preview stills
"""
import os, shutil, subprocess, math
from PIL import Image, ImageDraw
from . import motion_graphics as mg
from . import settings as cfgmod
from . import asset_library, subtitles as subs_engine, paths
from .util import ffmpeg, probe, run, fmt_ts, new_id, ffmpeg_path

TYPO_DIR = None  # set lazily


# ------------------------------------------------------------------ units
def collapse_units(timeline: list) -> list:
    """Merge hold-chains: a segment whose entrance is 'hold' joins the previous
    render unit (single continuous clip = perfect no-cut hold)."""
    units = []
    for entry in timeline:
        t = entry.get("transition", {}).get("type", "hard_cut")
        if t == "hold" and units:
            units[-1]["entries"].append(entry)
            units[-1]["end"] = entry["end"]
            units[-1]["duration"] = round(units[-1]["end"] - units[-1]["start"], 3)
        else:
            units.append({"start": entry["start"], "end": entry["end"],
                          "duration": round(entry["end"] - entry["start"], 3),
                          "entries": [entry],
                          "entrance": entry.get("transition", {}),
                          "asset_id": entry.get("asset_id"),
                          "asset_type": entry.get("asset_type"),
                          "fallback": entry.get("fallback"),
                          "role": entry.get("role"),
                          "motion": entry.get("motion")})
    for i, u in enumerate(units):
        u["index"] = i
    return units


# ------------------------------------------------------------------ filters
def _cover(pad_w, pad_h, w, h, x_expr=None, y_expr=None):
    s = (f"scale={pad_w}:{pad_h}:force_original_aspect_ratio=increase,"
         f"crop={w}:{h}")
    if x_expr is not None:
        s = (f"scale={pad_w}:{pad_h}:force_original_aspect_ratio=increase,"
             f"crop={w}:{h}:x='{x_expr}':y='{y_expr if y_expr else 0}'")
    return s


def _kenburns(motion: dict, dur: float, W: int, H: int, fps: int, settle_in=0.0) -> str:
    """zoompan Ken Burns; subtle 3-8% motion; optional entrance settle."""
    amt = float(motion.get("amount", 0.05)) if motion else 0.0
    kind = (motion or {}).get("type", "static")
    frames = max(2, int(dur * fps))
    zmax = 1.0 + max(0.02, amt)
    cx = "iw/2-(iw/zoom/2)"
    cy = "ih/2-(ih/zoom/2)"
    if settle_in > 0:
        dfr = max(2, int(settle_in * fps))
        z = f"'{zmax + 0.05}-0.05*min(on/{dfr}\\,1)'"
        return f"zoompan=z={z}:x='{cx}':y='{cy}':d={frames}:s={W}x{H}:fps={fps}"
    if kind in ("zoom_in", "kenburns"):
        z = f"'min(1.0+{zmax - 1.0}*on/{frames}\\,{zmax})'"
        x = cx
        y = cy
        if kind == "kenburns":
            x = f"'(iw-iw/zoom)*(on/{frames})*0.6+iw/2-(iw/zoom/2)-((iw-iw/zoom)*0.3)'"
    elif kind == "zoom_out":
        z = f"'max({zmax}-({zmax - 1.0})*on/{frames}\\,1.0)'"
        x, y = cx, cy
    elif kind == "pan_left":
        z = f"'{max(1.04, zmax - 0.02)}'"
        x = f"'(iw-iw/zoom)*(1-on/{frames})'"
        y = cy
    elif kind == "pan_right":
        z = f"'{max(1.04, zmax - 0.02)}'"
        x = f"'(iw-iw/zoom)*(on/{frames})'"
        y = cy
    elif kind == "pan_up":
        z = f"'{max(1.04, zmax - 0.02)}'"
        x = cx
        y = f"'(ih-ih/zoom)*(1-on/{frames})'"
    elif kind == "pan_down":
        z = f"'{max(1.04, zmax - 0.02)}'"
        x = cx
        y = f"'(ih-ih/zoom)*(on/{frames})'"
    else:
        z = "'1.0'"
        x, y = "0", "0"
    return f"zoompan=z={z}:x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={fps}"


_TINTS = {
    "red": "colorchannelmixer=rr=1.05:gg=0.96:bb=0.94",
    "blue": "colorchannelmixer=rr=0.96:gg=1.0:bb=1.06",
    "amber": "colorchannelmixer=rr=1.05:gg=1.01:bb=0.9",
    "gray": "eq=saturation=0.72",
    "bone": None,
}


def _grade(unit) -> str:
    parts = ["eq=contrast=1.05:saturation=0.9:gamma=0.99"]
    tint = (unit.get("entries", [{}])[0].get("visual_intent") or {}).get("tint", "bone")
    t = _TINTS.get(tint)
    if t:
        parts.append(t)
    return ",".join(parts)


# ------------------------------------------------------------------ typography card
def typography_card_png(entry, out_path, W, H):
    """Designed text card for segments with no usable asset (fallback:
    typography). Shows the narration fragment as an intentional quote panel."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    role = (entry.get("role") or "").replace("_", " ")
    text = entry.get("voiceover_summary") or entry.get("text") or ""
    accent = {"PROBLEM": "oxide_red", "COUNTEREXAMPLE": "uncertainty_gray",
              "PRACTICAL_MOVE": "signal_blue", "SOURCE": "muted_amber"}.get(entry.get("role", ""), "bone")
    panel_w = 1040
    x0 = (W - panel_w) // 2
    f = mg.font(56, bold=True)
    lines = mg.wrap_text(draw, "“" + text + "”", f, panel_w - 120)[:4]
    box_h = 200 + len(lines) * 74
    y0 = (H - box_h) // 2
    mg.frame(draw, x0, y0, panel_w, box_h, accent, soft=True)
    mg.kicker_bar(draw, x0 + 60, y0 + 44, role + " — VISUAL NOTE", accent, 26)
    yy = y0 + 110
    for ln in lines:
        draw.text((x0 + 60, yy), ln, font=f, fill=mg.RGBA["bone"])
        yy += 74
    mg.rule(draw, x0 + 60, y0 + box_h - 60, x0 + panel_w - 60, accent, 150, 2)
    img.convert("RGB").save(out_path, quality=92)
    return out_path


# ------------------------------------------------------------------ unit clip
def render_unit_clip(unit, out_path, W, H, fps, crf=22, preset="veryfast", asset_lookup=None,
                     bake_fades=True):
    entry = unit["entries"][0]
    dur = unit["duration"]
    if dur < 0.2:
        dur = 0.2
    frames = max(1, int(round(dur * fps)))
    asset = asset_lookup.get(unit.get("asset_id")) if asset_lookup else None
    fallback = unit.get("fallback")
    settle = 0.0
    ent = unit.get("entrance") or {}
    if ent.get("type") == "zoom" and ent.get("duration"):
        settle = float(ent["duration"])
    extra_w = 0
    x_expr = None
    if ent.get("type") == "slide" and ent.get("duration"):
        extra_w = 200
        d = float(ent["duration"])
        x_expr = f"(iw-ow)/2+(iw-ow)/2*(1-min(t/{d},1))"

    vf_parts = []
    src_is_still = True
    args = []
    if asset and asset["type"] == "video":
        src_is_still = False
        args += ["-stream_loop", "-1", "-i", asset["path"]]
        cover_w = W + extra_w
        vf_parts.append(_cover(cover_w, H, W, H, x_expr=x_expr,
                               y_expr="(ih-oh)/2" if extra_w else None))
        vf_parts.append(f"fps={fps}")
    elif asset and asset["type"] == "image":
        args += ["-i", asset["path"]]
        pre = 2 * H
        vf_parts.append(f"scale=-2:{pre}")
        vf_parts.append(_kenburns(unit.get("motion"), dur, W, H, fps, settle_in=settle))
        if extra_w:
            vf_parts.append(_cover(W + extra_w, H, W, H, x_expr=x_expr, y_expr="(ih-oh)/2"))
    else:
        # texture fallback or designed typography card
        if fallback == "__texture__":
            texs = [a for a in asset_library.all_assets(kind="image")
                    if a["category"] == "textures"]
            tex = texs[hash(unit["start"]) % max(1, len(texs))] if texs else None
            if tex:
                args += ["-i", tex["path"]]
                vf_parts.append(f"scale=-2:{2 * H}")
                vf_parts.append(_kenburns({"type": "kenburns", "amount": 0.05}, dur, W, H, fps))
        if not args:
            png = os.path.join(os.path.dirname(out_path), f"typo_{unit['index']:03d}.jpg")
            typography_card_png(entry, png, W, H)
            args += ["-i", png]
            vf_parts.append(f"scale=-2:{2 * H}")
            vf_parts.append(_kenburns({"type": "zoom_in", "amount": 0.045}, dur, W, H, fps))
    grade = _grade(unit)
    if grade:
        vf_parts.append(grade)
    # entrance effects baked into the unit clip
    if bake_fades:
        if ent.get("type") in ("fade", "dissolve", "blur") and ent.get("duration"):
            vf_parts.append(f"fade=t=in:st=0:d={ent['duration']:.2f}")
        elif ent.get("type") == "flash" and ent.get("duration"):
            vf_parts.append(f"fade=t=in:st=0:d={ent['duration'] * 0.8:.2f}:color=white")
        elif ent.get("type") == "evidence_pivot" and ent.get("duration"):
            vf_parts.append(f"fade=t=in:st=0:d={ent['duration'] * 0.8:.2f}:color=0xD0A457")
        elif ent.get("type") == "fade_from_black":
            vf_parts.append("fade=t=in:st=0:d=0.9")
    # exit effect (needed when the NEXT unit dips through black / pivot)
    if bake_fades and unit.get("_exit_fade"):
        d = unit["_exit_fade"]
        vf_parts.append(f"fade=t=out:st={max(0, dur - d):.2f}:d={d:.2f}")
    if bake_fades and unit.get("_exit_color_fade"):
        d, col = unit["_exit_color_fade"]
        vf_parts.append(f"fade=t=out:st={max(0, dur - d):.2f}:d={d:.2f}:color={col}")
    vf_parts.append("format=yuv420p")
    cmd = args + ["-vf", ",".join(vf_parts), "-frames:v", str(frames), "-r", str(fps),
            "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-an", out_path]
    ffmpeg(cmd, timeout=900, log_path=out_path + ".log")
    return out_path


# ------------------------------------------------------------------ assemble
def plan_unit_exits(units: list):
    """Derive A-side exit effects from the next unit's entrance (filter mode)."""
    for i in range(len(units) - 1):
        ent = units[i + 1].get("entrance") or {}
        t, d = ent.get("type"), float(ent.get("duration") or 0)
        if t in ("fade", "dissolve", "blur") and d:
            units[i]["_exit_fade"] = min(d, units[i]["duration"] * 0.5)
        elif t == "evidence_pivot" and d:
            units[i]["_exit_color_fade"] = (min(d * 0.7, units[i]["duration"] * 0.5), "0x7a3a30")
    return units


def assemble_filter_mode(units: list, workdir: str, W, H, fps, crf, preset) -> str:
    base = os.path.join(workdir, "base.mp4")
    listf = os.path.join(workdir, "concat.txt")
    with open(listf, "w") as f:
        for u in units:
            f.write(f"file '{u['clip_path']}'\n")
    run([ffmpeg_path(), "-hide_banner", "-nostdin", "-y", "-f", "concat", "-safe", "0",
         "-i", listf, "-c", "copy", base], timeout=600, log_path=os.path.join(workdir, "concat.log"))
    return base


def assemble_xfade_mode(units: list, workdir: str, W, H, fps, crf, preset) -> str:
    """True crossfades; each unit rendered with tail allowance so total
    duration still matches the narration master exactly."""
    base = os.path.join(workdir, "base_x.mp4")
    inputs = []
    for u in units:
        inputs += ["-i", u["clip_path"]]
    lines = []
    XFADE_MAP = {"fade": "fade", "dissolve": "dissolve", "zoom": "zoomin",
                 "slide": "smoothleft", "blur": "hblur", "flash": "fadewhite",
                 "glitch": "pixelize", "light_leak": "dissolve",
                 "evidence_pivot": "dissolve", "hard_cut": "fade",
                 "fade_from_black": "fade"}
    prev = "[0:v]"
    offset = 0.0
    for i in range(1, len(units)):
        ent = units[i].get("entrance") or {}
        d = float(ent.get("duration") or 0.04) if ent.get("type") not in ("hard_cut", None) else 0.04
        offset = units[i]["start"]
        tr = XFADE_MAP.get(ent.get("type"), "fade")
        out = f"[x{i}]"
        lines.append(f"{prev}[{i}:v]xfade=transition={tr}:duration={d:.2f}:offset={offset:.3f}{out}")
        prev = out
    script = os.path.join(workdir, "xfade.txt")
    with open(script, "w") as f:
        f.write(";\n".join(lines))
    cmd = inputs + [
        "-filter_complex_script", script, "-map", prev,
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-an", base]
    ffmpeg(cmd, timeout=1800, log_path=os.path.join(workdir, "xfade.log"))
    return base


# ------------------------------------------------------------------ motion graphics overlays
def prepare_motion_graphics(timeline, workdir):
    """Render MG PNGs; returns list of overlay plans."""
    plans = []
    for entry in timeline:
        m = entry.get("motion_graphic")
        if not m:
            continue
        template, params = mg.params_from_segment(entry)
        try:
            img = mg.render_graphic(template, params, seed=int(entry["start"] * 7) % 9999)
        except Exception as e:
            continue
        png = os.path.join(workdir, f"{m.get('id', 'mg')}_{len(plans):03d}.png")
        img.save(png)
        anim = m.get("anim", "fade")
        plans.append({"png": png, "start": entry["start"], "end": entry["end"],
                      "anim": anim, "entry": entry})
    return plans


# ------------------------------------------------------------------ audio graph
def _select_music_tracks(timeline, total):
    """AUTO mode: pick mood-appropriate tracks; evolve across mood runs."""
    mode = cfgmod.get("music.mode", "auto")
    music_assets = asset_library.all_assets(kind="music")
    if not music_assets or mode == "off":
        return []
    if mode in ("fixed", "random") or not cfgmod.get("music.base_volume", 0.28):
        pass
    if mode == "fixed":
        fixed = cfgmod.get("music.fixed_track", "")
        tr = next((a for a in music_assets if fixed.lower() in a["filename"].lower()), music_assets[0])
        return [{"asset": tr, "start": 0.0, "end": total, "volume": cfgmod.get("music.base_volume", 0.28)}]
    if mode == "random":
        tr = music_assets[hash(total) % len(music_assets)]
        return [{"asset": tr, "start": 0.0, "end": total, "volume": cfgmod.get("music.base_volume", 0.28)}]
    # auto: map moods in order, group contiguous runs >= 6s
    MOOD_FILES = {"hook": ["hook_pulse", "noir_pulse"], "bed": ["documentary_bed", "noir_pulse"],
                  "open": ["open_tape", "documentary_bed"], "sparse": ["sparse_tension", "near_silence"],
                  "near_silence": ["near_silence"], "resolve": ["resolve_warm", "open_tape"]}
    MOOD_VOL = {"hook": 1.0, "bed": 1.0, "open": 1.0, "sparse": 0.7, "near_silence": 0.4, "resolve": 0.9}
    segs = []
    for e in timeline:
        mood = (e.get("music") or {}).get("mood", "bed")
        segs.append((e["start"], e["end"], mood))
    runs = []
    for s, e, m in segs:
        if runs and runs[-1][2] == m and s - runs[-1][1] < 0.6:
            runs[-1][1] = e
        else:
            runs.append([s, e, m])
    merged = []
    for r in runs:
        if merged and (r[1] - merged[-1][1]) < 6.0 and merged[-1][2] == r[2]:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    # coalesce micro-runs into previous
    out = []
    for r in merged:
        if out and (r[1] - r[0]) < 5.0:
            out[-1][1] = r[1]
        else:
            out.append(r)
    base_vol = cfgmod.get("music.base_volume", 0.28)
    plans = []
    for s, e, m in out:
        cands = MOOD_FILES.get(m, MOOD_FILES["bed"])
        tr = next((a for c in cands for a in music_assets if c in a["filename"].lower()), None) or music_assets[0]
        plans.append({"asset": tr, "start": s, "end": e, "volume": base_vol * MOOD_VOL.get(m, 1.0)})
    return plans


def build_audio_filter(timeline, narration_path, total, workdir, input_offset=0):
    """Returns (filter_script, input_args, output_label, n_inputs).
    input_offset shifts audio input indices (base video occupies input 0)."""
    off = input_offset
    lines = []
    inputs = ["-i", narration_path]
    n = 1
    voice = f"[{off}:a]"
    # normalize voice
    lines.append(f"{voice}aformat=sample_rates=48000:channel_layouts=stereo[voice]")
    music_plans = _select_music_tracks(timeline, total)
    duck_parts = []
    for i, p in enumerate(music_plans):
        a = p["asset"]
        inputs += ["-stream_loop", "-1", "-i", a["path"]]
        idx = n + off
        n += 1
        dur = max(0.5, p["end"] - p["start"])
        # loop (input-side), trim, volume, fades, delay to start
        f = (f"[{idx}:a]atrim=0:{dur:.3f},"
             f"asetpts=PTS-STARTPTS,volume={p['volume']:.3f},"
             f"afade=t=in:d={min(2.0, dur/3):.2f},afade=t=out:st={max(0.1, dur - 3.5):.2f}:d={min(3.5, dur/2):.2f},"
             f"aformat=sample_rates=48000:channel_layouts=stereo,adelay={int(p['start']*1000)}|{int(p['start']*1000)}"
             f"[mus{i}]")
        duck_parts.append(f"[mus{i}]")
        lines.append(f)
    if duck_parts:
        if len(duck_parts) == 1:
            lines.append(f"{duck_parts[0]}anull[musmix]")
        else:
            lines.append("".join(duck_parts) +
                         f"amix=inputs={len(duck_parts)}:duration=longest:normalize=0[musmix]")
        duck_cfg = cfgmod.get("music.ducking", {})
        if duck_cfg.get("enabled", True):
            # voice feeds BOTH the sidechain and the final mix -> split it
            lines.append("[voice]asplit=2[voiceSC][voiceMix]")
            lines.append(
                f"[musmix][voiceSC]sidechaincompress=threshold={duck_cfg.get('threshold', 0.02)}:"
                f"ratio={duck_cfg.get('ratio', 8)}:attack={duck_cfg.get('attack', 120)}:"
                f"release={duck_cfg.get('release', 900)}[ducked]")
            music_label = "[ducked]"
            voice = "[voiceMix]"
        else:
            music_label = "[musmix]"
    else:
        music_label = None
    # sfx
    sfx_labels = []
    for entry in timeline:
        s = entry.get("sfx")
        if not s:
            continue
        asset = asset_library.get(s["asset_id"])
        if not asset:
            continue
        inputs += ["-i", asset["path"]]
        idx = n + off
        n += 1
        at = int(float(s.get("at", entry["start"])) * 1000)
        vol = float(s.get("volume", 0.5))
        lines.append(f"[{idx}:a]volume={vol:.2f},aformat=sample_rates=48000:channel_layouts=stereo,"
                     f"adelay={at}|{at}[sfx{n}]")
        sfx_labels.append(f"[sfx{n}]")
    # final mix
    parts = [voice] + ([music_label] if music_label else []) + sfx_labels
    if len(parts) == 1:
        lines.append(f"{parts[0]}anull[mixpre]")
    else:
        lines.append("".join(parts) + f"amix=inputs={len(parts)}:duration=first:normalize=0[mixpre]")
    lines.append(f"[mixpre]loudnorm=I=-16:TP=-1.5:LRA=11[aout]")
    return "\n;\n".join(lines), inputs, "[aout]", n


# ------------------------------------------------------------------ main render
def render_project(project: dict, log_cb=None, only_missing_previews=False) -> dict:
    res = cfgmod.get("render.resolution", "1920x1080").split("x")
    W, H = int(res[0]), int(res[1])
    fps = int(cfgmod.get("render.fps", 30))
    crf = int(cfgmod.get("render.crf", 20))
    preset = cfgmod.get("render.preset", "medium")
    xfade_mode = cfgmod.get("render.transition_mode", "filter") == "xfade"
    tail = float(cfgmod.get("render.tail_seconds", 0.6))
    workdir = os.path.join(project["dir"], "work")
    previews_dir = os.path.join(project["dir"], "previews")
    os.makedirs(workdir, exist_ok=True)
    os.makedirs(previews_dir, exist_ok=True)
    timeline = project["timeline"]["segments"]
    narration = project["narration"]
    total = round(narration["duration"] + tail, 3)
    proj_id = project["project_id"]

    def log(msg):
        if log_cb:
            log_cb(msg)
        print("[render]", msg)

    # 1. units
    units = collapse_units(timeline)
    plan_unit_exits(units)
    asset_lookup = {a["asset_id"]: a for a in asset_library.index().values()}
    if xfade_mode:
        for i, u in enumerate(units):
            u["_render_dur"] = u["duration"] + ((units[i + 1].get("entrance") or {}).get("duration") or 0.04
                                                if i < len(units) - 1 else 0)
    else:
        for u in units:
            u["_render_dur"] = u["duration"]

    # 2. unit clips
    for u in units:
        clip = os.path.join(workdir, f"unit_{u['index']:03d}.mp4")
        u["clip_path"] = clip
        need = True
        if os.path.exists(clip):
            info = probe(clip)
            if info.get("duration") and abs(info["duration"] - u["_render_dur"]) < 0.12:
                need = False
        if need:
            log(f"unit {u['index']:03d}  {u['start']:.1f}s→{u['end']:.1f}s  "
                f"asset={u.get('asset_name') or u.get('fallback')}")
            render_unit_clip(u, clip, W, H, fps, crf=min(28, crf + 6), preset="veryfast",
                             asset_lookup=asset_lookup, bake_fades=not xfade_mode)

    # 3. assemble
    if xfade_mode and len(units) > 1:
        base = assemble_xfade_mode(units, workdir, W, H, fps, crf, preset)
    else:
        base = assemble_filter_mode(units, workdir, W, H, fps, crf, preset)
    log(f"assembled base timeline ({total:.1f}s target)")

    # 4. final pass
    ass_path = os.path.join(project["dir"], "subtitles.ass")
    subs_engine.build_ass(timeline, ass_path, narration_meta=narration)
    mg_plans = prepare_motion_graphics(timeline, workdir)

    final = os.path.join(project["dir"], "final.mp4")
    inputs = ["-i", base]
    flines = ["[0:v]null[bas]"]
    cur = "[bas]"
    # subtitles
    flines.append(f"{cur}subtitles=filename='{ass_path}':fontsdir='{paths.STATIC_DIR}/fonts'[subt]")
    cur = "[subt]"
    # motion graphics overlays
    for i, p in enumerate(mg_plans):
        inputs += ["-loop", "1", "-t", f"{max(0.3, p['end'] - p['start']):.3f}", "-i", p["png"]]
        idx = i + 1
        dur = p["end"] - p["start"]
        chain = f"[{idx}:v]format=rgba,fade=t=in:st=0:d=0.45:alpha=1"
        if dur > 0.8:
            chain += f",fade=t=out:st={dur - 0.4:.2f}:d=0.4:alpha=1"
        if p["anim"] == "slide":
            chain = f"[{idx}:v]format=rgba,fade=t=in:st=0:d=0.3:alpha=1"
        chain += f",setpts=PTS+{p['start']:.3f}/TB[mg{i}]"
        flines.append(chain)
        x = "(main_w-overlay_w)/2"
        y = "(main_h-overlay_h)/2"
        if p["anim"] == "slide":
            x = f"(main_w-overlay_w)/2+60*max(0,1-(t-{p['start']:.2f})/0.5)"
        flines.append(f"{cur}[mg{i}]overlay=x='{x}':y='{y}':eof_action=pass[ov{i}]")
        cur = f"[ov{i}]"
    # global effects
    from .effects import global_video_filters
    gchain = global_video_filters(cfgmod.get("effects", {}), W, H)
    if gchain:
        flines.append(f"{cur}" + ",".join(gchain) + "[gfx]")
        cur = "[gfx]"
    flines.append(f"{cur}format=yuv420p[vout]")
    # audio
    audio_script, ainputs, aout, _ = build_audio_filter(timeline, narration["path"], total,
                                                        workdir, input_offset=1 + len(mg_plans))
    inputs += ainputs
    for line in audio_script.split("\n;\n"):
        flines.append(line)

    script_path = os.path.join(workdir, "final_filter.txt")
    with open(script_path, "w") as f:
        f.write(";\n".join(flines))
    cmd = (inputs +
           ["-filter_complex_script", script_path,
            "-map", "[vout]", "-map", aout,
            "-t", f"{total:.3f}",
            "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-c:a", "aac", "-b:a", cfgmod.get("render.audio_bitrate", "192k"),
            "-movflags", "+faststart", final])
    log("final pass: subtitles + motion graphics + effects + music/SFX mix")
    ffmpeg(cmd, timeout=3600, log_path=os.path.join(project["dir"], "render.log"))

    info = probe(final)
    log(f"render complete: final.mp4 ({info.get('duration', 0):.1f}s, {info.get('width')}x{info.get('height')})")

    # 5. poster + scene previews
    poster = os.path.join(project["dir"], "poster.jpg")
    ffmpeg(["-ss", "6", "-i", final, "-frames:v", "1", "-q:v", "3", poster], timeout=120)
    for entry in timeline:
        pv = os.path.join(previews_dir, f"scene_{entry['segment_id']}.jpg")
        if only_missing_previews and os.path.exists(pv):
            continue
        mid = (entry["start"] + entry["end"]) / 2
        try:
            ffmpeg(["-ss", f"{mid:.2f}", "-i", final, "-frames:v", "1", "-q:v", "4", pv], timeout=120)
        except Exception:
            pass
    # cleanup work dir (keep final + previews + logs; large intermediates go)
    for u in units:
        if os.path.exists(u.get("clip_path", "")):
            os.remove(u["clip_path"])
    for stray in ("base.mp4", "base_x.mp4", "concat.txt", "concat.log", "xfade.txt", "xfade.log",
                  "final_filter.txt"):
        p = os.path.join(workdir, stray)
        if os.path.exists(p):
            os.remove(p)
    for fn in os.listdir(workdir):
        if fn.endswith((".png", ".jpg")) :
            try:
                os.remove(os.path.join(workdir, fn))
            except OSError:
                pass
    return {"file": final, "duration": info.get("duration", total), "width": info.get("width", W),
            "height": info.get("height", H), "size_mb": round(os.path.getsize(final) / 1e6, 1)}


def render_scene_preview(project: dict, segment_id: str) -> str:
    """Quick single-scene preview clip (for REGENERATE SCENE workflows)."""
    res = cfgmod.get("render.resolution", "1920x1080").split("x")
    W, H = int(res[0]), int(res[1])
    fps = int(cfgmod.get("render.fps", 30))
    entry = next((e for e in project["timeline"]["segments"] if e["segment_id"] == segment_id), None)
    if not entry:
        raise KeyError(segment_id)
    unit = {"index": 0, "start": 0.0, "end": entry["end"] - entry["start"], "duration": entry["end"] - entry["start"],
            "entries": [entry], "entrance": {"type": "fade_from_black"}, "asset_id": entry.get("asset_id"),
            "asset_type": entry.get("asset_type"), "fallback": entry.get("fallback"),
            "role": entry.get("role"), "motion": entry.get("motion")}
    asset_lookup = {a["asset_id"]: a for a in asset_library.index().values()}
    out = os.path.join(project["dir"], "previews", f"clip_{segment_id}.mp4")
    render_unit_clip(unit, out, W, H, fps, crf=22, preset="veryfast", asset_lookup=asset_lookup)
    return out
