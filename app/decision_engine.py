"""Automatic Decision Engine.

For every segment it: (1) reads the semantic role, (2) extracts concepts,
(3) searches EXISTING library assets, (4) ranks them with weighted scoring,
(5) selects the best or applies the documented fallback chain, (6) decides
cut vs hold (no-cut intelligence), (7) chooses a narratively-justified
transition, (8) plans subtitle treatment, (9) detects motion-graphic
opportunities, (10) assigns music mood + justified SFX, (11) records
evidence status and human-review flags.

It never invents visuals: missing assets degrade through the fallback chain
(other asset → symbolic texture → typography card → hold → human review).
"""
import random
from . import lexicon, asset_library
from . import settings as cfgmod

TYPOGRAPHY_FALLBACK_ID = "__typography__"
TEXTURE_FALLBACK_ID = "__texture__"
HOLD_FALLBACK_ID = "__hold__"

FALLBACK_CHAIN = [HOLD_FALLBACK_ID, TEXTURE_FALLBACK_ID, TYPOGRAPHY_FALLBACK_ID]

ROLE_EMOTION = {
    "HOOK_SIGNAL": "intrigued", "PROBLEM": "tense", "PROMISE": "steady",
    "DEFINITION": "neutral", "SOURCE": "neutral", "EXAMPLE": "observant",
    "MECHANISM": "analytical", "COUNTEREXAMPLE": "uncertain",
    "EMOTIONAL_RECOGNITION": "warm", "PRACTICAL_MOVE": "empowered",
    "LIMITATION": "uncertain", "RECAP": "settled", "NEXT_WATCH": "resolved",
}


def visual_intent(seg) -> dict:
    concepts = seg.get("concepts") or []
    role = seg["role"]
    treat = lexicon.ROLE_TREATMENT.get(role, {})
    motif = None
    for c in concepts:
        if c in lexicon.CONCEPT_MOTIF:
            motif = lexicon.CONCEPT_MOTIF[c]
            break
    if not motif and treat.get("motifs"):
        motif = treat["motifs"][0]
    return {"motif": motif, "concepts": concepts[:6], "tint": treat.get("tint", "bone")}


def _state_change(prev, seg) -> int:
    if prev is None:
        return 0
    if (seg.get("chapter") or "") != (prev.get("chapter") or ""):
        return 3
    if prev["role"] != seg["role"]:
        return 2
    a, b = set(prev.get("concepts") or []), set(seg.get("concepts") or [])
    if not b:
        return 1
    overlap = len(a & b) / max(1, len(b))
    if overlap < 0.25:
        return 2
    return 1


def _pick_transition(prev, seg, rng, evidence=False) -> dict:
    weights = dict(cfgmod.get("transitions.weights", {}))
    level = _state_change(prev, seg)
    allowed = {
        0: ["hard_cut"],
        1: ["hard_cut", "fade"],
        2: ["hard_cut", "fade", "zoom", "slide", "blur", "evidence_pivot"],
        3: ["fade", "zoom", "slide", "blur", "flash", "light_leak", "glitch", "evidence_pivot", "dissolve"],
    }[min(level, 3)]
    if evidence and "evidence_pivot" in weights:
        weights["evidence_pivot"] = weights.get("evidence_pivot", 8) * 2.5  # source changes justify the pivot
    pool = {k: weights.get(k, 0) for k in allowed if weights.get(k, 0) > 0}
    if not pool:
        pool = {"hard_cut": 1}
    total = sum(pool.values())
    r = rng.uniform(0, total)
    acc = 0.0
    for k, w in pool.items():
        acc += w
        if r <= acc:
            dur = 0.0 if k == "hard_cut" else round(min(rng.uniform(0.25, cfgmod.get("transitions.max_duration", .6)), 0.6), 2)
            return {"type": k, "duration": dur, "state_change": level}
    return {"type": "hard_cut", "duration": 0.0, "state_change": level}


def _select_asset(seg, position, usage, last_used, exclude, target_ar, rng):
    beat = max(1.2, seg["end"] - seg["start"])
    kinds = ["image", "video"]
    role = seg["role"]
    concepts = seg.get("concepts") or []
    cands = asset_library.candidates(concepts, role, beat, target_ar, usage, last_used, position,
                                     kinds=kinds, exclude=exclude)
    threshold = 0.30
    if cands and cands[0][0] >= threshold:
        score, br, asset = cands[0]
        # small seeded jitter among near-ties keeps edits varied but explainable
        tied = [c for c in cands[:6] if c[0] > score - 0.06]
        if len(tied) > 1:
            score, br, asset = rng.choice(tied)
        return asset, score, br, None
    # ---- fallback chain (documented, never silently pretends success)
    # 1) symbolic texture
    textures = [a for a in asset_library.all_assets() if a["category"] in ("textures",) and a.get("enabled", True)]
    if textures:
        asset = rng.choice(textures)
        return asset, 0.18, {"semantic": 0, "scene": 0, "format": 0.5, "duration": 1, "diversity": 1, "quality": asset.get("quality", .7)}, "texture_fallback"
    # 2) typography (handled by renderer as designed text card)
    return None, 0.0, {}, "typography_fallback"


def plan_motion_graphics(seg, last_mg_end, mg_count, rng):
    if not cfgmod.get("motion_graphics.enabled", True):
        return None
    gap = cfgmod.get("motion_graphics.min_gap_seconds", 8.0)
    maxn = cfgmod.get("motion_graphics.max_per_video", 14)
    if mg_count >= maxn or (last_mg_end and seg["start"] - last_mg_end < gap):
        return None
    treat = lexicon.ROLE_TREATMENT.get(seg["role"], {})
    cands = []
    # explicit phrase triggers
    for c in seg.get("mg_candidates") or []:
        cands.append((c["weight"], c))
    # role-driven graphics
    gc = treat.get("graphic_chance", 0)
    if seg["role"] == "SOURCE" and (seg.get("evidence", {}).get("has_source") or seg.get("evidence", {}).get("meta")):
        cands.append((6.0, {"template": "evidence_card", "params": {}}))
    elif gc and rng.random() < gc:
        motif = (seg.get("visual_intent") or {}).get("motif")
        template = {"list_intro": "list_intro", "definition_card": "definition_card",
                    "counterexample_card": "counterexample_card", "playbook_rail": "playbook_rail",
                    "uncertainty_card": "uncertainty_card", "title_card": "title_card",
                    "quote_card": "quote_card", "list_summary": "list_summary",
                    "mechanism_map": "mechanism_map", "timeline": "timeline"}.get(motif)
        if template:
            cands.append((2.0, {"template": template, "params": {}}))
    if not cands:
        return None
    cands.sort(key=lambda x: -x[0])
    chosen = cands[0][1]
    return {"template": chosen["template"], "params": chosen.get("params", {}),
            "trigger": chosen.get("match"), "start": seg["start"], "end": seg["end"]}


def _sfx_for(seg, rng, last_sfx_pos, position):
    if not cfgmod.get("sfx.enabled", True):
        return None
    gap = cfgmod.get("sfx.min_gap_seconds", 6.0)
    if last_sfx_pos is not None and seg["start"] - last_sfx_pos < gap:
        return None
    names = []
    for c in (seg.get("concepts") or [])[:3]:
        names += lexicon.SFX_MAP.get(c, [])
    names += lexicon.SFX_MAP.get(seg["role"], [])
    if not names:
        return None
    name = names[0]
    pool = [a for a in asset_library.all_assets(kind="sfx") if name in (a.get("tags") or []) or name in a["filename"].lower()]
    if not pool:
        pool = [a for a in asset_library.all_assets(kind="sfx") if any(n in (a.get("tags") or []) for n in names)]
    if not pool:
        return None
    return {"asset_id": rng.choice(pool[:3])["asset_id"], "at": round(seg["start"], 2), "volume": cfgmod.get("sfx.volume", .5)}


def _music_mood(seg, arc_frac):
    role = seg["role"]
    if arc_frac < 0.08:
        return "hook"
    if role in ("PRACTICAL_MOVE", "PROMISE"):
        return "open"
    if role in ("COUNTEREXAMPLE", "LIMITATION"):
        return "sparse"
    if role in ("EMOTIONAL_RECOGNITION",):
        return "near_silence"
    if role in ("RECAP", "NEXT_WATCH"):
        return "resolve"
    return "bed"


def build_timeline(segments: list, project_id: str, seed: int = 7, options: dict | None = None) -> dict:
    """Returns {'segments': [...], 'scenes': [...], 'music': {...}, 'review_flags': n}"""
    options = options or {}
    rng = random.Random(seed)
    res = cfgmod.get("render.resolution", "1920x1080").split("x")
    target_ar = int(res[0]) / int(res[1])
    usage, last_used = {}, {}
    exclude = set()
    timeline, scenes = [], []
    last_mg_end, mg_count, last_sfx_pos = None, 0, None
    prev = None
    review_flags = 0
    narration = options.get("narration", {})
    placeholder = narration.get("placeholder")

    for i, seg in enumerate(segments):
        seg = dict(seg)
        position = i
        asset, score, br, fallback_mode = _select_asset(seg, position, usage, last_used, exclude, target_ar, rng)
        hold = False
        if prev and asset and prev.get("asset_id") == asset["asset_id"]:
            # NO-CUT INTELLIGENCE: same visual stays relevant & meaning unchanged
            if _state_change(prev, seg) <= 1 and rng.random() < 0.8:
                hold = True
                fallback_mode = prev.get("fallback")
        if asset is None:
            hold = prev is not None and _state_change(prev, seg) <= 1
            fallback = TYPOGRAPHY_FALLBACK_ID
        else:
            fallback = fallback_mode or None

        intent = visual_intent(seg)
        transition = {"type": "fade_from_black", "duration": 0.9, "state_change": 0} if i == 0 else \
            ({"type": "hold", "duration": 0} if hold else _pick_transition(prev, seg, rng,
                                                                           evidence=seg.get("evidence", {}).get("has_source")))
        entry = {
            "segment_id": seg["segment_id"],
            "start": seg["start"], "end": seg["end"], "duration": round(seg["end"] - seg["start"], 3),
            "voiceover_summary": (seg["text"][:140] + ("…" if len(seg["text"]) > 140 else "")),
            "text": seg["text"],
            "role": seg["role"],
            "emotion": ROLE_EMOTION.get(seg["role"], "neutral"),
            "concepts": seg["concepts"],
            "visual_intent": intent,
            "asset_id": asset["asset_id"] if asset else None,
            "asset_name": asset["filename"] if asset else None,
            "asset_type": asset["type"] if asset else None,
            "fallback": fallback,
            "text_overlay": None,
            "text_style": None,
            "motion": _motion_for(asset, seg, rng),
            "transition": transition,
            "music": {"mood": _music_mood(seg, seg.get("arc_position", 0)), "duck": True},
            "sfx": _sfx_for(seg, rng, last_sfx_pos, position),
            "evidence_status": seg.get("evidence", {}),
            "confidence": round(min(0.98, (0.45 + 0.5 * score) * (0.6 + 0.4 * seg.get("role_confidence", .5))), 2),
            "human_review_reason": None,
            "locked": False,
            "chapter": seg.get("chapter"),
            "words": seg.get("words", []),
            "timing_mode": seg.get("timing_mode", "estimated"),
        }
        # ---- human review flags (never pretend a missing asset was found)
        reasons = []
        if fallback == TYPOGRAPHY_FALLBACK_ID:
            reasons.append("no matching library asset — typography card used")
        elif fallback == "texture_fallback":
            reasons.append("weak asset match — symbolic texture used")
        if seg.get("role_confidence", 0) < 0.42:
            reasons.append("low role classification confidence")
        if placeholder:
            reasons.append("narration is a timing placeholder (offline demo) — add real TTS audio")
        if seg.get("timing_mode") != "word_timestamps" and options.get("flag_estimated_timing", True):
            reasons.append("word timings are estimated")
        if reasons:
            entry["human_review_reason"] = "; ".join(reasons)
            review_flags += 1
        if entry["sfx"]:
            last_sfx_pos = seg["start"]

        mg = plan_motion_graphics(seg, last_mg_end, mg_count, rng)
        if mg:
            mg["id"] = f"mg_{i:03d}"
            mg["segment_id"] = seg["segment_id"]
            entry["motion_graphic"] = mg
            last_mg_end = seg["end"]
            mg_count += 1
        else:
            entry["motion_graphic"] = None

        timeline.append(entry)
        if asset:
            usage[asset["asset_id"]] = usage.get(asset["asset_id"], 0) + 1
            last_used[asset["asset_id"]] = i
        prev = {**entry, "concepts": seg["concepts"]}

    return {"segments": timeline, "review_flags": review_flags,
            "target_ar": target_ar, "seed": seed}


def _motion_for(asset, seg, rng) -> dict:
    """Subtle Ken Burns: 3–8% movement over 4–12s. Not every sentence zooms."""
    if not asset:
        return {"type": "static", "amount": 0.0}
    dur = max(1.0, seg["end"] - seg["start"])
    treat = lexicon.ROLE_TREATMENT.get(seg["role"], {})
    if rng.random() > 0.82:
        return {"type": "static", "amount": 0.0}
    amount = round(rng.uniform(0.03, 0.08), 3)
    kind = rng.choice(["zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down", "kenburns"])
    if seg["role"] in ("PRACTICAL_MOVE", "DEFINITION"):
        kind = rng.choice(["zoom_in", "kenburns"])
    speed = max(0.25, min(1.0, dur / 8.0))
    return {"type": kind, "amount": amount, "speed": round(speed, 2), "duration": min(12.0, max(4.0, dur))}


def regenerate_segment(timeline: list, segment_id: str, seed_shift: int = 991):
    """Re-run asset selection for one segment (REGENERATE SCENE)."""
    import time as _time
    rng = random.Random(int(_time.time() * 1000) % 99991 + seed_shift)
    idx = next((i for i, e in enumerate(timeline) if e["segment_id"] == segment_id), None)
    if idx is None:
        raise KeyError(segment_id)
    seg = timeline[idx]
    prev = timeline[idx - 1] if idx > 0 else None
    if seg.get("locked"):
        return seg
    res = cfgmod.get("render.resolution", "1920x1080").split("x")
    target_ar = int(res[0]) / int(res[1])
    usage, last_used = {}, {}
    for j, e in enumerate(timeline):
        if e.get("asset_id"):
            usage[e["asset_id"]] = usage.get(e["asset_id"], 0) + 1
            last_used[e["asset_id"]] = j
    exclude = {prev["asset_id"]} if prev and prev.get("asset_id") else set()
    fake_seg = {"role": seg["role"], "concepts": seg["concepts"], "start": seg["start"], "end": seg["end"]}
    asset, score, br, fallback = _select_asset(fake_seg, idx, usage, last_used, exclude, target_ar, rng)
    if asset:
        seg["asset_id"] = asset["asset_id"]
        seg["asset_name"] = asset["filename"]
        seg["asset_type"] = asset["type"]
        seg["fallback"] = fallback
        seg["motion"] = _motion_for(asset, seg, rng)
        seg["confidence"] = round(min(0.98, 0.45 + 0.5 * score), 2)
    if prev:
        seg["transition"] = _pick_transition(prev, seg, rng, evidence=seg.get("evidence_status", {}).get("has_source"))
    return seg
