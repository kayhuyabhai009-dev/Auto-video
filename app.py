import concurrent.futures
import gzip
import hashlib
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from flask import Flask, jsonify, render_template_string, request, send_from_directory
import requests

app = Flask(__name__)

CACHE_DIR = "static/cache"
os.makedirs(CACHE_DIR, exist_ok=True)

GENERATION_HISTORY = []

# =====================================================================
# 1. CAPCUT ENGINE CONFIGURATION & SECURITY TOKENS
# =====================================================================

BASE_HOST = "https://editor-api-sg.capcutapi.com"

DEVICE_CONFIG = {
    "appvr": "19.6.0",
    "vc": "19600200",
    "vr": "288382976",
    "aid": "3006",
    "channel": "googleplay",
    "lan": "en",
    "loc": "ca",
    "region": "IN",
    "pf": "0",  # Android
    "tdid": "1909999081066873263",
    "hdr_tdid": "56889999854344566",
    "did": "ffffffff-8636-1a4e-ffff-ffffef05ac4a",
    "openudid": "7ff636da1fa1c2ed",
    "cdid": "fd118f24-894c-4e05-8e2b-7c52333664c6",
    "device_type": "RMX3491",
    "device_brand": "realme",
    "model": "Uk1YMzQ5MQ==",
    "manu": "cmVhbG1l",
    "gpurender": "QWRyZW5vIChUTSkgNjEw",
    "user_agent": "com.lemon.lvoverseas/19600200 (Linux; U; Android 13; en_IN; RMX3491; Build/RKQ1.211119.001; Cronet/TTNetVersion:82120377 2026-01-13 QuicVersion:5f252c33 2025-12-30)",
}

COOKIES = {
    "store-idc": "alisg",
    "store-country-code": "in",
    "store-country-code-src": "did",
    "install_id": "7684294038489024277",
    "ttreq": "1$dc19eebd76db7e304b014f68533d247bd72c9698",
    "store-country-sign": "MEIEDKdfNTsleeCtv_PEWAQgeRWhtBqNnRWraPQqSBhwoVsHV66TYlb3Jlf3ET6ajhsEELia0BmYKYxUGvJNgRqqDF8",
    "msToken": "QLijwVK5-ZkgyMUqYfE6Ieb48er008Lctmt4gwt_VOH-Go1GqNfbEoaehELRy8U2czHZDegjOOgSlNC7JAR5NUjgrEE2CgW4Y0nxmzgwP-WJ",
}

# =====================================================================
# 2. VERIFIED 11LABS VOICE MODELS
# =====================================================================

VOICE_DATABASE = [
    # --- MALE VOICES ---
    {
        "id": "7374727433896858128",
        "title": "Alex Pro (Flagship)",
        "voice_type": "iDJbhuGTR9N7lXjELodg",
        "platform": "11labs",
        "category": "male",
        "avatar": "https://p16-vimo-sg.ibyteimg.com/tos-alisg-i-aifo7olm7m-sg/d34d9009483244c09d73723b1865f21a",
        "lang": "HI / EN",
        "gender": "Male",
        "tag": "Hyper Realistic",
        "desc": "Ultra-rich cinematic voice. Best for YouTube and Reels."
    },
    {
        "id": "7477926365174436369",
        "title": "Noah Storyteller",
        "voice_type": "dlGxemPxFMTY7iXagmOj",
        "platform": "11labs",
        "category": "male",
        "avatar": "https://p16-vimo-sg.ibyteimg.com/tos-alisg-i-aifo7olm7m-sg/ad5f770b9114498b82a688c940e95f4c",
        "lang": "HI / EN",
        "gender": "Male",
        "tag": "Warm & Natural",
        "desc": "Deep emotional tone. Perfect for documentaries & stories."
    },
    {
        "id": "7628539149762481428",
        "title": "Liam Dynamic",
        "voice_type": "ZthjuvLPty3kTMaNKVKb",
        "platform": "11labs",
        "category": "male",
        "avatar": "https://p16-vimo-sg.ibyteimg.com/tos-alisg-i-aifo7olm7m-sg/86e873a04aa548378a5fd867a9b1c671",
        "lang": "HI / EN",
        "gender": "Male",
        "tag": "Youthful & Punchy",
        "desc": "High energy delivery. Best for viral hooks and ads."
    },
    {
        "id": "7369525170723099153",
        "title": "Adam Deep Narrator",
        "voice_type": "pNInz6obpgDQGcFmaJgB",
        "platform": "11labs",
        "category": "male",
        "avatar": "https://p16-heycan-image-sign-sg.ibyteimg.com/tos-alisg-i-fhsjxsyzit-sg/19e71838c5bb4dc191e3f0beb2744560~tplv-fhsjxsyzit-image.image",
        "lang": "HI / EN",
        "gender": "Male",
        "tag": "Classic Authority",
        "desc": "Authoritative baritone. Ideal for podcasts and explainers."
    },
    {
        "id": "7374727502712803841",
        "title": "Marcus Deep Bass",
        "voice_type": "153KLsX4S9dcU9E750gG",
        "platform": "11labs",
        "category": "male",
        "avatar": "https://p16-vimo-sg.ibyteimg.com/tos-alisg-i-aifo7olm7m-sg/d88409ece841488da2717856961fd654",
        "lang": "HI / EN",
        "gender": "Male",
        "tag": "Cinematic Bass",
        "desc": "Heavy low-frequency voice for movie trailers and mystery."
    },
    {
        "id": "7373896904729432577",
        "title": "Ethan Calm Host",
        "voice_type": "WGOZZ50ZyX8GWtwZGVDW",
        "platform": "11labs",
        "category": "male",
        "avatar": "https://p16-vimo-sg.ibyteimg.com/tos-alisg-i-aifo7olm7m-sg/12acec5a952549dd912f05399fdb7bc2",
        "lang": "HI / EN",
        "gender": "Male",
        "tag": "Friendly Podcast",
        "desc": "Casual and approachable. Great for conversation & tutorials."
    },
    {
        "id": "7374671961181393424",
        "title": "Daniel News Anchor",
        "voice_type": "XZq0uRgnKv2uOpky5Fbk",
        "platform": "11labs",
        "category": "male",
        "avatar": "https://p16-vimo-sg.ibyteimg.com/tos-alisg-i-aifo7olm7m-sg/b6e21f7c44224f9fbf500cd2dffa55a1",
        "lang": "HI / EN",
        "gender": "Male",
        "tag": "News Broadcast",
        "desc": "Crisp studio broadcast voice. Ideal for business & tech news."
    },
    {
        "id": "7424031714290176513",
        "title": "Lucas Commercial",
        "voice_type": "2gPFXx8pN3Avh27Dw5Ma",
        "platform": "11labs",
        "category": "male",
        "avatar": "https://p16-vimo-sg.ibyteimg.com/tos-alisg-i-aifo7olm7m-sg/d1ed43ecb85a46b49b66e93442b3d567",
        "lang": "HI / EN",
        "gender": "Male",
        "tag": "Promo & Ads",
        "desc": "Fast, clear and persuasive. Built for social media ads."
    },

    # --- FEMALE VOICES ---
    {
        "id": "7374727186323870209",
        "title": "Bella Soft Female",
        "voice_type": "XMWzAzwYm487GEok2uG2",
        "platform": "11labs",
        "category": "female",
        "avatar": "https://p16-vimo-sg.ibyteimg.com/tos-alisg-i-aifo7olm7m-sg/b41cac8c9b8a47198af78de70be38e69",
        "lang": "HI / EN",
        "gender": "Female",
        "tag": "Soothing & Sweet",
        "desc": "Soft feminine tone. Best for bedtime stories and affirmations."
    },
    {
        "id": "7374726937425482256",
        "title": "Emma Storyteller",
        "voice_type": "s73DTGwP2RrOFSydhplL",
        "platform": "11labs",
        "category": "female",
        "avatar": "https://p16-vimo-sg.ibyteimg.com/tos-alisg-i-aifo7olm7m-sg/0dda0f9276f14bc5bc8c623d3449bd1b",
        "lang": "HI / EN",
        "gender": "Female",
        "tag": "Engaging & Bright",
        "desc": "Lively voice with emotional inflection for children stories."
    },
    {
        "id": "7374727348349833729",
        "title": "Chloe Crisp Explainer",
        "voice_type": "InSLKyTvFCIeQZ0a0eES",
        "platform": "11labs",
        "category": "female",
        "avatar": "https://p16-vimo-sg.ibyteimg.com/tos-alisg-i-aifo7olm7m-sg/9d93c5f00e2c43ee9023875fd05c7f61",
        "lang": "HI / EN",
        "gender": "Female",
        "tag": "Corporate Explainer",
        "desc": "Articulate and confident voice for course videos & marketing."
    },
    {
        "id": "7579091304517291280",
        "title": "Sophia Emotional Narration",
        "voice_type": "mkRaeFYOxJgf5w1emssQ",
        "platform": "11labs",
        "category": "female",
        "avatar": "https://p16-vimo-sg.ibyteimg.com/tos-alisg-i-aifo7olm7m-sg/837ad74ac10548b3bd13660fd474a253",
        "lang": "HI / EN",
        "gender": "Female",
        "tag": "Deep Dramatic",
        "desc": "Cinematic female narration for suspense and drama."
    }
]

# =====================================================================
# 3. SIGNATURE HELPERS
# =====================================================================

def compact_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

def make_x_ss_stub(body_bytes: bytes) -> str:
    return hashlib.md5(body_bytes).hexdigest().upper()

def make_trace_id() -> str:
    seed = uuid.uuid4().hex[:32]
    return f"00-{seed}-{seed[:16]}-01"

def make_sign_header(path: str, pf: str, appvr: str, device_time: str, tdid: str) -> str:
    clean_path = path.split("?", 1)[0]
    return hashlib.md5(f"9e2c|{clean_path[-7:]}|{pf}|{appvr}|{device_time}|{tdid}|11ac".encode("utf-8")).hexdigest()

def make_header_content(path: str, pf: str, appvr: str, device_time: str, tdid: str) -> str:
    clean_path = path.split("?", 1)[0]
    return f"{clean_path[-7:]}|{pf}|{appvr}|{device_time}|{tdid}"

def build_capcut_headers(path: str, body_bytes: bytes) -> Dict[str, str]:
    now = time.time()
    now_sec = str(int(now))
    now_ms = str(int(now * 1000))
    pf = DEVICE_CONFIG["pf"]
    appvr = DEVICE_CONFIG["appvr"]
    tdid = DEVICE_CONFIG["tdid"]
    hdr_tdid = DEVICE_CONFIG["hdr_tdid"]

    return {
        "lan": DEVICE_CONFIG["lan"],
        "loc": DEVICE_CONFIG["loc"],
        "pf": pf,
        "vr": DEVICE_CONFIG["vr"],
        "appvr": appvr,
        "vc": DEVICE_CONFIG["vc"],
        "device-time": now_sec,
        "tdid": tdid,
        "sign-ver": "1",
        "sign": make_sign_header(path, pf, appvr, now_sec, tdid),
        "app-sdk-version": "184.0.0",
        "appid": DEVICE_CONFIG["aid"],
        "header-content": make_header_content(path, pf, appvr, now_sec, tdid),
        "host-abi": "64",
        "cc-newuser-channel": "common",
        "cache-control": "no-cache",
        "sysvr": "33",
        "ch": DEVICE_CONFIG["channel"],
        "uid": "0",
        "compressed": "1",
        "did": DEVICE_CONFIG["did"],
        "model": DEVICE_CONFIG["model"],
        "manu": DEVICE_CONFIG["manu"],
        "gpurender": DEVICE_CONFIG["gpurender"],
        "hdr-tdid": hdr_tdid,
        "hdr-device-time": now_sec,
        "version_code": DEVICE_CONFIG["vr"],
        "hdr-sign": make_sign_header(path, pf, appvr, now_sec, hdr_tdid),
        "hdr-sign-ver": "1",
        "x-ss-req-ticket": now_ms,
        "commerce-sign-version": "v1",
        "x-vc-bdturing-sdk-version": "2.3.10.i18n",
        "sdk-version": "2",
        "passport-sdk-version": "-1",
        "region": DEVICE_CONFIG["loc"],
        "x-tt-pba-enable": "1",
        "store-country-code": DEVICE_CONFIG["region"].lower(),
        "is-dispatch-us-ttp": "0",
        "store-country-code-src": "local",
        "content-type": "application/json; charset=utf-8",
        "x-ss-stub": make_x_ss_stub(body_bytes),
        "x-ss-dp": DEVICE_CONFIG["aid"],
        "x-tt-trace-id": make_trace_id(),
        "user-agent": DEVICE_CONFIG["user_agent"],
        "accept-encoding": "gzip, deflate",
    }

def build_query_params() -> Dict[str, str]:
    return {
        "ac": "wifi",
        "channel": DEVICE_CONFIG["channel"],
        "aid": DEVICE_CONFIG["aid"],
        "app_name": "vicut",
        "version_code": DEVICE_CONFIG["vc"],
        "version_name": DEVICE_CONFIG["appvr"],
        "device_platform": "android",
        "os": "android",
        "ssmix": "a",
        "device_type": DEVICE_CONFIG["device_type"],
        "device_brand": DEVICE_CONFIG["device_brand"],
        "language": DEVICE_CONFIG["lan"],
        "os_api": "33",
        "os_version": "13",
        "openudid": DEVICE_CONFIG["openudid"],
        "manifest_version_code": DEVICE_CONFIG["vc"],
        "resolution": "1080*2254",
        "dpi": "480",
        "update_version_code": DEVICE_CONFIG["vc"],
        "_rticket": str(int(time.time() * 1000)),
        "carrier_region": DEVICE_CONFIG["region"],
        "mcc_mnc": "405856",
        "is_android_pad": "0",
        "is_pad_pro_installed": "0",
        "region": DEVICE_CONFIG["region"],
        "cdid": DEVICE_CONFIG["cdid"],
        "effect_sdk_version": "22.0.0",
        "subdivision_id": "1275715",
        "user_type": "personal_user",
    }

# =====================================================================
# 4. CHUNKER, PARALLEL PIPELINE & SUBTITLE GENERATION
# =====================================================================

def chunk_text(text: str, max_chars: int = 370) -> List[str]:
    """Smart sentence/word chunker."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    current = ""
    words = text.split(" ")

    for word in words:
        if len(current) + len(word) + 1 > max_chars:
            if current:
                chunks.append(current.strip())
                current = word
            else:
                chunks.append(word[:max_chars])
                current = word[max_chars:]
        else:
            current = f"{current} {word}" if current else word

    if current:
        chunks.append(current.strip())

    return chunks


def execute_capcut_tts_chunk(text: str, voice_type: str, resource_id: str) -> Optional[Tuple[bytes, List[Dict]]]:
    """Synthesizes single TTS chunk with polling & word boundary info."""
    session = requests.Session()
    session.cookies.update(COOKIES)

    new_path = "/lv/v1/text_to_speech/new"
    payload_new = {
        "platform": "11labs",
        "voice": voice_type,
        "resource_id": resource_id,
        "word_boundary_enabled": True,
        "input": [text],
        "sample_rate": 24000,
        "scene": "long_text_editor",
        "mock_tone_info": "",
    }
    body_new_bytes = compact_json(payload_new).encode("utf-8")
    headers_new = build_capcut_headers(new_path, body_new_bytes)
    params_new = build_query_params()

    task_id = None
    for _ in range(2):
        try:
            resp_new = session.post(f"{BASE_HOST}{new_path}", params=params_new, headers=headers_new, data=body_new_bytes, timeout=12)
            task_id = resp_new.json().get("data", {}).get("task_id")
            if task_id:
                break
        except Exception:
            time.sleep(1)

    if not task_id:
        return None

    query_path = "/lv/v1/text_to_speech/query"
    payload_query = {"platform": "11labs", "task_id": task_id}
    body_query_bytes = compact_json(payload_query).encode("utf-8")

    # Polling Loop (Up to 25 attempts * 1.1s = 28 seconds timeout)
    for _ in range(25):
        time.sleep(1.1)
        headers_query = build_capcut_headers(query_path, body_query_bytes)
        params_query = build_query_params()

        try:
            resp_query = session.post(f"{BASE_HOST}{query_path}", params=params_query, headers=headers_query, data=body_query_bytes, timeout=10)
            content = resp_query.content
            if content[:2] == b"\x1f\x8b":
                query_res = json.loads(gzip.decompress(content).decode("utf-8"))
            else:
                query_res = resp_query.json()

            resource_infos = query_res.get("data", {}).get("resource_infos", [])
            if resource_infos and "url" in resource_infos[0]:
                audio_url = resource_infos[0]["url"]
                words = resource_infos[0].get("sub_title_utterance", {}).get("words", [])
                dl_res = requests.get(audio_url, timeout=12)
                if dl_res.status_code == 200:
                    return dl_res.content, words
        except Exception:
            continue

    return None


def generate_srt_subtitles(chunks: List[str], chunk_durations: List[float]) -> str:
    """Builds time-synced SRT subtitle file."""
    def format_time(seconds: float) -> str:
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

    srt_lines = []
    current_time = 0.0

    for idx, (chunk, duration) in enumerate(zip(chunks, chunk_durations), 1):
        start = current_time
        end = current_time + max(duration, 1.5)
        srt_lines.append(f"{idx}\n{format_time(start)} --> {format_time(end)}\n{chunk}\n")
        current_time = end + 0.08

    return "\n".join(srt_lines)

# =====================================================================
# 5. REST APIS & PREVIEWS (~25 CHARACTERS)
# =====================================================================

@app.route("/api/voices", methods=["GET"])
def get_voices():
    category = request.args.get("category", "all")
    if category == "all":
        return jsonify({"status": "success", "voices": VOICE_DATABASE})
    filtered = [v for v in VOICE_DATABASE if v["category"] == category]
    return jsonify({"status": "success", "voices": filtered})


@app.route("/api/search", methods=["POST"])
def search_live():
    query = request.json.get("query", "").strip().lower()
    if not query:
        return jsonify({"status": "success", "voices": VOICE_DATABASE})

    results = [
        v for v in VOICE_DATABASE 
        if query in v["title"].lower() or query in v["voice_type"].lower() or query in v["tag"].lower() or query in v["gender"].lower()
    ]
    return jsonify({"status": "success", "voices": results})


@app.route("/api/preview", methods=["POST"])
def generate_sample_preview():
    """Generates exact ~25 character high quality preview."""
    data = request.json
    lang = data.get("lang", "en")
    voice_type = data.get("voice_type")
    resource_id = data.get("resource_id")

    # EXACT ~25 CHARACTERS PROMPT
    sample_text = "नमस्ते! यह आवाज़ का डेमो है।" if lang == "hi" else "Hello! This is a voice demo."
    result = execute_capcut_tts_chunk(sample_text, voice_type, resource_id)

    if result:
        audio_bytes, _ = result
        filename = f"preview_{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(CACHE_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(audio_bytes)
        return jsonify({"status": "success", "audio_url": f"/static/cache/{filename}"})

    return jsonify({"status": "error", "message": "Voice server busy. Click preview again."}), 500


@app.route("/api/generate", methods=["POST"])
def generate_full_tts():
    """Parallelized chunk synthesis with auto SRT subtitle builder."""
    data = request.json
    text = data.get("text", "").strip()
    voice_type = data.get("voice_type")
    resource_id = data.get("resource_id")

    if not text:
        return jsonify({"status": "error", "message": "Please enter script."}), 400

    chunks = chunk_text(text, max_chars=370)
    total_chunks = len(chunks)

    # Parallel Execution via ThreadPool
    results = [None] * total_chunks
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(total_chunks, 4)) as executor:
        future_to_idx = {
            executor.submit(execute_capcut_tts_chunk, chunk, voice_type, resource_id): i 
            for i, chunk in enumerate(chunks)
        }
        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                res = future.result()
                if res:
                    results[idx] = res
            except Exception as e:
                print(f"[!] Error on chunk {idx}:", e)

    if any(r is None for r in results):
        return jsonify({"status": "error", "message": "Failed to synthesize one of the segments. Please retry."}), 500

    # Merge audio bytes & compute durations
    merged_bytes = bytearray()
    chunk_durations = []
    for audio_data, words in results:
        merged_bytes.extend(audio_data)
        last_word_end = words[-1]["end_time"] if words and "end_time" in words[-1] else (len(audio_data) / 3000)
        chunk_durations.append(last_word_end)

    file_id = uuid.uuid4().hex
    mp3_filename = f"studio_{file_id}.mp3"
    srt_filename = f"subtitles_{file_id}.srt"

    mp3_path = os.path.join(CACHE_DIR, mp3_filename)
    srt_path = os.path.join(CACHE_DIR, srt_filename)

    with open(mp3_path, "wb") as f:
        f.write(bytes(merged_bytes))

    srt_content = generate_srt_subtitles(chunks, chunk_durations)
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    voice_info = next((v for v in VOICE_DATABASE if v["voice_type"] == voice_type), {})
    history_item = {
        "id": file_id,
        "title": voice_info.get("title", "11Labs Voice"),
        "text": text[:60] + ("..." if len(text) > 60 else ""),
        "audio_url": f"/static/cache/{mp3_filename}",
        "srt_url": f"/static/cache/{srt_filename}",
        "chunks": total_chunks,
        "time": time.strftime("%H:%M:%S")
    }
    GENERATION_HISTORY.insert(0, history_item)

    return jsonify({
        "status": "success",
        "audio_url": f"/static/cache/{mp3_filename}",
        "srt_url": f"/static/cache/{srt_filename}",
        "chunks_processed": total_chunks,
        "text_length": len(text)
    })


@app.route("/api/dialogue", methods=["POST"])
def generate_dialogue():
    """Generates multi-speaker podcast / conversation audio."""
    lines = request.json.get("lines", [])
    if not lines:
        return jsonify({"status": "error", "message": "No dialogue script provided."}), 400

    merged_bytes = bytearray()
    chunks_text = []
    durations = []

    for line in lines:
        v_type = line.get("voice_type")
        r_id = line.get("resource_id")
        text = line.get("text", "").strip()
        if not text:
            continue

        res = execute_capcut_tts_chunk(text, v_type, r_id)
        if res:
            audio_bytes, words = res
            merged_bytes.extend(audio_bytes)
            chunks_text.append(f"{line.get('speaker', 'Speaker')}: {text}")
            durations.append(words[-1]["end_time"] if words else 3.0)
        else:
            return jsonify({"status": "error", "message": "Dialogue synthesis failed at speaker line."}), 500

    file_id = uuid.uuid4().hex
    mp3_filename = f"dialogue_{file_id}.mp3"
    srt_filename = f"dialogue_{file_id}.srt"

    with open(os.path.join(CACHE_DIR, mp3_filename), "wb") as f:
        f.write(bytes(merged_bytes))

    with open(os.path.join(CACHE_DIR, srt_filename), "w", encoding="utf-8") as f:
        f.write(generate_srt_subtitles(chunks_text, durations))

    return jsonify({
        "status": "success",
        "audio_url": f"/static/cache/{mp3_filename}",
        "srt_url": f"/static/cache/{srt_filename}"
    })


@app.route("/static/cache/<filename>")
def serve_audio(filename):
    return send_from_directory(CACHE_DIR, filename)

# =====================================================================
# 6. 500X NEXT-GEN STUDIO UI
# =====================================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CapCut AI Voice Studio Ultra Pro</title>
    <!-- Tailwind CSS, Google Fonts & Icons -->
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Plus+Jakarta+Sans:wght@200;300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { font-family: 'Plus Jakarta Sans', sans-serif; }
        h1, h2, h3, h4, .font-space { font-family: 'Space Grotesk', sans-serif; }
        .font-mono { font-family: 'JetBrains Mono', monospace; }
        body { 
            background: radial-gradient(circle at 10% 20%, rgb(6, 10, 20) 0%, rgb(2, 4, 8) 100%);
            color: #e2e8f0; 
        }
        .neon-border { border: 1px solid rgba(16, 185, 129, 0.35); box-shadow: 0 0 35px rgba(16, 185, 129, 0.12); }
        .glass { background: rgba(11, 17, 31, 0.78); backdrop-filter: blur(24px); border: 1px solid rgba(255, 255, 255, 0.07); }
        .active-card { border-color: #10b981 !important; background: linear-gradient(135deg, rgba(16, 185, 129, 0.22), rgba(4, 120, 87, 0.08)) !important; box-shadow: 0 0 30px rgba(16, 185, 129, 0.28); }
        .custom-scroll::-webkit-scrollbar { width: 5px; }
        .custom-scroll::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 20px; }
        .custom-scroll::-webkit-scrollbar-thumb:hover { background: #10b981; }
        .glow-text { text-shadow: 0 0 15px rgba(16, 185, 129, 0.5); }
    </style>
</head>
<body class="min-h-screen flex flex-col items-center p-3 md:p-8">

    <!-- TOP BAR NAVIGATION -->
    <nav class="w-full max-w-7xl flex justify-between items-center mb-8 pb-4 border-b border-slate-800/80">
        <div class="flex items-center space-x-4">
            <div class="w-13 h-13 bg-gradient-to-tr from-emerald-500 via-teal-400 to-cyan-500 rounded-2xl flex items-center justify-center text-slate-950 font-black text-2xl shadow-lg shadow-emerald-500/30 p-2.5">
                <i class="fa-solid fa-wand-magic-sparkles animate-pulse"></i>
            </div>
            <div>
                <h1 class="text-xl md:text-2xl font-extrabold text-white tracking-tight flex items-center">
                    CapCut Voice Studio <span class="ml-2.5 text-[9px] font-bold tracking-widest bg-emerald-500/20 text-emerald-300 px-3 py-1 rounded-full border border-emerald-500/40 glow-text">500X PRO</span>
                </h1>
                <p class="text-xs text-slate-400 font-medium">Parallel ElevenLabs Multithreading • 25-Char Live Previews • Dialogue Studio</p>
            </div>
        </div>
        
        <!-- Studio Mode Switcher -->
        <div class="flex items-center space-x-2 bg-slate-950/90 p-1.5 rounded-2xl border border-slate-800 shadow-xl">
            <button onclick="switchAppMode('studio')" id="tabStudio" class="px-4 py-2 rounded-xl text-xs font-bold bg-emerald-500 text-slate-950 transition shadow-md">Studio Mode</button>
            <button onclick="switchAppMode('dialogue')" id="tabDialogue" class="px-4 py-2 rounded-xl text-xs font-bold text-slate-400 hover:text-white transition">🎙️ Dialogue Studio</button>
        </div>
    </nav>

    <!-- MAIN STUDIO WORKSPACE -->
    <main id="studioWorkspace" class="w-full max-w-7xl grid grid-cols-1 lg:grid-cols-12 gap-8">

        <!-- LEFT BAR: 11LABS VOICE PICKER WITH 25-CHAR PREVIEWS -->
        <section class="lg:col-span-5 flex flex-col space-y-4">
            <div class="flex justify-between items-center">
                <h2 class="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center font-space">
                    <i class="fa-solid fa-microphone-lines mr-2 text-emerald-400"></i> Select 11Labs Voice
                </h2>
                <span id="voiceCount" class="text-xs text-emerald-400 bg-emerald-950/40 px-2.5 py-0.5 rounded-lg border border-emerald-800/50">Loading...</span>
            </div>

            <!-- Category Tabs -->
            <div class="flex items-center space-x-2 overflow-x-auto pb-1 custom-scroll text-xs">
                <button onclick="setCategory('all')" class="cat-tab px-3.5 py-2 rounded-xl bg-emerald-500 text-slate-950 font-extrabold transition">All (12)</button>
                <button onclick="setCategory('female')" class="cat-tab px-3.5 py-2 rounded-xl bg-slate-900/80 hover:bg-slate-800 text-slate-300 transition">👩 Female (4)</button>
                <button onclick="setCategory('male')" class="cat-tab px-3.5 py-2 rounded-xl bg-slate-900/80 hover:bg-slate-800 text-slate-300 transition">👨 Male (8)</button>
            </div>

            <!-- Instant Search Input -->
            <div class="relative">
                <input type="text" id="searchInput" placeholder="Search models (Alex, Noah, Sophia, Liam)..." 
                    class="w-full bg-slate-900/90 border border-slate-800/90 rounded-2xl px-4 py-3.5 pl-11 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 transition shadow-inner">
                <i class="fa-solid fa-magnifying-glass absolute left-4 top-4 text-slate-500 text-sm"></i>
            </div>

            <!-- Voice List Scrollable -->
            <div id="voiceList" class="custom-scroll overflow-y-auto max-h-[540px] space-y-3 pr-2">
                <!-- Javascript will inject cards -->
            </div>
        </section>

        <!-- RIGHT BAR: ADVANCED WRITER, PRESETS & VISUALIZER -->
        <section class="lg:col-span-7 flex flex-col space-y-5">
            
            <!-- Active Model Card -->
            <div class="glass rounded-3xl p-5 flex items-center justify-between shadow-2xl relative overflow-hidden neon-border">
                <div class="flex items-center space-x-4">
                    <img id="activeAvatar" src="" class="w-16 h-15 rounded-2xl object-cover border-2 border-emerald-500 shadow-xl">
                    <div>
                        <div class="flex items-center space-x-2">
                            <h3 id="activeTitle" class="font-bold text-white text-lg font-space">Alex Pro</h3>
                            <span id="activeBadge" class="text-[9px] bg-emerald-500/20 text-emerald-300 px-2.5 py-0.5 rounded-full font-mono border border-emerald-500/30">11Labs V2</span>
                        </div>
                        <p id="activeDesc" class="text-xs text-slate-400 mt-1">Ultra-rich cinematic voice.</p>
                    </div>
                </div>

                <!-- 25-Char Dual Previews -->
                <div class="flex items-center space-x-2">
                    <button onclick="playDualSample('hi')" class="text-xs bg-slate-900 hover:bg-emerald-500 text-slate-200 hover:text-slate-950 font-bold px-3.5 py-2 rounded-xl border border-slate-800 transition flex items-center space-x-1.5 shadow-lg">
                        <span>🇮🇳</span> <span>HI Sample</span>
                    </button>
                    <button onclick="playDualSample('en')" class="text-xs bg-slate-900 hover:bg-emerald-500 text-slate-200 hover:text-slate-950 font-bold px-3.5 py-2 rounded-xl border border-slate-800 transition flex items-center space-x-1.5 shadow-lg">
                        <span>🇺🇸</span> <span>EN Sample</span>
                    </button>
                </div>
            </div>

            <!-- Instant Script Presets -->
            <div class="flex items-center space-x-2 overflow-x-auto pb-1 text-[11px] custom-scroll">
                <span class="text-slate-400 font-bold uppercase font-space text-[10px]">Presets:</span>
                <button onclick="applyPreset('story')" class="bg-slate-900 hover:bg-slate-800 text-slate-300 px-3 py-1.5 rounded-xl border border-slate-800 transition">📖 Hindi Story</button>
                <button onclick="applyPreset('news')" class="bg-slate-900 hover:bg-slate-800 text-slate-300 px-3 py-1.5 rounded-xl border border-slate-800 transition">📰 Tech News</button>
                <button onclick="applyPreset('hook')" class="bg-slate-900 hover:bg-slate-800 text-slate-300 px-3 py-1.5 rounded-xl border border-slate-800 transition">⚡ Viral Hook</button>
                <button onclick="applyPreset('motivational')" class="bg-slate-900 hover:bg-slate-800 text-slate-300 px-3 py-1.5 rounded-xl border border-slate-800 transition">🔥 Motivation</button>
            </div>

            <!-- Workspace Textarea -->
            <div class="glass rounded-3xl p-5 flex flex-col space-y-3.5 shadow-xl">
                <div class="flex justify-between items-center text-xs">
                    <label class="font-bold text-slate-300 flex items-center uppercase tracking-wider font-space">
                        <i class="fa-solid fa-pen-nib text-emerald-400 mr-2"></i> Script Workspace
                    </label>
                    <div class="flex items-center space-x-3 text-slate-400 font-mono text-[11px]">
                        <span id="charCount" class="bg-slate-950/80 px-2 py-0.5 rounded-lg border border-slate-800">0 chars</span>
                        <span id="wordCount" class="bg-slate-950/80 px-2 py-0.5 rounded-lg border border-slate-800">0 words</span>
                        <span id="estTime" class="text-emerald-400 font-bold">~0s</span>
                    </div>
                </div>
                <textarea id="textInput" rows="7" 
                    class="w-full bg-slate-950/80 border border-slate-900 rounded-2xl p-4 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-emerald-500 transition resize-none leading-relaxed"
                    placeholder="Type or paste any text in Hindi, English, etc. Scripts exceeding 380 characters will automatically synthesize in parallel multi-threads and merge seamlessly!"></textarea>
                
                <div id="chunkWarning" class="hidden text-xs text-emerald-400 flex items-center bg-emerald-950/30 p-3 rounded-2xl border border-emerald-900/40">
                    <i class="fa-solid fa-bolt mr-2 animate-bounce"></i> Large Text Detected: Auto-split into <span id="chunkIndicator" class="font-bold mx-1">0</span> parallel segments.
                </div>
            </div>

            <!-- Generate Action Button -->
            <button id="generateBtn" onclick="generateSpeech()" 
                class="w-full bg-gradient-to-r from-emerald-500 via-teal-400 to-cyan-400 hover:from-emerald-400 hover:to-cyan-300 text-slate-950 font-extrabold py-4 px-6 rounded-2xl flex items-center justify-center space-x-2 shadow-lg shadow-emerald-500/20 transition transform active:scale-[0.98]">
                <i class="fa-solid fa-bolt text-lg"></i>
                <span class="text-sm uppercase tracking-widest font-space">Generate Speech + Subtitles (.SRT)</span>
            </button>

            <!-- Multithreaded Progress Monitor -->
            <div id="loadingTracker" class="hidden glass rounded-2xl p-4 flex flex-col space-y-2 border border-emerald-500/30">
                <div class="flex justify-between text-xs font-semibold text-slate-300">
                    <span id="progressText">Processing Chunks in Parallel...</span>
                    <span id="progressPercent">0%</span>
                </div>
                <div class="w-full bg-slate-950 rounded-full h-2.5 overflow-hidden border border-slate-800">
                    <div id="progressBar" class="bg-gradient-to-r from-emerald-500 to-teal-400 h-full w-0 transition-all duration-300"></div>
                </div>
            </div>

            <!-- RESULT STUDIO PLAYER & LIVE VISUALIZER -->
            <div id="resultBox" class="hidden glass rounded-3xl p-6 flex flex-col space-y-4 shadow-2xl border border-emerald-500/35">
                
                <!-- Output Bar -->
                <div class="flex items-center justify-between border-b border-slate-800/80 pb-3">
                    <span class="text-xs text-emerald-400 font-bold uppercase tracking-wider flex items-center font-space">
                        <i class="fa-solid fa-circle-check mr-2 text-emerald-400 animate-bounce"></i> Speech Ready
                    </span>
                    <div class="flex items-center space-x-2">
                        <a id="downloadSrtBtn" href="#" download="subtitles.srt" 
                           class="text-xs bg-slate-900 hover:bg-slate-800 text-slate-300 font-bold px-3 py-2 rounded-xl border border-slate-800 transition flex items-center space-x-1">
                            <i class="fa-solid fa-file-lines"></i>
                            <span>.SRT Subtitles</span>
                        </a>
                        <a id="downloadBtn" href="#" download="speech_audio.mp3" 
                           class="text-xs bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-extrabold px-4 py-2 rounded-xl flex items-center space-x-1.5 transition shadow-lg">
                            <i class="fa-solid fa-download"></i>
                            <span>Download MP3</span>
                        </a>
                    </div>
                </div>

                <!-- Canvas Visualizer -->
                <canvas id="audioVisualizer" height="65" class="w-full bg-slate-950 rounded-2xl border border-slate-900 shadow-inner"></canvas>

                <!-- Audio Controller -->
                <audio id="audioPlayer" controls class="w-full rounded-xl outline-none"></audio>

                <!-- Studio Modulation Controls -->
                <div class="grid grid-cols-2 gap-4 text-xs pt-1">
                    <div class="flex items-center justify-between bg-slate-950/80 p-3 rounded-2xl border border-slate-900">
                        <span class="text-slate-400 font-semibold">Speed:</span>
                        <div class="flex space-x-1.5">
                            <button onclick="setSpeed(0.8)" class="speed-btn px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700">0.8x</button>
                            <button onclick="setSpeed(1.0)" class="speed-btn px-2.5 py-1 rounded-lg bg-emerald-500 text-slate-950 font-bold">1x</button>
                            <button onclick="setSpeed(1.2)" class="speed-btn px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700">1.2x</button>
                            <button onclick="setSpeed(1.5)" class="speed-btn px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700">1.5x</button>
                        </div>
                    </div>
                    <div class="flex items-center justify-between bg-slate-950/80 p-3 rounded-2xl border border-slate-900">
                        <span class="text-slate-400 font-semibold">Volume Booster:</span>
                        <input type="range" id="volumeBooster" min="1" max="2" step="0.1" value="1" onchange="boostVolume(this.value)" class="w-24 accent-emerald-500 cursor-pointer">
                        <span id="volLabel" class="font-mono text-emerald-400 font-bold">100%</span>
                    </div>
                </div>

            </div>

        </section>

    </main>

    <!-- MULTI-SPEAKER DIALOGUE STUDIO WORKSPACE -->
    <main id="dialogueWorkspace" class="hidden w-full max-w-5xl flex flex-col space-y-6">
        <div class="glass rounded-3xl p-6 flex flex-col space-y-5 neon-border shadow-2xl">
            <div class="flex justify-between items-center">
                <div>
                    <h2 class="text-lg font-bold text-white font-space flex items-center">
                        <i class="fa-solid fa-comments text-emerald-400 mr-2"></i> Multi-Speaker Podcast Builder
                    </h2>
                    <p class="text-xs text-slate-400">Create multi-character audio conversations (e.g. Alex vs Sophia conversation).</p>
                </div>
                <button onclick="addDialogueLine()" class="text-xs bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold px-4 py-2.5 rounded-xl transition shadow-lg flex items-center space-x-1.5">
                    <i class="fa-solid fa-plus"></i> <span>Add Line</span>
                </button>
            </div>

            <!-- Dialogue Lines Container -->
            <div id="dialogueContainer" class="space-y-3.5">
                <!-- Lines injected here -->
            </div>

            <button onclick="generateDialogueAudio()" class="w-full bg-gradient-to-r from-emerald-500 to-teal-400 text-slate-950 font-extrabold py-4 rounded-2xl transition shadow-xl font-space">
                Merge & Generate Podcast Episode
            </button>
        </div>
    </main>

    <audio id="samplePlayer" class="hidden"></audio>

    <!-- CLIENT SCRIPT CONTROLLER -->
    <script>
        let allVoices = [];
        let selectedVoice = null;
        let currentCategory = 'all';
        const sampleAudio = document.getElementById("samplePlayer");
        const audioPlayer = document.getElementById("audioPlayer");

        // Web Audio API Visualizer Setup
        let audioCtx, analyser, sourceNode, gainNode;
        function setupVisualizer() {
            if (audioCtx) return;
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            analyser = audioCtx.createAnalyser();
            gainNode = audioCtx.createGain();
            sourceNode = audioCtx.createMediaElementSource(audioPlayer);
            sourceNode.connect(gainNode);
            gainNode.connect(analyser);
            analyser.connect(audioCtx.destination);
            analyser.fftSize = 64;
            drawVisualizer();
        }

        function drawVisualizer() {
            const canvas = document.getElementById("audioVisualizer");
            const ctx = canvas.getContext("2d");
            const bufferLength = analyser.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);

            function render() {
                requestAnimationFrame(render);
                analyser.getByteFrequencyData(dataArray);
                ctx.fillStyle = "#030712";
                ctx.fillRect(0, 0, canvas.width, canvas.height);

                const barWidth = (canvas.width / bufferLength) * 1.8;
                let x = 0;

                for (let i = 0; i < bufferLength; i++) {
                    const barHeight = (dataArray[i] / 255) * canvas.height;
                    ctx.fillStyle = `rgb(16, ${Math.min(255, 185 + dataArray[i])}, 129)`;
                    ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
                    x += barWidth + 2;
                }
            }
            render();
        }

        audioPlayer.onplay = () => {
            setupVisualizer();
            if (audioCtx.state === 'suspended') audioCtx.resume();
        };

        // Fetch Voices
        async function fetchVoices(cat = 'all') {
            document.getElementById("voiceCount").innerText = "Loading...";
            try {
                const res = await fetch(`/api/voices?category=${cat}`);
                const data = await res.json();
                allVoices = data.voices || [];
                renderVoiceList(allVoices);
                document.getElementById("voiceCount").innerText = `${allVoices.length} Voices`;
                if (!selectedVoice && allVoices.length > 0) {
                    selectVoice(allVoices[0]);
                }
            } catch (err) {
                document.getElementById("voiceCount").innerText = "Error";
            }
        }

        function setCategory(cat) {
            currentCategory = cat;
            document.querySelectorAll(".cat-tab").forEach(tab => {
                tab.className = "cat-tab px-3.5 py-2 rounded-xl bg-slate-900/80 hover:bg-slate-800 text-slate-300 transition";
            });
            event.target.className = "cat-tab px-3.5 py-2 rounded-xl bg-emerald-500 text-slate-950 font-extrabold transition";
            fetchVoices(cat);
        }

        function renderVoiceList(voices) {
            const container = document.getElementById("voiceList");
            container.innerHTML = "";

            voices.forEach(v => {
                const isSelected = selectedVoice && selectedVoice.voice_type === v.voice_type;
                const card = document.createElement("div");
                card.className = `cursor-pointer glass ${isSelected ? 'active-card' : ''} hover:border-slate-700/80 p-3.5 rounded-2xl flex items-center justify-between transition-all duration-300`;
                
                card.innerHTML = `
                    <div class="flex items-center space-x-3.5" onclick="selectVoiceById('${v.voice_type}')">
                        <img src="${v.avatar || 'https://via.placeholder.com/150'}" class="w-12 h-12 rounded-xl object-cover border border-slate-800">
                        <div>
                            <div class="flex items-center space-x-1.5">
                                <h4 class="text-sm font-bold text-white">${v.title}</h4>
                                <span class="text-[8px] bg-slate-950 text-emerald-400 px-1.5 py-0.5 rounded border border-emerald-950 uppercase font-mono">${v.lang}</span>
                            </div>
                            <p class="text-xs text-slate-400 font-medium">${v.tag} • ${v.gender}</p>
                        </div>
                    </div>
                    <!-- 25 CHARACTERS DUAL PREVIEW BUTTONS -->
                    <div class="flex items-center space-x-1.5">
                        <button onclick="previewSample(event, '${v.voice_type}', '${v.id}', 'hi', this)" 
                                title="Listen Hindi Demo (~25 chars)"
                                class="text-[10px] font-bold bg-slate-950/80 hover:bg-emerald-500 text-slate-300 hover:text-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800 transition flex items-center space-x-1">
                            <span>🇮🇳</span> <span>HI</span>
                        </button>
                        <button onclick="previewSample(event, '${v.voice_type}', '${v.id}', 'en', this)" 
                                title="Listen English Demo (~25 chars)"
                                class="text-[10px] font-bold bg-slate-950/80 hover:bg-emerald-500 text-slate-300 hover:text-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800 transition flex items-center space-x-1">
                            <span>🇺🇸</span> <span>EN</span>
                        </button>
                    </div>
                `;
                container.appendChild(card);
            });
        }

        function selectVoiceById(vType) {
            const voice = allVoices.find(v => v.voice_type === vType);
            if (voice) selectVoice(voice);
        }

        function selectVoice(v) {
            selectedVoice = v;
            document.getElementById("activeTitle").innerText = v.title;
            document.getElementById("activeDesc").innerText = v.desc || v.tag;
            document.getElementById("activeAvatar").src = v.avatar;
            renderVoiceList(allVoices);
        }

        async function previewSample(event, voice_type, resource_id, lang, btn) {
            if (event) event.stopPropagation();
            const originalText = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin text-[10px]"></i>`;

            try {
                const res = await fetch("/api/preview", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        voice_type: voice_type,
                        resource_id: resource_id,
                        lang: lang
                    })
                });
                const data = await res.json();
                if (data.status === "success") {
                    sampleAudio.src = data.audio_url;
                    sampleAudio.play();
                } else {
                    alert("Preview Error: " + data.message);
                }
            } catch (err) {
                alert("Network error: " + err.message);
            } finally {
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        }

        function playDualSample(lang) {
            if (!selectedVoice) return;
            previewSample(null, selectedVoice.voice_type, selectedVoice.id, lang, event.target);
        }

        // Script Presets
        const presets = {
            story: "एक समय की बात है, पहाड़ों के बीच एक छोटा सा सुंदर गाँव बसा हुआ था। वहाँ के लोग बहुत खुशहाल और मेहनती थे।",
            news: "In today's tech breakdown, artificial intelligence models are advancing at an unprecedented pace worldwide.",
            hook: "Stop scrolling! If you are not using this secret method today, you are missing out on 10x growth!",
            motivational: "संघर्ष जितना कठिन होगा, जीत उतनी ही शानदार होगी। आज का किया गया प्रयास कल का इतिहास बनेगा।"
        };

        function applyPreset(type) {
            textInput.value = presets[type] || "";
            textInput.dispatchEvent(new Event('input'));
        }

        // Live Search
        document.getElementById("searchInput").addEventListener("input", async (e) => {
            const val = e.target.value.trim().toLowerCase();
            const res = await fetch("/api/search", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ query: val })
            });
            const data = await res.json();
            renderVoiceList(data.voices || []);
        });

        // Script length & Estimator
        const textInput = document.getElementById("textInput");
        const charCount = document.getElementById("charCount");
        const wordCount = document.getElementById("wordCount");
        const estTime = document.getElementById("estTime");
        const chunkWarning = document.getElementById("chunkWarning");
        const chunkIndicator = document.getElementById("chunkIndicator");

        textInput.addEventListener("input", () => {
            const len = textInput.value.length;
            const words = textInput.value.trim().split(/\s+/).filter(Boolean).length;
            charCount.innerText = `${len} chars`;
            wordCount.innerText = `${words} words`;
            estTime.innerText = `~${Math.round(words / 2.5)}s`;

            if (len > 370) {
                const parts = Math.ceil(len / 370);
                chunkIndicator.innerText = parts;
                chunkWarning.classList.remove("hidden");
            } else {
                chunkWarning.classList.add("hidden");
            }
        });

        // Parallel Full Speech Synthesis Action
        async function generateSpeech() {
            if (!selectedVoice) return alert("Please select a voice model!");
            const text = textInput.value.trim();
            if (!text) return alert("Please type your script!");

            const btn = document.getElementById("generateBtn");
            const originalHtml = btn.innerHTML;
            
            btn.disabled = true;
            btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-lg mr-2"></i> Synthesizing Parallel Chunks...`;
            
            document.getElementById("resultBox").classList.add("hidden");
            const loadingTracker = document.getElementById("loadingTracker");
            const progressBar = document.getElementById("progressBar");
            const progressText = document.getElementById("progressText");
            const progressPercent = document.getElementById("progressPercent");

            loadingTracker.classList.remove("hidden");
            let progress = 0;
            const progressInterval = setInterval(() => {
                if (progress < 90) {
                    progress += 12;
                    progressBar.style.width = `${progress}%`;
                    progressPercent.innerText = `${Math.round(progress)}%`;
                }
            }, 400);

            try {
                const res = await fetch("/api/generate", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        text: text,
                        voice_type: selectedVoice.voice_type,
                        resource_id: selectedVoice.id
                    })
                });

                const data = await res.json();
                clearInterval(progressInterval);

                if (data.status === "success") {
                    progressBar.style.width = "100%";
                    progressPercent.innerText = "100%";
                    progressText.innerText = "Audio & Subtitles Generated!";

                    setTimeout(() => {
                        loadingTracker.classList.add("hidden");
                        audioPlayer.src = data.audio_url;
                        document.getElementById("downloadBtn").href = data.audio_url;
                        document.getElementById("downloadSrtBtn").href = data.srt_url;
                        document.getElementById("resultBox").classList.remove("hidden");
                        audioPlayer.play();
                    }, 400);
                } else {
                    alert("TTS Error: " + data.message);
                    loadingTracker.classList.add("hidden");
                }
            } catch (err) {
                alert("Request error: " + err.message);
                loadingTracker.classList.add("hidden");
                clearInterval(progressInterval);
            } finally {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            }
        }

        // Speed & Audio Modulation Helpers
        function setSpeed(rate) {
            audioPlayer.playbackRate = rate;
            document.querySelectorAll(".speed-btn").forEach(b => b.className = "speed-btn px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700");
            event.target.className = "speed-btn px-2.5 py-1 rounded-lg bg-emerald-500 text-slate-950 font-bold";
        }

        function boostVolume(val) {
            setupVisualizer();
            gainNode.gain.value = val;
            document.getElementById("volLabel").innerText = `${Math.round(val * 100)}%`;
        }

        // Dialogue Mode Builder
        function switchAppMode(mode) {
            if (mode === 'studio') {
                document.getElementById("studioWorkspace").classList.remove("hidden");
                document.getElementById("dialogueWorkspace").classList.add("hidden");
                document.getElementById("tabStudio").className = "px-4 py-2 rounded-xl text-xs font-bold bg-emerald-500 text-slate-950 transition shadow-md";
                document.getElementById("tabDialogue").className = "px-4 py-2 rounded-xl text-xs font-bold text-slate-400 hover:text-white transition";
            } else {
                document.getElementById("studioWorkspace").classList.add("hidden");
                document.getElementById("dialogueWorkspace").classList.remove("hidden");
                document.getElementById("tabDialogue").className = "px-4 py-2 rounded-xl text-xs font-bold bg-emerald-500 text-slate-950 transition shadow-md";
                document.getElementById("tabStudio").className = "px-4 py-2 rounded-xl text-xs font-bold text-slate-400 hover:text-white transition";
                if (document.getElementById("dialogueContainer").children.length === 0) {
                    addDialogueLine("Alex Pro (Flagship)", "iDJbhuGTR9N7lXjELodg", "7374727433896858128", "Hey Sophia! Welcome to our new AI podcast episode.");
                    addDialogueLine("Sophia Emotional Narration", "mkRaeFYOxJgf5w1emssQ", "7579091304517291280", "Thanks Alex! I am super excited to discuss technology today.");
                }
            }
        }

        function addDialogueLine(defSpeaker, defVoice, defId, defText = "") {
            const container = document.getElementById("dialogueContainer");
            const div = document.createElement("div");
            div.className = "dialogue-row glass p-3.5 rounded-2xl flex items-center space-x-3 border border-slate-800/80 shadow-md";
            div.innerHTML = `
                <select class="speaker-select bg-slate-950 text-xs text-white border border-slate-800 p-2.5 rounded-xl outline-none">
                    ${allVoices.map(v => `<option value="${v.voice_type}" data-id="${v.id}" ${v.title === defSpeaker ? 'selected' : ''}>${v.title}</option>`).join('')}
                </select>
                <input type="text" class="speaker-text flex-1 bg-slate-950 border border-slate-800 text-xs text-slate-200 p-2.5 rounded-xl focus:outline-none focus:border-emerald-500" placeholder="Dialogue line..." value="${defText}">
                <button onclick="this.parentElement.remove()" class="text-slate-500 hover:text-rose-400 text-sm px-2"><i class="fa-solid fa-trash"></i></button>
            `;
            container.appendChild(div);
        }

        async function generateDialogueAudio() {
            const rows = document.querySelectorAll(".dialogue-row");
            const lines = [];
            rows.forEach(r => {
                const sel = r.querySelector(".speaker-select");
                const opt = sel.options[sel.selectedIndex];
                lines.push({
                    speaker: opt.text,
                    voice_type: sel.value,
                    resource_id: opt.getAttribute("data-id"),
                    text: r.querySelector(".speaker-text").value.trim()
                });
            });

            if (lines.length === 0) return alert("Add at least one line.");
            const res = await fetch("/api/dialogue", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ lines })
            });
            const data = await res.json();
            if (data.status === "success") {
                switchAppMode('studio');
                audioPlayer.src = data.audio_url;
                document.getElementById("downloadBtn").href = data.audio_url;
                document.getElementById("downloadSrtBtn").href = data.srt_url;
                document.getElementById("resultBox").classList.remove("hidden");
                audioPlayer.play();
            } else {
                alert("Dialogue Error: " + data.message);
            }
        }

        fetchVoices('all');
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == "__main__":
    print("[+] CapCut 500X Ultra Pro Audio Studio running at: http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)