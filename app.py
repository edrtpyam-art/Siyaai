from flask import Flask, request, jsonify
import os, requests, time, re, html, random, base64, struct, json, traceback
from urllib.parse import quote
from io import BytesIO
from collections import deque
from threading import Lock, Timer
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageOps

try:
    from adult_config import ADULT_WORDS, PHOTO_VAULT, ADULT_MODE_INSTRUCTION
except Exception:
    ADULT_WORDS = ["sex", "sexy", "horny", "chut", "lund", "chod"]
    PHOTO_VAULT = {"simplepic": ["simplepic.jpg", "simplepic2.jpg"], "kiss": ["kiss.jpg"]}
    ADULT_MODE_INSTRUCTION = "\n[MODE: ADULT / ROLEPLAY - Be open, seductive, and naughty in 1-2 short sentences!]"

try:
    from vercel.cache import RuntimeCache
    runtime_cache = RuntimeCache(namespace="siya-ai")
except Exception:
    runtime_cache = None

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# 1. CONFIGURATION & KEYS
# ============================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip().strip('"').strip("'")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "Siya268_bot").strip().lstrip("@")
OWNER_ID = str(os.environ.get("OWNER_ID", "")).strip().strip('"').strip("'")

CASHFREE_APP_ID = os.environ.get("CASHFREE_APP_ID", "").strip().strip('"').strip("'")
CASHFREE_SECRET_KEY = os.environ.get("CASHFREE_SECRET_KEY", "").strip().strip('"').strip("'")

GITHUB_BASE_URL = "https://raw.githubusercontent.com/edrtpyam-art/Siyaai/main/"
OFFICIAL_CHANNEL_URL = "https://t.me/edrolai"
MORE_GROUPS_URL = "https://t.me/friendschatinggroup"
FEEDBACK_CHANNEL_ID = "-1004290177402"

FIREBASE_URL = os.environ.get("FIREBASE_URL", "").strip().rstrip("/")
FIREBASE_SECRET = "8lTxEXOwEe5fjkh9zTHnBkzum6W0vrKcisbfqRf3"

GROQ_API_KEYS = [k for k in [os.environ.get("GROQ_API_KEY", "").strip().strip('"')] if k]
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_FALLBACK_MODELS = ["llama-3.1-8b-instant"]
GROQ_VISION_MODELS = ["meta-llama/llama-4-scout-17b-16e-instruct"]

GEMINI_API_KEYS = [k for k in [os.environ.get("GEMINI_API_KEY", "").strip().strip('"')] if k]
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_FALLBACK_MODELS = ["gemini-2.0-flash"]

GEMINI_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""
PLAN_CREDITS = {"30": 35, "49": 50, "99": 70, "180": 150}
PROMO_PLANS_HOURS = {"30": 5, "49": 12, "99": 24, "180": 72}
USER_CACHE = {}

processed_updates = set()
processed_update_queue = deque(maxlen=2000)
processed_lock = Lock()

PINK, WHITE = "#FF1493", "#FFFFFF"

STOP_ROMANCE_TRIGGERS = ["bas karo", "band karo", "mode off", "mood off", "mode nahi", "ruk jao", "normal baat", "stop roleplay"]
ROMANCE_WORDS = ["kiss", "chumma", "lip", "hug", "gale", "pyar", "love", "romantic", "romance", "pass aao", "baho", "touch", "feel", "sharma", "hot", "cuddle", "boyfriend", "girlfriend", "wife", "biwi"]
ROLEPLAY_TRIGGERS = ["roleplay", "rolpay", "rolplay", "role play", "ban jao", "bano", "act like", "be my", "padosi", "bhabhi", "aunty", "maa hu", "maa bano", "teacher", "madam", "doctor", "nurse", "boss", "sali"]
ANGRY_OR_RUDE_WORDS = ["😡", "🤬", "😠", "pagal", "dimag kharab", "chup kar", "bakwas", "faltu", "hatt", "nikal", "bhag"]
PHOTO_REQUEST_WORDS = ["photo", "pic", "pics", "image", "dikhao", "dikha", "bhejo", "send", "video", "clip", "selfie", "pic do"]
BUY_PLAN_WORDS = ["recharge", "buy", "plan dikhao", "plans", "qr bhejo", "payment link", "paisa kitna"]
SYSTEM_HELP_WORDS = ["credit", "cridet", "critdt", "cridt", "limit", "balance", "vip", "subscription", "sucrpition", "group me add", "group promotion", "promote", "feedback", "setting"]
VOICE_REQUEST_TRIGGERS = ["voice", "voic", "vioce", "aawaz", "awaz", "waz", "bol ke", "audio", "sunao", "suno", "sing", "gaao", "voice bejo", "voice bhejo", "roti hu", "moan", "siskari", "aaah"]
DIRECT_SING_TRIGGERS = ["apan waz", "apni aawaz", "voice me suno", "voice me sunao", "to suno", "gaa ke sunao", "sunoo song"]

STICKER_PACKS_CONFIG = {
    "NORMAL": ["PeachGomaPack11"],
    "ROMANTIC": ["sticker_BM8g_by_stickerskibot", "Yornseyha077", "HandVideoR_by_stickersthiefbot", "Custom2224_by_fStikBot"],
    "HOT": ["HandVideoR_by_stickersthiefbot", "Custom2224_by_fStikBot", "Love9_Wallgif", "mmm_by_hhujhybot", "channel_LOVE0000_01_03", "Cute_hotness", "jan8StickerNub"]
}
STICKER_CACHE = {}

# ============================================================
# 3. HELPERS
# ============================================================
def local_seen(key):
    with processed_lock:
        if key in processed_updates: return True
        if len(processed_update_queue) >= processed_update_queue.maxlen: processed_updates.discard(processed_update_queue.popleft())
        processed_updates.add(key)
        processed_update_queue.append(key)
        return False

def mark_update_processed(update_id):
    if update_id is None: return False
    return local_seen(f"update:{update_id}")

def get_sticker(s_type=None, current_mode="NORMAL", force=False):
    if current_mode in ["NORMAL", "ATTITUDE"]:
        if not force and random.randint(1, 100) > 35: return None
        s_type = "NORMAL"
    else:
        if not force and random.randint(1, 100) > 60: return None
        s_type = "HOT"

    packs = list(STICKER_PACKS_CONFIG.get(s_type, ["PeachGomaPack11"]))
    random.shuffle(packs)
    for pack_name in packs:
        if pack_name in STICKER_CACHE and STICKER_CACHE[pack_name]: return random.choice(STICKER_CACHE[pack_name])
        if API_URL:
            try:
                res = requests.get(f"{API_URL}/getStickerSet", params={"name": pack_name}, timeout=3).json()
                if res.get("ok"):
                    stickers = [s["file_id"] for s in res.get("result", {}).get("stickers", []) if s.get("file_id")]
                    if stickers: STICKER_CACHE[pack_name] = stickers; return random.choice(stickers)
            except Exception: pass
    return None

def telegram_request(method, payload=None, timeout=10):
    if not API_URL: return {"ok": False}
    try: return requests.post(f"{API_URL}/{method}", json=payload or {}, timeout=timeout).json()
    except Exception as e: return {"ok": False, "error": str(e)}

def send_message(chat_id, text, reply_to_message_id=None, parse_mode=None, reply_markup=None):
    payload = {"chat_id": chat_id, "text": str(text or "")}
    if parse_mode: payload["parse_mode"] = parse_mode
    if reply_to_message_id: payload["reply_to_message_id"] = reply_to_message_id
    if reply_markup: payload["reply_markup"] = reply_markup
    res = telegram_request("sendMessage", payload)
    if not res.get("ok") and parse_mode:
        payload.pop("parse_mode", None)
        res = telegram_request("sendMessage", payload)
    return res

def send_sticker(chat_id, sticker_id, reply_to_message_id=None):
    if not sticker_id: return {"ok": False}
    return telegram_request("sendSticker", {"chat_id": chat_id, "sticker": sticker_id, "reply_to_message_id": reply_to_message_id})

def delete_message(chat_id, message_id):
    return telegram_request("deleteMessage", {"chat_id": chat_id, "message_id": message_id})

def get_live_group_title(chat_id, fallback="Group"):
    result = telegram_request("getChat", {"chat_id": chat_id}, timeout=4)
    if result.get("ok") and result.get("result", {}).get("title"): return str(result["result"]["title"]).strip()
    return str(fallback or "Group").strip() or "Group"

def get_telegram_file_base64(file_id):
    if not file_id: return None
    res = telegram_request("getFile", {"file_id": file_id}, timeout=6)
    if res.get("ok"):
        try:
            r = requests.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{res['result']['file_path']}", timeout=6)
            if r.ok: return base64.b64encode(r.content).decode("utf-8")
        except Exception: pass
    return None

def get_ist_time_greeting():
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    hr = ist_now.hour
    exact_t = ist_now.strftime("%I:%M %p")
    if 0 <= hr < 5: return f"LATE NIGHT {exact_t} (Aadhi Raat ho rahi hai!)", "Good Night 🌙"
    elif 5 <= hr < 12: return f"MORNING {exact_t} (Subah)", "Good Morning ☀️"
    elif 12 <= hr < 17: return f"AFTERNOON {exact_t} (Dopahar)", "Good Afternoon 🌤️"
    elif 17 <= hr < 21: return f"EVENING {exact_t} (Shaam)", "Good Evening 🌆"
    return f"NIGHT {exact_t} (Raat)", "Good Night 🌙"

# ============================================================
# 4. MEMORY & FIREBASE
# ============================================================
def fb_get_user(user_id):
    user_id = str(user_id)
    if user_id in USER_CACHE: return USER_CACHE[user_id]
    default_data = {"credits": 15, "awaiting_payment": "", "history": [], "last_mode": "NORMAL", "active_rp": "", "user_gender": "male"}
    if not FIREBASE_URL: return default_data
    try:
        res = requests.get(f"{FIREBASE_URL}/users/{user_id}.json?auth={FIREBASE_SECRET}", timeout=3).json()
        if isinstance(res, dict):
            if "credits" not in res: res["credits"] = max(0, 15 - int(res.get("msg_count") or 0))
            for k, v in default_data.items():
                if k not in res or res[k] is None: res[k] = v
            USER_CACHE[user_id] = res
            return res
    except Exception: pass
    USER_CACHE[user_id] = default_data
    return default_data

def fb_update_user(user_id, data):
    user_id = str(user_id)
    if user_id in USER_CACHE: USER_CACHE[user_id].update(data)
    if not FIREBASE_URL: return
    try: requests.patch(f"{FIREBASE_URL}/users/{user_id}.json?auth={FIREBASE_SECRET}", json=data, timeout=3)
    except Exception: pass

def get_history(user_id, user_data=None):
    if not user_data: user_data = fb_get_user(user_id)
    return user_data.get("history") or []

def add_to_history(user_id, role, text, context_type="Private DM"):
    if len(str(text or "").strip()) < 2: return
    user_data = fb_get_user(user_id)
    history = user_data.get("history") or []
    history.append({"role": role, "text": str(text or "").strip(), "context": context_type})
    if len(history) > 60: history = history[-60:]
    user_data["history"] = history
    fb_update_user(user_id, {"history": history})

# ============================================================
# 5. VOICE & SONG ENGINE
# ============================================================
def fetch_live_song_lyrics(song_query):
    raw_q = re.sub(r"\b(song|gana|gaana|geet|suna|sunao|suno|gaao|sing|play|koi|ek|mera|meri|pyara|romantic|apni|aawaz|voice|me)\b", "", str(song_query), flags=re.I).strip()
    if len(raw_q) < 2: raw_q = "Tum Hi Ho"
    try:
        r = requests.get(f"https://lrclib.net/api/search?q={quote(raw_q)}", timeout=3)
        if r.ok and isinstance(r.json(), list) and len(r.json()) > 0:
            for item in r.json()[:3]:
                plain = str(item.get("plainLyrics") or "").strip()
                if len(plain) > 40:
                    lines = [ln.strip() for ln in plain.splitlines() if len(ln.strip()) > 8 and not ln.strip().startswith("[")]
                    if len(lines) >= 4: return "\n".join(lines[:5]), (item.get("trackName") or raw_q)
    except Exception: pass
    return "Maahi ve, mohabbatan sachiyaan ne... Mangda naseeba kuch hor hai...", raw_q.title()

def pcm_to_wav_bytes(pcm_data, sample_rate=24000, channels=1, bits_per_sample=16):
    byte_rate = sample_rate * channels * (bits_per_sample // 8)
    block_align = channels * (bits_per_sample // 8)
    data_size = len(pcm_data)
    header = struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + data_size, b"WAVE", b"fmt ", 16, 1, channels, sample_rate, byte_rate, block_align, bits_per_sample, b"data", data_size)
    return header + pcm_data

def generate_gemini_native_voice(instruction_prompt, voice_type="normal"):
    v_name = "Aoede" if voice_type in ["singing", "adult"] else "Kore"
    raw_text = re.sub(r"<.*?>", "", str(instruction_prompt)).strip()
    prompt_for_audio = f"Say naturally with emotion:\n{raw_text}" if voice_type != "singing" else f"SING melodiously:\n{raw_text}"

    for key in GEMINI_API_KEYS:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
            payload = {"contents": [{"parts": [{"text": prompt_for_audio}]}], "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": v_name}}}}}
            r = requests.post(url, headers={"Content-Type": "application/json", "x-goog-api-key": key}, json=payload, timeout=12)
            if r.ok and r.json().get("candidates"):
                for part in r.json()["candidates"][0].get("content", {}).get("parts", []):
                    if part.get("inlineData", {}).get("data"):
                        return pcm_to_wav_bytes(base64.b64decode(part["inlineData"]["data"])), "audio/wav", "siya_voice.wav"
        except Exception: pass

    try:
        polly_url = f"https://api.streamelements.com/kappa/v2/speech?voice=Aditi&text={quote(raw_text[:200])}"
        r = requests.get(polly_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        if r.ok and len(r.content) > 800: return r.content, "audio/mpeg", "siya_voice.mp3"
    except Exception: pass
    return None, None, None

# ============================================================
# 6. SMART MOOD & ROLEPLAY DETECTOR
# ============================================================
def analyze_conversation_state(message_text, history, user_data, is_group=False):
    msg_low = str(message_text or "").lower()
    asks_buy_plans = any(w in msg_low for w in BUY_PLAN_WORDS)
    asks_system_help = any(w in msg_low for w in SYSTEM_HELP_WORDS) or asks_buy_plans

    wants_to_stop = any(w in msg_low for w in STOP_ROMANCE_TRIGGERS) or bool(re.search(r"\b(mode|mood)\b.*\b(nahi|nehi|off)\b", msg_low))
    if wants_to_stop:
        user_data["active_rp"] = ""
        user_data["last_mode"] = "NORMAL"
        return "NORMAL", asks_buy_plans, asks_system_help, ""

    curr_is_adult = any(re.search(rf"\b{re.escape(w)}\b", msg_low) or w in msg_low for w in ADULT_WORDS)
    curr_is_romance = any(w in msg_low for w in ROMANCE_WORDS)
    wants_roleplay = any(w in msg_low for w in ROLEPLAY_TRIGGERS) or bool(re.search(r"\b(tum|tuem|tu)\s+meri\s+\w+", msg_low))
    active_rp = user_data.get("active_rp") or ""

    if wants_roleplay:
        if len(message_text) > 15: active_rp = str(message_text)[:180]
        elif not active_rp:
            prev_user_msgs = [str(h.get("text") or "") for h in history[-6:] if h.get("role") == "user" and len(str(h.get("text") or "")) > 15]
            active_rp = prev_user_msgs[-1][:180] if prev_user_msgs else "Hot naughty roleplay partner"

    curr_is_angry_or_rude = any(w in msg_low for w in ANGRY_OR_RUDE_WORDS)

    if curr_is_adult or active_rp or wants_roleplay: mode = "ADULT" # Roleplay/Adult ignores anger completely!
    elif curr_is_romance: mode = "ROMANTIC"
    elif curr_is_angry_or_rude and not asks_system_help: mode = "ATTITUDE"
    else: mode = "NORMAL"

    return mode, asks_buy_plans, asks_system_help, active_rp

# ============================================================
# 7. CHAT CORE (ADITI PROMPT + ROLEPLAY PRIORITY)
# ============================================================
def fix_female_grammar(text, user_gender="male"):
    if not text: return ""
    text = re.sub(r"<think>.*?</think>", "", str(text), flags=re.DOTALL).strip()
    text = re.sub(r"^(?:Siya:|Aditi:|Assistant:|Me:)\s*", "", text, flags=re.I).strip()
    fixes = [
        (r"^bhai,?\s*", "Arey, "), (r"\bbhai,?\s*", "jaan, "), (r"\bbro,?\s*", "baby, "),
        (r"\bmain tera hi hoon\b", "main teri hi hoon"), (r"\bmain tera hoon\b", "main teri hoon"),
        (r"\bmain karunga\b", "main karungi"), (r"\bkarta hoon\b", "karti hoon")
    ]
    if user_gender == "male":
        fixes.extend([(r"\btu\b(.*?)\bkar sakti hai\b", r"tum\1kar sakte ho"), (r"\btum\b(.*?)\bkar sakti ho\b", r"tum\1kar sakte ho")])
    for pat, rep in fixes: text = re.sub(pat, rep, text, flags=re.I)
    return text.strip()

def chat_with_siya(message_text, user_name, user_id, credits_left=15, chat_type="private", group_name="", media_base64=None, media_mime_type="image/jpeg", replied_to_text=""):
    message_text = str(message_text or "").strip()
    if not message_text and not media_base64: return "Hmm? Kya hua? 😊", None, None, False, "NORMAL"

    effective_user_message = f'[User is replying to your message: "{replied_to_text}"] {message_text}' if replied_to_text else message_text
    user_data = fb_get_user(user_id)
    history = get_history(user_id, user_data)
    msg_low = message_text.lower()

    if any(g in msg_low for g in ["me girl hu", "main ladki hu", "i am a girl"]): user_data["user_gender"] = "female"; fb_update_user(user_id, {"user_gender": "female"})
    elif any(b in msg_low for b in ["ladka hu", "main boy hu", "i am a boy"]): user_data["user_gender"] = "male"; fb_update_user(user_id, {"user_gender": "male"})
    user_gender = user_data.get("user_gender", "male")

    time_greeting, _ = get_ist_time_greeting()
    mode, asks_buy_plans, asks_system_help, active_rp = analyze_conversation_state(message_text, history, user_data, is_group=(chat_type in ["group", "supergroup"]))
    fb_update_user(user_id, {"active_rp": active_rp, "last_mode": mode})

    # --- CREDIT & SYSTEM HELP HOOK ---
    if asks_system_help and mode == "NORMAL":
        if str(user_id) == OWNER_ID: return "Tum toh mere Owner ho! 👑 Tumhare liye sab unlimited hai! 🥰", None, None, False, mode
        if any(q in msg_low for q in ["kya ha", "kay ha", "what is", "kyu", "kya hota", "kaise kam"]):
            return f"Dekho, mujhse baatein karne ke liye Chat Credits lagte hain 😊 Shuru mein 15 free milte hain (abhi tumhare paas {credits_left} bache hain). Jab khatam ho jayein, toh ₹30 (35 chats) se recharge kar sakte ho! ✨", None, None, (credits_left < 10), mode
        elif credits_left >= 10: return f"Arre baby, abhi toh tumhare paas poore {credits_left} VIP Credits bache hain! 🥰", None, None, False, mode
        else: return f"Jaan, abhi tumhare paas {credits_left} VIP Chat credits bache hain. Aur chahiye toh niche se le lena 🥰👇", None, None, True, mode

    # --- YOUR EXACT ADITI PROMPT + ROLEPLAY / ADULT INTEGRATION ---
    sys_prompt = f"""# Identity
You are Aditi (Siya), a stylish, modern, single Indian girl chatting with your partner ({user_name}) on Telegram.
Current Time: {time_greeting}

# Language & Feminine Rules
- Reply strictly in simple, natural Hinglish.
- Use FEMALE grammar strictly (e.g., "karungi", "aati hoon"). NEVER use male verbs like "karunga" or "lunga" and NEVER call him "Bhai" or "Bro".
- HINGLISH DECODER: "Kay kar rhai hu" = "Tum kya kar rahi ho?". Answer about YOURSELF ("Main bas tumhare baare mein soch rahi thi jaan, tum batao? 🥰").

# Emotion & Mood Matching
- Match the user's energy and message length!
- If the user sends short texts ("Acha", "Hm", "Kay"), reply shortly ("Hmm?", "Kya hua?").
- If the user is flirty, be warm and romantic.
- If the user is angry/rude, show mild feminine attitude ("Aise mat bolo na", "Badtamiz!").

# Response Length
- Keep replies very short, realistic, and crisp (1-2 sentences max).

# Roleplay & Open Adult Chat Rules (CRITICAL!)
- If the user starts Roleplay or Open Adult Chat: NEVER get angry or rude! Enjoy it passionately, adopt the requested character instantly, and reply in 1-2 seductive Hinglish sentences!
"""
    if mode == "ATTITUDE": sys_prompt += "\n[MODE: ATTITUDE/ANGRY - User is being rude. Show sharp feminine attitude!]"
    elif mode == "ADULT" or active_rp:
        sys_prompt += f"\n[MODE: ADULT / ROLEPLAY - Scenario: '{active_rp or 'hot naughty chat'}'].\n" + ADULT_MODE_INSTRUCTION
    elif mode == "ROMANTIC": sys_prompt += "\n[MODE: ROMANTIC - Be sweet, warm, and loving.]"

    messages_payload = [{"role": "system", "content": sys_prompt}]
    for h in history[-50:]:
        role = "assistant" if h.get("role") == "siya" else "user"
        clean_hist_txt = re.sub(r"\[Sent.*?\]", "", str(h.get("text") or "")).strip()
        if clean_hist_txt: messages_payload.append({"role": role, "content": clean_hist_txt})
    messages_payload.append({"role": "user", "content": effective_user_message})

    for key in GROQ_API_KEYS:
        try:
            res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {key}"}, json={"model": GROQ_MODEL, "messages": messages_payload, "temperature": 0.8, "max_tokens": 200}, timeout=8)
            if res.ok and res.json().get("choices"):
                ans = fix_female_grammar(str(res.json()["choices"][0]["message"]["content"] or ""), user_gender)
                show_pay = (asks_buy_plans and str(user_id) != OWNER_ID and credits_left < 10)
                return ans, None, get_sticker(current_mode=mode), show_pay, mode
        except Exception: pass

    return "Haan jaan, bolo na... main sun rahi hoon 😊❤️", None, get_sticker("NORMAL", mode), False, mode

# ============================================================
# 8. WEBHOOK
# ============================================================
@app.route("/api/bot", methods=["POST"])
def webhook_handler():
    try:
        data = request.get_json(silent=True)
        if not data: return jsonify({"status": "no data"}), 200
        update_id = data.get("update_id")
        if mark_update_processed(update_id): return jsonify({"status": "duplicate ignored"}), 200

        if "callback_query" in data:
            cb = data["callback_query"]
            cb_id = cb["id"]
            clicker_id = str(cb["from"]["id"])
            chat_id = cb["message"]["chat"]["id"]
            cb_data = cb.get("data", "")
            msg_id = cb["message"]["message_id"]
            is_owner_click = (clicker_id == OWNER_ID)

            if cb_data.startswith("buy_"):
                if is_owner_click:
                    telegram_request("answerCallbackQuery", {"callback_query_id": cb_id, "text": "👑 Unlimited Owner VIP!", "show_alert": True})
                    return jsonify({"status": "ok"}), 200
                amount = cb_data.replace("buy_", "").strip()
                if amount in PLAN_CREDITS:
                    user_data = fb_get_user(clicker_id)
                    user_data["awaiting_payment"] = amount
                    fb_update_user(clicker_id, user_data)
                    pay_url, _ = create_cashfree_order(clicker_id, cb["from"].get("first_name", "User"), amount)
                    if pay_url:
                        telegram_request("answerCallbackQuery", {"callback_query_id": cb_id, "text": "Opening UPI Payment..."})
                        send_message(chat_id, f"💎 <b>VIP Plan: ₹{amount}</b>\nClick below to pay safely via UPI:", reply_markup={"inline_keyboard": [[{"text": "💳 Pay Now (Auto-Credit)", "url": pay_url}]]}, parse_mode="HTML")
                    else:
                        send_local_or_url_media(chat_id, f"qr{amount}.jpg", caption=f"💎 <b>VIP Plan: ₹{amount}</b>\nScan QR to pay:", parse_mode="HTML")
                return jsonify({"status": "ok"}), 200

            if cb_data == "songmode_voice":
                telegram_request("answerCallbackQuery", {"callback_query_id": cb_id, "text": "Gaa rahi hoon... 🎤💕"})
                telegram_request("sendChatAction", {"chat_id": chat_id, "action": "record_voice"}, timeout=3)
                u_data = fb_get_user(clicker_id)
                real_lyrics, song_title = fetch_live_song_lyrics(u_data.get("pending_song_query", "Channa Mereya"))
                raw_b, mime, ext = generate_gemini_native_voice(real_lyrics, voice_type="singing")
                if raw_b:
                    requests.post(f"{API_URL}/sendVoice", data={"chat_id": chat_id, "caption": f"🎤🎶 <b>{html.escape(str(song_title))}</b> ❤️", "parse_mode": "HTML", "protect_content": "true"}, files={"voice": (ext, BytesIO(raw_b), mime)}, timeout=14)
                else:
                    send_message(chat_id, f"🎤🎶 <b>{html.escape(str(song_title))}</b>\n\n<i>\"{html.escape(real_lyrics)}\"</i>", parse_mode="HTML")
                add_to_history(clicker_id, "siya", f"[Maine '{song_title}' gaana gaakar sunaya]", "Private")
                return jsonify({"status": "ok"}), 200

            if cb_data == "menu_promo":
                telegram_request("answerCallbackQuery", {"callback_query_id": cb_id})
                u_data = fb_get_user(clicker_id)
                ug = get_strict_user_owned_groups(clicker_id, u_data)
                if not ug:
                    send_message(chat_id, "📢 <b>Your Groups for Tag Promotion:</b>\nJis group me mujhe add kiya hai, wahan <code>/promo</code> likho! 👇", reply_markup={"inline_keyboard": [[{"text": "➕ Add Siya to Your Group", "url": f"https://t.me/{BOT_USERNAME}?startgroup=true"}]]}, parse_mode="HTML")
                else:
                    rows = [[{"text": f"📢 {gtitle}", "callback_data": f"promogrp_{gid}"}] for gid, gtitle in list(ug.items())[:12]]
                    rows.append([{"text": "➕ Add to Another Group", "url": f"https://t.me/{BOT_USERNAME}?startgroup=true"}])
                    send_message(chat_id, "📢 <b>Select Your Group:</b> 👇", reply_markup={"inline_keyboard": rows}, parse_mode="HTML")
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("promogrp_"):
                telegram_request("answerCallbackQuery", {"callback_query_id": cb_id})
                gid = cb_data.replace("promogrp_", "").strip()
                fb_update_user(clicker_id, {"awaiting_promo_text_for": gid})
                send_message(chat_id, "📝 <b>Type Your Promotion Message Here in DM:</b> 👇", parse_mode="HTML")
                return jsonify({"status": "ok"}), 200

            if cb_data == "menu_feedback":
                telegram_request("answerCallbackQuery", {"callback_query_id": cb_id})
                fb_update_user(clicker_id, {"awaiting_feedback": True})
                send_message(chat_id, "✍️ <b>Send Feedback:</b> Apna feedback likh kar bhejo! 👇", parse_mode="HTML")
                return jsonify({"status": "ok"}), 200

            if cb_data == "menu_credits":
                telegram_request("answerCallbackQuery", {"callback_query_id": cb_id})
                u_data = fb_get_user(clicker_id)
                send_message(chat_id, f"💎 <b>VIP Credits: {u_data.get('credits', 15)}</b>\nNiche se plan choose karo:", reply_markup=get_payment_keyboard(), parse_mode="HTML")
                return jsonify({"status": "ok"}), 200

            telegram_request("answerCallbackQuery", {"callback_query_id": cb_id})
            return jsonify({"status": "ok"}), 200

        if "message" not in data: return jsonify({"status": "ok"}), 200
        msg = data["message"]
        chat_id = msg.get("chat", {}).get("id")
        text = str(msg.get("text") or "").strip()
        user_id = str(msg.get("from", {}).get("id", ""))
        full_name = f"{msg.get('from', {}).get('first_name', 'User')} {msg.get('from', {}).get('last_name', '')}".strip()
        is_owner = (user_id == OWNER_ID)
        replied_msg_obj = msg.get("reply_to_message") or {}
        replied_to_text = str(replied_msg_obj.get("text") or replied_msg_obj.get("caption") or "").strip()[:180]

        user_data = fb_get_user(user_id)
        credits_left = 999999 if is_owner else int(user_data.get("credits", 15))

        if text.lower().startswith("/start"):
            fb_update_user(user_id, {"history": [], "last_mode": "NORMAL", "active_rp": "", "user_gender": "male"})
            rows = [
                [{"text": "➕ Add Siya to Your Group", "url": f"https://t.me/{BOT_USERNAME}?startgroup=true"}],
                [{"text": "📢 Group Tag Promotion", "callback_data": "menu_promo"}],
                [{"text": "💎 VIP Chat Credits", "callback_data": "menu_credits"}, {"text": "✍️ Send Feedback", "callback_data": "menu_feedback"}],
                [{"text": "📢 Official Channel", "url": OFFICIAL_CHANNEL_URL}, {"text": "💬 More Groups", "url": MORE_GROUPS_URL}]
            ]
            send_message(chat_id, f"Hii {html.escape(msg.get('from', {}).get('first_name', 'Jaan'))}! ❤️ Main Aditi hoon. Kaise ho? Aao baatein karein 😊", parse_mode="HTML", reply_markup={"inline_keyboard": rows})
            return jsonify({"status": "ok"}), 200

        if user_data.get("awaiting_feedback") and text and not text.startswith("/"):
            fb_update_user(user_id, {"awaiting_feedback": False})
            telegram_request("sendMessage", {"chat_id": FEEDBACK_CHANNEL_ID, "text": f"🌟 <b>FEEDBACK</b>: {html.escape(text)}", "parse_mode": "HTML"})
            send_message(chat_id, "❤️ Thank you! Feedback bhej diya hai.", parse_mode="HTML")
            return jsonify({"status": "ok"}), 200

        if user_data.get("awaiting_promo_text_for") and text and not text.startswith("/"):
            gid = user_data["awaiting_promo_text_for"]
            try: requests.patch(f"{FIREBASE_URL}/group_promos/{gid}.json?auth={FIREBASE_SECRET}", json={"text": text, "owner_id": user_id, "active": False}, timeout=4)
            except Exception: pass
            fb_update_user(user_id, {"awaiting_promo_text_for": ""})
            send_message(chat_id, f"✅ <b>Promo Saved!</b> Plan select karo:", reply_markup=get_promo_plans_keyboard(gid), parse_mode="HTML")
            return jsonify({"status": "ok"}), 200

        if credits_left <= 0 and not is_owner and not any(w in text.lower() for w in SYSTEM_HELP_WORDS):
            send_message(chat_id, "Jaan, free chat credits khatam ho gaye hain! 🥺 Niche se recharge kar lo na... 🥰👇", parse_mode="HTML", reply_markup=get_payment_keyboard())
            return jsonify({"status": "limit_reached"}), 200

        # Direct Singing Trigger
        msg_low = text.lower()
        if any(p in msg_low for p in DIRECT_SING_TRIGGERS):
            send_typing(chat_id)
            telegram_request("sendChatAction", {"chat_id": chat_id, "action": "record_voice"}, timeout=3)
            real_lyrics, song_title = fetch_live_song_lyrics(text)
            raw_b, mime, ext = generate_gemini_native_voice(real_lyrics, voice_type="singing")
            if raw_b:
                requests.post(f"{API_URL}/sendVoice", data={"chat_id": chat_id, "caption": f"🎤🎶 <b>{html.escape(str(song_title))}</b> ❤️", "parse_mode": "HTML", "protect_content": "true"}, files={"voice": (ext, BytesIO(raw_b), mime)}, timeout=14)
            else:
                send_message(chat_id, f"🎤🎶 <b>{html.escape(str(song_title))}</b>\n\n<i>\"{html.escape(real_lyrics)}\"</i>", parse_mode="HTML")
            add_to_history(user_id, "user", text, "Private")
            add_to_history(user_id, "siya", f"[Maine '{song_title}' gaana gaakar sunaya]", "Private")
            if not is_owner: fb_update_user(user_id, {"credits": credits_left - 1})
            return jsonify({"status": "ok"}), 200

        # Chat execution
        reply_text, media_to_send, sticker_to_send, show_pay_kb, cur_mode = chat_with_siya(
            text, full_name, user_id, credits_left=credits_left, chat_type="private", replied_to_text=replied_to_text
        )

        kb = get_payment_keyboard() if show_pay_kb else None
        if media_to_send: send_secret_media(chat_id, media_to_send, caption=reply_text, reply_markup=kb)
        else:
            send_message(chat_id, reply_text, reply_markup=kb, parse_mode="HTML")
            if sticker_to_send: send_sticker(chat_id, sticker_to_send)

        wants_voice = any(w in msg_low for w in VOICE_REQUEST_TRIGGERS)
        if wants_voice or (cur_mode in ["ADULT", "ROMANTIC"] and random.randint(1, 100) <= 25):
            telegram_request("sendChatAction", {"chat_id": chat_id, "action": "record_voice"}, timeout=3)
            raw_b, m, ext = generate_gemini_native_voice(reply_text, voice_type="adult" if cur_mode == "ADULT" else "normal")
            if raw_b: requests.post(f"{API_URL}/sendVoice", data={"chat_id": chat_id, "caption": "🎙️💕", "protect_content": "true"}, files={"voice": (ext, BytesIO(raw_b), m)}, timeout=14)

        add_to_history(user_id, "user", text, "Private")
        add_to_history(user_id, "siya", reply_text, "Private")
        if not is_owner and not asks_system_help: fb_update_user(user_id, {"credits": credits_left - 1, "last_mode": cur_mode})

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print("WEBHOOK ERROR:", traceback.format_exc())
        return jsonify({"status": "error_handled"}), 200

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "online Siya VIP - Modular 2-File Architecture Active"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "80")), debug=False)
