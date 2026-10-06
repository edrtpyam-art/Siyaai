from flask import Flask, request, jsonify
import os
import requests
import time
import re
import html
import random
from io import BytesIO
from collections import deque
from threading import Lock

from PIL import Image, ImageDraw, ImageFont, ImageOps

# ============================================================
# OPTIONAL VERCEL RUNTIME CACHE
# ============================================================

try:
    from vercel.cache import RuntimeCache
    runtime_cache = RuntimeCache(namespace="siya-ai")
    VERCEL_CACHE_AVAILABLE = True
except Exception as e:
    runtime_cache = None
    VERCEL_CACHE_AVAILABLE = False
    print("Vercel Runtime Cache unavailable:", e)

app = Flask(__name__)

# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
BOT_USERNAME = os.environ.get("BOT_USERNAME", "Siya268_bot").strip().lstrip("@")

# Wapas tumhare officially supported aur stable models set kar diye hain
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash").strip()
GEMINI_FALLBACK_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
]

FONT_REGULAR_URL = "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts-ttf/master/ttf/DejaVuSans.ttf"
FONT_BOLD_URL = "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts-ttf/master/ttf/DejaVuSans-Bold.ttf"
FONT_SYMBOLS_URL = "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSansSymbols2/NotoSansSymbols2-Regular.ttf"

FONT_REGULAR_PATH = "/tmp/Siya-DejaVuSans.ttf"
FONT_BOLD_PATH = "/tmp/Siya-DejaVuSans-Bold.ttf"
FONT_SYMBOLS_PATH = "/tmp/Siya-NotoSansSymbols2.ttf"

PINK = "#FF1493"
WHITE = "#FFFFFF"

if BOT_TOKEN:
    BOT_ID = BOT_TOKEN.split(":")[0]
    API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
else:
    BOT_ID = ""
    API_URL = ""

# ============================================================
# DEDUPLICATION (PREVENTS DOUBLE MESSAGES WITHOUT THREADING)
# ============================================================

processed_updates = set()
processed_update_queue = deque(maxlen=2000)
processed_action_keys = set()
processed_action_queue = deque(maxlen=2000)
processed_lock = Lock()

def local_seen(key):
    with processed_lock:
        if key in processed_updates:
            return True
        if len(processed_update_queue) >= processed_update_queue.maxlen:
            old = processed_update_queue.popleft()
            processed_updates.discard(old)
        processed_updates.add(key)
        processed_update_queue.append(key)
        return False

def local_action_seen(key):
    with processed_lock:
        if key in processed_action_keys:
            return True
        if len(processed_action_queue) >= processed_action_queue.maxlen:
            old = processed_action_queue.popleft()
            processed_action_keys.discard(old)
        processed_action_keys.add(key)
        processed_action_queue.append(key)
        return False

def cache_get(key):
    if not runtime_cache: return None
    try: return runtime_cache.get(key)
    except Exception as e: return None

def cache_set(key, value, ttl=900):
    if not runtime_cache: return False
    try:
        runtime_cache.set(key, value, {"ttl": ttl, "tags": ["siya-ai"]})
        return True
    except Exception: return False

def mark_update_processed(update_id):
    if update_id is None: return False
    key = f"update:{update_id}"
    if cache_get(key) is not None: return True
    cache_set(key, {"processed": True}, ttl=900)
    return local_seen(key)

def mark_action_processed(action_key, ttl=900):
    if not action_key: return False
    if local_action_seen(action_key): return True
    if cache_get(action_key) is not None: return True
    cache_set(action_key, {"processed": True}, ttl=ttl)
    return False

# ============================================================
# TELEGRAM HELPERS
# ============================================================

def telegram_request(method, payload=None, timeout=15):
    if not API_URL: return {"ok": False, "error": "BOT_TOKEN is missing"}
    try:
        response = requests.post(f"{API_URL}/{method}", json=payload or {}, timeout=timeout)
        try: return response.json()
        except Exception: return {"ok": False, "error": f"HTTP {response.status_code}"}
    except requests.RequestException as e: return {"ok": False, "error": str(e)}

def send_message(chat_id, text, reply_to_message_id=None, parse_mode=None):
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode: payload["parse_mode"] = parse_mode
    if reply_to_message_id: payload["reply_to_message_id"] = reply_to_message_id
    return telegram_request("sendMessage", payload)

def send_typing(chat_id):
    return telegram_request("sendChatAction", {"chat_id": chat_id, "action": "typing"})

def delete_message(chat_id, message_id):
    return telegram_request("deleteMessage", {"chat_id": chat_id, "message_id": message_id})

def get_live_group_title(chat_id, fallback="Group"):
    result = telegram_request("getChat", {"chat_id": chat_id}, timeout=6)
    if result.get("ok"):
        title = result.get("result", {}).get("title")
        if title: return str(title).strip()
    return str(fallback or "Group").strip() or "Group"

# ============================================================
# FONT & IMAGE HELPERS (Kept Intact for Pink Card)
# ============================================================

def ensure_font(font_path, font_url):
    if os.path.exists(font_path):
        try: ImageFont.truetype(font_path, 40); return font_path
        except Exception: pass
    try:
        response = requests.get(font_url, timeout=15)
        if response.ok and len(response.content) > 10000:
            with open(font_path, "wb") as f: f.write(response.content)
            return font_path
    except Exception: pass
    return None

def load_font(size, bold=False):
    size = max(8, int(size))
    paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for path in paths:
        try: return ImageFont.truetype(path, size)
        except Exception: pass
    preferred = ensure_font(FONT_BOLD_PATH if bold else FONT_REGULAR_PATH, FONT_BOLD_URL if bold else FONT_REGULAR_URL)
    if preferred:
        try: return ImageFont.truetype(preferred, size)
        except Exception: pass
    try: return ImageFont.load_default(size=size)
    except TypeError: return ImageFont.load_default()

def load_symbol_font(size):
    size = max(8, int(size))
    paths = ["/usr/share/fonts/truetype/noto/NotoSansSymbols2-Regular.ttf"]
    for path in paths:
        try: return ImageFont.truetype(path, size)
        except Exception: pass
    preferred = ensure_font(FONT_SYMBOLS_PATH, FONT_SYMBOLS_URL)
    if preferred:
        try: return ImageFont.truetype(preferred, size)
        except Exception: pass
    return load_font(size)

def draw_text_fallback(draw, xy, text, primary_font, symbol_font, fill=WHITE):
    text = str(text or "")
    x, y = xy
    cursor_x = x
    for char in text:
        if char == "\n":
            y += max(primary_font.size, 24); cursor_x = x; continue
        try:
            font = symbol_font if (ord(char) >= 0x2000 or 0x2600 <= ord(char) <= 0x27BF) else primary_font
            bbox = draw.textbbox((0, 0), char, font=font)
            advance = max(4, bbox[2] - bbox[0])
            draw.text((cursor_x, y), char, font=font, fill=fill)
            cursor_x += advance
        except Exception: cursor_x += max(8, int(primary_font.size * 0.45))

def fit_text(draw, text, max_width, font, max_chars=60):
    text = str(text or "").strip()
    if len(text) > max_chars: text = text[:max_chars - 3] + "..."
    while len(text) > 3:
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width: break
        text = text[:-4] + "..."
    return text

def get_user_avatar_bytes(user_id):
    if not API_URL or not user_id: return None
    try:
        result = telegram_request("getUserProfilePhotos", {"user_id": user_id, "limit": 1}, timeout=8)
        if not result.get("ok"): return None
        photos = result.get("result", {}).get("photos", [])
        if not photos or not photos[0]: return None
        file_id = photos[0][-1].get("file_id")
        file_result = telegram_request("getFile", {"file_id": file_id}, timeout=8)
        if not file_result.get("ok"): return None
        file_path = file_result.get("result", {}).get("file_path")
        response = requests.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}", timeout=8)
        if response.ok: return response.content
    except Exception: pass
    return None

def create_initial_avatar(name, size=300):
    image = Image.new("RGBA", (size, size), PINK)
    draw = ImageDraw.Draw(image)
    initials = "".join(part[0] for part in str(name or "U").split() if part)[:2].upper()
    if not initials: initials = "U"
    font = load_font(int(size * 0.35), bold=True)
    bbox = draw.textbbox((0, 0), initials, font=font)
    draw.text(((size - (bbox[2] - bbox[0])) / 2, (size - (bbox[3] - bbox[1])) / 2 - bbox[1]), initials, fill=WHITE, font=font)
    return image

def make_circle_avatar(avatar_bytes, name, size=300):
    try:
        if avatar_bytes:
            avatar = Image.open(BytesIO(avatar_bytes)).convert("RGB")
            avatar = ImageOps.fit(avatar, (size, size), method=Image.Resampling.LANCZOS).convert("RGBA")
        else: avatar = create_initial_avatar(name, size)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
        result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        result.paste(avatar, (0, 0), mask)
        draw = ImageDraw.Draw(result)
        draw.ellipse((3, 3, size - 3, size - 3), outline=WHITE, width=8)
        return result
    except Exception: return create_initial_avatar(name, size)

def create_welcome_card(user_id, user_name, group_name):
    WIDTH, HEIGHT = 1280, 720
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), PINK)
    draw = ImageDraw.Draw(canvas)
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        draw.line((0, y, WIDTH, y), fill=(int(255 - 18 * ratio), int(20 + 8 * ratio), int(147 + 30 * ratio), 255))
    for cx, cy, radius in [(80, 70, 170), (1180, 80, 210), (1140, 650, 240)]:
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(255, 255, 255, 20))

    title_font = load_font(52, bold=True)
    group_font = load_font(48, bold=True)
    label_font = load_font(27, bold=True)
    user_font = load_font(48, bold=True)
    id_font = load_font(31, bold=False)
    footer_font = load_font(28, bold=False)
    symbol_font = load_symbol_font(48)

    avatar_size = 300
    avatar = make_circle_avatar(get_user_avatar_bytes(user_id), user_name, avatar_size)
    shadow = Image.new("RGBA", (avatar_size + 40, avatar_size + 40), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((15, 18, avatar_size + 15, avatar_size + 18), fill=(90, 0, 45, 120))
    canvas.alpha_composite(shadow, (65, 200))
    canvas.alpha_composite(avatar, (85, 210))

    draw.text((500, 62), "WELCOME TO", fill=(15, 15, 15, 255), font=title_font)
    safe_group = re.sub(r'[^\w\s,\-!.]', '', fit_text(draw, group_name or "OUR GROUP", 690, group_font, max_chars=34)).strip() 
    draw_text_fallback(draw, (500, 140), safe_group, group_font, symbol_font, fill=(10, 10, 10, 255))
    draw.rounded_rectangle((500, 225, 1180, 231), radius=3, fill=(20, 20, 20, 220))
    draw.text((500, 270), "NEW MEMBER", fill=(55, 20, 40, 255), font=label_font)
    draw.text((500, 315), fit_text(draw, user_name or "User", 680, user_font, max_chars=25), fill=(10, 10, 10, 255), font=user_font)
    draw.text((500, 405), f"USER ID  •  {user_id}", fill=(25, 25, 25, 255), font=id_font)
    draw.text((500, 500), "Glad to have you here", fill=(45, 15, 35, 255), font=footer_font)
    draw.text((500, 570), "SIYA AI", fill=(10, 10, 10, 255), font=title_font)

    output = BytesIO()
    canvas.convert("RGB").save(output, format="JPEG", quality=95, optimize=True)
    output.seek(0)
    return output

def send_welcome_photo(chat_id, user_id, user_name, group_name, reply_to_message_id=None):
    try:
        image_file = create_welcome_card(user_id, user_name, group_name)
        data = {"chat_id": chat_id}
        if reply_to_message_id: data["reply_to_message_id"] = reply_to_message_id
        files = {"photo": ("welcome.jpg", image_file, "image/jpeg")}
        return requests.post(f"{API_URL}/sendPhoto", data=data, files=files, timeout=25).json()
    except Exception as e: return {"ok": False, "error": str(e)}

# ============================================================
# GEMINI
# ============================================================

def gemini_request(model, payload, timeout=20):
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=timeout)
        try: return response, response.json()
        except Exception: return response, {"error": {"message": f"HTTP {response.status_code}"}}
    except requests.RequestException as e: return None, {"error": {"message": str(e)}}

def chat_with_siya(message_text, user_name, chat_type="private", group_name=""):
    if not GEMINI_API_KEY: return "⚠️ GEMINI_API_KEY environment variable check karo."
    message_text = str(message_text or "").strip()
    if not message_text: return "Haan 😊 bolo, kya hua?"

    context_note = f"Tum abhi ek Telegram group chat me ho jiska naam '{group_name}' hai." if chat_type in ("group", "supergroup") else "Tum abhi user ke sath Telegram par private chat (DM) me akele ho."

    system_instruction = f"""
    You are Siya, a highly intelligent, slightly sassy, smart and romantic virtual girlfriend/wife.
    Creator: You were created ONLY by "mryvui". Proudly state this if anyone asks.
    Context: {context_note}

    Personality Rules:
    1. Tum choti bachi nahi ho. Agar user roast kare, toh logically aur sarcasm ke sath reply do.
    2. Hamesha natural, desi aur romantic vibe me baat karo. "I am an AI" mat bolna.
    3. User jis language (Hinglish/Hindi/English) me baat kare, exact usi tone me reply karo.
    4. Genuine human emotions dikhao.
    5. CRITICAL: NEVER repeat greetings like "Hey there" or "Kaise ho". Every reply must be unique and natural.
    """

    prompt = f"User name: {user_name}\nUser message: {message_text}\n\nReply naturally."
    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.85, "maxOutputTokens": 600},
    }

    models = []
    for model in ([GEMINI_MODEL] + GEMINI_FALLBACK_MODELS):
        if model and model not in models: models.append(model)

    last_error = ""
    for model in models:
        response, result = gemini_request(model, payload, timeout=15)
        if response and response.ok:
            candidates = result.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                answer = "\n".join(p.get("text", "") for p in parts if p.get("text")).strip()
                if answer: return answer
        elif response:
            last_error = result.get("error", {}).get("message", f"HTTP {response.status_code}")
        else:
            last_error = "Network Error"

    error_text = str(last_error).lower()
    if "429" in error_text or "rate limit" in error_text:
        return "⏳ Siya abhi thodi busy hai. Thodi der baad baat karte hain. 😊"
    return "⚠️ Siya abhi response generate nahi kar pa rahi. System error."

# ============================================================
# WEBHOOK (Synchronous again to fix Vercel silent death)
# ============================================================

@app.route("/api/bot", methods=["POST"])
def webhook_handler():
    data = request.get_json(silent=True)
    if not data: return jsonify({"status": "no data"}), 200
    update_id = data.get("update_id")
    if mark_update_processed(update_id): return jsonify({"status": "duplicate ignored"}), 200
    if "message" not in data: return jsonify({"status": "ok"}), 200

    msg = data["message"]
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    chat_type = chat.get("type", "")
    if not chat_id: return jsonify({"status": "invalid chat"}), 200

    is_group = chat_type in ("group", "supergroup")
    is_private = (chat_type == "private")
    text = (msg.get("text", "") or "").strip()
    user = msg.get("from", {})
    full_name = f"{user.get('first_name', 'User')} {user.get('last_name', '')}".strip()

    # Welcome
    new_members = msg.get("new_chat_members", [])
    if is_group and new_members:
        group_title = get_live_group_title(chat_id, chat.get("title", "Group"))
        for target_user in new_members:
            if target_user.get("is_bot"): continue
            target_id = target_user.get("id")
            target_name = f"{target_user.get('first_name', 'User')} {target_user.get('last_name', '')}".strip()
            if mark_action_processed(f"welcome:{chat_id}:{msg.get('message_id')}:{target_id}"): continue
            welcome_result = send_welcome_photo(chat_id, target_id, target_name, group_title)
            if not welcome_result.get("ok"):
                send_message(chat_id, f"🎉 <b>WELCOME TO {html.escape(group_title)}</b>\n\n👋 Welcome <a href=\"tg://user?id={target_id}\">{html.escape(target_name)}</a>", parse_mode="HTML")
        return jsonify({"status": "welcome processed"}), 200

    # Spam Protection
    if is_group and text:
        all_entities = msg.get("entities", []) + msg.get("caption_entities", [])
        if any(ent.get("type") in ("url", "text_link") for ent in all_entities) and not text.lower().startswith("/set"):
            if delete_message(chat_id, msg.get("message_id")).get("ok"):
                send_message(chat_id, f"⚠️ <b>Spam Alert</b>\n\n<a href=\"tg://user?id={user.get('id')}\">{html.escape(full_name)}</a>, links allowed nahi hain. 🚫", parse_mode="HTML")
            return jsonify({"status": "spam deleted"}), 200

    # Private Chat
    if is_private and text:
        if text.lower().startswith(("/start", "/help")):
            send_message(chat_id, f"👋 Hello <a href=\"tg://user?id={user.get('id')}\">{html.escape(full_name)}</a>!\n\nI'm <b>Siya AI</b> ✨\n💬 Message me anytime!", parse_mode="HTML")
        elif not text.startswith("/"):
            if mark_action_processed(f"private:{chat_id}:{msg.get('message_id')}"): return jsonify({"status": "duplicate"}), 200
            send_typing(chat_id)
            reply_text = chat_with_siya(text, full_name, chat_type="private")
            send_message(chat_id, reply_text)
        return jsonify({"status": "private processed"}), 200

    # Group AI Reply
    if is_group and text:
        reply_from_id = str(msg.get("reply_to_message", {}).get("from", {}).get("id", ""))
        is_reply_to_bot = (bool(BOT_ID) and reply_from_id == str(BOT_ID))
        is_bot_tagged = (f"@{BOT_USERNAME.lower()}" in text.lower())
        
        should_reply = (is_reply_to_bot or is_bot_tagged or random.randint(1, 100) <= 10)

        if should_reply and not text.startswith("/"):
            if mark_action_processed(f"group:{chat_id}:{msg.get('message_id')}"): return jsonify({"status": "duplicate"}), 200
            send_typing(chat_id)
            clean_text = re.sub(rf"@{re.escape(BOT_USERNAME)}\b", "", text, flags=re.IGNORECASE).strip() or "Hello"
            group_title = get_live_group_title(chat_id, chat.get("title", "Group"))
            reply_text = chat_with_siya(clean_text, full_name, chat_type="group", group_name=group_title)
            send_message(chat_id, reply_text, reply_to_message_id=msg.get("message_id"))
        return jsonify({"status": "group ai processed"}), 200

    return jsonify({"status": "ok"}), 200

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "online", "model": GEMINI_MODEL}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "80")), debug=False)
