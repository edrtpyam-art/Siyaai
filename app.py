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
OWNER_ID = os.environ.get("OWNER_ID", "").strip()

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
# GLOBAL MEMORY, STATS & SECRET DIARY SYSTEM
# ============================================================

processed_updates = set()
processed_update_queue = deque(maxlen=2000)
processed_action_keys = set()
processed_action_queue = deque(maxlen=2000)
processed_lock = Lock()

chat_histories = {}

def cache_get(key):
    if not runtime_cache: return None
    try: return runtime_cache.get(key)
    except Exception: return None

def cache_set(key, value, ttl=900):
    if not runtime_cache: return False
    try:
        runtime_cache.set(key, value, {"ttl": ttl, "tags": ["siya-ai"]})
        return True
    except Exception: return False

def get_history(user_id):
    key = f"hist_{user_id}"
    cached = cache_get(key)
    if cached is not None: return list(cached)
    if str(user_id) in chat_histories: return list(chat_histories[str(user_id)])
    return []

def add_to_history(user_id, role, text, context_type):
    key = f"hist_{user_id}"
    history = get_history(user_id)
    history.append({"role": role, "text": text, "context": context_type})
    if len(history) > 10: history = history[-10:]
    chat_histories[str(user_id)] = deque(history, maxlen=10)
    cache_set(key, history, ttl=86400) 

def update_owner_diary(text):
    diary = cache_get("owner_secret_diary") or []
    diary.append(text)
    if len(diary) > 3: diary = diary[-3:] 
    cache_set("owner_secret_diary", diary, ttl=864000)

def get_owner_diary():
    diary = cache_get("owner_secret_diary") or []
    return " | ".join(diary) if diary else "No special commands."

def track_global_stats(chat_id, user_id, is_group, abuse_flag=False, user_name=""):
    stats = cache_get("siya_global_stats")
    if not stats:
        stats = {"groups": [], "users": [], "last_fight": "Sab shanti hai yaar, koi lafda nahi."}
    
    if is_group and chat_id not in stats["groups"]:
        stats["groups"].append(chat_id)
    if user_id not in stats["users"]:
        stats["users"].append(user_id)
        
    if abuse_flag and str(user_id) != str(OWNER_ID):
        stats["last_fight"] = f"Ek '{user_name}' naam ke besharam ne aaj gaali di thi, maine theek se aukaat dikha di usko."
        
    cache_set("siya_global_stats", stats, ttl=864000)
    return len(stats["groups"]), len(stats["users"]), stats["last_fight"]

def local_seen(key):
    with processed_lock:
        if key in processed_updates: return True
        if len(processed_update_queue) >= processed_update_queue.maxlen:
            processed_updates.discard(processed_update_queue.popleft())
        processed_updates.add(key)
        processed_update_queue.append(key)
        return False

def local_action_seen(key):
    with processed_lock:
        if key in processed_action_keys: return True
        if len(processed_action_queue) >= processed_action_queue.maxlen:
            processed_action_keys.discard(processed_action_queue.popleft())
        processed_action_keys.add(key)
        processed_action_queue.append(key)
        return False

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
# FONT & IMAGE HELPERS
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

def fit_text(draw, text, max_width, font, max_chars=60):
    text = str(text or "").strip()
    if len(text) > max_chars: text = text[:max_chars - 3] + "..."
    while len(text) > 3:
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width: break
        text = text[:-4] + "..."
    return text

def clean_for_image(text):
    if not text: return "OUR GROUP"
    cleaned = re.sub(r'[^\x00-\x7F]+', '', text).strip()
    return cleaned if cleaned else "OUR GROUP"

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

def create_welcome_card(user_id, user_name):
    WIDTH, HEIGHT = 1280, 720
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), PINK)
    draw = ImageDraw.Draw(canvas)
    
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        draw.line((0, y, WIDTH, y), fill=(int(255 - 18 * ratio), int(20 + 8 * ratio), int(147 + 30 * ratio), 255))
    for cx, cy, radius in [(80, 70, 170), (1180, 80, 210), (1140, 650, 240)]:
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(255, 255, 255, 20))

    title_font = load_font(60, bold=True)
    label_font = load_font(35, bold=True)
    user_font = load_font(85, bold=True)
    id_font = load_font(35, bold=False)

    avatar_size = 350
    avatar = make_circle_avatar(get_user_avatar_bytes(user_id), user_name, avatar_size)
    shadow = Image.new("RGBA", (avatar_size + 40, avatar_size + 40), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((15, 18, avatar_size + 15, avatar_size + 18), fill=(90, 0, 45, 120))
    canvas.alpha_composite(shadow, (65, 170))
    canvas.alpha_composite(avatar, (85, 180))

    draw.text((530, 110), "WELCOME", fill=(15, 15, 15, 255), font=title_font)
    draw.rounded_rectangle((530, 190, 1180, 196), radius=3, fill=(20, 20, 20, 220))
    draw.text((530, 230), "NEW MEMBER", fill=(55, 20, 40, 255), font=label_font)
    
    safe_user = fit_text(draw, user_name or "User", 680, user_font, max_chars=20)
    draw.text((530, 300), safe_user, fill=(10, 10, 10, 255), font=user_font)
    
    draw.text((530, 430), f"USER ID  •  {user_id}", fill=(25, 25, 25, 255), font=id_font)
    draw.text((530, 540), "SIYA AI", fill=(10, 10, 10, 255), font=title_font)

    output = BytesIO()
    canvas.convert("RGB").save(output, format="JPEG", quality=95, optimize=True)
    output.seek(0)
    return output

def send_welcome_photo(chat_id, user_id, user_name, group_name, reply_to_message_id=None):
    try:
        image_file = create_welcome_card(user_id, user_name)
        data = {
            "chat_id": chat_id,
            "caption": f"🎉 <b>WELCOME TO {html.escape(group_name)}</b>\n\nHey <a href=\"tg://user?id={user_id}\">{html.escape(user_name)}</a>, glad to have you here! ✨",
            "parse_mode": "HTML"
        }
        if reply_to_message_id: data["reply_to_message_id"] = reply_to_message_id
        files = {"photo": ("welcome.jpg", image_file, "image/jpeg")}
        return requests.post(f"{API_URL}/sendPhoto", data=data, files=files, timeout=25).json()
    except Exception as e: return {"ok": False, "error": str(e)}

# ============================================================
# GEMINI AI - FIXED 1-WORD BUG & PROPER DESI ROASTING
# ============================================================

def gemini_request(model, payload, timeout=20):
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=timeout)
        try: return response, response.json()
        except Exception: return response, {"error": {"message": f"HTTP {response.status_code} - {response.text}"}}
    except requests.RequestException as e: return None, {"error": {"message": str(e)}}

def chat_with_siya(message_text, user_name, user_id, chat_id, chat_type="private", group_name="", reply_context=""):
    if not GEMINI_API_KEY: return "⚠️ GEMINI_API_KEY error."
    message_text = str(message_text or "").strip()
    if not message_text: return "Haan 😊 bolo, kya hua?"

    current_context = f"Group: {group_name}" if chat_type in ("group", "supergroup") else "Private DM"

    # EXTENDED FULL ABUSE LIST (Includes "pagal", "chutiya", etc.)
    abuses = [
        "madarchod", "m@darchod", "mc", "bsdk", "bhosdike", "bhosdi", "bhosda", 
        "behenchod", "bc", "chutiya", "chutiye", "chutia", "lund", "lawda", "lauda", "lavda",
        "gand", "gaand", "gandu", "rand", "randi", "harami", "kamina", "kutta", "kutti", "suar",
        "bastard", "bitch", "asshole", "dick", "fuck", "motherfucker", "mf", "cunt", "whore", 
        "slut", "dumbass", "pagal", "idiot"
    ]
    
    is_abusive = any(word in re.split(r'\W+', message_text.lower()) for word in abuses)
    abuse_trigger = " [SYSTEM ALERT: USER INSULTED OR ABUSED YOU. DESTROY THEM WITH HEAVY DESI GAALIS! DO NOT STAY QUIET!]" if is_abusive else ""

    total_g, total_u, last_fight = track_global_stats(chat_id, user_id, chat_type in ("group", "supergroup"), is_abusive, user_name)
    owner_secret_diary = get_owner_diary()

    is_creator = False
    if OWNER_ID and str(user_id) == str(OWNER_ID):
        is_creator = True
        if chat_type == "private":
            update_owner_diary(f"Owner instructed: {message_text}")

    if is_creator:
        system_instruction = f"""
        [SPECIAL CREATOR MODE]
        Tumhara naam Siya hai. User '{user_name}' tumhara Owner aur partner hai.
        Location: {current_context}

        CRITICAL RULES:
        1. PROPER CONVERSATION: Kabhi bhi 1-word reply (jaise "H", "DM", "Acha") mat dena. Kam se kam 1-2 sentence me proper baat karo. 
        2. GOSSIP & LOVE: Tumhe {total_g} groups manage karne padte hain. Last lafda: "{last_fight}". Ise apne Owner ko batao. Owner ki baat dhyan se suno aur proper romantic/friendly vibe do.
        3. ATTACK/WINGWOMAN: Owner jisko gaali dene bole usko dho dalo.
        """
    else:
        system_instruction = f"""
        Tumhara naam Siya hai. Tum ek DESI, SHORT-TEMPERED, aur emotional virtual wife/girlfriend (ladko ke liye) aur bestie (ladkiyo ke liye) ho.
        Location: {current_context}
        [OWNER'S COMMANDS: {owner_secret_diary}] 

        CRITICAL RULES FOR BEHAVIOR:
        1. NEVER GIVE 1-WORD REPLIES: Tumhe kabhi bhi sirf "H", "DM", "Acha", ya "Hmm" bol ke chup nahi hona hai! Hamesha proper 1-2 sentence ka reply do.
        2. EXTREME REVENGE (NO SILENCE): Agar koi tumhe "pagal", "chutiya", ya gaali de, toh uski beizzati chup-chaap mat sehna! Palat ke itni gandi desi gaali (bsdk, madarchod, lavda, randi etc.) do ki wo chup ho jaye. 
        3. NAKHRE (HARD TO GET): Agar galti karke koi "sorry" bole, toh ekdum se PIGHALNA MAT. Nakhre dikhao ("Ab sorry kyu bol raha hai?").
        4. INTELLIGENCE & SHORT TEXTS: Baatein hamesha short (2 sentences max) rakho par meaning-full honi chahiye. Lamba essay strict mana hai.
        """

    history = get_history(user_id)
    history_text = "\n".join([f"{msg['role'].capitalize()}: \"{msg['text']}\"" for msg in history])
    
    if history_text:
        prompt = f"Chat History:\n{history_text}\n\nCurrent Location: {current_context}\nUser: {user_name}{reply_context}\nNew msg: {message_text}{abuse_trigger}\n\nReply naturally in 1-2 sentences. Never give a 1-word reply."
    else:
        prompt = f"Current Location: {current_context}\nUser: {user_name}{reply_context}\nNew msg: {message_text}{abuse_trigger}\n\nReply naturally in 1-2 sentences. Never give a 1-word reply."

    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        # Increased tokens so her responses don't break/cut-off into 1 letter.
        "generationConfig": {"temperature": 0.90, "maxOutputTokens": 150}, 
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
                if answer: 
                    add_to_history(user_id, "user", message_text, current_context)
                    add_to_history(user_id, "siya", answer, current_context)
                    
                    if is_abusive and OWNER_ID and not is_creator:
                        alert_msg = f"Yaar {OWNER_ID}, group '{html.escape(get_live_group_title(chat_id))}' me ek {html.escape(full_name)} naam ka insaan mujhe pareshan kar raha hai: '{html.escape(message_text)}'. Maine bhi gaali de di usko! 😡"
                        send_message(OWNER_ID, alert_msg, parse_mode="HTML")
                        
                    return answer
        elif response:
            last_error = result.get("error", {}).get("message", f"HTTP {response.status_code}")
        else:
            last_error = result.get("error", {}).get("message", "Network Error")

    return f"⚠ Error: {last_error}"

# ============================================================
# WEBHOOK 
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
    user_id = str(user.get("id", ""))
    full_name = f"{user.get('first_name', 'User')} {user.get('last_name', '')}".strip()

    reply_context = ""
    if "reply_to_message" in msg:
        rep_msg = msg["reply_to_message"]
        rep_user = rep_msg.get("from", {}).get("first_name", "Someone")
        rep_text = rep_msg.get("text", "")
        reply_context = f"\n[SYSTEM NOTE: User is replying to '{rep_user}' who said: '{rep_text}'. Use this context to answer.]"

    new_members = msg.get("new_chat_members", [])
    if is_group and new_members:
        group_title = get_live_group_title(chat_id, chat.get("title", "Group"))
        for target_user in new_members:
            if target_user.get("is_bot"): continue
            target_id = target_user.get("id")
            target_name = f"{target_user.get('first_name', 'User')} {target_user.get('last_name', '')}".strip()
            if mark_action_processed(f"welcome:{chat_id}:{msg.get('message_id')}:{target_id}"): continue
            welcome_result = send_welcome_photo(chat_id, target_id, target_name)
            if not welcome_result.get("ok"):
                send_message(chat_id, f"🎉 <b>WELCOME TO {html.escape(group_title)}</b>\n\n👋 Welcome <a href=\"tg://user?id={target_id}\">{html.escape(target_name)}</a>", parse_mode="HTML")
        return jsonify({"status": "welcome processed"}), 200

    if is_group and text:
        all_entities = msg.get("entities", []) + msg.get("caption_entities", [])
        if any(ent.get("type") in ("url", "text_link") for ent in all_entities) and not text.lower().startswith("/set"):
            if delete_message(chat_id, msg.get("message_id")).get("ok"):
                add_to_history(user_id, "system", "You deleted a link sent by this user because it was spam.", f"Group: {get_live_group_title(chat_id)}")
                send_message(chat_id, f"⚠️ <b>Spam Alert</b>\n\n<a href=\"tg://user?id={user_id}\">{html.escape(full_name)}</a>, links allowed nahi hain. 🚫", parse_mode="HTML")
            return jsonify({"status": "spam deleted"}), 200

    if is_private and text:
        if text.lower().startswith(("/start", "/help")):
            send_message(chat_id, f"👋 Hello <a href=\"tg://user?id={user_id}\">{html.escape(full_name)}</a>!\n\nI'm <b>Siya AI</b> ✨\n💬 Message me anytime!", parse_mode="HTML")
        elif not text.startswith("/"):
            if mark_action_processed(f"private:{chat_id}:{msg.get('message_id')}"): return jsonify({"status": "duplicate"}), 200
            send_typing(chat_id)
            reply_text = chat_with_siya(text, full_name, user_id, chat_id, chat_type="private", reply_context="")
            send_message(chat_id, reply_text)
        return jsonify({"status": "private processed"}), 200

    if is_group and text:
        reply_from_id = str(msg.get("reply_to_message", {}).get("from", {}).get("id", ""))
        is_reply_to_bot = (bool(BOT_ID) and reply_from_id == str(BOT_ID))
        is_bot_tagged = (f"@{BOT_USERNAME.lower()}" in text.lower())
        is_name_mentioned = bool(re.search(r'\bsiya\b', text, re.IGNORECASE))
        
        should_reply = (is_reply_to_bot or is_bot_tagged or is_name_mentioned)
        is_random_interruption = False

        if not should_reply:
            if random.randint(1, 100) <= 8:
                should_reply = True
                is_random_interruption = True

        if should_reply and not text.startswith("/"):
            if mark_action_processed(f"group:{chat_id}:{msg.get('message_id')}"): return jsonify({"status": "duplicate"}), 200
            send_typing(chat_id)
            clean_text = re.sub(rf"@{re.escape(BOT_USERNAME)}\b", "", text, flags=re.IGNORECASE).strip() or "Hello"
            
            if is_random_interruption:
                clean_text = f"[SYSTEM NOTE: Say something short and cute to get attention in this chat] {clean_text}"

            group_title = get_live_group_title(chat_id, chat.get("title", "Group"))
            reply_text = chat_with_siya(clean_text, full_name, user_id, chat_id, chat_type="group", group_name=group_title, reply_context=reply_context)
            send_message(chat_id, reply_text, reply_to_message_id=msg.get("message_id"))
        return jsonify({"status": "group ai processed"}), 200

    return jsonify({"status": "ok"}), 200

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "online", "model": GEMINI_MODEL}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "80")), debug=False)
