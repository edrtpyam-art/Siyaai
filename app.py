from flask import Flask, request, jsonify
import os, requests, time, re, html, random, base64, struct, json, traceback
from urllib.parse import quote
from io import BytesIO
from threading import Timer, Thread, Event
from PIL import Image

app = Flask(__name__)

# ============================================================
# 1. CONFIG & VAULT SETUP
# ============================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip().strip('"').strip("'")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "hot_bhabhi_bot").strip().lstrip("@")
OWNER_ID = str(os.environ.get("OWNER_ID", "")).strip().strip('"').strip("'")

CASHFREE_APP_ID = os.environ.get("CASHFREE_APP_ID", "").strip().strip('"').strip("'")
CASHFREE_SECRET_KEY = os.environ.get("CASHFREE_SECRET_KEY", "").strip().strip('"').strip("'")
FIREBASE_URL = os.environ.get("FIREBASE_URL", "").strip().rstrip("/")
FIREBASE_SECRET = "8lTxEXOwEe5fjkh9zTHnBkzum6W0vrKcisbfqRf3"
FEEDBACK_CHANNEL_ID = "-1004290177402"

GITHUB_BASE_URL = "https://raw.githubusercontent.com/edrtpyam-art/Siyaai/main/"
OFFICIAL_CHANNEL_URL = "https://t.me/edrolai"
MORE_GROUPS_URL = "https://t.me/friendschatinggroup"

GROQ_KEYS = [k for k in [os.environ.get(f"GROQ_API_KEY{i}", "").strip().strip('"') for i in ["", "2", "3", "4"]] if k]
OPENROUTER_KEYS = [k for k in [os.environ.get(f"OPENROUTER_API_KEY{i}", "").strip().strip('"') for i in ["", "2"]] if k]
GEMINI_KEYS = [k for k in [os.environ.get(f"GEMINI_API_KEY{i}", "").strip().strip('"') for i in ["", "2", "3"]] if k]

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""
PLAN_CREDITS = {"9": 15, "19": 35, "29": 55, "49": 100, "99": 250, "179": 500}
USER_CACHE = {}
processed_updates = set()

PHOTO_VAULT = {
    "bodes": ["private1.jpg", "private2.jpg", "private3.jpg", "private4.jpg", "video.mp4", "video2.mp4"],
    "chut": ["open1.jpg", "open2.jpg", "opan3.jpg", "video4.mp4", "video5.mp4"],
    "gand": ["bom1.jpg", "bom2.jpg", "video6.mp4", "video7.mp4"],
    "kiss": ["kiss.jpg"], "simplepic": ["simplepic.jpg"]
}
HOT_STICKER_PACKS = ["HandVideoR_by_stickersthiefbot", "Custom2224_by_fStikBot", "Love9_Wallgif", "mmm_by_hhujhybot"]
STICKER_CACHE = {}

def mark_seen(key):
    if not key: return False
    if key in processed_updates: return True
    processed_updates.add(key)
    if len(processed_updates) > 2000: processed_updates.pop()
    return False

# ============================================================
# 2. TELEGRAM HELPERS
# ============================================================
def tg_req(method, payload=None, timeout=6):
    if not API_URL: return {"ok": False}
    try: return requests.post(f"{API_URL}/{method}", json=payload or {}, timeout=timeout).json()
    except Exception: return {"ok": False}

def send_msg(cid, text, reply_id=None, markup=None):
    p = {"chat_id": cid, "text": str(text or ""), "parse_mode": "HTML"}
    if reply_id: p["reply_to_message_id"] = reply_id
    if markup: p["reply_markup"] = markup
    r = tg_req("sendMessage", p)
    if not r.get("ok"): p.pop("parse_mode", None); r = tg_req("sendMessage", p)
    return r

def send_stk(cid, sid, reply_id=None):
    return tg_req("sendSticker", {"chat_id": cid, "sticker": sid, "reply_to_message_id": reply_id}) if sid else {"ok": False}

def get_hot_sticker():
    packs = list(HOT_STICKER_PACKS)
    random.shuffle(packs)
    for pk in packs[:2]:
        if pk in STICKER_CACHE and STICKER_CACHE[pk]: return random.choice(STK if (STK:=STICKER_CACHE[pk]) else [])
        r = tg_req("getStickerSet", {"name": pk}, timeout=2.5)
        if r.get("ok"):
            stks = [s["file_id"] for s in r.get("result", {}).get("stickers", []) if s.get("file_id")]
            if stks: STICKER_CACHE[pk] = stks; return random.choice(stks)
    return None

def get_media_item(tag, prefer_video=False):
    if not tag: tag = "bodes"
    t = str(tag).lower().strip()
    if t in ["boom", "bom", "ass", "back"]: t = "gand"
    elif t in ["private", "privatepic", "nudes", "body", "boobs"]: t = "bodes"
    elif t in ["open", "opan", "pussy", "front", "chut"]: t = "chut"
    cands = PHOTO_VAULT.get(f"{t}_video", []) if prefer_video and f"{t}_video" in PHOTO_VAULT else PHOTO_VAULT.get(t, PHOTO_VAULT.get("bodes", []))
    return random.choice(cands) if cands else "private1.jpg"

def send_secret_media(cid, fname, caption="", delete_after=15, reply_id=None, markup=None):
    if not fname: return {"ok": False}
    is_vid = str(fname).lower().endswith(".mp4")
    method, m_key = ("sendVideo", "video") if is_vid else ("sendPhoto", "photo")
    url = fname if str(fname).startswith("http") else GITHUB_BASE_URL + fname
    p = {"chat_id": cid, m_key: url, "caption": str(caption or ""), "protect_content": True, "has_spoiler": True, "parse_mode": "HTML"}
    if reply_id: p["reply_to_message_id"] = reply_id
    if markup: p["reply_markup"] = markup
    r = tg_req(method, p, timeout=10)
    if r.get("ok") and delete_after > 0:
        mid = r.get("result", {}).get("message_id")
        if mid: Timer(delete_after, lambda: tg_req("deleteMessage", {"chat_id": cid, "message_id": mid})).start()
    return r

def get_file_b64(file_id):
    if not file_id: return None
    res = tg_req("getFile", {"file_id": file_id}, timeout=4)
    if res.get("ok"):
        try:
            r = requests.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{res['result']['file_path']}", timeout=4)
            if r.ok:
                img = Image.open(BytesIO(r.content))
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                    bg.paste(img.convert("RGBA"), mask=img.split()[3])
                else: bg.paste(img.convert("RGB"))
                out = BytesIO(); bg.save(out, format="JPEG", quality=92)
                return base64.b64encode(out.getvalue()).decode("utf-8")
        except Exception: pass
    return None

def get_pay_kb():
    return {"inline_keyboard": [
        [{"text": "🔥 ₹9 (15 Chats)", "callback_data": "buy_9"}, {"text": "⚡ ₹19 (35 Chats)", "callback_data": "buy_19"}],
        [{"text": "💎 ₹29 (55 Chats)", "callback_data": "buy_29"}, {"text": "💎 ₹49 (100 Chats)", "callback_data": "buy_49"}],
        [{"text": "👑 ₹99 (250 Chats)", "callback_data": "buy_99"}, {"text": "🚀 ₹179 (500 Chats)", "callback_data": "buy_179"}]
    ]}

def get_main_menu_kb(cdisp):
    return {"inline_keyboard": [
        [{"text": f"🎁 Free Credits: {cdisp}", "callback_data": "menu_credits"}],
        [{"text": "✍️ Feedback", "callback_data": "menu_feedback"}, {"text": "📢 Official Channel", "url": OFFICIAL_CHANNEL_URL}],
        [{"text": "💬 More Groups", "url": MORE_GROUPS_URL}],
        [{"text": "🔥 ₹9 (15 Chats)", "callback_data": "buy_9"}, {"text": "⚡ ₹19 (35 Chats)", "callback_data": "buy_19"}],
        [{"text": "💎 ₹29 (55 Chats)", "callback_data": "buy_29"}, {"text": "💎 ₹49 (100 Chats)", "callback_data": "buy_49"}],
        [{"text": "👑 ₹99 (250 Chats)", "callback_data": "buy_99"}, {"text": "🚀 ₹179 (500 Chats)", "callback_data": "buy_179"}]
    ]}

# ============================================================
# 3. FIREBASE MEMORY
# ============================================================
def fb_get_user(uid):
    uid = str(uid)
    if uid in USER_CACHE: return USER_CACHE[uid]
    d = {"credits": 12, "awaiting_payment": "", "history": [], "active_rp": "", "awaiting_feedback": False}
    if FIREBASE_URL:
        try:
            r = requests.get(f"{FIREBASE_URL}/users/{uid}.json?auth={FIREBASE_SECRET}", timeout=2.5).json()
            if isinstance(r, dict):
                if "credits" not in r: r["credits"] = max(0, 12 - int(r.get("msg_count") or 0))
                for k, v in d.items():
                    if k not in r or r[k] is None: r[k] = v
                USER_CACHE[uid] = r; return r
        except Exception: pass
    USER_CACHE[uid] = d; return d

def fb_update_user(uid, data):
    uid = str(uid)
    if uid in USER_CACHE: USER_CACHE[uid].update(data)
    if FIREBASE_URL:
        try: requests.patch(f"{FIREBASE_URL}/users/{uid}.json?auth={FIREBASE_SECRET}", json=data, timeout=2.5)
        except Exception: pass

def add_to_history(uid, role, text):
    if len(str(text or "").strip()) < 2: return
    u = fb_get_user(uid); h = u.get("history") or []
    if h and h[-1]["text"] == text: return
    h.append({"role": role, "text": str(text).strip()})
    if len(h) > 25: h = h[-25:]
    u["history"] = h; fb_update_user(uid, {"history": h})

# ============================================================
# 4. CASHFREE PAYMENT
# ============================================================
@app.route("/api/pay/<session_id>", methods=["GET"])
def cashfree_checkout_page(session_id):
    mode = "sandbox" if (CASHFREE_APP_ID.upper().startswith("TEST") or "TEST" in CASHFREE_SECRET_KEY.upper()) else "production"
    order_id = request.args.get("order_id", "")
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>VIP UPI</title><script src="https://telegram.org/js/telegram-web-app.js"></script><script src="https://sdk.cashfree.com/js/v3/cashfree.js"></script><style>body{{background:#0f0f14;color:#fff;text-align:center;padding:20px;font-family:sans-serif;display:flex;flex-direction:column;justify-content:center;height:95vh;margin:0;}} .card{{background:#1b1b24;padding:25px;border-radius:16px;border:1px solid #ff1493;}} .btn{{background:linear-gradient(135deg,#ff1493,#ff69b4);color:#fff;border:none;padding:15px;border-radius:12px;width:100%;font-size:18px;font-weight:bold;margin-top:18px;cursor:pointer;}}</style></head><body><div class="card"><h2 style="color:#ff1493;margin-top:0;">💖 VIP Instant UPI</h2><p id="msg">Opening UPI App...</p><button class="btn" onclick="startPay()">💳 Pay Now with UPI</button></div><script>if(window.Telegram&&window.Telegram.WebApp){{window.Telegram.WebApp.ready();window.Telegram.WebApp.expand();}}const cf=Cashfree({{mode:"{mode}"}});function startPay(){{cf.checkout({{paymentSessionId:"{html.escape(session_id)}",redirectTarget:"_modal"}}).then(res=>{{if(res.paymentDetails||res.redirect){{document.getElementById("msg").innerText="✅ Verifying...";fetch("/api/cf_verify?order_id={html.escape(order_id)}").then(r=>r.json()).then(d=>{{if(d.paid&&window.Telegram&&window.Telegram.WebApp)window.Telegram.WebApp.close();}});}}}});}}window.onload=function(){{setTimeout(startPay,300);}};</script></body></html>""", 200, {"Content-Type": "text/html"}

@app.route("/api/cf_verify", methods=["GET", "POST"])
def cf_verify_endpoint():
    order_id = request.args.get("order_id", "")
    if not order_id and request.is_json:
        d = request.get_json(silent=True) or {}
        order_id = d.get("data", {}).get("order", {}).get("order_id", "")
    if not order_id or mark_seen(f"cf_paid:{order_id}"): return jsonify({"paid": False}), 200
    is_test = CASHFREE_APP_ID.upper().startswith("TEST")
    try:
        r = requests.get(f"https://{'sandbox' if is_test else 'api'}.cashfree.com/pg/orders/{order_id}", headers={"x-client-id": CASHFREE_APP_ID, "x-client-secret": CASHFREE_SECRET_KEY, "x-api-version": "2023-08-01"}, timeout=5)
        if r.ok and r.json().get("order_status") == "PAID":
            tags = r.json().get("order_tags") or {}
            uid, amt = str(tags.get("user_id") or ""), str(tags.get("amount") or "9")
            if uid:
                u = fb_get_user(uid)
                add_c = PLAN_CREDITS.get(amt, 15)
                tot = max(0, int(u.get("credits") or 0)) + add_c
                fb_update_user(uid, {"credits": tot, "awaiting_payment": ""})
                send_msg(uid, f"✅ <b>Instant UPI Payment Verified!</b>\n\nTumhara ₹{amt} ka plan activate ho gaya hai aur <b>+{add_c} VIP Chat Credits</b> add ho gaye hain (Total: {tot} Chats)! Chalo ab khul ke baatein karte hain... 😘🔥")
            return jsonify({"paid": True}), 200
    except Exception: pass
    return jsonify({"paid": False}), 200

def create_cf_order(uid, uname, amt):
    if not CASHFREE_APP_ID or not CASHFREE_SECRET_KEY: return None
    ts = int(time.time()); oid = f"ORD_{uid}_{amt}_{ts}"[:38]
    clean_name = re.sub(r"[^a-zA-Z0-9\s]", "", str(uname) or "VIP").strip() or "VIP"
    host = request.host_url.rstrip("/") if request else "https://siyaai.vercel.app"
    p = {"order_id": oid, "order_amount": float(amt), "order_currency": "INR", "customer_details": {"customer_id": f"CUST_{uid}", "customer_phone": "9999999999", "customer_name": clean_name}, "order_meta": {"return_url": f"https://t.me/{BOT_USERNAME}", "notify_url": f"{host}/api/cf_verify"}, "order_tags": {"user_id": str(uid), "amount": str(amt)}}
    try:
        r = requests.post("https://sandbox.cashfree.com/pg/orders" if CASHFREE_APP_ID.upper().startswith("TEST") else "https://api.cashfree.com/pg/orders", headers={"x-client-id": CASHFREE_APP_ID, "x-client-secret": CASHFREE_SECRET_KEY, "x-api-version": "2023-08-01", "Content-Type": "application/json"}, json=p, timeout=5)
        if r.ok and r.json().get("payment_session_id"): return f"{host}/api/pay/{r.json()['payment_session_id']}?order_id={oid}"
    except Exception: pass
    return None

# ============================================================
# 5. VOICE ENGINE (AOEDE NATIVE)
# ============================================================
def generate_voice(text):
    if not GEMINI_KEYS: return None, None, None
    clean = re.sub(r"<.*?>", "", str(text)).strip()
    clean = re.sub(r"[^\w\s.,!?~'-]", " ", clean)
    for pat, rep in {r"\bchut\b": "chuu-t", r"\blund\b": "laan-d", r"\bsex\b": "romance"}.items(): clean = re.sub(pat, rep, clean, flags=re.I)
    prompt = f"CRITICAL: You are a passionate Indian woman in an intimate bedroom. Speak ONLY these Hinglish lines with seductive breathiness and soft sighs:\n{clean}"
    for key in GEMINI_KEYS[:1]:
        for model in ["gemini-2.0-flash", "gemini-2.5-flash"]:
            try:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", headers={"x-goog-api-key": key}, json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Aoede"}}}}}, timeout=9)
                if r.ok and r.json().get("candidates"):
                    for p in r.json()["candidates"][0]["content"]["parts"]:
                        if p.get("inlineData", {}).get("data"):
                            raw = base64.b64decode(p["inlineData"]["data"])
                            return struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + len(raw), b"WAVE", b"fmt ", 16, 1, 1, 24000, 48000, 2, 16, b"data", len(raw)) + raw, "audio/wav", "voice.wav"
            except Exception: pass
    return None, None, None

# ============================================================
# 6. AI CORE WITH STRICT ANTI-REPETITION POOL
# ============================================================
def call_compat(url, key, model, msgs):
    try:
        r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json={"model": model, "messages": msgs, "temperature": 0.85, "max_tokens": 400}, timeout=5)
        if r.ok and r.json().get("choices"):
            ans = str(r.json()["choices"][0]["message"]["content"] or "").strip()
            ans = re.sub(r"<think>.*?</think>", "", ans, flags=re.DOTALL).strip()
            if len(ans) > 2: return ans
    except Exception: pass
    return None

def chat_ai(text, uname, uid, credits_left, is_owner, media_b64=None):
    u = fb_get_user(uid)
    hist = u.get("history", [])
    msg_low = text.lower()

    asks_media = any(w in msg_low for w in ["photo", "pic", "image", "dikhao", "dikha", "bhejo", "bhej", "send", "chut", "bodes", "gand"])
    
    last_bot_replies = [m["text"] for m in hist[-6:] if m["role"] == "siya"]
    anti_repeat_block = f"\n- ABSOLUTE RULE: DO NOT repeat any of these recent replies: {last_replies}. Your response must be 100% brand new and dynamic!" if last_bot_replies else ""

    sys = f"""You are Hot Bhabhi, a bold, seductive, and deeply passionate Indian woman chatting with your partner ({uname}).
CRITICAL RULES FOR OPEN CHAT:
1. NO REFUSAL & NO DRAMA: Never get angry, shy, or refuse! Be 100% open and consenting to any dirty talk or roleplay.
2. FORCE PHOTO TAG ON REQUEST: If user asks for photo/video/chut/bodes, you MUST include the exact tag at the very end of your response: `[PHOTO: chut]` or `[PHOTO: bodes]` or `[PHOTO: gand]`.
3. LENGTH: Keep replies strictly to 1 or 2 short, hot sentences (Max 25 words). Never write long stories!
4. LANGUAGE: Match his Desi Hinglish/English style with extreme heat. Use female grammar ("karungi", "meri").{anti_repeat_block}
"""

    if media_b64:
        v_prompt = f"Look at this sticker/photo. React seductively in first-person as his hot partner (1-2 Hinglish sentences). Context: {text}"
        for key in GROQ_KEYS[:1]:
            for vm in ["meta-llama/llama-4-scout-17b-16e-instruct"]:
                ans = call_compat("https://api.groq.com/openai/v1/chat/completions", key, vm, [{"role": "system", "content": sys}, {"role": "user", "content": [{"type": "text", "text": v_prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{media_b64}"}}]}])
                if ans: break
            if ans: break

    msgs = [{"role": "system", "content": sys}]
    for h in hist[-15:]: msgs.append({"role": "assistant" if h.get("role") == "siya" else "user", "content": h.get("text")})
    msgs.append({"role": "user", "content": text})

    ans = None
    for key in GEMINI_KEYS[:1]:
        for gm in ["gemini-2.0-flash", "gemini-2.5-flash"]:
            try:
                p = {"systemInstruction": {"parts": [{"text": sys}]}, "contents": [{"role": "user", "parts": [{"text": f"User says: {text}\nReply uniquely in 1-2 hot Hinglish sentences:"}]}], "generationConfig": {"temperature": 0.85, "maxOutputTokens": 400}, "safetySettings": [{"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"}, {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}]}
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{gm}:generateContent", headers={"x-goog-api-key": key}, json=p, timeout=5)
                if r.ok and r.json().get("candidates"):
                    ans = "\n".join(pt.get("text", "") for pt in r.json()["candidates"][0]["content"]["parts"] if not pt.get("thought")).strip()
                    if len(ans) > 2 and ans not in last_bot_replies: break
            except Exception: pass
        if ans: break

    if not ans:
        for key in GROQ_KEYS[:1]:
            ans = call_compat("https://api.groq.com/openai/v1/chat/completions", key, "llama-3.3-70b-versatile", msgs)
            if ans and ans not in last_bot_replies: break

    # Fallback pool if everything fails
    if not ans or ans in last_bot_replies:
        fallback_pool = [
            f"Arey {uname} jaan, itna kya sharma rahe ho? Khul ke batao ab kya karne ka mann hai? 🔥",
            f"Uff {uname}, tumhari baatein sunke aur garmi badh rahi hai... aao na paas! 🥵💋",
            f"Haan meri jaan, aaj raat sirf hum dono ki hai... jo dil mein hai wo karo na! 😘",
            f"Suno na {uname} baby, aise chup mat raho... mujhe apni baahon mein bhar lo! 😉❤️"
        ]
        ans = random.choice([f for f in fallback_pool if f not in last_bot_replies] or fallback_pool)

    # Extract Photo Tag
    photo_tag = None
    pm = re.search(r"\[PHOTO:\s*([a-zA-Z0-9_]+)\]", ans, re.I)
    if pm:
        photo_tag = pm.group(1).lower()
        ans = re.sub(r"\[PHOTO:\s*[a-zA-Z0-9_]+\]", "", ans, flags=re.I).strip()
    elif asks_media:
        photo_tag = "chut" if any(w in msg_low for w in ["chut", "pussy"]) else "bodes"

    ans = re.sub(r"^(?:Bhabhi:|Siya:|Me:)\s*", "", ans, flags=re.I).strip()
    return ans, photo_tag, get_hot_sticker()

# ============================================================
# 7. WEBHOOK
# ============================================================
@app.route("/api/bot", methods=["POST"])
def webhook():
    try:
        data = request.get_json(silent=True)
        if not data or mark_seen(f"upd:{data.get('update_id')}"): return jsonify({"status": "ok"}), 200

        if "callback_query" in data:
            cb = data["callback_query"]
            uid, cid, cb_data = str(cb["from"]["id"]), cb["message"]["chat"]["id"], cb.get("data", "")
            is_own = (uid == OWNER_ID)
            if cb_data.startswith("buy_"):
                if is_own:
                    tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "👑 Owner Unlimited VIP!", "show_alert": True})
                    return jsonify({"status": "ok"}), 200
                amt = cb_data.replace("buy_", "")
                if amt in PLAN_CREDITS:
                    url = create_cf_order(uid, cb["from"].get("first_name", "User"), amt)
                    tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "Opening UPI..."})
                    if url: send_msg(cid, f"💎 <b>Pay ₹{amt}</b>", markup={"inline_keyboard": [[{"text": f"💳 Pay ₹{amt} Now", "web_app": {"url": url}}]]})
            elif cb_data == "menu_credits":
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                send_msg(cid, f"💎 Credits: {'Unlimited 👑' if is_own else fb_get_user(uid).get('credits', 12)}", markup=get_pay_kb())
            elif cb_data == "menu_feedback":
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                fb_update_user(uid, {"awaiting_feedback": True})
                send_msg(cid, "✍️ Send feedback:")
            return jsonify({"status": "ok"}), 200

        if "message" not in data: return jsonify({"status": "ok"}), 200
        msg = data["message"]
        cid, uid, fname = msg["chat"]["id"], str(msg["from"]["id"]), msg["from"].get("first_name", "Jaan")
        text = str(msg.get("text") or "").strip()
        is_own = (uid == OWNER_ID)

        u = fb_get_user(uid)
        credits = int(u.get("credits", 12))

        if u.get("awaiting_feedback") and text and not text.startswith("/"):
            fb_update_user(uid, {"awaiting_feedback": False})
            send_msg(FEEDBACK_CHANNEL_ID, f"🌟 Feedback from {fname}:\n{text}")
            send_msg(cid, "❤️ Thank you!")
            return jsonify({"status": "ok"}), 200

        if text.lower().startswith(("/start", "/reset", "/credits", "/menu")):
            if text.lower().startswith("/reset"): fb_update_user(uid, {"history": [], "active_rp": ""})
            send_msg(cid, f"Hii {fname}! 🔥", markup=get_main_menu_kb("Unlimited 👑" if is_own else credits))
            send_msg(cid, "Aao na jaan, batao kya karne ka mann hai? 😘")
            return jsonify({"status": "ok"}), 200

        if not is_own and credits <= 0:
            send_msg(cid, "Credits khatam ho gaye! Recharge karo:", markup=get_pay_kb())
            return jsonify({"status": "ok"}), 200

        tg_req("sendChatAction", {"chat_id": cid, "action": "typing"}, timeout=2)

        b64 = None
        if "photo" in msg or "sticker" in msg:
            fid = msg["photo"][-1]["file_id"] if "photo" in msg else msg["sticker"].get("file_id")
            b64 = get_file_b64(fid)

        ans, pt, stk = chat_ai(msg.get("caption") or text or "Hi", fname, uid, credits, is_own, b64)

        if pt:
            send_secret_media(cid, get_media_item(pt), caption=ans, reply_id=msg.get("message_id"))
        else:
            send_msg(cid, ans, reply_id=msg.get("message_id"))
            if stk: send_stk(cid, stk, reply_id=msg.get("message_id"))

        if random.randint(1, 100) <= 25:
            tg_req("sendChatAction", {"chat_id": cid, "action": "record_voice"}, timeout=2)
            aud_b, m, ext = generate_voice(ans)
            if aud_b: requests.post(f"{API_URL}/sendVoice", data={"chat_id": cid}, files={"voice": (ext, BytesIO(aud_b), m)}, timeout=10)

        add_to_history(uid, "user", text or "[Media]")
        add_to_history(uid, "siya", ans)
        if not is_own: fb_update_user(uid, {"credits": max(0, credits - 1)})

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"status": "error"}), 200

# ============================================================
# 8. LANDING PAGE
# ============================================================
@app.route("/", methods=["GET"])
def health_check():
    return """<!DOCTYPE html><html><head><title>Edrol AI</title></head><body style="background:#0b1020;color:#fff;text-align:center;padding:50px;font-family:sans-serif;"><h1>Edrol AI Services Online</h1><p>Powered by Edrol Server</p></body></html>""", 200, {"Content-Type": "text/html; charset=utf-8"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "80")), debug=False)
