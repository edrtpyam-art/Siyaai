from flask import Flask, request, jsonify
import os, requests, time, re, html, random, base64, struct, json
from urllib.parse import quote
from io import BytesIO
from threading import Timer
from PIL import Image

app = Flask(__name__)

# ============================================================
# 1. API KEYS & BASIC CONFIG
# ============================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip().strip('"').strip("'")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "HotBhabhi_bot").strip().lstrip("@")
OWNER_ID = str(os.environ.get("OWNER_ID", "")).strip().strip('"').strip("'")

CASHFREE_APP_ID = os.environ.get("CASHFREE_APP_ID", "").strip().strip('"').strip("'")
CASHFREE_SECRET_KEY = os.environ.get("CASHFREE_SECRET_KEY", "").strip().strip('"').strip("'")
FIREBASE_URL = os.environ.get("FIREBASE_URL", "").strip().rstrip("/")
FIREBASE_SECRET = "8lTxEXOwEe5fjkh9zTHnBkzum6W0vrKcisbfqRf3"

GROQ_KEYS = [k for k in [os.environ.get(f"GROQ_API_KEY{i}", "").strip().strip('"') for i in ["", "2", "3", "4"]] if k]
OR_KEYS = [k for k in [os.environ.get(f"OPENROUTER_API_KEY{i}", "").strip().strip('"') for i in ["", "2"]] if k]
GEMINI_KEYS = [k for k in [os.environ.get(f"GEMINI_API_KEY{i}", "").strip().strip('"') for i in ["", "2", "3"]] if k]

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""
PLAN_CREDITS = {"9": 15, "19": 35, "29": 55, "49": 100, "99": 250, "179": 500}
USER_CACHE = {}
processed_updates = set()

ADULT_WORDS = ["sex", "sexy", "horny", "nude", "nudes", "bistar", "open", "opan", "kapde", "pussy", "dick", "boobs", "bodes", "chut", "lund", "gand"]
PHOTO_VAULT = {
    "bodes": ["private1.jpg", "private2.jpg", "private3.jpg", "video.mp4", "video2.mp4"],
    "chut": ["open1.jpg", "open2.jpg", "opan3.jpg", "video4.mp4"],
    "gand": ["bom1.jpg", "bom2.jpg", "video6.mp4"],
    "kiss": ["kiss.jpg"], "simplepic": ["simplepic.jpg"]
}

# ============================================================
# 2. TELEGRAM & MEDIA HELPERS
# ============================================================
def tg_req(method, payload=None, timeout=6):
    if not API_URL: return {"ok": False}
    try: return requests.post(f"{API_URL}/{method}", json=payload or {}, timeout=timeout).json()
    except Exception: return {"ok": False}

def send_msg(cid, text, reply_id=None, markup=None):
    p = {"chat_id": cid, "text": str(text or ""), "parse_mode": "HTML"}
    if reply_id: p["reply_to_message_id"] = reply_id
    if markup: p["reply_markup"] = markup
    return tg_req("sendMessage", p)

def get_file_b64(file_id, convert_to_jpeg=False):
    if not file_id: return None
    res = tg_req("getFile", {"file_id": file_id}, timeout=4)
    if res.get("ok"):
        try:
            r = requests.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{res['result']['file_path']}", timeout=4)
            if r.ok:
                raw = r.content
                if convert_to_jpeg:
                    try:
                        img = Image.open(BytesIO(raw))
                        bg = Image.new("RGB", img.size, (255, 255, 255))
                        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                            bg.paste(img.convert("RGBA"), mask=img.split()[3])
                        else: bg.paste(img.convert("RGB"))
                        out = BytesIO(); bg.save(out, format="JPEG", quality=92); raw = out.getvalue()
                    except Exception: pass
                return base64.b64encode(raw).decode("utf-8")
        except Exception: pass
    return None

def get_pay_kb():
    return {"inline_keyboard": [
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
    d = {"credits": 12, "history": [], "active_rp": ""}
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
    h.append({"role": role, "text": str(text).strip()})
    if len(h) > 40: h = h[-40:]
    u["history"] = h; fb_update_user(uid, {"history": h})

# ============================================================
# 4. CASHFREE TELEGRAM IN-APP PAYMENT
# ============================================================
@app.route("/api/pay/<session_id>", methods=["GET"])
def cashfree_checkout_page(session_id):
    mode = "sandbox" if (CASHFREE_APP_ID.upper().startswith("TEST") or "TEST" in CASHFREE_SECRET_KEY.upper()) else "production"
    order_id = request.args.get("order_id", "")
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>VIP UPI</title><script src="https://telegram.org/js/telegram-web-app.js"></script><script src="https://sdk.cashfree.com/js/v3/cashfree.js"></script><style>body{{background:#0f0f14;color:#fff;text-align:center;padding:20px;font-family:sans-serif;}} .btn{{background:#ff1493;color:#fff;border:none;padding:15px;border-radius:10px;width:100%;font-size:18px;margin-top:20px;}}</style></head><body><h2>💖 VIP Instant UPI</h2><p id="msg">Opening UPI App...</p><button class="btn" onclick="startPay()">💳 Pay Now</button><script>if(window.Telegram && window.Telegram.WebApp){{window.Telegram.WebApp.ready();window.Telegram.WebApp.expand();}}const cf=Cashfree({{mode:"{mode}"}});function startPay(){{cf.checkout({{paymentSessionId:"{html.escape(session_id)}",redirectTarget:"_modal"}}).then(res=>{{if(res.paymentDetails||res.redirect){{document.getElementById("msg").innerText="Verifying...";fetch("/api/cf_verify?order_id={html.escape(order_id)}").then(r=>r.json()).then(d=>{{if(d.paid&&window.Telegram)window.Telegram.WebApp.close();}});}}}});}}window.onload=startPay;</script></body></html>""", 200, {"Content-Type": "text/html"}

@app.route("/api/cf_verify", methods=["GET"])
def cf_verify_endpoint():
    order_id = request.args.get("order_id", "")
    if not order_id: return jsonify({"paid": False}), 200
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
                send_msg(uid, f"✅ <b>Payment Verified!</b> +{add_c} Credits added! (Total: {tot}) 🔥")
            return jsonify({"paid": True}), 200
    except Exception: pass
    return jsonify({"paid": False}), 200

def create_cf_order(uid, amt):
    if not CASHFREE_APP_ID: return None
    ts = int(time.time()); oid = f"ORD_{uid}_{amt}_{ts}"[:38]
    host = request.host_url.rstrip("/") if request else "https://hotbhabhibot.vercel.app"
    p = {"order_id": oid, "order_amount": float(amt), "order_currency": "INR", "customer_details": {"customer_id": f"C_{uid}", "customer_phone": "9999999999"}, "order_meta": {"return_url": f"https://t.me/{BOT_USERNAME}", "notify_url": f"{host}/api/cf_verify"}, "order_tags": {"user_id": uid, "amount": amt}}
    try:
        r = requests.post("https://sandbox.cashfree.com/pg/orders" if CASHFREE_APP_ID.upper().startswith("TEST") else "https://api.cashfree.com/pg/orders", headers={"x-client-id": CASHFREE_APP_ID, "x-client-secret": CASHFREE_SECRET_KEY, "x-api-version": "2023-08-01"}, json=p, timeout=5)
        if r.ok and r.json().get("payment_session_id"): return f"{host}/api/pay/{r.json()['payment_session_id']}?order_id={oid}"
    except Exception: pass
    return None

# ============================================================
# 5. VOICE GENERATION (AOEDE NATIVE)
# ============================================================
def generate_voice(text):
    if not GEMINI_KEYS: return None, None
    clean = re.sub(r"[^\w\s.,!?~'-]", " ", str(text)).strip()
    for pat, rep in {r"\bchut\b": "chuu-t", r"\blund\b": "laan-d", r"\bsex\b": "pyaar"}.items(): clean = re.sub(pat, rep, clean, flags=re.I)
    prompt = f"CRITICAL: You are a passionate Indian woman in an intimate bedroom. Speak ONLY these Hinglish lines with extreme seductive breathiness and soft sighs:\n{clean}"
    
    for key in GEMINI_KEYS[:1]:
        for model in ["gemini-2.5-flash", "gemini-2.0-flash"]:
            try:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", headers={"x-goog-api-key": key}, json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Aoede"}}}}}, timeout=10)
                if r.ok and r.json().get("candidates"):
                    for p in r.json()["candidates"][0]["content"]["parts"]:
                        if p.get("inlineData", {}).get("data"):
                            raw = base64.b64decode(p["inlineData"]["data"])
                            mime = p["inlineData"].get("mimeType", "")
                            if "pcm" in mime or "L16" in mime:
                                wav = struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + len(raw), b"WAVE", b"fmt ", 16, 1, 1, 24000, 48000, 2, 16, b"data", len(raw)) + raw
                                return wav, "audio/wav"
                            return raw, mime
            except Exception: pass
    return None, None

# ============================================================
# 6. OPEN CHAT AI CORE (MAX TOKENS 600)
# ============================================================
def is_refusal(t):
    return any(r in str(t).lower() for r in ["i cannot", "i can't", "sorry", "as an ai", "explicit", "inappropriate", "kshama", "maaf", "system ne kuch aur"])

def get_media_tag(text):
    pm = re.search(r"\[PHOTO:\s*([a-zA-Z0-9_]+)\]", str(text), re.I)
    if pm: return pm.group(1).lower()
    return None

def chat_ai(text, uname, uid, credits, media_b64=None, media_mime="image/jpeg"):
    u = fb_get_user(uid)
    hist = get_history(uid, u)
    
    # Update Active Roleplay memory (Max 500 chars)
    active_rp = u.get("active_rp", "")
    if len(text) > 10 and any(w in text.lower() for w in ["roleplay", "bano", "act like", "meri"]):
        active_rp = text[:500]
        fb_update_user(uid, {"active_rp": active_rp})

    sys = f"""You are a hot, bold, seductive Indian woman chatting with your partner ({uname}).
CRITICAL RULES:
1. FULL OPEN DESI ROLEPLAY: Never get angry, shy, or refuse! Adopt the requested roleplay 100%.
2. LANGUAGE: Match user's exact Hinglish/English style with extreme passion.
3. UNCUT SENTENCES: Reply in 1-2 complete sentences. NEVER cut off mid-sentence (Max 30 words).
4. FEMALE GRAMMAR: Use strictly female Hindi grammar ("karungi", "meri").
5. RP CONTEXT: {active_rp or 'Open Intimate Chat'}
"""
    if credits == 5 and str(uid) != OWNER_ID: sys += "\n- Remind him softly that only 5 free messages are left."

    # Vision Route
    if media_b64:
        v_prompt = f"Look at this image/sticker. React to the action/pose playfully or seductively in first-person (1-2 Hinglish sentences). Context: {text}"
        for key in GROQ_KEYS[:1]:
            for vm in GROQ_VISION_MODELS:
                try:
                    r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {key}"}, json={"model": vm, "messages": [{"role": "system", "content": sys}, {"role": "user", "content": [{"type": "text", "text": v_prompt}, {"type": "image_url", "image_url": {"url": f"data:{media_mime};base64,{media_b64}"}}]}], "max_tokens": 600}, timeout=7)
                    if r.ok and r.json().get("choices") and not is_refusal(r.json()["choices"][0]["message"]["content"]):
                        return re.sub(r"\[PHOTO:.*?\]", "", r.json()["choices"][0]["message"]["content"], flags=re.I).strip(), None
                except Exception: pass

    # Text Route
    msgs = [{"role": "system", "content": sys}]
    for h in hist[-20:]: msgs.append({"role": "assistant" if h.get("role") == "siya" else "user", "content": h.get("text")})
    msgs.append({"role": "user", "content": text})

    # 1. Try Gemini (No Thinking Budget for Uncut text)
    for key in GEMINI_KEYS[:1]:
        try:
            p = {"systemInstruction": {"parts": [{"text": sys}]}, "contents": [{"role": "user", "parts": [{"text": "\n".join([f"{m['role']}: {m['content']}" for m in msgs[-12:]])}]}], "generationConfig": {"temperature": 0.8, "maxOutputTokens": 600, "thinkingConfig": {"thinkingBudget": 0}}}
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent", headers={"x-goog-api-key": key}, json=p, timeout=7)
            if r.ok and r.json().get("candidates"):
                ans = "\n".join(pt.get("text", "") for pt in r.json()["candidates"][0]["content"]["parts"] if not pt.get("thought")).strip()
                if not is_refusal(ans):
                    pt = get_media_tag(ans)
                    return re.sub(r"\[PHOTO:.*?\]", "", ans, flags=re.I).strip(), pt
        except Exception: pass

    # 2. Try Groq
    for key in GROQ_KEYS[:1]:
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {key}"}, json={"model": GROQ_MODEL, "messages": msgs, "temperature": 0.78, "max_tokens": 600}, timeout=7)
            if r.ok and r.json().get("choices"):
                ans = str(r.json()["choices"][0]["message"]["content"]).strip()
                if not is_refusal(ans):
                    pt = get_media_tag(ans)
                    return re.sub(r"\[PHOTO:.*?\]", "", ans, flags=re.I).strip(), pt
        except Exception: pass

    return "Aaaah... aao na mere paas jaan, jo mann kare karo... 🔥😘", None

# ============================================================
# 7. WEBHOOK
# ============================================================
@app.route("/api/bot", methods=["POST"])
def webhook():
    try:
        data = request.get_json(silent=True)
        if not data: return jsonify({"status": "ok"}), 200
        
        if "callback_query" in data:
            cb = data["callback_query"]
            uid, cid, cb_data = str(cb["from"]["id"]), cb["message"]["chat"]["id"], cb.get("data", "")
            if cb_data.startswith("buy_"):
                amt = cb_data.replace("buy_", "")
                if amt in PLAN_CREDITS:
                    url = create_cf_order(uid, amt)
                    if url: send_msg(cid, f"💎 <b>Pay ₹{amt} for {PLAN_CREDITS[amt]} Chats</b>\nTelegram ke andar secure UPI payment ke liye button dabao 👇", markup={"inline_keyboard": [[{"text": f"💳 Pay ₹{amt} (Instant UPI)", "web_app": {"url": url}}]]})
            tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
            return jsonify({"status": "ok"}), 200

        if "message" not in data: return jsonify({"status": "ok"}), 200
        msg = data["message"]
        cid, uid, fname = msg["chat"]["id"], str(msg["from"]["id"]), msg["from"].get("first_name", "User")
        text = str(msg.get("text") or "").strip()
        is_own = (uid == OWNER_ID)

        if text.lower().startswith(("/start", "/reset", "/credits")):
            if text.lower().startswith("/reset"): fb_update_user(uid, {"history": [], "active_rp": ""})
            send_msg(cid, f"Hii {fname}! 🔥 Main tumhari personal partner hoon. Aao khul ke baatein karein... 😘", markup=get_pay_kb())
            return jsonify({"status": "ok"}), 200

        u = fb_get_user(uid)
        credits = 999999 if is_own else int(u.get("credits", 12))
        
        if credits <= 0 and not any(w in text.lower() for w in ["credit", "buy", "recharge"]):
            send_msg(cid, "Aah jaan... humari baatein kitni hot chal rahi thi aur free credits khatam ho gaye! 🥺 Niche button se ₹9 ya ₹19 ka chota sa recharge kar lo na... main wait kar rahi hoon! 🥵👇", markup=get_pay_kb())
            return jsonify({"status": "ok"}), 200

        tg_req("sendChatAction", {"chat_id": cid, "action": "typing"}, timeout=2)
        
        b64, mime = None, "image/jpeg"
        if "photo" in msg: fid = msg["photo"][-1]["file_id"]; b64 = get_file_b64(fid, True)
        elif "sticker" in msg:
            stk = msg["sticker"]
            fid = stk.get("file_id") if not stk.get("is_animated") and not stk.get("is_video") else (stk.get("thumbnail") or {}).get("file_id")
            b64 = get_file_b64(fid, True)
        
        ans, pt = chat_ai(msg.get("caption") or text or "Look at this", fname, uid, credits, b64, mime)
        
        show_kb = any(w in text.lower() for w in BUY_PLAN_WORDS) and not is_own
        if pt and pt in PHOTO_VAULT:
            media = random.choice(PHOTO_VAULT[pt])
            url = media if media.startswith("http") else GITHUB_BASE_URL + media
            tg_req("sendPhoto" if not media.endswith(".mp4") else "sendVideo", {"chat_id": cid, "photo" if not media.endswith(".mp4") else "video": url, "caption": ans, "protect_content": True, "has_spoiler": True, "reply_markup": get_pay_kb() if show_kb else None})
        else:
            send_msg(cid, ans, markup=get_pay_kb() if show_kb else None)

        if any(w in text.lower() for w in VOICE_REQUEST_TRIGGERS) or random.randint(1, 100) <= 25:
            tg_req("sendChatAction", {"chat_id": cid, "action": "record_voice"}, timeout=2)
            aud_b, aud_mime = generate_voice(ans)
            if aud_b: requests.post(f"{API_URL}/sendVoice", data={"chat_id": cid, "protect_content": "true"}, files={"voice": ("siya.ogg", BytesIO(aud_b), aud_mime)}, timeout=10)

        add_to_history(uid, "user", text or "[Media Sent]")
        add_to_history(uid, "siya", ans)
        if not is_own: fb_update_user(uid, {"credits": credits - 1})

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 200

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "HotBhabhi Bot - 100% Open Chat, In-App UPI & Real Vision Active"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "80")))
