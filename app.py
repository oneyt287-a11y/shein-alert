import asyncio
import requests
import os
import time
from playwright.async_api import async_playwright

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

SHEINVERSE_URL = "https://www.sheinindia.in/c/she-inverse"
CHECK_INTERVAL = 60
HEARTBEAT_INTERVAL = 21600  # 6 hours

product_status = {}
last_heartbeat = time.time()

# ==========================
# TELEGRAM
# ==========================

def send_message(text):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    )

def send_photo(caption, image_url):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
        data={
            "chat_id": CHANNEL_ID,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "HTML"
        }
    )

# ==========================
# VOUCHER LOGIC
# ==========================

def apply_voucher(price):
    if price < 500:
        return "🎟 Use ₹500 Voucher"
    elif 500 <= price < 1000:
        return "🎟 Use ₹1000 Voucher"
    else:
        return "❌ No Voucher"

# ==========================
# MONITOR FUNCTION
# ==========================

async def monitor():
    global last_heartbeat

    while True:  # Watchdog loop
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                async def handle_response(response):
                    if "product/list" in response.url:
                        try:
                            data = await response.json()
                            products = data.get("info", {}).get("products", [])

                            for product in products:

                                product_id = str(product.get("goods_id"))
                                name = product.get("goods_name")
                                price = int(float(product.get("salePrice", 0)))
                                image = product.get("goods_img")
                                link = f"https://www.sheinindia.in/p/{product_id}"
                                stock = product.get("stock", 0)
                                in_stock = stock > 0

                                previous_status = product_status.get(product_id)

                                # NEW PRODUCT
                                if product_id not in product_status:
                                    product_status[product_id] = in_stock

                                    if in_stock:
                                        caption = f"""
🆕 <b>NEW PRODUCT (IN STOCK)</b>

🛍 {name}
💰 ₹{price}
{apply_voucher(price)}

🔗 <a href="{link}">Open Product</a>
"""
                                        send_photo(caption, image)

                                # RESTOCK
                                elif previous_status is False and in_stock is True:
                                    product_status[product_id] = True

                                    caption = f"""
🔁 <b>RESTOCK ALERT!</b>

🛍 {name}
💰 ₹{price}
{apply_voucher(price)}

🔗 <a href="{link}">Open Product</a>
"""
                                    send_photo(caption, image)

                                else:
                                    product_status[product_id] = in_stock

                        except Exception as e:
                            print("JSON Error:", e)

                page.on("response", handle_response)

                while True:
                    await page.goto(SHEINVERSE_URL, timeout=60000)
                    await asyncio.sleep(CHECK_INTERVAL)

                    # Heartbeat
                    if time.time() - last_heartbeat > HEARTBEAT_INTERVAL:
                        send_message("🟢 SHEINVERSE Monitor Running 24/7")
                        last_heartbeat = time.time()

        except Exception as e:
            print("Browser crashed. Restarting...", e)
            await asyncio.sleep(5)

asyncio.run(monitor())