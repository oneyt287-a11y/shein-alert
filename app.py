import requests
import time
import json
import os
import threading
from flask import Flask

# ==========================
# CONFIG
# ==========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

API_URL = "https://www.sheinindia.in/api/category/sverse-5939-37961?fields=SITE&currentPage=1&pageSize=45&format=json&query=%3Arelevance&gridColumns=5&advfilter=true&platform=Desktop&showAdsOnNextPage=false&is_ads_enable_plp=true&displayRatings=true&segmentIds=&&store=shein"

CHECK_INTERVAL = 15
DATA_FILE = "products.json"

# ==========================
# FAST SESSION
# ==========================

session = requests.Session()

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Connection": "keep-alive"
}

# ==========================
# FLASK (Railway keep alive)
# ==========================

app = Flask(__name__)

@app.route("/")
def home():
    return "SHEINVERSE BOT RUNNING ⚡"

def run_web():
    app.run(host="0.0.0.0", port=8000)

threading.Thread(target=run_web, daemon=True).start()

# ==========================
# STORAGE
# ==========================

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

stored_products = load_data()

# ==========================
# TELEGRAM
# ==========================

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    session.post(url, data=payload, timeout=10)

def send_photo(caption, image_url):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHANNEL_ID,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "HTML"
    }
    session.post(url, data=payload, timeout=15)

# ==========================
# PRICE (Exact Display From Site)
# ==========================

def get_display_price(product):
    offer = product.get("offerPrice", {})
    regular = product.get("price", {})

    if offer.get("displayformattedValue"):
        return offer.get("displayformattedValue")
    elif regular.get("displayformattedValue"):
        return regular.get("displayformattedValue")
    else:
        return "Price Not Available"

# ==========================
# SIZE EXTRACTION
# ==========================

def extract_sizes(product):
    sizes = set()
    variants = product.get("skuList") or product.get("variantOptions") or []

    for v in variants:
        size = v.get("size") or v.get("sizeName") or v.get("value")
        in_stock = v.get("inStock")

        if size:
            if in_stock is None:
                sizes.add(size)
            elif in_stock:
                sizes.add(size)

    return sizes

# ==========================
# MAIN LOOP
# ==========================

print("🚀 SHEINVERSE BOT STARTED (ALL PRODUCTS MODE)")

while True:
    try:
        start_time = time.time()

        response = session.get(API_URL, headers=HEADERS, timeout=15)
        data = response.json()

        products = data.get("products", [])

        for p in products:

            code = str(p.get("code"))
            name = p.get("name")

            display_price = get_display_price(p)

            image = None
            imgs = p.get("images", [])
            if imgs:
                image = imgs[0].get("url")

            link = "https://www.sheinindia.in" + p.get("url", "")

            current_sizes = extract_sizes(p)

            previous_data = stored_products.get(code)

            # NEW PRODUCT
            if code not in stored_products:

                stored_products[code] = {
                    "sizes": list(current_sizes)
                }
                save_data(stored_products)

                caption = f"""🆕 <b>NEW PRODUCT</b>

🛍 <b>{name}</b>
💰 {display_price}
📦 Sizes: {", ".join(current_sizes) if current_sizes else "Available"}

🔗 {link}
"""

                if image:
                    send_photo(caption, image)
                else:
                    send_message(caption)

            # EXISTING PRODUCT
            else:
                old_sizes = set(previous_data.get("sizes", []))

                sold_out = old_sizes - current_sizes
                restocked = current_sizes - old_sizes

                if sold_out:
                    send_message(f"""⚠️ <b>SIZE SOLD OUT</b>

🛍 <b>{name}</b>
❌ Sold Out: {", ".join(sold_out)}

🔗 {link}
""")

                if restocked:
                    send_message(f"""🔁 <b>SIZE RESTOCKED</b>

🛍 <b>{name}</b>
✅ Restocked: {", ".join(restocked)}

🔗 {link}
""")

                stored_products[code]["sizes"] = list(current_sizes)
                save_data(stored_products)

        elapsed = time.time() - start_time
        time.sleep(max(0, CHECK_INTERVAL - elapsed))

    except Exception as e:
        print("Error:", e)
        time.sleep(5)
