"""Subtitle engine.

Generates a styled .ass file synchronized to narration word timings.
Default is cinematic SELECTIVE subtitles; FULL CAPTION MODE covers every
segment for accessibility. Color logic: BONE normal text; OXIDE RED pressure;
SIGNAL BLUE agency/action; MUTED AMBER source/history; UNCERTAINTY GRAY
hedging/limits. Accents are applied to individual words only.
"""
import os
from . import lexicon
from . import settings as cfgmod
from .util import fmt_ts

PAL = {k: v.lstrip("#") for k, v in lexicon.PALETTE.items()}


def _ass_color(hex6, alpha=0):          # RGB hex -> &HAABBGGRR
    r, g, b = hex6[0:2], hex6[2:4], hex6[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _wrap_lines(words, max_chars, max_lines):
    """Greedy wrap of timed words into lines; returns list of lines (each a list of word dicts)."""
    lines, cur, cur_len = [], [], 0
    for w in words:
        ww = w["word"]
        add = len(ww) + (1 if cur else 0)
        if cur and cur_len + add > max_chars:
            lines.append(cur)
            cur, cur_len = [w], len(ww)
        else:
            cur.append(w)
            cur_len += add
    if cur:
        lines.append(cur)
    return lines


def _accented(line_words, accents_on, anim):
    """Build ASS text for one line with per-word semantic colors."""
    out = []
    for w in line_words:
        word = w["word"].replace("{", "").replace("}", "")
        accent = lexicon.word_accent(word)
        color = None
        if accents_on and accent:
            color = {"red": "oxide_red", "blue": "signal_blue", "amber": "muted_amber",
                     "gray": "uncertainty_gray"}[accent]
        emph = accents_on and lexicon.is_emphasis(word)
        tag = ""
        if color:
            tag += "{\\c" + _ass_color(PAL[color]) + "\\b1}"
        elif emph and anim == "word_highlight":
            tag += "{\\c" + _ass_color(PAL["muted_amber"]) + "}"
        if anim == "word_highlight" and not color and not emph:
            tag += "{\\2c" + _ass_color(PAL["signal_blue"]) + "}" if False else ""
        if anim == "typewriter":
            tag += "{\\k%d}" % max(1, int((w.get("end", w.get("start", 0)) - w.get("start", 0)) * 100))
        out.append(tag + word)
        if color or (emph and anim == "word_highlight"):
            out[-1] += "{\\r}"
    return " ".join(out)


def build_ass(timeline, out_path, subtitle_cfg=None, narration_meta=None):
    cfg = {**cfgmod.get("subtitles", {}), **(subtitle_cfg or {})}
    mode = cfg.get("mode", "selective")
    header = _style_header(cfg)
    events = []
    selective_roles = {"HOOK_SIGNAL", "PROMISE", "MECHANISM", "PRACTICAL_MOVE", "SOURCE",
                       "COUNTEREXAMPLE", "RECAP", "DEFINITION", "EMOTIONAL_RECOGNITION", "LIMITATION",
                       "PROBLEM", "NEXT_WATCH"}
    anim = cfg.get("animation", "fade")
    for seg in timeline:
        if mode == "off":
            break
        if mode == "selective":
            has_accentable = any(lexicon.word_accent(w["word"]) for w in seg.get("words", []))
            if seg["role"] not in selective_roles and not has_accentable and not seg.get("emphasis_words"):
                continue
        words = seg.get("words") or []
        if not words:
            continue
        # build cues of up to max_lines lines
        lines = _wrap_lines(words, cfg.get("max_chars", 42), cfg.get("max_lines", 2))
        per_cue = max(1, int(cfg.get("max_lines", 2)))
        for i in range(0, len(lines), per_cue):
            cue_lines = lines[i:i + per_cue]
            t0 = cue_lines[0][0]["start"]
            t1 = cue_lines[-1][-1]["end"] + 0.12
            # extend to next cue start if close (avoid flashing)
            if i + per_cue < len(lines):
                nxt = lines[i + per_cue][0]["start"]
                t1 = min(max(t1, nxt - 0.05), nxt)
            body_lines = [_accented(ln, cfg.get("accent_colors", True), anim) for ln in cue_lines]
            text = "\\N".join(body_lines)
            fx = _anim_tags(anim, t0, t1, cfg)
            events.append(f"Dialogue: 0,{fmt_ts(t0, comma=True)},{fmt_ts(t1, comma=True)},Noir,,0,0,0,,{fx}{text}")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header + "\n" + "\n".join(events) + "\n")
    return {"path": out_path, "events": len(events), "mode": mode}


def _anim_tags(anim, t0, t1, cfg):
    if anim == "fade":
        return "{\\fad(140,120)}"
    if anim == "pop":
        return "{\\fad(90,90)\\fscx72\\fscy72\\t(0,140,\\fscx104\\fscy104)\\t(140,240,\\fscx100\\fscy100)}"
    if anim == "typewriter":
        return "{\\k30}"      # per-line quick reveal approximation; per-word k added in _accented when anim==typewriter
    if anim == "slide":
        return "{\\fad(120,110)\\move(%d,%d,%d,%d,0,180)}" % (_cx(cfg), _cy(cfg) + 26, _cx(cfg), _cy(cfg))
    return "{\\fad(130,120)}"


def _cx(cfg):
    return int(cfg.get("custom_x", 0.5) * 1920)


def _cy(cfg):
    return int(cfg.get("custom_y", 0.82) * 1080)


def _alignment(cfg):
    pos = cfg.get("position", "bottom")
    return {"top": 8, "center": 5, "bottom": 2}.get(pos, 2)


def _margins(cfg):
    pos = cfg.get("position", "bottom")
    if pos == "custom":
        # approximate via margins from custom_y
        y = cfg.get("custom_y", 0.82)
        if y < 0.25:
            return 40, int(y * 1080), 40
        if y > 0.75:
            return 40, 40, int((1 - y) * 1080)
        return 40, 40, 40
    return {"top": (40, 70, 40), "center": (40, 40, 40), "bottom": (40, 40, 96)}[pos]


def _style_header(cfg):
    L, R, V = _margins(cfg)
    alpha = int((1 - float(cfg.get("background_opacity", 0.35))) * 255)
    outline = 2 if cfg.get("stroke", True) else 0
    shadow = 1 if cfg.get("shadow", True) else 0
    border_style = 4 if cfg.get("background", False) else 1
    spacing = float(cfg.get("letter_spacing", 0))
    bold = -1 if cfg.get("bold", True) else 0
    italic = -1 if cfg.get("italic") else 0
    underline = -1 if cfg.get("underline") else 0
    font = cfg.get("font", "DejaVu Sans")
    size = int(cfg.get("size", 54))
    line_spacing = float(cfg.get("line_spacing", 1.15))
    return f"""[Script Info]
; HUMAN SYSTEMS NOIR — subtitle engine
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Noir,{font},{size},{_ass_color(PAL['bone'])},{_ass_color(PAL['signal_blue'])},{_ass_color(PAL['obsidian'], 40)},{_ass_color(PAL['obsidian'], alpha)},{bold},{italic},{underline},0,100,100,{spacing},0,{border_style},{outline},{shadow},{_alignment(cfg)},{L},{R},{V},1
Style: Kicker,{font},{int(size * 0.55)},{_ass_color(PAL['muted_amber'])},{_ass_color(PAL['signal_blue'])},{_ass_color(PAL['obsidian'], 40)},{_ass_color(PAL['obsidian'], alpha)},-1,0,0,0,100,100,{spacing + 2},0,{border_style},{outline},0,{_alignment(cfg)},{L},{R},{V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""
