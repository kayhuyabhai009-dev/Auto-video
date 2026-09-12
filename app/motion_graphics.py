"""Motion graphics system.

Motion graphics are separate visual INFORMATION CARDS (never subtitles):
fact cards, number cards, list intros, evidence cards, mechanism maps,
timelines, playbook rails, counterexample/uncertainty cards, title cards.
Each template renders to a transparent 1920x1080 PNG with Pillow, using the
HUMAN SYSTEMS NOIR palette. The renderer animates them (fade/slide/zoom) as
an overlay on layer 4.

Templates are data-driven so users can add custom templates as JSON files in
assets/motion_graphics/templates/.
"""
import json, math, os
from PIL import Image, ImageDraw, ImageFont
from . import paths, lexicon
from .util import read_json

W, H = 1920, 1080

PAL = {k: tuple(int(v[i:i + 2], 16) for i in (1, 3, 5)) for k, v in lexicon.PALETTE.items()}
RGBA = {k: v + (255,) for k, v in PAL.items()}
BONE_DIM = PAL["bone"] + (200,)
PANEL = (32, 37, 42, 235)
PANEL_SOFT = (32, 37, 42, 200)

ROLE_ACCENT = {"SOURCE": "muted_amber", "PRACTICAL_MOVE": "signal_blue",
               "COUNTEREXAMPLE": "uncertainty_gray", "LIMITATION": "uncertainty_gray",
               "PROBLEM": "oxide_red", "HOOK_SIGNAL": "oxide_red",
               "EMOTIONAL_RECOGNITION": "signal_blue", "PROMISE": "signal_blue"}

_font_cache = {}


def font(size, bold=False, mono=False):
    key = (size, bold, mono)
    if key in _font_cache:
        return _font_cache[key]
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    if mono:
        name = "DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf"
    path = os.path.join(paths.STATIC_DIR, "fonts", name)
    if not os.path.exists(path):
        path = os.path.join(paths.STATIC_DIR, "fonts", "DejaVuSans.ttf")
    f = ImageFont.truetype(path, size)
    _font_cache[key] = f
    return f


def wrap_text(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_tracked(draw, xy, text, fnt, fill, tracking=0):
    """Letter-spaced text (kicker style)."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking
    return x


def tracked_width(draw, text, fnt, tracking=0):
    return sum(draw.textlength(c, font=fnt) + tracking for c in text) - (tracking if text else 0)


def base_canvas():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def frame(draw, x, y, w, h, accent="bone", soft=False, thickness=2):
    fill = PANEL_SOFT if soft else PANEL
    draw.rounded_rectangle([x, y, x + w, y + h], radius=6, fill=fill,
                           outline=RGBA.get(accent, RGBA["bone"]) + (140,) if False else (232, 226, 214, 90), width=thickness)
    # accent tab on the left edge
    draw.rectangle([x - 5, y + 12, x - 1, y + h - 12], fill=RGBA.get(accent, RGBA["bone"]))


def kicker_bar(draw, x, y, label, accent="muted_amber", size=30):
    f = font(size, bold=True)
    wpx = tracked_width(draw, label.upper(), f, 6)
    draw.rectangle([x, y + size // 2 - 2, x + 46, y + size // 2 + 2], fill=RGBA[accent])
    draw_tracked(draw, (x + 62, y), label.upper(), f, RGBA[accent], 6)
    return wpx + 62


def rule(draw, x1, y, x2, color="bone", alpha=110, w=2):
    draw.line([x1, y, x2, y], fill=RGBA[color][:3] + (alpha,), width=w)


# ---------------------------------------------------------------- templates
def t_fact_card(img, draw, p):
    accent = p.get("accent", "bone")
    frame(draw, 560, 380, 800, 320, accent)
    kicker_bar(draw, 610, 430, p.get("kicker", "KEY FACT"), accent)
    f = font(72, bold=True)
    lines = wrap_text(draw, p.get("title", "KEY FACT"), f, 700)
    y = 480
    for ln in lines[:3]:
        draw.text((610, y), ln, font=f, fill=RGBA["bone"])
        y += 84
    if p.get("body"):
        fb = font(34)
        for ln in wrap_text(draw, p["body"], fb, 700)[:2]:
            draw.text((610, y + 6), ln, font=fb, fill=BONE_DIM)
            y += 46
    return img


def t_number_card(img, draw, p):
    n = str(p.get("number", 1))
    accent = p.get("accent", "signal_blue")
    # giant ghost numeral
    fnum = font(460, bold=True)
    tw = draw.textlength(n, font=fnum)
    draw.text(((W - tw) / 2, 250), n, font=fnum, fill=PAL[accent] + (46,))
    # solid numeral chip + label
    draw.rectangle([820, 470, 1100, 610], outline=RGBA[accent], width=3)
    fn = font(96, bold=True)
    draw.text(((W - draw.textlength(n, font=fn)) / 2, 482), n, font=fn, fill=RGBA[accent])
    ft = font(56, bold=True)
    label = p.get("label", "FACT")
    draw.text(((W - draw.textlength(label, font=ft)) / 2, 640), label, font=ft, fill=RGBA["bone"])
    rule(draw, 860, 730, 1060, accent, 160, 3)
    if p.get("body"):
        fb = font(36)
        for i, ln in enumerate(wrap_text(draw, p["body"], fb, 900)[:2]):
            tw = draw.textlength(ln, font=fb)
            draw.text(((W - tw) / 2, 760 + i * 48), ln, font=fb, fill=BONE_DIM)
    return img


def t_title_card(img, draw, p):
    rule(draw, 660, 400, 1260, "bone", 90, 1)
    f = font(96, bold=True)
    lines = wrap_text(draw, p.get("title", "HUMAN SYSTEMS"), f, 1100)
    y = 440
    for ln in lines[:2]:
        tw = draw.textlength(ln, font=f)
        draw.text(((W - tw) / 2, y), ln, font=f, fill=RGBA["bone"])
        y += 108
    kicker_bar(draw, (W - tracked_width(draw, p.get("kicker", "A HUMAN SYSTEMS NOIR FILM"), font(28, True), 8)) / 2,
               680, p.get("kicker", "A HUMAN SYSTEMS NOIR FILM"), "muted_amber", 28)
    rule(draw, 660, 760, 1260, "bone", 90, 1)
    return img


def t_quote_card(img, draw, p):
    fq = font(300, bold=True)
    draw.text((330, 200), "“", font=fq, fill=PAL["signal_blue"] + (70,))
    frame(draw, 460, 330, 1000, 420, "signal_blue", soft=True)
    f = font(52, bold=False)
    lines = wrap_text(draw, p.get("title", ""), f, 880)
    y = 390
    for ln in lines[:5]:
        draw.text((510, y), ln, font=f, fill=RGBA["bone"])
        y += 66
    if p.get("body"):
        fb = font(30, bold=True)
        draw_tracked(draw, (510, y + 16), p["body"].upper(), fb, RGBA["signal_blue"], 4)
    return img


def t_warning_card(img, draw, p):
    frame(draw, 560, 380, 800, 320, "oxide_red")
    # hazard stripes top edge
    for i in range(-8, 26):
        x = 560 + i * 40
        draw.polygon([(x, 380), (x + 20, 380), (x + 8, 392), (x - 12, 392)], fill=PAL["oxide_red"] + (200,))
    kicker_bar(draw, 610, 430, p.get("kicker", "WARNING"), "oxide_red")
    f = font(66, bold=True)
    lines = wrap_text(draw, p.get("title", "COMMON TRAP"), f, 700)
    y = 486
    for ln in lines[:2]:
        draw.text((610, y), ln, font=f, fill=RGBA["bone"])
        y += 78
    if p.get("body"):
        fb = font(32)
        for ln in wrap_text(draw, p["body"], fb, 700)[:2]:
            draw.text((610, y + 4), ln, font=fb, fill=BONE_DIM)
            y += 44
    return img


def t_statistic_card(img, draw, p):
    frame(draw, 520, 360, 880, 360, "muted_amber")
    kicker_bar(draw, 570, 410, p.get("kicker", "THE DATA"), "muted_amber")
    fnum = font(150, bold=True)
    num = p.get("stat", "68%")
    draw.text((570, 470), num, font=fnum, fill=RGBA["muted_amber"])
    numw = draw.textlength(num, font=fnum)
    fb = font(36)
    y = 500
    for ln in wrap_text(draw, p.get("body", ""), fb, 800 - numw - 40)[:4]:
        draw.text((590 + numw, y), ln, font=fb, fill=RGBA["bone"])
        y += 48
    if p.get("source"):
        fs = font(26, bold=True)
        draw.text((570, 660), "SOURCE: " + p["source"].upper(), font=fs, fill=PAL["muted_amber"] + (220,))
    return img


def t_list_intro(img, draw, p):
    count = int(p.get("count", 3))
    label = p.get("label", "FACTS").upper()
    title = p.get("title", f"{count} {label}")
    f = font(120, bold=True)
    lines = wrap_text(draw, title.upper(), f, 1200)
    y = 350
    for ln in lines[:2]:
        tw = draw.textlength(ln, font=f)
        draw.text(((W - tw) / 2, y), ln, font=f, fill=RGBA["bone"])
        y += 132
    # numbered nodes
    total_w = count * 120 + (count - 1) * 60
    x = (W - total_w) / 2
    fy = font(52, bold=True)
    for i in range(count):
        cx = x + i * 180
        draw.ellipse([cx, 700, cx + 110, 810], outline=RGBA["signal_blue"], width=4)
        num = str(i + 1)
        tw = draw.textlength(num, font=fy)
        draw.text((cx + (110 - tw) / 2, 712), num, font=fy, fill=RGBA["signal_blue"])
        if i < count - 1:
            draw.line([cx + 118, 755, cx + 172, 755], fill=(232, 226, 214, 120), width=2)
    return img


def t_list_summary(img, draw, p):
    items = p.get("items") or ["The pattern is observable", "Meaning is not proof", "One move changes the loop"]
    frame(draw, 480, 250, 960, 580, "signal_blue", soft=True)
    kicker_bar(draw, 530, 300, p.get("kicker", "TO RECAP"), "signal_blue")
    y = 380
    fn = font(44, bold=True)
    fb = font(34)
    for i, it in enumerate(items[:4]):
        if isinstance(it, dict):
            head, body = it.get("title", ""), it.get("body", "")
        else:
            head, body = it, ""
        draw.ellipse([530, y + 6, 566, y + 42], outline=RGBA["signal_blue"], width=3)
        draw.text((540, y + 8), str(i + 1), font=font(24, bold=True), fill=RGBA["signal_blue"])
        draw.text((590, y), head, font=fn, fill=RGBA["bone"])
        if body:
            for j, ln in enumerate(wrap_text(draw, body, fb, 780)[:2]):
                draw.text((590, y + 56 + j * 42), ln, font=fb, fill=BONE_DIM)
            y += 60
        y += 76
    return img


def t_mechanism_map(img, draw, p):
    """Cause → effect node map from segment concepts."""
    nodes = p.get("nodes") or ["TRIGGER", "RESPONSE", "REINFORCEMENT"]
    n = len(nodes)
    frame(draw, 360, 400, 1200, 280, "bone", soft=True)
    kicker_bar(draw, 410, 350, p.get("kicker", "MECHANISM"), "muted_amber")
    bw, gap = 300, 110
    total = n * bw + (n - 1) * gap
    x = (W - total) / 2
    y = 500
    fb = font(32, bold=True)
    for i, node in enumerate(nodes[:4]):
        draw.rounded_rectangle([x, y, x + bw, y + 90], radius=8, outline=RGBA["bone"], width=3)
        lines = wrap_text(draw, node.upper()[:24], fb, bw - 30)
        ty = y + (90 - len(lines) * 38) / 2
        for ln in lines:
            tw = draw.textlength(ln, font=fb)
            draw.text((x + (bw - tw) / 2, ty), ln, font=fb, fill=RGBA["bone"])
            ty += 38
        if i < n - 1:
            ax = x + bw
            draw.line([ax + 8, y + 45, ax + gap - 16, y + 45], fill=RGBA["muted_amber"], width=3)
            draw.polygon([(ax + gap - 16, y + 37), (ax + gap - 4, y + 45), (ax + gap - 16, y + 53)],
                         fill=RGBA["muted_amber"])
        x += bw + gap
    return img


def t_timeline(img, draw, p):
    """Horizontal timeline with markers — moving goalposts / escalation / repair."""
    marks = p.get("marks") or ["AGREE", "RULES CHANGE", "NEW DEMANDS", "PATTERN"]
    accent = p.get("accent", "oxide_red")
    y = 560
    x1, x2 = 360, 1560
    draw.line([x1, y, x2, y], fill=(232, 226, 214, 160), width=3)
    kicker_bar(draw, 410, 470, p.get("kicker", "TIMELINE"), accent)
    n = len(marks)
    fb = font(30, bold=True)
    for i, m in enumerate(marks[:5]):
        cx = x1 + (x2 - x1) * (i / max(1, n - 1))
        last = i == n - 1
        col = RGBA[accent] if last else RGBA["bone"]
        r = 16 if last else 10
        draw.ellipse([cx - r, y - r, cx + r, y + r], fill=col)
        above = i % 2 == 0
        ly = y - 66 if above else y + 40
        lines = wrap_text(draw, m.upper()[:26], fb, 260)
        for j, ln in enumerate(lines[:2]):
            tw = draw.textlength(ln, font=fb)
            draw.text((cx - tw / 2, ly + j * 34), ln, font=fb, fill=col)
        if last:
            # flag pole showing the final shifted state
            draw.line([cx, y - 4, cx, y - 90], fill=RGBA[accent], width=3)
            draw.polygon([(cx, y - 90), (cx + 56, y - 76), (cx, y - 62)], fill=RGBA[accent])
    return img


def t_decision_tree(img, draw, p):
    frame(draw, 460, 330, 1000, 420, "signal_blue", soft=True)
    kicker_bar(draw, 510, 380, p.get("kicker", "DECISION"), "signal_blue")
    fb = font(34, bold=True)
    root = p.get("title", "Is the request changing?")
    lines = wrap_text(draw, root, fb, 360)
    y = 470
    for ln in lines[:2]:
        draw.text((510, y), ln, font=fb, fill=RGBA["bone"])
        y += 42
    yes, no = p.get("yes", "State the agreement"), p.get("no", "Continue as usual")
    bx = 950
    draw.text((bx, 450), "YES →", font=font(30, bold=True), fill=RGBA["signal_blue"])
    for j, ln in enumerate(wrap_text(draw, yes, fb, 420)[:2]):
        draw.text((bx + 110, 450 + j * 42), ln, font=fb, fill=RGBA["bone"])
    draw.text((bx, 580), "NO →", font=font(30, bold=True), fill=RGBA["uncertainty_gray"])
    for j, ln in enumerate(wrap_text(draw, no, fb, 420)[:2]):
        draw.text((bx + 110, 580 + j * 42), ln, font=fb, fill=BONE_DIM)
    draw.line([870, 470, 930, 470], fill=RGBA["signal_blue"], width=2)
    draw.line([870, 590, 930, 590], fill=RGBA["uncertainty_gray"], width=2)
    return img


def t_evidence_card(img, draw, p):
    """CLAIM / SOURCE / DATE / LIMIT — amber for source, gray for limitation."""
    frame(draw, 480, 250, 960, 580, "muted_amber")
    kicker_bar(draw, 530, 300, "EVIDENCE", "muted_amber")
    fhead = font(28, bold=True)
    fbody = font(38, bold=True)
    ftxt = font(34)
    y = 380
    draw.text((530, y), "CLAIM", font=fhead, fill=PAL["bone"] + (200,))
    y += 40
    for ln in wrap_text(draw, p.get("claim", ""), fbody, 860)[:2]:
        draw.text((530, y), ln, font=fbody, fill=RGBA["bone"])
        y += 48
    y += 14
    rule(draw, 530, y, 1390, "bone", 60, 1)
    y += 18
    src = p.get("source") or "Source not stated in script"
    draw.text((530, y), "SOURCE", font=fhead, fill=PAL["muted_amber"])
    draw.text((680, y - 4), src, font=ftxt, fill=RGBA["muted_amber"])
    y += 52
    if p.get("date"):
        draw.text((530, y), "DATE", font=fhead, fill=PAL["muted_amber"])
        draw.text((680, y - 4), str(p["date"]), font=ftxt, fill=RGBA["muted_amber"])
        y += 52
    y += 10
    lim = p.get("limit") or "What this does NOT prove is not stated"
    draw.text((530, y), "LIMIT", font=fhead, fill=PAL["uncertainty_gray"])
    for ln in wrap_text(draw, lim, ftxt, 800)[:2]:
        draw.text((680, y - 4), ln, font=ftxt, fill=RGBA["uncertainty_gray"])
        y += 44
    return img


def t_counterexample_card(img, draw, p):
    """OBSERVED vs INTERPRETED vs ALTERNATIVE — three-column discipline."""
    frame(draw, 340, 300, 1240, 480, "uncertainty_gray", soft=True)
    kicker_bar(draw, 390, 350, "COUNTEREXAMPLE", "uncertainty_gray")
    cols = [
        ("OBSERVED", p.get("observed", "What you can see"), "bone"),
        ("INTERPRETED", p.get("interpreted", "What you assume"), "oxide_red"),
        ("ALTERNATIVE", p.get("alternative", "What else it could be"), "uncertainty_gray"),
    ]
    x = 390
    fb = font(30, bold=True)
    ft = font(34)
    for head, body, col in cols:
        draw.text((x, 430), head, font=fb, fill=RGBA[col])
        rule(draw, x, 470, x + 360, col, 150, 3)
        yy = 495
        for ln in wrap_text(draw, body, ft, 360)[:5]:
            draw.text((x, yy), ln, font=ft, fill=RGBA[col] if col != "bone" else RGBA["bone"])
            yy += 44
        x += 410
    return img


def t_uncertainty_card(img, draw, p):
    frame(draw, 520, 400, 880, 280, "uncertainty_gray")
    kicker_bar(draw, 570, 450, p.get("kicker", "WHAT WE DON'T KNOW"), "uncertainty_gray")
    f = font(52, bold=True)
    y = 510
    for ln in wrap_text(draw, p.get("title", "The evidence has limits"), f, 780)[:3]:
        draw.text((570, y), ln, font=f, fill=RGBA["bone"])
        y += 62
    return img


def t_definition_card(img, draw, p):
    frame(draw, 480, 350, 960, 380, "bone")
    kicker_bar(draw, 530, 400, p.get("kicker", "DEFINITION"), "bone")
    f = font(58, bold=True)
    y = 460
    for ln in wrap_text(draw, p.get("title", ""), f, 860)[:4]:
        draw.text((530, y), ln, font=f, fill=RGBA["bone"])
        y += 70
    if p.get("body"):
        fb = font(32)
        for ln in wrap_text(draw, p["body"], fb, 860)[:2]:
            draw.text((530, y + 6), ln, font=fb, fill=BONE_DIM)
            y += 44
    return img


def t_playbook_rail(img, draw, p):
    """NOTICE → REGULATE → VERIFY → BOUNDARY → BUILD with step highlighting."""
    steps = lexicon.PLAYBOOK_STEPS
    active = int(p.get("active", -1))
    y = 560
    x1, x2 = 360, 1560
    draw.line([x1, y, x2, y], fill=(94, 142, 165, 170), width=4)
    kicker_bar(draw, 410, 440, "THE PLAYBOOK", "signal_blue")
    n = len(steps)
    seg = (x2 - x1) / (n - 1)
    fb = font(36, bold=True)
    fs = font(24)
    for i, (name, hint) in enumerate(steps):
        cx = x1 + i * seg
        on = i == active
        done = 0 <= active and i < active
        col = RGBA["signal_blue"] if (on or done) else (232, 226, 214, 150)
        r = 26 if on else 14
        draw.ellipse([cx - r, y - r, cx + r, y + r], fill=col if on else (17, 19, 21, 255),
                     outline=col, width=4)
        if done:
            draw.line([cx - 10, y, cx - 3, y + 8], fill=RGBA["signal_blue"], width=4)
            draw.line([cx - 3, y + 8, cx + 11, y - 9], fill=RGBA["signal_blue"], width=4)
        tw = draw.textlength(name, font=fb)
        draw.text((cx - tw / 2, y - 110), name, font=fb, fill=col)
        if on and p.get("hint", True):
            hint_lns = wrap_text(draw, "“" + hint + "”", fs, 380)
            yy = y + 44
            box_h = len(hint_lns) * 32 + 24
            box_w = max(draw.textlength("“" + hint + "”", font=fs) for _ in [0]) + 36
            box_w = min(420, box_w + 20)
            draw.rounded_rectangle([cx - box_w / 2, yy, cx + box_w / 2, yy + box_h],
                                   radius=6, fill=(17, 19, 21, 230), outline=RGBA["signal_blue"], width=2)
            for ln in hint_lns:
                lw = draw.textlength(ln, font=fs)
                draw.text((cx - lw / 2, yy + 12), ln, font=fs, fill=RGBA["bone"])
                yy += 32
    return img


def t_boundary_line(img, draw, p):
    """BLUE BOUNDARY LINE motif — a clean luminous horizontal limit."""
    y = 540
    for wdt, al in [(14, 36), (8, 70), (3, 235)]:
        draw.line([240, y, 1680, y], fill=PAL["signal_blue"] + (al,), width=wdt)
    kicker_bar(draw, 240, y - 110, p.get("kicker", "THE LIMIT"), "signal_blue")
    f = font(56, bold=True)
    yy = y + 50
    for ln in wrap_text(draw, p.get("title", "This far, then no further."), f, 1200)[:2]:
        tw = draw.textlength(ln, font=f)
        draw.text(((W - tw) / 2, yy), ln, font=f, fill=RGBA["bone"])
        yy += 70
    return img


def t_red_thread(img, draw, p):
    """RED THREAD motif — influence/obligation path across the frame."""
    pts = [(180, 780), (560, 470), (960, 640), (1360, 380), (1740, 560)]
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=PAL["oxide_red"] + (200,), width=5)
    for cx, cy in pts:
        draw.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=PAL["oxide_red"] + (255,))
    kicker_bar(draw, 180, 250, p.get("kicker", "THE THREAD"), "oxide_red")
    f = font(52, bold=True)
    yy = 860
    for ln in wrap_text(draw, p.get("title", "Every favor ties a thread."), f, 1300)[:2]:
        draw.text((180, yy), ln, font=f, fill=RGBA["bone"])
        yy += 66
    return img


def t_waveform_motif(img, draw, p):
    """WAVEFORM motif — voice/attention."""
    import random as _r
    rnd = _r.Random(p.get("seed", 4))
    cx, cy = W // 2, 520
    for i in range(64):
        x = cx - 480 + i * 15
        h = int((math.sin(i * 0.55) * 0.5 + 0.5) * 90 * (0.35 + rnd.random() * 0.65)) + 8
        col = RGBA["signal_blue"] if 20 <= i < 44 else (232, 226, 214, 140)
        draw.line([x, cy - h, x, cy + h], fill=col, width=6)
    kicker_bar(draw, cx - 180, cy - 260, p.get("kicker", "THE SIGNAL"), "signal_blue")
    f = font(50, bold=True)
    yy = cy + 140
    for ln in wrap_text(draw, p.get("title", "Attention has a shape."), f, 1100)[:2]:
        tw = draw.textlength(ln, font=f)
        draw.text(((W - tw) / 2, yy), ln, font=f, fill=RGBA["bone"])
        yy += 62
    return img


def t_ledger_motif(img, draw, p):
    frame(draw, 700, 280, 520, 520, "muted_amber")
    kicker_bar(draw, 750, 330, p.get("kicker", "THE LEDGER"), "muted_amber")
    y = 420
    for i in range(5):
        draw.line([750, y, 1000, y], fill=(232, 226, 214, 130), width=2)
        draw.line([1020, y - 14, 1060, y + 10], fill=PAL["muted_amber"] + (200,), width=3)  # tally mark
        y += 70
    f = font(46, bold=True)
    yy = 840
    for ln in wrap_text(draw, p.get("title", "Favors become debts."), f, 1100)[:2]:
        tw = draw.textlength(ln, font=f)
        draw.text(((W - tw) / 2, yy), ln, font=f, fill=RGBA["bone"])
        yy += 60
    return img


def t_door_motif(img, draw, p):
    cx = W // 2
    # minimal door: frame + slightly open leaf with light gap
    draw.rounded_rectangle([cx - 190, 260, cx + 190, 820], radius=8, outline=(232, 226, 214, 190), width=6)
    draw.rectangle([cx - 20, 268, cx + 178, 812], fill=(32, 37, 42, 255))
    draw.rectangle([cx + 160, 268, cx + 178, 812], fill=PAL["signal_blue"] + (120,))  # light edge
    draw.ellipse([cx + 120, 540, cx + 144, 564], fill=RGBA["bone"])
    kicker_bar(draw, cx - 190, 190, p.get("kicker", "THE DOOR"), "signal_blue")
    f = font(48, bold=True)
    yy = 870
    for ln in wrap_text(draw, p.get("title", "Exits are allowed."), f, 1100)[:2]:
        tw = draw.textlength(ln, font=f)
        draw.text(((W - tw) / 2, yy), ln, font=f, fill=RGBA["bone"])
        yy += 62
    return img


def t_clock_motif(img, draw, p):
    cx, cy, r = W // 2, 520, 250
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(232, 226, 214, 200), width=6)
    for i in range(12):
        a = math.pi * 2 * i / 12
        x1, y1 = cx + math.sin(a) * (r - 26), cy - math.cos(a) * (r - 26)
        x2, y2 = cx + math.sin(a) * (r - 10), cy - math.cos(a) * (r - 10)
        draw.line([x1, y1, x2, y2], fill=(232, 226, 214, 170), width=5)
    import random as _r
    rnd = _r.Random(p.get("seed", 7))
    ha = math.pi * 2 * rnd.randint(0, 11) / 12
    ma = math.pi * 2 * rnd.randint(0, 59) / 60
    draw.line([cx, cy, cx + math.sin(ha) * (r * 0.5), cy - math.cos(ha) * (r * 0.5)], fill=RGBA["bone"], width=10)
    draw.line([cx, cy, cx + math.sin(ma) * (r * 0.78), cy - math.cos(ma) * (r * 0.78)], fill=RGBA["oxide_red"], width=6)
    draw.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=RGBA["bone"])
    kicker_bar(draw, cx - 150, cy - r - 90, p.get("kicker", "THE CLOCK"), "muted_amber")
    return img


def t_document_motif(img, draw, p):
    x, y, w, h = 760, 240, 400, 560
    draw.rectangle([x + 12, y + 12, x + w + 12, y + h + 12], fill=(17, 19, 21, 200))  # shadow
    draw.rectangle([x, y, x + w, y + h], fill=(232, 226, 214, 245))
    ly = y + 50
    for i in range(11):
        wl = w - 90 if i % 3 else w - 150
        draw.line([x + 45, ly, x + 45 + wl, ly], fill=(32, 37, 42, 200), width=8)
        ly += 42
    draw.line([x + 45, y + h - 110, x + w - 45, y + h - 110], fill=PAL["oxide_red"] + (255,), width=4)
    draw_tracked(draw, (x + 45, y + h - 90), "SIGNED?", font(24, bold=True), PAL["oxide_red"], 4)
    kicker_bar(draw, x + 20, 150, p.get("kicker", "THE DOCUMENT"), "muted_amber")
    return img


TEMPLATES = {
    "fact_card": t_fact_card, "number_card": t_number_card, "title_card": t_title_card,
    "quote_card": t_quote_card, "warning_card": t_warning_card, "statistic_card": t_statistic_card,
    "list_intro": t_list_intro, "list_summary": t_list_summary, "mechanism_map": t_mechanism_map,
    "timeline": t_timeline, "decision_tree": t_decision_tree, "evidence_card": t_evidence_card,
    "counterexample_card": t_counterexample_card, "uncertainty_card": t_uncertainty_card,
    "definition_card": t_definition_card, "playbook_rail": t_playbook_rail,
    "boundary_line": t_boundary_line, "red_thread": t_red_thread, "waveform": t_waveform_motif,
    "ledger": t_ledger_motif, "door": t_door_motif, "clock": t_clock_motif, "document": t_document_motif,
}


def list_templates() -> list:
    return sorted(TEMPLATES.keys())


def render_graphic(template: str, params: dict | None = None, seed: int = 0) -> Image.Image:
    """Render one motion graphic to a transparent RGBA image."""
    params = dict(params or {})
    # custom user template?
    custom = os.path.join(paths.ASSETS_DIR, "motion_graphics", "templates", f"{template}.json")
    if not os.path.exists(custom) and template in TEMPLATES:
        params.setdefault("seed", seed)
        img = base_canvas()
        draw = ImageDraw.Draw(img)
        return TEMPLATES[template](img, draw, params)
    if os.path.exists(custom):
        spec = read_json(custom, {}) or {}
        # custom template: JSON that may reference a base template + overrides
        base = spec.get("base", "fact_card")
        params.update(spec.get("params", {}))
        params.setdefault("seed", seed)
        if base in TEMPLATES:
            img = base_canvas()
            draw = ImageDraw.Draw(img)
            return TEMPLATES[base](img, draw, params)
    # unknown template → plain fact card fallback
    img = base_canvas()
    draw = ImageDraw.Draw(img)
    return TEMPLATES["fact_card"](img, draw, {"title": template.replace("_", " ").upper(),
                                              "kicker": "HUMAN SYSTEMS NOIR"})


def params_from_segment(seg: dict) -> tuple:
    """Derive (template, params) from a timeline segment's motion_graphic entry."""
    mg = seg.get("motion_graphic") or {}
    template = mg.get("template", "fact_card")
    params = dict(mg.get("params") or {})
    accent = ROLE_ACCENT.get(seg.get("role", ""), "bone")
    params.setdefault("accent", accent)
    text = seg.get("text", "")
    concepts = seg.get("concepts") or []
    if template in ("fact_card", "definition_card", "uncertainty_card", "title_card", "quote_card", "warning_card"):
        params.setdefault("title", _headline_from(seg))
        params.setdefault("kicker", _kicker_from(seg, template))
        if len(text) > 90:
            params.setdefault("body", text[:160] + ("…" if len(text) > 160 else ""))
    if template == "number_card":
        if "number" not in params:
            import re
            m = re.search(r"\b(first|second|third|1|2|3)\b", text, re.I)
            params["number"] = {"first": 1, "second": 2, "third": 3}.get((m.group(1).lower() if m else None), 1)
        params.setdefault("label", "FACT" if "fact" in text.lower() else "POINT")
    if template == "list_intro":
        params.setdefault("label", "FACTS" if "fact" in text.lower() else "POINTS")
        params.setdefault("title", _headline_from(seg, upper=True))
    if template == "evidence_card":
        ev = seg.get("evidence_status") or {}
        meta = ev.get("meta") or {}
        params.setdefault("claim", _headline_from(seg))
        params.setdefault("source", meta.get("author") or _extract_source(text))
        params.setdefault("date", meta.get("year") or (ev.get("year")))
        params.setdefault("limit", meta.get("limit") or None)
    if template == "counterexample_card":
        params.setdefault("observed", _headline_from(seg, maxlen=70))
    if template == "mechanism_map":
        nodes = [c.upper() for c in concepts[:3]] or ["TRIGGER", "RESPONSE", "RESULT"]
        while len(nodes) < 3:
            nodes.append("OUTCOME")
        params.setdefault("nodes", nodes)
        params.setdefault("kicker", "MECHANISM")
    if template == "timeline":
        params.setdefault("kicker", "TIMELINE")
    if template == "playbook_rail":
        params.setdefault("active", params.get("number", 0) - 1 if params.get("number") else -1)
    if template in ("red_thread", "waveform", "ledger", "door", "clock", "document", "boundary_line"):
        params.setdefault("title", _headline_from(seg))
        params.setdefault("kicker", template.replace("_", " ").upper())
    return template, params


def _headline_from(seg, maxlen=70, upper=False):
    text = seg.get("text", "")
    words = text.split()
    head = " ".join(words[:10])
    if len(words) > 10:
        head += "…"
    head = head.strip()
    if upper:
        head = head.upper()
    return head[:maxlen] if len(head) > maxlen else head


def _kicker_from(seg, template):
    role = seg.get("role", "")
    return {"warning_card": "WARNING", "definition_card": "DEFINITION",
            "uncertainty_card": "WHAT WE DON'T KNOW", "quote_card": "RECOGNIZE THIS",
            "title_card": "HUMAN SYSTEMS NOIR", "fact_card": "KEY FACT"}.get(template, role.replace("_", " ").title())


def _extract_source(text):
    import re
    m = re.search(r"(?:according to|published in|researchers at|a \d{4} study (?:by|from))\s+([A-Z][\w&.\- ]{2,40})", text)
    if m:
        return m.group(1).strip()
    m = re.search(r"\b(19|20)\d{2}\b", text)
    return f"Study cited ({m.group(0)})" if m else None
