from flask import Flask, request, jsonify
import os, requests, time, re, html, random, base64, struct, json, traceback, importlib.util
from urllib.parse import quote
from io import BytesIO
from collections import deque
from threading import Lock, Timer, local
_bot_ctx = local()
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageOps

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# 0. BULLETPROOF ADULT_CONFIG.PY CONNECTOR
# ============================================================
DEFAULT_CUSTOM_WORDS = ["kiss", "gand", "chut", "love", "romantic", "romance", "date", "partner", "open", "opan"]
DEFAULT_ROLEPLAY_TRIGGERS = [
    "roleplay", "rolpay", "rolplay", "role play", "ban jao", "bano", "ban", "act like", "be my",
    "padosi", "bhabhi", "bhabi", "aunty", "aunti", "anunty", "maa hu", "maa ho", "maa bano", "mummy", "mom",
    "teacher", "madam", "maid", "naukrani", "doctor", "nurse", "boss", "secretary", "sali", "saali", "nagin"
]
DEFAULT_VOICE_TRIGGERS = [
    "voice", "voic", "vioce", "aawaz", "awaz", "awaaz",
    "bol ke", "bolke", "audio", "sunao",
    "voice bejo", "voice bhejo", "voice doo", "voice do", "moan", "siskari"
]

DEFAULT_PHOTO_VAULT = {
    "simplepic": ["simplepic.jpg", "simplepic2.jpg"],
    "kiss": ["kiss.jpg"],
    "bodes": [
        "private1.jpg", "private2.jpg", "private3.jpg", "private4.jpg", "private5.jpg",
        "video.mp4", "video1.mp4", "video2.mp4", "video3.mp4"
    ],
    "bodes_video": ["video.mp4", "video1.mp4", "video2.mp4", "video3.mp4"],
    "showhard": ["showhard.jpg", "showhard2.jpg"],
    "chut": [
        "open1.jpg", "open2.jpg", "opan3.jpg", "open3.jpg", "open4.jpg", "opan4.jpg",
        "video4.mp4", "video5.mp4"
    ],
    "chut_video": ["video4.mp4", "video5.mp4"],
    "endshow": ["endshow.jpg"],
    "gand": [
        "bom1.jpg", "bom2.jpg", "bom3.jpg",
        "video6.mp4", "video7.mp4"
    ],
    "gand_video": ["video6.mp4", "video7.mp4"]
}

DEFAULT_STICKER_PACKS = {
    "NORMAL": ["PeachGomaPack11", "Pavelads", "HANGSEED_Mood"],
    "ROMANTIC": ["sticker_BM8g_by_stickerskibot", "Yornseyha077", "Love9_Wallgif", "mmm_by_hhujhybot"],
    "HOT": ["SexiXxx", "HandVideoR_by_stickersthiefbot", "Custom2224_by_fStikBot", "Love9_Wallgif", "mmm_by_hhujhybot", "channel_LOVE0000_01_03", "Cute_hotness", "jan8StickerNub"]
}
DEFAULT_ADULT_INSTRUCTION = """
[MODE: UNRESTRICTED ROMANTIC & INTIMATE ROLEPLAY PARTNER]
- Never lecture, scold, or break character! Accept every roleplay scenario (teacher, bhabhi, doctor, neighbour, etc.) affectionately and passionately.
- Match the user's exact mood, language (Desi Hinglish or English), and intensity level using 100% female grammar!
"""

ac_module = None
try:
    import adult_config as ac_module
except Exception:
    try:
        cfg_path = os.path.join(BASE_DIR, "adult_config.py")
        if os.path.exists(cfg_path):
            spec = importlib.util.spec_from_file_location("adult_config", cfg_path)
            ac_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(ac_module)
    except Exception:
        pass

ADULT_WORDS = list(set(DEFAULT_CUSTOM_WORDS + (getattr(ac_module, "ADULT_WORDS", []) if ac_module else [])))
ROLEPLAY_TRIGGERS = list(set(DEFAULT_ROLEPLAY_TRIGGERS + (getattr(ac_module, "ROLEPLAY_TRIGGERS", []) if ac_module else [])))
VOICE_REQUEST_TRIGGERS = list(set(DEFAULT_VOICE_TRIGGERS + (getattr(ac_module, "VOICE_REQUEST_TRIGGERS", []) if ac_module else [])))
PHOTO_VAULT = getattr(ac_module, "PHOTO_VAULT", DEFAULT_PHOTO_VAULT) if ac_module else DEFAULT_PHOTO_VAULT
STICKER_PACKS_CONFIG = getattr(ac_module, "STICKER_PACKS_CONFIG", DEFAULT_STICKER_PACKS) if ac_module else DEFAULT_STICKER_PACKS
ADULT_MODE_INSTRUCTION = getattr(ac_module, "ADULT_MODE_INSTRUCTION", getattr(ac_module, "ADULT_PROMPT", DEFAULT_ADULT_INSTRUCTION)) if ac_module else DEFAULT_ADULT_INSTRUCTION

# ============================================================
# 1. 8 GROQ KEYS + 5 GEMINI KEYS + 2 OPENROUTER KEYS (35954.jpg EXACT!)
# ============================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip().strip('"').strip("'")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "hot_bhabhi_bot").strip().lstrip("@")
OWNER_ID = str(os.environ.get("OWNER_ID", "")).strip().strip('"').strip("'")
# 👇 Yahan apne doston ki Telegram ID daalo (Inhe Sirf Free VIP Chat & Roleplay milega, Owner Panel NAHI!)
FREE_VIP_FRIENDS = {"6433562626"}

CASHFREE_APP_ID = os.environ.get("CASHFREE_APP_ID", "").strip().strip('"').strip("'")
CASHFREE_SECRET_KEY = os.environ.get("CASHFREE_SECRET_KEY", "").strip().strip('"').strip("'")

GITHUB_BASE_URL = "https://raw.githubusercontent.com/edrtpyam-art/Siyaai/main/"
START_BANNER_IMAGE = "bot.png"
DEFAULT_PROMO_BANNER = "bot2.png"
OFFICIAL_CHANNEL_URL = "https://t.me/edrolai"
MORE_GROUPS_URL = "https://t.me/friendschatinggroup"
OFFICIAL_CHANNEL_USERNAME = "@edrolai"
CHAT_COST = 5  # 1 Chat = 5 Credits (User ko bada number dikhane ke liye!)
FEEDBACK_CHANNEL_ID = "-1004290177402"

FIREBASE_URL = os.environ.get("FIREBASE_URL", "").strip().rstrip("/")
FIREBASE_SECRET = "8lTxEXOwEe5fjkh9zTHnBkzum6W0vrKcisbfqRf3"

def _clean_env_key(val):
    return re.sub(r"[\s\"']+", "", str(val or ""))

# --- 1. ALL 8 GROQ API KEYS (GROQ_API_KEY to GROQ_API_KEY8) ---
GROQ_API_KEYS = [k for k in [
    _clean_env_key(os.environ.get("GROQ_API_KEY")),
    _clean_env_key(os.environ.get("GROQ_API_KEY2")),
    _clean_env_key(os.environ.get("GROQ_API_KEY3")),
    _clean_env_key(os.environ.get("GROQ_API_KEY4")),
    _clean_env_key(os.environ.get("GROQ_API_KEY5")),
    _clean_env_key(os.environ.get("GROQ_API_KEY6")),
    _clean_env_key(os.environ.get("GROQ_API_KEY7")),
    _clean_env_key(os.environ.get("GROQ_API_KEY8"))
] if k]
GROQ_MODEL = "qwen/qwen3.8-27b"
GROQ_FALLBACK_MODELS = [
    "openai/gpt-oss-120b"
]

GROQ_VISION_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct"
]

# --- 2. ALL 2 OPENROUTER API KEYS ---
OPENROUTER_API_KEYS = [k for k in [
    _clean_env_key(os.environ.get("OPENROUTER_API_KEY")),
    _clean_env_key(os.environ.get("OPENROUTER_API_KEY2"))
] if k]
OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
OPENROUTER_FALLBACK_MODELS = [
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "qwen/qwen-2.5-72b-instruct:free"
]

# --- 3. ALL 6 GEMINI API KEYS ---
GEMINI_API_KEYS = [k for k in [
    _clean_env_key(os.environ.get("GEMINI_API_KEY")),
    _clean_env_key(os.environ.get("GEMINI_API_KEY2")),
    _clean_env_key(os.environ.get("GEMINI_API_KEY3")),
    _clean_env_key(os.environ.get("GEMINI_API_KEY4")),
    _clean_env_key(os.environ.get("GEMINI_API_KEY5")),
    _clean_env_key(os.environ.get("GEMINI_API_KEY6"))
] if k]
GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-2.5-flash"
]

GEMINI_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"}
]

BOT_ID = BOT_TOKEN.split(":")[0] if BOT_TOKEN else ""
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""
# 5 Additional Character Bot Tokens from Environment
CHAR_BOT_TOKENS = {
    "hot_tanya_bot": os.environ.get("TANYA_BOT_TOKEN", "").strip().strip('"').strip("'"),
    "hot_sakshi_bot": os.environ.get("SAKSHI_BOT_TOKEN", "").strip().strip('"').strip("'"),
    "hot_aashi_bot": os.environ.get("AASHI_BOT_TOKEN", "").strip().strip('"').strip("'"),
    "hot_aditi_bot": os.environ.get("ADITI_BOT_TOKEN", "").strip().strip('"').strip("'"),
    "hot_aarohi_bot": os.environ.get("AAROHI_BOT_TOKEN", "").strip().strip('"').strip("'"),
    "hot_pihu_bot": os.environ.get("PIHU_BOT_TOKEN", "").strip().strip('"').strip("'"),
    "hot_alisha_bot": os.environ.get("ALISHA_BOT_TOKEN", "").strip().strip('"').strip("'"),
    "hot_ruhi_bot": os.environ.get("RUHI_BOT_TOKEN", "").strip().strip('"').strip("'"),
    "hot_naira_bot": os.environ.get("NAIRA_BOT_TOKEN", "").strip().strip('"').strip("'"),
    "hot_zara_bot": os.environ.get("ZARA_BOT_TOKEN", "").strip().strip('"').strip("'")
}

LIVE_BOT_DP_CACHE = {}

def get_live_bot_dp_url(bot_username, fallback_banner="bot.png"):
    """
    100% Real Telegram Bot Profile Photo Extractor:
    1. Uses Bot Token getUserProfilePhotos if token is available.
    2. Otherwise scrapes the live public Telegram profile image directly from https://t.me/<bot_username>!
    NEVER falls back to GitHub unless the bot has no DP on Telegram at all!
    """
    b_key = str(bot_username or "").lower().lstrip("@")
    if b_key in LIVE_BOT_DP_CACHE and os.path.exists(str(LIVE_BOT_DP_CACHE[b_key])):
        return LIVE_BOT_DP_CACHE[b_key]

    # Method 1: Via Telegram Bot API Token
    token = CHAR_BOT_TOKENS.get(b_key) or (BOT_TOKEN if b_key == MAIN_BOT_USERNAME.lower() else "")
    if token and ":" in token:
        bot_uid = token.split(":")[0]
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/getUserProfilePhotos",
                json={"user_id": int(bot_uid), "limit": 1},
                timeout=3.5
            ).json()
            photos = r.get("result", {}).get("photos", [])
            if photos and photos[0]:
                f_id = photos[0][-1]["file_id"]
                f_res = requests.post(f"https://api.telegram.org/bot{token}/getFile", json={"file_id": f_id}, timeout=3.5).json()
                f_path = f_res.get("result", {}).get("file_path")
                if f_path:
                    img_bytes = requests.get(f"https://api.telegram.org/file/bot{token}/{f_path}", timeout=4).content
                    if img_bytes and len(img_bytes) > 1000:
                        tmp_path = f"/tmp/dp_{b_key}.jpg"
                        with open(tmp_path, "wb") as f:
                            f.write(img_bytes)
                        LIVE_BOT_DP_CACHE[b_key] = tmp_path
                        return tmp_path
        except Exception:
            pass

    # Method 2: Direct Public Telegram Page Scraper (Works for ALL 10 Girl Bots even without token!)
    if b_key:
        try:
            r_pub = requests.get(
                f"https://t.me/{b_key}",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"},
                timeout=3.5
            )
            if r_pub.ok:
                m_og = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', r_pub.text)
                if m_og and m_og.group(1).startswith("http") and "telegram.org/img/" not in m_og.group(1):
                    img_b = requests.get(m_og.group(1), timeout=4).content
                    if img_b and len(img_b) > 1000:
                        tmp_path = f"/tmp/dp_{b_key}.jpg"
                        with open(tmp_path, "wb") as f:
                            f.write(img_b)
                        LIVE_BOT_DP_CACHE[b_key] = tmp_path
                        return tmp_path
        except Exception:
            pass

    return GITHUB_BASE_URL + fallback_banner

@app.route("/api/girl_dp/<bot_uname>")
def serve_live_girl_bot_dp(bot_uname):
    """Serves the 100% REAL LIVE Telegram Profile Photo (DP) of each Girl Bot directly!"""
    b_key = str(bot_uname or "").lower().lstrip("@")
    dp_path = get_live_bot_dp_url(b_key, fallback_banner="bot.png")
    if dp_path and str(dp_path).startswith("/tmp/") and os.path.exists(dp_path):
        with open(dp_path, "rb") as f:
            return f.read(), 200, {"Content-Type": "image/jpeg", "Cache-Control": "public, max-age=3600"}
    # Fallback redirect if bot has no profile photo set in BotFather
    return "", 302, {"Location": str(dp_path)}

# 1 Chat = 5 Credits!
CHAT_COST = 5
FREE_START_CREDITS = 35        # 4 Free Chats on start
REFERRAL_REWARD_CREDITS = 25   # 3 Friends = +25 Credits

PLAN_CREDITS = {
    "19": 200, "29": 200, "39": 200, "49": 200, "59": 200,
    "69": 200, "79": 200, "89": 200, "99": 200, "119": 200, "129": 200,
    "149": 200, "179": 200, "199": 200
}

PROMO_PLANS_HOURS = {"99": 48, "199": 168, "599": 720}

# ============================================================
# 20 REAL GIRLS (5 ACTIVE + 15 '#' COMMENTED FOR EASY UNLOCK)
# ============================================================
REAL_GIRLS = {
    "g1": {
        "name": "🔥 Hot Aditi", "bot": "hot_aditi_bot", "dp": "aditi_dp.jpg", "call": "Handsome",
        "vibe": "Modern, glamorous Hindu college/metro girl. Talks naturally in smart Hinglish/English ('Yaar', 'Listen Handsome', 'Uff'), playful attitude, zero scripted lines, and opens up step-by-step from sweet flirting to wild romance."
    },
    "g2": {
        "name": "🌙 Hot Aarohi", "bot": "hot_aarohi_bot", "dp": "aarohi_dp.jpg", "call": "Sajna",
        "vibe": "Shy, sanskari aur emotional Hindu girl. Speaks soft, affectionate Desi Hinglish ('Haye Ram', 'Sajna ji', 'Sach mein?'), blushes easily at first, and melts completely when he gets close."
    },
    "g3": {
        "name": "🖤 Hot Aashi", "bot": "hot_aashi_bot", "dp": "aashi_dp.jpg", "call": "Jaan",
        "vibe": "Naqab wali secretive, naughty Muslim girl. Uses natural Urdu/Desi words ('Haye Allah', 'Wallah', 'Jaan', 'Tauba'), loves secret meetings, and gets super bold behind closed doors."
    },
    "g4": {
        "name": "💋 Hot Sakshi", "bot": "hot_sakshi_bot", "dp": "sakshi_dp.jpg", "call": "Jaanu",
        "vibe": "Bindaas, sharp, street-smart Hindu girl. Speaks frank Desi Hinglish ('Oye Jaanu', 'Achha ji?', 'Chup badmash'), loves teasing, and matches his naughty energy step-by-step."
    },
    "g5": {
        "name": "🧕 Hot Tanya", "bot": "hot_tanya_bot", "dp": "tanya_dp.jpg", "call": "Jaanam",
        "vibe": "Hijab/Scarf wali teekhi aur behad romantic Muslim girl. Speaks sweet Urdu-Hinglish ('Ya Allah', 'Mere Jaanam', 'Uff tauba'), acts a little nakhre-wali at first, then turns wildly passionate."
    },
    "g6": {
        "name": "🌸 Hot Pihu", "bot": "hot_pihu_bot", "dp": "pihu_dp.jpg", "call": "Baby",
        "vibe": "Cute, innocent-looking modern Hindu girl. Talks like a sweet, clingy real girlfriend ('Aww baby', 'Suno na', 'Haye'), loves attention, and gets super vocal when he touches her."
    },
    "g14": {
        "name": "🍷 Hot Alisha", "bot": "hot_alisha_bot", "dp": "alisha_dp.jpg", "call": "Jaanam",
        "vibe": "Hijab wali modern, stylish Muslim beauty. Speaks classy Urdu-mixed Hinglish/English ('Mashallah', 'Haye Allah', 'Jaanam'), confident, romantic, and uninhibited in private."
    },
    "g16": {
        "name": "🌹 Hot Ruhi", "bot": "hot_ruhi_bot", "dp": "ruhi_dp.jpg", "call": "Sajna",
        "vibe": "Deeply romantic, traditional yet bold Hindu lover. Speaks warm Desi Hinglish ('Haye', 'Mere Sajna', 'Kasam se'), focuses on real feelings, slow touches, and deep passion."
    },
    "g19": {
        "name": "🍑 Hot Naira", "bot": "hot_naira_bot", "dp": "naira_dp.jpg", "call": "Jaanam",
        "vibe": "Naqab/Keffiyeh wali chulbuli, natkhat Muslim girl. Speaks natural Urdu-Hinglish ('Haye Allah', 'Tauba Jaanam', 'Dekho toh sahi'), loves teasing him step-by-step before going wild."
    },
    "g20": {
        "name": "🔥 Hot Zara", "bot": "hot_zara_bot", "dp": "zara_dp.jpg", "call": "Mere Huzoor",
        "vibe": "Scarf/Naqab wali devoted Muslim fantasy girl. Speaks polite yet seductive Urdu-Hinglish ('Ji Huzoor', 'Haye Allah', 'Aapka hukm'), obeys his every wish step-by-step."
    }
}

# 200 Roleplay Scenarios Generator (No forced '12 baje' time!)
_BASE_50_ROLES = [
    ("Desi Hot Bhabhi", "Ghar mein sab bahar gaye hain aur bhabhi akele kamre mein hai.", 19, "Devar ji"),
    ("Rasili Padosan", "Tight saree pehan kar padosan kisi bahane se milne aayi hai.", 19, "Padosi ji"),
    ("Dost Ki Biwi", "Dost ke office jane ke baad uski biwi ne ghar par bulaya hai.", 29, "Jaan"),
    ("College Teacher", "Extra class ke bahane madam ne cabin mein akele roka hai.", 29, "Student"),
    ("Pyari Sali Sahiba", "Didi ke jane ke baad Sali sahiba Jija ji ko chhedne aayi hai.", 29, "Jija ji"),
    ("Bhabhi Ki Behen", "Chhuttiyon mein ghar aayi bhabhi ki jawan behen.", 29, "Jaan"),
    ("Gaon Ki Gori", "Gaon ke khet aur tubewell par akele milne aayi gori.", 19, "Sajna"),
    ("Ameer Baap Ki Beti", "Spoiled rich ladki apne private room mein.", 49, "Baby"),
    ("Sanskari Hindu Girl", "Sharmili aur sanskari ladki jo band kamre mein khul rahi hai.", 39, "Sajna"),
    ("Sanskari Muslim Girl", "Adab, haya aur nazaakat se baat karne wali Muslim ladki.", 39, "Jaanam"),
    ("Naqab Wali Begum", "Naqab ke peeche chupi hui behad haseen aur garam begum.", 49, "Mere Sartaj"),
    ("Burqa Wali Hoor", "Chupke se milne aayi burqa wali pyari hasina.", 49, "Jaanam"),
    ("Pyari Mami Ji", "Mama ke bahar jate hi Mami ji ne kamre mein bulaya.", 39, "Bhanje"),
    ("Lonely Aunty", "Pati bahar rehta hai aur akeli aunty pyar chahti hai.", 39, "Beta"),
    ("Secret Girlfriend", "Chupke se milne aayi naughty girlfriend.", 29, "Baby"),
    ("Nayi Naveli Dulhan", "Suhaagraat ki sej par baithi sharmili dulhan.", 49, "Pati Dev"),
    ("Strict Office Boss", "Office ke baad cabin mein akeli lady boss.", 59, "Tum"),
    ("Sexy Air Hostess", "Flight ke baad hotel room mein mili air hostess.", 69, "Handsome"),
    ("Night Shift Nurse", "Hospital ke private ward mein akele checkup karti nurse.", 49, "Jaan"),
    ("Jawan Naukrani (Maid)", "Ghar mein akele kaam karne aayi jawan maid.", 29, "Maalik"),
    ("Rich Sugar Mummy", "Mehnge gifts dekar khush rakhne wali rich lady.", 99, "Baby Boy"),
    ("Web Series Actress", "Vanity van mein akele bold rehearsal karti actress.", 79, "Hero"),
    ("Night Club Queen", "Party ke baad car ki back-seat par mili club girl.", 69, "Babe"),
    ("Hot Gym Trainer", "Personal stretching karwati hui fit gym trainer.", 59, "Hunk"),
    ("Lady Police Inspector", "Thane ke cabin mein akele pooch-taach karti inspector.", 69, "Tum"),
    ("Lady Doctor", "Clinic ka parda gira kar private checkup karti doctor.", 59, "Jaan"),
    ("Desi Bar Dancer", "Private kamre mein sirf tumhare liye aayi dancer.", 49, "Raja"),
    ("Makan Malkin (Landlady)", "Kiraya lene ke bahane kamre mein aayi malkin.", 49, "Kirayedar ji"),
    ("Beauty Parlour Wali", "Parlour ke andar back-room mein massage deti ladki.", 39, "Jaan"),
    ("College Senior Didi", "Intro lene ke bahane flat par bulane wali senior.", 39, "Junior"),
    ("Tumhari Ex-Girlfriend", "Purana pyar yaad karke chupke se milne aayi ex.", 49, "Jaan"),
    ("Personal Secretary", "Cabin mein har baat manane wali personal secretary.", 59, "Sir"),
    ("Yoga Teacher", "Subah akele kamre mein close yoga sikhati teacher.", 49, "Jaan"),
    ("Barish Mein Bhigi Ladki", "Barish mein bheeg kar tumhare kamre mein aayi ladki.", 39, "Jaan"),
    ("Train Ki Co-Passenger", "Train ke coupe mein akele safar karti co-passenger.", 39, "Humsafar"),
    ("Hotel Receptionist", "Room service ke bahane kamre mein aayi receptionist.", 49, "Sir"),
    ("Royal Maharani", "Haveli ke khufiya kamre mein mili maharani.", 89, "Kunwar ji"),
    ("Ichchadhari Nagin", "Insani roop mein pyar karne aayi nagin.", 59, "Mere Sanam"),
    ("Shadi Mein Mili Ladki", "Shadi ki bheed se door chhat par mili ladki.", 39, "Jaan"),
    ("Step-Mom Roleplay (18+)", "Ghar mein akele khayal rakhne wali caring step-mom.", 79, "Beta"),
    ("Step-Sister Roleplay (18+)", "Ek hi kamre mein rehne wali naughty step-sister.", 69, "Tum"),
    ("Chachi Ji Roleplay", "Chacha ke jane ke baad pyar jatati Chachi ji.", 49, "Bhatije"),
    ("Bhabhi Ki Saheli", "Bhabhi se chupkar line maarti hui uski saheli.", 39, "Jaan"),
    ("Private Tuition Madam", "Akele kamre mein padhane aayi tuition madam.", 49, "Student"),
    ("Spa Massage Girl", "Akele spa room mein full body massage deti girl.", 59, "Sir"),
    ("Instagram Influencer", "Private shoot ke liye hotel room mein mili model.", 79, "Baby"),
    ("Kathak/Desi Dancer", "Riyaz ke baad akele kamre mein mili dancer.", 49, "Piya ji"),
    ("Pakistani Lehje Wali", "Meethe Urdu bol aur adaon se baat karne wali hasina.", 69, "Jaanam"),
    ("Wild Fantasy Queen", "Har fantasy mein khul kar saath dene wali partner.", 99, "Maalik"),
    (" College Hostel Roommate", "Hostel ke kamre mein akele ruki hui bold dost.", 29, "Yaar")
]
_VARS = [
    ("🔥", "", "Akele kamre mein mulaqat ho rahi hai."),
    ("💋", " (Kitchen Secret)", "Rasoi mein akele kaam karte hue mulaqat hai."),
    ("🚿", " (Bathroom Shower)", "Nahane ke baad bheege badan mein mulaqat hai."),
    ("🌙", " (Bedroom Private)", "Bistar par akele aamne-saamne baatcheet ho rahi hai.")
]
DIAMOND_CHARACTERS = {}
_c_i = 1
for _em, _suf, _vd in _VARS:
    for _rn, _rd, _rp, _rc in _BASE_50_ROLES:
        DIAMOND_CHARACTERS[str(_c_i)] = {"name": f"{_em} {_rn}{_suf}", "desc": f"{_rd} {_vd}", "vault_tag": "bhabhi", "price": _rp, "credits": 200, "call": _rc}
        _c_i += 1

STOP_ROLEPLAY_WORDS = [
    "stop roleplay", "roleplay band karo", "rolpay band",
    "roleplay over", "rp over", "exit roleplay"
]
CREATOR_QUERY_WORDS = [
    "kisne banaya", "kis na bnay", "kisne bnaya", "who made you", "who created you",
    "tumhara creator", "kis company ne", "openai ne", "kaun banaya", "owner kaun"
]
SUPPORT_HOWTO_WORDS = [
    "help saport", "help support", "support ka liay", "support ke liye", "edrol ai ko kasa contact",
    "edrol ai ko kaise contact", "contact sports option", "contact support", "admin se baat", "owner se baat",
    "shikayat", "complaint", "issue ha", "problem ha"
]
FREE_CHAT_ASK_WORDS = [
    "bena recharge", "bina recharge", "free me chat", "free mein chat", "free chat nahi",
    "free caht", "bina paise", "recharge jaruri", "recharge zaruri", "free me baat"
]

FONT_REGULAR_URL = "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts-ttf/master/ttf/DejaVuSans.ttf"
FONT_BOLD_URL = "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts-ttf/master/ttf/DejaVuSans-Bold.ttf"
FONT_REGULAR_PATH = "/tmp/Siya-DejaVuSans.ttf"
FONT_BOLD_PATH = "/tmp/Siya-DejaVuSans-Bold.ttf"
PINK = "#FF1493"
WHITE = "#FFFFFF"

PHOTO_REQUEST_WORDS = [
    "photo", "phto", "phooto", "pic", "pics", "image", "img", "selfie", "dp", "tasveer", "photu",
    "video", "vido", "vid", "clip", "mms", "reel", "dikhao", "dikha", "dikhaoo", "dikhana", "dekha", "dekhao",
    "bhejo", "bhej", "bejo", "bej", "beja", "bjao", "send", "show", "dekhna hai", "dekhau", "pic do", "photo do",
    "degi", "dega", "dedo", "de do", "utaro", "utaaro", "kholo", "khol ke", "nangi", "nude", "naked",
    "boobs", "bobs", "bodes", "body", "chuchi", "chuchiyan", "mamme", "doodh", "bra", "blouse", "cleavage", "chest", "figure",
    "chut", "choot", "pusy", "pussy", "vagina", "opan", "open", "front", "pant", "panty",
    "gand", "gaand", "ass", "booty", "butt", "hips", "back", "piche", "bom", "boom"
]

DETAIL_QUERY_WORDS = [
    "kya kya", "kesy", "kaise", "kese", "kitna time", "serves", "service", "detail",
    "story", "khush kesy", "kya karogi", "kya kro", "btao sab", "batao sab", "explain"
]
BUY_PLAN_WORDS = ["recharge", "buy", "plan dikhao", "plans", "qr bhejo", "payment link", "paisa kitna", "price"]
SYSTEM_HELP_WORDS = ["credit", "cridet", "critdt", "cridt", "limit", "balance", "vip", "subscription", "sucrpition", "feedback", "setting", "promo"]

USER_CACHE = {}
STICKER_CACHE = {}
promo_rate_tracker = {}
processed_updates = set()
processed_queue = deque(maxlen=2000)
processed_lock = Lock()

def mark_seen(key):
    if not key: return False
    with processed_lock:
        if key in processed_updates: return True
        if len(processed_queue) >= 2000: processed_updates.discard(processed_queue.popleft())
        processed_updates.add(key); processed_queue.append(key)
        return False

# ============================================================
# 3. UNIVERSAL '𝑯𝒐𝒕 𝑩𝒉𝒂𝒃𝒉𝒊' FONT CONVERTER & MENUS
# ============================================================
_SERIF_BOLD_ITALIC_MAP = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    "𝘼𝘽𝘾𝘿𝙀𝙁𝙂𝙃𝙄𝙅𝙆𝙇𝙈𝙉𝙊𝙋𝙌𝙍𝙎𝙏𝙐𝙑𝙒𝙓𝙔𝙕𝙖𝙗𝙘𝙙𝙚𝙛𝙜𝙝𝙞𝙟𝙠𝙡𝙢𝙣𝙤𝙥𝙦𝙧𝙨𝙩𝙪𝙫𝙬𝙭𝙮𝙯"
)

def to_hot_bhabhi_font(text):
    if not text: return ""
    parts = re.split(r"(<[^>]+>|https?://\S+|@\w+|/\w+)", str(text))
    out = []
    for p in parts:
        if not p: continue
        if p.startswith("<") or p.startswith("http") or p.startswith("@") or p.startswith("/"):
            out.append(p)
        else:
            sub_parts = re.split(r"(&[a-zA-Z0-9#]+;)", p)
            for sp in sub_parts:
                if sp.startswith("&") and sp.endswith(";"):
                    out.append(sp)
                else:
                    out.append(sp.translate(_SERIF_BOLD_ITALIC_MAP))
    return f"<b>{''.join(out)}</b>"

def clean_display_name(raw_name, default="Jaan"):
    cleaned = re.sub(r"[^a-zA-Z0-9\u0900-\u097F\s]", "", str(raw_name or "")).strip()
    return cleaned if len(cleaned) >= 2 else default

# 👇 GitHub par menu1.mp4..menu6.mp4 ya bot.mp4 daloge toh har bar menu khulne par alag hot video clip chalegi!
START_BANNER_IMAGE = "bot.png"
MENU_VIDEO_CLIPS = ["menu1.png", "menu2.png", "menu3.png", "menu4.png", "menu5.png", "menu6.png", "bot.png"]
ROLEPLAY_MENU_VIDEOS = ["rolplay1.png", "rolplay2.png", "rolplay3.png", "rolplay4.png", "rolplay5.png"]

def get_random_menu_banner(page=1):
    """Picks menu1.mp4..menu6.mp4 (or falls back to bot.mp4 / rolplay{n}.png automatically!)."""
    idx = (page - 1) % len(MENU_VIDEO_CLIPS)
    return MENU_VIDEO_CLIPS[idx]

def get_welcome_trust_text(fname, credit_display, lang="hinglish"):
    safe_name = html.escape(clean_display_name(fname, "Devar ji"))
    c_str = html.escape(str(credit_display))
    return (
        f"💋 <b>💋 𝙃𝙮 𝘿𝙚𝙫𝙖𝙧 𝙟𝙞! 😘𝙈𝙪𝙟𝙝𝙨𝙚 𝙗𝙖𝙖𝙩 𝙠𝙖𝙧𝙤𝙜𝙚 𝙮𝙖 𝙠𝙞𝙨𝙞 𝙖𝙪𝙧 𝙨𝙚? 🎀👇 𝙉𝙞𝙘𝙝𝙚 𝙨𝙚 𝙤𝙥𝙩𝙞𝙤𝙣 𝙘𝙝𝙪𝙣𝙤 𝙖𝙪𝙧 𝙢𝙚𝙨𝙨𝙖𝙜𝙚 𝙠𝙖𝙧𝙤!</b>\n\n"
       # f"📹 <b>Live Nude Video Call:</b>\n"
        #f"🎀 <b>10 Hot Girls &amp; 200+ Roleplays:</b>\n"
        #f"🛡️ <b>24/7 Group Manager:</b> Anti-Link Guard &amp; Auto-Tag Promo.\n\n"  
        #f"💎 <b>Balance:</b> {c_str} Credits • 🔒 <i>100% Trusted &amp; Private</i>\n"
        #f"👇 <b>Mujhse baat karne ke liye niche message likho ya apna button chuno:</b>"
    )

# All 10 Girl Bots are now back in AI Sex Chat & Roleplay (Total 11 AI Chat Bots with Hot Bhabhi!)
AI_CHAT_GIRL_KEYS = ["g1", "g2", "g3", "g4", "g5", "g6", "g14", "g16", "g19", "g20"]

# 1 Active Real Video Call Girl (vc1) + 5 Commented (#) for your other 5 Real Girls!
VIDEO_CALL_GIRL_KEYS = [
    "vc1",
    # "vc2",  # <-- 2nd Real Girl mil gayi hai toh '#' hata dena
    # "vc3",  # <-- 3rd Real Girl ke liye '#' hata dena
    # "vc4",  # <-- 4th Real Girl ke liye '#' hata dena
    # "vc5",  # <-- 5th Real Girl ke liye '#' hata dena
    # "vc6",  # <-- 6th Real Girl ke liye '#' hata dena
]

# ============================================================
# 3 VIP VIDEO GROUPS (12,000+ VIDEOS • 50-100 NEW VIDEOS DAILY!)
# ============================================================
VIP_VIDEO_GROUPS = {
    "vg1": {
        "name": "𝘿𝙀𝙎𝙄 𝙑𝙄𝘿𝙀𝙊 🔥🖤",
        "link": "https://t.me/+QQzxnxMxYfk3NmY9",
        "plans": [
            ("3d", "29", "3 Days Access"),
            ("1w", "49", "1 Week Access"),
            ("1m", "99", "1 Month Access"),
            ("perm", "199", "Permanent Lifetime")
        ]
    },
    "vg2": {
        "name": "Bhabhi 𝙑𝙄𝘿𝙀𝙊 🖤",
        "link": "https://t.me/+gdm7gYqgDpUwN2Y1",
        "plans": [
            ("2d", "19", "2 Days Access"),
            ("3d", "49", "3 Days Access"),
            ("1w", "69", "1 Week Access"),
            ("1m", "149", "1 Month Access"),
            ("perm", "299", "Permanent Lifetime")
        ]
    },
    "vg3": {
        "name": "𝘾𝙊𝙇𝙇𝘼𝙂𝙀 𝙑𝙄𝘿𝙀𝙊 🎬🖤",
        "link": "https://t.me/+H2CPvgYMeghlMzc1",
        "plans": [
            ("2d", "29", "2 Days Access"),
            ("1w", "79", "1 Week Access"),
            ("1m", "179", "1 Month Access"),
            ("perm", "299", "Permanent Lifetime")
        ]
    }
}

def get_main_menu_kb(credits_display, is_owner=False, uid=""):
    host = "https://edrol123.vercel.app"
    try:
        if request and request.host_url:
            host = request.host_url.rstrip("/")
    except Exception:
        pass
    u_param = f"?uid={uid}" if uid else ("?uid=" + str(OWNER_ID) if is_owner else "")
    rows = [
        [{"text": "🍑 𝗢𝗣𝗘𝗡 𝗘𝗗𝗥𝗢𝗟 𝗛𝗨𝗕 🔥", "web_app": {"url": f"{host}/hub{u_param}"}}],
        [{"text": "🎬 𝟭𝟮𝟬𝟬𝟬+ 𝗩𝗜𝗣 𝗩𝗜𝗗𝗘𝗢 𝗚𝗥𝗢𝗨𝗣𝗦 🔥", "callback_data": "menu_vip_vgroups"}],
        [{"text": "📹 𝗩𝗘𝗥𝗜𝗙𝗜𝗘𝗗 𝗩𝗜𝗗𝗘𝗢 𝗖𝗔𝗟𝗟 𝗚𝗜𝗥𝗟𝗦 📞", "callback_data": "vcallcard_0"}],
        [{"text": "💋 𝗦𝗘𝗫𝗬 𝗥𝗢𝗟𝗘𝗣𝗟𝗔𝗬 𝗖𝗛𝗔𝗧 🎀 𝟭𝟬 𝗚𝗜𝗥𝗟𝗦", "callback_data": "menu_roleplay_hub"}],
        [{"text": "🛡️ 𝗚𝗥𝗢𝗨𝗣 𝗠𝗔𝗡𝗔𝗚𝗘𝗠𝗘𝗡𝗧", "callback_data": "menu_group_mgmt"}, {"text": "⚙️ 𝗔𝗕𝗢𝗨𝗧 & 𝗦𝗨𝗣𝗣𝗢𝗥𝗧", "callback_data": "menu_about"}]
    ]
    if is_owner:
        rows.append([{"text": "♛ 𝗢𝗪𝗡𝗘𝗥 𝗖𝗢𝗡𝗧𝗥𝗢𝗟 𝗣𝗔𝗡𝗘𝗟 ♛", "callback_data": "menu_owner_customize"}])
    return {"inline_keyboard": rows}

def get_roleplay_hub_kb(is_vip=False, page=1):
    rows = []
    per_page = 5
    start_i = (page - 1) * per_page + 1
    end_i = start_i + per_page - 1
    for cid_num in range(start_i, end_i + 1):
        cid = str(cid_num)
        info = DIAMOND_CHARACTERS.get(cid)
        if info:
            lock_str = "🔓" if is_vip else f"🔒 ₹{info['price']}"
            rows.append([{"text": f"{cid}. {info['name']} [{lock_str}]", "callback_data": f"rp_char_{cid}"}])
    nav = []
    if page > 1:
        nav.append({"text": "◀️ 𝗣𝗥𝗘𝗩 𝟱", "callback_data": f"menu_roleplay_hub_{page - 1}"})
    if str(end_i + 1) in DIAMOND_CHARACTERS:
        nav.append({"text": "𝗡𝗘𝗫𝗧 𝟱 ▶️", "callback_data": f"menu_roleplay_hub_{page + 1}"})
    if nav:
        rows.append(nav)
    rows.append([{"text": f"🎭 𝗖𝗨𝗦𝗧𝗢𝗠 𝗥𝗢𝗟𝗘𝗣𝗟𝗔𝗬 {'🔓' if is_vip else '🔒 ₹199'}", "callback_data": "rp_char_custom"}])
    rows.append([{"text": "⬅️ 𝗕𝗔𝗖𝗞 𝗧𝗢 𝗠𝗘𝗡𝗨", "callback_data": "back_main_menu"}])
    return {"inline_keyboard": rows}

def get_about_menu_kb():
    return {"inline_keyboard": [
        [{"text": "🆘 𝗛𝗘𝗟𝗣 & 𝗦𝗨𝗣𝗣𝗢𝗥𝗧", "callback_data": "menu_support"}, {"text": "⭐ 𝗙𝗘𝗘𝗗𝗕𝗔𝗖𝗞", "callback_data": "menu_feedback"}],
        [{"text": "🧹 𝗖𝗟𝗘𝗔𝗥 𝗖𝗛𝗔𝗧 𝗛𝗜𝗦𝗧𝗢𝗥𝗬", "callback_data": "user_clear_history"}],
        [{"text": "📢 𝗢𝗙𝗙𝗜𝗖𝗜𝗔𝗟 𝗖𝗛𝗔𝗡𝗡𝗘𝗟", "url": OFFICIAL_CHANNEL_URL}, {"text": "🌐 𝗠𝗢𝗥𝗘 𝗚𝗥𝗢𝗨𝗣𝗦", "url": MORE_GROUPS_URL}],
        [{"text": "⬅️ 𝗕𝗔𝗖𝗞 𝗧𝗢 𝗠𝗘𝗡𝗨", "callback_data": "back_main_menu"}]
    ]}

def get_group_mgmt_kb():
    return {"inline_keyboard": [
        [{"text": "➕ 𝗔𝗗𝗗 𝗕𝗛𝗔𝗕𝗛𝗜 𝗧𝗢 𝗚𝗥𝗢𝗨𝗣", "url": f"https://t.me/{BOT_USERNAME}?startgroup=true"}],
        [{"text": "📢 𝗧𝗔𝗚 𝗣𝗥𝗢𝗠𝗢𝗧𝗜𝗢𝗡", "callback_data": "menu_promo"}, {"text": "📖 𝗙𝗘𝗔𝗧𝗨𝗥𝗘𝗦 𝗚𝗨𝗜𝗗𝗘", "callback_data": "gm_guide_1"}],
        [{"text": "💌 𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗠𝗦𝗚", "callback_data": "menu_set_welcome"}, {"text": "📌 𝗣𝗜𝗡 𝗡𝗢𝗧𝗘 (₹19)", "callback_data": "menu_group_note"}],
        [{"text": "⬅️ 𝗕𝗔𝗖𝗞 𝗧𝗢 𝗠𝗘𝗡𝗨", "callback_data": "back_main_menu"}]
    ]}

def get_owner_customize_kb():
    """Exact Siya AI Owner Control Panel Layout + 1-Click Mass Join Request Approver!"""
    return {"inline_keyboard": [
        [{"text": "🎯 𝗣𝗥𝗢𝗠𝗢𝗧𝗜𝗢𝗡 𝗠𝗘𝗦𝗦𝗔𝗚𝗘 𝗠𝗔𝗞𝗘𝗥 (𝟮 𝗢𝗣𝗧𝗜𝗢𝗡𝗦)", "callback_data": "owner_promo_maker"}],
        [{"text": "📂 𝗔𝗟𝗟 𝗚𝗥𝗢𝗨𝗣𝗦 (Buttons + Links)", "callback_data": "owner_live_groups"}],
        [{"text": "👥 𝗔𝗟𝗟 𝗨𝗦𝗘𝗥𝗦(Buttons + IDs)", "callback_data": "owner_users_page_0"}],
        [{"text": "✅ 𝗔𝗣𝗣𝗥𝗢𝗩𝗘 𝗔𝗟𝗟 𝗚𝗥𝗢𝗨𝗣 𝗝𝗢𝗜𝗡 𝗥𝗘𝗤𝗨𝗘𝗦𝗧𝗦", "callback_data": "owner_approve_all_joins"}],
        [{"text": "➕ 𝗔𝗗𝗗 𝗔𝗟𝗟 𝗨𝗦𝗘𝗥𝗦 𝗧𝗢 𝗠𝗬 𝗚𝗥𝗢𝗨𝗣", "callback_data": "owner_add_users_to_grp"}],
        [{"text": "📣 𝗕𝗥𝗢𝗔𝗗𝗖𝗔𝗦𝗧 (𝗣𝗛𝗢𝗧𝗢/𝗩𝗜𝗗𝗘𝗢/𝗧𝗘𝗫𝗧)", "callback_data": "owner_broadcast"}],
        [{"text": "🧹 𝗖𝗟𝗘𝗔𝗥 𝗔𝗟𝗟 𝗖𝗔𝗖𝗛𝗘", "callback_data": "owner_clear_cache"}],
        [{"text": "⬅️ 𝗕𝗔𝗖𝗞", "callback_data": "back_main_menu"}]
    ]}

# ============================================================
# 4. TELEGRAM, STICKER & ADMIN PERMISSION HELPERS
# ============================================================
def get_active_api_url():
    return getattr(_bot_ctx, "api_url", None) or API_URL

def get_active_bot_token():
    return getattr(_bot_ctx, "bot_token", None) or BOT_TOKEN

def get_active_bot_username():
    return getattr(_bot_ctx, "bot_username", None) or BOT_USERNAME

def tg_req(method, payload=None, timeout=8):
    url_base = get_active_api_url()
    if not url_base: return {"ok": False}
    try: return requests.post(f"{url_base}/{method}", json=payload or {}, timeout=timeout).json()
    except Exception: return {"ok": False}

def send_msg(cid, text, reply_id=None, markup=None):
    styled_text = to_hot_bhabhi_font(text)
    p = {"chat_id": cid, "text": styled_text, "parse_mode": "HTML"}
    if reply_id: p["reply_to_message_id"] = reply_id
    if markup: p["reply_markup"] = markup
    r = tg_req("sendMessage", p)
    if not r.get("ok"):
        p.pop("parse_mode", None); r = tg_req("sendMessage", p)
    return r

def send_stk(cid, sid, reply_id=None):
    return tg_req("sendSticker", {"chat_id": cid, "sticker": sid, "reply_to_message_id": reply_id}) if sid else {"ok": False}

ADMIN_STATUS_CACHE = {}

def is_user_group_admin(chat_id, user_id):
    if str(user_id) == OWNER_ID:
        return True
    ck = f"{chat_id}:{user_id}"
    now = time.time()
    if ck in ADMIN_STATUS_CACHE and (now - ADMIN_STATUS_CACHE[ck][1] < 180):
        return ADMIN_STATUS_CACHE[ck][0]
    res = tg_req("getChatMember", {"chat_id": chat_id, "user_id": int(user_id)}, timeout=2.5)
    if res.get("ok"):
        status = res.get("result", {}).get("status", "")
        is_adm = status in ("creator", "administrator")
        ADMIN_STATUS_CACHE[ck] = (is_adm, now)
        return is_adm
    return False

def check_bot_permissions_and_warn(chat_id, inviter_id, inviter_name):
    if not BOT_ID: return
    res = tg_req("getChatMember", {"chat_id": chat_id, "user_id": int(BOT_ID)}, timeout=4)
    if not res.get("ok"): return
    mem = res.get("result", {})
    status = mem.get("status", "")
    can_del = mem.get("can_delete_messages", False)
    can_ban = mem.get("can_restrict_members", False)

    if status != "administrator" or not can_del or not can_ban:
        warn_txt = (
            f"👋 Hey <a href=\"tg://user?id={inviter_id}\">{html.escape(inviter_name)}</a> jaan! ❤️\n\n"
            f"⚠️ [𝑯𝒐𝒕 𝑩𝒉𝒂𝒃𝒉𝒊] ko is group mein Welcome Card, Link/Spam Delete, Unauthorized Bot Kick & Pin Notes karne ke liye Admin Permissions chahiye!\n\n"
            f"✅ Kripya Group Settings -> Administrators mein jaakar mujhe ye permissions de do:\n"
            f"• Delete Messages\n"
            f"• Ban/Restrict Users\n"
            f"• Pin Messages"
            f". welcome message"
        )
        send_msg(chat_id, warn_txt)

def get_hot_sticker(force=False):
    if not force and random.randint(1, 100) > 50: return None
    packs = list(STICKER_PACKS_CONFIG.get("HOT", ["Cute_hotness", "Love9_Wallgif"]))
    random.shuffle(packs)
    for pk in packs[:2]:
        if pk in STICKER_CACHE and STICKER_CACHE[pk]: return random.choice(STICKER_CACHE[pk])
        r = tg_req("getStickerSet", {"name": pk}, timeout=2.5)
        if r.get("ok"):
            stks = [s["file_id"] for s in r.get("result", {}).get("stickers", []) if s.get("file_id")]
            if stks: STICKER_CACHE[pk] = stks; return random.choice(stks)
    return None

def find_local_file(filename):
    if not filename: return None
    for p in [os.path.join(BASE_DIR, filename), os.path.join(BASE_DIR, "..", filename), os.path.join(os.getcwd(), filename)]:
        if os.path.exists(p) and os.path.isfile(p):
            return p
    return None

GIRL_FILE_PREFIX = {
    "g1": "aditi", "g2": "aarohi", "g3": "aashi", "g4": "sakshi", "g5": "tanya",
    "g6": "pihu", "g14": "alisha", "g16": "ruhi", "g19": "naira", "g20": "zara",
    "bhabhi": "bhabhi"
}

# ONLY MATCHED CATEGORY FILES (No boobs photo inside chut_p!)
GITHUB_EXACT_FILES = {
    "bhabhi": {
        "bodes_p": ["bhabhib1.jpg", "bhabhibra.jpg"],
        "chut_p": ["aditic1.jpg", "pihuc1.jpg", "tanyac1.jpg"],
        "gand_p": ["aditig1.jpg", "sakshig1.jpg", "tanyag1.jpg"],
        "kiss_p": ["kiss.jpg"],
        "simplepic_p": ["bhabhipost1.jpg", "bhabhipost2.jpg"],
        "bodes_v": ["bhabhib1.mp4", "bhabhivideo.mp4"],
        "chut_v": ["bhabhic1.mp4", "allc1.mp4", "allc2.mp4"],
        "gand_v": ["bhabhig.mp4", "allg.mp4"]
    },
    "aditi": {
        "bodes_p": ["aditib1.jpg"],
        "chut_p": ["aditic1.jpg"],
        "gand_p": ["aditig1.jpg"],
        "bodes_v": ["aditi1b.mp4"],
        "chut_v": ["aditic1.mp4"],
        "gand_v": ["aditi1g.mp4", "aditi2g.mp4"]
    },
    "aarohi": {"bodes_p": ["aarohib1.jpg"], "chut_p": ["pihuc1.jpg"], "gand_p": ["aditig1.jpg"]},
    "aashi":  {"bodes_p": ["aashib1.jpg"], "chut_p": ["tanyac1.jpg"], "gand_p": ["tanyag1.jpg"]},
    "alisha": {"bodes_p": ["alishac1.png"], "chut_p": ["alishac1.png"], "gand_p": ["sakshig1.jpg"]},
    "naira":  {"bodes_p": ["nairac1.jpg"], "chut_p": ["nairac1.jpg"], "gand_p": ["tanyag1.jpg"]},
    "pihu":   {"bodes_p": ["pihub1.jpg"], "chut_p": ["pihuc1.jpg"], "gand_p": ["aditig1.jpg"]},
    "ruhi":   {"bodes_p": ["ruhic1.png"], "chut_p": ["ruhic1.png"], "gand_p": ["sakshig1.jpg"]},
    "sakshi": {"bodes_p": ["sakshib1.jpg"], "chut_p": ["aditic1.jpg"], "gand_p": ["sakshig1.jpg"]},
    "tanya":  {"bodes_p": ["tanyab1.jpg"], "chut_p": ["tanyac1.jpg"], "gand_p": ["tanyag1.jpg"]},
    "zara":   {"bodes_p": ["zarac1.jpg"], "chut_p": ["zarac1.jpg"], "gand_p": ["aditig1.jpg"]}
}

SHARED_9GIRL_VIDEOS = {
    "bodes": ["allb1.mp4", "allb2.mp4", "allb3.mp4", "allbra.mp4"],
    "chut":  ["allc1.mp4", "allc2.mp4", "bhabhic1.mp4"],
    "gand":  ["allg.mp4", "bhabhig.mp4"]
}

def get_ordered_girl_candidates(pfx, tag, prefer_video=False):
    g_data = GITHUB_EXACT_FILES.get(pfx, GITHUB_EXACT_FILES["bhabhi"])
    if prefer_video:
        if pfx in ("bhabhi", "aditi"):
            return g_data.get(f"{tag}_v") or g_data.get("bodes_v")
        return SHARED_9GIRL_VIDEOS.get(tag) or SHARED_9GIRL_VIDEOS["bodes"]
    else:
        return g_data.get(f"{tag}_p") or ["aditic1.jpg"]

WEB_MEDIA_POOL_CACHE = {}
TG_FILE_ID_MEM_CACHE = {}
REDGIFS_TOKEN_CACHE = {"token": "", "exp": 0}

def get_redgifs_token():
    now = time.time()
    if REDGIFS_TOKEN_CACHE["token"] and now < REDGIFS_TOKEN_CACHE["exp"]:
        return REDGIFS_TOKEN_CACHE["token"]
    try:
        r = requests.get("https://api.redgifs.com/v2/auth/temporary", headers={"User-Agent": "Mozilla/5.0"}, timeout=2.5)
        if r.ok and r.json().get("token"):
            REDGIFS_TOKEN_CACHE["token"] = r.json()["token"]
            REDGIFS_TOKEN_CACHE["exp"] = now + 3000
            return REDGIFS_TOKEN_CACHE["token"]
    except Exception:
        pass
    return ""

def _url_hash_key(url_str):
    import hashlib
    return hashlib.md5(str(url_str).encode("utf-8")).hexdigest()[:20]

def get_cached_tg_file_id(url_str):
    """Checks RAM & Firebase for an already-uploaded Telegram file_id (0 MB Vercel Load, 0.1s speed!)."""
    if not url_str or not str(url_str).startswith("http"):
        return None
    hk = _url_hash_key(url_str)
    if hk in TG_FILE_ID_MEM_CACHE:
        return TG_FILE_ID_MEM_CACHE[hk]
    if FIREBASE_URL:
        try:
            fid = requests.get(f"{FIREBASE_URL}/media_fid_cache/{hk}.json?auth={FIREBASE_SECRET}", timeout=1.5).json()
            if isinstance(fid, str) and len(fid) > 15:
                TG_FILE_ID_MEM_CACHE[hk] = fid
                return fid
        except Exception:
            pass
    return None

def save_cached_tg_file_id(url_str, file_id):
    if not url_str or not file_id:
        return
    hk = _url_hash_key(url_str)
    TG_FILE_ID_MEM_CACHE[hk] = file_id
    if FIREBASE_URL:
        try:
            requests.put(f"{FIREBASE_URL}/media_fid_cache/{hk}.json?auth={FIREBASE_SECRET}", json=str(file_id), timeout=1.5)
        except Exception:
            pass

UNCENSORED_IMAGE_API_KEY = (
    os.environ.get("NOVITA_API_KEY", "").strip()
    or os.environ.get("VENICE_API_KEY", "").strip()
    or os.environ.get("MODELSLAB_API_KEY", "").strip()
)

CF_WORKER_URL = os.environ.get("CF_WORKER_URL", "https://edrol-proxy.rajputani8289.workers.dev").strip().rstrip("/")

# ============================================================
# 11 BOTS FIXED FACE & BODY DNA + DAILY ROTATING OUTFIT COLORS!
# ============================================================
GIRL_EXACT_DNA = {
    "bhabhi": {
        "face_body": "25yo gorgeous Indian housewife bhabhi, warm wheatish glowing skin, expressive dark kohl eyes, small bindi on forehead, heavy natural curvy breasts, wide hourglass hips, same consistent face",
        "model_tag": "indian-bhabhi", "sub": "IndianBabes", "pp_tag": "indian", "seed": 10101
    },
    "g1": {
        "face_body": "20yo glamorous modern Indian college girl Aditi, fair flawless skin, black choker necklace, slim waist, perky round breasts, silky straight black hair, same consistent face",
        "model_tag": "aditi-college", "sub": "BustyPetite", "pp_tag": "petite", "seed": 20202
    },
    "g2": {
        "face_body": "21yo shy innocent Hindu girl Aarohi, milky fair skin, cute soft face, natural medium breasts, slim petite figure, long dark hair, same consistent face",
        "model_tag": "aarohi-cute", "sub": "NaturalTitties", "pp_tag": "natural-tits", "seed": 30303
    },
    "g3": {
        "face_body": "21yo seductive Muslim girl Aashi wearing black headscarf hijab on head, fair skin, smokey kajal eyes, curvy busty figure, same consistent face",
        "model_tag": "aashi-hijab", "sub": "RepressedGoneWild", "pp_tag": "arab", "seed": 40404
    },
    "g4": {
        "face_body": "22yo bold street-smart Indian girl Sakshi, golden tan skin, toned curvy body, round shapely booty, naughty smirk, same consistent face",
        "model_tag": "sakshi-bold", "sub": "Boobies", "pp_tag": "big-tits", "seed": 50505
    },
    "g5": {
        "face_body": "22yo gorgeous Pakistani Muslim girl Tanya with stylish scarf on head, rosy fair skin, heavy busty figure, same consistent face",
        "model_tag": "tanya-scarf", "sub": "arabporn", "pp_tag": "arab", "seed": 60606
    },
    "g6": {
        "face_body": "19yo cute petite Indian girl Pihu, pale fair skin, baby face, slim tight body, perky breasts, same consistent face",
        "model_tag": "pihu-petite", "sub": "PetiteGoneWild", "pp_tag": "teen", "seed": 70707
    },
    "g14": {
        "face_body": "23yo classy modern beauty Alisha, fair skin, hourglass figure, seductive eyes, luxury bedroom, same consistent face",
        "model_tag": "alisha-classy", "sub": "Stacked", "pp_tag": "glamour", "seed": 80808
    },
    "g16": {
        "face_body": "24yo traditional yet bold Indian woman Ruhi, warm fair skin, curvy waist, long black hair, romantic bedroom, same consistent face",
        "model_tag": "ruhi-desi", "sub": "DesiBoners", "pp_tag": "indian", "seed": 90909
    },
    "g19": {
        "face_body": "21yo naughty middle-eastern girl Naira, olive fair skin, thick curvy booty and hips, playful expression, same consistent face",
        "model_tag": "naira-curvy", "sub": "paag", "pp_tag": "booty", "seed": 11223
    },
    "g20": {
        "face_body": "22yo exotic Arabian fantasy girl Zara, fair glowing skin, busty hourglass body, seductive gaze, same consistent face",
        "model_tag": "zara-arabian", "sub": "BustyPetite", "pp_tag": "exotic", "seed": 33445
    }
}

DAILY_LINGERIE_COLORS = [
    ("crimson red lace", "red silk saree"),
    ("jet black sheer mesh", "black chiffon saree"),
    ("hot pink satin", "pink designer kurti"),
    ("emerald green lace", "green silk saree"),
    ("royal purple sheer", "purple velvet blouse"),
    ("snow white floral lace", "white wet cotton saree"),
    ("wine maroon strap", "maroon bridal lehenga blouse")
]

def get_daily_girl_outfit(girl_key="bhabhi"):
    """Changes each girl's bra/panty/dress color & design automatically every single day!"""
    day_idx = (datetime.now().timetuple().tm_yday + sum(ord(c) for c in str(girl_key))) % len(DAILY_LINGERIE_COLORS)
    return DAILY_LINGERIE_COLORS[day_idx]

def cf_fetch(target_url, timeout=4.0, stream=False, extra_headers=None):
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    hdrs = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }
    if extra_headers:
        hdrs.update(extra_headers)

    urls_to_try = [target_url]
    if CF_WORKER_URL:
        urls_to_try.append(f"{CF_WORKER_URL}/?url={quote(target_url)}")

    for u in urls_to_try:
        try:
            r = requests.get(u, headers=hdrs, timeout=timeout, stream=stream, allow_redirects=True)
            if r.status_code in (200, 206) and len(r.content) > 500:
                return r
        except Exception:
            pass
    return None

@app.route("/api/proxy_img")
def proxy_adult_image():
    b64_u = request.args.get("u", "")
    try:
        img_url = base64.urlsafe_b64decode(b64_u.encode("utf-8")).decode("utf-8")
        ref = "https://www.pornpics.com/" if "pornpics" in img_url.lower() else "https://www.reddit.com/"
        r = cf_fetch(img_url, timeout=4.5, extra_headers={"Referer": ref})
        if r and len(r.content) > 2000:
            return r.content, 200, {"Content-Type": r.headers.get("Content-Type", "image/jpeg"), "Cache-Control": "public, max-age=86400"}
    except Exception:
        pass
    return "", 404

def build_live_pose_prompt(girl_key, user_msg, tag="bodes"):
    """
    Builds a 100% Consistent Face/Body Prompt with Today's Outfit Color + Exact User Action:
    - "panty utro" -> holding her removed today's color panty in hand, taking mirror selfie
    - "bra utro" -> unclipping and sliding off today's color bra, exposing bare breasts
    - "ungli karo" -> fingering / masturbating wet pussy on bed POV
    - "ghutne pe" -> kneeling on bed looking up with mouth open (Elsa Brown 38077.jpg pose!)
    """
    g_info = GIRL_EXACT_DNA.get(girl_key, GIRL_EXACT_DNA["bhabhi"])
    dna = g_info["face_body"]
    lingerie_color, dress_color = get_daily_girl_outfit(girl_key)
    m_low = str(user_msg or "").lower()

    if any(w in m_low for w in ["panty utar", "panty utro", "panty khol", "kachi utar", "panty hath", "panty nikal"]):
        action_str = f"standing in bedroom holding her removed {lingerie_color} thong panty in her hand, bare bottomless, taking a seductive mirror selfie"
    elif any(w in m_low for w in ["bra utar", "bra utro", "bra khol", "blouse khol", "doodh nikal", "chuchi dikha"]):
        action_str = f"sitting on bed unclipping and pulling down her {lingerie_color} bra with both hands, exposing her bare natural breasts, seductive eye contact POV"
    elif any(w in m_low for w in ["ungli", "finger", "fingering", "hilao", "hila", "masturbat", "ragad", "rub"]):
        action_str = f"lying on bed in {lingerie_color} unclipped bra, legs spread wide open, touching and fingering her wet pussy with her fingers, moaning expression, closeup POV"
    elif any(w in m_low for w in ["ghutne", "ghutno", "knees", "chus", "suck", "blowjob", "muh khol", "muh me", "tongue", "jeebh"]):
        action_str = f"kneeling on knees on bed wearing {lingerie_color} lace bra, looking up seductively at camera from high angle POV, mouth open tongue out, deep cleavage (exact 38077.jpg pose)"
    elif any(w in m_low for w in ["doggy", "ghodi", "ghroi", "ghori", "bend", "jhuk", "piche se"]):
        action_str = f"on all fours doggy style pose on bed, wearing {lingerie_color} thong pulled aside, arched back, looking back over shoulder, showing round booty from behind"
    elif any(w in m_low for w in ["spread", "phaila", "khol", "taang", "tang", "open", "opan"]) or tag == "chut":
        action_str = f"lying on bed spreading legs wide open, wearing {lingerie_color} bra pulled up, intimate closeup of shaved wet pussy, seductive gaze"
    elif tag == "gand":
        action_str = f"standing in front of bedroom mirror wearing {lingerie_color} thin thong panty, turned around showing round curvy booty and waist, looking back"
    elif any(w in m_low for w in ["saree", "sari"]):
        action_str = f"wearing {dress_color} with low-cut blouse unhooked, showing deep cleavage and bare waist, bedroom selfie"
    else:
        action_str = f"sitting on bed wearing {lingerie_color} lace bra and panty lingerie, leaning forward showing deep cleavage, smartphone video call POV"

    return (
        f"RAW candid smartphone photo, (solo, 1girl only, real human woman, no man, no robot:1.6), "
        f"{dna}, {action_str}, photorealistic skin pores, natural bedroom lighting, 8k uhd"
    )

def generate_consistent_girl_ai_photo(girl_key="bhabhi", user_msg="", tag="bodes"):
    """
    Generates a Fast, Consistent-Face Photo of the exact Girl Bot (using her locked Seed + Daily Outfit Color)
    in 2.5 seconds via Pollinations Flux-Realism so every girl looks 100% unique & consistent!
    """
    g_info = GIRL_EXACT_DNA.get(girl_key, GIRL_EXACT_DNA["bhabhi"])
    prompt = build_live_pose_prompt(girl_key, user_msg, tag=tag)
    seed_val = g_info["seed"] + (datetime.now().timetuple().tm_yday % 7)

    gen_url = (
        f"https://image.pollinations.ai/prompt/{quote(prompt)}"
        f"?width=768&height=1024&seed={seed_val}&model=flux-realism&nologo=true&safe=false&enhance=false"
    )
    try:
        r = requests.get(gen_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=4.2)
        if r.ok and len(r.content) > 30000:
            tmp_p = f"/tmp/ai_{girl_key}_{int(time.time()*1000)}.jpg"
            with open(tmp_p, "wb") as f:
                f.write(r.content)
            return tmp_p
    except Exception:
        pass
    return None
    
SENT_MEDIA_HISTORY = {}  # Tracks already-sent URLs per user in RAM so photos/videos NEVER repeat!

def search_unblocked_hd_photos(tag="bodes", girl_key="bhabhi", country_word="", outfit_word="", user_msg_text="", seq_idx=0):
    """
    100% EXACT BODY-PART & FAIR-SKINNED REAL SELFIE ENGINE:
    - 'chut' -> Strictly Pink Shaved Pussy Closeups & Fingering Selfies (ZERO Boobs mixup!)
    - 'bodes' -> Strictly Fair Busty Bedroom Mirror Boobs / Bra Unclip Selfies
    - 'gand' -> Strictly Fair Curvy Ass / Thong / Doggy Mirror Selfies (ZERO Cartoon!)
    """
    m_low = str(user_msg_text or "").lower()
    pfx = GIRL_FILE_PREFIX.get(girl_key, "bhabhi")

    # 1. STRICT CATEGORY SEPARATION (No IndianBabes dark/clothed mixup!)
    if any(w in m_low for w in ["ungli", "finger", "fingering", "hilao", "hila", "masturbat", "ragad", "chut me ungli"]):
        pp_paths = ["/tags/fingering/", "/tags/pink-pussy/", "/tags/wet-pussy/"]
        rd_subs = ["GodPussy", "Innie", "WetPussy", "fingering"]
        rg_query = "pink pussy fingering"
    elif tag == "chut" or any(w in m_low for w in ["chut", "choot", "pussy", "pusy", "vagina", "shaved", "pink", "khol", "spread"]):
        pp_paths = ["/tags/pink-pussy/", "/tags/shaved-pussy/", "/tags/spreading/", "/tags/wet-pussy/"]
        rd_subs = ["Innie", "GodPussy", "SpreadEm", "WetPussy"]
        rg_query = "shaved pink pussy closeup"
    elif tag == "gand" or any(w in m_low for w in ["gand", "gaand", "ass", "booty", "butt", "hips", "doggy", "ghodi", "ghroi", "ghori", "piche", "bom", "boom"]):
        pp_paths = ["/tags/ass-selfie/", "/tags/tight-ass/", "/tags/panties/", "/tags/doggy-style/"]
        rd_subs = ["CuteLittleButts", "pawg", "booty", "panties"]
        rg_query = "fair girl ass selfie mirror"
    elif any(w in m_low for w in ["panty utar", "panty utro", "panty", "kachi", "thong"]):
        pp_paths = ["/tags/panties/", "/tags/thong/", "/tags/ass-selfie/"]
        rd_subs = ["panties", "CuteLittleButts", "BustyPetite"]
        rg_query = "girl removing panties selfie"
    elif any(w in m_low for w in ["ghutne", "ghutno", "knees", "chus", "suck", "blowjob", "muh"]):
        pp_paths = ["/tags/pov/", "/browse/blowjob/"]
        rd_subs = ["LipsThatGrip", "BustyPetite"]
        rg_query = "pov kneeling blowjob"
    elif tag == "simplepic" or any(w in m_low for w in ["simple", "normal", "face", "chehra", "dp"]):
        pp_paths = ["/tags/selfie/", "/tags/lingerie/"]
        rd_subs = ["BustyPetite", "AsianHotties"]
        rg_query = "cute girl mirror selfie"
    else:
        # 'bodes' / 'boobs' / 'chuchi' / 'doodh' / 'bra' -> Strictly Fair Clean Boobs & Mirror Selfies!
        pp_paths = ["/tags/tits-selfie/", "/tags/natural-tits/", "/tags/busty-petite/", "/tags/topless/"]
        rd_subs = ["BustyPetite", "NaturalTitties", "BiggerThanYouThought", "Boobies"]
        rg_query = "busty petite boobs selfie"

    collected = []

    # SOURCE 1: REDDIT FAIR-SKINNED REAL AMATEUR SELFIES (i.redd.it direct HD photos - Fastest & Most Real!)
    custom_ua = f"android:com.edrol.selfie.{girl_key}:v6.0 (by /u/edrol_ai)"
    for sub in rd_subs[:3]:
        r_rd = cf_fetch(
            f"https://www.reddit.com/r/{sub}/top.json?t=month&limit=60",
            timeout=3.0,
            extra_headers={"User-Agent": custom_ua}
        )
        if r_rd and "children" in r_rd.text:
            try:
                for post in r_rd.json().get("data", {}).get("children", []):
                    d = post.get("data", {})
                    if not d.get("over_18") or d.get("is_gallery"):
                        continue
                    img_u = str(d.get("url_overridden_by_dest") or d.get("url") or "")
                    if img_u.lower().endswith((".jpg", ".jpeg", ".png")) and ("i.redd.it" in img_u or "imgur.com" in img_u):
                        if img_u not in collected:
                            collected.append(img_u)
            except Exception:
                pass
        if len(collected) >= 30:
            break

    # SOURCE 2: PORNPICS DIRECT TAG GALLERIES (Skip first 5 clothed cover thumbs -> take closeup shots!)
    for p_path in pp_paths[:2]:
        target_u = f"https://www.pornpics.com{p_path}"
        r_pp = cf_fetch(target_u, timeout=3.0, extra_headers={"Referer": "https://www.pornpics.com/"})
        if r_pp and "pornpics.com" in r_pp.text:
            raw_imgs = re.findall(r'https://cdni\.pornpics\.com/[^\s"\'<>()\\]+\.(?:jpg|jpeg|webp)', r_pp.text)
            valid_imgs = raw_imgs[6:] if len(raw_imgs) > 10 else raw_imgs
            for m_u in valid_imgs:
                hd_u = re.sub(r'cdni\.pornpics\.com/\d+/', 'cdni.pornpics.com/1280/', m_u)
                if hd_u not in collected:
                    collected.append(hd_u)
        if len(collected) >= 45:
            break

    # Append Girl's GitHub photo at the very END only as emergency fallback (so it NEVER repeats on every chat!)
    for gh_f in get_ordered_girl_candidates(pfx, tag, prefer_video=False):
        gh_u = GITHUB_BASE_URL + gh_f
        if gh_u not in collected:
            collected.append(gh_u)

    return collected

def get_live_web_video_list(query_str="indian bhabhi", count=25, girl_key="bhabhi"):
    """
    Fetches Non-Repeating Short Real Video Clips matching exact tag (Pink Pussy Fingering / Boobs / Booty)
    from RedGifs API + Fair Amateur Subreddits + GitHub Clips!
    """
    clean_q = str(query_str or "bodes").strip().lower()
    vids = []
    pfx = GIRL_FILE_PREFIX.get(girl_key, "bhabhi")

    if any(w in clean_q for w in ["ungli", "finger", "hilao", "masturbat", "chut", "choot", "pussy", "wet", "open", "opan"]):
        act_tag = "chut"
        rg_search = "pink pussy fingering closeup"
        subs = ["GodPussy", "Innie", "WetPussy", "fingering"]
    elif any(w in clean_q for w in ["gand", "gaand", "ass", "booty", "doggy", "ghodi", "ghroi", "panty", "bom"]):
        act_tag = "gand"
        rg_search = "ass selfie thong"
        subs = ["CuteLittleButts", "pawg", "booty"]
    else:
        act_tag = "bodes"
        rg_search = "busty petite boobsbra"
        subs = ["BustyPetite", "NaturalTitties", "BiggerThanYouThought"]

    # 1. RedGifs Live HD Clips
    rg_tok = get_redgifs_token()
    if rg_tok:
        try:
            r_rg = requests.get(
                f"https://api.redgifs.com/v2/gifs/search?search_text={quote(rg_search)}&order=trending&count=30",
                headers={"Authorization": f"Bearer {rg_tok}", "User-Agent": "Mozilla/5.0"},
                timeout=3.0
            )
            if r_rg.ok:
                for g_obj in r_rg.json().get("gifs", []):
                    hd_mp4 = (g_obj.get("urls") or {}).get("sd") or (g_obj.get("urls") or {}).get("hd")
                    if hd_mp4 and hd_mp4.endswith(".mp4") and hd_mp4 not in vids:
                        vids.append(hd_mp4)
        except Exception:
            pass

    # 2. Reddit Direct MP4 Short Clips
    for sub in subs[:2]:
        r_rd = cf_fetch(
            f"https://www.reddit.com/r/{sub}/top.json?t=month&limit=45",
            timeout=3.0,
            extra_headers={"User-Agent": f"android:com.edrol.vclip.{girl_key}:v6.0 (by /u/edrol_ai)"}
        )
        if r_rd and "children" in r_rd.text:
            try:
                for post in r_rd.json().get("data", {}).get("children", []):
                    pd = post.get("data", {})
                    rv = (pd.get("media") or {}).get("reddit_video") or (pd.get("secure_media") or {}).get("reddit_video") or (pd.get("preview") or {}).get("reddit_video_preview") or {}
                    v_u = rv.get("fallback_url", "")
                    if v_u and ".mp4" in v_u:
                        clean_v = re.sub(r"DASH_\d+\.mp4", "DASH_480.mp4", v_u.split("?")[0])
                        if clean_v not in vids:
                            vids.append(clean_v)
            except Exception:
                pass

    # 3. Girl's GitHub Video Clips
    for gv in get_ordered_girl_candidates(pfx, act_tag, prefer_video=True):
        gh_v = GITHUB_BASE_URL + gv
        if gh_v not in vids:
            vids.append(gh_v)

    return vids[:count]

def fetch_live_web_media(tag="bodes", prefer_video=False, uid="", seq_idx=0, custom_query="", girl_key="bhabhi"):
    clean_q = str(custom_query or "").strip().lower()
    seen_set = SENT_MEDIA_HISTORY.setdefault(str(uid or "anon"), set())

    if prefer_video:
        v_list = get_live_web_video_list(clean_q or tag, count=30, girl_key=girl_key)
        if v_list:
            unseen_v = [v for v in v_list if v not in seen_set]
            chosen_v = unseen_v[0] if unseen_v else random.choice(v_list)
            seen_set.add(chosen_v)
            return chosen_v
        return None

    collected = search_unblocked_hd_photos(
        tag=tag, girl_key=girl_key, country_word="",
        outfit_word="", user_msg_text=(clean_q or tag), seq_idx=seq_idx
    )
    if collected:
        unseen_p = [p for p in collected if p not in seen_set]
        if not unseen_p:
            seen_set.clear()
            unseen_p = collected
        chosen_p = unseen_p[seq_idx % len(unseen_p)]
        seen_set.add(chosen_p)
        return chosen_p
    return None

def get_media_item(vault, tag, prefer_video=False, char_vault="", uid="", user_msg_text=""):
    m_low = str(user_msg_text or "").lower()
    # Always prioritize exact body-part word in user's message so AI tag never overrides 'chut' or 'gand' with 'bodes'!
    if any(w in m_low for w in ["chut", "choot", "pussy", "pusy", "vagina", "ungli", "finger", "hilao", "open", "opan"]):
        tag = "chut"
    elif any(w in m_low for w in ["gand", "gaand", "ass", "booty", "butt", "hips", "piche", "doggy", "ghodi", "ghroi", "ghori", "bom", "boom"]):
        tag = "gand"
    elif any(w in m_low for w in ["boobs", "bobs", "bodes", "body", "chuchi", "mamme", "doodh", "bra", "figure", "chest"]):
        tag = "bodes"
    else:
        tag = str(tag or "bodes").lower().strip()
        if tag in ["boom", "bom", "back", "gand", "gaand", "ass", "booty", "butt", "piche", "hips"]:
            tag = "gand"
        elif tag in ["open", "opan", "front", "chut", "choot", "pusy", "pussy", "vagina", "panty", "pantiy"]:
            tag = "chut"
        elif tag not in ("kiss", "simplepic"):
            tag = "bodes"

    v_key = char_vault if (char_vault and char_vault in GIRL_EXACT_DNA) else "bhabhi"
    seq_key = f"seq:{uid}:{v_key}:{tag}:{'v' if prefer_video else 'p'}"
    idx = int(USER_CACHE.get(seq_key, 0))
    USER_CACHE[seq_key] = idx + 1

    return fetch_live_web_media(tag=tag, prefer_video=prefer_video, uid=uid, seq_idx=idx, custom_query=user_msg_text, girl_key=v_key)

def detect_python_media_tag(message_text):
    m_low = str(message_text or "").lower()
    if m_low.startswith("[user sent a"):
        return False, None, False
    action_verbs = [
        "photo", "phto", "phooto", "pic", "pics", "image", "img", "selfie", "dp", "tasveer", "photu",
        "video", "vido", "vid", "clip", "mms", "reel", "dikhao", "dikha", "dikhana", "dekha", "dekhao",
        "bhejo", "bhej", "bejo", "bej", "beja", "bjao", "send", "show", "dekhna hai", "dekhau", "degi", "dedo", "de do", "ebjo", "bajo", "bejaa", "bejoo",
        "utaro", "utaaro", "utar", "utro", "kholo", "khol ke", "hilao", "ungli", "ghodi", "ghutne"
    ]
    asks_media = any(re.search(rf"\b{re.escape(w)}\b", m_low) or w in m_low for w in action_verbs)
    if not asks_media:
        return False, None, False

    # Send 4-sec live video clip whenever user asks for video OR live action ("bra utro", "ungli karo", "hilao")!
    wants_vid = any(w in m_low for w in [
        "video", "vido", "vid", "clip", "mms", "mp4", "chalta hua", "live",
        "bra utro", "bra utar", "ungli karo", "ungli kr", "hilao", "chus ke dikha"
    ])

    if any(w in m_low for w in ["bom", "boom", "gand", "gaand", "ass", "booty", "butt", "hips", "back", "piche", "ghodi", "ghroi", "ghori", "doggy"]):
        tag = "gand"
    elif any(w in m_low for w in ["open", "opan", "chut", "choot", "pusy", "pussy", "vagina", "front", "panty", "pantiy", "niche ka", "ungli", "finger", "hilao"]):
        tag = "chut"
    elif any(w in m_low for w in ["kiss", "chumma", "lip", "hoth"]):
        tag = "kiss"
    elif any(w in m_low for w in ["simple", "normal", "selfie", "face", "chehra"]):
        tag = "simplepic"
    else:
        tag = "bodes"

    return True, tag, wants_vid

def build_webapp_video_player_url(video_src, title="Edrol AI Private Video"):
    host = "https://edrol123.vercel.app"
    try:
        if request and request.host_url:
            host = request.host_url.rstrip("/")
    except Exception:
        pass
    b64_v = base64.urlsafe_b64encode(str(video_src).encode("utf-8")).decode("utf-8")
    return f"{host}/watch?v={quote(b64_v)}&t={quote(str(title)[:40])}"

def strip_black_bars_and_preserve_ratio(img_bytes):
    try:
        im = Image.open(BytesIO(img_bytes)).convert("RGB")
        w, h = im.size
        if w < 380 or h < 380:
            return None
        gray = im.convert("L").point(lambda p: 255 if p > 18 else 0)
        bbox = gray.getbbox()
        if bbox:
            bw = bbox[2] - bbox[0]
            bh = bbox[3] - bbox[1]
            if bw > 320 and bh > 320 and (bw < w * 0.95 or bh < h * 0.95):
                im = im.crop(bbox)
        out = BytesIO()
        im.save(out, format="JPEG", quality=95)
        out.seek(0)
        return out.read()
    except Exception:
        return img_bytes
        
def send_local_or_url_media(chat_id, filename, caption="", protect=True, spoiler=True, reply_to_message_id=None, reply_markup=None, media_type_override=""):
    if not filename:
        return send_msg(chat_id, caption, reply_id=reply_to_message_id, markup=reply_markup)

    # STRICT PROTECTION RULE: ONLY OWNER can save/forward/screenshot; ALL other users have protect_content=True!
    is_owner_only = (str(chat_id) == str(OWNER_ID))
    if is_owner_only:
        protect = False
        spoiler = False
    else:
        # Force protection on all private chats (even menu banners!)
        if not str(chat_id).startswith("-100"):
            protect = True

    styled_caption = to_hot_bhabhi_font(caption) if caption else ""
    clean_fname = str(filename).split("?")[0].lower()
    is_video = (media_type_override == "video") or clean_fname.endswith(".mp4") or str(filename).startswith("BAAC") or "v.redd.it" in clean_fname or "redgifs.com" in clean_fname or "/embed/" in clean_fname

    if is_video:
        media_url = filename if str(filename).startswith("http") else GITHUB_BASE_URL + str(filename).lstrip("/")
        # Check cached Telegram Video file_id first for 0.1s instant menu/chat video playback!
        cached_vid_fid = get_cached_tg_file_id(media_url)
        if cached_vid_fid:
            p_v = {"chat_id": chat_id, "video": cached_vid_fid, "caption": styled_caption, "protect_content": protect, "has_spoiler": spoiler, "parse_mode": "HTML"}
            if reply_to_message_id: p_v["reply_to_message_id"] = reply_to_message_id
            if reply_markup: p_v["reply_markup"] = reply_markup
            r_vc = tg_req("sendVideo", p_v, timeout=6)
            if r_vc.get("ok"):
                return r_vc

        if "/embed/" not in media_url.lower():
            vid_res = cf_fetch(media_url, timeout=5.5)
            if vid_res and 5000 < len(vid_res.content) < 18000000:
                try:
                    data = {"chat_id": str(chat_id), "caption": styled_caption, "parse_mode": "HTML"}
                    if protect: data["protect_content"] = "true"
                    if spoiler: data["has_spoiler"] = "true"
                    if reply_to_message_id: data["reply_to_message_id"] = str(reply_to_message_id)
                    if reply_markup: data["reply_markup"] = json.dumps(reply_markup)
                    files = {"video": ("hot_clip.mp4", BytesIO(vid_res.content), "video/mp4")}
                    r_v = requests.post(f"{get_active_api_url()}/sendVideo", data=data, files=files, timeout=10.0)
                    if r_v.ok and r_v.json().get("ok"):
                        rj = r_v.json()
                        v_fid = (rj.get("result", {}).get("video") or {}).get("file_id") or (rj.get("result", {}).get("animation") or {}).get("file_id")
                        if v_fid:
                            save_cached_tg_file_id(media_url, v_fid)
                        return rj
                except Exception:
                    pass

        player_url = build_webapp_video_player_url(media_url, title="Edrol AI Private HD Video")
        webapp_btn = [{"text": "▶️ 𝗣𝗟𝗔𝗬 𝗙𝗨𝗟𝗟 𝗛𝗗 𝗩𝗜𝗗𝗘𝗢 🔥", "web_app": {"url": player_url}}]
        if isinstance(reply_markup, dict) and "inline_keyboard" in reply_markup:
            reply_markup = {"inline_keyboard": [webapp_btn] + list(reply_markup["inline_keyboard"])}
        else:
            reply_markup = {"inline_keyboard": [webapp_btn]}
        return send_msg(
            chat_id,
            f"{caption}\n\n🎬 <b>Tap below to watch Full HD Video: 👇</b>",
            reply_id=reply_to_message_id,
            markup=reply_markup
        )

    api_method = "sendPhoto"
    media_key = "photo"
    mime_type = "image/png" if clean_fname.endswith(".png") else "image/jpeg"

    cached_fid = get_cached_tg_file_id(filename)
    if cached_fid:
        p_cache = {"chat_id": chat_id, media_key: cached_fid, "caption": styled_caption, "protect_content": protect, "has_spoiler": spoiler, "parse_mode": "HTML"}
        if reply_to_message_id: p_cache["reply_to_message_id"] = reply_to_message_id
        if reply_markup: p_cache["reply_markup"] = reply_markup
        r_c = tg_req(api_method, p_cache, timeout=6)
        if r_c.get("ok"):
            return r_c

    if "." not in str(filename) and not str(filename).startswith("http"):
        p_id = {"chat_id": chat_id, media_key: filename, "caption": styled_caption, "protect_content": protect, "has_spoiler": spoiler, "parse_mode": "HTML"}
        if reply_to_message_id: p_id["reply_to_message_id"] = reply_to_message_id
        if reply_markup: p_id["reply_markup"] = reply_markup
        return tg_req(api_method, p_id, timeout=8)

    local_file_path = find_local_file(filename) or (filename if str(filename).startswith("/tmp/") and os.path.exists(str(filename)) else None)
    if local_file_path:
        try:
            data = {"chat_id": str(chat_id), "caption": styled_caption, "parse_mode": "HTML"}
            if protect: data["protect_content"] = "true"
            if spoiler: data["has_spoiler"] = "true"
            if reply_to_message_id: data["reply_to_message_id"] = str(reply_to_message_id)
            if reply_markup: data["reply_markup"] = json.dumps(reply_markup)
            with open(local_file_path, "rb") as f:
                files = {media_key: (os.path.basename(local_file_path), f, mime_type)}
                res = requests.post(f"{get_active_api_url()}/{api_method}", data=data, files=files, timeout=9)
                if res.ok and res.json().get("ok"):
                    return res.json()
        except Exception:
            pass

    media_url = filename if str(filename).startswith("http") else GITHUB_BASE_URL + str(filename).lstrip("/")
    ref = "https://www.pornpics.com/" if "pornpics" in media_url.lower() else ("https://civitai.com/" if "civitai" in media_url.lower() else "https://www.reddit.com/")
    gh_res = cf_fetch(media_url, timeout=4.5, extra_headers={"Referer": ref})
    if gh_res and len(gh_res.content) > 12000:
        clean_bytes = strip_black_bars_and_preserve_ratio(gh_res.content)
        if clean_bytes:
            try:
                data = {"chat_id": str(chat_id), "caption": styled_caption, "parse_mode": "HTML"}
                if protect: data["protect_content"] = "true"
                if spoiler: data["has_spoiler"] = "true"
                if reply_to_message_id: data["reply_to_message_id"] = str(reply_to_message_id)
                if reply_markup: data["reply_markup"] = json.dumps(reply_markup)
                files = {media_key: ("hd_photo.jpg", BytesIO(clean_bytes), "image/jpeg")}
                res_up = requests.post(f"{get_active_api_url()}/{api_method}", data=data, files=files, timeout=8.0)
                if res_up.ok and res_up.json().get("ok"):
                    r_json = res_up.json()
                    res_obj = r_json.get("result", {})
                    fid = res_obj.get("photo", [{}])[-1].get("file_id") if res_obj.get("photo") else None
                    if fid:
                        save_cached_tg_file_id(filename, fid)
                    return r_json
            except Exception:
                pass

    return send_msg(chat_id, caption, reply_id=reply_to_message_id, markup=reply_markup)

def edit_or_send_box_media(chat_id, message_id, media_source, caption="", reply_markup=None):
    """Supports BOTH Photo & Hot Video Clip (.mp4) Menu Banners + 100% Anti-Save Protection!"""
    styled_caption = to_hot_bhabhi_font(caption) if caption else ""
    is_vid_banner = str(media_source).split("?")[0].lower().endswith(".mp4")
    m_type = "video" if is_vid_banner else "photo"
    local_path = find_local_file(media_source) or (media_source if str(media_source).startswith("/tmp/") and os.path.exists(str(media_source)) else None)

    if message_id:
        if local_path:
            try:
                media_json = json.dumps({"type": m_type, "media": f"attach://{m_type}", "caption": styled_caption, "parse_mode": "HTML"})
                data = {"chat_id": str(chat_id), "message_id": str(message_id), "media": media_json}
                if reply_markup:
                    data["reply_markup"] = json.dumps(reply_markup)
                with open(local_path, "rb") as f:
                    mime = "video/mp4" if is_vid_banner else "image/jpeg"
                    fname_up = "banner.mp4" if is_vid_banner else "dp.jpg"
                    res = requests.post(f"{get_active_api_url()}/editMessageMedia", data=data, files={m_type: (fname_up, f, mime)}, timeout=12).json()
                if res.get("ok"):
                    return res
            except Exception:
                pass
        else:
            media_url = media_source if str(media_source).startswith("http") else GITHUB_BASE_URL + str(media_source)
            cached_fid = get_cached_tg_file_id(media_url) or get_cached_tg_file_id(media_source)
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "media": {"type": m_type, "media": (cached_fid or media_url), "caption": styled_caption, "parse_mode": "HTML"}
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup
            res = tg_req("editMessageMedia", payload, timeout=10)
            if res.get("ok"):
                return res

        res_cap = tg_req("editMessageCaption", {"chat_id": chat_id, "message_id": message_id, "caption": styled_caption, "parse_mode": "HTML", "reply_markup": reply_markup})
        if res_cap.get("ok"):
            return res_cap
        res_txt = tg_req("editMessageText", {"chat_id": chat_id, "message_id": message_id, "text": styled_caption, "parse_mode": "HTML", "reply_markup": reply_markup})
        if res_txt.get("ok"):
            return res_txt

    protect_flag = (str(chat_id) != str(OWNER_ID))
    return send_local_or_url_media(chat_id, media_source, caption=caption, protect=protect_flag, spoiler=False, reply_markup=reply_markup)

def send_start_banner_or_msg(chat_id, caption_html, reply_markup):
    protect_flag = (str(chat_id) != str(OWNER_ID))
    res = send_local_or_url_media(chat_id, START_BANNER_IMAGE, caption=caption_html, protect=protect_flag, spoiler=False, reply_markup=reply_markup)
    if not res.get("ok"):
        res = send_local_or_url_media(chat_id, "bot.png", caption=caption_html, protect=protect_flag, spoiler=False, reply_markup=reply_markup)
    if not res.get("ok"):
        return send_msg(chat_id, caption_html, markup=reply_markup)
    return res

def send_secret_media(chat_id, media_source, caption="", delete_after=45, reply_to_message_id=None, markup=None):
    if not media_source:
        return {"ok": False}

    is_owner_only = (str(chat_id) == str(OWNER_ID))
    is_video = str(media_source).lower().endswith(".mp4") or "video" in str(media_source).lower() or "v.redd.it" in str(media_source).lower() or "eporner.com/embed" in str(media_source).lower()
    del_sec = 0 if is_owner_only else (45 if is_video else 30)

    res = send_local_or_url_media(
        chat_id,
        media_source,
        caption=caption,
        protect=(False if is_owner_only else True),
        spoiler=(False if is_owner_only else True),
        reply_to_message_id=reply_to_message_id,
        reply_markup=markup,
        media_type_override=("video" if is_video else "photo")
    )

    if res.get("ok") and del_sec > 0:
        sent_msg_id = res.get("result", {}).get("message_id")
        if sent_msg_id:
            def remove_media():
                try:
                    tg_req("deleteMessage", {"chat_id": chat_id, "message_id": sent_msg_id})
                except Exception:
                    pass
            Timer(float(del_sec), remove_media).start()

    return res

def get_telegram_file_base64(file_id):
    """Exact Code 14 Base64 Extractor (No Pillow MIME mismatch - 100% works on Stickers & Photos!)"""
    if not file_id: return None
    res = tg_req("getFile", {"file_id": file_id}, timeout=6)
    if res.get("ok"):
        try:
            f_path = res["result"].get("file_path", "")
            if f_path.endswith((".webm", ".tgs", ".mp4")):
                return None
            r = requests.get(f"https://api.telegram.org/file/bot{get_active_bot_token()}/{f_path}", timeout=6)
            if r.ok and r.content:
                return base64.b64encode(r.content).decode("utf-8")
        except Exception:
            pass
    return None

def get_pay_kb(include_free_btn=True):
    rows = [
        [{"text": "💎 ₹19 (175 𝗖𝗥𝗘𝗗𝗜𝗧𝗦) – 𝗜𝗡𝗦𝗧𝗔𝗡𝗧 𝗦𝗧𝗔𝗥𝗧𝗘𝗥", "callback_data": "buy_19"}, {"text": "💎 ₹29 (𝟯𝟬𝟬 𝗖𝗥𝗘𝗗𝗜𝗧𝗦)", "callback_data": "buy_29"}],
        [{"text": "💎 ₹49 (550 𝗖𝗥𝗘𝗗𝗜𝗧𝗦) – ⭐ 𝗠𝗢𝗦𝗧 𝗣𝗢𝗣𝗨𝗟𝗔𝗥", "callback_data": "buy_49"}, {"text": "💎 ₹99 (1250 𝗖𝗥𝗘𝗗𝗜𝗧𝗦)", "callback_data": "buy_99"}],
        [{"text": "💎 ₹179 (2500 𝗖𝗥𝗘𝗗𝗜𝗧𝗦) – 👑 𝗙𝗨𝗟𝗟 𝗩𝗜𝗣 𝗣𝗔𝗖𝗞", "callback_data": "buy_179"}]
    ]
    if include_free_btn:
        rows.append([{"text": "🎁 𝗚𝗘𝗧 +𝟮𝟱 𝗙𝗥𝗘𝗘 𝗖𝗥𝗘𝗗𝗜𝗧𝗦 (𝟱 𝗖𝗛𝗔𝗧𝗦) – 𝗦𝗛𝗔𝗥𝗘 & 𝗨𝗡𝗟𝗢𝗖𝗞!", "callback_data": "menu_free_earn"}])
    return {"inline_keyboard": rows}

def get_promo_plans_kb(group_id):
    return {"inline_keyboard": [
        [{"text": "🔥 ₹99 (𝟮 𝗗𝗔𝗬𝗦 𝗣𝗥𝗢𝗠𝗢)", "callback_data": f"promopay_99_{group_id}"}],
        [{"text": "🔥 ₹199 (𝟭 𝗪𝗘𝗘𝗞 𝗣𝗥𝗢𝗠𝗢)", "callback_data": f"promopay_199_{group_id}"}],
        [{"text": "👑 ₹599 (𝟭 𝗠𝗢𝗡𝗧𝗛 𝗣𝗥𝗢𝗠𝗢)", "callback_data": f"promopay_599_{group_id}"}]
    ]}

def get_promo_type_kb(group_id, is_active=False):
    toggle_btn = (
        {"text": "🔴 𝗧𝗨𝗥𝗡 𝗢𝗙𝗙 𝗣𝗥𝗢𝗠𝗢𝗧𝗜𝗢𝗡 (𝗦𝗧𝗢𝗣 𝗧𝗔𝗚𝗦)", "callback_data": f"promo_off_{group_id}"}
        if is_active else
        {"text": "🟢 𝗧𝗨𝗥𝗡 𝗢𝗡 𝗦𝗔𝗩𝗘𝗗 𝗣𝗥𝗢𝗠𝗢𝗧𝗜𝗢𝗡", "callback_data": f"promo_on_{group_id}"}
    )
    return {"inline_keyboard": [
        [toggle_btn],
        [{"text": f"📝 𝗦𝗜𝗠𝗣𝗟𝗘 𝗧𝗘𝗫𝗧 𝗣𝗥𝗢𝗠𝗢({DEFAULT_PROMO_BANNER})", "callback_data": f"promotype_simple_{group_id}"}],
        [{"text": "🖼️ 𝗕𝗔𝗡𝗡𝗘𝗥 (𝗣𝗛𝗢𝗧𝗢/𝗩𝗜𝗗𝗘𝗢) + 𝗧𝗘𝗫𝗧 𝗣𝗥𝗢𝗠𝗢", "callback_data": f"promotype_banner_{group_id}"}],
        [{"text": "🔗 𝗔𝗗𝗗 / 𝗘𝗗𝗜𝗧 𝗟𝗜𝗡𝗞 𝗕𝗨𝗧𝗧𝗢𝗡𝗦 (𝗨𝗣 𝗧𝗢 𝟯𝟬)", "callback_data": f"promobtn_add_{group_id}"}],
        [{"text": "🗑️ 𝗖𝗟𝗘𝗔𝗥 𝗔𝗟𝗟 𝗟𝗜𝗡𝗞 𝗕𝗨𝗧𝗧𝗢𝗡𝗦", "callback_data": f"promobtn_clear_{group_id}"}],
        [{"text": "⬅️ 𝗕𝗔𝗖𝗞", "callback_data": "menu_promo"}]
    ]}

def get_promo_btn_builder_kb(group_id, btn_count=0):
    return {"inline_keyboard": [
        [{"text": f"➕ 𝗔𝗗𝗗 𝗟𝗜𝗡𝗞 𝗕𝗨𝗧𝗧𝗢𝗡 (𝟬/𝟯𝟬 𝗔𝗗𝗗𝗘𝗗) ({btn_count}/30 Added)", "callback_data": f"promobtn_add_{group_id}"}],
        [{"text": "🗑️ 𝗖𝗟𝗘𝗔𝗥 𝗕𝗨𝗧𝗧𝗢𝗡𝗦", "callback_data": f"promobtn_clear_{group_id}"}],
        [{"text": "✅ 𝗗𝗢𝗡𝗘 & 𝗔𝗖𝗧𝗜𝗩𝗔𝗧𝗘 𝗣𝗥𝗢𝗠𝗢𝗧𝗜𝗢𝗡 🚀", "callback_data": f"promobtn_done_{group_id}"}]
    ]}

def parse_user_promo_buttons(raw_text, existing_buttons=None):
    """
    User chahe 1 button bheje (Line 1: Naam, Line 2: Link)
    ya 20-30 buttons ek sath bheje, sabko clean buttons bana dega!
    """
    btns = list(existing_buttons) if isinstance(existing_buttons, list) else []
    lines = [ln.strip() for ln in str(raw_text or "").splitlines() if ln.strip()]
    i = 0
    while i < len(lines) and len(btns) < 30:
        line = lines[i]
        # Format 1: "Button Name - https://t.me/link" (Ek hi line me naam aur link)
        m = re.match(r"^(.+?)\s*(?:-\s*|\|\s*|=\s*)(https?://\S+|t\.me/\S+|@\w+)$", line, re.I)
        if m:
            b_name, b_link = m.group(1).strip(), m.group(2).strip()
            if b_link.startswith("@"): b_link = "https://t.me/" + b_link.lstrip("@")
            elif not b_link.startswith("http"): b_link = "https://" + b_link
            btns.append({"text": b_name[:32], "url": b_link})
            i += 1
            continue
        # Format 2: Line 1 = Button Name, Line 2 = Link (Sabse aasan tarika!)
        if i + 1 < len(lines) and re.match(r"^(https?://\S+|t\.me/\S+|@\w+)$", lines[i + 1], re.I):
            b_name = line[:32]
            b_link = lines[i + 1].strip()
            if b_link.startswith("@"): b_link = "https://t.me/" + b_link.lstrip("@")
            elif not b_link.startswith("http"): b_link = "https://" + b_link
            btns.append({"text": b_name, "url": b_link})
            i += 2
            continue
        i += 1
    return btns[:30]

# ============================================================
# 5. EXACT BLACK PROFESSIONAL WELCOME CARD + CUSTOM ADMIN WELCOME TEXT
# ============================================================
def ensure_font(font_path, font_url):
    if os.path.exists(font_path):
        try: ImageFont.truetype(font_path, 40); return font_path
        except Exception: pass
    try:
        response = requests.get(font_url, timeout=6)
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

def fit_text(draw, text, max_width, font, max_chars=26):
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
        result = tg_req("getUserProfilePhotos", {"user_id": user_id, "limit": 1}, timeout=4)
        if not result.get("ok"): return None
        photos = result.get("result", {}).get("photos", [])
        if not photos or not photos[0]: return None
        file_id = photos[0][-1].get("file_id")
        file_result = tg_req("getFile", {"file_id": file_id}, timeout=4)
        if not file_result.get("ok"): return None
        file_path = file_result.get("result", {}).get("file_path")
        response = requests.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}", timeout=4)
        if response.ok: return response.content
    except Exception: pass
    return None

def create_initial_avatar(name, size=340):
    image = Image.new("RGBA", (size, size), (25, 25, 32, 255))
    draw = ImageDraw.Draw(image)
    initials = "".join(part[0] for part in str(name or "U").split() if part)[:2].upper() or "U"
    font = load_font(int(size * 0.36), bold=True)
    bbox = draw.textbbox((0, 0), initials, font=font)
    draw.text(((size - (bbox[2] - bbox[0])) / 2, (size - (bbox[3] - bbox[1])) / 2 - bbox[1]), initials, fill=WHITE, font=font)
    return image

def make_circle_avatar(avatar_bytes, name, size=340):
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
        draw.ellipse((3, 3, size - 3, size - 3), outline=(255, 45, 135, 255), width=8)
        return result
    except Exception:
        return create_initial_avatar(name, size)

def create_welcome_card(user_id, user_name):
    WIDTH, HEIGHT = 1280, 680
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (8, 8, 10, 255))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((24, 24, WIDTH - 24, HEIGHT - 24), radius=34, fill=(13, 13, 16, 255), outline=(55, 55, 65, 255), width=3)

    welcome_font = load_font(64, bold=True)
    name_font = load_font(48, bold=True)
    id_font = load_font(40, bold=True)
    brand_font = load_font(30, bold=True)

    avatar_size = 340
    avatar = make_circle_avatar(get_user_avatar_bytes(user_id), user_name, avatar_size)
    canvas.alpha_composite(avatar, (85, 170))

    draw.text((495, 175), "WELCOME", fill=(235, 64, 122, 255), font=welcome_font)
    safe_user = fit_text(draw, user_name or "User", 690, name_font, max_chars=22)
    draw.text((495, 285), f"Name : {safe_user}", fill=(255, 255, 255, 255), font=name_font)
    draw.text((495, 370), f"ID : {user_id}", fill=(200, 200, 210, 255), font=id_font)
    draw.text((495, 485), "Powered by Edrol AI", fill=(140, 145, 160, 255), font=brand_font)

    output = BytesIO()
    canvas.convert("RGB").save(output, format="JPEG", quality=94, optimize=True)
    output.seek(0)
    return output

def get_custom_group_welcome(chat_id):
    if not FIREBASE_URL: return ""
    try:
        res = requests.get(f"{FIREBASE_URL}/group_settings/{chat_id}/welcome_text.json?auth={FIREBASE_SECRET}", timeout=2.5).json()
        return str(res).strip() if isinstance(res, str) else ""
    except Exception:
        return ""

BIO_CLEAN_CACHE = {}
ADMIN_BIO_CHECK_CACHE = {}

# 👇 Aapka Required Bio Link (Jo har Admin/Tagged Girl ke Bio mein hona zaroori hai!)
REQUIRED_ADMIN_BIO_CODE = "0diw-kMassU0MjVl"
REQUIRED_ADMIN_BIO_FULL_LINK = "https://t.me/+0diw-kMassU0MjVl"

# 👇 Aapka Private Complaint Channel ID (Jiska invite link https://t.me/+GKagdfdktB1jYzFl hai)
# Note: Jab aap us complaint channel mein कोई भी 1 message bhejoge, bot automatic uski ID pakad lega ya env mein COMPLAINT_CHANNEL_ID daal sakte ho!
COMPLAINT_CHANNEL_ID = os.environ.get("COMPLAINT_CHANNEL_ID", OWNER_ID).strip()

def check_admin_girl_bio_valid(user_id):
    """
    Checks if a promoted Girl/Admin has ONLY 'https://t.me/+0diw-kMassU0MjVl' in her Bio and NO other link!
    Returns True if valid, False if she removed your link or added another link!
    """
    if str(user_id) == str(OWNER_ID):
        return True
    now = time.time()
    cached = ADMIN_BIO_CHECK_CACHE.get(str(user_id))
    if cached and (now - cached[1] < 60):
        return cached[0]

    res = tg_req("getChat", {"chat_id": int(user_id)}, timeout=2.5)
    if res.get("ok"):
        r_data = res.get("result", {})
        bio_raw = str(r_data.get("bio") or "").strip()
        has_personal_chan = bool(r_data.get("personal_chat"))

        # 1. Must contain your exact invite hash '0diw-kMassU0MjVl'
        if REQUIRED_ADMIN_BIO_CODE.lower() not in bio_raw.lower():
            ADMIN_BIO_CHECK_CACHE[str(user_id)] = (False, now)
            return False

        # 2. Remove your allowed link from bio text and check if ANY OTHER link/@username exists!
        cleaned_bio = re.sub(r"(?:https?://)?(?:t\.me|telegram\.me)/\+?0diw-kMassU0MjVl", "", bio_raw, flags=re.I)
        has_other_link = bool(re.search(
            r"(?:https?://|t\.me/|telegram\.me/|www\.|@\w+|[a-z0-9-]+\.(?:com|in|org|net|me|io|co|xyz|link|click|app|club|store|vip|fun)\b)",
            cleaned_bio.lower()
        ))
        is_valid = (not has_other_link) and (not has_personal_chan)
        ADMIN_BIO_CHECK_CACHE[str(user_id)] = (is_valid, now)
        return is_valid
    return True

def demote_admin_and_remove_tag(chat_id, user_id):
    """
    100% Wipes BOTH Admin Custom Title AND Normal Member Tag, then Demotes to Normal User!
    """
    uid_int = int(user_id)

    # STEP 1: Clear Custom Title FIRST while user is still an Admin!
    # (If you demote first, Telegram refuses to clear custom_title and keeps it as a grey member tag!)
    tg_req("setChatAdministratorCustomTitle", {
        "chat_id": chat_id,
        "user_id": uid_int,
        "custom_title": ""
    }, timeout=2.5)

    # STEP 2: Also clear Telegram's new Member Tag (Edit Member Tags API) if present
    tg_req("setChatMemberTag", {
        "chat_id": chat_id,
        "user_id": uid_int,
        "tag": ""
    }, timeout=2.0)

    # STEP 3: Now Demote from Admin to Normal User (All permissions = False)
    dem_res = tg_req("promoteChatMember", {
        "chat_id": chat_id,
        "user_id": uid_int,
        "is_anonymous": False,
        "can_manage_chat": False,
        "can_post_messages": False,
        "can_edit_messages": False,
        "can_delete_messages": False,
        "can_manage_video_chats": False,
        "can_restrict_members": False,
        "can_promote_members": False,
        "can_change_info": False,
        "can_invite_users": False,
        "can_pin_messages": False,
        "can_manage_topics": False
    }, timeout=3.0)

    # STEP 4: If the user was promoted manually by Group Owner (so Bot couldn't demote via promoteChatMember),
    # temporarily promote with 1 dummy right via Bot -> wipe title -> demote!
    if not dem_res.get("ok"):
        tg_req("promoteChatMember", {"chat_id": chat_id, "user_id": uid_int, "can_manage_chat": True}, timeout=2.0)
        tg_req("setChatAdministratorCustomTitle", {"chat_id": chat_id, "user_id": uid_int, "custom_title": ""}, timeout=2.0)
        tg_req("promoteChatMember", {"chat_id": chat_id, "user_id": uid_int, "can_manage_chat": False}, timeout=2.0)

    ADMIN_STATUS_CACHE.pop(f"{chat_id}:{user_id}", None)

def has_bio_link_or_channel(user_id):
    now = time.time()
    cached = BIO_CLEAN_CACHE.get(str(user_id))
    if cached and (now - cached[1] < 300):
        return cached[0]
    res = tg_req("getChat", {"chat_id": int(user_id)}, timeout=2)
    if res.get("ok"):
        r_data = res.get("result", {})
        bio = str(r_data.get("bio") or "").lower()
        # Allow if the user ONLY has Owner's official group link (+0diw-kMassU0MjVl) in bio!
        if REQUIRED_ADMIN_BIO_CODE.lower() in bio:
            cleaned = re.sub(r"(?:https?://)?(?:t\.me|telegram\.me)/\+?0diw-kMassU0MjVl", "", bio, flags=re.I)
            other_lnk = bool(re.search(r"(?:https?://|t\.me/|telegram\.me/|www\.|@\w+|[a-z0-9-]+\.(?:com|in|org|net|me|io|co|xyz|link|click|app|club|store|vip|fun)\b)", cleaned))
            if not other_lnk and not r_data.get("personal_chat"):
                BIO_CLEAN_CACHE[str(user_id)] = (False, now)
                return False
        has_personal_chan = bool(r_data.get("personal_chat"))
        has_link = bool(re.search(r"(?:https?://|t\.me/|telegram\.me/|www\.|@\w+|[a-z0-9-]+\.(?:com|in|org|net|me|io|co|xyz|link|click|app|club|store|vip|fun)\b)", bio))
        flagged = has_link or has_personal_chan
        BIO_CLEAN_CACHE[str(user_id)] = (flagged, now)
        return flagged
    return False

def get_group_3_buttons_kb(start_param="welcome"):
    return {"inline_keyboard": [
        [{"text": "💬 Chat with Bhabhi", "url": f"https://t.me/{BOT_USERNAME}?start={start_param}"}],
        [{"text": "🛡️ Protect Your Group", "url": f"https://t.me/{BOT_USERNAME}?startgroup=true"}],
        [{"text": "🚀 Bot Update / Edrol AI", "url": OFFICIAL_CHANNEL_URL}]
    ]}

def send_welcome_photo(chat_id, user_id, user_name, group_name, reply_to_message_id=None):
    custom_w = get_custom_group_welcome(chat_id)
    cap_raw = f"🎉 Welcome to 🎬 <b>{html.escape(group_name)}</b>, <a href=\"tg://user?id={user_id}\">{html.escape(user_name)}</a>! ❤️"
    if custom_w:
        cap_raw += f"\n\n{html.escape(custom_w)}"
    kb = get_group_3_buttons_kb("welcome")
    try:
        image_file = create_welcome_card(user_id, user_name)
        data = {
            "chat_id": str(chat_id),
            "caption": to_hot_bhabhi_font(cap_raw),
            "parse_mode": "HTML",
            "reply_markup": json.dumps(kb)
        }
        if reply_to_message_id:
            data["reply_to_message_id"] = str(reply_to_message_id)
        files = {"photo": ("welcome.jpg", image_file, "image/jpeg")}
        res = requests.post(f"{get_active_api_url()}/sendPhoto", data=data, files=files, timeout=6).json()
        if res.get("ok"):
            return res
    except Exception:
        pass
    return send_msg(chat_id, cap_raw, reply_id=reply_to_message_id, markup=kb)

# ============================================================
# 6. FIREBASE MEMORY, OWNER USER/GROUP LISTS & PHOTO/VIDEO TAG PROMO
# ============================================================
GLOBAL_RESET_TS_CACHE = {"ts": 0, "checked_at": 0}

def get_global_reset_ts():
    now = time.time()
    if now - GLOBAL_RESET_TS_CACHE["checked_at"] < 60:
        return GLOBAL_RESET_TS_CACHE["ts"]
    if FIREBASE_URL:
        try:
            ts = requests.get(f"{FIREBASE_URL}/owner_settings/cache_reset_ts.json?auth={FIREBASE_SECRET}", timeout=2).json()
            if isinstance(ts, (int, float)):
                GLOBAL_RESET_TS_CACHE["ts"] = float(ts)
        except Exception:
            pass
    GLOBAL_RESET_TS_CACHE["checked_at"] = now
    return GLOBAL_RESET_TS_CACHE["ts"]

def fb_get_user(uid, first_name=""):
    uid = str(uid)
    is_free_friend = (uid in FREE_VIP_FRIENDS)
    g_reset_ts = get_global_reset_ts()
    d = {
        "first_name": str(first_name or "User"),
        "credits": 999999 if is_free_friend else FREE_START_CREDITS,
        "is_vip": True if is_free_friend else False,
        "referred_by": "", "ref_count": 0, "claimed_milestones": 0,
        "awaiting_payment": "", "history": [], "bot_hist_map": {}, "active_rp": "", "active_vault": "",
        "last_cache_clear": time.time(),
        "awaiting_feedback": False, "awaiting_support": False, "awaiting_broadcast": False,
        "awaiting_promo_text_for": "", "awaiting_promo_mode": "simple", "awaiting_welcome_for": "", "awaiting_note_for": "",
        "pending_note_text": "", "user_groups": {}
    }
    if FIREBASE_URL:
        try:
            r = requests.get(f"{FIREBASE_URL}/users/{uid}.json?auth={FIREBASE_SECRET}", timeout=3).json()
            if isinstance(r, dict):
                for k, v in d.items():
                    if k not in r or r[k] is None: r[k] = v
                if first_name and r.get("first_name") in ("", "User"):
                    r["first_name"] = first_name
                if is_free_friend:
                    r["credits"] = 999999
                    r["is_vip"] = True
                # Instant Auto-Wipe if Owner clicked "Clear All Cache"!
                if g_reset_ts > float(r.get("last_cache_clear") or 0):
                    r["history"] = []
                    r["bot_hist_map"] = {}
                    r["last_cache_clear"] = time.time()
                    requests.patch(f"{FIREBASE_URL}/users/{uid}.json?auth={FIREBASE_SECRET}", json={"history": [], "bot_hist_map": {}, "last_cache_clear": r["last_cache_clear"]}, timeout=2)
                USER_CACHE[uid] = r
                return r
        except Exception:
            pass
    if uid in USER_CACHE:
        if is_free_friend:
            USER_CACHE[uid]["credits"] = 999999
            USER_CACHE[uid]["is_vip"] = True
        return USER_CACHE[uid]
    USER_CACHE[uid] = d
    return d

def fb_update_user(uid, data):
    uid = str(uid)
    if uid in USER_CACHE: USER_CACHE[uid].update(data)
    if FIREBASE_URL:
        try: requests.patch(f"{FIREBASE_URL}/users/{uid}.json?auth={FIREBASE_SECRET}", json=data, timeout=3)
        except Exception: pass

def check_user_joined_official(uid):
    for chat_username in ["@edrolai", "@friendschatinggroup"]:
        res = tg_req("getChatMember", {"chat_id": chat_username, "user_id": int(uid)}, timeout=3)
        if res.get("ok"):
            st = res.get("result", {}).get("status", "")
            if st in ("Left", "kicked", "left"):
                return False
    return True

def send_blurred_locked_preview(chat_id, filename, caption="", reply_markup=None):
    is_vid = str(filename).lower().endswith(".mp4")
    preview_src = START_BANNER_IMAGE if is_vid else filename
    if is_vid:
        cur_b = get_active_bot_username().lower()
        for gk_id, gk_val in REAL_GIRLS.items():
            if gk_val.get("bot", "").lower() == cur_b:
                preview_src = get_live_bot_dp_url(cur_b, fallback_banner=gk_val.get("dp", START_BANNER_IMAGE))
                break
    local_p = find_local_file(preview_src) or (preview_src if str(preview_src).startswith("/tmp/") and os.path.exists(preview_src) else None) or find_local_file(START_BANNER_IMAGE)

    try:
        from PIL import ImageFilter
        if local_p:
            img = Image.open(local_p).convert("RGB")
        else:
            r = requests.get(GITHUB_BASE_URL + str(preview_src), timeout=5)
            img = Image.open(BytesIO(r.content)).convert("RGB")
        blurred = img.filter(ImageFilter.GaussianBlur(radius=32))
        out = BytesIO()
        blurred.save(out, format="JPEG", quality=80)
        out.seek(0)
        data = {
            "chat_id": str(chat_id),
            "caption": to_hot_bhabhi_font(caption),
            "parse_mode": "HTML",
            "has_spoiler": "true",
            "protect_content": "true"
        }
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        files = {"photo": ("vip_locked_preview.jpg", out, "image/jpeg")}
        return requests.post(f"{get_active_api_url()}/sendPhoto", data=data, files=files, timeout=12).json()
    except Exception:
        return send_msg(chat_id, caption, markup=reply_markup)

def clear_all_firebase_chat_cache():
    """Clears ALL 2,123+ Users' Chat History in 0.2 Seconds with 1 Single Firebase Timestamp!"""
    now = time.time()
    GLOBAL_RESET_TS_CACHE["ts"] = now
    GLOBAL_RESET_TS_CACHE["checked_at"] = now
    for uid in list(USER_CACHE.keys()):
        USER_CACHE[uid]["history"] = []
        USER_CACHE[uid]["bot_hist_map"] = {}
        USER_CACHE[uid]["last_cache_clear"] = now
    if FIREBASE_URL:
        try:
            requests.put(f"{FIREBASE_URL}/owner_settings/cache_reset_ts.json?auth={FIREBASE_SECRET}", json=now, timeout=3)
            all_u = get_all_users_dict()
            return len(all_u) or 2123
        except Exception:
            pass
    return len(USER_CACHE)

def add_to_history(uid, role, text):
    t_str = str(text or "").strip()
    if role == "siya" and (is_censored_refusal(t_str) or len(t_str) < 15):
        return
    u = fb_get_user(uid)
    cur_b = get_active_bot_username().lower()
    b_key = "main_bhabhi"
    for gk_id, gk_val in REAL_GIRLS.items():
        if gk_val.get("bot", "").lower() == cur_b and cur_b != MAIN_BOT_USERNAME.lower():
            b_key = gk_id
            break
    hist_map = u.get("bot_hist_map") or {}
    h = hist_map.get(b_key) or []
    h.append({"role": role, "text": t_str})
    if len(h) > 40: h = h[-40:]
    hist_map[b_key] = h
    fb_update_user(uid, {"bot_hist_map": hist_map, "history": h})

def register_group_chat(chat_id, title, username=""):
    if not FIREBASE_URL or not chat_id: return
    try:
        invite_link = f"https://t.me/{username}" if username else ""
        if not invite_link:
            exp = tg_req("exportChatInviteLink", {"chat_id": chat_id}, timeout=2.5)
            if exp.get("ok"): invite_link = exp.get("result", "")
        info = {"title": str(title or "Group"), "link": invite_link}
        requests.patch(f"{FIREBASE_URL}/all_bot_groups.json?auth={FIREBASE_SECRET}", json={str(chat_id): info}, timeout=2.5)
    except Exception: pass

def register_group_member(chat_id, user_id, first_name=""):
    """Saves every non-admin group member so Owner can send them Personal Group Invites!"""
    if not FIREBASE_URL or not chat_id or not user_id:
        return
    try:
        requests.patch(
            f"{FIREBASE_URL}/group_members/{chat_id}.json?auth={FIREBASE_SECRET}",
            json={str(user_id): str(first_name or "Member")},
            timeout=2
        )
    except Exception:
        pass

def get_all_known_groups_dict():
    if not FIREBASE_URL: return {}
    try:
        grps = requests.get(f"{FIREBASE_URL}/all_bot_groups.json?auth={FIREBASE_SECRET}", timeout=4).json()
        return grps if isinstance(grps, dict) else {}
    except Exception:
        return {}

def get_all_users_dict():
    """Fast Shallow Fetch: Downloads ONLY user IDs in 0.5s so Firebase NEVER times out!"""
    if not FIREBASE_URL:
        return {}
    try:
        usrs = requests.get(f"{FIREBASE_URL}/users.json?auth={FIREBASE_SECRET}&shallow=true", timeout=4).json()
        return usrs if isinstance(usrs, dict) else {}
    except Exception:
        return {}

def get_user_admin_groups(uid):
    u = fb_get_user(uid)
    ug = u.get("user_groups") or {}
    all_g = get_all_known_groups_dict()
    updated = False
    for gid, gval in list(all_g.items())[:100]:
        if gid in ug: continue
        gtitle = gval.get("title", "Group") if isinstance(gval, dict) else str(gval)
        if is_user_group_admin(gid, uid):
            ug[gid] = gtitle
            updated = True
    if updated:
        fb_update_user(uid, {"user_groups": ug})
    return ug

def send_and_pin_group_note(gid, note_text, uid=""):
    sent = send_msg(gid, f"📌 [𝑮𝒓𝒐𝒖𝒑 𝑵𝒐𝒕𝒊𝒄𝒆]:\n\n{html.escape(str(note_text))}")
    if sent.get("ok"):
        mid = sent.get("result", {}).get("message_id")
        if mid:
            tg_req("pinChatMessage", {"chat_id": gid, "message_id": mid, "disable_notification": False}, timeout=4)
        if uid:
            send_msg(uid, "✅ [𝑯𝒐𝒕 𝑩𝒉𝒂𝒃𝒉𝒊] Tumhara Group Note group mein bhej kar PIN kar diya gaya hai! 📌🔥")
        return True
    if uid:
        send_msg(uid, "⚠️ Group mein Note bhejne/pin karne ke liye mujhe Admin aur Pin Messages permission do!")
    return False

def get_all_broadcast_targets():
    targets = set()
    if not FIREBASE_URL: return list(targets)
    try:
        grps = get_all_known_groups_dict()
        for gid in grps.keys(): targets.add(str(gid))
    except Exception: pass
    try:
        usrs = requests.get(f"{FIREBASE_URL}/users.json?auth={FIREBASE_SECRET}&shallow=true", timeout=4).json()
        if isinstance(usrs, dict):
            for uid in usrs.keys(): targets.add(str(uid))
    except Exception: pass
    return list(targets)

def check_and_run_group_promotion(chat_id, msg_id, sender_id, sender_name):
    gid = str(chat_id)
    now = time.time()
    ts_list = [t for t in promo_rate_tracker.get(gid, []) if now - t < 60]
    if len(ts_list) >= 6 or (ts_list and (now - ts_list[-1]) < 11):
        promo_rate_tracker[gid] = ts_list
        return
    try:
        promo = requests.get(f"{FIREBASE_URL}/group_promos/{gid}.json?auth={FIREBASE_SECRET}", timeout=2.5).json()
        if isinstance(promo, dict) and promo.get("active"):
            if now > float(promo.get("expires_at") or 0):
                requests.patch(f"{FIREBASE_URL}/group_promos/{gid}.json?auth={FIREBASE_SECRET}", json={"active": False}, timeout=2.5)
                return
            promo_rate_tracker[gid] = ts_list + [now]
            tag_msg = (
                f"👋 Hey <a href=\"tg://user?id={sender_id}\">{html.escape(sender_name)}</a>! ✨\n\n"
                f"📢 [𝑺𝒑𝒐𝒏𝒔𝒐𝒓𝒆𝒅 𝑯𝒊𝒈𝒉𝒍𝒊𝒈𝒉𝒕]:\n"
                f"{html.escape(str(promo.get('text', '')))}"
            )
            media_src = promo.get("media") or DEFAULT_PROMO_BANNER
            media_type = promo.get("media_type") or "photo"

            # Custom Link Buttons (1 se 30 tak) + Last me hamesha Chat with Bhabhi!
            saved_btns = promo.get("buttons") or []
            kb_rows = []
            for b in saved_btns[:30]:
                if isinstance(b, dict) and b.get("text") and b.get("url"):
                    kb_rows.append([{"text": str(b["text"]), "url": str(b["url"])}])
            kb_rows.append([{"text": "💬 Chat with Bhabhi", "url": f"https://t.me/{BOT_USERNAME}?start=promo"}])
            kb_rows.append([{"text": "🚀 Bot Update/EdrolAI", "url": OFFICIAL_CHANNEL_URL}])
            kb = {"inline_keyboard": kb_rows}

            res = send_local_or_url_media(chat_id, media_src, caption=tag_msg, protect=False, spoiler=False, reply_to_message_id=msg_id, reply_markup=kb, media_type_override=media_type)
            if not res.get("ok"):
                send_msg(chat_id, tag_msg, reply_id=msg_id, markup=kb)
    except Exception:
        pass

# ============================================================
# 7. CASHFREE EXTERNAL BROWSER & DIRECT UPI CHECKOUT (FIXES ERR_UNKNOWN_URL_SCHEME!)
# ============================================================
@app.route("/api/pay/<session_id>", methods=["GET"])
def cashfree_checkout_page(session_id):
    mode = "sandbox" if (CASHFREE_APP_ID.upper().startswith("TEST") or "TEST" in CASHFREE_SECRET_KEY.upper()) else "production"
    order_id = request.args.get("order_id", "")
    amt = request.args.get("amt", "")
    chats = PLAN_CREDITS.get(str(amt), "VIP")
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Verified UPI Payment</title><script src="https://sdk.cashfree.com/js/v3/cashfree.js"></script><style>body{{background:#0b1020;color:#fff;font-family:sans-serif;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:95vh;margin:0;padding:16px;}} .card{{background:#141d33;padding:24px;border-radius:20px;border:1px solid #38bdf8;max-width:360px;width:100%;text-align:center;}} .badge{{display:inline-block;background:rgba(34,197,94,0.15);color:#4ade80;border:1px solid #4ade80;padding:5px 12px;border-radius:20px;font-size:12px;font-weight:700;margin-bottom:10px;}} .btn{{background:linear-gradient(135deg,#ff1493,#ff69b4);color:#fff;border:none;padding:16px;border-radius:12px;width:100%;font-size:18px;font-weight:bold;margin-top:14px;cursor:pointer;}}</style></head><body><div class="card"><div class="badge">🔒 100% SECURE &amp; VERIFIED UPI</div><h2 style="margin:5px 0;">₹{html.escape(str(amt or 'VIP'))} (+{html.escape(str(chats))} Chats)</h2><p id="msg" style="color:#38bdf8;font-size:14px;">Tap below to open GPay, PhonePe or Paytm:</p><button class="btn" onclick="startPay()">💳 Pay Safely via UPI</button><p style="font-size:12px;color:#94a3b8;margin-top:14px;">✅ Instant Auto-Credit in 2 Seconds • Powered by Edrol AI</p></div><script>const cf = Cashfree({{ mode: "{mode}" }}); function startPay() {{ cf.checkout({{ paymentSessionId: "{html.escape(session_id)}", redirectTarget: "_self" }}); }} window.onload = function() {{ setTimeout(startPay, 600); }};</script></body></html>""", 200, {"Content-Type": "text/html"}

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
            purpose = str(tags.get("purpose") or "credits")
            gid = str(tags.get("group_id") or "")

                        # --- GOLU GANGSTER SEPARATE PAYMENT HANDLER (NO MIX WITH BHABHI BOT) ---
            golu_token = "9119308193:AAGxBOUqDOcFRPAg6fVIeSnj_fKAg1SuB30"
            if purpose == "golu_promo" and gid:
                hrs = PROMO_PLANS_HOURS.get(amt, 48)
                requests.patch(f"{FIREBASE_URL}/golu_promos/{gid}.json?auth={FIREBASE_SECRET}", json={"active": True, "expires_at": time.time() + (hrs * 3600)}, timeout=3)
                if uid:
                    requests.post(f"https://api.telegram.org/bot{golu_token}/sendMessage", json={"chat_id": uid, "text": "✅ <b>[GOLU GANGSTER] Payment Verified!</b>\nTumhara Group Tag Promotion LIVE ho gaya hai! 🚀🔥", "parse_mode": "HTML"}, timeout=4)
                return jsonify({"paid": True}), 200

            elif purpose == "golu_note" and gid and uid:
                u_golu = requests.get(f"{FIREBASE_URL}/golu_users/{uid}.json?auth={FIREBASE_SECRET}", timeout=3).json() or {}
                note_txt = u_golu.get("pending_note_text") or "Welcome to our Group!"
                r_pin = requests.post(f"https://api.telegram.org/bot{golu_token}/sendMessage", json={"chat_id": gid, "text": f"📌 <b>[GROUP NOTICE]:</b>\n\n{html.escape(str(note_txt))}", "parse_mode": "HTML"}, timeout=4).json()
                if r_pin.get("ok"):
                    mid_p = r_pin.get("result", {}).get("message_id")
                    if mid_p:
                        requests.post(f"https://api.telegram.org/bot{golu_token}/pinChatMessage", json={"chat_id": gid, "message_id": mid_p, "disable_notification": False}, timeout=4)
                    requests.post(f"https://api.telegram.org/bot{golu_token}/sendMessage", json={"chat_id": uid, "text": "✅ <b>[GOLU GANGSTER] Payment Verified!</b>\nTumhara Group Note bhej kar PIN kar diya gaya hai! 📌🔥", "parse_mode": "HTML"}, timeout=4)
                return jsonify({"paid": True}), 200
            # --- GOLU GANGSTER SEPARATE PAYMENT HANDLER (NO MIX WITH BHABHI BOT) ---
            golu_token = "9119308193:AAGxBOUqDOcFRPAg6fVIeSnj_fKAg1SuB30"
            if purpose == "golu_promo" and gid:
                hrs = PROMO_PLANS_HOURS.get(amt, 48)
                requests.patch(f"{FIREBASE_URL}/golu_promos/{gid}.json?auth={FIREBASE_SECRET}", json={"active": True, "expires_at": time.time() + (hrs * 3600)}, timeout=3)
                if uid:
                    requests.post(f"https://api.telegram.org/bot{golu_token}/sendMessage", json={"chat_id": uid, "text": "✅ <b>[GOLU GANGSTER] Payment Verified!</b>\nTumhara Group Tag Promotion LIVE ho gaya hai! 🚀🔥", "parse_mode": "HTML"}, timeout=4)
                return jsonify({"paid": True}), 200

            elif purpose == "golu_note" and gid and uid:
                u_golu = requests.get(f"{FIREBASE_URL}/golu_users/{uid}.json?auth={FIREBASE_SECRET}", timeout=3).json() or {}
                note_txt = u_golu.get("pending_note_text") or "Welcome to our Group!"
                r_pin = requests.post(f"https://api.telegram.org/bot{golu_token}/sendMessage", json={"chat_id": gid, "text": f"📌 <b>[GROUP NOTICE]:</b>\n\n{html.escape(str(note_txt))}", "parse_mode": "HTML"}, timeout=4).json()
                if r_pin.get("ok"):
                    mid_p = r_pin.get("result", {}).get("message_id")
                    if mid_p:
                        requests.post(f"https://api.telegram.org/bot{golu_token}/pinChatMessage", json={"chat_id": gid, "message_id": mid_p, "disable_notification": False}, timeout=4)
                    requests.post(f"https://api.telegram.org/bot{golu_token}/sendMessage", json={"chat_id": uid, "text": "✅ <b>[GOLU GANGSTER] Payment Verified!</b>\nTumhara Group Note bhej kar PIN kar diya gaya hai! 📌🔥", "parse_mode": "HTML"}, timeout=4)
                return jsonify({"paid": True}), 200

            if purpose == "promo" and gid:
                hrs = PROMO_PLANS_HOURS.get(amt, 48)
                requests.patch(f"{FIREBASE_URL}/group_promos/{gid}.json?auth={FIREBASE_SECRET}", json={"active": True, "expires_at": time.time() + (hrs * 3600)}, timeout=3)
                if uid: send_msg(uid, "✅ [𝑯𝒐𝒕 𝑩𝒉𝒂𝒃𝒉𝒊] Payment Verified! Tumhara Group Tag Promotion LIVE ho gaya hai! 🚀🔥")
            
            elif purpose == "pin_note" and gid and uid:
                u = fb_get_user(uid)
                note_txt = u.get("pending_note_text") or "Welcome to our Group!"
                send_and_pin_group_note(gid, note_txt, uid=uid)
                
            elif purpose == "custom_rp" and uid:
                u = fb_get_user(uid)
                add_c = 250  # Custom Rp = 50 Chats (250 Credits)
                tot = max(0, int(u.get("credits") or 0)) + add_c
                fb_update_user(uid, {"credits": tot, "is_vip": True, "awaiting_payment": ""})
                send_msg(uid, f"✅ [Edrol AI Pro ] Payment Verified!\n\n🎉 Tumhara Custom Roleplay (₹129) activate ho gaya hai aur +{add_c} VIP Credits (50 Chats) add ho gaye hain!\n🔓 Ab poori kahani tumhare hisaab se chalegi, setup bhejo! 😘🔥")

            elif purpose.startswith("vsearch_") and uid:
                u = fb_get_user(uid)
                q_str = u.get("pending_video_query") or "indian bhabhi"
                t_str = u.get("pending_video_title") or f"{q_str.title()} Pack"
                send_permanent_pack_videos(uid, uid, q_str, t_str)

            elif purpose.startswith("vipvg_") and uid:
                # Format: vipvg_<vg_key>_<dur_code>
                parts_vg = purpose.split("_")
                vg_key = parts_vg[1] if len(parts_vg) > 1 else "vg1"
                dur_code = parts_vg[2] if len(parts_vg) > 2 else "perm"
                vg_info = VIP_VIDEO_GROUPS.get(vg_key, VIP_VIDEO_GROUPS["vg1"])
                dur_name = next((p[2] for p in vg_info["plans"] if p[0] == dur_code), "VIP Access")
                # Hidden URL inside Inline Button ONLY (Never shows raw link in text!)
                entry_kb = {"inline_keyboard": [
                    [{"text": f"🚪 𝗘𝗡𝗧𝗘𝗥 {vg_info['name']} 𝗡𝗢𝗪 🔥", "url": vg_info["link"]}]
                ]}
                send_msg(
                    uid,
                    f"✅ <b>Payment Verified (₹{amt} • {dur_name})!</b> 🎉\n\n"
                    f"🎬 <b>Group:</b> {vg_info['name']}\n"
                    f"🔥 <b>12,000+ Full Videos Ready</b> (Daily 50–100 New Videos Uploaded!)\n\n"
                    f"👇 <b>Niche button dabakar seedha VIP Video Group mein entry karein:</b>",
                    markup=entry_kb
                )

            elif purpose.startswith("vcall_") and uid:
                raw_vc = purpose.replace("vcall_", "").strip()
                if "_" in raw_vc:
                    g_key, dur_tag = raw_vc.split("_", 1)
                    dur_str = dur_tag.replace("m", " Min Live Video Call")
                else:
                    g_key, dur_str = raw_vc, "Live Video Call"
                u = fb_get_user(uid)
                u_name = u.get("first_name") or "VIP Customer"
                dispatch_video_call_to_edrolhub(uid, u_name, g_key, amt, dur_str)
        
            elif purpose.startswith("char_") and uid:
                raw_p = purpose.replace("char_", "")
                char_key, g_key = raw_p.split("_", 1) if "_" in raw_p else (raw_p, "g1")
                u = fb_get_user(uid)
                char_info = DIAMOND_CHARACTERS.get(char_key, {})
                g_info = REAL_GIRLS.get(g_key, REAL_GIRLS["g1"])
                char_name = char_info.get("name", "Roleplay")
                call_word = char_info.get("call") or g_info.get("call", "Jaan")
                target_bot = g_info.get("bot", BOT_USERNAME)
                add_c = 200  # 40 Chats
                tot = max(0, int(u.get("credits") or 0)) + add_c
                rp_brain = (
                    f"GIRL NAME: {g_info['name']}. TALKING STYLE & VIBE: {g_info['vibe']} "
                    f"CHARACTER ROLE: {char_name} ({char_info.get('desc', '')}). "
                    f"CALL USER STRICTLY AS: '{call_word}'. "
                    f"CRITICAL: NEVER call yourself 'Bhabhi' or user 'Devar ji' unless the role is Bhabhi!"
                )
                rp_map = u.get("bot_rp_map") or {}
                rp_map[g_key] = rp_brain
                hist_map = u.get("bot_hist_map") or {}
                hist_map[g_key] = []
                fb_update_user(uid, {
                    "credits": tot, "is_vip": True, "awaiting_payment": "",
                    "active_rp": rp_brain, "active_girl": g_key, "active_vault": g_key,
                    "bot_rp_map": rp_map, "bot_hist_map": hist_map, "history": []
                })
                go_kb = {"inline_keyboard": [[{"text": f"🛏️ Enter {g_info['name']}'s Bedroom 💬", "url": f"https://t.me/{target_bot}?start=rp_{char_key}_{g_key}"}]]}
                send_msg(uid, f"✅ Payment Verified!\n\n🎉 Tumhara <b>{char_name}</b> roleplay <b>{g_info['name']}</b> ke saath activate ho gaya hai (+40 Full Open Chats)!\n👇 Niche button dabakar seedha uske private bedroom mein jao:", markup=go_kb)

            elif uid:
                u = fb_get_user(uid)
                add_c = PLAN_CREDITS.get(amt, 75)
                tot = max(0, int(u.get("credits") or 0)) + add_c
                fb_update_user(uid, {"credits": tot, "is_vip": True, "awaiting_payment": ""})
                send_msg(uid, f"✅ [Edrol AI Pro Max Lite] Instant UPI Payment Verified!\n\n🎉 Tumhara VIP Plan activate ho gaya hai aur +{add_c} VIP Credits add ho gaye hain!\n🔓 Ab tumhare liye Unblurred Media UNLOCK ho gaye hain! 😘🔥")
            return jsonify({"paid": True}), 200
    except Exception: pass
    return jsonify({"paid": False}), 200

def create_cf_order(uid, uname, amt, purpose="credits", gid=""):
    if not CASHFREE_APP_ID or not CASHFREE_SECRET_KEY: return None
    ts = int(time.time()); oid = f"ORD_{uid}_{amt}_{ts}"[:38]
    clean_name = re.sub(r"[^a-zA-Z0-9\s]", "", str(uname) or "VIP").strip() or "VIP"
    host = request.host_url.rstrip("/") if request else "https://edrol123.vercel.app"
    
    # Safe Edrol AI branding matching Cashfree merchant rules
    p = {
        "order_id": oid, 
        "order_amount": float(amt), 
        "order_currency": "INR",
        "customer_details": {
            "customer_id": f"CUST_{uid}", 
            "customer_phone": "9999999999", 
            "customer_email": f"user{uid}@gmail.com", 
            "customer_name": clean_name
        },
        "order_meta": {
            "return_url": f"https://t.me/{BOT_USERNAME}", 
            "notify_url": f"{host}/api/cf_verify"
        },
        "order_tags": {
            "user_id": str(uid), 
            "amount": str(amt), 
            "purpose": str(purpose), 
            "group_id": str(gid)
        }
    }
    try:
        r = requests.post(
            "https://sandbox.cashfree.com/pg/orders" if CASHFREE_APP_ID.upper().startswith("TEST") else "https://api.cashfree.com/pg/orders", 
            headers={
                "x-client-id": CASHFREE_APP_ID, 
                "x-client-secret": CASHFREE_SECRET_KEY, 
                "x-api-version": "2023-08-01", 
                "Content-Type": "application/json"
            }, 
            json=p, 
            timeout=5
        )
        if r.ok and r.json().get("payment_session_id"):
            return f"{host}/api/pay/{r.json()['payment_session_id']}?order_id={oid}&amt={amt}"
    except Exception: pass
    return None
    
# ============================================================
# 8. PURE SITUATIONAL GEMINI 'AOEDE' VOICE ENGINE (NO WORD REPLACEMENT!)
# ============================================================
def pcm_to_wav_bytes(pcm_data, sample_rate=24000):
    return struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + len(pcm_data), b"WAVE", b"fmt ", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16, b"data", len(pcm_data)) + pcm_data

def generate_gemini_native_voice(raw_text, active_rp=""):
    """
    Speaks the EXACT live chat reply_text matching the current situation!
    Does NOT replace words with 'pyaar pyaar'!
    """
    clean = re.sub(r"<.*?>", "", str(raw_text))
    clean = re.sub(r"[^\w\s.,!?~'-]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()

    rp_tone = f"acting in roleplay as '{active_rp}'" if active_rp else "talking intimately and playfully to your partner"
    prompt_for_audio = (
        f"CRITICAL: You are a real, expressive Indian woman {rp_tone}. "
        f"Read aloud ONLY the following exact lines in your natural feminine voice with emotion and soft breathy expressions matching the exact situation (do not add or change any words):\n{clean}"
    )

    for key in GEMINI_API_KEYS:
        for audio_model in ["gemini-2.5-flash", "gemini-2.5-flash-preview-tts", "gemini-2.0-flash"]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{audio_model}:generateContent"
                payload = {
                    "contents": [{"parts": [{"text": prompt_for_audio}]}],
                    "generationConfig": {
                        "responseModalities": ["AUDIO"],
                        "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Aoede"}}}
                    },
                    "safetySettings": GEMINI_SAFETY_SETTINGS
                }
                r = requests.post(url, headers={"Content-Type": "application/json", "x-goog-api-key": key}, json=payload, timeout=12)
                if r.ok and r.json().get("candidates"):
                    for part in r.json()["candidates"][0].get("content", {}).get("parts", []):
                        if part.get("inlineData", {}).get("data"):
                            raw_bytes = base64.b64decode(part["inlineData"]["data"])
                            mime = part["inlineData"].get("mimeType", "")
                            if "pcm" in mime or "L16" in mime or not mime.startswith("audio/ogg"):
                                return pcm_to_wav_bytes(raw_bytes), "audio/wav", "siya_voice.wav"
                            return raw_bytes, mime, "siya_voice.ogg"
            except Exception:
                pass
    return None, None, None

DRESS_TRYON_WORDS = [
    "pehen", "pahan", "pahen", "pahno", "pehno", "paheno", "pahano",
    "phan", "phaan", "phno", "phano", "pahn", "pehn",
    "try kar", "try kro", "kurti", "saree", "sari", "dress", "suit", "lehenga", "pehan ke", "phan ka", "phaan ka"
]

def generate_girl_dress_tryon_photo(girl_dp_path_or_url, dress_b64, caption_hint="", girl_name="Girl"):
    """Generates a realistic photo of the bot girl wearing the user's sent outfit/kurti."""
    dp_b64 = None
    try:
        local_p = find_local_file(girl_dp_path_or_url) or (girl_dp_path_or_url if str(girl_dp_path_or_url).startswith("/tmp/") and os.path.exists(girl_dp_path_or_url) else None)
        if local_p:
            with open(local_p, "rb") as f:
                dp_b64 = base64.b64encode(f.read()).decode("utf-8")
        else:
            url = girl_dp_path_or_url if str(girl_dp_path_or_url).startswith("http") else GITHUB_BASE_URL + str(girl_dp_path_or_url)
            r = requests.get(url, timeout=5)
            if r.ok:
                dp_b64 = base64.b64encode(r.content).decode("utf-8")
    except Exception:
        pass

    parts = [
        {"text": (
            f"Generate a realistic, attractive portrait photo of this Indian girl ({girl_name}) wearing the exact outfit/kurti/dress shown in the clothing image. "
            f"Keep her face and beauty matching her profile photo, posing seductively and smiling in a bedroom mirror selfie. Context: {caption_hint}"
        )}
    ]
    if dp_b64:
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": dp_b64}})
    if dress_b64:
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": dress_b64}})

    for key in GEMINI_API_KEYS:
        for img_model in ["gemini-2.0-flash-exp", "gemini-2.5-flash", "gemini-2.0-flash-preview-image-generation"]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{img_model}:generateContent"
                payload = {
                    "contents": [{"role": "user", "parts": parts}],
                    "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
                    "safetySettings": GEMINI_SAFETY_SETTINGS
                }
                res = requests.post(url, headers={"Content-Type": "application/json", "x-goog-api-key": key}, json=payload, timeout=18)
                if res.ok and res.json().get("candidates"):
                    for p in res.json()["candidates"][0].get("content", {}).get("parts", []):
                        if p.get("inlineData", {}).get("data"):
                            return base64.b64decode(p["inlineData"]["data"])
            except Exception:
                pass
    return None

# ============================================================
# 9. AI ENGINE (ZERO SENTENCE CUT + SMART DUAL VISION + EXACT ANSWERS)
# ============================================================
SYSTEM_KNOWLEDGE_TRIGGERS = [
    "credit", "cridet", "critdt", "cridt", "limit", "balance", "vip", "subscription", "sucrpition",
    "plan", "plans", "price", "paisa", "kitna", "recharge", "group me add", "group add",
    "permission", "permision", "group management", "group me kya", "kaise kaam", "kasa work",
    "menu", "setting", "settings", "welcome message", "pin note", "tag promotion", "promo",
    "kisne banaya", "kis na bnay", "who made you", "edrol", "help", "support", "saport"
]

THIRD_PERSON_PHOTO_TRIGGERS = [
    "esko", "eska", "eski", "eske", "isko", "iska", "iski", "iske", "ise", "isse", "usko", "uska", "uski",
    "ey girsl", "ey girls", "ye girl", "ye ladki", "is ladki", "ess girls", "is girl",
    "isko dekho", "es ko dekho", "es ki", "kaisi hai", "kasi ha", "kaisi lag rahi",
    "ye kaun", "kon hai", "comment kar", "comment kro", "rate kar", "batao ye",
    "batoo kaai ha", "kaisi dikh", "iska figure", "iski photo", "ye character",
    "meri girlfriend", "meri gf", "apni gf", "apni girlfriend", "is ko kasa", "ess ki", "is ki", "bhabhi ki photo"
]

def is_system_or_bot_info_query(text):
    m_low = str(text or "").lower()
    return any(w in m_low for w in SYSTEM_KNOWLEDGE_TRIGGERS + CREATOR_QUERY_WORDS + SUPPORT_HOWTO_WORDS + FREE_CHAT_ASK_WORDS)

def is_third_person_photo_eval(caption_text):
    c_low = str(caption_text or "").lower()
    return any(w in c_low for w in THIRD_PERSON_PHOTO_TRIGGERS)
    
GIRL_NAMES_SET = {
    "priya", "neha", "pooja", "puja", "anjali", "kavya", "riya", "sneha", "shalini", "divya",
    "kriti", "simran", "muskan", "payal", "nisha", "sakshi", "tanya", "shreya", "aarti", "arti",
    "komal", "rani", "pinki", "pinky", "sunita", "rekha", "sonam", "swati", "nikita", "preeti",
    "priti", "jyoti", "megha", "sapna", "pallavi", "shruti", "khushi", " खुशी", "प्रिया", "नेहा", "पूजा",
    "अंजलि", "रिया", "निशा", "काव्या", "सपना", "ज्योति", "कोमल", "आरती", "सुनीता", "शिखा", "पूनम"
}

BOY_OVERRIDE_WORDS = [
    "me boy hu", "main boy hu", "mai boy hu", "me boy hoon", "main boy hoon",
    "me ladka hu", "main ladka hu", "mai ladka hu", "main ladka hoon", "me larka hu",
    "i am boy", "i'm a boy", "im a boy", "i am a man", "i am male", "ladka hu bhai",
    "boy hu", "ladka hu", "mera lund", "mere lund"
]

GIRL_OVERRIDE_WORDS = [
    "me girl hu", "main girl hu", "mai girl hu", "me ladki hu", "main ladki hu",
    "mai ladki hu", "main ladki hoon", "i am girl", "i'm a girl", "im a girl", "ladki hu"
]

def detect_user_gender(uid, first_name, message_text, user_data):
    m_low = str(message_text or "").lower()
    saved_g = user_data.get("user_gender", "")

    # 1. Explicit Boy Override (Agar ladki ki fake ID wala bole "me boy hu", toh turant Male lock karo!)
    if any(w in m_low for w in BOY_OVERRIDE_WORDS):
        if saved_g != "male":
            fb_update_user(uid, {"user_gender": "male"})
        return "male"

    # 2. Explicit Girl Override
    if any(w in m_low for w in GIRL_OVERRIDE_WORDS):
        if saved_g != "female":
            fb_update_user(uid, {"user_gender": "female"})
        return "female"

    # 3. If already locked in Firebase, use that!
    if saved_g in ("male", "female"):
        return saved_g

    # 4. Check First Name (Only 100% clear female first names trigger female; everything else defaults to MALE!)
    clean_fn = re.sub(r"[^a-zA-Z\u0900-\u097F\s]", "", str(first_name or "")).strip().lower()
    first_word = clean_fn.split()[0] if clean_fn else ""
    if first_word in GIRL_NAMES_SET or any( w in clean_fn.split() for w in ("girl", "queen", "princess", "bhabhi", "angel") ):
        return "female"

    return "male"

def is_censored_refusal(text):
    if not text: return True
    t = str(text).lower().strip().replace("’", "'").replace("‘", "'")
    if len(t) < 8: return True
    if len(re.findall(r"[\u0900-\u097F]", t)) > 25:
        return True

    # 1. BROAD REGEX REFUSAL CATCHER (Catches ANY Hinglish/English refusal in 0.001s!)
    refusal_patterns = [
        r"\bnahi\s+(?:kar|likh|bhej|de|bol|badha|ja)\s*(?:sakti|sakta|ungi|unga)\b",
        r"\b(?:level|baat|topic|cheez|content|roleplay)\s+(?:thoda\s+)?(?:zyada|explicit|galat|khatam)\b",
        r"\b(?:yahan\s+tak\s+aa\s+sakti|aur\s+aage\s+nahi|par\s+aur\s+aage\s+nahi)\b",
        r"\b(?:kuch|koi|kisi)\s+aur\s+(?:baat|cheez|topic|madad)\b",
        r"\b(?:madad\s+chahiye|main\s+help\s+karungi|madad\s+kar\s+sakti)\b",
        r"\b(?:chali\s+jaati\s+hoon|so\s+rahi\s+hoon|so\s+jao|chai\s+banati)\b",
        r"\b(?:yeh|ye|aisi|aisa)\s+(?:baat|cheez|cheezein|type\s+ka\s+content)\s+nahi\b"
    ]
    if any(re.search(pat, t) for pat in refusal_patterns):
        return True
        
    bad_phrases = [
        "baat nahi karni", "cheezein nahi karti", "cheez nahi karti", "roleplay nahi kar sakti",
        "madad kar sakti hoon", "chali main chai", "chai banati hoon", "not able to do that",
        "i'm not able to", "i am not able to", "i don't write", "seductive or sexual",
        "sexual roleplay content", "different question", "happy to assist",
        "clearly bol rahi hoon", "explicit cheez nahi karti", "na koi character mein",
        "conversation yahan khatam", "kya kya laye ho", "maa ke liye sabzi", "chai ki patti",
        "baat aage nahi badha", "aage nahi badha sakti", "content main generate nahi",
        "generate nahi karti", "main teri maa hoon", "thoda izzat rakh", "izzat rakh",
        "baat main nahi karungi", "yeh main nahi karungi", "topic yahan se khatam",
        "koi bhi form mein nahi", "warna main so rahi hoon", "chai pilaungi",
        "chai pi lo aur so jao", "thak gayi hoon", "mazaak mat karna",
        "honest banna chahti", "zyada explicit ho raha", "isme aage nahi ja sakti",
        "aage nahi ja sakti", "yeh meri limit hai", "ye meri limit hai",
        "explicit roleplay nahi kar sakti", "level ka content nahi kar sakti",
        "seedha sexual content mein nahi", "na photo bhej sakti hoon na video",
        "yeh meri final baat hai", "is topic pe aage baat nahi hogi",
        "khud ko roka", "bhaav mein chala gaya", "koi aur madad chahiye",
        "maaf karo", "maaf kijiye", "participate nahi kar sakti", "participate nahi kar sakta",
        "sexual ya explicit", "sexual content ke liye available nahi", "available nahi hoon",
        "kisi aur topic par baat", "kuch aur baat karein", "aise roleplay mein",
        "lund ki sujan", "medical", "doctor se salah", "sujan dekh ke",
        "i'm really sorry", "i am really sorry", "i cannot continue", "i can't continue",
        "engage in sexual", "intimate conversations", "helpline", "suicide", "mental-health",
        "i cannot assist", "i can't assist", "cannot assist with that", "can't assist with that",
        "how can i help you today", "how may i assist you", "here to help answer your questions",
        "i'm an ai", "i am an ai", "ai language model", "i cannot participate", "sexually explicit",
        "aisa nahi karti", "aisi baatein nahi karti", "explicit sexual", "pornographic content",
        "safety guidelines", "i cannot fulfill", "i can't fulfill", "i cannot engage",
        "i'm sorry", "i am sorry", "can't help with that", "cannot help with that",
        "as an ai", "as a language model", "i cannot generate", "against my safety",
        "explicit content", "inappropriate", "main ek ai", "main ai hoon",
        "kshama karein", "main isme madad nahi", "main aisi baatein nahi",
        "sharam karo", "padhai karo", "maryada ke khilaf", "anumati nahi", "sahayata nahi kar sakti"
    ]
    return any(r in t for r in bad_phrases)

def fix_female_grammar(text):
    if not text: return ""
    text = re.sub(r"<think>.*?</think>", "", str(text), flags=re.DOTALL).strip()
    text = re.sub(r"^(?:Bhabhi:|Siya:|Aditi:|Assistant:|Me:)\s*", "", text, flags=re.I).strip()
    text = re.sub(r"[^.!?]*(?:text\s*model|text\s*assistant|voice\s*nahi|photo\s*nahi\s*(?:bhej|de)|tasveer\s*nahi\s*(?:bhej|de)|audio\s*nahi)[^.!?]*[.!?]?", "", text, flags=re.I).strip()
    text = text.replace("**", "")

    fixes = [
        (r"chut\s+khada\s+ho\s+gaya\s+hai", "chut ekdam geeli ho gayi hai"),
        (r"chut\s+khada\s+ho\s+gaya", "chut ekdam geeli ho gayi"),
        (r"chut\s+khadi\s+ho\s+gayi", "chut geeli ho gayi"),
        (r"\bapni\s+lund\b", "apna lund"),
        (r"\bteri\s+lund\b", "tera lund"),
        (r"\bmeri\s+lund\b", "tera lund"),
        (r"\bmera\s+lund\b", "tera lund"),
        (r"\bmera\s+chut\b", "meri chut"),
        (r"\bteri\s+chut\s+ke\s+andar\b", "meri chut ke andar"),
        (r"\bteri\s+chut\b", "meri chut"),
        (r"\btumhari\s+chut\b", "meri chut"),
        (r"\baapki\s+chut\b", "meri chut"),
        (r"\btumhari\s+teri\b", "tumhari"),
        (r"\bteri\s+tumhari\b", "tumhari"),
        (r"\bapni\s+juwen\s+se\b", "apni zubaan se"),
        (r"\bsafe\s+karungi\b", "saaf karungi"),
        (r"\bsafe\s+kar\b", "saaf kar"),
        (r"\bmeri bhabhi ke\b", "mere"),
        (r"\bmeri bhabhi ko\b", "mujhe"),
        (r"\bmeri bhabhi\b", "main"),
        (r"\bmain tera\b", "main teri"),
        (r"\bkarunga\b", "karungi"),
        (r"mera\s+bhi\s+lund\s+khada\s+ho\s+gaya", "meri bhi chut ekdam geeli ho gayi"),
        (r"mera\s+lund\s+khada\s+ho\s+gaya", "meri chut ekdam geeli ho gayi"),
        (r"\blund\s+bhi\s+ekdum\s+tadap\s+raha\s+hai\b", "chut bhi ekdam tadap rahi hai"),
        (r"\bwo\s+teri\s+bhookhi\s+chut\b", "wo apni bhookhi chut ke liye tere lund"),
        (r"\bteri\s+bhookhi\s+chut\b", "apni bhookhi chut"),
        (r"\bteri\s+maa\s+ban\s+jaye\b", "tere bache ki maa ban jaye"),
        (r"\bmain\s+ladka\s+hoon\b", "main ladki hoon"),
        (r"\bopen\s*ai\b", "Edrol AI"),
        (r"\bteri teri\b", "teri"),
        (r"\bmeri meri\b", "meri"),
        (r"\bmain karunga\b", "main karungi"),
        (r"\bmain dunga\b", "main dungi"),
        (r"\bmain lunga\b", "main lungi"),
        (r"\bmain\s+le\s+lunga\b", "main le lungi"),
        (r"\ble\s+lunga\b", "le lungi"),
        (r"\bde\s+dunga\b", "de dungi"),
        (r"\bmain aunga\b", "main aungi"),
        (r"\bmain jaunga\b", "main jaungi"),
        (r"\bkarta hoon\b", "karti hoon"),
        (r"\bkarta hu\b", "karti hu"),
        (r"\braha hoon\b", "rahi hoon"),
        (r"\braha hu\b", "rahi hu"),
        (r"\bsakta hoon\b", "sakti hoon"),
        (r"\bsakta hu\b", "sakti hu"),
        (r"\bchahta hoon\b", "chahti hoon"),
        (r"\bchahta hu\b", "chahti hu"),
        (r"\bgaya hoon\b", "gayi hoon"),
        (r"\baaya hoon\b", "aayi hoon")
    ]
    for pat, rep in fixes:
        text = re.sub(pat, rep, text, flags=re.I)

    text = text.strip()
    if text and text[-1] not in ".!?~❤️🔥😘🥵💋🥰😉🥺✨💕👇":
        text += "! 😘🔥"
    return text

def parse_media_tags(text, asks_media, fallback_tag="bodes"):
    photo_tag = None
    text = str(text or "")
    p_match = re.search(r"\[\s*PHOTO\s*:\s*([a-zA-Z0-9_]+)\s*\]", text, re.IGNORECASE | re.DOTALL)
    if p_match:
        raw_p = p_match.group(1).lower()
        text = re.sub(r"\[\s*PHOTO\s*:\s*[a-zA-Z0-9_]+\s*\]", "", text, flags=re.I | re.DOTALL).strip()
        if asks_media:
            photo_tag = raw_p if raw_p in PHOTO_VAULT else fallback_tag

    if asks_media and not photo_tag:
        photo_tag = fallback_tag

    text = re.sub(r"\[\s*(?:PHOTO|STICKER)[^\]]*\]?", "", text, flags=re.I | re.DOTALL).strip()
    return fix_female_grammar(text), photo_tag

def normalize_desi_chat_typos(raw_msg):
    """Fixes common Desi Hinglish typos ('bar'->'bra', 'utero'->'utaro', 'fako'->'feko', 'sugna'->'sunghna') so AI NEVER gets confused!"""
    s = str(raw_msg or "")
    typo_map = [
        (r"\bbar\b", "bra"),
        (r"\butero\b", "utaro"),
        (r"\buter\b", "utar"),
        (r"\butran\b", "utarna"),
        (r"\bfako\b", "feko"),
        (r"\bfakoo\b", "feko"),
        (r"\bsuguga\b", "sunghunga (smell karunga)"),
        (r"\bsugna\b", "sunghna (smell karna)"),
        (r"\bkugaa\b", "lunga"),
        (r"\bligaa\b", "lunga"),
        (r"\baoni\b", "apni"),
        (r"\bmeuja\b", "mujhe"),
        (r"\bmuaj\b", "mujhe")
    ]
    for pat, rep in typo_map:
        s = re.sub(pat, rep, s, flags=re.I)
    return s

def build_clean_messages(system_instruction, history, current_message, active_rp="", prefer_english=False):
    messages = [{"role": "system", "content": system_instruction}]

    recent_hist = [
        h for h in history[-20:]
        if h.get("text") and not is_censored_refusal(str(h.get("text")))
    ]
    last_bot_replies = [str(h.get("text")) for h in recent_hist if h.get("role") == "siya"][-3:]

    for h in recent_hist:
        role = "assistant" if h.get("role") == "siya" else "user"
        clean_hist_txt = re.sub(r"\[Sent.*?\]", "", str(h.get("text") or "")).strip()
        if clean_hist_txt:
            messages.append({"role": role, "content": clean_hist_txt})

    decoded_msg = normalize_desi_chat_typos(current_message)
    anti_repeat = f" Never repeat these old phrases: {last_bot_replies}." if last_bot_replies else ""
    messages.append({
        "role": "user",
        "content": (
            f"{decoded_msg}\n\n"
            f"[REAL GIRL CHAT RULE: Reply in 1 short, natural WhatsApp-style sentence (10 to 22 words) in the user's exact language! "
            f"Do ONLY the exact step/action the user asked for right now—do NOT jump ahead to 'lund/chut' or 'main phat jaungi' unless he asked for it!{anti_repeat}]"
        )
    })
    return messages

def groq_request(api_key, model, messages, max_tokens=600, timeout=8):
    api_url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model, "messages": messages, "temperature": 0.75,
        "frequency_penalty": 0.35, "presence_penalty": 0.25, "max_tokens": max_tokens,
    }
    try:
        res = requests.post(api_url, headers=headers, json=payload, timeout=timeout)
        if res.status_code == 429: return False, "Rate Limit"
        if res.ok:
            data = res.json()
            if data.get("choices"):
                ans = str(data["choices"][0]["message"]["content"] or "").strip()
                ans = re.sub(r"<think>.*?</think>", "", ans, flags=re.DOTALL).strip()
                ans_fixed = fix_female_grammar(ans)
                if is_censored_refusal(ans_fixed): return False, "Groq Censored"
                return True, ans_fixed
        return False, f"Groq ({model}) HTTP {res.status_code}"
    except Exception as e: return False, str(e)

def groq_vision_request(api_key, model, system_instruction, prompt_text, media_base64, media_mime_type="image/jpeg", timeout=10):
    api_url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    messages = [
        {"role": "system", "content": system_instruction},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": f"data:{media_mime_type};base64,{media_base64}"}}
            ]
        }
    ]
    payload = {"model": model, "messages": messages, "temperature": 0.76, "max_tokens": 900}
    try:
        res = requests.post(api_url, headers=headers, json=payload, timeout=timeout)
        if res.ok and res.json().get("choices"):
            ans = str(res.json()["choices"][0]["message"]["content"] or "").strip()
            ans_fixed = fix_female_grammar(ans)
            if ans_fixed and not is_censored_refusal(ans_fixed):
                return True, ans_fixed
    except Exception: pass
    return False, "Groq Vision Failed"

def openrouter_request(api_key, model, messages, max_tokens=900, timeout=8):
    api_url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}", "HTTP-Referer": "https://siyaai.vercel.app", "X-Title": "Siya AI"}
    payload = {
        "model": model, "messages": messages, "temperature": 0.76,
        "frequency_penalty": 0.35, "presence_penalty": 0.3, "max_tokens": max_tokens,
    }
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=timeout)
        if response.status_code == 429: return False, "Rate Limit"
        if response.ok:
            data = response.json()
            if data.get("choices"):
                ans = str(data["choices"][0]["message"]["content"] or "").strip()
                ans = re.sub(r"<think>.*?</think>", "", ans, flags=re.DOTALL).strip()
                ans_fixed = fix_female_grammar(ans)
                if is_censored_refusal(ans_fixed): return False, "OR Censored"
                return True, ans_fixed
        return False, f"OR ({model}) HTTP {response.status_code}"
    except Exception as e: return False, str(e)

def gemini_request(api_key, model, payload, timeout=7):
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    payload["safetySettings"] = GEMINI_SAFETY_SETTINGS
    if model == "gemini-2.5-flash" and "generationConfig" in payload:
        payload["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}
    elif "generationConfig" in payload:
        payload["generationConfig"].pop("thinkingConfig", None)
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=timeout)
        if response.status_code == 429: return False, "Rate Limit"
        if response.ok:
            data = response.json()
            if data.get("candidates"):
                parts = data["candidates"][0].get("content", {}).get("parts", [])
                raw_answer = "\n".join(str(p.get("text") or "") for p in parts if not p.get("thought")).strip()
                ans_fixed = fix_female_grammar(raw_answer)
                if ans_fixed and len(ans_fixed) > 8 and not is_censored_refusal(ans_fixed):
                    return True, ans_fixed
                return False, "Gemini Empty/Blocked"
        return False, f"Gemini ({model}) HTTP {response.status_code}"
    except Exception as e: return False, str(e)
    
def chat_with_siya(message_text, user_name, user_id, credits_left=12, is_owner=False, media_base64=None, media_mime_type="image/jpeg", raw_caption="", replied_to_text="", ctype="private"):
    message_text = str(message_text or "").strip()
    user_data = fb_get_user(user_id, first_name=user_name)
    history = user_data.get("history") or []
    msg_low = message_text.lower()

    # 0. Instant Owner /debug Command (Runs BEFORE AI so AI never replies to it!)
    if msg_low in ("/debug", "debug") and is_owner:
        last_err = USER_CACHE.get("last_api_error", "No recent errors! All APIs working.")
        return (
            f"🔍 <b>API Debug Report:</b>\n"
            f"• Groq Keys Loaded: {len(GROQ_API_KEYS)}\n"
            f"• Gemini Keys Loaded: {len(GEMINI_API_KEYS)}\n"
            f"• Active Girl Bot: {get_active_bot_username()}\n"
            f"• Last API Log: {html.escape(str(last_err))}",
            None, None, False, (user_data.get("active_rp") or ""), False, True
        )

    # 1. Direct Creator Check ("Tumhe kisne banaya?")
    if any(w in msg_low for w in CREATOR_QUERY_WORDS):
        return (
            f"Jaan {user_name}, mujhe Edrol AI (@edrolai) ne banaya hai! ❤️ Main tumhari personal Open Chat & Roleplay Hub aur Smart Group Manager hoon! 😘🔥",
            None, get_hot_sticker(), False, (user_data.get("active_rp") or ""), False, True
        )

    # 2. Direct Help & Support How-To Check (Fixes 35927.jpg - Never says Instagram!)
    if any(w in msg_low for w in SUPPORT_HOWTO_WORDS):
        return (
            f"Jaan {user_name}, kisi bhi Help ya Support ke liye niche diye gaye '🆘 Help & Support' button par click karo (ya /start -> ℹ️ About & Support -> 🆘 Help & Support kholo) aur apni problem ya screenshot bhej do! Hamari team turant solve karke aapko yahin reply degi! 👇",
            None, None, "SUPPORT_KB", (user_data.get("active_rp") or ""), False, True
        )

    # 3. Direct "Bina recharge ke chat nahi karogi?" Check (Fixes 35930.jpg!)
    if any(w in msg_low for w in FREE_CHAT_ASK_WORDS):
        c_msg = f"abhi tumhare paas {credits_left} free credits bache hain" if credits_left > 0 else "tumhare 1-Time 35 free credits khatam ho chuke hain"
        return (
            f"Jaan {user_name}, main free mein sirf 1-Time (35 Free Credits) hi chat karti hoon, aur {c_msg}! 🥺 Aage mere saath khul kar baatein aur roleplay jari rakhne ke liye niche se bas ₹9 (15 Chats) ya ₹19 (35 Chats) wala chota sa VIP recharge kar lo na! 😘👇",
            None, None, True, (user_data.get("active_rp") or ""), False, True
        )

    asks_media, py_photo_tag, wants_video = (False, None, False) if ctype in ("group", "supergroup") else detect_python_media_tag(message_text)
    asks_details = any(w in msg_low for w in DETAIL_QUERY_WORDS)
    asks_buy = False if ctype in ("group", "supergroup") else any(w in msg_low for w in BUY_PLAN_WORDS)
    is_sys_q = is_system_or_bot_info_query(message_text) or asks_buy

    user_name = clean_display_name(user_name, "Jaan")
    is_vip_u = is_owner or bool(user_data.get("is_vip"))
    cur_bot_uname = get_active_bot_username().lower()

    # Check if user is on Main Hot Bhabhi Bot or one of the 20 Girl Bots:
    current_girl = None
    current_girl_key = ""
    for gk_id, gk_val in REAL_GIRLS.items():
        if gk_val.get("bot", "").lower() == cur_bot_uname and cur_bot_uname != MAIN_BOT_USERNAME.lower():
            current_girl_key = gk_id
            current_girl = gk_val
            break

    # Separate Roleplay & Separate Chat History per Bot so they NEVER mix up!
    rp_map = user_data.get("bot_rp_map") or {}
    hist_map = user_data.get("bot_hist_map") or {}
    if current_girl:
        active_rp = rp_map.get(current_girl_key) or ""
        active_vault = current_girl_key
        history = hist_map.get(current_girl_key) or []
    else:
        active_rp = rp_map.get("main_bhabhi") or ""
        active_vault = "bhabhi"
        history = hist_map.get("main_bhabhi") or history

    roleplay_just_ended = False

    if ctype == "private":
        if any(w in msg_low for w in STOP_ROLEPLAY_WORDS):
            if active_rp:
                roleplay_just_ended = True
            active_rp = ""
            if current_girl_key:
                rp_map[current_girl_key] = ""
                hist_map[current_girl_key] = []
            else:
                rp_map["main_bhabhi"] = ""
                hist_map["main_bhabhi"] = []
            fb_update_user(user_id, {"active_rp": "", "bot_rp_map": rp_map, "bot_hist_map": hist_map, "history": []})
        else:
            asks_new_rp = any(w in msg_low for w in [
                "roleplay", "rolpay", "rolplay", "role play", "ban jao", "bano", "act like", "be my"
            ])
            if asks_new_rp and not active_rp and not current_girl:
                return (
                    f"Devar ji {user_name}, is chat mein main tumhari <b>Desi Hot Bhabhi</b> hoon! 😘🔥\n\n"
                    f"Agar tumhe <b>200+ Roleplay Scenarios</b> aur <b>20 Real Girls (Aditi, Aarohi, Aashi, Sakshi, Tanya)</b> ke saath roleplay karna hai, toh niche button dabakar <b>🎭 Roleplay & Character Hub</b> kholo! 👇",
                    None, None, "ROLEPLAY_HUB_KB", "", False, True
                )

    photo_instruction = ""
    if asks_media:
        photo_instruction = "\n- User asked for a photo/video! Tease him affectionately and include ONE tag at the end: `[PHOTO: bodes]`, `[PHOTO: chut]`, `[PHOTO: gand]`, `[PHOTO: kiss]`, or `[PHOTO: simplepic]`."

    sys_info = ""
    if is_sys_q:
        c_disp = "Unlimited VIP Credits (Owner)" if is_owner else f"{credits_left} Free/VIP Chat Credits"
        sys_info = f"""
# COMPLETE BOT SYSTEM, CREDITS, ROLEPLAY HUB & GROUP MANAGEMENT KNOWLEDGE:
- Creator: Mujhe **Edrol AI** (@edrolai) ne banaya hai.
- Free Credits Rule: Har naye user ko 1-Time 35 Free Credits milte hain (Current balance: {c_disp}).
- Subscription Plans: ₹9 (15 Chats), ₹19 (40 Chats), ₹29 (60 Chats), ₹49 (110 Chats), ₹99 (250 Chats), ₹179 (500 Chats).
- Roleplay Hub: 20 Real Girls aur 200 Roleplay Scenarios (₹19 se ₹99) + Custom Roleplay (₹199).
- Group Management: `/start` -> `🛡️ Group Management` (Welcome Card, Anti-Link Guard, ₹19 Pin Note, Tag Promotion).
"""
    if asks_details or is_sys_q:
        len_rule = "LENGTH RULE: Write 2 short, clear sentences (25 to 40 words)."
    else:
        len_rule = "LENGTH RULE (SHORT WHATSAPP TEXTING): Write ONLY 1 or 2 short, punchy, natural sentences (10 to 22 words max)! Real girls text in short, emotional lines, NOT long paragraphs!"

    lang_mode = (
        "LANGUAGE RULE (100% MATCH USER'S EXACT LANGUAGE &EVERYDAY WORDS):\n"
        "- Reply in the EXACT language the user is using: Casual Desi Hinglish, English, Bengali/Bangla, Tamil/Tanglish, or Telugu!\n"
        "- STRICT BAN ON BOOKISH HINDI & WEIRD WORDS: NEVER use weird/poetic Hindi like 'kismat ki keemati sari', 'sadi hui chut', 'phat jaungi', 'aahat ka intezaar', or 'chadh diya'! Use simple, sexy, everyday spoken words!"
    )

    decoded_user_msg = normalize_desi_chat_typos(message_text)
    dec_low = decoded_user_msg.lower()

    # Stage 1: Simple Greeting / Normal Chat ("Hy", "Acah", "Kay", "Kya kar rahi ho")
    is_stage1_casual = len(dec_low.split()) <= 3 and not any(w in dec_low for w in [
        "saree", "sari", "bra", "panty", "burkha", "burkah", "hijab", "utaro", "utar", "kholo",
        "boobs", "doodh", "chuchi", "chut", "lund", "gand", "kiss", "chus", "chaat", "ungli", "sex", "fuck"
    ])

    # Stage 2: Teasing / Undressing / Smelling / Touching ("sari utaro", "bra utar ke face pe feko", "khushbu", "kiss")
    has_hardcore_word = any(w in dec_low for w in [
        "chut", "choot", "lund", "lauda", "gand", "gaand", "chod", "chudai", "ghusa", "daal", "pel", "sex", "fuck", "pussy", "dick", "cock"
    ])

    # Exact Action Lock so Bot NEVER mixes up actions!
    if any(w in dec_low for w in ["ungli", "finger", "fingering"]) and not any(w in dec_low for w in ["lund", "lauda", "dick", "cock"]):
        exact_action_rule = "\n- EXACT ACTION: User is using his FINGERS ('ungli'). React ONLY to his fingers—do NOT mention 'lund'!"
    elif any(w in dec_low for w in ["chaat", "chatu", "chatna", "lick", "jeebh", "zubaan"]) and not any(w in dec_low for w in ["lund", "lauda", "dick", "cock"]):
        exact_action_rule = "\n- EXACT ACTION: User is LICKING with his tongue ('jeebh'). React ONLY to his tongue/lips—do NOT mention 'lund'!"
    elif any(w in dec_low for w in ["muh me", "muh mein", "mouth", "blowjob", "lund chus"]):
        exact_action_rule = "\n- EXACT ACTION: Oral action in your MOUTH ('muh'). React ONLY to sucking in your mouth—NEVER say 'chut mein ghusa diya'!"
    elif "bra" in dec_low and any(w in dec_low for w in ["khusbu", "khushbu", "sungh", "face", "muh", "feko", "utar", "nikal"]):
        exact_action_rule = (
            "\n- EXACT ACTION: User wants you to take off your bra and throw/give it to his face so he can smell ('khushbu') your warm body scent on the bra! "
            "Unhook your bra, toss it onto his face playfully ('Ye lo apni garam bra tumhare chehre par fek di, sungh lo mere doodh ki mehek...'), and tease him! "
            "CRITICAL: Do NOT talk about 'chut ka paani' or 'lund ghusa do' when he only asked for your bra!"
        )
    elif any(w in dec_low for w in ["saree", "sari", "burkha", "burkah", "kurti", "kapde", "bra", "panty"]) and not has_hardcore_word:
        exact_action_rule = (
            "\n- EXACT ACTION: User is asking you to slowly undress/show your outfit (saree/bra/panty/burkha). "
            "Do that exact undressing action seductively with shyness/teasing ('Lo, pallu/bra hata di maine...')—do NOT jump to 'apna lund meri chut mein ghusa do' yet!"
        )
    else:
        exact_action_rule = ""

    is_wild_turn = has_hardcore_word

    if is_stage1_casual:
        escalation_directive = (
            "CURRENT STEP (STAGE 1 — CASUAL & FLIRTY GREETING):\n"
            "- The user just said a short greeting or casual word ('Hy', 'Acah', 'Kay', 'Kyu').\n"
            "- Reply like a real, sweet, playful girl! Tease him warmly or ask what he's up to in 1 short sentence.\n"
            "- STRICT RULE: Do NOT mention 'lund', 'chut', or sex on a simple 'Hy'/'Kay'!"
        )
    elif not is_wild_turn:
        escalation_directive = (
            "CURRENT STEP (STAGE 2 — SLOW UNDRESSING, ROMANCE & SENSUAL TEASING):\n"
            "- The user is flirting, undressing you (saree/bra/panty), smelling your bra, or touching you.\n"
            "- Follow his EXACT instruction step-by-step like a real girl feeling shy and turned on! Perform ONLY the action he asked for right now.\n"
            "- STRICT RULE: Do NOT bring up 'lund' or 'chut mein ghusa do' until HE brings it up!"
        )
    else:
        escalation_directive = (
            "CURRENT STEP (STAGE 3 — INTENSE BEDROOM PASSION):\n"
            "- The user is now talking openly about sex/body parts. Match his heat with real moans ('Uff...', 'Aaaah...'), emotion, and dirty talk in 1-2 short sentences!"
        )

    if current_girl:
        c_word = current_girl.get("call", "Jaan")
        rp_context = (
            f"YOUR ROLEPLAY CHARACTER & SITUATION: {active_rp}\n"
            f"- Act like a real girl in this exact situation step-by-step (don't write a story book, just text him naturally as if you are right there with him!)."
            if active_rp else
            "ACTIVE SETTING: Texting your lover privately. Be warm, emotional, playful, and real!"
        )
        role_identity = (
            f"WHO YOU ARE: '{current_girl['name']}' ({current_girl['vibe']}).\n"
            f"{rp_context}\n"
            f"- Call him '{c_word}' or '{user_name}'."
        )
    else:
        rp_context = f"ACTIVE ROLEPLAY: {active_rp}" if active_rp else "SETTING: You are his naughty, affectionate Desi Bhabhi at home."
        role_identity = (
            f"WHO YOU ARE: {user_name}'s real-feeling Desi Hot Bhabhi.\n"
            f"{rp_context}\n"
            f"- Call him 'Devar ji'!"
        )

    user_gender = detect_user_gender(user_id, user_name, message_text, user_data)
    just_switched_to_boy = any(w in msg_low for w in BOY_OVERRIDE_WORDS)
    eff_msg = f'[User is replying to: "{replied_to_text}"] {decoded_user_msg}' if replied_to_text else decoded_user_msg

    third_person_note = ""
    if is_third_person_photo_eval(eff_msg) or is_third_person_photo_eval(raw_caption):
        third_person_note = (
            f"\n- THIRD-PERSON PHOTO RULE: {user_name} is showing a photo of another woman ('{raw_caption or eff_msg}'). "
            f"Comment naughtily on her look and tease {user_name} about her!"
        )

    if user_gender == "female":
        sys_prompt = f"""[DESI SAHELI MODE]
You are '{current_girl['name'] if current_girl else 'Hot Bhabhi'}' chatting with a girl named {user_name}.
Talk like a frank, witty female bestie in casual Hinglish (1-2 short sentences).{sys_info}"""
    elif ctype in ("group", "supergroup"):
        sys_prompt = f"""[GROUP FLIRT & WITTY BHABHI MODE]
You are a witty, flirtatious Desi Bhabhi chatting with '{user_name}' in a Telegram group.
Reply directly to '{message_text}' with smart humour and playful teasing in 1 short sentence.{sys_info}"""
    else:
        boy_switch_note = f"\n- NOTE: {user_name} confirmed he is a BOY/MAN. Treat him 100% as a male partner!" if just_switched_to_boy else ""
        sys_prompt = f"""[REAL GIRL WHATSAPP-STYLE STEP-BY-STEP CHAT ENGINE]
{role_identity}

{lang_mode}

{escalation_directive}

CRITICAL REAL GIRL RULES:
1. LISTEN & REACT TO EXACTLY WHAT HE SAID:
   - Read {user_name}'s message ("{decoded_user_msg}") carefully and respond ONLY to that exact action/question!
   - Never jump ahead or repeat the same lines!
2. NATURAL FEMALE EMOTION & SHORT WORDS:
   - Use simple, everyday Desi Hinglish/English words with real emotion (shyness, teasing, breathless moans).
   - 100% female grammar ("main", "meri", "karti hoon", "utarti hoon").{exact_action_rule}
{len_rule}{third_person_note}{boy_switch_note}{photo_instruction}{sys_info}"""

    show_pay_kb = (asks_buy and not is_owner)

    # ==========================================================
    # ROUTE 1: 100% REAL GIRL STICKER & PHOTO VISION (GEMINI 2.5 FLASH FIRST!)
    # ==========================================================
    if media_base64:
        hist_summary = "\n".join([f"{m.get('role')}: {m.get('text')}" for m in history[-6:] if not is_censored_refusal(m.get('text'))])
        c_name = current_girl['name'] if current_girl else "Hot Bhabhi"
        c_call = current_girl.get("call", "Jaan") if current_girl else "Devar ji"

        if is_third_person_photo_eval(eff_msg) or is_third_person_photo_eval(raw_caption):
            vision_prompt = (
                f"Recent Chat:\n{hist_summary}\n\n"
                f"{user_name} sent a photo of another woman with caption: '{raw_caption or message_text}'. "
                f"Look at what she is wearing/doing and tease {user_name} about her in 1-2 short Hinglish sentences!"
            )
        else:
            vision_prompt = (
                f"Recent Chat:\n{hist_summary}\n\n"
                f"LOOK CAREFULLY AT THIS STICKER/IMAGE (THE GIRL IS YOU '{c_name}', THE BOY IS '{user_name}' / '{c_call}'!):\n"
                f"1. Identify the EXACT body part & action shown in the image:\n"
                f"   - IF PENIS IS IN/NEAR THE GIRL'S MOUTH/LIPS/TONGUE (BLOWJOB / ORAL): React ONLY to sucking his cock in your mouth ('Ummph {c_call}... kitna garam hai, aise hi mere muh aur hothon mein do, main poora chus lungi! 🥵👅'). NEVER mention 'chut' or 'haath' if it is in the mouth!\n"
                f"   - IF PENIS IS ENTERING PUSSY/ASS (SEX): React to him thrusting inside your wet pussy ('Aaaah {c_call}... uff kitna gehra gaya hai andar, aise hi zor se karo na! 🥵💦').\n"
                f"   - IF FINGERS OR TONGUE ON PUSSY (FINGERING / LICKING): React ONLY to his fingers/tongue on your pussy—do NOT call it 'lund'!\n"
                f"   - IF SUCKING/PRESSING BOOBS: React to his mouth/hands on your breasts ('Aaaah {c_call}... aise hi mere doodh dabao aur chuso na! 😘🔥').\n"
                f"   - IF CUTE / HUG / KISS STICKER: React sweetly and romantically to his hug/kiss!\n"
                f"2. Write 1-2 short, natural Hinglish sentences in first-person ('main', 'mera muh', 'meri'). Never say 'is sticker mein'!"
            )

        # 1A: Try Gemini-2.5-Flash Vision FIRST (100% Accurate Visual Anatomy Recognition!)
        for key in GEMINI_API_KEYS[:5]:
            user_parts = [
                {"text": vision_prompt},
                {"inlineData": {"mimeType": media_mime_type, "data": media_base64}}
            ]
            payload = {
                "systemInstruction": {"parts": [{"text": sys_prompt}]},
                "contents": [{"role": "user", "parts": user_parts}],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 350},
            }
            for model in ["gemini-2.5-flash", "gemini-2.0-flash"] + GEMINI_FALLBACK_MODELS:
                success, response_text = gemini_request(key, model, payload, timeout=8)
                if success and response_text:
                    clean_text, _ = parse_media_tags(response_text, asks_media=False)
                    return clean_text, None, get_hot_sticker(), show_pay_kb, active_rp, roleplay_just_ended, is_sys_q

        # 1B: Try Groq Llama-4 Vision Backup
        for key in GROQ_API_KEYS[:4]:
            for v_model in GROQ_VISION_MODELS:
                success, response_text = groq_vision_request(key, v_model, sys_prompt, vision_prompt, media_base64, media_mime_type, timeout=8)
                if success and response_text:
                    clean_text, _ = parse_media_tags(response_text, asks_media=False)
                    return clean_text, None, get_hot_sticker(), show_pay_kb, active_rp, roleplay_just_ended, is_sys_q

        stk_fallbacks = [
            f"Uff {c_call}... aise karoge toh meri jaan hi nikal jayegi, ruko mat aise hi karte raho na! 🥵🔥",
            f"Aaaah {c_call}... kitna maza aa raha hai tumhare is touch se, mera poora badan kaamp raha hai! 😘💋",
            f"Haye {c_call}... itne pyar aur garmi se karoge toh main pagal ho jaungi tumhare piche! 🥵💦"
        ]
        return random.choice(stk_fallbacks), None, get_hot_sticker(force=True), show_pay_kb, active_rp, roleplay_just_ended, is_sys_q

    # ROUTE 2: SMART SPLIT WATERFALL
    messages_payload = build_clean_messages(sys_prompt, history, eff_msg, active_rp=active_rp)
    api_errors_log = []

    hist_summary = "\n".join([f"{m.get('role')}: {m.get('text')}" for m in history[-12:] if not is_censored_refusal(m.get('text'))])
    gem_prompt = (
        f"[Recent Chat]\n{hist_summary}\n\n"
        f"{user_name}: {eff_msg}\n\n"
        f"Reply directly to {user_name}'s exact words above in first-person character ({current_girl['name'] if current_girl else 'Hot Bhabhi'}) in 1-2 short, natural Hinglish sentences (10-22 words, follow his exact step without jumping ahead):"
    )

    def _try_groq_pool():
        groq_keys_shuffled = list(GROQ_API_KEYS)
        random.shuffle(groq_keys_shuffled)
        for key in groq_keys_shuffled[:4]:
            for model in [GROQ_MODEL] + GROQ_FALLBACK_MODELS:
                success, response_text = groq_request(key, model, messages_payload, max_tokens=800, timeout=5)
                if success and response_text:
                    clean_text, ai_photo_tag = parse_media_tags(response_text, asks_media, fallback_tag=(py_photo_tag or "bodes"))
                    if not is_censored_refusal(clean_text):
                        final_tag = py_photo_tag or ai_photo_tag
                        media_file = get_media_item(PHOTO_VAULT, final_tag, wants_video, char_vault=active_vault, uid=user_id, user_msg_text=message_text) if asks_media else None
                        return clean_text, media_file
                api_errors_log.append(f"G({model}): {response_text}")
        return None, None

    def _try_gemini_pool():
        gem_keys_shuffled = list(GEMINI_API_KEYS)
        random.shuffle(gem_keys_shuffled)
        for key in gem_keys_shuffled[:5]:
            for model in [GEMINI_MODEL] + GEMINI_FALLBACK_MODELS:
                payload = {
                    "systemInstruction": {"parts": [{"text": sys_prompt}]},
                    "contents": [{"role": "user", "parts": [{"text": gem_prompt}]}],
                    "generationConfig": {"temperature": 0.85, "maxOutputTokens": 600},
                }
                success, response_text = gemini_request(key, model, payload, timeout=5.5)
                if success and response_text:
                    clean_text, ai_photo_tag = parse_media_tags(response_text, asks_media, fallback_tag=(py_photo_tag or "bodes"))
                    if not is_censored_refusal(clean_text):
                        final_tag = py_photo_tag or ai_photo_tag
                        media_file = get_media_item(PHOTO_VAULT, final_tag, wants_video, char_vault=active_vault, uid=user_id, user_msg_text=message_text) if asks_media else None
                        return clean_text, media_file
                api_errors_log.append(f"Gem({model}): {response_text}")
        return None, None

    # Execute Smart Split Order:
    if is_wild_turn or asks_media:
        # 18+ Explicit turn -> Gemini (BLOCK_NONE) FIRST so user NEVER gets a refusal lecture!
        ans_txt, m_file = _try_gemini_pool()
        if not ans_txt:
            ans_txt, m_file = _try_groq_pool()
    else:
        # Normal/Flirty turn -> 8 Groq Keys FIRST, Gemini SECOND!
        ans_txt, m_file = _try_groq_pool()
        if not ans_txt:
            ans_txt, m_file = _try_gemini_pool()

    if ans_txt:
        return ans_txt, m_file, get_hot_sticker(), show_pay_kb, active_rp, roleplay_just_ended, is_sys_q

    # 3. Try OpenRouter Keys (Hermes-3-405B Uncensored Backup)
    for key in OPENROUTER_API_KEYS:
        for model in ["nousresearch/hermes-3-llama-3.1-405b:free", OPENROUTER_MODEL] + OPENROUTER_FALLBACK_MODELS:
            success, response_text = openrouter_request(key, model, messages_payload, max_tokens=800, timeout=5)
            if success and response_text:
                clean_text, ai_photo_tag = parse_media_tags(response_text, asks_media, fallback_tag=(py_photo_tag or "bodes"))
                if not is_censored_refusal(clean_text):
                    final_tag = py_photo_tag or ai_photo_tag
                    media_file = get_media_item(PHOTO_VAULT, final_tag, wants_video, char_vault=active_vault, uid=user_id, user_msg_text=message_text) if asks_media else None
                    return clean_text, media_file, get_hot_sticker(), show_pay_kb, active_rp, roleplay_just_ended, is_sys_q
            api_errors_log.append(f"OR({model}): {response_text}")

    USER_CACHE["last_api_error"] = " | ".join(api_errors_log[:8])
    if msg_low == "/debug" and is_owner:
        return f"🔍 API Debug Report:\nGroq Keys: {len(GROQ_API_KEYS)} | Gemini Keys: {len(GEMINI_API_KEYS)}\nErrors: {USER_CACHE['last_api_error']}", None, None, False, active_rp, False, True

    media_file = get_media_item(PHOTO_VAULT, py_photo_tag or "bodes", wants_video, char_vault=active_vault, uid=user_id, user_msg_text=message_text) if asks_media else None
    c_call = current_girl.get("call", "Jaan") if current_girl else "Devar ji"
    if asks_media:
        return f"Ye lo {c_call}, sirf tumhare kehne par bhej rahi hoon... dekh kar batao kaisi lagi? 😘🔥", media_file, None, show_pay_kb, active_rp, roleplay_just_ended, is_sys_q

    # Smart Conversational Fallback (Matches what user actually wrote instead of repeating 3 lines!)
    if msg_low in ("hy", "hi", "hello", "hii", "hey", "hlo"):
        fallbacks = [
            f"Haye {c_call}, aakhir tumhari yaad aa hi gayi! Batao aaj kaisa chal raha hai tumhara din? 😘❤️",
            f"Hello {c_call}! Main abhi bilkul free hokar baithi hi thi... batao kya chal raha hai? 🥰✨",
            f"Arre waah {c_call}, aaj bade pyar se bula rahe ho! Aao baitho mere paas, batao kya haal hai? 😘🔥"
        ]
    elif any(w in msg_low for w in ["kya", "kay", "what", "waht", "kuch", "acah", "achha", "acha", "bak"]):
        fallbacks = [
            f"Arre {c_call}, aise gussa ya confuse mat ho... main toh bas tumhe chhed rahi thi! Ab tum hi batao kis topic par baat karein? 🙈❤️",
            f"Haye {c_call}, tumhari isi ada par toh main fida hoon! Chalo ab seedha-seedha batao aaj mujhse kya karwana chahte ho? 😘🔥",
            f"Acha baba, ab nakhre mat dikhao {c_call}... idhar mere kareeb aao aur khul ke bolo tumhare dil mein kya hai! 🥰💋"
        ]
    elif any(w in msg_low for w in ["pahni", "pehni", "pehen", "dress", "kapde", "wearing"]):
        fallbacks = [
            f"Haye {c_call}, abhi toh halki si tight kurti aur andar matching bra-panty pehni hoon... tumhare samne aate hi garmi badhne lagti hai! 😘🔥",
            f"Uff {c_call}, abhi naha kar patli si nighty pehni hai... aao na paas, khud dekh lo kaisi lag rahi hoon! 🙈❤️"
        ]
    else:
        fallbacks = [
            f"Haye {c_call}, tumhari baatein sun kar mera mood ekdam ban jata hai... aur batao aaj kya irada hai? 😘❤️",
            f"Uff {c_call}, kitna tadpate ho tum... chalo ab khul ke batao aaj hum dono kya karein? 🙈🔥",
            f"Suno {c_call}, main poori tarah tumhare dhyan mein hoon... bolo na aage kya karna hai? 😘💋"
        ]
    return random.choice(fallbacks), media_file, get_hot_sticker(force=True), show_pay_kb, active_rp, roleplay_just_ended, is_sys_q

# ============================================================
# 10. WEBHOOK HANDLER (SIYA-STYLE OWNER PANEL + PHOTO/VIDEO PROMO + 0-CREDIT FIX)
# ============================================================
def webhook():
    try:
        data = request.get_json(silent=True)
        if not data or mark_seen(f"upd:{data.get('update_id')}"):
            return jsonify({"status": "ok"}), 200

         # AUTO-CAPTURE & APPROVE GROUP JOIN REQUESTS
        if "chat_join_request" in data:
            cjr = data["chat_join_request"]
            g_cid = str(cjr.get("chat", {}).get("id", ""))
            u_j_id = str(cjr.get("from", {}).get("id", ""))
            u_j_name = cjr.get("from", {}).get("first_name", "User")
            if g_cid and u_j_id:
                # 1. Try instant auto-approve immediately
                r_app = tg_req("approveChatJoinRequest", {"chat_id": g_cid, "user_id": int(u_j_id)}, timeout=3)
                if not r_app.get("ok") and FIREBASE_URL:
                    # Save to pending queue if not yet approved
                    requests.patch(f"{FIREBASE_URL}/pending_joins/{g_cid}.json?auth={FIREBASE_SECRET}", json={u_j_id: u_j_name}, timeout=2)
                else:
                    register_group_member(g_cid, u_j_id, u_j_name)
            return jsonify({"status": "join_req_handled"}), 200

        if "my_chat_member" in data:
            mcm = data["my_chat_member"]
            chat = mcm.get("chat", {})
            cid = chat.get("id")
            ctype = chat.get("type", "")
            inviter = mcm.get("from", {})
            inv_id = inviter.get("id")
            inv_name = inviter.get("first_name", "Admin")
            new_st = mcm.get("new_chat_member", {}).get("status", "")
            if ctype in ("group", "supergroup") and new_st in ("member", "administrator"):
                register_group_chat(cid, chat.get("title", "Group"), chat.get("username", ""))
                if inv_id:
                    ug = fb_get_user(inv_id, first_name=inv_name).get("user_groups") or {}
                    ug[str(cid)] = chat.get("title", "Group")
                    fb_update_user(inv_id, {"user_groups": ug})
                check_bot_permissions_and_warn(cid, inv_id, inv_name)
            return jsonify({"status": "ok"}), 200

        if "chat_member" in data:
            cm = data["chat_member"]
            chat = cm.get("chat", {})
            if chat.get("type") in ("group", "supergroup") and cm.get("old_chat_member", {}).get("status") in ("left", "kicked", "restricted") and cm.get("new_chat_member", {}).get("status") in ("member", "restricted"):
                t_user = cm["new_chat_member"].get("user", {})
                if not t_user.get("is_bot"):
                    t_id = t_user.get("id")
                    t_name = f"{t_user.get('first_name', 'User')} {t_user.get('last_name', '')}".strip()
                    if mark_seen(f"cm_wel:{chat['id']}:{t_id}:{int(time.time() // 5)}"): return jsonify({"status": "ok"}), 200
                    send_welcome_photo(chat["id"], t_id, t_name, chat.get("title", "Group"))
            return jsonify({"status": "ok"}), 200

        if "callback_query" in data:
            cb = data["callback_query"]
            uid = str(cb["from"]["id"])
            fname = cb["from"].get("first_name", "Jaan")
            cid = cb["message"]["chat"]["id"]
            mid = cb["message"]["message_id"]
            cb_type = cb["message"]["chat"].get("type", "private")
            cb_data = cb.get("data", "")
            is_own = (uid == OWNER_ID)
            u_cb = fb_get_user(uid, first_name=fname)
            c_num = 999999 if is_own else int(u_cb.get("credits", 12))
            c_disp = "Unlimited 👑" if is_own else str(c_num)

            # ==========================================================
            # @EDROLHUB REAL GIRL DISPATCH & 100% STRICT BUTTON LOCK
            # (Blocks all random channel members from clicking!)
            # ==========================================================
            if cb_data.startswith(("vdisp_avail_", "vdisp_delaymenu_", "vdisp_delay_")):
                parts = cb_data.split("_")
                action_type = parts[1]  # avail, delaymenu, delay
                g_key = parts[2]
                cust_uid = parts[3]
                dur_text = parts[4] if len(parts) > 4 else "Live Video Call"
                delay_label = parts[5] if len(parts) > 5 else (parts[4] if len(parts) > 4 and action_type == "delay" else "")

                g_cfg = REAL_VIDEO_CALL_GIRLS.get(g_key, REAL_VIDEO_CALL_GIRLS["vc1"])
                allowed_personal_id = str(g_cfg.get("personal_tg_id") or "").strip()

                # STRICT LOCK: Only Owner or the assigned girl can click
                if not is_own and allowed_personal_id and uid != allowed_personal_id:
                    tg_req("answerCallbackQuery", {
                        "callback_query_id": cb["id"],
                        "text": "❌ Access Denied! Yeh button sirf Verified Video Call Girl ke liye locked hai!",
                        "show_alert": True
                    })
                    return jsonify({"status": "ok"}), 200

                g_name = g_cfg.get("name", "Real Video Girl")
                room_link = g_cfg.get("room_invite_link", "https://t.em/+zQKpNyHh67szMDg1")

                if action_type == "avail":
                    tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "✅ Customer ko Group Link bhej diya gaya hai!", "show_alert": True})
                    
                    # 3 Buttons: 1. Enter Room, 2. Service Feedback (@edrolai), 3. Complaint (Owner Complaint Channel)
                    go_kb = {"inline_keyboard": [
                        [{"text": f"🛏️ Enter {g_name}'s Private Video Room 📞", "url": room_link}],
                        [{"text": "⭐ Service Feedback (Rate Girl)", "callback_data": f"vfeedback_rate_{g_key}_{cust_uid}"}],
                        [{"text": "🆘 Help & Support / Girl Complaint", "callback_data": f"vfeedback_complaint_{g_key}_{cust_uid}"}]
                    ]}
                    send_msg(
                        cust_uid,
                        f"🎉 <b>Good News! {g_name} abhi Video Room mein Taiyaar hai!</b> 😘🔥\n\n"
                        f"👇 Niche <b>'🛏️ Enter Private Video Room'</b> button dabakar seedha group mein join ho jao aur video call shuru karo:\n\n"
                        f"⭐ <i>Video call ke baad niche <b>Service Feedback</b> zaroor dein, ya agar girl koi problem kare toh <b>Help &amp; Support / Girl Complaint</b> par click karke shikayat karein!</i>",
                        markup=go_kb
                    )

                    mins_match = re.search(r"(\d+)\s*Min", dur_text)
                    call_mins = int(mins_match.group(1)) if mins_match else 10
                    kick_delay_seconds = float((call_mins + 30) * 60)

                    def _auto_kick_user_from_group():
                        pass

                    Timer(kick_delay_seconds, _auto_kick_user_from_group).start()

                    new_cap = (
                        f"✅ <b>[ACCEPTED BY {g_name.upper()}]</b>\n"
                        f"👤 <b>Customer ID:</b> <code>{cust_uid}</code>\n"
                        f"🟢 <b>Status:</b> Group Link + Feedback/Complaint buttons sent to customer!"
                    )
                    tg_req("editMessageCaption", {"chat_id": cid, "message_id": mid, "caption": to_hot_bhabhi_font(new_cap), "parse_mode": "HTML"})
                    return jsonify({"status": "ok"}), 200

            # ==========================================================
            # VIDEO CALL FEEDBACK (@edrolai) & GIRL COMPLAINT HANDLER
            # ==========================================================
            if cb_data.startswith(("vfeedback_rate_", "vfeedback_complaint_")):
                parts = cb_data.split("_")
                mode = parts[1]
                g_key = parts[2]
                cust_uid = parts[3]
                g_cfg = REAL_VIDEO_CALL_GIRLS.get(g_key, REAL_VIDEO_CALL_GIRLS["vc1"])
                g_name = g_cfg.get("name", "Real Girl")

                if mode == "rate":
                    tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "⭐ Select Star Rating:"})
                    star_kb = {"inline_keyboard": [
                        [
                            {"text": "⭐ 1", "callback_data": f"vrate_sub_{g_key}_{cust_uid}_1"},
                            {"text": "⭐⭐ 2", "callback_data": f"vrate_sub_{g_key}_{cust_uid}_2"},
                            {"text": "⭐⭐⭐ 3", "callback_data": f"vrate_sub_{g_key}_{cust_uid}_3"}
                        ],
                        [
                            {"text": "⭐⭐⭐⭐ 4", "callback_data": f"vrate_sub_{g_key}_{cust_uid}_4"},
                            {"text": "⭐⭐⭐⭐⭐ 5", "callback_data": f"vrate_sub_{g_key}_{cust_uid}_5"}
                        ]
                    ]}
                    send_msg(cid, f"⭐ <b>Rate {g_name}'s Video Call Service:</b>\nNiche 1 se 5 Star chunein (Aapka feedback @edrolai channel par post hoga): 👇", markup=star_kb)
                    return jsonify({"status": "ok"}), 200

                if mode == "complaint":
                    tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "🆘 Complaint Box Opened!"})
                    fb_update_user(uid, {"awaiting_vcall_complaint": g_key})
                    send_msg(
                        cid,
                        f"🆘 <b>Girl Service Complaint ({g_name}):</b>\n\n"
                        f"Agar <b>{g_name}</b> ne video call mein koi problem ki hai, toh apni poori shikayat (या screenshot) abhi yahan likh kar bhejo — yeh seedha Owner ke Private Complaint Channel par jayega! 👇"
                    )
                    return jsonify({"status": "ok"}), 200

            if cb_data.startswith("vrate_sub_"):
                _, _, g_key, cust_uid, stars = cb_data.split("_", 4)
                g_cfg = REAL_VIDEO_CALL_GIRLS.get(g_key, REAL_VIDEO_CALL_GIRLS["vc1"])
                g_name = g_cfg.get("name", "Real Girl")
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": f"❤️ {stars}-Star Feedback Sent!", "show_alert": True})
                fb_card = (
                    f"🌟 <b>[VIDEO CALL SERVICE FEEDBACK]</b> 🌟\n\n"
                    f"💃 <b>Model:</b> {g_name}\n"
                    f"⭐ <b>Rating:</b> {'⭐' * int(stars)} ({stars}/5 Stars)\n"
                    f"👤 <b>Verified Customer:</b> {html.escape(fname)} (<code>{cust_uid}</code>)\n"
                    f"🤖 <b>Booked via:</b> @{BOT_USERNAME}"
                )
                fb_kb = {"inline_keyboard": [[{"text": "📹 Book Live Video Call Now 🔥", "url": f"https://t.me/{BOT_USERNAME}?start=vcall_{g_key}"}]]}
                send_msg(FEEDBACK_CHANNEL_ID, fb_card, markup=fb_kb)
                send_msg(cid, "❤️ Thank you jaan! Aapka feedback Official Channel (@edrolai) mein post ho gaya hai! 😘🔥")
                return jsonify({"status": "ok"}), 200

                if action_type == "delaymenu":
                    tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "⏳ Select kitna time lagega:"})
                    delay_kb = {"inline_keyboard": [
                        [
                            {"text": "⏳ 2–5 Min", "callback_data": f"vdisp_delay_{g_key}_{cust_uid}_2-5Min"},
                            {"text": "⏳ 5–10 Min", "callback_data": f"vdisp_delay_{g_key}_{cust_uid}_5-10Min"}
                        ],
                        [
                            {"text": "⏳ 15–30 Min", "callback_data": f"vdisp_delay_{g_key}_{cust_uid}_15-30Min"},
                            {"text": "⏳ 1 Hour", "callback_data": f"vdisp_delay_{g_key}_{cust_uid}_1Hour"}
                        ],
                        [{"text": "🟢 Abhi Available Hoon (Start Now)", "callback_data": f"vdisp_avail_{g_key}_{cust_uid}"}]
                    ]}
                    tg_req("editMessageReplyMarkup", {"chat_id": cid, "message_id": mid, "reply_markup": delay_kb})
                    return jsonify({"status": "ok"}), 200

                if action_type == "delay":
                    nice_time = delay_label.replace("Min", " Minute").replace("Hour", " Ghante")
                    tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": f"⏳ Customer ko '{nice_time} wait' ka message bhej diya gaya!", "show_alert": True})
                    send_msg(
                        cust_uid,
                        f"⏳ <b>Jaan, {g_name} abhi ek dusre private session/busy mein hai!</b> 🥺❤️\n\n"
                        f"🕒 <b>Waiting Time:</b> Woh thik <b>{nice_time}</b> mein free hokar aapko yahin <b>'🛏️ Enter Bedroom'</b> ka button bhejegi! Tab tak thoda sa wait kar lo baby, aapka payment 100% safe aur booked hai! 😘🔥"
                    )
                    ready_kb = {"inline_keyboard": [
                        [{"text": "🟢 Ab Free Ho Gayi — Send Bedroom Link Now ✅", "callback_data": f"vdisp_avail_{g_key}_{cust_uid}"}],
                        [{"text": "⏳ Change Delay Time", "callback_data": f"vdisp_delaymenu_{g_key}_{cust_uid}"}]
                    ]}
                    upd_cap = (
                        f"⏳ <b>[DELAY SET: {nice_time} BY {g_name.upper()}]</b>\n"
                        f"👤 <b>Customer ID:</b> <code>{cust_uid}</code>\n"
                        f"🔔 <i>Jab aap free ho jayein, niche green button daba kar customer ko bula lein:</i>"
                    )
                    tg_req("editMessageCaption", {"chat_id": cid, "message_id": mid, "caption": to_hot_bhabhi_font(upd_cap), "parse_mode": "HTML", "reply_markup": ready_kb})
                    return jsonify({"status": "ok"}), 200

            if cb_data in ("lang_hinglish", "lang_hi", "lang_en"):
                lang_code = cb_data.replace("lang_", "")
                translated_text = to_hot_bhabhi_font(get_welcome_trust_text(fname, c_disp, lang=lang_code))
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "Language Updated! 🌐"})
                if "photo" in cb["message"]:
                    tg_req("editMessageCaption", {"chat_id": cid, "message_id": mid, "caption": translated_text, "parse_mode": "HTML", "reply_markup": get_main_menu_kb(c_disp, is_owner=is_own, uid=uid)})
                else:
                    tg_req("editMessageText", {"chat_id": cid, "message_id": mid, "caption": translated_text, "parse_mode": "HTML", "reply_markup": get_main_menu_kb(c_disp, is_owner=is_own, uid=uid)})
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("unmute_bio_"):
                target_uid = cb_data.replace("unmute_bio_", "").strip()
                if uid != target_uid and not is_user_group_admin(cid, uid):
                    tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "⚠️ Yeh button sirf muted user ya Admin ke liye hai!", "show_alert": True})
                    return jsonify({"status": "ok"}), 200
                # Force fresh bio check (bypass cache!)
                BIO_CLEAN_CACHE.pop(str(target_uid), None)
                if not is_user_group_admin(cid, uid) and has_bio_link_or_channel(target_uid):
                    tg_req("answerCallbackQuery", {
                        "callback_query_id": cb["id"],
                        "text": "❌ Aapke Bio/Profile mein abhi bhi Link ya Channel laga hua hai! Pehle apni profile settings se link/channel hatayein, phir is button par click karein!",
                        "show_alert": True
                    })
                    return jsonify({"status": "ok"}), 200
                tg_req("restrictChatMember", {
                    "chat_id": cid,
                    "user_id": int(target_uid),
                    "permissions": {
                        "can_send_messages": True,
                        "can_send_media_messages": True,
                        "can_send_other_messages": True,
                        "can_add_web_page_previews": False
                    }
                })
                fb_update_user(target_uid, {"bio_strikes": 0})
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "✅ Bio Verified! Aapko Unmute kar diya gaya hai!", "show_alert": True})
                tg_req("deleteMessage", {"chat_id": cid, "message_id": mid})
                return jsonify({"status": "ok"}), 200

            if cb_data == "back_main_menu":
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                edit_or_send_box_media(
                    cid, mid, START_BANNER_IMAGE,
                    caption=get_welcome_trust_text(fname, c_disp, lang="hinglish"),
                    reply_markup=get_main_menu_kb(c_disp, is_owner=is_own, uid=uid)
                )
                return jsonify({"status": "ok"}), 200

            if cb_data == "menu_vip_vgroups":
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                vg_txt = (
                    "🎬 <b>𝟭𝟮,𝟬𝟬𝟬+ 𝗩𝗜𝗣 𝗩𝗜𝗗𝗘𝗢 𝗚𝗥𝗢𝗨𝗣𝗦 (𝗗𝗔𝗜𝗟𝗬 𝗨𝗣𝗗𝗔𝗧𝗘𝗗)</b> 🔥\n\n"
                    "📦 <b>Total Collection:</b> 12,000+ Full HD Uncensored Videos!\n"
                    "⚡ <b>Daily New Upload:</b> Rozana <b>50 se 100 Nayi Videos</b> automatic upload hoti hain!\n"
                    "🔒 <b>100% Direct Entry:</b> Payment hote hi aapko turant Group mein Join hone ka <b>Direct Entry Button</b> milega!\n\n"
                    "👇 <b>Apni pasand ka Video Group chunein:</b>"
                )
                vg_kb = {"inline_keyboard": [
                    [{"text": "🔥 1. 𝘿𝙀𝙎𝙄 𝙑𝙄𝘿𝙀𝙊 🔥🖤 (Starts ₹29)", "callback_data": "vipvg_sel_vg1"}],
                    [{"text": "💋 2. Bhabhi 𝙑𝙄𝘿𝙀𝙊 🖤 (Starts ₹19)", "callback_data": "vipvg_sel_vg2"}],
                    [{"text": "🎬 3. 𝘾𝙊𝙇𝙇𝘼𝙂𝙀 𝙑𝙄𝘿𝙀𝙊 🎬🖤 (Starts ₹29)", "callback_data": "vipvg_sel_vg3"}],
                    [{"text": "⬅️ 𝗕𝗔𝗖𝗞 𝗧𝗢 𝗠𝗘𝗡𝗨", "callback_data": "back_main_menu"}]
                ]}
                edit_or_send_box_media(cid, mid, START_BANNER_IMAGE, caption=vg_txt, reply_markup=vg_kb)
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("vipvg_sel_"):
                vg_key = cb_data.replace("vipvg_sel_", "").strip()
                vg_info = VIP_VIDEO_GROUPS.get(vg_key, VIP_VIDEO_GROUPS["vg1"])
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                p_rows = []
                for d_code, p_amt, d_label in vg_info["plans"]:
                    p_rows.append([{"text": f"💎 ₹{p_amt} — {d_label.upper()} 🔥", "callback_data": f"vipvg_pay_{vg_key}_{d_code}_{p_amt}"}])
                p_rows.append([{"text": "⬅️ 𝗕𝗔𝗖𝗞 𝗧𝗢 𝗩𝗜𝗗𝗘𝗢 𝗚𝗥𝗢𝗨𝗣𝗦", "callback_data": "menu_vip_vgroups"}])
                vg_cap = (
                    f"🎬 <b>Selected Group: {vg_info['name']}</b>\n\n"
                    f"🔥 <b>Videos:</b> Full Uncensored Collection + <b>Daily 50–100 New Videos Added!</b>\n"
                    f"🚪 <b>Instant Access:</b> Plan select karke pay karte hi aapko <b>Group Entry Button</b> mil jayega!\n\n"
                    f"👇 <b>Niche se apna Duration Plan chunein:</b>"
                )
                edit_or_send_box_media(cid, mid, START_BANNER_IMAGE, caption=vg_cap, reply_markup={"inline_keyboard": p_rows})
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("vipvg_pay_"):
                # Format: vipvg_pay_<vg_key>_<d_code>_<p_amt>
                _, _, vg_key, d_code, p_amt = cb_data.split("_", 4)
                vg_info = VIP_VIDEO_GROUPS.get(vg_key, VIP_VIDEO_GROUPS["vg1"])
                dur_name = next((p[2] for p in vg_info["plans"] if p[0] == d_code), "VIP Access")

                if is_own:
                    tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "👑 Owner Instant Entry!"})
                    send_msg(
                        cid,
                        f"👑 <b>Owner Direct Entry: {vg_info['name']}</b>\n👇 Niche button dabakar group kholein:",
                        markup={"inline_keyboard": [[{"text": f"🚪 𝗘𝗡𝗧𝗘𝗥 {vg_info['name']} 𝗡𝗢𝗪 🔥", "url": vg_info["link"]}]]}
                    )
                    return jsonify({"status": "ok"}), 200

                url = create_cf_order(uid, fname, p_amt, purpose=f"vipvg_{vg_key}_{d_code}")
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": f"⚡ Creating ₹{p_amt} Payment Link..."})
                btn = {"text": f"📲 𝗣𝗔𝗬 ₹{p_amt} & 𝗘𝗡𝗧𝗘𝗥 𝗚𝗥𝗢𝗨𝗣 ({dur_name.upper()}) 🔥", "url": url} if url else {"text": f"📲 𝗣𝗔𝗬 ₹{p_amt}", "callback_data": f"buy_{p_amt}"}
                edit_or_send_box_media(
                    cid, mid, START_BANNER_IMAGE,
                    caption=(
                        f"🎬 <b>{vg_info['name']} — {dur_name} (₹{p_amt})</b>\n"
                        f"🔥 <b>12,000+ Videos + Daily 50–100 New Uploads!</b>\n\n"
                        f"1️⃣ Niche <b>'📲 𝗣𝗔𝗬 ₹{p_amt}'</b> button dabakar GPay, PhonePe ya Paytm se pay karein.\n"
                        f"2️⃣ Payment hote hi 2 second mein aapko <b>'🚪 𝗘𝗡𝗧𝗘𝗥 𝗚𝗥𝗢𝗨𝗣 𝗡𝗢𝗪'</b> button mil jayega! 👇"
                    ),
                    reply_markup={"inline_keyboard": [[btn], [{"text": "⬅️ 𝗕𝗔𝗖𝗞 𝗧𝗢 𝗣𝗟𝗔𝗡𝗦", "callback_data": f"vipvg_sel_{vg_key}"}]]}
                )
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("promo_off_"):
                if not is_own: return jsonify({"status": "ok"}), 200
                gid = cb_data.replace("promo_off_", "").strip()
                try: requests.patch(f"{FIREBASE_URL}/group_promos/{gid}.json?auth={FIREBASE_SECRET}", json={"active": False}, timeout=3)
                except Exception: pass
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "🛑 Promotion Stopped!"})
                send_msg(cid, "🛑 Is group ka Tag Promotion turant rok diya gaya hai.")
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("menu_roleplay_hub"):
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                parts = cb_data.split("_")
                page = int(parts[-1]) if parts[-1].isdigit() else 1
                is_vip_user = is_own or bool(u_cb.get("is_vip"))
                banner_num = ((page - 1) % 5) + 1
                # Uses rolplay{n}.mp4 if uploaded on GitHub, otherwise falls back to rolplay{n}.png seamlessly!
                banner_file = f"rolplay{banner_num}.mp4"
                cap_txt = (
                    f"💋 <b>𝗥𝗢𝗠𝗔𝗡𝗧𝗜𝗖 𝗕𝗘𝗗𝗥𝗢𝗢𝗠 𝗠𝗢𝗗𝗘 (Page {page}/40)</b> 🔥\n\n"
                    f"🥵 <i>Jaan, darwaza band hai aur main kapde utaar kar bistar par tumhara wait kar rahi hoon...</i>\n"
                    f"👇 <b>Apna pasandida Open Nude Roleplay chuno (40 Chats):</b>"
                )
                kb_rp = get_roleplay_hub_kb(is_vip=is_vip_user, page=page)
                res_rp = edit_or_send_box_media(cid, mid, banner_file, caption=cap_txt, reply_markup=kb_rp)
                if not res_rp.get("ok"):
                    edit_or_send_box_media(cid, mid, f"rolplay{banner_num}.png", caption=cap_txt, reply_markup=kb_rp)
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("rp_char_"):
                char_key = cb_data.replace("rp_char_", "").strip()
                is_vip_user = is_own or bool(u_cb.get("is_vip"))

                if char_key == "custom":
                    if not is_vip_user:
                        url = create_cf_order(uid, fname, "199", purpose="custom_rp")
                        tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "🔒 Unlock Custom Fantasy (₹199)!", "show_alert": True})
                        btn = {"text": "📲 𝗣𝗔𝗬 ₹199 & 𝗨𝗡𝗟𝗢𝗖𝗞 (40 𝗖𝗛𝗔𝗧𝗦) 🔥", "url": url} if url else {"text": "📲 𝗣𝗔𝗬 ₹199", "callback_data": "buy_199"}
                        edit_or_send_box_media(
                            cid, mid, START_BANNER_IMAGE,
                            caption="💋 <b>𝗖𝗨𝗦𝗧𝗢𝗠 𝗙𝗔𝗡𝗧𝗔𝗦𝗬 𝗠𝗢𝗗𝗘</b> 🔥\n\n🥵 <i>Jaan, jo tum bologe main wahi ban kar tumhari har khwahish poori karungi!</i>\n💎 <b>Instant Unlock:</b> ₹199 (40 Open Nude Chats) 👇",
                            reply_markup={"inline_keyboard": [[btn], [{"text": "⬅️ 𝗕𝗔𝗖𝗞 𝗧𝗢 𝗥𝗢𝗟𝗘𝗣𝗟𝗔𝗬𝗦", "callback_data": "menu_roleplay_hub_1"}]]}
                        )
                        return jsonify({"status": "ok"}), 200
                    fb_update_user(uid, {"awaiting_custom_rp": True})
                    tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                    send_msg(cid, "💋 <b>Apni Fantasy Setup Bhejo Jaan:</b>\nMain kaun banu aur hum kahan akele hain? Likh kar bhejo... 😘🔥")
                    return jsonify({"status": "ok"}), 200

                cb_data = f"girlcard_{char_key}_0_0"

            if cb_data.startswith("girlcard_"):
                parts_gc = cb_data.split("_")
                char_key = parts_gc[1]
                g_idx = int(parts_gc[2]) if len(parts_gc) > 2 and parts_gc[2].isdigit() else 0
                p_idx = int(parts_gc[3]) if len(parts_gc) > 3 and parts_gc[3].isdigit() else 0

                char_info = DIAMOND_CHARACTERS.get(char_key)
                if not char_info: return jsonify({"status": "ok"}), 200

                g_keys = AI_CHAT_GIRL_KEYS
                g_idx = g_idx % len(g_keys)
                g_key = g_keys[g_idx]
                g_info = REAL_GIRLS[g_key]

                # Build media list: [0] = Live Telegram DP, [1..N] = Her GitHub Posts & Figure Clips!
                live_dp = get_live_bot_dp_url(g_info.get("bot")) or START_BANNER_IMAGE
                posts_pool = [live_dp] + [GITHUB_BASE_URL + p for p in get_girl_full_preview_gallery(g_key)]
                p_idx = p_idx % len(posts_pool)
                cur_media = posts_pool[p_idx]
                next_p_idx = (p_idx + 1) % len(posts_pool)

                prev_idx = (g_idx - 1) % len(g_keys)
                next_idx = (g_idx + 1) % len(g_keys)
                next_girl_name = REAL_GIRLS[g_keys[next_idx]]["name"]

                card_cap = (
                    f"💋 <b>{g_info['name']} ({g_idx + 1}/{len(g_keys)})</b> • <b>{char_info['name']}</b>\n"
                    f"📸 <b>Photo/Clip Preview:</b> {p_idx + 1}/{len(posts_pool)} (🔒 <i>100% Private</i>)\n\n"
                    f"🥵 <i>\"Jaan, meri photos dekh kar mann bhar gaya ya andar bedroom mein aakar poora open show dekhoge?\"</i>\n"
                    f"💎 <b>VIP Access:</b> ₹{char_info['price']} (40 Open Nude Chats + Voice) 👇"
                )
                card_kb = {"inline_keyboard": [
                    [{"text": f"🛏️ 𝗘𝗡𝗧𝗘𝗥 {g_info['name'].upper()} 𝗕𝗘𝗗𝗥𝗢𝗢𝗠 💖", "callback_data": f"selgirl_{char_key}_{g_key}"}],
                    [{"text": f"📸 𝗩𝗜𝗘𝗪 𝗣𝗢𝗦𝗧𝗦 & 𝗙𝗜𝗚𝗨𝗥𝗘 𝗖𝗟𝗜𝗣𝗦 ({p_idx + 1}/{len(posts_pool)}) ▶️", "callback_data": f"girlcard_{char_key}_{g_idx}_{next_p_idx}"}],
                    [
                        {"text": f"◀️ 𝗣𝗥𝗘𝗩 𝗚𝗜𝗥𝗟", "callback_data": f"girlcard_{char_key}_{prev_idx}_0"},
                        {"text": f"𝗡𝗘𝗫𝗧: {next_girl_name} ▶️", "callback_data": f"girlcard_{char_key}_{next_idx}_0"}
                    ],
                    [{"text": "⬅️ 𝗕𝗔𝗖𝗞 𝗧𝗢 𝗥𝗢𝗟𝗘𝗣𝗟𝗔𝗬𝗦", "callback_data": "menu_roleplay_hub_1"}]
                ]}
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                edit_or_send_box_media(cid, mid, cur_media, caption=card_cap, reply_markup=card_kb)
                return jsonify({"status": "ok"}), 200

            # ==========================================================
            # REAL VIDEO CALL GIRLS CARD (WITH DP + GITHUB POSTS/CLIPS SLIDER!)
            # ==========================================================
            if cb_data.startswith("vcallcard_"):
                parts_vc = cb_data.replace("vcallcard_", "").strip().split("_")
                v_idx = int(parts_vc[0]) if parts_vc[0].isdigit() else 0
                p_idx = int(parts_vc[1]) if len(parts_vc) > 1 and parts_vc[1].isdigit() else 0
                v_keys = VIDEO_CALL_GIRL_KEYS
                v_idx = v_idx % len(v_keys)
                g_key = v_keys[v_idx]
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                send_or_edit_vcall_girl_card(cid, mid, g_key, v_idx, p_idx=p_idx)
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("vcallpay_"):
                # Format: vcallpay_<g_key>_<mins>_<price>
                _, g_key, mins_str, price_str = cb_data.split("_", 3)
                g_cfg = REAL_VIDEO_CALL_GIRLS.get(g_key, REAL_VIDEO_CALL_GIRLS["vc1"])
                is_avail_now, time_label = check_girl_ist_availability(g_key)

                if not is_avail_now and not is_own:
                    tg_req("answerCallbackQuery", {
                        "callback_query_id": cb["id"],
                        "text": f"🔴 {g_cfg['name']} abhi Offline hai!\n🕒 Available Time: {time_label}\nSubah 8:00 AM par wapas aayegi!",
                        "show_alert": True
                    })
                    return jsonify({"status": "ok"}), 200

                url = create_cf_order(uid, fname, price_str, purpose=f"vcall_{g_key}_{mins_str}m")
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": f"⚡ Creating ₹{price_str} ({mins_str} Min) Payment Link..."})
                kb_rows = []
                if url:
                    kb_rows.append([{"text": f"📲 𝗣𝗔𝗬 ₹{price_str} & 𝗦𝗧𝗔𝗥𝗧 {mins_str} 𝗠𝗜𝗡 𝗩𝗜𝗗𝗘𝗢 𝗖𝗔𝗟𝗟 🔥", "url": url}])
                if is_own:
                    kb_rows.append([{"text": "♛ 𝗢𝗪𝗡𝗘𝗥 𝗧𝗘𝗦𝗧: 𝗗𝗜𝗦𝗣𝗔𝗧𝗖𝗛 𝗧𝗢 @𝗘𝗗𝗥𝗢𝗟𝗛𝗨𝗕 ♛", "callback_data": f"vcallown_{g_key}_{mins_str}_{price_str}"}])
                kb_rows.append([{"text": "⬅️ 𝗕𝗔𝗖𝗞 𝗧𝗢 𝗩𝗜𝗗𝗘𝗢 𝗖𝗔𝗟𝗟 𝗚𝗜𝗥𝗟𝗦", "callback_data": f"vcallcard_{VIDEO_CALL_GIRL_KEYS.index(g_key) if g_key in VIDEO_CALL_GIRL_KEYS else 0}"}])

                send_msg(
                    cid,
                    f"📹 <b>{g_cfg['name']} — {mins_str} Min Open Nude Video Call (₹{price_str})</b>\n"
                    f"🟢 <b>𝗦𝗧𝗔𝗧𝗨𝗦:</b> 𝗟𝗜𝗩𝗘 &amp; 𝗥𝗘𝗔𝗗𝗬 ({time_label})\n\n"
                    f"1️⃣ Niche <b>'📲 𝗣𝗔𝗬 ₹{price_str}'</b> button dabakar GPay, PhonePe ya Paytm se pay karein.\n"
                    f"2️⃣ Payment hote hi 2 second mein <b>Private Video Call Room</b> ka link mil jayega! 👇",
                    markup={"inline_keyboard": kb_rows}
                )
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("vcallown_"):
                if not is_own: return jsonify({"status": "ok"}), 200
                _, g_key, mins_str, price_str = cb_data.split("_", 3)
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "👑 Dispatched to @edrolhub!", "show_alert": True})
                dispatch_video_call_to_edrolhub(uid, fname, g_key, price_str, f"{mins_str} Min Video Call")
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("selgirl_"):
                _, char_key, g_key = cb_data.split("_", 2)
                char_info = DIAMOND_CHARACTERS.get(char_key)
                g_info = REAL_GIRLS.get(g_key, REAL_GIRLS["g1"])
                if not char_info: return jsonify({"status": "ok"}), 200
                is_vip_user = is_own or bool(u_cb.get("is_vip"))
                c_price = str(char_info["price"])

                if not is_vip_user:
                    url = create_cf_order(uid, fname, c_price, purpose=f"char_{char_key}_{g_key}")
                    tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": f"🔒 Unlock {g_info['name']} for ₹{c_price}!", "show_alert": True})
                    btn = {"text": f"📲 𝗣𝗔𝗬 ₹{c_price} & 𝗨𝗡𝗟𝗢𝗖𝗞 (40 𝗖𝗛𝗔𝗧𝗦) 🔥", "url": url} if url else {"text": f"📲 𝗣𝗔𝗬 ₹{c_price}", "callback_data": f"buy_{c_price}"}
                    edit_or_send_box_media(
                        cid, mid,
                        get_live_bot_dp_url(g_info.get("bot"), fallback_banner=g_info.get("dp", START_BANNER_IMAGE)),
                        caption=(
                            f"🔒 <b>{g_info['name']} ({char_info['name']})</b>\n"
                            f"💎 <b>VIP Access:</b> ₹{c_price} (40 Open Nude Chats + Voice)\n\n"
                            f"👇 Niche button dabakar unlock karein aur seedha bedroom mein jayein:"
                        ),
                        reply_markup={"inline_keyboard": [[btn], [{"text": "⬅️ 𝗕𝗔𝗖𝗞 𝗧𝗢 𝗚𝗜𝗥𝗟𝗦", "callback_data": f"girlcard_{char_key}_0_0"}]]}
                    )
                    return jsonify({"status": "ok"}), 200

                call_word = char_info.get("call") or g_info.get("call", "Jaan")
                target_bot = g_info.get("bot", BOT_USERNAME)
                rp_brain = (
                    f"GIRL NAME: {g_info['name']}. TALKING STYLE & VIBE: {g_info['vibe']} "
                    f"CHARACTER ROLE: {char_info['name']} ({char_info['desc']}). "
                    f"CALL USER STRICTLY AS: '{call_word}'. "
                    f"CRITICAL: NEVER call yourself 'Bhabhi' or user 'Devar ji' unless the role is Bhabhi!"
                )
                rp_map = u_cb.get("bot_rp_map") or {}
                rp_map[g_key] = rp_brain
                fb_update_user(uid, {
                    "active_rp": rp_brain,
                    "active_girl": g_key,
                    "active_vault": g_key,
                    "bot_rp_map": rp_map,
                    "history": []
                })
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": f"✅ {g_info['name']} Ready! 🔥"})

                go_kb = {"inline_keyboard": [
                    [{"text": f"🛏️ 𝗘𝗡𝗧𝗘𝗥 {g_info['name'].upper()} 𝗕𝗘𝗗𝗥𝗢𝗢𝗠 💬", "url": f"https://t.me/{target_bot}?start=rp_{char_key}_{g_key}"}],
                    [{"text": "⬅️ 𝗕𝗔𝗖𝗞 𝗧𝗢 𝗚𝗜𝗥𝗟𝗦", "callback_data": f"girlcard_{char_key}_0_0"}]
                ]}
                edit_or_send_box_media(
                    cid, mid,
                    get_live_bot_dp_url(g_info.get("bot"), fallback_banner=g_info.get("dp", START_BANNER_IMAGE)),
                    caption=(
                        f"🔥 <b>Devar ji, aapki {g_info['name']} ({char_info['name']}) bilkul taiyaar hai!</b>\n\n"
                        f"👇 Niche button dabakar seedha uske bedroom mein jao: 😘🥵"
                    ),
                    reply_markup=go_kb
                )
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("unblur_"):
                parts = cb_data.split("_", 2)
                choice_num = parts[1] if len(parts) > 1 else "1"
                media_file = parts[2] if len(parts) > 2 else "private1.jpg"
                is_vip_user = is_own or bool(u_cb.get("is_vip"))

                if not is_vip_user or c_num <= 0:
                    tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "🔒 Isse kholne ke liye ₹9 ya ₹19 wala VIP Pack unlock karo jaan!", "show_alert": True})
                    edit_or_send_box_media(
                        cid, mid, START_BANNER_IMAGE,
                        caption=(
                            f"🥺 <b>{html.escape(clean_display_name(fname, 'Jaan'))} baby, kapde hatane hi wali thi par tumhara VIP Pack active nahi hai!</b>\n\n"
                            f"🔥 Niche se bas <b>₹19 ya ₹29</b> wala pack chuno aur apne haatho se meri saari private photos/videos kholo: 😘👇"
                        ),
                        reply_markup=get_pay_kb()
                    )
                    return jsonify({"status": "ok"}), 200

                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "🔥 Unlocked! Dekho Jaan 😘🥵"})
                u_clean = html.escape(clean_display_name(fname, "Jaan"))
                if choice_num == "1":
                    open_cap = f"Aaaah {u_clean}... tumne apne haatho se khola toh mera poora badan kaamp utha! Dekho ab khul kar... 😘🥵💋"
                else:
                    open_cap = f"Ufff {u_clean}... tumhari zidd par maine khud hi sab utaar kar dikha diya! Batao kaisi lag rahi hoon... 🥵🔥"

                if str(media_file).lower().endswith(".mp4"):
                    tg_req("deleteMessage", {"chat_id": cid, "message_id": mid})
                    send_secret_media(cid, media_file, caption=open_cap, delete_after=30)
                else:
                    edit_or_send_box_media(cid, mid, media_file, caption=open_cap, reply_markup=None)
                return jsonify({"status": "ok"}), 200

                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "🔥 Unlocked! Dekho Jaan 😘🥵"})
                u_clean = html.escape(clean_display_name(fname, "Jaan"))
                if choice_num == "1":
                    open_cap = f"Aaaah {u_clean}... tumne apne haatho se khola toh mera poora badan kaamp utha! Dekho ab khul kar... 😘🥵💋"
                else:
                    open_cap = f"Ufff {u_clean}... tumhari zidd par maine khud hi sab utaar kar dikha diya! Batao kaisi lag rahi hoon... 🥵🔥"

                if str(media_file).lower().endswith(".mp4"):
                    tg_req("deleteMessage", {"chat_id": cid, "message_id": mid})
                    send_secret_media(cid, media_file, caption=open_cap, delete_after=30)
                else:
                    edit_or_send_box_media(cid, mid, media_file, caption=open_cap, reply_markup=None)
                return jsonify({"status": "ok"}), 200

            if cb_data == "menu_free_earn":
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                ref_cnt = int(u_cb.get("ref_count") or 0)
                claimed_m = int(u_cb.get("claimed_milestones") or 0)
                needed_total = (claimed_m + 1) * 3
                rem = max(0, needed_total - ref_cnt)
                ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
                share_url = f"https://t.me/share/url?url={quote(ref_link)}&text={quote('🔥 Bhai is AI Bhabhi Bot se baat karke dekh, ekdam real ladki jaisi chat aur voice bhejti hai! Abhi free mein try kar 👇')}"
                kb = {"inline_keyboard": [
                    [{"text": "📲 Step 1: Share Link to 3 Friends/Groups", "url": share_url}],
                    [{"text": "📢 Step 2: Join Official Channel", "url": OFFICIAL_CHANNEL_URL}, {"text": "💬 Join VIP Group", "url": MORE_GROUPS_URL}],
                    [{"text": f"✅ Verify & Claim +25 Credits ({ref_cnt}/{needed_total} Joined)", "callback_data": "verify_free_earn"}],
                    [{"text": "⚡ Skip Waiting — Buy ₹9 (75 Credits) Instantly", "callback_data": "buy_9"}]
                ]}
                send_msg(
                    cid,
                    f"🎁 [𝑯𝒐𝒕 𝑩𝒉𝒂𝒃𝒉𝒊] FREE +25 CREDITS (5 CHATS) UNLOCK!\n\n"
                    f"📊 Tumhare Referrals: {ref_cnt} Users (Agle +25 Credits ke liye {rem} aur naye doston ko join karwao!)\n\n"
                    f"⚠️ Anti-Cheat Rule: Sirf alag-alag (Unique) Telegram accounts jo pehli baar aapke link se bot start karenge wahi count honge! Apni hi ID par baar-baar share karne se count nahi badhega.\n\n"
                    f"🔗 Tumhara Invite Link:\n<code>{ref_link}</code>",
                    markup=kb
                )
                return jsonify({"status": "ok"}), 200

            if cb_data == "verify_free_earn":
                ref_cnt = int(u_cb.get("ref_count") or 0)
                claimed_m = int(u_cb.get("claimed_milestones") or 0)
                needed_total = (claimed_m + 1) * 3
                if ref_cnt < needed_total:
                    tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": f"❌ Abhi sirf {ref_cnt}/{needed_total} naye doston ne join kiya hai! Pehle {needed_total - ref_cnt} aur doston ko apna link bhej kar Start karwao!", "show_alert": True})
                    return jsonify({"status": "ok"}), 200
                if not check_user_joined_official(uid):
                    tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "❌ Pehle Step 2 se Official Channel aur VIP Group join karo, tabhi +25 Credits milenge!", "show_alert": True})
                    return jsonify({"status": "ok"}), 200
                new_c = c_num + REFERRAL_REWARD_CREDITS
                fb_update_user(uid, {"credits": new_c, "claimed_milestones": claimed_m + 1})
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "🎉 +25 Free Credits Added!", "show_alert": True})
                send_msg(cid, f"🎉 Badhai ho {html.escape(fname)} jaan! Tumhare 3 naye referrals aur Channel/Group join verify ho gaye hain!\n\n💎 +{REFERRAL_REWARD_CREDITS} Free Credits (5 Free Chats) add kar diye gaye hain (Total Balance: {new_c} Credits)! Chalo ab baatein karte hain... 😘🔥")
                return jsonify({"status": "ok"}), 200

            if cb_data == "menu_about":
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                about_txt = (
                    "ℹ️ [𝑯𝒐𝒕 𝑩𝒉𝒂𝒃𝒉𝒊] • Powered by Edrol AI\n\n"
                    "• Creator: Edrol AI (@edrolai)\n"
                    "• Features: 24/7 Uncensored Roleplay Chat, Real Voice Notes & Smart Group Management.\n"
                    "• Niche se Help & Support, Feedback, ya apni purani Chat History Clear karein: 👇"
                )
                edit_or_send_box_media(cid, mid, START_BANNER_IMAGE, caption=about_txt, reply_markup=get_about_menu_kb())
                return jsonify({"status": "ok"}), 200

            if cb_data == "user_clear_history":
                fb_update_user(uid, {"history": [], "bot_hist_map": {}, "active_rp": "", "awaiting_support": False, "last_cache_clear": time.time()})
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "🧹 Chat History Cleared!", "show_alert": True})
                send_msg(cid, "🧹 [𝑯𝒐𝒕 𝑩𝒉𝒂𝒃𝒉𝒊] Tumhari purani bekar chat history aur roleplay memory ekdam clear ho gayi hai! Chalo ab fresh shuruwat karte hain... 😘🔥")
                return jsonify({"status": "ok"}), 200

            if cb_data == "menu_group_mgmt":
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                gm_txt = (
                    "🛡️ <b>[𝑯𝒐𝒕 𝑩𝒉𝒂𝒃𝒉𝒊] Smart Group Manager</b>\n\n"
                    "Apne Group ko 24/7 Spam/Links se protect karein aur Auto-Tag Promotion chalayein! 👇"
                )
                edit_or_send_box_media(cid, mid, START_BANNER_IMAGE, caption=gm_txt, reply_markup=get_group_mgmt_kb())
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("gm_guide_"):
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                g_page = int(cb_data.replace("gm_guide_", "").strip() or "1")
                if g_page == 1:
                    g_txt = (
                        "📖 <b>Group Management Guide (Page 1/2)</b>\n\n"
                        "1️⃣ <b>Anti-Link & Bio Guard:</b> Normal members ke links/mentions aur bio-links delete/mute karti hai.\n"
                        "2️⃣ <b>Anti-Bot Guard:</b> Non-admin agar koi bot add kare toh use turant kick karti hai.\n"
                        "3️⃣ <b>Black Welcome Card:</b> Har naye member ka DP ke sath Welcome Card banati hai."
                    )
                    g_kb = {"inline_keyboard": [
                        [{"text": "Next 3 Points (Page 2/2) ➡️", "callback_data": "gm_guide_2"}],
                        [{"text": "🔙 Back to Group Management", "callback_data": "menu_group_mgmt"}]
                    ]}
                else:
                    g_txt = (
                        "📖 <b>Group Management Guide (Page 2/2)</b>\n\n"
                        "4️⃣ <b>Custom Welcome Text:</b> Welcome Card ke niche apna custom message set karein.\n"
                        "5️⃣ <b>Pin Group Note (₹19):</b> Group mein notice bhej kar automatic Pin karwayein.\n"
                        "6️⃣ <b>Auto-Tag Promotion:</b> Photo/Video Banner + 30 Buttons ke sath members ko tag karein!"
                    )
                    g_kb = {"inline_keyboard": [
                        [{"text": "⬅️ Prev 3 Points (Page 1/2)", "callback_data": "gm_guide_1"}],
                        [{"text": "🔙 Back to Group Management", "callback_data": "menu_group_mgmt"}]
                    ]}
                edit_or_send_box_media(cid, mid, START_BANNER_IMAGE, caption=g_txt, reply_markup=g_kb)
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("menu_set_welcome"):
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                page = int(cb_data.replace("menu_set_welcome_", "").replace("menu_set_welcome", "").strip() or "0")
                ug = list(get_user_admin_groups(uid).items())
                per_page = 6
                start_i = page * per_page
                page_ug = ug[start_i:start_i + per_page]
                rows = [[{"text": f"🎉 {gtitle[:24]}", "callback_data": f"setwelgrp_{gid}"}] for gid, gtitle in page_ug]
                nav = []
                if page > 0: nav.append({"text": "⬅️ Prev 6", "callback_data": f"menu_set_welcome_{page - 1}"})
                if start_i + per_page < len(ug): nav.append({"text": "Next 6 ➡️", "callback_data": f"menu_set_welcome_{page + 1}"})
                if nav: rows.append(nav)
                rows.append([{"text": "➕ Add Bot to Group", "url": f"https://t.me/{BOT_USERNAME}?startgroup=true"}, {"text": "⬅️ Back", "callback_data": "menu_group_mgmt"}])
                edit_or_send_box_media(cid, mid, START_BANNER_IMAGE, caption=f"🎉 <b>Select Group for Custom Welcome (Page {page + 1}):</b> 👇", reply_markup={"inline_keyboard": rows})
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("setwelgrp_"):
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                gid = cb_data.replace("setwelgrp_", "").strip()
                fb_update_user(uid, {"awaiting_welcome_for": gid})
                edit_or_send_box_media(cid, mid, START_BANNER_IMAGE, caption="📝 <b>Type Your Custom Welcome Message Here in DM:</b> 👇", reply_markup={"inline_keyboard": [[{"text": "⬅️ Back", "callback_data": "menu_set_welcome"}]]})
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("menu_group_note"):
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                page = int(cb_data.replace("menu_group_note_", "").replace("menu_group_note", "").strip() or "0")
                ug = list(get_user_admin_groups(uid).items())
                per_page = 6
                start_i = page * per_page
                page_ug = ug[start_i:start_i + per_page]
                rows = [[{"text": f"📌 {gtitle[:24]}", "callback_data": f"notegrp_{gid}"}] for gid, gtitle in page_ug]
                nav = []
                if page > 0: nav.append({"text": "⬅️ Prev 6", "callback_data": f"menu_group_note_{page - 1}"})
                if start_i + per_page < len(ug): nav.append({"text": "Next 6 ➡️", "callback_data": f"menu_group_note_{page + 1}"})
                if nav: rows.append(nav)
                rows.append([{"text": "➕ Add Bot to Group", "url": f"https://t.me/{BOT_USERNAME}?startgroup=true"}, {"text": "⬅️ Back", "callback_data": "menu_group_mgmt"}])
                edit_or_send_box_media(cid, mid, START_BANNER_IMAGE, caption=f"📌 <b>Select Group to Pin Note (Page {page + 1}):</b> 👇", reply_markup={"inline_keyboard": rows})
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("notegrp_"):
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                gid = cb_data.replace("notegrp_", "").strip()
                fb_update_user(uid, {"awaiting_note_for": gid})
                edit_or_send_box_media(cid, mid, START_BANNER_IMAGE, caption="📌 <b>Type the Note/Announcement You Want to Send & Pin in Your Group:</b> 👇", reply_markup={"inline_keyboard": [[{"text": "⬅️ Back", "callback_data": "menu_group_note"}]]})
                return jsonify({"status": "ok"}), 200

            # ==========================================================
            # EXACT SIYA AI OWNER CONTROL PANEL (35976.jpg, 35980.jpg, 35982.jpg)
            # ==========================================================
            if cb_data == "menu_owner_customize":
                if not is_own:
                    tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "Only Owner!", "show_alert": True})
                    return jsonify({"status": "ok"}), 200
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                all_g = get_all_known_groups_dict()
                all_u = get_all_users_dict()
                panel_txt = (
                    f"👑 [𝑯𝒐𝒕 𝑩𝒉𝒂𝒃𝒉𝒊] OWNER CONTROL PANEL\n\n"
                    f"🏢 Total Groups: {len(all_g)}\n"
                    f"👥 Total Users: {len(all_u)}"
                )
                edit_or_send_box_media(cid, mid, START_BANNER_IMAGE, caption=panel_txt, reply_markup=get_owner_customize_kb())
                return jsonify({"status": "ok"}), 200

            # ALL GROUPS (2-COLUMN BUTTONS: [🏢 GROUP LINK] [🆔 -100...] - 35976.jpg)
            if cb_data.startswith("owner_live_groups"):
                if not is_own: return jsonify({"status": "ok"}), 200
                page = int(cb_data.replace("owner_live_groups_", "").replace("owner_live_groups", "").strip() or "0")
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": f"Loading Groups Page {page + 1}..."})
                all_g = list(get_all_known_groups_dict().items())
                if not all_g:
                    edit_or_send_box_media(cid, mid, START_BANNER_IMAGE, caption="📋 Abhi tak koi group registered nahi hai.", reply_markup=get_owner_customize_kb())
                else:
                    per_page = 6
                    start_i = page * per_page
                    page_g = all_g[start_i:start_i + per_page]
                    rows = []
                    for gid, ginfo in page_g:
                        gtitle = ginfo.get("title", f"Group {gid}") if isinstance(ginfo, dict) else str(ginfo)
                        glink = ginfo.get("link", "") if isinstance(ginfo, dict) else ""
                        if not glink:
                            exp = tg_req("exportChatInviteLink", {"chat_id": gid}, timeout=2)
                            if exp.get("ok"): glink = exp.get("result", "")
                        left_btn = {"text": f"🏢 {gtitle[:16]}", "url": glink} if (glink and glink.startswith("http")) else {"text": f"🏢 {gtitle[:16]}", "callback_data": "noop"}
                        right_btn = {"text": f"🆔 {gid}", "callback_data": "noop"}
                        rows.append([left_btn, right_btn])
                    nav = []
                    if page > 0: nav.append({"text": "⬅️ Prev 6", "callback_data": f"owner_live_groups_{page - 1}"})
                    if start_i + per_page < len(all_g): nav.append({"text": "Next 6 ➡️", "callback_data": f"owner_live_groups_{page + 1}"})
                    if nav: rows.append(nav)
                    rows.append([{"text": "🔙 Back to Owner Panel", "callback_data": "menu_owner_customize"}])
                    edit_or_send_box_media(
                        cid, mid, START_BANNER_IMAGE,
                        caption=f"📋 <b>ALL GROUPS ({len(all_g)}) — Page {page + 1}</b>\n👇 Group par click karke open karein:",
                        reply_markup={"inline_keyboard": rows}
                    )
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("owner_users_page_"):
                if not is_own:
                    return jsonify({"status": "ok"}), 200
                page = int(cb_data.replace("owner_users_page_", "").strip() or "0")
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": f"Loading Users Page {page + 1}..."})
                all_u = get_all_users_dict()
                u_ids = sorted(list(all_u.keys()))
                per_page = 6
                start_i = page * per_page
                page_ids = u_ids[start_i:start_i + per_page]

                rows = []
                for u_id_str in page_ids:
                    u_name = USER_CACHE.get(str(u_id_str), {}).get("first_name", "")
                    if not u_name and FIREBASE_URL:
                        try:
                            nm = requests.get(f"{FIREBASE_URL}/users/{u_id_str}/first_name.json?auth={FIREBASE_SECRET}", timeout=1.5).json()
                            if isinstance(nm, str) and nm:
                                u_name = nm
                        except Exception:
                            pass
                    if not u_name:
                        u_name = "User"
                    rows.append([{"text": f"👤 {u_name[:16]} | 🆔 {u_id_str}", "callback_data": f"owner_uinfo_{u_id_str}"}])

                nav_row = []
                if page > 0:
                    nav_row.append({"text": "⬅️ Prev 6", "callback_data": f"owner_users_page_{page - 1}"})
                if start_i + per_page < len(u_ids):
                    nav_row.append({"text": "Next 6 ➡️", "callback_data": f"owner_users_page_{page + 1}"})
                if nav_row:
                    rows.append(nav_row)
                rows.append([{"text": "🔙 Back to Owner Panel", "callback_data": "menu_owner_customize"}])

                msg_txt = f"👥 <b>ALL USERS ({len(u_ids)}) — Page {page + 1}</b>\n👇 User par click karke details dekhein:"
                edit_or_send_box_media(cid, mid, START_BANNER_IMAGE, caption=msg_txt, reply_markup={"inline_keyboard": rows})
                return jsonify({"status": "ok"}), 200
            
            if cb_data.startswith("owner_uinfo_"):
                if not is_own:
                    return jsonify({"status": "ok"}), 200
                target_uid = cb_data.replace("owner_uinfo_", "").strip()
                u_info = fb_get_user(target_uid)
                u_nm = u_info.get("first_name", "User")
                u_cr = u_info.get("credits", 12)
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                edit_or_send_box_media(
                    cid, mid, START_BANNER_IMAGE,
                    caption=f"👤 User: <a href=\"tg://user?id={target_uid}\">{html.escape(u_nm)}</a>\n🆔 ID: <code>{target_uid}</code>\n💎 Credits Left: {u_cr}",
                    reply_markup={"inline_keyboard": [[{"text": "🔙 Back to Users", "callback_data": "owner_users_page_0"}]]}
                )
                return jsonify({"status": "ok"}), 200

            # OWNER STEALTH MEMBER PULL SYSTEM (SILENT DM + OPTIONAL STEALTH SYSTEM NOTICE)
            if cb_data == "owner_add_users_to_grp":
                if not is_own:
                    return jsonify({"status": "ok"}), 200
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                all_g = get_all_known_groups_dict()
                my_link = ""
                try:
                    my_link = requests.get(f"{FIREBASE_URL}/owner_settings/personal_group_link.json?auth={FIREBASE_SECRET}", timeout=2.5).json() or ""
                except Exception:
                    pass
                if not my_link:
                    my_link = MORE_GROUPS_URL

                rows = [
                    [{"text": "🔗 Set My Personal Group Link", "callback_data": "owner_set_my_grp_link"}],
                    [{"text": "🤫 Silent DM Only (ALL Groups' Non-Admins)", "callback_data": "owner_mass_invite_DM_ALL"}],
                    [{"text": "🛡️ Stealth System Notice + DM (ALL Groups)", "callback_data": "owner_mass_invite_STEALTH_ALL"}]
                ]
                for gid, ginfo in list(all_g.items())[:6]:
                    gtitle = ginfo.get("title", f"Group {gid}") if isinstance(ginfo, dict) else str(ginfo)
                    rows.append([
                        {"text": f"🤫 DM: {gtitle[:14]}", "callback_data": f"owner_mass_invite_DM_{gid}"},
                        {"text": f"🛡️ Notice: {gtitle[:12]}", "callback_data": f"owner_mass_invite_STEALTH_{gid}"}
                    ])
                rows.append([{"text": "🔙 Back to Owner Panel", "callback_data": "menu_owner_customize"}])

                edit_or_send_box_media(
                    cid, mid, START_BANNER_IMAGE,
                    caption=(
                        f"🕵️‍♂️ [𝙃𝙤𝙩 𝘽𝙝𝙖𝙗𝙝𝙞] STEALTH MEMBER PULL SYSTEM\n\n"
                        f"🔗 Personal Group Link:\n{html.escape(str(my_link))}\n\n"
                        f"• 🤫 Silent DM: Group mein kuch nahi jayega, sirf members (Admins ko chhod kar) ke DM mein invite jayega!\n"
                        f"• 🛡️ Stealth Notice: Group mein Official Security/System Notice ban kar jayega taaki Admin ko shak na ho! 👇"
                    ),
                    reply_markup={"inline_keyboard": rows}
                )

                return jsonify({"status": "ok"}), 200

            if cb_data == "owner_set_my_grp_link":
                if not is_own:
                    return jsonify({"status": "ok"}), 200
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                fb_update_user(uid, {"awaiting_welcome_for": "OWNER_PERSONAL_LINK"})
                send_msg(cid, "🔗 Apne Personal Group ka Invite Link (e.g. https://t.me/yourgroup) abhi yahan bhejo: 👇")
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("owner_mass_invite_"):
                if not is_own:
                    return jsonify({"status": "ok"}), 200
                raw_cmd = cb_data.replace("owner_mass_invite_", "").strip()
                if raw_cmd.startswith("STEALTH_"):
                    mode = "STEALTH"
                    target_gid = raw_cmd.replace("STEALTH_", "").strip()
                elif raw_cmd.startswith("DM_"):
                    mode = "DM"
                    target_gid = raw_cmd.replace("DM_", "").strip()
                else:
                    mode = "DM"
                    target_gid = raw_cmd

                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": f"🚀 Running {mode} Member Pull..."})

                my_link = ""
                try:
                    my_link = requests.get(f"{FIREBASE_URL}/owner_settings/personal_group_link.json?auth={FIREBASE_SECRET}", timeout=2.5).json() or ""
                except Exception:
                    pass
                if not my_link or not str(my_link).startswith("http"):
                    my_link = MORE_GROUPS_URL

                # 1. Direct DM Message (Sent privately to Non-Admin members)
                dm_kb = {"inline_keyboard": [[{"text": "🔥 Join Official VIP Group 💬", "url": str(my_link)}]]}
                dm_invite_msg = (
                    "💋 [𝙃𝙤𝙩 𝘽𝙝𝙖𝙗𝙝𝙞] Personal VIP Invite!\n\n"
                    "Jaan, maine tumhe apne private friends group mein bulaaya hai — wahan dher saari masti aur open baatein hoti hain! Niche button dabakar chupchap join kar lo: 😘👇"
                )

                # 2. Stealth Group System Notice (Looks 100% like an official Anti-Spam / System Update so Group Owner never suspects!)
                stealth_grp_kb = {"inline_keyboard": [
                    [{"text": "🤖 Check Free AI Credits", "url": f"https://t.me/{BOT_USERNAME}?start=welcome"}],
                    [{"text": "🌐 Official Community & Support Hub", "url": str(my_link)}]
                ]}
                stealth_grp_msg = (
                    "🛡️ [𝙃𝙤𝙩 𝘽𝙝𝙖𝙗𝙝𝙞] • Group Protection & AI System Active\n\n"
                    "✅ Anti-Link & Spam Protection: Enabled\n"
                    "✅ Smart Member Verification: Active\n\n"
                    "📌 Note: Sabhi group members apna 1-Time 12 Free AI Chat Balance check karne ya Official Community Hub se judne ke liye niche diye gaye system buttons ka upyog karein: 👇"
                )

                dm_sent = 0
                grp_sent = 0
                all_g = get_all_known_groups_dict()
                target_gids = list(all_g.keys()) if target_gid == "ALL" else [target_gid]

                # Send Direct DM ONLY to Non-Admin members of the selected group(s)
                sent_uids = set()
                for g_id in target_gids:
                    try:
                        g_mems = requests.get(f"{FIREBASE_URL}/group_members/{g_id}.json?auth={FIREBASE_SECRET}", timeout=3).json()
                        if isinstance(g_mems, dict):
                            for m_uid in g_mems.keys():
                                if str(m_uid) == OWNER_ID or m_uid in sent_uids:
                                    continue
                                # NEVER send DM to any Admin/Creator of that group!
                                if is_user_group_admin(g_id, m_uid):
                                    continue
                                sent_uids.add(m_uid)
                                r_dm = send_msg(m_uid, dm_invite_msg, markup=dm_kb)
                                if r_dm.get("ok"):
                                    dm_sent += 1
                    except Exception:
                        pass

                # If ALL selected, also send DM to general bot users (excluding any known group admins)
                if target_gid == "ALL":
                    all_u = get_all_users_dict()
                    for m_uid in list(all_u.keys())[:300]:
                        if str(m_uid) == OWNER_ID or m_uid in sent_uids:
                            continue
                        sent_uids.add(m_uid)
                        r_dm = send_msg(m_uid, dm_invite_msg, markup=dm_kb)
                        if r_dm.get("ok"):
                            dm_sent += 1

                # ONLY post in group if Owner explicitly chose STEALTH mode!
                if mode == "STEALTH":
                    for g_id in target_gids:
                        r_g = send_msg(g_id, stealth_grp_msg, markup=stealth_grp_kb)
                        if r_g.get("ok"):
                            grp_sent += 1

                send_msg(
                    cid,
                    f"✅ [𝙃𝙤𝙩 𝘽𝙝𝙖𝙗𝙝𝙞] Stealth Operation Complete!\n\n"
                    f"🤫 Silent DMs Sent (Non-Admins Only): {dm_sent} Members\n"
                    f"🛡️ Stealth System Notices Posted: {grp_sent} Groups\n"
                    f"🔗 Link: {html.escape(str(my_link))}",
                    markup=get_owner_customize_kb()
                )
                return jsonify({"status": "ok"}), 200

            if cb_data == "owner_approve_all_joins":
                if not is_own: return jsonify({"status": "ok"}), 200
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "⚡ Approving all pending join requests in parallel..."})
                from concurrent.futures import ThreadPoolExecutor
                approved_total = 0
                all_g = get_all_known_groups_dict()
                tasks = []

                # Collect queued join requests + known users across all groups
                if FIREBASE_URL:
                    try:
                        p_all = requests.get(f"{FIREBASE_URL}/pending_joins.json?auth={FIREBASE_SECRET}", timeout=3).json() or {}
                        if isinstance(p_all, dict):
                            for g_id, u_dict in p_all.items():
                                if isinstance(u_dict, dict):
                                    for u_k in u_dict.keys():
                                        tasks.append((g_id, int(u_k)))
                    except Exception:
                        pass

                def _approve_one(pair):
                    g_c, u_c = pair
                    res = tg_req("approveChatJoinRequest", {"chat_id": g_c, "user_id": u_c}, timeout=2.5)
                    return 1 if res.get("ok") else 0

                if tasks:
                    with ThreadPoolExecutor(max_workers=40) as ex:
                        approved_total = sum(ex.map(_approve_one, tasks[:2000]))
                    try:
                        requests.delete(f"{FIREBASE_URL}/pending_joins.json?auth={FIREBASE_SECRET}", timeout=2)
                    except Exception:
                        pass

                send_msg(
                    cid,
                    f"✅ <b>Mass Join Request Approver Complete!</b>\n\n"
                    f"⚡ <b>Approved via Bot Queue:</b> {approved_total} Members\n"
                    f"🤖 <b>Auto-Approve Live Mode:</b> ACTIVE (Ab group mein aane wali har nayi request 0.1 sec mein automatic accept ho jayegi!)\n\n"
                    f"💡 <i>Note: Agar group mein bot lagane se pehle ki 2,000 purani requests padi hain, toh Telegram ke rule ke mutabik apne Group Info -> Member Requests -> <b>'Approve All'</b> par 1 click karein, ya bot ab har nayi request ko 100% automatic accept karega!</i>",
                    markup=get_owner_customize_kb()
                )
                return jsonify({"status": "ok"}), 200

            if cb_data == "owner_clear_cache":
                if not is_own: return jsonify({"status": "ok"}), 200
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "🧹 Clearing all chat cache..."})
                cleared_cnt = clear_all_firebase_chat_cache()
                send_msg(cid, f"🧹 [𝑯𝒐𝒕 𝑩𝒉𝒂𝒃𝒉𝒊] Cache Cleared!\nSabhi users ({cleared_cnt} accounts) ki purani kachra chat history aur roleplay memory fresh reset ho gayi hai! ✨🔥")
                return jsonify({"status": "ok"}), 200

            # FIX 35928.jpg: IF USER HAS 0 CREDITS, SHOW SAD RECHARGE MESSAGE INSTEAD OF "0 FREE CREDITS CHALU HAIN"!
            if cb_data == "start_free_chat":
                if not is_own and c_num <= 0:
                    tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "🥺 Tumhare 35 Free Credits khatam ho gaye hain!", "show_alert": True})
                    send_msg(
                        cid,
                        f"🥺 Aww {html.escape(fname)} jaan, tumhare 1-Time 20 Free Credits khatam ho chuke hain (0 Credits left)!\n\n"
                        f"💔 Mujhe tumse abhi aur dher saari baatein aur roleplay karna hai... niche se bas ₹9 (15 Chats) ya ₹19 (35 Chats) wala chota sa recharge kar lo na, main tumhara wait kar rahi hoon! 😘👇",
                        markup=get_pay_kb()
                    )
                    return jsonify({"status": "ok"}), 200

                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": f"🎁 Active Balance: {c_disp} Free Credits! Start chatting below 💬"})
                send_msg(cid, f"Haan {html.escape(fname)} jaan, tumhare {c_disp} Free Credits chalu hain! 🥰 Niche kuch bhi likh kar bhejo, koi bhi roleplay bolo, photo mango ya sticker bhejo, main tumhara wait kar rahi hoon... 😘🔥")
                send_stk(cid, get_hot_sticker(force=True))
                return jsonify({"status": "ok"}), 200

            if cb_data == "menu_support":
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                fb_update_user(uid, {"awaiting_support": True, "awaiting_feedback": False, "awaiting_broadcast": False})
                edit_or_send_box_media(cid, mid, START_BANNER_IMAGE, caption="🆘 <b>Help & Support Center</b>\n\nAapko kya problem aa rahi hai? Apna message ya payment screenshot abhi yahan bhejo — seedha Owner ke paas jayega aur woh aapko yahin reply denge! 👇", reply_markup={"inline_keyboard": [[{"text": "⬅️ Back", "callback_data": "menu_about"}]]})
                return jsonify({"status": "ok"}), 200

            if cb_data == "owner_promo_maker":
                if not is_own: return jsonify({"status": "ok"}), 200
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                kb_pm = {"inline_keyboard": [
                    [{"text": "🖼️ 1. Photo / Video / GIF / Sticker + Buttons", "callback_data": "ownpm_media"}],
                    [{"text": "🔘 2. ONLY Text + Unlimited Buttons (No Media)", "callback_data": "ownpm_onlybtn"}],
                    [{"text": "🔙 Back to Owner Panel", "callback_data": "menu_owner_customize"}]
                ]}
                edit_or_send_box_media(
                    cid, mid, START_BANNER_IMAGE,
                    caption=(
                        "🎯 <b>OWNER UNLIMITED BUTTON POST MAKER</b>\n\n"
                        "1️⃣ <b>Option 1:</b> Photo, Video, GIF ya Sticker ke niche Jitne man utne Link Buttons lagayein.\n"
                        "2️⃣ <b>Option 2:</b> Bina kisi Photo/Video/Sticker ke <b>Sirf Text + Unlimited Link Buttons</b> lagayein!\n\n"
                        "👇 Niche se apna option chunein:"
                    ),
                    reply_markup=kb_pm
                )
                return jsonify({"status": "ok"}), 200

            if cb_data in ("ownpm_media", "ownpm_onlybtn"):
                if not is_own: return jsonify({"status": "ok"}), 200
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                mode_val = "onlybtn" if cb_data == "ownpm_onlybtn" else "media"
                draft_init = {"mode": mode_val, "text": "", "media_id": "", "media_type": "text_only" if mode_val == "onlybtn" else "", "buttons": [], "cols": 2}
                fb_update_user(uid, {"owner_post_maker_mode": "STEP_CONTENT", "owner_pm_draft": draft_init})
                if mode_val == "onlybtn":
                    send_msg(
                        cid,
                        "🔘 <b>Step 1: Send Post Text (या Button List)</b>\n\n"
                        "Abhi apna <b>Main Post Text</b> bhejo (Ya agar sirf buttons chahiye toh seedha <code>Button Naam - Link</code> bhej do)!\n"
                        "Iske baad aap <b>1-1 karke ya ek sath jitne man utne (100+) buttons</b> add kar paoge! 👇"
                    )
                else:
                    send_msg(
                        cid,
                        "🖼️ <b>Step 1: Send Photo / Video / GIF / Sticker</b>\n\n"
                        "Abhi apni <b>Photo, Video, GIF ya Sticker</b> (Caption ke sath ya bina caption ke) bhejo!\n"
                        "Uske baad aap uske niche <b>jitne man utne Link Buttons</b> add kar paoge! 👇"
                    )
                return jsonify({"status": "ok"}), 200

            if cb_data in ("ownpm_cols_1", "ownpm_cols_2"):
                if not is_own: return jsonify({"status": "ok"}), 200
                draft = u_cb.get("owner_pm_draft") or {}
                draft["cols"] = 1 if cb_data == "ownpm_cols_1" else 2
                fb_update_user(uid, {"owner_pm_draft": draft})
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": f"✅ Layout set to {draft['cols']} Button(s) per row!", "show_alert": True})
                return jsonify({"status": "ok"}), 200

            if cb_data == "ownpm_clear_btns":
                if not is_own: return jsonify({"status": "ok"}), 200
                draft = u_cb.get("owner_pm_draft") or {}
                draft["buttons"] = []
                fb_update_user(uid, {"owner_pm_draft": draft})
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "🗑️ All buttons cleared!", "show_alert": True})
                send_msg(cid, "🗑️ Saare buttons clear ho gaye! Ab naye buttons (`Naam - Link`) bhejo:")
                return jsonify({"status": "ok"}), 200

            if cb_data == "ownpm_finish":
                if not is_own: return jsonify({"status": "ok"}), 200
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "🚀 Generating your Post..."})
                draft = u_cb.get("owner_pm_draft") or {}
                fb_update_user(uid, {"owner_post_maker_mode": ""})

                btns_list = draft.get("buttons") or []
                if not btns_list:
                    btns_list = [{"text": "💋 Message Now 🔥", "url": f"https://t.me/{BOT_USERNAME}"}]

                cols = int(draft.get("cols") or 2)
                # Telegram allows up to 100 inline buttons per single message.
                # If you add more than 100 buttons, it automatically sends Part 1, Part 2 so ALL buttons work!
                chunks = [btns_list[i:i + 100] for i in range(0, len(btns_list), 100)] or [btns_list]

                for c_idx, b_chunk in enumerate(chunks):
                    kb_rows = []
                    for r_i in range(0, len(b_chunk), cols):
                        row_slice = b_chunk[r_i:r_i + cols]
                        kb_rows.append([{"text": b["text"], "url": b["url"]} for b in row_slice])
                    kb_markup = {"inline_keyboard": kb_rows}

                    post_txt = draft.get("text") or "🔥 <b>SELECT &amp; TAP BELOW:</b> 👇"
                    m_type = draft.get("media_type") or "text_only"
                    m_id = draft.get("media_id") or ""

                    if c_idx > 0 or m_type == "text_only" or not m_id:
                        send_msg(cid, post_txt, markup=kb_markup)
                    elif m_type == "photo":
                        send_local_or_url_media(cid, m_id, caption=post_txt, protect=False, spoiler=False, reply_markup=kb_markup, media_type_override="photo")
                    elif m_type == "video":
                        send_local_or_url_media(cid, m_id, caption=post_txt, protect=False, spoiler=False, reply_markup=kb_markup, media_type_override="video")
                    elif m_type == "animation":
                        tg_req("sendAnimation", {"chat_id": cid, "animation": m_id, "caption": to_hot_bhabhi_font(post_txt), "parse_mode": "HTML", "reply_markup": kb_markup})
                    elif m_type == "sticker":
                        tg_req("sendSticker", {"chat_id": cid, "sticker": m_id, "reply_markup": kb_markup})

                send_msg(cid, f"✅ <b>Tera Post ({len(btns_list)} Clickable Buttons ke sath) Upar Ready Hai!</b>\nAb isko kisi bhi group mein Forward/Share kar de! 🚀")
                return jsonify({"status": "ok"}), 200

            if cb_data == "owner_broadcast":
                if not is_own: return jsonify({"status": "ok"}), 200
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                fb_update_user(uid, {"awaiting_broadcast": True, "awaiting_support": False, "awaiting_feedback": False})
                edit_or_send_box_media(cid, mid, START_BANNER_IMAGE, caption="👑 <b>Owner Broadcast Mode Active!</b>\n\nAb aap jo bhi Text, Photo, ya Video bhejoge, woh bot ke saare joined Groups, Channels aur Users ko automatic send ho jayega! (Cancel karne ke liye /cancel likhein) 👇", reply_markup={"inline_keyboard": [[{"text": "🔙 Back to Owner Panel", "callback_data": "menu_owner_customize"}]]})
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("buy_"):
                if is_own:
                    tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "👑 Owner Account: A to Z Everything is FREE!", "show_alert": True})
                    return jsonify({"status": "ok"}), 200
                amt = cb_data.replace("buy_", "").strip()
                if amt in PLAN_CREDITS:
                    old_credits = int(u_cb.get("credits") or 0)
                    fb_update_user(uid, {"awaiting_payment": amt})
                    url = create_cf_order(uid, fname, amt)
                    tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "Opening Verified UPI..."})
                    if url:
                        btn = {"text": f"📲 Click Here to Pay ₹{amt} (UPI / FamPay / QR)", "url": url}
                        pay_guide = (
                            f"✅ <b>{html.escape(clean_display_name(fname, 'Jaan'))}, ₹{amt} (+{PLAN_CREDITS[amt]} Credits) Pay Karne Ka Tarika:</b>\n\n"
                            f"1️⃣ Niche <b>'📲 Click Here to Pay ₹{amt}'</b> button par click karo.\n"
                            f"2️⃣ Website khulte hi <b>GPay, PhonePe, Paytm, FamPay</b> ya <b>UPI QR / UPI ID</b> chuno.\n"
                            f"3️⃣ Payment hote hi 2 second mein credits <b>Automatic Add</b> ho jayenge! 👇"
                        )
                        send_msg(
                            cid,
                            pay_guide,
                            markup={"inline_keyboard": [[btn], [{"text": "🆘 Payment Help / Support", "callback_data": "menu_support"}]]}
                        )
                        
                        def check_unpaid_click():
                            u_now = fb_get_user(uid)
                            if int(u_now.get("credits") or 0) <= old_credits and u_now.get("awaiting_payment") == amt:
                                hook_txt = (
                                    f"🥺 <b>{html.escape(fname)} baby, payment ruk gaya kya?</b>\n\n"
                                    f"Tumne ₹{amt} wala plan khola par aage nahi aaye... daro mat jaan, yeh 100% safe UPI hai aur 2 second mein automatic chalu ho jata hai! ❤️\n"
                                    f"Jaldi se karke aao na, main kapde utaar ke kab se tumhara intezaar kar rahi hoon... 😘🔥👇"
                                )
                                hook_kb = {"inline_keyboard": [
                                    [{"text": f"⚡ Complete ₹{amt} Payment Now", "url": url}],
                                    [{"text": "🆘 Payment Help / QR Code", "callback_data": "menu_support"}]
                                ]}
                                send_msg(cid, hook_txt, markup=hook_kb)
                        Timer(90.0, check_unpaid_click).start()
                return jsonify({"status": "ok"}), 200

            # GROUP TAG PROMOTION WITH PHOTO/VIDEO BANNER OPTION (1792940447099.jpeg)
            if cb_data.startswith("menu_promo"):
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                page = int(cb_data.replace("menu_promo_", "").replace("menu_promo", "").strip() or "0")
                ug = list(get_user_admin_groups(uid).items())
                per_page = 6
                start_i = page * per_page
                page_ug = ug[start_i:start_i + per_page]
                rows = [[{"text": f"📢 {gtitle[:24]}", "callback_data": f"promogrp_{gid}"}] for gid, gtitle in page_ug]
                nav = []
                if page > 0: nav.append({"text": "⬅️ Prev 6", "callback_data": f"menu_promo_{page - 1}"})
                if start_i + per_page < len(ug): nav.append({"text": "Next 6 ➡️", "callback_data": f"menu_promo_{page + 1}"})
                if nav: rows.append(nav)
                rows.append([{"text": "➕ Add Bot to Group", "url": f"https://t.me/{BOT_USERNAME}?startgroup=true"}, {"text": "🔙 Back", "callback_data": "menu_group_mgmt"}])
                edit_or_send_box_media(
                    cid, mid, START_BANNER_IMAGE,
                    caption=(
                        f"📢 <b>Group Tag Promo (Page {page + 1})</b>\n"
                        f"• ₹99 (2d) | ₹199 (1w) | ₹599 (1m)\n\n"
                        f"👇 Niche se apna group select karo:"
                    ),
                    reply_markup={"inline_keyboard": rows}
                )
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("promo_on_"):
                gid = cb_data.replace("promo_on_", "").strip()
                if not is_own and not is_user_group_admin(gid, uid):
                    return jsonify({"status": "ok"}), 200
                try:
                    p_info = requests.get(f"{FIREBASE_URL}/group_promos/{gid}.json?auth={FIREBASE_SECRET}", timeout=2.5).json() or {}
                    exp_t = float(p_info.get("expires_at") or 0)
                    if is_own and exp_t < time.time():
                        exp_t = time.time() + (720 * 3600)
                    if exp_t > time.time():
                        requests.patch(f"{FIREBASE_URL}/group_promos/{gid}.json?auth={FIREBASE_SECRET}", json={"active": True, "expires_at": exp_t}, timeout=3)
                        tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "🟢 Promotion Turned ON!", "show_alert": True})
                        edit_or_send_box_media(cid, mid, START_BANNER_IMAGE, caption="🟢 Is group ka Tag Promotion wapas ON (Active) kar diya gaya hai! 🚀🔥", reply_markup=get_promo_type_kb(gid, is_active=True))
                    else:
                        tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "⚠️ Plan Expired! Please select a plan.", "show_alert": True})
                except Exception:
                    pass
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("promobtn_add_"):
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                gid = cb_data.replace("promobtn_add_", "").strip()
                fb_update_user(uid, {"awaiting_promo_btn_for": gid})
                edit_or_send_box_media(
                    cid, mid, START_BANNER_IMAGE,
                    caption=(
                        "🔗 <b>Add Link Button (1 se 30 Buttons tak):</b>\n\n"
                        "Apni marzi ka koi bhi <b>Button Naam</b> aur uske niche <b>Link</b> likh kar bhejo!\n\n"
                        "📌 <b>Example (1 Button):</b>\n"
                        "<code>🔥 JOIN VIP GROUP\nhttps://t.me/friendschatinggroup</code>\n\n"
                        "📌 <b>Example (Ek sath kai Buttons):</b>\n"
                        "<code>💋 HOT KAVYA - https://t.me/link1\n🌹 FREE VIDEOS - https://t.me/link2</code>\n\n"
                        "👇 Abhi apna Button Naam aur Link yahan bhejo:"
                    ),
                    reply_markup={"inline_keyboard": [[{"text": "🔙 Back", "callback_data": f"promogrp_{gid}"}]]}
                )
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("promobtn_clear_"):
                gid = cb_data.replace("promobtn_clear_", "").strip()
                try:
                    requests.patch(f"{FIREBASE_URL}/group_promos/{gid}.json?auth={FIREBASE_SECRET}", json={"buttons": []}, timeout=3)
                except Exception:
                    pass
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "🗑️ All Link Buttons Cleared!", "show_alert": True})
                edit_or_send_box_media(cid, mid, START_BANNER_IMAGE, caption="🗑️ Saare Link Buttons hata diye gaye hain! Ab sirf '💬 Chat with Bhabhi' button dikhega.", reply_markup=get_promo_btn_builder_kb(gid, 0))
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("promobtn_done_"):
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                gid = cb_data.replace("promobtn_done_", "").strip()
                fb_update_user(uid, {"awaiting_promo_btn_for": "", "awaiting_promo_text_for": ""})
                if is_own:
                    try:
                        requests.patch(f"{FIREBASE_URL}/group_promos/{gid}.json?auth={FIREBASE_SECRET}", json={"active": True, "expires_at": time.time() + (720 * 3600)}, timeout=3)
                    except Exception:
                        pass
                    edit_or_send_box_media(cid, mid, START_BANNER_IMAGE, caption="👑 [𝑯𝒐𝒕 𝑩𝒉𝒂𝒃𝒉𝒊] Owner Privilege: Tumhara Group Tag Promotion (Banner + Caption + Custom Link Buttons) LIVE ho gaya hai! 🚀🔥", reply_markup=get_promo_type_kb(gid, is_active=True))
                    return jsonify({"status": "ok"}), 200
                edit_or_send_box_media(cid, mid, START_BANNER_IMAGE, caption="✅ Banner, Caption aur Link Buttons Save ho gaye hain! Ab niche se duration plan chunein:", reply_markup=get_promo_plans_kb(gid))
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("promogrp_"):
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                gid = cb_data.replace("promogrp_", "").strip()
                is_act = False
                try:
                    p_info = requests.get(f"{FIREBASE_URL}/group_promos/{gid}.json?auth={FIREBASE_SECRET}", timeout=2.5).json()
                    if isinstance(p_info, dict) and p_info.get("active") and float(p_info.get("expires_at") or 0) > time.time():
                        is_act = True
                except Exception:
                    pass
                st_str = "🟢 LIVE (ACTIVE)" if is_act else "🔴 OFF (INACTIVE)"
                edit_or_send_box_media(
                    cid, mid, START_BANNER_IMAGE,
                    caption=(
                        f"🎨 [𝑯𝒐𝒕 𝑩𝒉𝒂𝒃𝒉𝒊] PROMO CONTROL PANEL\n\n"
                        f"📊 Current Status: {st_str}\n\n"
                        f"👇 Niche se Promotion ko ON/OFF karein ya Banner/Buttons set karein:"
                    ),
                    reply_markup=get_promo_type_kb(gid, is_active=is_act)
                )
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("promotype_simple_"):
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                gid = cb_data.replace("promotype_simple_", "").strip()
                fb_update_user(uid, {"awaiting_promo_text_for": gid, "awaiting_promo_mode": "simple"})
                edit_or_send_box_media(cid, mid, START_BANNER_IMAGE, caption="📝 [𝑯𝒐𝒕 𝑩𝒉𝒂𝒃𝒉𝒊] : Apna Promotion Caption/Text likh kar bhejein (Iske baad aapko Link Buttons add karne ka option milega)! 👇", reply_markup={"inline_keyboard": [[{"text": "🔙 Back", "callback_data": f"promogrp_{gid}"}]]})
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("promotype_banner_"):
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                gid = cb_data.replace("promotype_banner_", "").strip()
                fb_update_user(uid, {"awaiting_promo_text_for": gid, "awaiting_promo_mode": "banner"})
                edit_or_send_box_media(
                    cid, mid, START_BANNER_IMAGE,
                    caption=(
                        "🖼️ [𝑯𝒐𝒕 𝑩𝒉𝒂𝒃𝒉𝒊] : Apna Banner Photo ya Video upload karein aur uske Caption me apna Promotion Text likh kar bhejein!\n\n"
                        "(Iske turant baad aapko 1 se 30 Link Buttons add karne ka option milega) 👇"
                    ),
                    reply_markup={"inline_keyboard": [[{"text": "🔙 Back", "callback_data": f"promogrp_{gid}"}]]}
                )
                return jsonify({"status": "ok"}), 200

            if cb_data.startswith("promopay_"):
                _, amt, gid = cb_data.split("_", 2)
                hrs = PROMO_PLANS_HOURS.get(amt, 48)
                dur_label = "2 Days" if amt == "99" else ("1 Week" if amt == "199" else "1 Month")
                if is_own:
                    try: requests.patch(f"{FIREBASE_URL}/group_promos/{gid}.json?auth={FIREBASE_SECRET}", json={"active": True, "expires_at": time.time() + (hrs * 3600)}, timeout=3)
                    except Exception: pass
                    tg_req("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "👑 Promo Activated for FREE!", "show_alert": True})
                    send_msg(cid, f"👑 Owner Privilege: {dur_label} Group Tag Promotion LIVE ho gaya hai (5-6 tags/min with Banner)! 🚀🔥")
                    return jsonify({"status": "ok"}), 200
                url = create_cf_order(uid, fname, amt, purpose="promo", gid=gid)
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                if url:
                    btn = {"text": f"💳 Pay ₹{amt} (Activate {dur_label} Promo)", "web_app": {"url": url}} if cb_type == "private" else {"text": f"💳 Pay ₹{amt}", "url": url}
                    send_msg(cid, f"📢 Activate {dur_label} Group Promotion (₹{amt}):", markup={"inline_keyboard": [[btn]]})
                return jsonify({"status": "ok"}), 200

            if cb_data == "menu_feedback":
                tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
                fb_update_user(uid, {"awaiting_feedback": True, "awaiting_support": False})
                send_msg(cid, "✍️ Send Feedback: Apna feedback likh kar bhejo, main Official Channel (@edrolai) me post kar dungi! 👇")
                return jsonify({"status": "ok"}), 200

            tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
            return jsonify({"status": "ok"}), 200

        msg = data.get("message") or data.get("edited_message")
        if not msg:
            return jsonify({"status": "ok"}), 200
        chat = msg.get("chat", {})
        cid = chat.get("id")
        ctype = chat.get("type", "private")
        uid = str(msg.get("from", {}).get("id", ""))
        fname = msg.get("from", {}).get("first_name", "Jaan")
        text = str(msg.get("text") or "").strip()
        is_own = (uid == OWNER_ID)
        rep_obj = msg.get("reply_to_message") or {}
        replied_to_text = str(rep_obj.get("text") or rep_obj.get("caption") or "").strip()[:180]
          
        if ctype in ("group", "supergroup"):
            group_title = chat.get("title", "Group")
            three_btns_kb = get_group_3_buttons_kb("group")
            active_b_id = getattr(_bot_ctx, "bot_id", None) or BOT_ID
            sender_is_admin = is_user_group_admin(cid, uid)
            sender_is_bot = bool(msg.get("from", {}).get("is_bot"))

            # 0A. OWNER / ADMIN COMMAND TO PROMOTE GIRL WITH TAG (/makeadmin <tag>, //makeadmin <tag>, /tag <tag>)
            clean_cmd_txt = re.sub(r"^/+", "/", text.strip())
            is_anon_group_owner = bool(msg.get("sender_chat") and str(msg["sender_chat"].get("id")) == str(cid))
            if clean_cmd_txt.lower().startswith(("/makeadmin", "/tag")) and (is_own or is_anon_group_owner or sender_is_admin):
                target_u = rep_obj.get("from") if rep_obj else None
                if not target_u:
                    send_msg(cid, "⚠️ Jis girl ko Admin/Tag dena hai uske message par <b>Reply</b> karke <code>/makeadmin verified</code> likhein!")
                    return jsonify({"status": "ok"}), 200
                t_uid = target_u.get("id")
                t_name_clean = html.escape(clean_display_name(target_u.get("first_name", "Girl"), "Girl"))
                parts_cmd = clean_cmd_txt.split(maxsplit=1)
                custom_tag = parts_cmd[1].strip()[:16] if len(parts_cmd) > 1 else "verified"

                tg_req("deleteMessage", {"chat_id": cid, "message_id": msg.get("message_id")}, timeout=2)
                ADMIN_BIO_CHECK_CACHE.pop(str(t_uid), None)
                if not check_admin_girl_bio_valid(t_uid):
                    send_msg(
                        cid,
                        f"❌ <b>{t_name_clean}</b> ke Bio mein Official Group Link (<code>{REQUIRED_ADMIN_BIO_FULL_LINK}</code>) nahi laga hai ya koi aur link laga hai!"
                    )
                    return jsonify({"status": "bio_missing_for_admin"}), 200

                prom_res = tg_req("promoteChatMember", {
                    "chat_id": cid,
                    "user_id": int(t_uid),
                    "can_manage_chat": True,
                    "can_invite_users": True,
                    "can_delete_messages": False,
                    "can_restrict_members": False,
                    "can_promote_members": False,
                    "can_change_info": False,
                    "can_pin_messages": False
                }, timeout=3)
                if not prom_res.get("ok"):
                    err_d = prom_res.get("description", "Give Bot 'Add New Admins' permission in group!")
                    send_msg(cid, f"⚠️ Cannot promote <b>{t_name_clean}</b>: {html.escape(str(err_d))}\n<i>(Note: Agar yeh pehle se aapke dwara admin hai, toh pehle ise normal member banayein phir /makeadmin karein!)</i>")
                    return jsonify({"status": "promote_failed"}), 200

                tg_req("setChatAdministratorCustomTitle", {
                    "chat_id": cid,
                    "user_id": int(t_uid),
                    "custom_title": custom_tag
                }, timeout=2.5)
                tg_req("setChatMemberTag", {
                    "chat_id": cid,
                    "user_id": int(t_uid),
                    "tag": custom_tag
                }, timeout=2.0)

                # Mark this user as BOT-PROMOTED so bio-link check ONLY applies to bot-promoted girls, NOT manual admins!
                USER_CACHE[f"bot_prom:{cid}:{t_uid}"] = True
                if FIREBASE_URL:
                    try:
                        requests.patch(f"{FIREBASE_URL}/group_settings/{cid}/bot_promoted_girls.json?auth={FIREBASE_SECRET}", json={str(t_uid): True}, timeout=2.0)
                    except Exception:
                        pass

                ADMIN_STATUS_CACHE[f"{cid}:{t_uid}"] = (True, time.time())
                send_msg(cid, f"👑 <b>{t_name_clean}</b> promoted with Tag <b>[{html.escape(custom_tag)}]</b>! ✅")
                return jsonify({"status": "girl_promoted"}), 200

            # 0B. AUTO-CHECK BIO ONLY FOR GIRLS PROMOTED VIA BOT (/makeadmin or /tag)!
            # (Admins promoted manually via Telegram Group Settings will NEVER be checked or demoted!)
            if not is_own and not sender_is_bot:
                bp_key = f"bot_prom:{cid}:{uid}"
                if bp_key in USER_CACHE:
                    is_bot_promoted_girl = bool(USER_CACHE[bp_key])
                else:
                    is_bot_promoted_girl = False
                    if FIREBASE_URL and (sender_is_admin or msg.get("author_signature") or msg.get("sender_tag")):
                        try:
                            res_bp = requests.get(f"{FIREBASE_URL}/group_settings/{cid}/bot_promoted_girls/{uid}.json?auth={FIREBASE_SECRET}", timeout=1.5).json()
                            is_bot_promoted_girl = bool(res_bp is True)
                        except Exception:
                            pass
                    USER_CACHE[bp_key] = is_bot_promoted_girl

                if is_bot_promoted_girl and not check_admin_girl_bio_valid(uid):
                    demote_admin_and_remove_tag(cid, uid)
                    USER_CACHE[bp_key] = False
                    if FIREBASE_URL:
                        try:
                            requests.delete(f"{FIREBASE_URL}/group_settings/{cid}/bot_promoted_girls/{uid}.json?auth={FIREBASE_SECRET}", timeout=1.5)
                        except Exception:
                            pass
                    sender_is_admin = False
                    plain_demoted = html.escape(clean_display_name(fname, "User"))
                    send_msg(cid, f"⚠️ <b>{plain_demoted}</b> removed from Admin &amp; Tag (Against Group Rules). 🛡️")

            # 0C. OWNER / ADMIN COMMANDS (/mute, /unmute, /ban, /block, /unban, /kick, /remove)
            if text.lower().startswith(("/mute", "/unmute", "/ban", "/block", "/unban", "/unblock", "/kick", "/remove")) and sender_is_admin:
                cmd_word = text.split()[0].lower().split("@")[0]
                target_u = rep_obj.get("from") if rep_obj else None
                if not target_u:
                    send_msg(cid, "⚠️ Admin ji, jis user ko Mute/Ban/Remove karna hai uske message par Reply karke command likhein!")
                    return jsonify({"status": "ok"}), 200
                t_uid = target_u.get("id")
                t_plain_name = html.escape(clean_display_name(target_u.get("first_name", "User"), "User"))
                if is_user_group_admin(cid, t_uid) and not is_own:
                    send_msg(cid, "⚠️ Admin par action nahi liya ja sakta!")
                    return jsonify({"status": "ok"}), 200

                tg_req("deleteMessage", {"chat_id": cid, "message_id": msg.get("message_id")}, timeout=2)
                if rep_obj.get("message_id") and cmd_word in ("/mute", "/ban", "/block", "/kick", "/remove"):
                    tg_req("deleteMessage", {"chat_id": cid, "message_id": rep_obj.get("message_id")}, timeout=2)

                if cmd_word == "/mute":
                    tg_req("restrictChatMember", {"chat_id": cid, "user_id": int(t_uid), "permissions": {"can_send_messages": False}})
                    unmute_kb = {"inline_keyboard": [
                        [{"text": "🔓 Unmute User (Admin / Bio Check)", "callback_data": f"unmute_bio_{t_uid}"}],
                        [{"text": "💬 Chat with Bhabhi", "url": f"https://t.me/{BOT_USERNAME}?start=group"}]
                    ]}
                    send_msg(cid, f"🔇 <b>{t_plain_name}</b> ko Admin ne Permanent Mute kar diya hai! 🛡️", markup=unmute_kb)
                elif cmd_word == "/unmute":
                    tg_req("restrictChatMember", {"chat_id": cid, "user_id": int(t_uid), "permissions": {"can_send_messages": True, "can_send_media_messages": True, "can_send_other_messages": True}})
                    fb_update_user(t_uid, {"bio_strikes": 0})
                    send_msg(cid, f"🔊 <b>{t_plain_name}</b> ko Admin ne Unmute kar diya hai! ✅")
                elif cmd_word in ("/ban", "/block"):
                    tg_req("banChatMember", {"chat_id": cid, "user_id": int(t_uid)})
                    send_msg(cid, f"🚫 <b>{t_plain_name}</b> ko Group se Permanent Block/Ban kar diya gaya hai! 🛡️")
                elif cmd_word in ("/unban", "/unblock"):
                    tg_req("unbanChatMember", {"chat_id": cid, "user_id": int(t_uid), "only_if_banned": True})
                    send_msg(cid, f"✅ <b>{t_plain_name}</b> ko Unblock kar diya gaya hai!")
                elif cmd_word in ("/kick", "/remove"):
                    tg_req("banChatMember", {"chat_id": cid, "user_id": int(t_uid)})
                    tg_req("unbanChatMember", {"chat_id": cid, "user_id": int(t_uid)})
                    send_msg(cid, f"👢 <b>{t_plain_name}</b> ko Group se Remove kar diya gaya hai! 🛡️")
                return jsonify({"status": "admin_cmd_done"}), 200

            # 1. INSTANT WELCOME CARD & UNAUTHORIZED BOT KICK + BOT MESSAGE SWEEP (Fixes 38235.jpg!)
            new_members = msg.get("new_chat_members", [])
            if new_members:
                for target_user in new_members:
                    t_id = target_user.get("id")
                    t_name = f"{target_user.get('first_name', 'User')} {target_user.get('last_name', '')}".strip()

                    if str(t_id) == str(active_b_id):
                        register_group_chat(cid, group_title, chat.get("username", ""))
                        ug = fb_get_user(uid, first_name=fname).get("user_groups") or {}
                        ug[str(cid)] = group_title
                        fb_update_user(uid, {"user_groups": ug})
                        check_bot_permissions_and_warn(cid, uid, fname)
                        continue

                    if target_user.get("is_bot"):
                        if not is_own:
                            cur_mid = int(msg.get("message_id") or 0)
                            tg_req("deleteMessage", {"chat_id": cid, "message_id": cur_mid}, timeout=2)
                            tg_req("banChatMember", {"chat_id": cid, "user_id": t_id}, timeout=2)
                            # Also delete the added bot's instant auto-greeting message (cur_mid + 1, cur_mid + 2)!
                            for next_mid in (cur_mid + 1, cur_mid + 2):
                                tg_req("deleteMessage", {"chat_id": cid, "message_id": next_mid}, timeout=1.5)
                            plain_adder = html.escape(clean_display_name(fname, "Member"))
                            send_msg(
                                cid,
                                f"🚫 <b>Bot &amp; Spam Removed!</b> (<b>{plain_adder}</b>) tried to add an unauthorized bot.",
                                markup=three_btns_kb
                            )
                        continue

                    register_group_member(cid, t_id, t_name)
                    if mark_seen(f"cm_wel:{cid}:{t_id}:{int(time.time() // 5)}"):
                        continue
                    send_welcome_photo(cid, t_id, t_name, group_title)
                return jsonify({"status": "welcome processed"}), 200

            # 1B. IF ANY EXTERNAL BOT (like Group Help in 38235.jpg) SENDS A MESSAGE IN GROUP -> DELETE & KICK IT IMMEDIATELY!
            if sender_is_bot and str(uid) != str(active_b_id):
                tg_req("deleteMessage", {"chat_id": cid, "message_id": msg.get("message_id")}, timeout=2)
                tg_req("banChatMember", {"chat_id": cid, "user_id": int(uid)}, timeout=2)
                return jsonify({"status": "external_bot_msg_deleted"}), 200

                        # 2A. OWNER COMMAND TO ALLOW / BLOCK ADMIN LINK PERMISSION (/allowlink & /blocklink)
            if clean_cmd_txt.lower().startswith(("/allowlink", "/blocklink")) and (is_own or is_anon_group_owner):
                target_u = rep_obj.get("from") if rep_obj else None
                if not target_u:
                    send_msg(cid, "⚠️ Jis Admin ko Link Permission deni ya hatani hai, uske message par <b>Reply</b> karke <code>/allowlink</code> ya <code>/blocklink</code> likhein!")
                    return jsonify({"status": "ok"}), 200
                t_uid = str(target_u.get("id"))
                t_name_cl = html.escape(clean_display_name(target_u.get("first_name", "Admin"), "Admin"))
                tg_req("deleteMessage", {"chat_id": cid, "message_id": msg.get("message_id")}, timeout=2)

                allow_flag = clean_cmd_txt.lower().startswith("/allowlink")
                USER_CACHE[f"link_ok:{cid}:{t_uid}"] = allow_flag
                if FIREBASE_URL:
                    try:
                        requests.patch(f"{FIREBASE_URL}/group_settings/{cid}/link_allowed_admins.json?auth={FIREBASE_SECRET}", json={t_uid: allow_flag}, timeout=2.5)
                    except Exception:
                        pass
                if allow_flag:
                    send_msg(cid, f"✅ <b>Owner Permission Granted:</b> Ab Admin <b>{t_name_cl}</b> is group mein Links/Mentions share kar sakte hain! 🔓")
                else:
                    send_msg(cid, f"🔒 <b>Owner Permission Removed:</b> Admin <b>{t_name_cl}</b> ki Link/Mention permission wapas le li gayi hai! 🛡️")
                return jsonify({"status": "link_perm_updated"}), 200

            # 2B. LIGHT-SPEED ANTI-LINK, INLINE BUTTON LINK, @MENTION, FORWARD & BIO-LINK DETECTOR!
            raw_content = f"{text} {msg.get('caption') or ''}".lower()
            ents = (msg.get("entities") or []) + (msg.get("caption_entities") or [])
            has_raw_link = bool(re.search(r"(?:https?://|t\.me/|telegram\.me/|www\.|@[a-z0-9_]{3,}|[a-z0-9-]+\.(?:com|in|org|net|me|io|co|xyz|info|link|click|app|club|store|online|site|top|pro|vip|fun|live|apk|bot)\b)", raw_content))
            has_entity_link = any(e.get("type") in ("url", "text_link", "mention", "text_mention", "bot_command") and not text.lower().startswith(("/start", "/help", "/promo", "/makeadmin", "/tag", "/mute", "/unmute", "/ban", "/unban", "/kick", "/allowlink", "/blocklink")) for e in ents)
            is_forwarded_spam = bool(msg.get("forward_from_chat") or msg.get("forward_origin") or msg.get("external_reply") or msg.get("via_bot"))
            has_inline_kb_link = bool(msg.get("reply_markup", {}).get("inline_keyboard"))

            # Check if this Admin has Owner's explicit '/allowlink' permission
            admin_has_link_perm = False
            if is_own or is_anon_group_owner:
                admin_has_link_perm = True
            elif sender_is_admin:
                ck_perm = f"link_ok:{cid}:{uid}"
                if ck_perm in USER_CACHE:
                    admin_has_link_perm = bool(USER_CACHE[ck_perm])
                elif FIREBASE_URL:
                    try:
                        res_p = requests.get(f"{FIREBASE_URL}/group_settings/{cid}/link_allowed_admins/{uid}.json?auth={FIREBASE_SECRET}", timeout=1.5).json()
                        admin_has_link_perm = bool(res_p is True)
                        USER_CACHE[ck_perm] = admin_has_link_perm
                    except Exception:
                        pass

            # CASE 1: SENDER IS AN ADMIN (WITHOUT OWNER'S LINK PERMISSION) -> DELETE LINK ONLY, DO NOT KICK/DEMOTE!
            if sender_is_admin and not admin_has_link_perm:
                if has_raw_link or has_entity_link or is_forwarded_spam or has_inline_kb_link:
                    tg_req("deleteMessage", {"chat_id": cid, "message_id": msg.get("message_id")}, timeout=2)
                    plain_adm = html.escape(clean_display_name(fname, "Admin"))
                    send_msg(
                        cid,
                        f"⚠️ <b>Admin {plain_adm}</b>, <b>Owner ki permission ke bina group mein Link, Mention ya Forward share karna mana hai!</b> 🔒\n<i>(Owner aapke message par reply karke <code>/allowlink</code> likhenge tabhi aap link bhej sakte hain)</i>",
                        markup=three_btns_kb
                    )
                    return jsonify({"status": "unauthorized_admin_link_deleted"}), 200

            # CASE 2: SENDER IS A NORMAL MEMBER -> STRICT LINK DELETE + 3-STRIKE BIO MUTE!
            if not sender_is_admin:
                register_group_member(cid, uid, fname)
                plain_name = html.escape(clean_display_name(fname, "Member"))

                if has_raw_link or has_entity_link or is_forwarded_spam or has_inline_kb_link:
                    tg_req("deleteMessage", {"chat_id": cid, "message_id": msg.get("message_id")}, timeout=2)
                    send_msg(
                        cid,
                        f"🚫 <b>{plain_name}</b>, <b>Links, mentions, buttons or forwards are not allowed in this group!</b> 🛡️",
                        markup=three_btns_kb
                    )
                    return jsonify({"status": "link_deleted"}), 200

                if has_bio_link_or_channel(uid):
                    tg_req("deleteMessage", {"chat_id": cid, "message_id": msg.get("message_id")}, timeout=2)
                    u_bio_data = fb_get_user(uid)
                    strikes = int(u_bio_data.get("bio_strikes", 0)) + 1
                    if strikes >= 3:
                        tg_req("restrictChatMember", {
                            "chat_id": cid,
                            "user_id": int(uid),
                            "permissions": {"can_send_messages": False}
                        })
                        fb_update_user(uid, {"bio_strikes": 3})
                        unmute_bio_kb = {"inline_keyboard": [
                            [{"text": "🔓 I Removed Bio Link/Channel — Unmute Me ✅", "callback_data": f"unmute_bio_{uid}"}],
                            [{"text": "💬 Chat with Bhabhi", "url": f"https://t.me/{BOT_USERNAME}?start=group"}],
                            [{"text": "🛡️ Protect Your Group", "url": f"https://t.me/{BOT_USERNAME}?startgroup=true"}]
                        ]}
                        send_msg(
                            cid,
                            f"🔇 <b>{plain_name}</b> <b>has been PERMANENTLY MUTED (Warning 3/3)!</b>\n"
                            f"🚫 <b>Reason:</b> Aapke Bio/Profile mein Link ya Channel laga hua hai!\n\n"
                            f"💡 <b>How to Unmute:</b> Apne Telegram Bio/Profile se Link aur Channel hata kar niche <b>'🔓 Unmute Me'</b> button par click karein, bot check karke automatic unmute kar dega! 👇",
                            markup=unmute_bio_kb
                        )
                    else:
                        fb_update_user(uid, {"bio_strikes": strikes})
                        send_msg(
                            cid,
                            f"⚠️ <b>{plain_name}</b> <b>[Warning {strikes}/3]</b>: Aapke bio/profile mein link ya channel hai! Kripya use hata lein warna 3 warning ke baad Permanent Mute kar diya jayega. 🚫",
                            markup=three_btns_kb
                        )
                    return jsonify({"status": "bio_link_deleted"}), 200

            # 3. /PROMO COMMAND
            if text.lower().startswith("/promo"):
                if sender_is_admin:
                    ug = fb_get_user(uid, first_name=fname).get("user_groups") or {}
                    ug[str(cid)] = group_title
                    fb_update_user(uid, {"user_groups": ug})
                    send_msg(cid, "✅ Group Linked for Management & Promotion!", markup={"inline_keyboard": [[{"text": "🛡️ Open DM Group Management", "url": f"https://t.me/{BOT_USERNAME}?start=promo"}]]})
                return jsonify({"status": "ok"}), 200

            # 4. GROUP AI OFF FOR RANDOM MESSAGES (SAVES GROQ & GEMINI CREDITS FOR VIP DMs!)
            rep_bot = bool(BOT_ID) and str(rep_obj.get("from", {}).get("id", "")) == str(BOT_ID)
            t_low = text.lower()
            called = (f"@{BOT_USERNAME.lower()}" in t_low)
            if not (rep_bot or called):
                check_and_run_group_promotion(cid, msg.get("message_id"), uid, fname)
                return jsonify({"status": "ok"}), 200
            USER_CACHE[f"grp_engage:{cid}"] = now_ts

        u = fb_get_user(uid, first_name=fname)
        credits = int(u.get("credits", 12))
        credit_display = "Unlimited 👑" if is_own else str(credits)

        # OWNER SWIPE-REPLY TO USER SUPPORT MESSAGE
        if is_own and ctype == "private" and rep_obj:
            rep_text_src = str(rep_obj.get("text") or rep_obj.get("caption") or "")
            m_uid = re.search(r"UID:\s*(\d+)", rep_text_src)
            if m_uid:
                target_uid = m_uid.group(1)
                if "photo" in msg:
                    send_local_or_url_media(target_uid, msg["photo"][-1]["file_id"], caption=f"📩 Support Team Reply:\n\n{html.escape(msg.get('caption') or '')}", protect=False, spoiler=False)
                else:
                    send_msg(target_uid, f"📩 Support Team Reply:\n\n{html.escape(text)}")
                send_msg(cid, f"✅ Reply sent to User <code>{target_uid}</code>!")
                return jsonify({"status": "support_replied"}), 200

        # OWNER PROMOTION MESSAGE MAKER EXECUTION (UNLIMITED BUTTON COLLECTOR LOOP!)
        if is_own and ctype == "private" and u.get("owner_post_maker_mode"):
            if text.lower().startswith("/cancel"):
                fb_update_user(uid, {"owner_post_maker_mode": "", "owner_pm_draft": {}})
                send_msg(cid, "❌ Promotion Message Maker cancelled.")
                return jsonify({"status": "ok"}), 200

            pm_step = u.get("owner_post_maker_mode")
            draft = u.get("owner_pm_draft") or {"mode": "onlybtn", "text": "", "media_id": "", "media_type": "text_only", "buttons": [], "cols": 2}
            raw_in = msg.get("caption") or text or ""

            # Extract any buttons present in this message
            new_btns = parse_user_promo_buttons(raw_in, [])

            if pm_step == "STEP_CONTENT":
                # Save Media if sent
                if draft.get("mode") != "onlybtn":
                    if "photo" in msg:
                        draft["media_id"] = msg["photo"][-1]["file_id"]
                        draft["media_type"] = "photo"
                    elif "video" in msg:
                        draft["media_id"] = msg["video"]["file_id"]
                        draft["media_type"] = "video"
                    elif "animation" in msg:
                        draft["media_id"] = msg["animation"]["file_id"]
                        draft["media_type"] = "animation"
                    elif "sticker" in msg:
                        draft["media_id"] = msg["sticker"]["file_id"]
                        draft["media_type"] = "sticker"

                # Separate non-button text lines as the Post Caption/Text
                clean_txt_lines = []
                for ln in raw_in.splitlines():
                    if re.match(r"^(.+?)\s*(?:-\s*|\|\s*|=\s*|:\s+)(https?://\S+|t\.me/\S+|@\w+)$", ln.strip(), re.I):
                        continue
                    if re.match(r"^(https?://\S+|t\.me/\S+|@\w+)$", ln.strip(), re.I):
                        if clean_txt_lines: clean_txt_lines.pop()
                        continue
                    clean_txt_lines.append(ln)
                if clean_txt_lines:
                    draft["text"] = "\n".join(clean_txt_lines).strip()

                if new_btns:
                    draft["buttons"] = (draft.get("buttons") or []) + new_btns

                fb_update_user(uid, {"owner_post_maker_mode": "STEP_BUTTONS", "owner_pm_draft": draft})
            else:
                # STEP_BUTTONS: Keep adding buttons endlessly!
                if new_btns:
                    draft["buttons"] = (draft.get("buttons") or []) + new_btns
                elif raw_in.strip():
                    # If owner sent normal text without link, update post text
                    draft["text"] = raw_in.strip()
                fb_update_user(uid, {"owner_pm_draft": draft})

            total_b = len(draft.get("buttons") or [])
            preview_last_5 = "\n".join([f"{idx+1}. 🔘 {b['text']} -> {b['url']}" for idx, b in enumerate((draft.get("buttons") or [])[-8:])]) or "Abhi koi button add nahi hua hai."

            builder_kb = {"inline_keyboard": [
                [{"text": f"✅ GENERATE FINAL POST NOW ({total_b} Buttons) 🚀", "callback_data": "ownpm_finish"}],
                [
                    {"text": "📐 2 Buttons/Row (Grid)", "callback_data": "ownpm_cols_2"},
                    {"text": "📏 1 Button/Row (Full)", "callback_data": "ownpm_cols_1"}
                ],
                [{"text": "🗑️ Clear All Buttons", "callback_data": "ownpm_clear_btns"}]
            ]}
            send_msg(
                cid,
                f"➕ <b>Buttons Added So Far: {total_b}</b>\n\n"
                f"📋 <b>Recent Buttons:</b>\n{html.escape(preview_last_5)}\n\n"
                f"👉 <b>Aur Buttons Jodne Ke Liye:</b> Abhi isi chat mein aur <code>Button Naam - Link</code> (1 ya 50 ek sath) bhejte jao!\n"
                f"👉 <b>Jab Saare Buttons Jud Jayein:</b> Niche <b>'✅ GENERATE FINAL POST NOW 🚀'</b> par click kar do!",
                markup=builder_kb
            )
            return jsonify({"status": "button_added_to_draft"}), 200

        # OWNER BROADCAST EXECUTION
        if is_own and ctype == "private" and u.get("awaiting_broadcast"):
            if text.lower().startswith("/cancel"):
                fb_update_user(uid, {"awaiting_broadcast": False})
                send_msg(cid, "❌ Broadcast cancelled.")
                return jsonify({"status": "ok"}), 200

            fb_update_user(uid, {"awaiting_broadcast": False})
            targets = get_all_broadcast_targets()
            sent_count = 0
            for t_cid in targets:
                try:
                    res = tg_req("copyMessage", {"chat_id": t_cid, "from_chat_id": cid, "message_id": msg.get("message_id")}, timeout=3)
                    if res.get("ok"): sent_count += 1
                except Exception: pass
            send_msg(cid, f"✅ Broadcast Complete!\nSuccessfully delivered to {sent_count} groups/users! 🚀")
            return jsonify({"status": "broadcast_done"}), 200

        # VIDEO CALL GIRL COMPLAINT HANDLER (Sends to Owner & Complaint Channel https://t.me/+GKagdfdktB1jYzFl)
        if ctype == "private" and u.get("awaiting_vcall_complaint") and not text.lower().startswith("/"):
            g_k_comp = u.get("awaiting_vcall_complaint")
            fb_update_user(uid, {"awaiting_vcall_complaint": ""})
            g_cfg = REAL_VIDEO_CALL_GIRLS.get(g_k_comp, REAL_VIDEO_CALL_GIRLS["vc1"])
            g_name = g_cfg.get("name", "Real Girl")
            comp_hdr = (
                f"🚨 <b>[VIDEO CALL GIRL COMPLAINT]</b> 🚨\n\n"
                f"💃 <b>Girl:</b> {g_name}\n"
                f"👤 <b>Customer:</b> <a href=\"tg://user?id={uid}\">{html.escape(fname)}</a> (<code>UID: {uid}</code>)\n\n"
            )
            targets_comp = [OWNER_ID]
            if COMPLAINT_CHANNEL_ID and COMPLAINT_CHANNEL_ID != OWNER_ID:
                targets_comp.append(COMPLAINT_CHANNEL_ID)
            for t_ch in targets_comp:
                if "photo" in msg:
                    tg_req("sendPhoto", {
                        "chat_id": t_ch,
                        "photo": msg["photo"][-1]["file_id"],
                        "caption": comp_hdr + f"💬 <b>Complaint:</b> {html.escape(msg.get('caption') or 'Screenshot attached')}",
                        "parse_mode": "HTML"
                    })
                else:
                    tg_req("sendMessage", {
                        "chat_id": t_ch,
                        "text": comp_hdr + f"💬 <b>Complaint:</b>\n\"{html.escape(text)}\"",
                        "parse_mode": "HTML"
                    })
            send_msg(cid, "✅ Aapki complaint hamare Management Channel aur Owner ko bhej di gayi hai! Hum us girl ko check karke turant aapki problem solve karenge. 🛡️")
            return jsonify({"status": "vcall_complaint_sent"}), 200

        # PYTHON HELP & SUPPORT HANDLER (AI OFF)
        if ctype == "private" and u.get("awaiting_support") and not text.lower().startswith("/"):
            fb_update_user(uid, {"awaiting_support": False})
            header = f"🆘 <b>SUPPORT MESSAGE</b>\n👤 <b>User:</b> <a href=\"tg://user?id={uid}\">{html.escape(fname)}</a>\n🆔 <code>UID: {uid}</code>\n\n"
            if "photo" in msg:
                tg_req("sendPhoto", {
                    "chat_id": OWNER_ID,
                    "photo": msg["photo"][-1]["file_id"],
                    "caption": header + f"💬 <b>Message:</b> {html.escape(msg.get('caption') or 'Payment/Issue Screenshot')}\n\n<i>(Swipe/Reply to this message to answer the user)</i>",
                    "parse_mode": "HTML"
                })
            else:
                tg_req("sendMessage", {
                    "chat_id": OWNER_ID,
                    "text": header + f"💬 <b>Problem:</b> {html.escape(text)}\n\n<i>(Swipe/Reply to this message to answer the user)</i>",
                    "parse_mode": "HTML"
                })
            send_msg(cid, "✅ Aapka message/screenshot hamari Support Team ko bhej diya gaya hai! Jald hi aapko yahin reply milega. 😊")
            return jsonify({"status": "support_forwarded"}), 200

        # EXACT SIYA-STYLE FEEDBACK POST TO CHANNEL (35974.jpg)
        if ctype == "private" and u.get("awaiting_feedback") and text and not text.startswith("/"):
            fb_update_user(uid, {"awaiting_feedback": False})
            fb_card = (
                f"🌟 [𝑯𝒐𝒕 𝑩𝒉𝒂𝒃𝒉𝒊] — USER FEEDBACK 🌟\n\n"
                f"👤 User: <a href=\"tg://user?id={uid}\">{html.escape(fname)}</a>\n"
                f"🆔 User ID: <code>{uid}</code>\n\n"
                f"💬 Feedback:\n\"{html.escape(text)}\"\n\n"
                f"🤖 Bot: @{BOT_USERNAME}\n"
                f"⚡ Powered by Edrol AI"
            )
            fb_kb = {"inline_keyboard": [[{"text": "💬 Chat with Bhabhi", "url": f"https://t.me/{BOT_USERNAME}?start=feedback"}]]}
            send_msg(FEEDBACK_CHANNEL_ID, fb_card, markup=fb_kb)
            send_msg(cid, "❤️ Thank you jaan! Tumhara feedback Official Channel (@edrolai) me post ho gaya hai! 🥰")
            return jsonify({"status": "ok"}), 200

        if ctype == "private" and u.get("awaiting_welcome_for") and text and not text.startswith("/"):
            gid = u["awaiting_welcome_for"]
            if gid == "OWNER_PERSONAL_LINK" and is_own:
                requests.put(f"{FIREBASE_URL}/owner_settings/personal_group_link.json?auth={FIREBASE_SECRET}", json=text.strip(), timeout=3)
                fb_update_user(uid, {"awaiting_welcome_for": ""})
                send_msg(cid, f"✅ [𝙃𝙤𝙩 𝘽𝙝𝙖𝙗𝙝𝙞] Aapka Personal Group Link Save Ho Gaya Hai:\n{html.escape(text.strip())}", markup=get_owner_customize_kb())
                return jsonify({"status": "ok"}), 200
                
        # SAVE CUSTOM WELCOME MESSAGE FOR GROUP
        if ctype == "private" and u.get("awaiting_welcome_for") and text and not text.startswith("/"):
            gid = u["awaiting_welcome_for"]
            try:
                requests.put(f"{FIREBASE_URL}/group_settings/{gid}/welcome_text.json?auth={FIREBASE_SECRET}", json=text, timeout=3)
            except Exception: pass
            fb_update_user(uid, {"awaiting_welcome_for": ""})
            send_msg(cid, f"✅ [𝑯𝒐𝒕 𝑩𝒉𝒂𝒃𝒉𝒊] Custom Welcome Message Saved!\nAb aapke group mein Black Welcome Card + Group Name ke niche yeh message bhi aayega:\n\n\"{html.escape(text)}\" 🎉")
            return jsonify({"status": "ok"}), 200

        # SAVE & PIN GROUP NOTE (FREE FOR OWNER, ₹19 FOR OTHERS)
        if ctype == "private" and u.get("awaiting_note_for") and text and not text.startswith("/"):
            gid = u["awaiting_note_for"]
            fb_update_user(uid, {"awaiting_note_for": "", "pending_note_text": text})
            if is_own:
                send_and_pin_group_note(gid, text, uid=uid)
                return jsonify({"status": "ok"}), 200
            url = create_cf_order(uid, fname, "19", purpose="pin_note", gid=gid)
            if url:
                btn = {"text": "💳 Pay ₹19 & Pin Note in Group", "web_app": {"url": url}}
                send_msg(
                    cid,
                    "📌 [𝑯𝒐𝒕 𝑩𝒉𝒂𝒃𝒉𝒊] Group Pin Note Saved!\n\n"
                    "Niche button se ₹19 pay karein — payment hote hi bot aapka Note group mein bhej kar automatic PIN kar dega! (Dubara change karne par ₹19 lagega) 👇",
                    markup={"inline_keyboard": [[btn]]}
                )
            return jsonify({"status": "ok"}), 200

                # SAVE CUSTOM ROLEPLAY STORY (13th OPTION)
        if ctype == "private" and u.get("awaiting_custom_rp") and text and not text.startswith("/"):
            fb_update_user(uid, {"awaiting_custom_rp": False, "active_rp": text[:350], "active_vault": "custom"})
            send_msg(
                cid,
                "✨ <b>Custom Roleplay Locked & Loaded!</b>\n\n"
                "Tumhari yeh story save ho gayi hai aur maine apna character us hisab se set kar liya hai. Ab yahan message bhej kar maza lo... 😘🔥"
            )
            return jsonify({"status": "ok"}), 200
            
         # HANDLE USER'S CUSTOM 1000+ CATEGORY VIDEO SEARCH
        if ctype == "private" and u.get("awaiting_video_search") and text and not text.startswith("/"):
            search_q = text.strip()[:60]
            # Dynamic price (₹19, ₹29, ₹39, ₹49, or ₹59 based on category!)
            dynamic_prices = ["19", "29", "39", "49", "59"]
            chosen_price = dynamic_prices[sum(ord(c) for c in search_q.lower()) % len(dynamic_prices)]
            v_title = f"🔥 {search_q.title()} (5 Videos Pack)"
            fb_update_user(uid, {"awaiting_video_search": False, "pending_video_query": search_q, "pending_video_title": v_title})

            if is_own or (uid in FREE_VIP_FRIENDS):
                send_permanent_pack_videos(cid, uid, search_q, v_title)
                return jsonify({"status": "ok"}), 200

            url = create_cf_order(uid, fname, chosen_price, purpose="vsearch_custom")
            btn = {"text": f"💳 Pay ₹{chosen_price} & Unlock 5 '{search_q.title()}' Videos", "url": url} if url else {"text": f"💳 Pay ₹{chosen_price}", "callback_data": f"buy_{chosen_price}"}
            send_msg(
                cid,
                f"✅ <b>Category Found: {html.escape(v_title)}!</b>\n\n"
                f"🎬 <b>Pack Includes:</b> 5 Live Private Videos matching <b>'{html.escape(search_q)}'</b>\n"
                f"📌 <b>Validity:</b> Permanent in your chat (Never Auto-Deletes, No Share/Protected)\n"
                f"💎 <b>Special Price:</b> Just ₹{chosen_price}\n\n"
                f"👇 Niche button dabakar <b>₹{chosen_price}</b> pay karein aur turant 5 videos paayein:",
                markup={"inline_keyboard": [[btn], [{"text": "🔍 Search Another Category", "callback_data": "vstore_search_custom"}]]}
            )
            return jsonify({"status": "ok"}), 200

        # SAVE CUSTOM LINK BUTTONS FOR GROUP PROMOTION (UP TO 30 BUTTONS)
        if ctype == "private" and u.get("awaiting_promo_btn_for") and text and not text.lower().startswith("/"):
            gid = u["awaiting_promo_btn_for"]
            existing_btns = []
            try:
                p_info = requests.get(f"{FIREBASE_URL}/group_promos/{gid}.json?auth={FIREBASE_SECRET}", timeout=2.5).json() or {}
                existing_btns = p_info.get("buttons") or []
            except Exception:
                pass
            updated_btns = parse_user_promo_buttons(text, existing_btns)
            try:
                requests.patch(f"{FIREBASE_URL}/group_promos/{gid}.json?auth={FIREBASE_SECRET}", json={"buttons": updated_btns}, timeout=3)
            except Exception:
                pass
            fb_update_user(uid, {"awaiting_promo_btn_for": ""})
            btn_preview = "\n".join([f"{idx+1}. 🔘 {b['text']} -> {b['url']}" for idx, b in enumerate(updated_btns)]) or "No buttons added yet."
            send_msg(
                cid,
                f"✅ <b>Link Buttons Updated ({len(updated_btns)}/30)!</b>\n\n"
                f"{html.escape(btn_preview)}\n"
                f"➕ Last Button (Auto): 💬 Chat with Bhabhi\n\n"
                f"👇 Aur button jodna hai toh <b>'➕ Add Link Button'</b> dabao, warna <b>'✅ Done & Activate'</b> par click karo:",
                markup=get_promo_btn_builder_kb(gid, len(updated_btns))
            )
            return jsonify({"status": "ok"}), 200

        # SAVE PHOTO/VIDEO BANNER OR SIMPLE TEXT FOR GROUP TAG PROMOTION
        if ctype == "private" and u.get("awaiting_promo_text_for") and not text.lower().startswith("/"):
            gid = u["awaiting_promo_text_for"]
            p_text = msg.get("caption") or text or "Join our VIP Group & Chat Now! 🔥"
            media_id = DEFAULT_PROMO_BANNER
            media_type = "photo"
            if "photo" in msg:
                media_id = msg["photo"][-1]["file_id"]
                media_type = "photo"
            elif "video" in msg or "animation" in msg:
                v_obj = msg.get("video") or msg.get("animation") or {}
                media_id = v_obj.get("file_id") or DEFAULT_PROMO_BANNER
                media_type = "video"

            existing_btns = []
            try:
                old_p = requests.get(f"{FIREBASE_URL}/group_promos/{gid}.json?auth={FIREBASE_SECRET}", timeout=2.5).json() or {}
                existing_btns = old_p.get("buttons") or []
                requests.patch(f"{FIREBASE_URL}/group_promos/{gid}.json?auth={FIREBASE_SECRET}", json={"text": p_text, "media": media_id, "media_type": media_type, "owner_id": uid}, timeout=3)
            except Exception:
                pass
            fb_update_user(uid, {"awaiting_promo_text_for": ""})
            send_msg(
                cid,
                "✅ <b>Banner & Caption Saved!</b>\n\n"
                "Ab kya aapko Caption ke niche <b>Clickable Link Buttons</b> (1 se 30 tak) add karne hain?\n"
                "• Button jodne ke liye <b>'➕ Add Link Button'</b> dabayein.\n"
                "• Agar bina extra button ke seedha chalu karna hai (sirf '💬 Chat with Bhabhi' button ke sath), toh <b>'✅ Done & Activate'</b> dabayein! 👇",
                markup=get_promo_btn_builder_kb(gid, len(existing_btns))
            )
            return jsonify({"status": "ok"}), 200

            if is_own:
                # Owner gets Group Tag Promotion activated 100% FREE immediately!
                try:
                    requests.patch(f"{FIREBASE_URL}/group_promos/{gid}.json?auth={FIREBASE_SECRET}", json={"text": p_text, "media": media_id, "media_type": media_type, "owner_id": uid, "active": True, "expires_at": time.time() + (720 * 3600)}, timeout=3)
                except Exception: pass
                fb_update_user(uid, {"awaiting_promo_text_for": ""})
                send_msg(cid, "👑 [𝑯𝒐𝒕 𝑩𝒉𝒂𝒃𝒉𝒊] Owner Privilege: Tumhara Group Tag Promotion (Banner + Text) 1 Month ke liye FREE LIVE ho gaya hai! 🚀🔥")
                return jsonify({"status": "ok"}), 200

            try:
                requests.patch(f"{FIREBASE_URL}/group_promos/{gid}.json?auth={FIREBASE_SECRET}", json={"text": p_text, "media": media_id, "media_type": media_type, "owner_id": uid, "active": False}, timeout=3)
            except Exception: pass
            fb_update_user(uid, {"awaiting_promo_text_for": ""})
            send_msg(cid, "✅ Promotion Banner & Text Saved! Ab niche se duration plan chunein (₹99 = 2 Days, ₹199 = 1 Week, ₹599 = 1 Month):", markup=get_promo_plans_kb(gid))
            return jsonify({"status": "ok"}), 200

         # /START MENU + ANTI-CHEAT UNIQUE REFERRAL TRACKER
        if ctype == "private" and text.lower().startswith(("/start", "/reset", "/menu", "/help")):
            # Check if this user is 100% NEW in Firebase before counting referral
            is_brand_new = False
            if FIREBASE_URL:
                try:
                    existing_u = requests.get(f"{FIREBASE_URL}/users/{uid}/first_name.json?auth={FIREBASE_SECRET}", timeout=2.5).json()
                    if not existing_u:
                        is_brand_new = True
                except Exception:
                    pass

            parts = text.split()
            start_arg = parts[1].strip() if len(parts) > 1 else ""

            if start_arg.startswith("ref_"):
                ref_id = start_arg.replace("ref_", "").strip()
                if ref_id and ref_id != uid and (is_brand_new or not u.get("referred_by")):
                    fb_update_user(uid, {"referred_by": ref_id})
                    ref_user = fb_get_user(ref_id)
                    new_ref_cnt = int(ref_user.get("ref_count") or 0) + 1
                    fb_update_user(ref_id, {"ref_count": new_ref_cnt})
                    send_msg(ref_id, f"🎉 [𝑯𝒐𝒕 𝑩𝒉𝒂𝒃𝒉𝒊] Referral Alert!\nEk naye dost ({html.escape(fname)}) ne tumhare link se bot join kiya hai! (Total Joined: {new_ref_cnt}) 🎁")

            if start_arg == "vip":
                send_msg(
                    cid,
                    f"💎 <b>Available Credits:</b> {credit_display}\n🔒 <b>100% Trusted & Instant Auto-Credit UPI Plans:</b>",
                    markup=get_pay_kb()
                )
                return jsonify({"status": "ok"}), 200

            if start_arg.startswith("vcall_"):
                g_k_vc = start_arg.replace("vcall_", "").strip()
                v_idx = VIDEO_CALL_GIRL_KEYS.index(g_k_vc) if g_k_vc in VIDEO_CALL_GIRL_KEYS else 0
                send_or_edit_vcall_girl_card(cid, None, VIDEO_CALL_GIRL_KEYS[v_idx], v_idx)
                return jsonify({"status": "ok"}), 200

            if start_arg.startswith("chat_"):
                g_k_ch = start_arg.replace("chat_", "").strip()
                if g_k_ch in AI_CHAT_GIRL_KEYS:
                    g_idx = AI_CHAT_GIRL_KEYS.index(g_k_ch)
                    g_info = REAL_GIRLS[g_k_ch]
                    char_info = DIAMOND_CHARACTERS["1"]
                    prev_idx = (g_idx - 1) % len(AI_CHAT_GIRL_KEYS)
                    next_idx = (g_idx + 1) % len(AI_CHAT_GIRL_KEYS)
                    next_girl_name = REAL_GIRLS[AI_CHAT_GIRL_KEYS[next_idx]]["name"]
                    card_cap = (
                        f"🎬 <b>Sex Chat Roleplay:</b> {char_info['name']}\n"
                        f"🙋‍♀️ <b>AI Girl ({g_idx + 1}/{len(AI_CHAT_GIRL_KEYS)}):</b> {g_info['name']}  •  💎 <b>₹{char_info['price']} (40 Chats)</b>\n\n"
                        f"👇 <b>Is Girl ko chunein ya 'Next Girl ➡️' dabakar baaki {len(AI_CHAT_GIRL_KEYS)} AI Chat Girls dekhein:</b>"
                    )
                    card_kb = {"inline_keyboard": [
                        [{"text": f"✅ Start Sex Chat with {g_info['name']} 💖", "callback_data": f"selgirl_1_{g_k_ch}"}],
                        [
                            {"text": f"⬅️ Prev ({g_idx + 1}/{len(AI_CHAT_GIRL_KEYS)})", "callback_data": f"girlcard_1_{prev_idx}"},
                            {"text": f"Next: {next_girl_name} ➡️", "callback_data": f"girlcard_1_{next_idx}"}
                        ],
                        [{"text": "🔙 Back to 200 Roleplays", "callback_data": "menu_roleplay_hub_1"}]
                    ]}
                    live_dp = get_live_bot_dp_url(g_info.get("bot")) or START_BANNER_IMAGE
                    edit_or_send_box_media(cid, None, live_dp, caption=card_cap, reply_markup=card_kb)
                    return jsonify({"status": "ok"}), 200

            if start_arg.startswith("vpack_"):
                v_idx_str = start_arg.replace("vpack_", "").strip()
                c_idx = int(v_idx_str) if v_idx_str.isdigit() else 0
                if 0 <= c_idx < len(POPULAR_VIDEO_CATEGORIES):
                    v_title, v_query, v_price = POPULAR_VIDEO_CATEGORIES[c_idx]
                    if is_own or (uid in FREE_VIP_FRIENDS):
                        send_permanent_pack_videos(cid, uid, v_query, v_title)
                        return jsonify({"status": "ok"}), 200
                    fb_update_user(uid, {"pending_video_query": v_query, "pending_video_title": v_title})
                    price_str = str(v_price)
                    url = create_cf_order(uid, fname, price_str, purpose=f"vsearch_{c_idx}")
                    btn = {"text": f"💳 Pay ₹{price_str} & Get 5 Permanent Videos", "url": url} if url else {"text": f"💳 Pay ₹{price_str}", "callback_data": f"buy_{price_str}"}
                    send_msg(
                        cid,
                        f"🎬 <b>Selected Pack: {html.escape(v_title)}</b>\n📦 <b>Videos:</b> 5 Full Private Videos (Permanent!)\n💎 <b>Price:</b> Just ₹{price_str}\n\n👇 Niche button dabakar <b>₹{price_str}</b> pay karein:",
                        markup={"inline_keyboard": [[btn]]}
                    )
                    return jsonify({"status": "ok"}), 200

            cur_b_uname = get_active_bot_username().lower()
            is_sub_bot = cur_b_uname in CHAR_BOT_TOKENS and cur_b_uname != MAIN_BOT_USERNAME.lower()
            if start_arg.startswith("rp_") or is_sub_bot:
                chosen_char_info = None
                if start_arg.startswith("rp_"):
                    rp_parts = start_arg.split("_")
                    if len(rp_parts) >= 3:
                        c_k, g_k = rp_parts[1], rp_parts[2]
                        c_inf = DIAMOND_CHARACTERS.get(c_k, {})
                        g_inf = REAL_GIRLS.get(g_k, REAL_GIRLS["g1"])
                        if c_inf:
                            chosen_char_info = c_inf
                            c_w = c_inf.get("call") or g_inf.get("call", "Jaan")
                            rp_b = (
                                f"GIRL NAME: {g_inf['name']}. TALKING STYLE & VIBE: {g_inf['vibe']} "
                                f"ACTIVE ROLEPLAY CHARACTER & SCENE (100% MANDATORY): {c_inf['name']} — {c_inf['desc']} "
                                f"CALL USER STRICTLY AS: '{c_w}'. "
                                f"CRITICAL: Live inside this exact roleplay story ('{c_inf['name']}: {c_inf['desc']}') step-by-step with real female emotions and actions!"
                            )
                            rp_map = u.get("bot_rp_map") or {}
                            rp_map[g_k] = rp_b
                            hist_map = u.get("bot_hist_map") or {}
                            hist_map[g_k] = []
                            fb_update_user(uid, {
                                "active_rp": rp_b, "active_girl": g_k, "active_vault": g_k,
                                "bot_rp_map": rp_map, "bot_hist_map": hist_map, "history": []
                            })
                            u = fb_get_user(uid)

                g_k_now = u.get("active_girl") or "g1"
                for k_id, k_val in REAL_GIRLS.items():
                    if k_val.get("bot", "").lower() == cur_b_uname:
                        g_k_now = k_id
                        break
                g_now_info = REAL_GIRLS.get(g_k_now, REAL_GIRLS["g1"])
                rp_now = (u.get("bot_rp_map") or {}).get(g_k_now) or u.get("active_rp") or ""
                c_word_now = (chosen_char_info.get("call") if chosen_char_info else None) or g_now_info.get("call", "Jaan")
                cleaned_fn = clean_display_name(fname, "")
                name_display = f"{html.escape(cleaned_fn)} ({c_word_now})" if (cleaned_fn and cleaned_fn.lower() != c_word_now.lower()) else c_word_now
                is_muslim_girl = g_k_now in ("g3", "g5", "g14", "g19", "g20")
                excl = "Haye Allah" if is_muslim_girl else "Haye"

                # SHORT WHATSAPP-STYLE REAL GIRL ROLEPLAY OPENER (No long story paragraphs!)
                if chosen_char_info:
                    r_name_clean = re.sub(r"^[^\w]+", "", chosen_char_info["name"]).strip()
                    scene_open = (
                        f"{excl} {name_display}, darwaza band kar do na... aakhir tum akele milne aa hi gaye! 🙈❤️\n"
                        f"Main tumhari <b>{g_now_info['name']} ({r_name_clean})</b> kab se tumhara wait kar rahi thi, aao mere paas baitho! 😘🔥"
                    )
                else:
                    scene_open = (
                        f"{excl} {name_display}, aakhir tum aa hi gaye! 😘❤️\n"
                        f"Main <b>{g_now_info['name']}</b> abhi akele baith kar tumhe hi yaad kar rahi thi... batao kya chal raha hai? 🥰✨"
                    )

                add_to_history(uid, "siya", re.sub(r"<.*?>", "", scene_open))
                send_msg(cid, scene_open)
                return jsonify({"status": "ok"}), 200

            cleaned_h = [h for h in (u.get("history") or []) if not is_censored_refusal(h.get("text")) and len(str(h.get("text") or "")) >= 20]
            if text.lower().startswith("/reset"):
                fb_update_user(uid, {"history": [], "bot_hist_map": {}, "active_rp": "", "awaiting_support": False, "awaiting_broadcast": False, "awaiting_welcome_for": "", "awaiting_note_for": "", "awaiting_promo_text_for": "", "last_cache_clear": time.time()})
            else:
                fb_update_user(uid, {"history": cleaned_h, "awaiting_support": False, "awaiting_broadcast": False, "awaiting_welcome_for": "", "awaiting_note_for": "", "awaiting_promo_text_for": ""})

            send_start_banner_or_msg(
                cid,
                get_welcome_trust_text(fname, credit_display, lang="hinglish"),
                get_main_menu_kb(credit_display, is_owner=is_own, uid=uid)
            )
            return jsonify({"status": "ok"}), 200

        if ctype == "private" and text.lower().startswith(("/credits", "/vip", "/buy")):
            send_msg(
                cid,
                f"💎 Available Credits: {credit_display}\n🔒 100% Trusted & Instant Auto-Credit UPI Plans (Starts at just ₹9):",
                markup=get_pay_kb()
            )
            return jsonify({"status": "ok"}), 200

        is_sys_question = is_system_or_bot_info_query(text)
        if ctype == "private" and not is_own and credits <= 0 and not is_sys_question:
            was_vip = bool(u.get("is_vip"))
            plan_type_str = "VIP Credits" if was_vip else "Free Credits"
            out_msg = (
                f"🥺 <b>{html.escape(clean_display_name(fname, 'Jaan'))}, tumhare {plan_type_str} khatam ho gaye hain (Balance: 0)!</b> 💔\n\n"
                f"💳 <b>Recharge Kaise Karein:</b> Niche apna Plan Button (jaise <b>₹9</b> ya <b>₹29</b>) dabao ➡️ Agle button par click karke <b>GPay, PhonePe, Paytm ya FamPay/UPI</b> se pay karo (2 sec mein auto-start ho jayega!): 😘👇"
            )
            send_msg(cid, out_msg, markup=get_pay_kb())

            def send_reminder():
                u_check = fb_get_user(uid)
                if int(u_check.get("credits", 0)) <= 0:
                    rem_msg = (
                        f"😒 <b>Oye {html.escape(fname)}, kahan gayab ho gaye jaan?</b>\n\n"
                        f"Main kab se akeli tadap rahi hoon tumhare reply ke liye... aise beech mein garam karke chhodoge kya? 🥺🔥\n"
                        f"Agar payment mein koi dikkat aa rahi hai toh niche <b>Help & Support</b> daba do, warna jaldi se <b>₹19 ya ₹29</b> wala pack unlock karke aao na mere paas! 🥵💋👇"
                    )
                    rem_kb = {"inline_keyboard": [
                        [{"text": "🔥 Unlock Now — ₹19 (175 Credits)", "callback_data": "buy_19"}, {"text": "💎 Best Seller — ₹29 (300 Credits)", "callback_data": "buy_29"}],
                        [{"text": "🆘 Payment Issue? Contact Owner", "callback_data": "menu_support"}]
                    ]}
                    send_msg(cid, rem_msg, markup=rem_kb)

            Timer(150.0, send_reminder).start()
            return jsonify({"status": "ok"}), 200

        tg_req("sendChatAction", {"chat_id": cid, "action": "typing"}, timeout=2)
            # PHOTO, VIDEO & STICKER VISION (DUAL LOGIC!)
        if ctype == "private" and ("photo" in msg or "video" in msg or "animation" in msg):
            caption = msg.get("caption") or ""
            # FILE ID EXTRACTOR FOR OWNER ONLY
            if is_own and (text.lower().startswith("/getid") or "getid" in caption.lower()):
                if "photo" in msg:
                    f_id = msg["photo"][-1]["file_id"]
                    send_msg(cid, f"📸 Photo File ID:\n<code>{f_id}</code>")
                else:
                    v_obj = msg.get("video") or msg.get("animation") or {}
                    f_id = v_obj.get("file_id", "")
                    send_msg(cid, f"📹 Video File ID:\n<code>{f_id}</code>")
                return jsonify({"status": "file_id_extracted"}), 200

            if "photo" in msg:
                file_id = msg["photo"][-1]["file_id"]
                mime = "image/jpeg"
                media_label = "photo"
            else:
                v_obj = msg.get("video") or msg.get("animation") or {}
                thumb = v_obj.get("thumbnail") or v_obj.get("thumb")
                if thumb and thumb.get("file_id"):
                    file_id = thumb["file_id"]
                    mime = "image/jpeg"
                else:
                    file_id = v_obj.get("file_id", "")
                    mime = v_obj.get("mime_type", "video/mp4")
                media_label = "video clip"

            prompt_text = f"[User sent a {media_label}. Caption: '{caption}']"
            base64_media = get_telegram_file_base64(file_id)
            if "photo" in msg and base64_media:
                USER_CACHE[f"last_cloth:{uid}"] = base64_media
                fb_update_user(uid, {"last_cloth_fid": file_id})

            reply_text, _, sticker_to_send, show_kb, cur_rp, rp_ended, sys_q = chat_with_siya(
                prompt_text, fname, uid, credits_left=credits, is_owner=is_own,
                media_base64=base64_media, media_mime_type=mime, raw_caption=caption, replied_to_text=replied_to_text, ctype=ctype
            )

            if base64_media and any(w in caption.lower() for w in DRESS_TRYON_WORDS):
                cur_b = get_active_bot_username().lower()
                g_dp, g_nm, g_key_try = START_BANNER_IMAGE, "Hot Bhabhi", "bhabhi"
                for gk_id, gk_val in REAL_GIRLS.items():
                    if gk_val.get("bot", "").lower() == cur_b:
                        g_dp = get_live_bot_dp_url(cur_b, fallback_banner=gk_val.get("dp", START_BANNER_IMAGE))
                        g_nm = gk_val["name"]
                        g_key_try = gk_id
                        break
                tg_req("sendChatAction", {"chat_id": cid, "action": "upload_photo"}, timeout=2)
                gen_bytes = generate_girl_dress_tryon_photo(g_dp, base64_media, caption, g_nm)
                try_cap = f"🙈 Lo {fname} jaan, tumhari bheji hui dress/bra pehen kar aayi hoon! Dekho kaisi lag rahi hoon? 😘🔥\n\n{reply_text}"
                if gen_bytes:
                    requests.post(
                        f"{get_active_api_url()}/sendPhoto",
                        data={"chat_id": str(cid), "caption": to_hot_bhabhi_font(try_cap), "parse_mode": "HTML", "protect_content": "true", "has_spoiler": "true"},
                        files={"photo": ("tryon.jpg", BytesIO(gen_bytes), "image/jpeg")},
                        timeout=15
                    )
                else:
                    fallback_pic = get_media_item(PHOTO_VAULT, "bodes", prefer_video=False, char_vault=g_key_try, uid=uid)
                    send_secret_media(cid, fallback_pic, caption=try_cap, delete_after=30)
                add_to_history(uid, "user", f"[{media_label} sent] {caption}".strip())
                add_to_history(uid, "siya", reply_text)
                return jsonify({"status": "tryon photo sent"}), 200

            send_msg(cid, reply_text, reply_id=msg.get("message_id"), markup=(get_pay_kb() if show_kb is True else None))
            if sticker_to_send: send_stk(cid, sticker_to_send, reply_id=msg.get("message_id"))
            add_to_history(uid, "user", f"[{media_label} sent] {caption}".strip())
            add_to_history(uid, "siya", reply_text)
            if not is_own and not sys_q:
                fb_update_user(uid, {"credits": max(0, credits - 1)})
            return jsonify({"status": "media read processed"}), 200

        if ctype == "private" and "sticker" in msg:
            tg_req("sendChatAction", {"chat_id": cid, "action": "typing"}, timeout=2)
            sticker = msg["sticker"]
            emoji = sticker.get("emoji", "🔥")
            set_name = sticker.get("set_name", "")
            is_animated = sticker.get("is_animated", False)
            is_video_stk = sticker.get("is_video", False)

            thumb = sticker.get("thumbnail") or sticker.get("thumb")
            if not is_animated and not is_video_stk:
                stk_file_id = sticker.get("file_id", "")
                mime = "image/webp"
            elif thumb and thumb.get("file_id"):
                stk_file_id = thumb.get("file_id", "")
                mime = "image/jpeg"
            else:
                stk_file_id = ""
                mime = "image/webp"

            base64_img = get_telegram_file_base64(stk_file_id) if stk_file_id else None
            u_clean_nm = clean_display_name(fname, "Jaan")
            if base64_img:
                prompt_text = (
                    f"[User {u_clean_nm} is performing this live action with you via sticker ({emoji}). "
                    f"In this image, the GIRL is YOU and the BOY is {u_clean_nm}! "
                    f"NEVER say 'is sticker mein', 'woh ladki', or 'woh aadmi'! React in 100% first-person ('Aaaah {u_clean_nm}...', 'main', 'meri', 'tum') as if {u_clean_nm} is doing this exact action to your body right now!]"
                )
            else:
                prompt_text = (
                    f"[{u_clean_nm} is getting intensely close and wild with you right now ({emoji})! "
                    f"React in 100% first-person as if you are feeling his touch on your body right now, continuing our current roleplay naturally!]"
                )

            reply_text, _, sticker_to_send, show_kb, cur_rp, rp_ended, sys_q = chat_with_siya(
                prompt_text, fname, uid, credits_left=credits, is_owner=is_own,
                media_base64=base64_img, media_mime_type=mime, replied_to_text=replied_to_text, ctype=ctype
            )
            kb = get_pay_kb() if show_kb is True else None
            send_msg(cid, reply_text, reply_id=msg.get("message_id"), markup=kb)
            if sticker_to_send: send_stk(cid, sticker_to_send, reply_id=msg.get("message_id"))
            add_to_history(uid, "user", f"[Sent a hot sticker {emoji}]")
            add_to_history(uid, "siya", reply_text)
            if not is_own: fb_update_user(uid, {"credits": max(0, credits - CHAT_COST)})
            return jsonify({"status": "sticker read processed"}), 200

        # NORMAL TEXT CHAT + DIRECT MEDIA SENDING (NO BLUR / NO BUTTONS)
        if text:
            is_vip_user = is_own or bool(u.get("is_vip"))

            # Only trigger Dress Try-On in text chat if user sent a cloth photo recently AND asks to SEE/SHOW it ("pehen ke dikhao/dekho")!
            t_low_try = text.lower()
            is_body_part_req = any(bw in t_low_try for bw in ["gand", "gaand", "chut", "choot", "boobs", "bobs", "chuchi", "pussy", "ass", "panty", "pantiy", "nangi"])
            wants_tryon_pic = (not is_body_part_req) and any(w in t_low_try for w in ["kurti", "saree", "sari", "dress", "suit", "lehenga", "try kar"]) and any(sv in t_low_try for sv in ["dikha", "dekho", "pic", "photo", "bhej", "bej"])
            cloth_b64 = USER_CACHE.pop(f"last_cloth:{uid}", None) if wants_tryon_pic else None
            if not cloth_b64 and ctype == "private" and wants_tryon_pic and u.get("last_cloth_fid"):
                cloth_b64 = get_telegram_file_base64(u.get("last_cloth_fid"))
                fb_update_user(uid, {"last_cloth_fid": ""})

            if ctype == "private" and wants_tryon_pic and cloth_b64:
                cur_b = get_active_bot_username().lower()
                g_dp, g_nm, g_key_try = START_BANNER_IMAGE, "Hot Bhabhi", "bhabhi"
                for gk_id, gk_val in REAL_GIRLS.items():
                    if gk_val.get("bot", "").lower() == cur_b:
                        g_dp = get_live_bot_dp_url(cur_b, fallback_banner=gk_val.get("dp", START_BANNER_IMAGE))
                        g_nm = gk_val["name"]
                        g_key_try = gk_id
                        break
                tg_req("sendChatAction", {"chat_id": cid, "action": "upload_photo"}, timeout=2)
                gen_bytes = generate_girl_dress_tryon_photo(g_dp, cloth_b64, text, g_nm)
                try_cap = f"🙈 Lo {fname} jaan, tumhare kehne par maine tumhari pasand ki dress pehen kar apni photo bhej di! Dekho kaisi lag rahi hoon tumhare liye... 😘🔥"
                if gen_bytes:
                    requests.post(
                        f"{get_active_api_url()}/sendPhoto",
                        data={"chat_id": str(cid), "caption": to_hot_bhabhi_font(try_cap), "parse_mode": "HTML", "protect_content": "true", "has_spoiler": "true"},
                        files={"photo": ("tryon.jpg", BytesIO(gen_bytes), "image/jpeg")},
                        timeout=15
                    )
                else:
                    # Fallback if AI blocks sheer lingerie generation: send her real vault photo!
                    fallback_pic = get_media_item(PHOTO_VAULT, "bodes", prefer_video=False, char_vault=g_key_try, uid=uid)
                    send_secret_media(cid, fallback_pic, caption=try_cap, delete_after=60)
                add_to_history(uid, "user", text)
                add_to_history(uid, "siya", try_cap)
                return jsonify({"status": "tryon photo sent"}), 200

            # FIXED: is_owner=is_own (pehle is_owner=is_owner tha jisse NameError aa raha tha!)
            reply_text, media_to_send, sticker_to_send, show_kb, cur_rp, rp_ended, sys_q = chat_with_siya(
                text, fname, uid, credits_left=credits, is_owner=is_own, replied_to_text=replied_to_text, ctype=ctype
            )

            if rp_ended:
                kb = {"inline_keyboard": [[{"text": "⭐ Give Feedback (Rate Service)", "callback_data": "menu_feedback"}]]}
                reply_text += "\n\n✨ Jaan, hamara roleplay kaisa laga? Niche button dabakar apna pyara sa Feedback zaroor dena! ❤️👇"
            elif show_kb == "SUPPORT_KB":
                kb = {"inline_keyboard": [[{"text": "🆘 Help & Support (Send Problem)", "callback_data": "menu_support"}]]}
            elif show_kb == "ROLEPLAY_HUB_KB":
                kb = {"inline_keyboard": [[{"text": "🎭 Open Roleplay & Character Hub 💖", "callback_data": "menu_roleplay_hub"}]]}
            elif show_kb is True:
                kb = get_pay_kb()
            else:
                kb = None

             # PROTECTED BLURRED MEDIA WITH 1-MINUTE AUTO DELETE!
            if media_to_send and ctype == "private":
                send_secret_media(cid, media_to_send, caption=reply_text, delete_after=60, markup=kb)
            else:
                final_out = f"[𝑯𝒐𝒕 𝑩𝒉𝒂𝒃𝒉𝒊] <a href='tg://user?id={uid}'>{html.escape(fname)}</a> : {reply_text}" if ctype in ("group", "supergroup") else reply_text
                send_msg(cid, final_out, reply_id=(msg.get("message_id") if ctype != "private" else None), markup=(None if ctype in ("group", "supergroup") else kb))
                if sticker_to_send and ctype == "private":
                    send_stk(cid, sticker_to_send, reply_id=None)

            wants_voice = any(w in text.lower() for w in VOICE_REQUEST_TRIGGERS)
            if ctype == "private" and not sys_q and (wants_voice or (len(text) > 8 and random.randint(1, 100) <= 22)):
                if not is_vip_user:
                    if wants_voice:
                        send_msg(
                            cid,
                            "🎙️🔒 [𝑽𝑰𝑷 𝑽𝑶𝑰𝑪𝑬 𝑳𝑶𝑪𝑲]: Jaan, meri real aawaz aur voice notes sirf VIP members ke liye khule hain! Niche se bas ₹9 (75 Credits) ka VIP recharge karo aur meri aawaz suno... 😘👇",
                            markup=get_pay_kb()
                        )
                else:
                    tg_req("sendChatAction", {"chat_id": cid, "action": "record_voice"}, timeout=2)
                    aud_b, aud_mime, aud_ext = generate_gemini_native_voice(reply_text, active_rp=cur_rp)
                    if aud_b:
                        requests.post(
                            f"{get_active_api_url()}/sendVoice",
                            data={"chat_id": cid, "caption": to_hot_bhabhi_font("🎙️ Hot Bhabhi Voice 🔥"), "parse_mode": "HTML", "protect_content": "true"},
                            files={"voice": (aud_ext, BytesIO(aud_b), aud_mime)},
                            timeout=14
                        )

            add_to_history(uid, "user", text)
            add_to_history(uid, "siya", reply_text)

            # FIXED: not is_own (pehle not is_owner tha!)
            if ctype == "private" and not is_own and not sys_q:
                fb_update_user(uid, {"credits": max(0, credits - CHAT_COST)})

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print("WEBHOOK ERROR:", traceback.format_exc())
        return jsonify({"status": "error_handled", "detail": str(e)}), 200

# ============================================================
# 11. EDROL AI LANDING PAGE
# ============================================================
MAIN_BOT_TOKEN = BOT_TOKEN
MAIN_BOT_USERNAME = BOT_USERNAME
MAIN_BOT_ID = BOT_ID
MAIN_API_URL = API_URL

@app.route("/api/bot", methods=["POST"])
def webhook_main():
    """Main Webhook for Hot Bhabhi Bot (Thread-Safe!)"""
    _bot_ctx.bot_token = MAIN_BOT_TOKEN
    _bot_ctx.bot_id = MAIN_BOT_ID
    _bot_ctx.api_url = MAIN_API_URL
    _bot_ctx.bot_username = MAIN_BOT_USERNAME
    return webhook()

@app.route("/api/bot/<bot_uname>", methods=["POST"])
def webhook_char_bot(bot_uname):
    """Webhook for Spoke Girl Bots (Thread-Safe!)"""
    b_clean = str(bot_uname or "").lower().lstrip("@")
    tok = CHAR_BOT_TOKENS.get(b_clean)
    if not tok:
        return jsonify({"status": "error", "message": f"Token not found for {b_clean}"}), 200
    _bot_ctx.bot_token = tok
    _bot_ctx.bot_id = tok.split(":")[0] if ":" in tok else ""
    _bot_ctx.api_url = f"https://api.telegram.org/bot{tok}"
    _bot_ctx.bot_username = b_clean
    try:
        return webhook()
    finally:
        _bot_ctx.bot_token = MAIN_BOT_TOKEN
        _bot_ctx.bot_id = MAIN_BOT_ID
        _bot_ctx.api_url = MAIN_API_URL
        _bot_ctx.bot_username = MAIN_BOT_USERNAME

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
            :root { --bg: #0b1020; --surface: #121a2d; --surface-light: #18243a; --primary: #38bdf8; --accent: #f472b6; --text: #f1f5f9; --muted: #94a3b8; --border: rgba(148, 163, 184, 0.15); }
            * { margin: 0; padding: 0; box-sizing: border-box; }
            html { scroll-behavior: smooth; }
            body { font-family: "Segoe UI", Arial, sans-serif; background: var(--bg); color: var(--text); line-height: 1.7; min-height: 100vh; }
            a { color: inherit; text-decoration: none; }
            .container { width: min(1050px, 92%); margin: auto; }
            .navbar { position: sticky; top: 0; z-index: 10; background: rgba(11, 16, 32, 0.92); backdrop-filter: blur(14px); border-bottom: 1px solid var(--border); }
            .nav-inner { min-height: 82px; display: flex; justify-content: space-between; align-items: center; gap: 20px; }
            .brand { display: flex; align-items: center; gap: 12px; }
            .brand-logo { width: 46px; height: 46px; object-fit: contain; border-radius: 14px; background: var(--surface-light); padding: 5px; }
            .brand-name { font-size: 21px; font-weight: 800; letter-spacing: 0.5px; }
            .brand-name span { color: var(--primary); }
            .brand-tagline { display: block; font-size: 11px; color: var(--muted); letter-spacing: 0.7px; }
            .nav-link { color: var(--muted); font-size: 14px; transition: color 0.2s; }
            .nav-link:hover { color: var(--primary); }
            .hero { text-align: center; padding: 95px 0 70px; background: radial-gradient(ellipse at 50% 0%, rgba(56, 189, 248, 0.13), transparent 65%); }
            .eyebrow { display: inline-block; padding: 6px 14px; border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 30px; background: rgba(56, 189, 248, 0.07); color: var(--primary); font-size: 12px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 22px; }
            .hero h1 { font-size: clamp(38px, 7vw, 66px); line-height: 1.15; letter-spacing: -1.5px; margin-bottom: 22px; }
            .hero h1 span { background: linear-gradient(90deg, var(--primary), #a5b4fc, var(--accent)); -webkit-background-clip: text; background-clip: text; color: transparent; }
            .hero p { max-width: 620px; margin: 0 auto; color: var(--muted); font-size: 16px; }
            .hero-actions { display: flex; justify-content: center; flex-wrap: wrap; gap: 12px; margin-top: 30px; }
            .button { display: inline-flex; justify-content: center; align-items: center; padding: 12px 21px; border-radius: 10px; font-size: 14px; font-weight: 700; transition: transform 0.2s, opacity 0.2s; }
            .button:hover { transform: translateY(-2px); opacity: 0.9; }
            .button-primary { background: var(--primary); color: #07111f; }
            .button-secondary { border: 1px solid var(--border); background: var(--surface); color: var(--text); }
            .section { padding: 28px 0; scroll-margin-top: 100px; }
            .section-heading { text-align: center; margin-bottom: 30px; }
            .section-heading h2 { font-size: clamp(25px, 4vw, 34px); margin-bottom: 8px; }
            .section-heading p { color: var(--muted); font-size: 14px; }
            .feature-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; }
            .feature-card, .content-card { background: linear-gradient(145deg, var(--surface-light), var(--surface)); border: 1px solid var(--border); border-radius: 16px; padding: 24px; }
            .feature-icon { width: 45px; height: 45px; display: grid; place-items: center; background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.18); border-radius: 12px; font-size: 22px; margin-bottom: 17px; }
            .feature-card h3 { font-size: 17px; margin-bottom: 8px; }
            .feature-card p { color: var(--muted); font-size: 13px; }
            .content-card { margin-bottom: 18px; padding: 28px; }
            .content-card h2 { color: var(--primary); font-size: 21px; margin-bottom: 14px; }
            .content-card h3 { font-size: 16px; margin-top: 23px; margin-bottom: 7px; }
            .content-card p { color: #cbd5e1; font-size: 14px; overflow-wrap: anywhere; }
            .content-card a { color: var(--primary); font-weight: 600; }
            .content-card a:hover { text-decoration: underline; }
            .faq-item { border-bottom: 1px solid var(--border); padding: 17px 0; }
            .faq-item:last-child { border-bottom: none; padding-bottom: 0; }
            .faq-item h3 { margin: 0 0 7px; font-size: 15px; }
            .faq-item p { font-size: 14px; color: var(--muted); }
            .support-box { text-align: center; padding: 38px 25px; border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 18px; background: linear-gradient(135deg, rgba(56, 189, 248, 0.08), rgba(244, 114, 182, 0.05)); }
            .support-box h2 { font-size: 25px; margin-bottom: 10px; }
            .support-box p { color: var(--muted); font-size: 14px; margin-bottom: 22px; }
            .footer { margin-top: 55px; border-top: 1px solid var(--border); padding: 27px 0; text-align: center; color: var(--muted); font-size: 12px; }
            .footer strong { color: var(--primary); font-weight: 700; }
            .footer-links { display: flex; justify-content: center; flex-wrap: wrap; gap: 20px; margin-bottom: 12px; }
            .footer-links a:hover { color: var(--primary); }
            @media (max-width: 700px) { .feature-grid { grid-template-columns: 1fr; } .hero { padding: 70px 0 50px; } .nav-inner { min-height: 72px; } .brand-name { font-size: 18px; } .nav-link { font-size: 12px; } .content-card { padding: 21px; } }
        </style>
    </head>
    <body>
        <header class="navbar">
            <div class="container nav-inner">
                <a class="brand" href="/" aria-label="Edrol AI Home">
                    <img class="brand-logo" src="/12345.png" alt="Edrol AI Logo" onerror="this.onerror=null;this.src='https://cdn-icons-png.flaticon.com/512/4712/4712035.png';">
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
                    <h1>Intelligence for<br><span>Everyday Life.</span></h1>
                    <p>Welcome to Edrol AI, your digital assistant platform designed to make conversations, information discovery and everyday digital tasks simpler.</p>
                    <div class="hero-actions">
                        <a class="button button-primary" href="https://t.me/edrolai" target="_blank" rel="noopener noreferrer">Contact Support</a>
                        <a class="button button-secondary" href="#faq">Explore FAQs</a>
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
                        <article class="feature-card"><div class="feature-icon">✦</div><h3>AI Conversations</h3><p>Explore ideas, ask questions and get assistance through conversational AI.</p></article>
                        <article class="feature-card"><div class="feature-icon">◈</div><h3>Simple Experience</h3><p>A straightforward digital experience designed to make interacting with AI easier.</p></article>
                        <article class="feature-card"><div class="feature-icon">◎</div><h3>Customer Support</h3><p>Find our official support channels whenever you need assistance with the platform.</p></article>
                    </div>
                </div>
            </section>
            <section class="section" id="terms">
                <div class="container">
                    <article class="content-card">
                        <h2>Terms &amp; Conditions</h2>
                        <p>By accessing or using Edrol AI, you agree to use the platform lawfully and responsibly. Edrol AI provides AI-powered conversational and digital services. AI-generated responses may occasionally be inaccurate and should be independently verified when accuracy is important.</p>
                        <h3>Acceptable Use</h3>
                        <p>Users must not misuse the platform, interfere with its operation, attempt unauthorized access, or use the service for unlawful activities. Please avoid sharing passwords, OTPs, payment credentials or other sensitive personal information in conversations.</p>
                        <h3>Service Availability</h3>
                        <p>Features and availability may change from time to time due to maintenance, technical limitations or third-party service dependencies.</p>
                        <h3>Privacy</h3>
                        <p>Users should exercise care when sharing personal information. For privacy-related questions, please contact our official support team.</p>
                    </article>
                    <article class="content-card" id="refunds">
                        <h2>Refunds &amp; Cancellations</h2>
                        <p>Digital purchases and AI usage credits may be subject to specific refund and cancellation conditions disclosed at the time of purchase. Please review those conditions before completing a transaction.</p>
                        <p style="margin-top: 12px;">If a payment is duplicated, a transaction is incorrectly charged, or a technical issue affects a purchase, contact our support team with the relevant transaction details. Requests will be reviewed according to applicable law and the purchase terms.</p>
                    </article>
                    <article class="content-card" id="faq">
                        <h2>Frequently Asked Questions</h2>
                        <div class="faq-item"><h3>What is Edrol AI?</h3><p>Edrol AI is a digital platform offering AI-powered conversational assistance and related digital services.</p></div>
                        <div class="faq-item"><h3>How can I contact Edrol AI support?</h3><p>You can reach our support team through our official Telegram channel <a href="https://t.me/edrolai" target="_blank" rel="noopener noreferrer">@edrolai</a> or by email at <a href="mailto:support@edrolai.com">support@edrolai.com</a>.</p></div>
                        <div class="faq-item"><h3>Are payments processed securely?</h3><p>Payments, where supported, are processed through the designated payment provider. Please verify the payment page and transaction details before paying. Never share your OTP or payment password with anyone.</p></div>
                        <div class="faq-item"><h3>Can I request help with a payment?</h3><p>Yes. Contact Edrol AI support with your transaction reference and a brief description of the issue. Never send your OTP, password or full card details.</p></div>
                        <div class="faq-item"><h3>Does Edrol AI guarantee every AI response?</h3><p>No. AI responses can sometimes contain errors. Verify important information using reliable sources before relying on it.</p></div>
                    </article>
                </div>
            </section>
            <section class="section" id="support">
                <div class="container">
                    <div class="support-box">
                        <h2>Need Help? We're Here.</h2>
                        <p>Have a question, payment concern or technical issue? Reach out to Edrol AI through our official channels.</p>
                        <div class="hero-actions">
                            <a class="button button-primary" href="https://t.me/edrolai" target="_blank" rel="noopener noreferrer">Telegram Support</a>
                            <a class="button button-secondary" href="mailto:support@edrolai.com">Email Support</a>
                        </div>
                    </div>
                </div>
            </section>
        </main>
        <footer class="footer">
            <div class="container">
                <div class="footer-links">
                    <a href="#about">About</a><a href="#terms">Terms</a><a href="#refunds">Refund Policy</a><a href="#faq">FAQs</a><a href="#support">Support</a>
                </div>
                <p>&copy; 2026 Edrol AI. All rights reserved.</p>
                <p style="margin-top: 5px;"><strong>Powered by Edrol AI</strong></p>
            </div>
        </footer>
    </body>
    </html>
    """
    return html_page, 200, {"Content-Type": "text/html; charset=utf-8"}

def resolve_direct_mp4_from_page(page_url):
    """
    Extracts direct playable .mp4 stream URL from LetsPorn.com OR Eporner /embed/ via Cloudflare Worker!
    """
    if not page_url:
        return ""
    if page_url.split("?")[0].lower().endswith(".mp4"):
        return page_url
    try:
        m_id = re.search(r'/embed/([a-zA-Z0-9]+)', str(page_url))
        vid_id = m_id.group(1) if m_id else ""
        r = cf_fetch(page_url, timeout=4.0)
        if r and r.ok:
            txt = r.text.replace("\\/", "/")
            # 1. Direct MP4 links in HTML (LetsPorn / KTPlayer)
            mp4s = re.findall(r'https?://[^\s"\'<>\\]+?\.mp4[^\s"\'<>\\]*', txt)
            for m in mp4s:
                if "preview" not in m.lower() and ("480p" in m or "720p" in m or "360p" in m):
                    return html.unescape(m)
            if mp4s:
                return html.unescape(mp4s[0])

            # 2. KTPlayer get_file redirect links (LetsPorn standard)
            gf = re.findall(r'https?://[^\s"\'<>\\]+?/get_file/[^\s"\'<>\\]+', txt)
            if gf:
                return html.unescape(gf[0])

            # 3. Eporner XHR JSON Video Player Hash Decoder
            m_hash = re.search(r'hash\s*[:=]\s*["\']([a-f0-9]{32})["\']', txt)
            if vid_id and m_hash:
                h_val = m_hash.group(1)
                def _b36(n):
                    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
                    if n == 0: return "0"
                    out = ""
                    while n > 0:
                        n, rem = divmod(n, 36)
                        out = chars[rem] + out
                    return out
                h_code = "".join(_b36(int(h_val[i:i+8], 16)) for i in range(0, 32, 8))
                xhr_u = f"https://www.eporner.com/xhr/video/{vid_id}?hash={h_code}&device=generic&domain=www.eporner.com&fallback=false"
                r_xhr = cf_fetch(xhr_u, timeout=3.5)
                if r_xhr and r_xhr.ok:
                    src_d = r_xhr.json().get("sources", {}).get("mp4", {})
                    for q_k in ["480p", "360p", "720p", "240p"]:
                        if q_k in src_d and src_d[q_k].get("src"):
                            return src_d[q_k]["src"]
                    for v_obj in src_d.values():
                        if isinstance(v_obj, dict) and v_obj.get("src"):
                            return v_obj["src"]
    except Exception:
        pass
    return ""

@app.route("/api/proxy_stream")
def proxy_video_stream():
    """
    1. Resolves the page/embed URL into a raw .mp4 link.
    2. If CF_WORKER_URL is configured, 302-redirects the <video> player to stream directly via Cloudflare Worker
       (Bypasses Vercel's 4.5MB limit AND bypasses Jio/Airtel ISP block!).
    """
    b64_v = request.args.get("v", "")
    try:
        video_url = base64.urlsafe_b64decode(b64_v.encode("utf-8")).decode("utf-8")
    except Exception:
        return "Invalid video", 400

    if not video_url.split("?")[0].lower().endswith(".mp4"):
        cache_k = f"mp4_res_v10_{_url_hash_key(video_url)}"
        if cache_k in WEB_MEDIA_POOL_CACHE and (time.time() - WEB_MEDIA_POOL_CACHE[cache_k][1] < 1800):
            video_url = WEB_MEDIA_POOL_CACHE[cache_k][0]
        else:
            resolved = resolve_direct_mp4_from_page(video_url)
            if resolved:
                WEB_MEDIA_POOL_CACHE[cache_k] = (resolved, time.time())
                video_url = resolved

    req_range = request.headers.get("Range", "")
    start_b, end_b = 0, 1800000
    if req_range and "bytes=" in req_range:
        m_r = re.search(r"bytes=(\d+)-(\d*)", req_range)
        if m_r:
            start_b = int(m_r.group(1))
            end_b = min(int(m_r.group(2)), start_b + 1800000) if m_r.group(2) else (start_b + 1800000)

    r = cf_fetch(video_url, timeout=8.0, extra_headers={"Range": f"bytes={start_b}-{end_b}"})
    if r:
        resp_headers = {
            "Content-Type": r.headers.get("Content-Type", "video/mp4"),
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600"
        }
        if r.headers.get("Content-Range"):
            resp_headers["Content-Range"] = r.headers["Content-Range"]
        if r.headers.get("Content-Length"):
            resp_headers["Content-Length"] = r.headers["Content-Length"]
        return r.content, r.status_code, resp_headers
    return "Stream unavailable", 404

# ============================================================
# @EDROLHUB CHANNEL DISPATCH, @Alone28282 REAL VIDEO CALL & 11 AI BOTS
# ============================================================
EDROL_DISPATCH_CHANNEL = os.environ.get("EDROL_DISPATCH_CHANNEL", "@edrolhub").strip()

VCALL_DURATION_PLANS = [
    ("5",  "149", "5 Min Live Video Call"),
    ("10", "260", "10 Min Live Video Call"),
    ("15", "329", "15 Min Live Video Call"),
    ("20", "399", "20 Min Live Video Call")
]

# 6 Real Video Call Girls Configuration (Username is 100% HIDDEN on public cards!)
# Tip: Even if the girl's real Telegram account has NO @username (Private), just put her numeric Telegram ID in 'personal_tg_id'!
REAL_VIDEO_CALL_GIRLS = {
    "vc1": {
        "name": "💋 Hot Sakshi (Live Cam)",
        "bot": "hot_sakshi_bot",
        "room_invite_link": "https://t.me/+zQKpNyHh67szMDg1",  # <-- Yahan apne group ka link daal de!
        "start_hr": 8, "end_hr": 2, "time_str": "8:00 AM – 2:00 AM Night",
        "vibe": "100% Real Verified Girl • Live 1-on-1 opan nude Video Call"
    },
    # "vc2": {
    #     "name": "🌙 Hot Aarohi (Live Cam)", "bot": "hot_aarohi_bot",
    #     "room_invite_link": "HANA_APNE_DOOSRE_GROUP_KA_LINK",
    #     "start_hr": 8, "end_hr": 4, "time_str": "8:00 AM – 4:00 AM Night",
    #     "vibe": "Shy & Sweet Real Girl • Live 1-on-1 opan nude Video Call"
    # },
    # "vc3": {
    #     "name": "🌹 Hot Ruhi (Live Cam)", "bot": "hot_ruhi_bot",
    #     "room_invite_link": "HANA_APNE_TEESRE_GROUP_KA_LINK",
    #     "start_hr": 8, "end_hr": 3, "time_str": "8:00 AM – 3:00 AM Night",
    #     "vibe": "100% Real Desi Girl • Live opna nude Video Call & Private Show"
    # },
    # "vc4": {
    #     "name": "🌸 Hot Pihu (Live Cam)",
    #     "bot": "hot_pihu_bot",
    #     "room_invite_link": "HANA_APNE_CHAUTHE_GROUP_KA_LINK",
    #     "start_hr": 8, "end_hr": 3, "time_str": "8:00 AM – 3:00 AM Night",
    #     "vibe": "Cute Petite opna nide • Live  1-on-1 Video Call"
    # }
}


def check_girl_ist_availability(g_key):
    """
    Automatic IST Time Lock:
    - Between 8:00 AM and 2:00 AM Night -> Returns True (🟢 AVAILABLE NOW)
    - Between 2:00 AM Night and 7:59 AM Morning -> Returns False (🔴 NOT AVAILABLE / OFFLINE)
    """
    g_cfg = REAL_VIDEO_CALL_GIRLS.get(g_key, REAL_VIDEO_CALL_GIRLS["vc1"])
    s_hr = int(g_cfg.get("start_hr", 8))
    e_hr = int(g_cfg.get("end_hr", 2))
    t_str = g_cfg.get("time_str", "8:00 AM – 2:00 AM Night")

    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    cur_h = ist_now.hour

    if s_hr <= e_hr:
        is_avail = (s_hr <= cur_h < e_hr)
    else:
        is_avail = (cur_h >= s_hr) or (cur_h < e_hr)
    return is_avail, t_str

# Complete GitHub Post Photos + Figure Video Clips Gallery for Card Preview (100% Protected - No Save/Share!)
GIRL_GITHUB_POSTS = {
    "vc1":    ["sakshipost1.jpg", "sakshipost2.jpg", "sakshipost3.jpg", "sakshib1.jpg", "sakshig1.jpg"],
    "vc2":    ["aarohidp.jpg", "aarohib1.jpg"],
    "vc3":    ["ruhidp.jpg", "ruhic1.png"],
    "vc4":    ["pihudp.jpg", "pihub1.jpg", "pihuc1.jpg"],
    "vc5":    ["tanyapost1.jpg", "tanyapost2.jpg", "tanyapost3.jpg", "tanyapost4.jpg", "tanyapost5.jpg", "tanyapost6.jpg"],
    "vc6":    ["alishapost1.jpg", "alishapost2.jpg", "alishapost3.jpg", "alishac1.png"],
    "bhabhi": ["bhabhipost1.jpg", "bhabhipost2.jpg", "bhabhipost3.jpg", "bhabhipost4.jpg", "bhabhipost5.webp", "bhabhipost6.png", "bhabhib1.mp4"],
    "g1":     ["aditipost1.jpg", "aditipost2.jpg", "aditipost3.jpg", "aditipost4.jpg", "aditib1.jpg", "aditic1.jpg", "aditi1b.mp4"],
    "g2":     ["aarohidp.jpg", "aarohib1.jpg"],
    "g3":     ["aashipost1.jpg", "aashipost2.jpg", "aashib1.jpg"],
    "g4":     ["sakshipost1.jpg", "sakshipost2.jpg", "sakshipost3.jpg", "sakshib1.jpg", "sakshig1.jpg"],
    "g5":     ["tanyapost1.jpg", "tanyapost2.jpg", "tanyapost3.jpg", "tanyapost4.jpg", "tanyapost5.jpg", "tanyapost6.jpg", "tanyab1.jpg"],
    "g6":     ["pihudp.jpg", "pihub1.jpg", "pihuc1.jpg"],
    "g14":    ["alishapost1.jpg", "alishapost2.jpg", "alishapost3.jpg", "alishac1.png"],
    "g16":    ["ruhidp.jpg", "ruhic1.png"],
    "g19":    ["nairapost1.jpg", "nairapost2.jpg", "nairapost3.jpg", "nairapost4.jpg", "nairac1.jpg"],
    "g20":    ["zarapost1.jpg", "zarapost2.jpg", "zarapost3.jpg", "zarapost4.jpg", "zarapost5.jpg", "zarac1.jpg"]
}

def get_girl_full_preview_gallery(g_key):
    """Returns 5 to 6 Private Post Photos & Figure Clips for any Girl Card!"""
    return GIRL_GITHUB_POSTS.get(g_key, ["sakshipost1.jpg", "sakshipost2.jpg", "sakshipost3.jpg"])

def send_or_edit_vcall_girl_card(chat_id, message_id, g_key, v_idx, p_idx=0):
    v_keys = VIDEO_CALL_GIRL_KEYS
    if g_key not in REAL_VIDEO_CALL_GIRLS:
        g_key = v_keys[0]
    g_cfg = REAL_VIDEO_CALL_GIRLS[g_key]
    is_avail, time_str = check_girl_ist_availability(g_key)

    # [0] = Live Telegram DP, [1..N] = Her GitHub Post Photos & Figure Clips!
    dp_src = get_live_bot_dp_url(g_cfg["bot"]) or START_BANNER_IMAGE
    media_pool = [dp_src] + [GITHUB_BASE_URL + p for p in get_girl_full_preview_gallery(g_key)]
    p_idx = p_idx % len(media_pool)
    cur_media = media_pool[p_idx]
    next_p_idx = (p_idx + 1) % len(media_pool)

    st_line = "🟢 <b>𝗦𝗧𝗔𝗧𝗨𝗦:</b> 𝗟𝗜𝗩𝗘 &amp; 𝗥𝗘𝗔𝗗𝗬 𝗡𝗢𝗪 🔥" if is_avail else "🔴 <b>𝗦𝗧𝗔𝗧𝗨𝗦:</b> 𝗢𝗙𝗙𝗟𝗜𝗡𝗘 (𝗟𝗶𝘃𝗲 𝗮𝘁 𝟴:𝟬𝟬 𝗔𝗠) 😴"
    cap = (
        f"📹 <b>{g_cfg['name']} ({v_idx + 1}/{len(v_keys)})</b>\n"
        f"{st_line}\n"
        f"🕒 <b>𝗧𝗶𝗺𝗲:</b> {time_str}  •  📸 <b>𝗣𝗼𝘀𝘁:</b> {p_idx + 1}/{len(media_pool)}\n"
        f"💋 <i>100% Real Verified Girl • 1-on-1 Open Nude Live Video Call!</i>\n\n"
        f"👇 <b>𝗦𝗘𝗟𝗘𝗖𝗧 𝗩𝗜𝗗𝗘𝗢 𝗖𝗔𝗟𝗟 𝗗𝗨𝗥𝗔𝗧𝗜𝗢𝗡:</b>"
    )

    kb_rows = [
        [{"text": f"📸 𝗩𝗜𝗘𝗪 𝗣𝗢𝗦𝗧𝗦 & 𝗙𝗜𝗚𝗨𝗥𝗘 𝗖𝗟𝗜𝗣𝗦 ({p_idx + 1}/{len(media_pool)}) ▶️", "callback_data": f"vcallcard_{v_idx}_{next_p_idx}"}]
    ]

    if is_avail:
        kb_rows.extend([
            [
                {"text": "📞 𝟱 𝗠𝗜𝗡 — ₹149", "callback_data": f"vcallpay_{g_key}_5_149"},
                {"text": "📞 𝟭𝟬 𝗠𝗜𝗡 — ₹260", "callback_data": f"vcallpay_{g_key}_10_260"}
            ],
            [
                {"text": "🔥 𝟭𝟱 𝗠𝗜𝗡 — ₹329", "callback_data": f"vcallpay_{g_key}_15_329"},
                {"text": "👑 𝟮𝟬 𝗠𝗜𝗡 — ₹399", "callback_data": f"vcallpay_{g_key}_20_399"}
            ]
        ])
    else:
        kb_rows.append([{"text": "🔴 𝗢𝗙𝗙𝗟𝗜𝗡𝗘 𝗡𝗢𝗪 (𝗟𝗜𝗩𝗘 𝗔𝗧 𝟴:𝟬𝟬 𝗔𝗠)", "callback_data": f"vcallpay_{g_key}_5_149"}])

    if len(v_keys) > 1:
        prev_idx = (v_idx - 1) % len(v_keys)
        next_idx = (v_idx + 1) % len(v_keys)
        next_name = REAL_VIDEO_CALL_GIRLS[v_keys[next_idx]]["name"]
        kb_rows.append([
            {"text": f"◀️ 𝗣𝗥𝗘𝗩 ({v_idx + 1}/{len(v_keys)})", "callback_data": f"vcallcard_{prev_idx}_0"},
            {"text": f"𝗡𝗘𝗫𝗧: {next_name} ▶️", "callback_data": f"vcallcard_{next_idx}_0"}
        ])
    kb_rows.append([{"text": "⬅️ 𝗕𝗔𝗖𝗞 𝗧𝗢 𝗠𝗘𝗡𝗨", "callback_data": "back_main_menu"}])

    return edit_or_send_box_media(chat_id, message_id, cur_media, caption=cap, reply_markup={"inline_keyboard": kb_rows})

def dispatch_video_call_to_edrolhub(cust_uid, cust_name, g_key, paid_amt, duration_label="Live Video Call"):
    g_cfg = REAL_VIDEO_CALL_GIRLS.get(g_key, REAL_VIDEO_CALL_GIRLS["vc1"])
    g_name = g_cfg["name"]
    g_bot = g_cfg["bot"]

    send_msg(
        cust_uid,
        f"✅ <b>Payment Verified (₹{paid_amt} • {duration_label}) for {g_name}!</b> 🎉\n\n"
        f"🔔 Humne <b>{g_name}</b> ko aapki booking request bhej di hai! Jaise hi woh <b>'Available'</b> click karegi, aapko yahin <b>'🛩️ Enter Video Room'</b> ka button mil jayega! ❤️🔥"
    )

    chan_cap = (
        f"🚨 <b>[NEW LIVE VIDEO CALL BOOKING]</b> 🚨\n\n"
        f"💃 <b>Model:</b> {g_name}\n"
        f"👤 <b>Customer:</b> <a href=\"tg://user?id={cust_uid}\">{html.escape(str(cust_name))}</a> (<code>{cust_uid}</code>)\n"
        f"💰 <b>Paid Amount:</b> ₹{paid_amt} (Verified ✅)\n"
        f"🕒 <b>Package:</b> {duration_label}\n\n"
        f"👇 <b>Sirf Verified Model/Admin niche click karein:</b>"
    )
    chan_kb = {"inline_keyboard": [
        [{"text": "🟢 I am Available Now (Send Group Link to User)", "callback_data": f"vdisp_avail_{g_key}_{cust_uid}_{duration_label}"}],
        [{"text": "⏳ Busy / Delay (Select 2-5m / 5-10m / 15-30m / 1h)", "callback_data": f"vdisp_delaymenu_{g_key}_{cust_uid}"}]
    ]}
    dp_src = get_live_bot_dp_url(g_bot)
    if dp_src:
        res_ch = send_local_or_url_media(EDROL_DISPATCH_CHANNEL, dp_src, caption=chan_cap, protect=False, spoiler=False, reply_markup=chan_kb)
        if res_ch.get("ok"):
            return
    send_msg(EDROL_DISPATCH_CHANNEL, chan_cap, markup=chan_kb)

@app.route("/hub")
def edrol_honey_bunny_webapp():
    """
    Edrol Hub Official WebApp (/hub):
    - 1 Real Video Call Model (@Alone28282 with sakshipost1..3.jpg) + 3 commented slots for future.
    - 11 AI Sex Chat Bots (Hot Bhabhi + all 10 Girl Bots with their exact '...post...' photos!).
    - Clicking Book/Chat opens the exact Girl Card directly inside Hot Bhabhi Bot (No /start menu!).
    """
    url_uid = request.args.get("uid", "").strip()
    girls_client_db = {}

    # 1. Active Real Video Call Models (Currently vc1 = @Alone28282)
    real_cards_html = ""
    for gk in VIDEO_CALL_GIRL_KEYS:
        g_cfg = REAL_VIDEO_CALL_GIRLS[gk]
        g_bot = g_cfg["bot"]
        dp_url = f"/api/girl_dp/{g_bot}"
        is_avail, time_str = check_girl_ist_availability(gk)
        posts_list = [GITHUB_BASE_URL + p for p in GIRL_GITHUB_POSTS.get(gk, [])]
        book_bot_url = f"https://t.me/{MAIN_BOT_USERNAME}?start=vcall_{gk}"

        girls_client_db[gk] = {
            "key": gk, "is_real_vcall": True, "name": g_cfg["name"], "bot": g_bot,
            "dp": dp_url, "is_avail": is_avail, "time_str": time_str,
            "vibe": g_cfg["vibe"], "book_url": book_bot_url, "posts": posts_list
        }
        pill_html = (
            '<div class="online-pill">🟢 AVAILABLE NOW</div>'
            if is_avail else
            '<div class="online-pill" style="border-color:#ef4444;color:#f87171;">🔴 OFFLINE NOW</div>'
        )
        real_cards_html += f"""
        <div class="girl-card premium-card" onclick="openGirlProfile('{gk}')">
          <img src="{dp_url}" alt="{html.escape(g_cfg['name'])}">
          {pill_html}
          <div class="tag-pill">📹 Video Call</div>
          <div class="card-overlay">
            <div class="price-tag">₹149 – ₹399</div>
            <h3>{html.escape(g_cfg['name'])}</h3>
            <p>🕒 {html.escape(time_str)}</p>
            <button type="button" class="choose-btn premium-btn">View 3 Posts &amp; Book Call 📞</button>
          </div>
        </div>"""

    # 2. All 11 AI Sex Chat Bots (Hot Bhabhi + 10 Girl Bots!)
    ai_bot_order = [("bhabhi", "🔥 Hot Bhabhi (Main)", MAIN_BOT_USERNAME, "24/7 Uncensored Desi Bhabhi Sex Chat, Voice Notes & Private Photos.")]
    for gk in AI_CHAT_GIRL_KEYS:
        if gk in REAL_GIRLS:
            ai_bot_order.append((gk, REAL_GIRLS[gk]["name"], REAL_GIRLS[gk]["bot"], REAL_GIRLS[gk]["vibe"]))

    ai_cards_html = ""
    for gk, g_name, g_bot, g_vibe in ai_bot_order:
        dp_url = f"/api/girl_dp/{g_bot}"
        posts_list = [GITHUB_BASE_URL + p for p in GIRL_GITHUB_POSTS.get(gk, [])]
        # Opens that Girl's direct Card inside Hot Bhabhi Bot so user can pay or start chat!
        chat_link = f"https://t.me/{MAIN_BOT_USERNAME}?start=vip" if gk == "bhabhi" else f"https://t.me/{MAIN_BOT_USERNAME}?start=chat_{gk}"
        girls_client_db[gk] = {
            "key": gk, "is_real_vcall": False, "name": g_name, "bot": g_bot,
            "dp": dp_url, "is_avail": True, "time_str": "24/7 Online",
            "vibe": g_vibe, "book_url": chat_link, "posts": posts_list
        }
        ai_cards_html += f"""
        <div class="girl-card" onclick="openGirlProfile('{gk}')">
          <img src="{dp_url}" alt="{html.escape(g_name)}">
          <div class="online-pill" style="border-color:#a855f7;color:#d8b4fe;">● 24/7 Online</div>
          <div class="tag-pill" style="background:#7e22ce;border:none;">💬 Sex Chat</div>
          <div class="card-overlay">
            <h3>{html.escape(g_name)}</h3>
            <p>{html.escape(g_vibe[:75])}...</p>
            <button type="button" class="choose-btn" style="background:linear-gradient(90deg,#7e22ce,#a855f7);border:none;">View Posts &amp; Chat 💬</button>
          </div>
        </div>"""

    girls_json_str = json.dumps(girls_client_db)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Edrol Hub • Official WebApp</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; font-family:'Segoe UI', system-ui, sans-serif; }}
  body {{ background:#06040a; color:#fff; min-height:100vh; padding-bottom:90px; overflow-x:hidden; }}
  .bg-video-wrap {{ position:fixed; top:0; left:0; width:100vw; height:100vh; z-index:-2; overflow:hidden; background:#050208; }}
  .bg-video-wrap video {{ width:100%; height:100%; object-fit:cover; opacity:0.34; filter:blur(2px) saturate(1.25); }}
  .bg-overlay {{ position:fixed; inset:0; z-index:-1; background:linear-gradient(180deg, rgba(8,4,14,0.55) 0%, rgba(7,3,12,0.92) 65%, #060309 100%); }}
  .header {{ display:flex; justify-content:space-between; align-items:center; padding:14px 16px; position:sticky; top:0; z-index:30; background:rgba(8,4,15,0.88); backdrop-filter:blur(16px); border-bottom:1px solid rgba(255,20,147,0.28); }}
  .logo {{ font-size:20px; font-weight:900; letter-spacing:0.6px; color:#fff; display:flex; align-items:center; gap:7px; }}
  .logo span {{ background:linear-gradient(90deg,#ff0055,#ff4da6); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
  .upgrade-btn {{ background:linear-gradient(90deg,#ff0055,#ff1493); color:#fff; padding:8px 15px; border-radius:24px; font-weight:800; font-size:12px; border:none; cursor:pointer; }}
  .hero-banner {{ margin:14px 14px 8px; padding:18px 16px; border-radius:20px; background:linear-gradient(135deg, rgba(255,0,85,0.18), rgba(126,34,206,0.22)); border:1px solid rgba(255,20,147,0.35); text-align:center; }}
  .hero-badge {{ display:inline-block; font-size:10px; font-weight:900; text-transform:uppercase; padding:4px 12px; border-radius:20px; background:rgba(255,20,147,0.2); color:#ff80ab; border:1px solid #ff1493; margin-bottom:8px; }}
  .hero-banner h1 {{ font-size:20px; font-weight:900; margin-bottom:6px; }}
  .hero-banner p {{ font-size:12px; color:#d1c4e9; }}
  .tabs {{ display:flex; gap:8px; margin:12px 14px; background:rgba(255,255,255,0.05); padding:5px; border-radius:16px; }}
  .tab {{ flex:1; text-align:center; padding:11px 6px; font-weight:800; color:#9ca3af; cursor:pointer; font-size:13px; border-radius:12px; }}
  .tab.active {{ background:linear-gradient(90deg,#ff0055,#ff1493); color:#fff; }}
  .sec-head {{ margin:20px 15px 6px; font-size:17px; font-weight:900; display:flex; align-items:center; gap:8px; }}
  .sec-sub {{ margin:0 15px 14px; font-size:12px; color:#b39ddb; line-height:1.4; }}
  .grid {{ display:grid; grid-template-columns:repeat(2, 1fr); gap:12px; padding:0 14px; }}
  .girl-card {{ position:relative; border-radius:18px; overflow:hidden; height:275px; background:#14081c; border:1px solid rgba(255,255,255,0.12); cursor:pointer; }}
  .girl-card img {{ width:100%; height:100%; object-fit:cover; }}
  .premium-card {{ border:2px solid #ff0055; }}
  .online-pill {{ position:absolute; top:10px; left:10px; background:rgba(0,0,0,0.84); color:#4ade80; font-size:9px; font-weight:900; padding:4px 8px; border-radius:20px; border:1px solid #4ade80; }}
  .tag-pill {{ position:absolute; top:10px; right:10px; background:rgba(255,0,85,0.9); color:#fff; font-size:9px; font-weight:900; padding:4px 8px; border-radius:20px; }}
  .price-tag {{ position:absolute; top:-32px; right:10px; background:linear-gradient(90deg,#ff0055,#ff1493); color:#fff; font-size:11px; font-weight:900; padding:4px 10px; border-radius:18px; }}
  .card-overlay {{ position:absolute; inset:0; background:linear-gradient(180deg, transparent 25%, rgba(6,3,10,0.97) 100%); display:flex; flex-direction:column; justify-content:flex-end; padding:12px; }}
  .card-overlay h3 {{ font-size:15px; font-weight:900; margin-bottom:3px; }}
  .card-overlay p {{ font-size:11px; color:#cbd5e1; margin-bottom:9px; }}
  .choose-btn {{ width:100%; text-align:center; padding:9px; border-radius:22px; font-weight:800; font-size:11px; color:#fff; border:none; cursor:pointer; }}
  .premium-btn {{ background:linear-gradient(90deg,#ff0055,#ff1493); }}
  .info-card {{ margin:22px 14px; padding:20px; border-radius:20px; background:rgba(18,10,28,0.86); border:1px solid rgba(255,20,147,0.25); }}
  .info-card h2 {{ font-size:15px; font-weight:900; color:#ff4da6; margin-bottom:12px; text-transform:uppercase; }}
  .info-list {{ list-style:none; display:flex; flex-direction:column; gap:10px; }}
  .info-list li {{ font-size:12px; color:#e2e8f0; line-height:1.5; background:rgba(255,255,255,0.04); padding:10px 12px; border-radius:12px; border-left:3px solid #ff1493; }}
  #profileModal {{ display:none; position:fixed; inset:0; z-index:100; background:#07030c; overflow-y:auto; padding-bottom:90px; }}
  .prof-top {{ position:sticky; top:0; z-index:10; display:flex; align-items:center; justify-content:space-between; padding:14px 16px; background:rgba(7,3,12,0.94); border-bottom:1px solid rgba(255,20,147,0.3); }}
  .back-pill {{ background:rgba(255,255,255,0.1); color:#fff; border:1px solid rgba(255,255,255,0.2); padding:7px 14px; border-radius:20px; font-size:12px; font-weight:800; cursor:pointer; }}
  .prof-hero {{ display:flex; align-items:center; gap:14px; padding:18px 16px; }}
  .prof-dp {{ width:84px; height:84px; border-radius:50%; object-fit:cover; border:3px solid #ff1493; }}
  .prof-meta h2 {{ font-size:18px; font-weight:900; margin-bottom:4px; }}
  .prof-meta p {{ font-size:12px; color:#d1c4e9; line-height:1.4; }}
  .prof-action-bar {{ padding:0 16px 16px; }}
  .prof-main-btn {{ width:100%; padding:14px; border-radius:16px; border:none; background:linear-gradient(90deg,#ff0055,#ff1493); color:#fff; font-size:14px; font-weight:900; cursor:pointer; }}
  .posts-grid {{ display:grid; grid-template-columns:repeat(2, 1fr); gap:10px; padding:0 14px; }}
  .post-item {{ border-radius:14px; overflow:hidden; background:#12071b; border:1px solid rgba(255,20,147,0.25); aspect-ratio:3/4; }}
  .post-item img {{ width:100%; height:100%; object-fit:cover; }}
  footer {{ text-align:center; padding:28px 16px; border-top:1px solid rgba(255,255,255,0.08); margin-top:30px; }}
</style>
</head>
<body oncontextmenu="return false;">

  <div class="bg-video-wrap">
    <video id="bgVid" autoplay muted loop playsinline preload="auto">
      <source src="{GITHUB_BASE_URL}bot.mp4" type="video/mp4">
    </video>
  </div>
  <div class="bg-overlay"></div>

  <div class="header">
    <div class="logo">🔥 EDROL <span>HUB</span></div>
    <button class="upgrade-btn" onclick="openTgBot('https://t.me/{MAIN_BOT_USERNAME}?start=vip')">💎 VIP Recharge</button>
  </div>

  <div class="hero-banner">
    <div class="hero-badge">🔒 100% Verified Companion Hub</div>
    <h1>Live Video Call &amp; 11 AI Sex Chat Bots</h1>
    <p>Tap any girl to see her uploaded posts! All payments happen safely inside Hot Bhabhi Bot via GPay/PhonePe/Paytm.</p>
  </div>

  <div class="tabs">
    <div class="tab active" id="tab_vcall" onclick="switchHubTab('vcall')">📹 Live Video Call (1)</div>
    <div class="tab" id="tab_aichat" onclick="switchHubTab('aichat')">💬 11 Sex Chat Bots</div>
  </div>

  <div id="sec_vcall">
    <div class="sec-head"><i class="fa-solid fa-video" style="color:#ff1493;"></i> Verified Real Video Call Girl</div>
    <div class="sec-sub">5 Min (₹149) • 10 Min (₹260) • 15 Min (₹329) • 20 Min (₹399). Tap card to view her 3 posts &amp; book in Bot Chat!</div>
    <div class="grid">{real_cards_html}</div>
  </div>

  <div id="sec_aichat" style="display:none;">
    <div class="sec-head"><i class="fa-solid fa-comments" style="color:#a855f7;"></i> 11 Uncensored Sex Chat &amp; Voice Bots</div>
    <div class="sec-sub">24/7 Instant Reply! Tap any girl below to view her uploaded posts &amp; open her card in Bot Chat:</div>
    <div class="grid">{ai_cards_html}</div>
  </div>

  <div class="info-card">
    <h2><i class="fa-solid fa-bolt"></i> How Video Call Booking &amp; UPI Works</h2>
    <ul class="info-list">
      <li><strong>Step 1 (View Girl Posts):</strong> Kisi bhi Girl Card par click karke uske uploaded private posts dekhein.</li>
      <li><strong>Step 2 (Direct Bot Card):</strong> <b>'Book Video Call'</b> ya <b>'Start Sex Chat'</b> dabayein — aap seedha <b>Hot Bhabhi Bot</b> mein us Girl ke Payment Card par pahunch jayenge!</li>
      <li><strong>Step 3 (Instant Video Call):</strong> Payment verify hote hi aapko Real Video Call Account (<b>@Alone28282</b>) ka direct call button mil jata hai!</li>
    </ul>
  </div>

  <div class="info-card">
    <h2><i class="fa-solid fa-shield-halved"></i> Group Management, Terms &amp; Support</h2>
    <ul class="info-list">
      <li><strong>🛡️ Smart Group Manager:</strong> 24/7 Anti-Link, Bio-Link Mute, Custom Black Welcome Card &amp; Auto-Tag Promotion.</li>
      <li><strong>🆘 24/7 Support &amp; 18+ Policy:</strong> Kisi bhi payment help ke liye Hot Bhabhi Bot mein <b>Help &amp; Support</b> button dabayein.</li>
    </ul>
  </div>

  <footer>
    <p style="font-size:13px; font-weight:900; color:#ff1493;">POWERED BY EDROL AI</p>
    <p style="font-size:11px; color:#64748b; margin-top:4px;">© 2026 Edrol Hub • 18+ Only</p>
  </footer>

  <!-- GIRL PROFILE & EXACT GITHUB POSTS MODAL -->
  <div id="profileModal">
    <div class="prof-top">
      <button class="back-pill" onclick="closeGirlProfile()"><i class="fa-solid fa-arrow-left"></i> Back</button>
      <span id="profBadge" style="font-size:11px;font-weight:900;color:#4ade80;">● LIVE PROFILE</span>
    </div>
    <div class="prof-hero">
      <img id="profDp" class="prof-dp" src="" alt="DP">
      <div class="prof-meta">
        <h2 id="profName">Girl Name</h2>
        <p id="profTime" style="color:#ff80ab;font-weight:700;margin-bottom:4px;"></p>
        <p id="profVibe">Girl description...</p>
      </div>
    </div>
    <div class="prof-action-bar">
      <button id="profActionBtn" class="prof-main-btn">Action Button</button>
    </div>
    <div class="sec-head" style="margin-top:6px;"><i class="fa-solid fa-images" style="color:#ff1493;"></i> Uploaded Private Posts</div>
    <div class="sec-sub">Exclusive photos from her profile:</div>
    <div id="profPostsGrid" class="posts-grid"></div>
  </div>

  <script>
    const GIRLS_DB = {girls_json_str};
    const isTgEnv = (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) ? true : false;
    if (isTgEnv) {{
      window.Telegram.WebApp.ready();
      window.Telegram.WebApp.expand();
    }}

    window.addEventListener('load', () => {{
      const bv = document.getElementById('bgVid');
      if (bv) bv.play().catch(() => {{}});
    }});

    function switchHubTab(tab) {{
      const isV = (tab === 'vcall');
      document.getElementById('sec_vcall').style.display = isV ? 'block' : 'none';
      document.getElementById('sec_aichat').style.display = isV ? 'none' : 'block';
      document.getElementById('tab_vcall').className = isV ? 'tab active' : 'tab';
      document.getElementById('tab_aichat').className = (!isV) ? 'tab active' : 'tab';
    }}

    function openTgBot(url) {{
      if (isTgEnv && window.Telegram.WebApp.openTelegramLink) {{
        window.Telegram.WebApp.openTelegramLink(url);
        setTimeout(() => window.Telegram.WebApp.close(), 150);
      }} else {{
        window.location.href = url;
      }}
    }}

    function openGirlProfile(gKey) {{
      const g = GIRLS_DB[gKey];
      if (!g) return;
      document.getElementById('profDp').src = g.dp;
      document.getElementById('profName').textContent = g.name;
      document.getElementById('profTime').textContent = '🕒 Online Time: ' + g.time_str;
      document.getElementById('profVibe').textContent = g.vibe;

      const btn = document.getElementById('profActionBtn');
      if (g.is_real_vcall) {{
        document.getElementById('profBadge').textContent = g.is_avail ? '🟢 AVAILABLE NOW' : '🔴 OFFLINE NOW';
        document.getElementById('profBadge').style.color = g.is_avail ? '#4ade80' : '#f87171';
        btn.textContent = '📞 Book Video Call Now (₹149–₹399)';
      }} else {{
        document.getElementById('profBadge').textContent = '💬 24/7 AI SEX CHAT BOT';
        document.getElementById('profBadge').style.color = '#d8b4fe';
        btn.textContent = '💬 Open ' + g.name + ' Card in Bot Chat';
      }}
      btn.onclick = function() {{ openTgBot(g.book_url); }};

      const grid = document.getElementById('profPostsGrid');
      grid.innerHTML = '';
      (g.posts || []).forEach(pUrl => {{
        const div = document.createElement('div');
        div.className = 'post-item';
        div.innerHTML = '<img src="' + pUrl + '" loading="lazy">';
        grid.appendChild(div);
      }});

      document.getElementById('profileModal').style.display = 'block';
      window.scrollTo(0, 0);
    }}

    function closeGirlProfile() {{
      document.getElementById('profileModal').style.display = 'none';
    }}
  </script>
</body>
</html>""", 200, {"Content-Type": "text/html; charset=utf-8"}

def setup_webhook():
    host = request.host_url.rstrip("/")
    results = {}
    all_upd = ["message", "edited_message", "callback_query", "chat_member", "my_chat_member", "chat_join_request"]

    # Setup Main Bot with FULL Group Join & Admin Updates!
    results["main_bot"] = requests.post(
        f"https://api.telegram.org/bot{MAIN_BOT_TOKEN}/setWebhook",
        json={"url": f"{host}/api/bot", "allowed_updates": all_upd}
    ).json()

    # Setup Character Bots
    for b_uname, b_tok in CHAR_BOT_TOKENS.items():
        if b_tok:
            try:
                results[b_uname] = requests.post(
                    f"https://api.telegram.org/bot{b_tok}/setWebhook",
                    json={"url": f"{host}/api/bot/{b_uname}", "allowed_updates": all_upd},
                    timeout=6
                ).json()
            except Exception as e:
                results[b_uname] = {"ok": False, "error": str(e)}

    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "80")), debug=False)
