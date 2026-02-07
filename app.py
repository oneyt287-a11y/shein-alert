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

CHECK_INTERVAL = 120  # seconds

DATA_FILE = "products.json"

# ==========================
# FLASK KEEP-ALIVE
# ==========================

app = Flask(__name__)

@app.route("/")
def home():
    return "SHEINVERSE API BOT Running"

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
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHANNEL_ID,
            "text": text,
            "parse_mode": "HTML"
        }
        requests.post(url, data=payload, timeout=10)
    except:
        pass

def send_photo(caption, image_url):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        payload = {
            "chat_id": CHANNEL_ID,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "HTML"
        }
        requests.post(url, data=payload, timeout=15)
    except:
        pass

# ==========================
# VOUCHER LOGIC
# ==========================

def voucher_text(price):
    if price < 500:
        return "🎟 Use ₹500 Voucher"
    elif price < 1000:
        return "🎟 Use ₹1000 Voucher"
    else:
        return "❌ No Voucher"

# ==========================
# MONITOR
# ==========================

while True:
    try:
        resp = requests.get(API_URL, timeout=30)
        data = resp.json()

        products = data.get("products", [])

        for p in products:

            code = str(p.get("code"))
            name = p.get("name")
            price = p.get("offerPrice", {}).get("value") or p.get("price", {}).get("value", 0)
            image = None

            imgs = p.get("images", [])
            if imgs:
                image = imgs[0].get("url")

            link_path = p.get("url")
            link = "https://www.sheinindia.in" + link_path

            in_stock = True  # API returns only in-stock products

            prev = stored_products.get(code)

            # 🚀 NEW PRODUCT
            if code not in stored_products:
                stored_products[code] = in_stock
                save_data(stored_products)

                caption = f"""🆕 <b>NEW PRODUCT</b>

🛍 {name}
💰 ₹{price}
{voucher_text(price)}

🔗 <a href="{link}">Open Product</a>"""

                send_photo(caption, image)

            # 🔁 RESTOCK
            elif prev == False and in_stock == True:
                stored_products[code] = True
                save_data(stored_products)

                caption = f"""🔁 <b>RESTOCK ALERT!</b>

🛍 {name}
💰 ₹{price}
{voucher_text(price)}

🔗 <a href="{link}">Open Product</a>"""

                send_photo(caption, image)

            else:
                stored_products[code] = in_stock

        # WAIT
        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        print("Error:", e)
        time.sleep(10)
