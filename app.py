import requests
import time
import json
import os
import threading
import random
from flask import Flask

# ================= CONFIG =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

CATEGORY_PAGE = "https://www.sheinindia.in/sheinverse-c-37961.html"

API_URL = "https://www.sheinindia.in/api/category/sverse-5939-37961?fields=SITE&currentPage=1&pageSize=45&format=json&query=%3Arelevance&gridColumns=5&advfilter=true&platform=Desktop&showAdsOnNextPage=false&is_ads_enable_plp=true&displayRatings=true&segmentIds=&&store=shein"

# Safe for Railway (datacenter IP)
NORMAL_MIN = 25
NORMAL_MAX = 35
FLASH_INTERVAL = 10
FLASH_DURATION = 60

DATA_FILE = "products.json"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/119 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/118 Safari/537.36",
]

session = requests.Session()

# ================= WEB SERVER (Railway requires open port) =================

app = Flask(__name__)

@app.route("/")
def home():
    return "SHEINVERSE BOT RUNNING ⚡"

def run_web():
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# ================= STORAGE =================

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

stored_products = load_data()

# ================= TELEGRAM =================

def send_message(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        session.post(url, data={
            "chat_id": CHANNEL_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }, timeout=10)
    except:
        pass

def send_photo(caption, image_url):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        session.post(url, data={
            "chat_id": CHANNEL_ID,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "HTML"
        }, timeout=15)
    except:
        pass

# ================= HEADERS =================

def browser_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
        "Connection": "keep-alive",
    }

def api_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Referer": CATEGORY_PAGE,
        "X-Requested-With": "XMLHttpRequest",
        "Connection": "keep-alive",
    }

# ================= SESSION WARMUP =================

last_warmup = 0

def warmup_session():
    global last_warmup
    if time.time() - last_warmup > 300:  # warm every 5 minutes
        try:
            print("🌐 Refreshing session cookies...")
            session.get(CATEGORY_PAGE, headers=browser_headers(), timeout=15)
            last_warmup = time.time()
            time.sleep(2)
        except:
            pass

# ================= HELPERS =================

def get_price(product):
    offer = product.get("offerPrice", {})
    regular = product.get("price", {})

    if offer.get("displayformattedValue"):
        return offer["displayformattedValue"]

    if regular.get("displayformattedValue"):
        return regular["displayformattedValue"]

    return "Price N/A"

def extract_sizes(product):
    sizes = set()
    variants = product.get("skuList") or []

    for v in variants:
        size = v.get("sizeName") or v.get("size")
        if v.get("inStock"):
            sizes.add(size)

    return sizes

# ================= FETCH =================

def fetch_products():
    try:
        warmup_session()

        response = session.get(API_URL, headers=api_headers(), timeout=15)

        if response.status_code != 200:
            print("Blocked:", response.status_code)
            return None

        if "application/json" not in response.headers.get("Content-Type", ""):
            print("Non JSON response")
            return None

        return response.json()

    except Exception as e:
        print("Fetch error:", e)
        return None

# ================= MAIN LOOP =================

print("🚀 SHEINVERSE MONITOR STARTED (Railway Mode)")

flash_mode_until = 0

while True:
    try:
        now = time.time()
        in_flash = now < flash_mode_until

        data = fetch_products()
        if not data:
            time.sleep(15)
            continue

        products = data.get("products", [])
        activity = False

        for p in products:

            code = str(p.get("code"))
            name = p.get("name")
            price = get_price(p)
            link = "https://www.sheinindia.in" + p.get("url", "")

            image = None
            imgs = p.get("images", [])
            if imgs:
                image = imgs[0].get("url")

            current_sizes = extract_sizes(p)
            old = stored_products.get(code)

            if code not in stored_products:

                stored_products[code] = {"sizes": list(current_sizes)}
                save_data(stored_products)

                caption = f"""🆕 <b>NEW PRODUCT</b>

🛍 <b>{name}</b>
💰 {price}
📦 Sizes: {", ".join(current_sizes) if current_sizes else "Available"}

🔗 {link}
"""

                if image:
                    send_photo(caption, image)
                else:
                    send_message(caption)

                activity = True

            else:
                old_sizes = set(old.get("sizes", []))
                restocked = current_sizes - old_sizes
                sold_out = old_sizes - current_sizes

                if restocked:
                    send_message(f"""🔁 <b>SIZE RESTOCKED</b>

🛍 <b>{name}</b>
💰 {price}
✅ Restocked: {", ".join(restocked)}

🔗 {link}
""")
                    activity = True

                if sold_out:
                    send_message(f"""⚠ <b>SIZE SOLD OUT</b>

🛍 <b>{name}</b>
❌ Sold Out: {", ".join(sold_out)}

🔗 {link}
""")

                stored_products[code]["sizes"] = list(current_sizes)
                save_data(stored_products)

        if activity:
            flash_mode_until = time.time() + FLASH_DURATION
            print("⚡ Flash mode activated")

        if in_flash:
            sleep_time = FLASH_INTERVAL + random.uniform(1, 3)
        else:
            sleep_time = random.randint(NORMAL_MIN, NORMAL_MAX)

        time.sleep(sleep_time)

    except Exception as e:
        print("Loop error:", e)
        time.sleep(15)
