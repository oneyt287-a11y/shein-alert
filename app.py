import requests
import time
import json
import os
import threading
from flask import Flask
from concurrent.futures import ThreadPoolExecutor
import aiohttp
import asyncio

app = Flask(__name__)

# CONFIG
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
API_URL = "https://www.sheinindia.in/api/category/sverse-5939-37961"
CHECK_INTERVAL = 10
DATA_FILE = "products.json"

# SHARED STATE
stored_products_lock = threading.Lock()
stored_products = {}

@app.route("/")
def home():
    return {"status": "SHEINVERSE BOT v2.0 🚀"}

def load_data():
    global stored_products
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                stored_products.update(json.load(f))
                print(f"📂 Loaded {len(stored_products)} products")
    except Exception as e:
        print(f"⚠️ Load error: {e}")

def save_data():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(stored_products, f)
    except Exception as e:
        print(f"⚠️ Save error: {e}")

# TELEGRAM
def send_message(text):
    if not all([BOT_TOKEN, CHANNEL_ID]):
        print("❌ Missing BOT_TOKEN or CHANNEL_ID")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": CHANNEL_ID, 
            "text": text[:4096], 
            "parse_mode": "HTML"
        }, timeout=10)
        return resp.status_code == 200
    except:
        return False

def send_photo(caption, image_url):
    if not all([BOT_TOKEN, CHANNEL_ID]): return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    try:
        resp = requests.post(url, json={
            "chat_id": CHANNEL_ID, 
            "photo": image_url, 
            "caption": caption[:1020], 
            "parse_mode": "HTML"
        }, timeout=15)
        return resp.status_code == 200
    except:
        return False

def extract_sizes(product):
    sizes = set()
    variants = product.get("skuList") or []
    for v in variants:
        size = v.get("size") or v.get("sizeName") or v.get("value")
        if size and v.get("inStock") != False:
            sizes.add(size)
    return sizes

def process_product(product):
    code = str(product.get("code") or "")
    if not code: return
    
    name = product.get("name", "Unknown")
    price = product.get("offerPrice", {}).get("value") or product.get("price", {}).get("value") or 0
    images = product.get("images", [])
    image_url = images[0].get("url") if images else None
    url_path = product.get("url", "")
    product_url = f"https://www.sheinindia.in{url_path}" if url_path else ""
    sizes = extract_sizes(product)
    
    with stored_products_lock:
        prev_data = stored_products.get(code)
        prev_sizes = set(prev_data.get("sizes", [])) if prev_data else set()
    
    # NEW PRODUCT
    if code not in stored_products:
        print(f"🆕 NEW: {name}")
        with stored_products_lock:
            stored_products[code] = {"sizes": list(sizes)}
        
        caption = f"""🆕 <b>NEW PRODUCT!</b>

🛍 <b>{name}</b>
💰 ₹{price}
📦 Sizes: {', '.join(sizes) or 'N/A'}

🔗 {product_url}"""
        
        if image_url and send_photo(caption, image_url):
            print(f"✅ Sent photo for {name}")
        else:
            send_message(caption)
            print(f"✅ Sent message for {name}")
    
    # SIZE CHANGES
    else:
        sold_out = prev_sizes - sizes
        restocked = sizes - prev_sizes
        
        if sold_out:
            msg = f"""⚠️ <b>SIZES SOLD OUT</b>

🛍 <b>{name}</b>
❌ {', '.join(sold_out)}
🔗 {product_url}"""
            send_message(msg)
            print(f"⚠️ Sold out: {name}")
        
        if restocked:
            msg = f"""🔥 <b>SIZES RESTOCKED!</b>

🛍 <b>{name}</b>
✅ {', '.join(restocked)}
🔗 {product_url}"""
            send_message(msg)
            print(f"🔥 Restock: {name}")
        
        with stored_products_lock:
            stored_products[code]["sizes"] = list(sizes)

def monitor_loop():
    load_data()
    print("🚀 SHEINVERSE MONITOR STARTED")
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    while True:
        try:
            print(f"🔄 Polling Shein... ({time.strftime('%H:%M:%S')})")
            resp = session.get(API_URL, timeout=15)
            
            if resp.status_code != 200:
                print(f"❌ API Error: {resp.status_code}")
            else:
                data = resp.json()
                products = data.get("products", [])
                print(f"📦 Found {len(products)} products")
                
                if products:
                    with ThreadPoolExecutor(max_workers=8) as executor:
                        executor.map(process_product, products)
                    save_data()
                else:
                    print("⚠️ No products in response")
            
        except Exception as e:
            print(f"💥 Error: {e}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    thread = threading.Thread(target=monitor_loop, daemon=True)
    thread.start()
    print("🌐 Flask ready at /")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
