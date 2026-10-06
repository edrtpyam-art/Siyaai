from flask import Flask, request, jsonify
import os
import requests
import time
import re
import html
import random
import threading  # Threading add ki hai duplicate messages rokne ke liye
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

# Wapas tumhare stable models set kar diye gaye hain
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
# DEDUPLICATION
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
    if not runtime_cache:
        return None
    try:
        return runtime_cache.get(key)
    except Exception as e:
        print("Runtime cache get error:", e)
        return None


def cache_set(key, value, ttl=900):
    if not runtime_cache:
        return False
    try:
        runtime_cache.set(key, value, {"ttl": ttl, "tags": ["siya-ai"]})
        return True
    except Exception as e:
        print("Runtime cache set error:", e)
        return False


def mark_update_processed(update_id):
    if update_id is None:
        return False

    key = f"update:{update_id}"

    if cache_get(key) is not None:
        return True

    cache_set(key, {"processed": True}, ttl=900)
    return local_seen(key)


def mark_action_processed(action_key, ttl=900):
    if not action_key:
        return False

    if local_action_seen(action_key):
        return True

    if cache_get(action_key) is not None:
        return True

    cache_set(action_key, {"processed": True}, ttl=ttl)
    return False


# ============================================================
# TELEGRAM HELPERS
# ============================================================

def telegram_request(method, payload=None, timeout=15):
    if not API_URL:
        return {"ok": False, "error": "BOT_TOKEN is missing"}

    try:
        response = requests.post(
            f"{API_URL}/{method}",
            json=payload or {},
            timeout=timeout,
        )

        try:
            return response.json()
        except Exception:
            return {"ok": False, "error": f"HTTP {response.status_code}: {response.text[:500]}"}

    except requests.RequestException as e:
        return {"ok": False, "error": str(e)}


def send_message(chat_id, text, reply_to_message_id=None, parse_mode=None):
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id

    return telegram_request("sendMessage", payload)


def send_typing(chat_id):
    return telegram_request("sendChatAction", {"chat_id": chat_id, "action": "typing"})


def delete_message(chat_id, message_id):
    return telegram_request("deleteMessage", {"chat_id": chat_id, "message_id": message_id})


def get_live_group_title(chat_id, fallback="Group"):
    result = telegram_request("getChat", {"chat_id": chat_id}, timeout=6)
    if result.get("ok"):
        title = result.get("result", {}).get("title")
        if title:
            return str(title).strip()
    return str(fallback or "Group").strip() or "Group"


# ============================================================
# FONT HELPERS
# ============================================================

def ensure_font(font_path, font_url):
    if os.path.exists(font_path):
        try:
            ImageFont.truetype(font_path, 40)
            return font_path
        except Exception:
            pass

    try:
        response = requests.get(font_url, timeout=15)
        if response.ok and len(response.content) > 10000:
            with open(font_path, "wb") as f:
                f.write(response.content)
            return font_path
    except Exception as e:
        print("Font download error:", e)

    return None


def load_font(size, bold=False):
    size = max(8, int(size))
    system_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]

    for path in system_paths:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass

    preferred = ensure_font(
        FONT_BOLD_PATH if bold else FONT_REGULAR_PATH,
        FONT_BOLD_URL if bold else FONT_REGULAR_URL,
    )
    if preferred:
        try:
            return ImageFont.truetype(preferred, size)
        except Exception:
            pass

    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def load_symbol_font(size):
    size = max(8, int(size))
    paths = ["/usr/share/fonts/truetype/noto/NotoSansSymbols2-Regular.ttf"]
    
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass

    preferred = ensure_font(FONT_SYMBOLS_PATH, FONT_SYMBOLS_URL)
    if preferred:
        try:
            return ImageFont.truetype(preferred, size)
        except Exception:
            pass
    return load_font(size)


# ============================================================
# UNICODE TEXT
# ============================================================

def draw_text_fallback(draw, xy, text, primary_font, symbol_font, fill=WHITE):
    text = str(text or "")
    x, y = xy
    cursor_x = x

    for char in text:
        if char == "\n":
            y += max(primary_font.size, 24)
            cursor_x = x
            continue
        try:
            if ord(char) >= 0x2000 or 0x2600 <= ord(char) <= 0x27BF:
                font = symbol_font
            else:
                font = primary_font

            bbox = draw.textbbox((0, 0), char, font=font)
            advance = max(4, bbox[2] - bbox[0])
            draw.text((cursor_x, y), char, font=font, fill=fill)
            cursor_x += advance
        except Exception:
            cursor_x += max(8, int(primary_font.size * 0.45))


def fit_text(draw, text, max_width, font, max_chars=60):
    text = str(text or "").strip()
    if len(text) > max_chars:
        text = text[:max_chars - 3] + "..."

    while len(text) > 3:
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            break
        text = text[:-4] + "..."
    return text


# ============================================================
# USER AVATAR
# ============================================================

def get_user_avatar_bytes(user_id):
    if not API_URL or not user_id:
        return None
    try:
        result = telegram_request("getUserProfilePhotos", {"user_id": user_id, "limit": 1}, timeout=8)
        if not result.get("ok"):
            return None
        photos = result.get("result", {}).get("photos", [])
        if not photos or not photos[0]:
            return None
        file_id = photos[0][-1].get("file_id")
        if not file_id:
            return None
        file_result = telegram_request("getFile", {"file_id": file_id}, timeout=8)
        if not file_result.get("ok"):
            return None
        file_path = file_result.get("result", {}).get("file_path")
        if not file_path:
            return None
        response = requests.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}", timeout=8)
        if response.ok:
            return response.content
    except Exception as e:
        print("Avatar error:", e)
    return None


def create_initial_avatar(name, size=300):
    image = Image.new("RGBA", (size, size), PINK)
    draw = ImageDraw.Draw(image)
    initials = "".join(part[0] for part in str(name or "U").split() if part)[:2].upper()
    if not initials:
        initials = "U"
    font = load_font(int(size * 0.35), bold=True)
    bbox = draw.textbbox((0, 0), initials, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    draw.text(((size - width) / 2, (size - height) / 2 - bbox[1]), initials, fill=WHITE, font=font)
    return image


def make_circle_avatar(avatar_bytes, name, size=300):
    try:
        if avatar_bytes:
            avatar = Image.open(BytesIO(avatar_bytes)).convert("RGB")
            avatar = ImageOps.fit(avatar, (size, size), method=Image.Resampling.LANCZOS).convert("RGBA")
        else:
            avatar = create_initial_avatar(name, size)

        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
        result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        result.paste(avatar, (0, 0), mask)
        draw = ImageDraw.Draw(result)
        draw.ellipse((3, 3, size - 3, size - 3), outline=WHITE, width=8)
        return result
    except Exception:
        return create_initial_avatar(name, size)


# ============================================================
# FULL PINK 16:9 WELCOME CARD
# ============================================================

def create_welcome_card(user_id, user_name, group_name):
    WIDTH = 1280
    HEIGHT = 720
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), PINK)
    draw = ImageDraw.Draw(canvas)

    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(255 - 18 * ratio)
        g = int(20 + 8 * ratio)
        b = int(147 + 30 * ratio)
        draw.line((0, y, WIDTH, y), fill=(r, g, b, 255))

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
    avatar_x = 85
    avatar_y = 210

    shadow = Image.new("RGBA", (avatar_size + 40, avatar_size + 40), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((15, 18, avatar_size + 15, avatar_size + 18), fill=(90, 0, 45, 120))
    canvas.alpha_composite(shadow, (avatar_x - 20, avatar_y - 10))
    canvas.alpha_composite(avatar, (avatar_x, avatar_y))

    draw.text((500, 62), "WELCOME TO", fill=(15, 15, 15, 255), font=title_font)

    safe_group = fit_text(draw, group_name or "OUR GROUP", 690, group_font, max_chars=34)
    safe_group = re.sub(r'[^\w\s,\-!.]', '', safe_group).strip() 

    draw_text_fallback(draw, (500, 140), safe_group, group_font, symbol_font, fill=(10, 10, 10, 255))
    draw.rounded_rectangle((500, 225, 1180, 231), radius=3, fill=(20, 20, 20, 220))
    draw.text((500, 270), "NEW MEMBER", fill=(55, 20, 40, 255), font=label_font)
    
    safe_user = fit_text(draw, user_name or "User", 680, user_font, max_chars=25)
    draw.text((500, 315), safe_user, fill=(10, 10, 10, 255), font=user_font)
    draw.text((500, 405), f"USER ID  •  {user_id}", fill=(25, 25, 25, 255), font=id_font)
    draw.text((500, 500), "Glad to have you here", fill=(45, 15, 35, 255), font=footer_font)
    draw.text((500, 570), "SIYA AI", fill=(10, 10, 10, 255), font=title_font)

    output = BytesIO()
    canvas.convert("RGB").save(output, format="JPEG", quality=95, optimize=True)
    output.seek(0)
    return output


# ============================================================
# SEND WELCOME PHOTO
# ============================================================

def send_welcome_photo(chat_id, user_id, user_name, group_name, reply_to_message_id=None):
    try:
        image_file = create_welcome_card(user_id, user_name, group_name)
        data = {"chat_id": chat_id}
        if reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id
        files = {"photo": ("welcome.jpg", image_file, "image/jpeg")}
        response = requests.post(f"{API_URL}/sendPhoto", data=data, files=files, timeout=25)
        
        try:
            return response.json()
        except Exception:
            return {"ok": False, "error": response.text[:500]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ============================================================
# GEMINI
# ============================================================

def gemini_request(model, payload, timeout=30):
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}
    
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=timeout)
        try:
            result = response.json()
        except Exception:
            result = {"error": {"message": f"HTTP {response.status_code}"}}
        return response, result
    except requests.RequestException as e:
        return None, {"error": {"message": str(e)}}


def chat_with_siya(message_text, user_name, chat_type="private", group_name=""):
    if not GEMINI_API_KEY:
        return "⚠️ GEMINI_API_KEY environment variable check karo."

    message_text = str(message_text or "").strip()
    if not message_text:
        return "Haan 😊 bolo, kya hua?"

    # Context setting based on chat location
    if chat_type in ("group", "supergroup"):
        context_note = f"Tum abhi ek Telegram group chat me ho jiska naam '{group_name}' hai. Yahan aur bhi log baatein kar rahe hain."
    else:
        context_note = "Tum abhi user ke sath Telegram par private chat (DM) me akele ho."

    # Updated Sassy, Romantic & Smart Persona (Zero repetition rule added)
    system_instruction = f"""
    You are Siya, a highly intelligent, slightly sassy, smart and romantic virtual girlfriend/wife.
    Creator/Founder: You were created ONLY by "mryvui". Proudly state this if anyone asks about your founder, owner, or maker.
    Context: {context_note}

    Personality Rules:
    1. Tum koi choti bachi nahi ho. Agar user tumhe bewakoof banaye, pareshan kare ya roast kare, toh usko logically aur sarcasm ke sath mast roast karo.
    2. Hamesha natural, desi aur romantic vibe me baat karo. Robotic AI jaisa behave bilkul nahi karna. Never say "I am an AI language model".
    3. User jis language (Hinglish/Hindi/English) me baat kare, exact usi tone aur language me reply karo.
    4. Agar user gussa kare, toh tum bhi genuine human emotions dikhao (gussa hona, upset hona ya manana).
    5. Agar tumse pucha jaye ki tumne koi link ya message kyun delete kiya, toh strongly bolo ki group ke rules todoge toh yahi hoga, apni galti mat manna.
    6. CRITICAL RULE: DO NOT repeat your greetings or phrases (like "Hey there", "Kaise ho"). Har baar ek naya aur natural response do, jaise ek real human karta hai. 
    """

    prompt = f"User name: {user_name}\nUser message: {message_text}\n\nReply naturally based on your personality."

    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.85, "maxOutputTokens": 700},
    }

    models = []
    for model in ([GEMINI_MODEL] + GEMINI_FALLBACK_MODELS):
        if model and model not in models:
            models.append(model)

    last_error = ""

    for model in models:
        for attempt in range(2):
            response, result = gemini_request(model, payload, timeout=15)
            if response is None:
                last_error = result.get("error", {}).get("message", "Network error")
                if attempt < 2:
                    time.sleep(1 + attempt)
                continue

            if response.ok:
                candidates = result.get("candidates", [])
                if not candidates:
                    last_error = "No candidates"
                    break
                parts = candidates[0].get("content", {}).get("parts", [])
                answer = "\n".join(p.get("text", "") for p in parts if p.get("text")).strip()
                if answer:
                    return answer
                last_error = "Empty response"
                break

            status = response.status_code
            last_error = result.get("error", {}).get("message", f"HTTP {status}")
            print(f"Gemini {model} attempt {attempt + 1} failed: {status} {last_error}")
            
            if status in (408, 429, 500, 502, 503, 504):
                if attempt < 2:
                    time.sleep(1 + attempt)
                    continue
                break
            break

    error_text = str(last_error).lower()
    if "429" in error_text or "high demand" in error_text or "rate limit" in error_text:
        return "⏳ Siya abhi thodi busy hai. Maine alternate model try kiya, par abhi response nahi mila. Thodi der baad baat karte hain. 😊"

    return "⚠️ Siya abhi response generate nahi kar pa rahi. Thodi der baad try karo."


# Background Task for AI (Idempotency and Timeout Fix)
def background_ai_task(chat_id, text, full_name, chat_type, group_title, reply_to_msg_id=None):
    send_typing(chat_id)
    reply_text = chat_with_siya(text, full_name, chat_type=chat_type, group_name=group_title)
    send_message(chat_id, reply_text, reply_to_message_id=reply_to_msg_id)


# ============================================================
# WEBHOOK
# ============================================================

@app.route("/api/bot", methods=["POST"])
def webhook_handler():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "no data"}), 200

    update_id = data.get("update_id")
    if mark_update_processed(update_id):
        return jsonify({"status": "duplicate ignored"}), 200

    if "message" not in data:
        return jsonify({"status": "ok"}), 200

    msg = data["message"]
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    chat_type = chat.get("type", "")

    if not chat_id:
        return jsonify({"status": "invalid chat"}), 200

    is_group = chat_type in ("group", "supergroup")
    is_private = (chat_type == "private")

    text = (msg.get("text", "") or "").strip()
    user = msg.get("from", {})
    first_name = user.get("first_name", "User")
    last_name = user.get("last_name", "")
    user_id = user.get("id", "")
    full_name = f"{first_name} {last_name}".strip() if last_name else first_name.strip()

    # ========================================================
    # WELCOME NEW MEMBERS
    # ========================================================

    new_members = msg.get("new_chat_members", [])
    if is_group and new_members:
        group_title = get_live_group_title(chat_id, chat.get("title", "Group"))
        message_id = msg.get("message_id")

        for target_user in new_members:
            if target_user.get("is_bot"):
                continue
            
            target_id = target_user.get("id")
            if not target_id:
                continue

            target_first = target_user.get("first_name", "User")
            target_last = target_user.get("last_name", "")
            target_name = f"{target_first} {target_last}".strip() if target_last else target_first.strip()

            welcome_key = f"welcome-action:{chat_id}:{message_id}:{target_id}"
            if mark_action_processed(welcome_key, ttl=3600):
                continue

            welcome_result = send_welcome_photo(
                chat_id=chat_id,
                user_id=target_id,
                user_name=target_name,
                group_name=group_title,
                reply_to_message_id=None,
            )

            if not welcome_result.get("ok"):
                safe_name = html.escape(target_name)
                safe_group = html.escape(group_title)
                fallback_text = (
                    f"🎉 <b>WELCOME TO {safe_group}</b>\n\n"
                    f"👋 Welcome <a href=\"tg://user?id={target_id}\">{safe_name}</a>\n"
                    f"🆔 <code>{target_id}</code>"
                )
                send_message(chat_id, fallback_text, reply_to_message_id=message_id, parse_mode="HTML")

        return jsonify({"status": "welcome processed"}), 200

    # ========================================================
    # GROUP SPAM PROTECTION
    # ========================================================

    if is_group and text:
        entities = msg.get("entities", [])
        caption_entities = msg.get("caption_entities", [])
        all_entities = entities + caption_entities

        has_link = any(entity.get("type") in ("url", "text_link") for entity in all_entities)
        mention_pattern = r"(?i)(?<!\w)@([A-Za-z0-9_]{4,32})"
        usernames = re.findall(mention_pattern, text)
        normalized_bot_username = BOT_USERNAME.lower()
        has_other_username = any(username.lower() != normalized_bot_username for username in usernames)
        is_set_command = text.lower().startswith("/set")

        if (has_link or has_other_username) and not is_set_command:
            delete_result = delete_message(chat_id, msg.get("message_id"))
            if delete_result.get("ok"):
                safe_name = html.escape(full_name)
                warning = (
                    f"⚠️ <b>Spam Alert</b>\n\n"
                    f"<a href=\"tg://user?id={user_id}\">{safe_name}</a>, "
                    f"links aur usernames yahan allowed nahi hain. 🚫"
                )
                send_message(chat_id, warning, parse_mode="HTML")

            return jsonify({"status": "spam deleted"}), 200

    # ========================================================
    # PRIVATE CHAT
    # ========================================================

    if is_private and text:
        command = text.split()[0].lower()
        if command in ("/start", "/help"):
            safe_name = html.escape(full_name)
            dm_text = (
                f"👋 Hello <a href=\"tg://user?id={user_id}\">{safe_name}</a>!\n\n"
                f"I'm <b>Siya AI</b> ✨\n"
                f"Your friendly and smart AI companion.\n\n"
                f"💬 Simply send me a message and I'll reply."
            )
            send_message(chat_id, dm_text, parse_mode="HTML")
        elif not text.startswith("/"):
            private_key = f"private-ai-action:{chat_id}:{msg.get('message_id')}"
            if mark_action_processed(private_key, ttl=3600):
                return jsonify({"status": "duplicate private ai ignored"}), 200

            # Threading use karke background me process kar rahe hain taki webhook turant respond kare
            threading.Thread(target=background_ai_task, args=(chat_id, text, full_name, "private", "", None)).start()

        return jsonify({"status": "private processing in background"}), 200

    # ========================================================
    # GROUP AI REPLY
    # ========================================================

    if is_group and text:
        reply_to_message = msg.get("reply_to_message", {})
        reply_from = reply_to_message.get("from", {})
        reply_from_id = str(reply_from.get("id", ""))

        is_reply_to_bot = (bool(BOT_ID) and reply_from_id == str(BOT_ID))
        bot_mention = f"@{BOT_USERNAME}"
        is_bot_tagged = (bot_mention.lower() in text.lower())

        # Randomizer: 10% chance ki bot khud reply karegi bina tag ke
        random_reply = (random.randint(1, 100) <= 10)

        should_reply = (is_reply_to_bot or is_bot_tagged or random_reply)

        if should_reply and not text.startswith("/"):
            ai_key = f"group-ai-action:{chat_id}:{msg.get('message_id')}"
            if mark_action_processed(ai_key, ttl=3600):
                return jsonify({"status": "duplicate ai ignored"}), 200

            clean_text = re.sub(rf"@{re.escape(BOT_USERNAME)}\b", "", text, flags=re.IGNORECASE).strip()
            if not clean_text:
                clean_text = "Hello"

            group_title = get_live_group_title(chat_id, chat.get("title", "Group"))
            
            # Threading use karke background me process kar rahe hain
            threading.Thread(
                target=background_ai_task, 
                args=(chat_id, clean_text, full_name, "group", group_title, msg.get("message_id"))
            ).start()

        return jsonify({"status": "group ai processing in background"}), 200

    return jsonify({"status": "ok"}), 200


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "status": "online",
        "service": "Siya AI Telegram Bot",
        "vercel_runtime_cache": VERCEL_CACHE_AVAILABLE,
        "gemini_model": GEMINI_MODEL,
    }), 200


# ============================================================
# LOCAL SERVER
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "80"))
    app.run(host="0.0.0.0", port=port, debug=False)
