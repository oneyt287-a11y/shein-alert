import requests
import time
import json
import os
import threading
from flask import Flask
import aiohttp
import asyncio
from concurrent.futures import ThreadPoolExecutor

# ==========================
# CONFIG
# ==========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

API_URL = "https://www.sheinindia.in/api/category/sverse-5939-37961?fields=SITE&currentPage=1&pageSize=45&format=json&query=%3Arelevance&gridColumns=5&advfilter=true&platform=Desktop&showAdsOnNextPage=false&is_ads_enable_plp=true&displayRatings=true&segmentIds=&&store=shein"

CHECK_INTERVAL = 60  # Reduced from 120s for faster monitoring [web:6]
DATA_FILE = "products.json"
SESSION_TIMEOUT = 5.0  # Faster timeout [web:6]

# ==========================
# HTTP SESSION (Connection Pooling)
# ==========================

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})
adapter = requests.adapters.HTTPAdapter(
    pool_connections=10,
    pool_maxsize=20,
    max_retries=2
)
session.mount('http://', adapter)
session.mount('https://', adapter)

# ==========================
# FLASK (Railway keep-alive) - Optimized
# ==========================

app = Flask(__name__)

@app.route("/")
def home():
    return {"status": "SHEINVERSE BOT RUNNING", "timestamp": time.time()}

def run_web():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)), debug=False)

threading.Thread(target=run_web, daemon=True).start()

# ==========================
# STORAGE (Async JSON)
# ==========================

stored_products = {}
data_lock = threading.Lock()

def load_data():
    global stored_products
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                stored_products = json.load(f)
        except:
            stored_products = {}
    return stored_products

def save_data():
    with data_lock:
        with open(DATA_FILE, "w") as f:
            json.dump(stored_products, f)

stored_products = load_data()

# ==========================
# TELEGRAM (Batch-friendly, shorter timeouts)
# ==========================

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text[:4096],  # Truncate to avoid errors
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        response = requests.post(url, data=payload, timeout=10)  # Faster timeout [web:6]
        return response.status_code == 200
    except:
        return False

def send_photo(caption, image_url):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHANNEL_ID,
        "photo": image_url,
        "caption": caption[:1020],  # Photo caption limit
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, data=payload, timeout=15)
        return response.status_code == 200
    except:
        return False

# ==========================
# VOUCHER LOGIC
# ==========================

def voucher_text(price):
    if price < 500:
        return "🎟 Use ₹500 Voucher"
    elif price < 1000:
        return "🎟 Use ₹1000 Voucher"
    else:
        return "🎟 Eligible for ₹1000 Voucher"

# ==========================
# SIZE EXTRACTION (Optimized)
# ==========================

def extract_sizes(product):
    sizes = set()
    variants = product.get("skuList") or product.get("variantOptions") or []
    for v in variants:
        size = v.get("size") or v.get("sizeName") or v.get("value")
        if size and (v.get("inStock") is True or v.get("inStock") is None):
            sizes.add(size)
    return sizes

# ==========================
# PROCESS SINGLE PRODUCT (Faster parsing)
# ==========================

def process_product(p, send_photo_func, send_message_func):
    code = str(p.get("code", ""))
    if not code:
        return

    name = p.get("name", "Unknown")
    price = p.get("offerPrice", {}).get("value") or p.get("price", {}).get("value") or 0

    imgs = p.get("images", [])
    image = imgs[0].get("url") if imgs else None

    link_path = p.get("url", "")
    link = "https://www.sheinindia.in" + link_path if link_path else ""

    current_sizes = extract_sizes(p)

    with data_lock:
        previous_data = stored_products.get(code)
        old_sizes = set(previous_data.get("sizes", [])) if previous_data else set()

    # NEW PRODUCT
    if code not in stored_products:
        with data_lock:
            stored_products[code] = {"sizes": list(current_sizes)}
        caption = f"""🆕 <b>NEW PRODUCT</b>

🛍 <b>{name}</b>
💰 ₹{price}
📦 Sizes: {', '.join(current_sizes) or 'Available'}

{voucher_text(price)}

🔗 {link}"""
        if image and send_photo_func(caption, image):
            return
        send_message_func(caption)

    # EXISTING PRODUCT UPDATES
    else:
        sold_out = old_sizes - current_sizes
        restocked = current_sizes - old_sizes

        if sold_out:
            message = f"""⚠️ <b>SIZE SOLD OUT</b>

🛍 <b>{name}</b>
❌ Sold Out: {', '.join(sold_out)}

🔗 {link}"""
            send_message_func(message)

        if restocked:
            message = f"""🔁 <b>SIZE RESTOCKED</b>

🛍 <b>{name}</b>
✅ Restocked: {', '.join(restocked)}

🔗 {link}"""
            send_message_func(message)

        with data_lock:
            stored_products[code]["sizes"] = list(current_sizes)

# ==========================
# MAIN FETCH (Optimized with Session + ThreadPool)
# ==========================

def fetch_and_process():
    try:
        response = session.get(API_URL, timeout=SESSION_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        products = data.get("products", [])

        with ThreadPoolExecutor(max_workers=10) as executor:  # Parallel processing [web:10]
            futures = [
                executor.submit(process_product, p, send_photo, send_message)
                for p in products
            ]
            for future in futures:
                future.result()  # Wait for completion

        save_data()  # Single save after all processing

    except Exception as e:
        print(f"Fetch error: {e}")

# ==========================
# MONITOR LOOP (Faster interval, better error handling)
# ==========================

print("🚀 OPTIMIZED SHEINVERSE BOT STARTED")

while True:
    fetch_and_process()
    time.sleep(CHECK_INTERVAL)
