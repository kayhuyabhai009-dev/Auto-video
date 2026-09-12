"""Script segmentation.

After narration exists, divide the script into SEMANTIC segments (not blindly
one scene per sentence). Grouping respects: punctuation, paragraph and chapter
boundaries, semantic/role changes, emphasis keywords, and the rhythm ranges
for each role. Timings come from word timestamps when the narration provides
them; otherwise they are distributed estimates and marked timing_mode=estimated.
"""
import re
from . import lexicon
from .util import sentence_split

CHAPTER_RE = re.compile(r"^\s*(?:##|CHAPTER)\s*[:\-]?\s*(.+?)\s*$")
EVIDENCE_TAG_RE = re.compile(r"\[\[\s*SOURCE\s*:\s*(?P<author>[^|\]]+?)?\s*(?:\|\s*(?P<title>[^|\]]*?))?\s*(?:\|\s*(?P<year>[^|\]]*?))?\s*(?:\|\s*(?P<limit>[^\]]*?))?\s*\]\]", re.I)


def parse_script(text: str):
    """Returns list of blocks: {'chapter': str|None, 'text': str, 'sentences': [..]}"""
    blocks, current_chapter = [], None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = CHAPTER_RE.match(line)
        if m:
            current_chapter = m.group(1)
            continue
        blocks.append({"chapter": current_chapter, "line": line})
    return blocks


def _sentence_word_spans(sent, word_iter, words_used):
    """Assign narration word timings to a sentence's words in order."""
    import re as _re
    toks = _re.findall(r"[\w']+", sent)
    spans = []
    for t in toks:
        if words_used < len(word_iter):
            w = word_iter[words_used]
            spans.append({"word": t, "start": w["start"], "end": w["end"], "estimated": w.get("estimated", True)})
            words_used += 1
        else:
            prev_end = spans[-1]["end"] if spans else 0.0
            est_dur = max(0.18, min(0.9, len(t) * 0.075))
            spans.append({"word": t, "start": prev_end + 0.02, "end": prev_end + 0.02 + est_dur, "estimated": True})
            words_used += 1
    return spans, words_used


def _close_sentence_role(text):
    role, conf = lexicon.classify_role(text)
    return role, conf


def segment_script(script_text: str, narration: dict, options: dict | None = None) -> list:
    options = options or {}
    word_ts = narration.get("word_timestamps") or []
    total_dur = narration.get("duration", 0.0)
    timing_mode = "word_timestamps" if narration.get("timing_mode") == "word_timestamps" else "estimated"

    blocks = parse_script(script_text)
    # flatten to sentences with chapter tags
    sentences = []
    for b in blocks:
        for sent in sentence_split(b["line"]):
            etag = EVIDENCE_TAG_RE.search(sent)
            clean = EVIDENCE_TAG_RE.sub("", sent).strip()
            if not clean:
                continue
            sentences.append({"chapter": b["chapter"], "text": clean,
                              "evidence_meta": etag.groupdict() if etag else None})

    if not sentences:
        return []
    words_used = 0
    for s in sentences:
        spans, words_used = _sentence_word_spans(s["text"], word_ts, words_used)
        s["words"] = spans
        s["start"] = spans[0]["start"]
        s["end"] = spans[-1]["end"]

    from . import settings as cfgmod
    rhythm = cfgmod.get("rhythm", {})

    # ---- grouping pass
    segments = []
    cur = None

    def flush():
        nonlocal cur
        if not cur:
            return
        text = " ".join(s["text"] for s in cur["sents"])
        words = [w for s in cur["sents"] for w in s["words"]]
        start = cur["sents"][0]["start"]
        end = cur["sents"][-1]["end"]
        if end - start < 0.4 and segments:
            end = max(end, segments[-1]["end"] + 0.4)
        concepts = lexicon.extract_concepts(text)
        role, conf = lexicon.classify_role(text, ordinal=0, total=1)
        ev = lexicon.evidence_status(text)
        ev_meta = next((s["evidence_meta"] for s in cur["sents"] if s["evidence_meta"]), None)
        segments.append({
            "text": text,
            "start": round(start, 3),
            "end": round(max(end, start + 0.4), 3),
            "words": words,
            "chapter": cur["chapter"],
            "concepts": concepts,
            "role": role,
            "role_confidence": conf,
            "evidence": {**ev, **({"meta": ev_meta} if ev_meta else {})},
            "mg_candidates": lexicon.detect_motion_graphics(text),
        })
        cur = None

    total = len(sentences)
    for i, s in enumerate(sentences):
        if cur is None:
            cur = {"chapter": s["chapter"], "sents": [s], "role": None}
        else:
            same_chapter = (cur["chapter"] == s["chapter"])
            dur_so_far = s["end"] - cur["sents"][0]["start"]
            # provisional role of combined text
            combined = " ".join(x["text"] for x in cur["sents"] + [s])
            new_role, _ = lexicon.classify_role(combined)
            cur_role, _ = lexicon.classify_role(" ".join(x["text"] for x in cur["sents"]))
            rng = rhythm.get(cur_role if cur_role in rhythm else "DEFAULT", [2.5, 6.0])
            max_dur = rng[1] + 1.5
            force_break = False
            if not same_chapter:
                force_break = True
            if new_role != cur_role and dur_so_far > rng[0] * 0.75:
                force_break = True
            if len(cur["sents"]) >= 3:
                force_break = True
            if dur_so_far > max_dur:
                force_break = True
            # very short sentences merge into the current thought
            if s["end"] - s["start"] < 0.9 and not force_break and dur_so_far < max_dur:
                cur["sents"].append(s)
                continue
            if force_break:
                flush()
                cur = {"chapter": s["chapter"], "sents": [s]}
                continue
            cur["sents"].append(s)
    flush()

    # ---- assign roles with global ordinal & refine confidence
    n = len(segments)
    for idx, seg in enumerate(segments):
        role, conf = lexicon.classify_role(seg["text"], ordinal=idx, total=n)
        seg["role"], seg["role_confidence"] = role, conf
        seg["segment_id"] = f"seg_{idx:03d}"
        seg["timing_mode"] = timing_mode
        # emphasis words
        seg["emphasis_words"] = [w["word"] for w in seg["words"] if lexicon.is_emphasis(w["word"])]
        # semantic arc position
        seg["arc_position"] = round((seg["start"] / max(0.001, total_dur)), 3) if total_dur else 0
        seg["duration"] = round(seg["end"] - seg["start"], 3)
    # stretch rounding: make last segment end exactly at narration end
    if total_dur and segments:
        segments[-1]["end"] = max(segments[-1]["end"], round(total_dur, 3))
    return segments
