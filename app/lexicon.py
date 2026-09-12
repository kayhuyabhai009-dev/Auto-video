"""Semantic lexicon for HUMAN SYSTEMS NOIR.

This is the knowledge base that lets every visual decision carry a semantic
reason: concept extraction, script-role classification, evidence detection,
subtitle accent colorization, motion-graphic triggers and SFX justification.
Prefer OBSERVABLE objects/actions (phone, document, door, hands, clock) over
inferring intent from faces.
"""

# ---------------------------------------------------------------- concepts
# concept_key -> trigger phrases (lowercase, word-boundary matched).
# concept keys double as asset semantic_tags so the matcher links them.
CONCEPT_LEXICON = {
    # objects / observable cues
    "phone": ["phone", "smartphone", "cellphone", "text message", "texted", "texting",
              "notification", "notifications", "screen", "mobile", "call", "caller", "voicemail"],
    "message": ["message", "messages", "messaging", "chat", "reply", "replied", "dm", "inbox"],
    "document": ["document", "documents", "contract", "paperwork", "agreement", "written",
                 "in writing", "letter", "email", "file", "report", "terms"],
    "signature": ["signed", "signature", "sign", "initial here"],
    "clock": ["clock", "time", "deadline", "hours", "minutes", "late", "delay", "schedule",
              "countdown", "eventually", "suddenly", "slowly", "urgency"],
    "door": ["door", "doorway", "entrance", "exit", "closed door", "open door", "threshold"],
    "hands": ["hands", "hand", "fingers", "gesture", "grip", "hold", "held"],
    "desk": ["desk", "table", "workspace", "office", "study", "papers on"],
    "computer": ["computer", "laptop", "screen", "browser", "online", "internet", "app", "profile", "account"],
    "money": ["money", "payment", "paid", "invoice", "fee", "charge", "price", "cost", "debt",
              "salary", "budget", "financial", "bill"],
    "ledger": ["ledger", "favor", "favors", "owed", "owe", "obligation", "obligations",
              "tally", "record of", "kept track", "scorekeeping", "commitments"],
    "notebook": ["notebook", "notes", "journal", "wrote down", "diary", "annotation", "annotations"],
    "book": ["book", "books", "reading", "read", "literature", "textbook", "publication"],
    "coffee": ["coffee", "cup", "mug", "tea"],
    "cigarette": ["cigarette", "smoke", "smoking"],
    "city": ["city", "street", "streets", "crowd", "crowded", "urban", "subway", "traffic", "commute"],
    "rain": ["rain", "raining", "storm", "wet", "drizzle", "downpour"],
    "night": ["night", "midnight", "dark", "darkness", "evening", "late night", "small hours"],
    "window": ["window", "windows", "glass", "reflection"],
    "mirror": ["mirror", "reflection", "reflected"],
    "chair": ["chair", "seat", "sitting", "sat"],
    "elevator": ["elevator", "lift"],
    "keys": ["keys", "key", "lock", "locked", "unlock"],

    # psychological / abstract concepts mapped to symbolic motifs
    "boundary": ["boundary", "boundaries", "limit", "limits", "say no", "refuse", "decline",
                 "consent", "permission", "private", "privacy", "personal space", "line"],
    "pressure": ["pressure", "pressured", "pushed", "guilt", "guilty", "shame", "obligated",
                 "duty", "expected to", "should", "must", "demands", "demanding"],
    "manipulation": ["manipulation", "manipulate", "manipulative", "coerce", "coercion",
                     "gaslight", "gaslighting", "exploit", "exploitation", "control"],
    "moving_goalposts": ["moving the goalposts", "changes the rules", "changed the rules",
                         "shifting standards", "new conditions", "renegotiate", "moves the goalposts",
                         "rules after you agree", "moving goalposts", "changed the terms"],
    "triangulation": ["triangulation", "third party", "someone else said", "compare you",
                      "compares you", "other people think"],
    "reciprocity": ["reciprocity", "return the favor", "owe them", "paid back", "favors create"],
    "scarcity": ["scarcity", "limited time", "act now", "running out", "last chance", "urgent"],
    "authority": ["authority", "boss", "manager", "expert", "official", "credentials",
                  "position of power", "senior", "in charge"],
    "loneliness": ["loneliness", "lonely", "isolated", "isolation", "alone", "no one", "nobody"],
    "attention": ["attention", "focus", "distraction", "distracted", "notice", "noticed",
                  "spotlight", "watching"],
    "stress": ["stress", "stressed", "anxiety", "anxious", "overwhelm", "overwhelmed",
               "burnout", "exhausted", "tension", "tense"],
    "trust": ["trust", "trusted", "trustworthy", "reliability", "reliable", "consistent"],
    "conversation": ["conversation", "talk", "talking", "spoke", "discussion", "dialogue",
                     "said", "says", "tells", "told"],
    "observation": ["observed", "observation", "you see", "you notice", "watch", "watches",
                    "visible", "shows up as", "looks like"],
    "interpretation": ["interpretation", "interpret", "might mean", "could mean", "assume",
                       "assumption", "meaning", "implies", "suggests"],
    "confusion": ["confusion", "confused", "unclear", "vague", "ambiguous", "misunderstood"],
    "empathy": ["empathy", "compassion", "kindness", "care", "caring", "warmth"],
    "fatigue": ["tired", "fatigue", "sleep", "sleepy", "rest", "exhaustion", "worn out"],
    "culture": ["culture", "cultural", "background", "upbringing", "different norms", "tradition"],
    "decision": ["decision", "decide", "choice", "choose", "options", "trade-off", "tradeoff"],
    "habit": ["habit", "habits", "routine", "automatic", "pattern", "patterns"],
    "memory": ["memory", "remember", "recall", "forget", "forgot", "past"],
    "identity": ["identity", "self-image", "who you are", "sense of self"],
    "social": ["social", "group", "friends", "family", "colleagues", "team", "people around",
               "others", "community"],
    "work": ["work", "job", "workplace", "coworker", "employee", "employer", "career", "shift"],
    "online": ["online", "internet", "social media", "feed", "platform", "algorithm", "digital",
               "profile", "post", "posts"],
    "evidence": ["evidence", "research", "study", "studies", "data", "measured", "experiment",
                 "experiment", "meta-analysis", "findings", "researchers", "participants"],
    "agreement": ["agree", "agreed", "agreement", "deal", "promise", "promised", "commitment"],
    "exit": ["walk away", "leave", "leaving", "end the conversation", "step back", "disengage",
             "exit", "step out"],
    "verification": ["verify", "verification", "check", "checked", "confirm", "ask for",
                     "clarify", "question", "questions"],
    "regulation": ["regulate", "breathe", "breathing", "pause", "calm", "settle", "ground yourself"],
    "repair": ["repair", "apologize", "apology", "make it right", "restore", "rebuild"],
}

# map each concept to the motif language of the channel (used for stylized
# graphics when no photographic asset exists)
CONCEPT_MOTIF = {
    "moving_goalposts": "timeline", "agreement": "document", "boundary": "boundary_line",
    "pressure": "red_thread", "manipulation": "red_thread", "triangulation": "red_thread",
    "reciprocity": "ledger", "attention": "waveform", "evidence": "evidence_card",
    "verification": "evidence_card", "exit": "door", "door": "door", "keys": "door",
    "clock": "clock", "document": "document", "message": "waveform", "phone": "waveform",
    "money": "ledger", "ledger": "ledger", "loneliness": "negative_space",
    "interpretation": "uncertainty", "confusion": "uncertainty", "culture": "uncertainty",
    "fatigue": "uncertainty", "regulation": "boundary_line", "repair": "timeline",
    "decision": "decision_tree", "verification": "evidence_card", "habit": "timeline",
    "memory": "timeline", "identity": "mirror", "mirror": "mirror",
}

# ---------------------------------------------------------------- roles
# role -> list of (regex, weight). Classification scores every role and picks
# the best; structural position provides a prior.
ROLE_CUES = {
    "HOOK_SIGNAL": [
        (r"\b(imagine|picture this|consider this|here'?s the (thing|problem)|what if i told you|"
         r"why (do|does)|have you ever|there'?s a (moment|pattern)|pay attention)\b", 3),
        (r"\?.*", 1),
        (r"\b(you know the feeling|it starts small|it begins with)\b", 2),
    ],
    "PROBLEM": [
        (r"\b(problem|trouble|difficult|confusing|drains|exhausting|keeps happening|"
         r"why .*(hard|difficult)|what'?s really going on|the issue)\b", 3),
        (r"\b(frustrating|unfair|stuck|repeats|cycle)\b", 2),
    ],
    "PROMISE": [
        (r"\b(in this video|today (we|you)|by the end|you'?ll (learn|know|understand)|"
         r"we'?ll (cover|break down|look at)|let'?s break)\b", 3),
        (r"\b(this video|today'?s video)\b", 3.5),
        (r"\b(what you can do|how to (spot|handle|respond)|three (facts|reasons|things)|"
         r"\b(five|four|two|three)\b.*\b(facts|reasons|signs|things|patterns))\b", 2),
    ],
    "DEFINITION": [
        (r"\b(defined as|definition|is when|refers to|means that|by .*(we mean)|"
         r"is called|the term)\b", 3),
        (r"\b(psychologists call|known as|describes)\b", 2),
    ],
    "SOURCE": [
        (r"\b(study|studies|research|researchers|published|journal|university|"
         r"according to|data|meta-?analysis|survey|experiment|dr\.\s?\w+|professor)\b", 3),
        (r"\b(\d{4})\b", 1),
        (r"\b(participants|sample|respondents|findings)\b", 2),
    ],
    "EXAMPLE": [
        (r"\b(for example|for instance|imagine a|picture a|say (you|a)|consider a|"
         r"take a|here'?s (a|an)|a (friend|coworker|manager|colleague))\b", 3),
        (r"\b(one evening|last week|one day|at work|in a meeting)\b", 2),
    ],
    "MECHANISM": [
        (r"\b(because|the reason|this works because|what happens|the mechanism|"
         r"this creates|leads to|results in|the effect|triggers|sets off|so the)\b", 3),
        (r"\b(step by step|first .*(then|next)|each time|the more .*(the more))\b", 2),
    ],
    "COUNTEREXAMPLE": [
        (r"\b(but|however|on the other hand|alternative|another explanation|doesn'?t mean|"
         r"not always|could (just|simply) be|equally|or maybe|before you assume|"
         r"it might simply|just as likely)\b", 3),
        (r"\b(also|sometimes|in some cases|may be|might be)\b", 1),
    ],
    "EMOTIONAL_RECOGNITION": [
        (r"\b(if you'?ve (felt|ever)|you'?re not (alone|crazy|imagining)|it'?s not (just|only) you|"
         r"this is exhausting|you deserve|be kind to yourself|many people feel|"
         r"it makes sense (that|if))\b", 3),
        (r"\b(feel|feels|feeling|felt)\b", 1),
    ],
    "PRACTICAL_MOVE": [
        (r"\b(try this|what to do|you can|here'?s what you (can|do)|practical|"
         r"one (move|step)|ask for|state |say: |next time|instead, )\b", 3),
        (r"\b(notice|regulate|verify|boundary|build|respond|script|practice)\b", 2),
        (r"\b(don'?t answer|pause before|write it down|ask them to)\b", 2),
    ],
    "LIMITATION": [
        (r"\b(limitation|limit|caveat|doesn'?t prove|only shows|correlation|"
         r"small sample|one study|not (a diagnosis|conclusive)|exceptions?)\b", 3),
        (r"\b(cannot|can'?t) (say|prove|know)\b", 2),
    ],
    "RECAP": [
        (r"\b(to recap|in short|so remember|the key (point|idea)|to sum( up|marize)?|"
         r"quick recap|the takeaway)\b", 3),
        (r"\b(three things to remember|what matters most)\b", 2),
    ],
    "NEXT_WATCH": [
        (r"\b(next video|next time|in the next|watch next|subscribe|part two|"
         r"up next|until then)\b", 3),
    ],
}

# noir master grammar — structural prior by ordinal position of segment
GRAMMAR_ARC = ["HOOK_SIGNAL", "PROBLEM", "PROMISE", "DEFINITION", "MECHANISM",
               "EXAMPLE", "COUNTEREXAMPLE", "PRACTICAL_MOVE", "EMOTIONAL_RECOGNITION",
               "RECAP", "NEXT_WATCH"]

# role -> default visual motif priority (checked with concepts)
ROLE_TREATMENT = {
    "HOOK_SIGNAL": {"motifs": ["waveform", "negative_space"], "scene": ["city", "night", "phone"],
                    "graphic_chance": 0.25, "tint": "red"},
    "PROBLEM": {"motifs": ["red_thread", "timeline"], "scene": ["office", "phone", "desk"],
                "graphic_chance": 0.2, "tint": "red"},
    "PROMISE": {"motifs": ["list_intro"], "scene": ["desk", "notebook"], "graphic_chance": 0.9,
                "tint": "blue"},
    "DEFINITION": {"motifs": ["definition_card", "mechanism_map"], "scene": ["book", "notebook"],
                   "graphic_chance": 0.75, "tint": "bone"},
    "SOURCE": {"motifs": ["evidence_card", "source_desk"], "scene": ["book", "document", "desk"],
               "graphic_chance": 0.85, "tint": "amber"},
    "EXAMPLE": {"motifs": [], "scene": ["phone", "conversation", "office", "message"],
                "graphic_chance": 0.1, "tint": "bone"},
    "MECHANISM": {"motifs": ["mechanism_map", "waveform", "ledger"], "scene": ["clock", "document", "computer"],
                  "graphic_chance": 0.55, "tint": "bone"},
    "COUNTEREXAMPLE": {"motifs": ["counterexample_card", "uncertainty"], "scene": ["window", "rain", "night"],
                       "graphic_chance": 0.85, "tint": "gray"},
    "EMOTIONAL_RECOGNITION": {"motifs": ["quote_card"], "scene": ["window", "rain", "loneliness", "night"],
                              "graphic_chance": 0.2, "tint": "bone"},
    "PRACTICAL_MOVE": {"motifs": ["playbook_rail", "number_card"], "scene": ["notebook", "door", "hands"],
                       "graphic_chance": 0.75, "tint": "blue"},
    "LIMITATION": {"motifs": ["uncertainty_card"], "scene": ["window", "fog", "night"],
                   "graphic_chance": 0.6, "tint": "gray"},
    "RECAP": {"motifs": ["list_summary", "timeline"], "scene": ["desk", "notebook", "city"],
              "graphic_chance": 0.5, "tint": "blue"},
    "NEXT_WATCH": {"motifs": ["title_card"], "scene": ["city", "night", "door"],
                   "graphic_chance": 0.7, "tint": "bone"},
}

# ---------------------------------------------------------------- evidence
EVIDENCE_CUES = [
    r"\b(a \d{4} study|the \d{4} study|in \d{4},? (researchers|a study))\b",
    r"\baccording to\b", r"\bpublished in\b", r"\b(a|the) (study|survey|meta-?analysis|experiment) (found|showed|suggests)",
    r"\bresearchers (at|from)\b", r"\bthe findings?\b", r"\bdata (from|shows)\b",
]
EVIDENCE_LIMIT_CUES = [
    r"doesn'?t (prove|mean|tell)", r"only (shows|measures)", r"correlation", r"small sample",
    r"can'?t (say|prove)", r"doesn'?t (capture|explain)", r"one study", r"not conclusive",
    r"in (rats|mice|students|one country)", r"limited to",
]

# ---------------------------------------------------------------- subtitle accents
# semantic color classes for selective accenting of single words
ACCENT_WORDS = {
    "red": [
        "pressure", "pressured", "guilt", "guilty", "obligation", "obligated", "shame",
        "demands", "demand", "demanded", "manipulation", "manipulate", "manipulative",
        "coerce", "coercion", "gaslighting", "gaslight", "exploit", "exploiting", "control",
        "controls", "controlled", "guilt-trip", "owe", "owes", "owed", "debt", "urgency",
        "urgent", "threat", "conflict", "tension", "rules", "changed", "moves", "renegotiate",
        "must", "expected", "demands.",
    ],
    "blue": [
        "boundary", "boundaries", "consent", "verify", "verified", "verification", "ask",
        "asking", "clarify", "state", "respond", "response", "pause", "breathe", "choose",
        "choice", "decide", "option", "options", "say", "no", "limit", "limits", "exit",
        "leave", "practice", "notice", "regulate", "build", "write", "agreed", "agreement",
        "step", "move", "action", "agency", "safety", "safe",
    ],
    "amber": [
        "study", "studies", "research", "researchers", "evidence", "data", "published",
        "journal", "survey", "meta-analysis", "source", "according", "history", "origin",
        "originally", "experiment", "findings", "participants", "professor", "doctor",
    ],
    "gray": [
        "might", "may", "could", "possibly", "perhaps", "maybe", "sometimes", "unclear",
        "uncertain", "alternatively", "alternative", "ambiguous", "likely", "unlikely",
        "tired", "distraction", "distracted", "anxious", "assumption", "assume", "assuming",
        "interpretation", "not", "cannot", "doesn't", "unknown", "correlation", "limitations",
        "limitation", "caveat", "however", "but", "unless",
    ],
}

# words that mark emphasis (used for highlight/underline animation targets)
EMPHASIS_WORDS = [
    "never", "always", "everything", "nothing", "only", "exactly", "key", "most",
    "biggest", "first", "second", "third", "important", "remember", "truth", "real",
]

# ---------------------------------------------------------------- motion graphic triggers
# (regex, template, weight, param extractor key)
MG_TRIGGERS = [
    (r"\b(three|3|four|4|five|5|two|2)\b[^.!?]{0,30}\b(facts|reasons|signs|things|ways|rules|steps|truths|patterns|lessons)\b",
     "list_intro", 5, "count"),
    (r"\b(number (one|1)|first(ly)?|fact (number )?(one|1))\b", "number_card", 4, "one"),
    (r"\b(number (two|2)|second(ly)?|fact (number )?(two|2))\b", "number_card", 4, "two"),
    (r"\b(number (three|3)|third(ly)?|fact (number )?(three|3))\b", "number_card", 4, "three"),
    (r"\b(warning|be careful|careful|red flag|red flags|danger)\b", "warning_card", 4, None),
    (r"\b(did you know|here'?s the (scary )?part|the biggest (reason|problem|mistake))\b",
     "fact_card", 3, None),
    (r"\b(the solution|so what (do|can) you do|here'?s what (helps|works)|the fix)\b",
     "solution_card", 4, None),
    (r"\b(in short|to recap|the takeaway|remember (this|these))\b", "list_summary", 3, None),
    (r"\b(psychology|psychological)\b[^.!?]{0,40}\b(facts|principles|effects)\b", "list_intro", 5, "count"),
    (r"\b(study|research|according to|published|journal)\b", "evidence_card", 3, None),
    (r"\b(because|the mechanism|this is why|what actually happens)\b", "mechanism_map", 2, None),
    (r"\b(step (one|1|two|2|three|3)|next step|the playbook)\b", "playbook_rail", 3, None),
    (r"\b(timeline|over the (years|months)|day one|week one|month one)\b", "timeline", 2, None),
]

NUM_WORD = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
            "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7}

PLAYBOOK_STEPS = [
    ("NOTICE", "What actually changed?"),
    ("REGULATE", "Don't answer immediately."),
    ("VERIFY", "Ask for the original agreement."),
    ("BOUNDARY", "State what you agreed to."),
    ("BUILD", "Continue only if it is respected."),
]

# ---------------------------------------------------------------- sfx semantics
SFX_MAP = {
    "document": ["paper", "page"],
    "message": ["click"],
    "phone": ["click"],
    "computer": ["click"],
    "signature": ["paper"],
    "notebook": ["paper"],
    "book": ["page"],
    "door": ["door"],
    "keys": ["click"],
    "decision": ["click"],
    "verification": ["click"],
    "evidence": ["paper"],
    "SOURCE": ["paper"],
    "PRACTICAL_MOVE": ["click"],
    "HOOK_SIGNAL": ["riser"],
    "RECAP": ["impact_soft"],
    "NEXT_WATCH": ["impact_soft"],
}

# ---------------------------------------------------------------- colors
PALETTE = {
    "obsidian": "#111315",
    "charcoal": "#20252A",
    "bone": "#E8E2D6",
    "oxide_red": "#C94A3D",
    "signal_blue": "#5E8EA5",
    "muted_amber": "#D0A457",
    "uncertainty_gray": "#9BA3A8",
}

ROLE_COLOR = {
    "PRESSURE": "oxide_red", "AGENCY": "signal_blue", "SOURCE": "muted_amber",
    "UNCERTAINTY": "uncertainty_gray", "NEUTRAL": "bone",
}

import re as _re


def _rx(phrase: str):
    """Word-bounded literal phrase pattern (prevents 'fee' matching 'feeling')."""
    return _re.compile(r"(?<![A-Za-z0-9])" + _re.escape(phrase) + r"(?![A-Za-z0-9])", _re.I)


def _compile(entries):
    return [(c, [_rx(p) for p in phrases]) for c, phrases in entries.items()]


_CONCEPT_COMPILED = _compile(CONCEPT_LEXICON)
_ROLE_COMPILED = {r: [(_re.compile(p, _re.I), w) for p, w in cues] for r, cues in ROLE_CUES.items()}
_EVIDENCE_COMPILED = [_re.compile(p, _re.I) for p in EVIDENCE_CUES]
_EVIDENCE_LIMIT_COMPILED = [_re.compile(p, _re.I) for p in EVIDENCE_LIMIT_CUES]
_MG_COMPILED = [( _re.compile(p, _re.I), t, w, k) for p, t, w, k in MG_TRIGGERS]


def extract_concepts(text: str) -> list:
    found = []
    for concept, patterns in _CONCEPT_COMPILED:
        hits = sum(1 for p in patterns if p.search(text))
        if hits:
            found.append((concept, hits))
    found.sort(key=lambda x: (-x[1], x[0]))
    return [c for c, _ in found]


def classify_role(text: str, ordinal: int = None, total: int = None) -> tuple:
    scores = {}
    for role, cues in _ROLE_COMPILED.items():
        s = 0.0
        for pat, w in cues:
            m = pat.search(text)
            if m:
                s += w * (1.25 if m.start() < 80 else 1.0)  # early match = stronger signal
        if s:
            scores[role] = s
    # structural priors
    if ordinal is not None and total:
        frac = ordinal / max(1, total - 1)
        if ordinal == 0 and "HOOK_SIGNAL" not in scores:
            scores["HOOK_SIGNAL"] = scores.get("HOOK_SIGNAL", 0) + 1.5
        if frac > 0.88 and "NEXT_WATCH" not in scores:
            scores["NEXT_WATCH"] = 1.2
        if 0.80 < frac <= 0.92:
            scores["RECAP"] = scores.get("RECAP", 0) + 0.8
    if not scores:
        # grammar arc fallback by position
        if ordinal is not None and total:
            idx = min(len(GRAMMAR_ARC) - 1, int((ordinal / max(1, total)) * len(GRAMMAR_ARC)))
            return GRAMMAR_ARC[idx], 0.35
        return "MECHANISM", 0.35
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    top, second = ranked[0], (ranked[1] if len(ranked) > 1 else (None, 0))
    margin = (top[1] - second[1]) / max(1.0, top[1])
    return top[0], round(min(0.98, 0.45 + margin * 0.5), 2)


def evidence_status(text: str) -> dict:
    has_source = any(p.search(text) for p in _EVIDENCE_COMPILED)
    has_limit = any(p.search(text) for p in _EVIDENCE_LIMIT_COMPILED)
    ym = _re.search(r"\b(19|20)\d{2}\b", text)
    return {"has_source": has_source, "has_limitation": has_limit, "year": ym.group(0) if ym else None}


def detect_motion_graphics(text: str):
    """Return list of (template, weight, params)."""
    out = []
    for pat, template, weight, key in _MG_COMPILED:
        m = pat.search(text)
        if not m:
            continue
        params = {}
        if key == "count":
            nm = _re.search(r"\b(three|3|four|4|five|5|two|2|six|6)\b", m.group(0), _re.I)
            if nm:
                params["count"] = NUM_WORD.get(nm.group(1).lower(), 3)
        elif key in NUM_WORD:
            params["number"] = NUM_WORD[key]
            params["label"] = "FACT" if _re.search(r"fact", text, _re.I) else "POINT"
        out.append({"template": template, "weight": weight, "params": params, "match": m.group(0)})
    return out


_ACCENT_LOOKUP = {}
for color, words in ACCENT_WORDS.items():
    for w in words:
        _ACCENT_LOOKUP[w.lower()] = color


def word_accent(word: str):
    w = word.lower().strip(".,!?;:\"'()")
    return _ACCENT_LOOKUP.get(w)


def is_emphasis(word: str):
    return word.lower().strip(".,!?;:\"'()") in EMPHASIS_WORDS
