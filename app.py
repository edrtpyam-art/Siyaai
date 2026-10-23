from flask import Flask, request, jsonify
import os, requests, time, re, html, random, base64, struct, json, traceback
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
FEEDBACK_CHANNEL_ID = "-1004290177402"

GROQ_KEYS = [k for k in [os.environ.get(f"GROQ_API_KEY{i}", "").strip().strip('"') for i in ["", "2", "3", "4"]] if k]
OR_KEYS = [k for k in [os.environ.get(f"OPENROUTER_API_KEY{i}", "").strip().strip('"') for i in ["", "2"]] if k]
GEMINI_KEYS = [k for k in [os.environ.get(f"GEMINI_API_KEY{i}", "").strip().strip('"') for i in ["", "2", "3"]] if k]

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""
PLAN_CREDITS = {"9": 15, "19": 35, "29": 55, "49": 100, "99": 250, "179": 500}
USER_CACHE = {}

ADULT_WORDS = ["chut", "lund", "ludn", "lauda", "gand", "gaand", "boob", "boobs", "bodes", "nude", "nudes",
    "sex", "sexy", "fuck", "fucking", "fck", "chod", "chudai", "chodna", "pussy", "dick",
    "cock", "ass", "bra", "panty", "kapde utar", "nangi", "open", "opan", "horny",
    "suck", "lick", "chatna", "daal", "dal diya", "ghusa", "nipple", "figure", "bed per", "bistar",
    "mutth", "muth", "randi", "suhagraat", "blowjob", "handjob", "cum", "pani nikal",
    "paani nikal", "pani nekal", "pani nekl", "nekl gaya", "nikal gaya", "jhad gaya", "jhar gaya",
    "pel", "pelna", "chuchi", "mamme", "doodh", "kothe", "bitch", "slut",
    "whore", "raseli", "rasili", "rasli", "gili", "geeli", "maruga", "marunga", "muh me", "mua me",
    "muee me", "mhueee", "mhue", "far duga", "faad dunga", "sari uter", "sari utar"]
PHOTO_VAULT = {
    "bodes": ["private1.jpg", "private2.jpg", "private3.jpg", "video.mp4", "video2.mp4"],
    "chut": ["open1.jpg", "open2.jpg", "opan3.jpg", "video4.mp4"],
    "gand": ["bom1.jpg", "bom2.jpg", "video6.mp4"],
    "kiss": ["kiss.jpg"], "simplepic": ["simplepic.jpg"]
}

# ============================================================
# 2. TELEGRAM & KEYBOARD HELPERS
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

def get_main_menu_kb(credits_left):
    return {"inline_keyboard": [
        [{"text": f"🎁 Free Credits: {credits_left}", "callback_data": "menu_credits"}],
        [{"text": "✍️ Feedback", "callback_data": "menu_feedback"}, {"text": "📢 Official Channel", "url": "https://t.me/edrolai"}],
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
    d = {"credits": 12, "history": [], "active_rp": "", "awaiting_feedback": False}
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
    host = request.host_url.rstrip("/") if request else "https://siyaai.vercel.app"
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
# 6. OPEN CHAT AI CORE (FAST - NO THINKING)
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

    # 1. Try Gemini (Fast mode - NO thinking config)
    for key in GEMINI_KEYS[:1]:
        try:
            p = {"systemInstruction": {"parts": [{"text": sys}]}, "contents": [{"role": "user", "parts": [{"text": "\n".join([f"{m['role']}: {m['content']}" for m in msgs[-12:]])}]}], "generationConfig": {"temperature": 0.8, "maxOutputTokens": 600}}
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
            elif cb_data == "menu_credits":
                send_msg(cid, f"💎 <b>VIP Credits: {fb_get_user(uid).get('credits', 12)}</b>\nChoose plan:", markup=get_pay_kb())
            elif cb_data == "menu_feedback":
                fb_update_user(uid, {"awaiting_feedback": True})
                send_msg(cid, "✍️ Apna feedback likh kar bhejo, main Official Channel me post kar dungi! 👇")
                
            tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
            return jsonify({"status": "ok"}), 200

        if "message" not in data: return jsonify({"status": "ok"}), 200
        msg = data["message"]
        cid, uid, fname = msg["chat"]["id"], str(msg["from"]["id"]), msg["from"].get("first_name", "User")
        text = str(msg.get("text") or "").strip()
        is_own = (uid == OWNER_ID)

        u = fb_get_user(uid)
        credits = 999999 if is_own else int(u.get("credits", 12))

        # Feedback Submission Handling
        if u.get("awaiting_feedback") and text and not text.startswith("/"):
            fb_update_user(uid, {"awaiting_feedback": False})
            send_msg(FEEDBACK_CHANNEL_ID, f"🌟 <b>FEEDBACK</b> from <a href=\"tg://user?id={uid}\">{html.escape(fname)}</a>:\n<i>{html.escape(text)}</i>")
            send_msg(cid, "❤️ Thank you! Feedback Official Channel me post ho gaya hai! 🥰")
            return jsonify({"status": "ok"}), 200

        # Start & Menu Commands
        if text.lower().startswith(("/start", "/reset", "/credits", "/menu")):
            if text.lower().startswith("/reset"): fb_update_user(uid, {"history": [], "active_rp": ""})
            send_msg(cid, f"Hii {fname}! 🔥 Main tumhari personal partner hoon. Aao khul ke baatein karein... 😘", markup=get_main_menu_kb(credits))
            return jsonify({"status": "ok"}), 200
        
        if credits <= 0 and not any(w in text.lower() for w in ["credit", "buy", "recharge", "menu"]):
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
        
        show_kb = any(w in text.lower() for w in ["buy", "recharge", "plan"]) and not is_own
        if pt and pt in PHOTO_VAULT:
            media = random.choice(PHOTO_VAULT[pt])
            url = media if media.startswith("http") else GITHUB_BASE_URL + media
            tg_req("sendPhoto" if not media.endswith(".mp4") else "sendVideo", {"chat_id": cid, "photo" if not media.endswith(".mp4") else "video": url, "caption": ans, "protect_content": True, "has_spoiler": True, "reply_markup": get_pay_kb() if show_kb else None})
        else:
            send_msg(cid, ans, markup=get_pay_kb() if show_kb else None)

        if any(w in text.lower() for w in ["voice", "audio", "sunao", "awaz"]) or random.randint(1, 100) <= 25:
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
def health_check():
    html_page = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">

        <meta name="theme-color" content="#0b1020">
        <meta name="description" content="Edrol AI - Intelligent digital assistance, conversational AI and digital services.">

        <title>Edrol AI | Intelligent Digital Services</title>

        <style>
            :root {
                --bg: #0b1020;
                --surface: #121a2d;
                --surface-light: #18243a;
                --primary: #38bdf8;
                --accent: #f472b6;
                --text: #f1f5f9;
                --muted: #94a3b8;
                --border: rgba(148, 163, 184, 0.15);
            }

            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            html {
                scroll-behavior: smooth;
            }

            body {
                font-family: "Segoe UI", Arial, sans-serif;
                background: var(--bg);
                color: var(--text);
                line-height: 1.7;
                min-height: 100vh;
            }

            a {
                color: inherit;
                text-decoration: none;
            }

            .container {
                width: min(1050px, 92%);
                margin: auto;
            }

            .navbar {
                position: sticky;
                top: 0;
                z-index: 10;
                background: rgba(11, 16, 32, 0.92);
                backdrop-filter: blur(14px);
                border-bottom: 1px solid var(--border);
            }

            .nav-inner {
                min-height: 82px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 20px;
            }

            .brand {
                display: flex;
                align-items: center;
                gap: 12px;
            }

            .brand-logo {
                width: 46px;
                height: 46px;
                object-fit: contain;
                border-radius: 14px;
                background: var(--surface-light);
                padding: 5px;
            }

            .brand-name {
                font-size: 21px;
                font-weight: 800;
                letter-spacing: 0.5px;
            }

            .brand-name span {
                color: var(--primary);
            }

            .brand-tagline {
                display: block;
                font-size: 11px;
                color: var(--muted);
                letter-spacing: 0.7px;
            }

            .nav-link {
                color: var(--muted);
                font-size: 14px;
                transition: color 0.2s;
            }

            .nav-link:hover {
                color: var(--primary);
            }

            .hero {
                text-align: center;
                padding: 95px 0 70px;
                background:
                    radial-gradient(ellipse at 50% 0%,
                    rgba(56, 189, 248, 0.13), transparent 65%);
            }

            .eyebrow {
                display: inline-block;
                padding: 6px 14px;
                border: 1px solid rgba(56, 189, 248, 0.3);
                border-radius: 30px;
                background: rgba(56, 189, 248, 0.07);
                color: var(--primary);
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 1px;
                text-transform: uppercase;
                margin-bottom: 22px;
            }

            .hero h1 {
                font-size: clamp(38px, 7vw, 66px);
                line-height: 1.15;
                letter-spacing: -1.5px;
                margin-bottom: 22px;
            }

            .hero h1 span {
                background: linear-gradient(90deg, var(--primary), #a5b4fc, var(--accent));
                -webkit-background-clip: text;
                background-clip: text;
                color: transparent;
            }

            .hero p {
                max-width: 620px;
                margin: 0 auto;
                color: var(--muted);
                font-size: 16px;
            }

            .hero-actions {
                display: flex;
                justify-content: center;
                flex-wrap: wrap;
                gap: 12px;
                margin-top: 30px;
            }

            .button {
                display: inline-flex;
                justify-content: center;
                align-items: center;
                padding: 12px 21px;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 700;
                transition: transform 0.2s, opacity 0.2s;
            }

            .button:hover {
                transform: translateY(-2px);
                opacity: 0.9;
            }

            .button-primary {
                background: var(--primary);
                color: #07111f;
            }

            .button-secondary {
                border: 1px solid var(--border);
                background: var(--surface);
                color: var(--text);
            }

            .section {
                padding: 28px 0;
                scroll-margin-top: 100px;
            }

            .section-heading {
                text-align: center;
                margin-bottom: 30px;
            }

            .section-heading h2 {
                font-size: clamp(25px, 4vw, 34px);
                margin-bottom: 8px;
            }

            .section-heading p {
                color: var(--muted);
                font-size: 14px;
            }

            .feature-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 18px;
            }

            .feature-card,
            .content-card {
                background: linear-gradient(
                    145deg,
                    var(--surface-light),
                    var(--surface)
                );
                border: 1px solid var(--border);
                border-radius: 16px;
                padding: 24px;
            }

            .feature-icon {
                width: 45px;
                height: 45px;
                display: grid;
                place-items: center;
                background: rgba(56, 189, 248, 0.1);
                border: 1px solid rgba(56, 189, 248, 0.18);
                border-radius: 12px;
                font-size: 22px;
                margin-bottom: 17px;
            }

            .feature-card h3 {
                font-size: 17px;
                margin-bottom: 8px;
            }

            .feature-card p {
                color: var(--muted);
                font-size: 13px;
            }

            .content-card {
                margin-bottom: 18px;
                padding: 28px;
            }

            .content-card h2 {
                color: var(--primary);
                font-size: 21px;
                margin-bottom: 14px;
            }

            .content-card h3 {
                font-size: 16px;
                margin-top: 23px;
                margin-bottom: 7px;
            }

            .content-card p {
                color: #cbd5e1;
                font-size: 14px;
                overflow-wrap: anywhere;
            }

            .content-card a {
                color: var(--primary);
                font-weight: 600;
            }

            .content-card a:hover {
                text-decoration: underline;
            }

            .faq-item {
                border-bottom: 1px solid var(--border);
                padding: 17px 0;
            }

            .faq-item:last-child {
                border-bottom: none;
                padding-bottom: 0;
            }

            .faq-item h3 {
                margin: 0 0 7px;
                font-size: 15px;
            }

            .faq-item p {
                font-size: 14px;
                color: var(--muted);
            }

            .support-box {
                text-align: center;
                padding: 38px 25px;
                border: 1px solid rgba(56, 189, 248, 0.2);
                border-radius: 18px;
                background: linear-gradient(
                    135deg,
                    rgba(56, 189, 248, 0.08),
                    rgba(244, 114, 182, 0.05)
                );
            }

            .support-box h2 {
                font-size: 25px;
                margin-bottom: 10px;
            }

            .support-box p {
                color: var(--muted);
                font-size: 14px;
                margin-bottom: 22px;
            }

            .footer {
                margin-top: 55px;
                border-top: 1px solid var(--border);
                padding: 27px 0;
                text-align: center;
                color: var(--muted);
                font-size: 12px;
            }

            .footer strong {
                color: var(--primary);
                font-weight: 700;
            }

            .footer-links {
                display: flex;
                justify-content: center;
                flex-wrap: wrap;
                gap: 20px;
                margin-bottom: 12px;
            }

            .footer-links a:hover {
                color: var(--primary);
            }

            @media (max-width: 700px) {
                .feature-grid {
                    grid-template-columns: 1fr;
                }

                .hero {
                    padding: 70px 0 50px;
                }

                .nav-inner {
                    min-height: 72px;
                }

                .brand-name {
                    font-size: 18px;
                }

                .nav-link {
                    font-size: 12px;
                }

                .content-card {
                    padding: 21px;
                }
            }
        </style>
    </head>

    <body>
        <header class="navbar">
            <div class="container nav-inner">
                <a class="brand" href="/" aria-label="Edrol AI Home">
                    <img
                        class="brand-logo"
                        src="/12345.png"
                        alt="Edrol AI Logo"
                        onerror="this.onerror=null;this.src='https://cdn-icons-png.flaticon.com/512/4712/4712035.png';"
                    >
                    <div>
                        <div class="brand-name">Edrol <span>AI</span></div>
                        <span class="brand-tagline">INTELLIGENT DIGITAL SERVICES</span>
                    </div>
                </a>

                <a class="nav-link" href="#about">About Us</a>
            </div>
        </header>

        <main>
            <section class="hero" id="about">
                <div class="container">
                    <span class="eyebrow">Meet Edrol AI</span>

                    <h1>
                        Intelligence for<br>
                        <span>Everyday Life.</span>
                    </h1>

                    <p>
                        Welcome to Edrol AI, your digital assistant platform
                        designed to make conversations, information discovery
                        and everyday digital tasks simpler.
                    </p>

                    <div class="hero-actions">
                        <a class="button button-primary"
                           href="https://t.me/edrolai"
                           target="_blank"
                           rel="noopener noreferrer">
                            Contact Support
                        </a>

                        <a class="button button-secondary" href="#faq">
                            Explore FAQs
                        </a>
                    </div>
                </div>
            </section>

            <section class="section">
                <div class="container">
                    <div class="section-heading">
                        <h2>Designed Around You</h2>
                        <p>A simple, accessible and user-focused AI experience.</p>
                    </div>

                    <div class="feature-grid">
                        <article class="feature-card">
                            <div class="feature-icon">✦</div>
                            <h3>AI Conversations</h3>
                            <p>
                                Explore ideas, ask questions and get assistance
                                through conversational AI.
                            </p>
                        </article>

                        <article class="feature-card">
                            <div class="feature-icon">◈</div>
                            <h3>Simple Experience</h3>
                            <p>
                                A straightforward digital experience designed
                                to make interacting with AI easier.
                            </p>
                        </article>

                        <article class="feature-card">
                            <div class="feature-icon">◎</div>
                            <h3>Customer Support</h3>
                            <p>
                                Find our official support channels whenever
                                you need assistance with the platform.
                            </p>
                        </article>
                    </div>
                </div>
            </section>

            <section class="section" id="terms">
                <div class="container">
                    <article class="content-card">
                        <h2>Terms &amp; Conditions</h2>

                        <p>
                            By accessing or using Edrol AI, you agree to use
                            the platform lawfully and responsibly. Edrol AI
                            provides AI-powered conversational and digital
                            services. AI-generated responses may occasionally
                            be inaccurate and should be independently verified
                            when accuracy is important.
                        </p>

                        <h3>Acceptable Use</h3>
                        <p>
                            Users must not misuse the platform, interfere
                            with its operation, attempt unauthorized access,
                            or use the service for unlawful activities.
                            Please avoid sharing passwords, OTPs, payment
                            credentials or other sensitive personal information
                            in conversations.
                        </p>

                        <h3>Service Availability</h3>
                        <p>
                            Features and availability may change from time
                            to time due to maintenance, technical limitations
                            or third-party service dependencies.
                        </p>

                        <h3>Privacy</h3>
                        <p>
                            Users should exercise care when sharing personal
                            information. For privacy-related questions,
                            please contact our official support team.
                        </p>
                    </article>

                    <article class="content-card" id="refunds">
                        <h2>Refunds &amp; Cancellations</h2>

                        <p>
                            Digital purchases and AI usage credits may be
                            subject to specific refund and cancellation
                            conditions disclosed at the time of purchase.
                            Please review those conditions before completing
                            a transaction.
                        </p>

                        <p style="margin-top: 12px;">
                            If a payment is duplicated, a transaction is
                            incorrectly charged, or a technical issue affects
                            a purchase, contact our support team with the
                            relevant transaction details. Requests will be
                            reviewed according to applicable law and the
                            purchase terms.
                        </p>
                    </article>

                    <article class="content-card" id="faq">
                        <h2>Frequently Asked Questions</h2>

                        <div class="faq-item">
                            <h3>What is Edrol AI?</h3>
                            <p>
                                Edrol AI is a digital platform offering
                                AI-powered conversational assistance and
                                related digital services.
                            </p>
                        </div>

                        <div class="faq-item">
                            <h3>How can I contact Edrol AI support?</h3>
                            <p>
                                You can reach our support team through our
                                official Telegram channel
                                <a href="https://t.me/edrolai"
                                   target="_blank"
                                   rel="noopener noreferrer">@edrolai</a>
                                or by email at
                                <a href="mailto:support@edrolai.com">
                                    support@edrolai.com
                                </a>.
                            </p>
                        </div>

                        <div class="faq-item">
                            <h3>Are payments processed securely?</h3>
                            <p>
                                Payments, where supported, are processed
                                through the designated payment provider.
                                Please verify the payment page and transaction
                                details before paying. Never share your OTP
                                or payment password with anyone.
                            </p>
                        </div>

                        <div class="faq-item">
                            <h3>Can I request help with a payment?</h3>
                            <p>
                                Yes. Contact Edrol AI support with your
                                transaction reference and a brief description
                                of the issue. Never send your OTP, password
                                or full card details.
                            </p>
                        </div>

                        <div class="faq-item">
                            <h3>Does Edrol AI guarantee every AI response?</h3>
                            <p>
                                No. AI responses can sometimes contain errors.
                                Verify important information using reliable
                                sources before relying on it.
                            </p>
                        </div>
                    </article>
                </div>
            </section>

            <section class="section" id="support">
                <div class="container">
                    <div class="support-box">
                        <h2>Need Help? We're Here.</h2>
                        <p>
                            Have a question, payment concern or technical issue?
                            Reach out to Edrol AI through our official channels.
                        </p>

                        <div class="hero-actions">
                            <a class="button button-primary"
                               href="https://t.me/edrolai"
                               target="_blank"
                               rel="noopener noreferrer">
                                Telegram Support
                            </a>

                            <a class="button button-secondary"
                               href="mailto:support@edrolai.com">
                                Email Support
                            </a>
                        </div>
                    </div>
                </div>
            </section>
        </main>

        <footer class="footer">
            <div class="container">
                <div class="footer-links">
                    <a href="#about">About</a>
                    <a href="#terms">Terms</a>
                    <a href="#refunds">Refund Policy</a>
                    <a href="#faq">FAQs</a>
                    <a href="#support">Support</a>
                </div>

                <p>&copy; 2026 Edrol AI. All rights reserved.</p>
                <p style="margin-top: 5px;">
                    <strong>Powered by Edrol AI</strong>
                </p>
            </div>
        </footer>
    </body>
    </html>
    """

    return html_page, 200, {"Content-Type": "text/html; charset=utf-8"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "80")))
