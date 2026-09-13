import asyncio
import logging
import os
import re
import sys
import json
import aiohttp
from aiohttp import web
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# High-performance logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("HyperBot")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_IDS_FILE = os.path.join(os.path.dirname(__file__), "chat_ids.json")
LEGACY_CHAT_ID_FILE = os.path.join(os.path.dirname(__file__), "chat_id.txt")

# Global memory cache for set of Admin Chat IDs
SAVED_CHAT_IDS = set()

# Global persistent aiohttp client session for instant zero-latency HTTP requests
HTTP_CLIENT: aiohttp.ClientSession = None

def get_saved_chat_ids():
    global SAVED_CHAT_IDS
    if SAVED_CHAT_IDS:
        return list(SAVED_CHAT_IDS)
    
    if os.path.exists(CHAT_IDS_FILE):
        try:
            with open(CHAT_IDS_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    SAVED_CHAT_IDS = set(str(cid) for cid in data)
        except Exception as e:
            logger.error(f"Error reading chat_ids.json: {e}")

    if os.path.exists(LEGACY_CHAT_ID_FILE):
        try:
            with open(LEGACY_CHAT_ID_FILE, "r") as f:
                legacy_id = f.read().strip()
                if legacy_id:
                    SAVED_CHAT_IDS.add(str(legacy_id))
        except Exception:
            pass

    return list(SAVED_CHAT_IDS)

def save_chat_id(chat_id):
    global SAVED_CHAT_IDS
    str_id = str(chat_id).strip()
    if not str_id:
        return
    get_saved_chat_ids()
    if str_id not in SAVED_CHAT_IDS:
        SAVED_CHAT_IDS.add(str_id)
        logger.info(f"New Admin Chat ID registered: {str_id}. Total admins: {len(SAVED_CHAT_IDS)}")
        try:
            with open(CHAT_IDS_FILE, "w") as f:
                json.dump(list(SAVED_CHAT_IDS), f)
        except Exception as e:
            logger.error(f"Error saving chat_ids.json: {e}")

# Pre-compiled Regex patterns for microsecond execution speed (bKash, Nagad, Rocket, Upay, etc.)
TRX_REGEX = re.compile(r'(?:Trx\s*ID|Txn\s*ID|TxID|TxnID|Transaction\s*ID|Ref(?:erence)?\s*ID|Trx|Txn|ID)[:\s\-]*([A-Za-z0-9]{6,16})', re.IGNORECASE)
FALLBACK_TRX_REGEX = re.compile(r'\b(?=.*\d)([A-Z0-9]{7,14})\b')
TK_REGEX_1 = re.compile(r'(?:Tk|BDT|৳)\s*([0-9,]+(?:\.[0-9]{1,2})?)', re.IGNORECASE)
TK_REGEX_2 = re.compile(r'([0-9,]+(?:\.[0-9]{1,2})?)\s*(?:Tk|BDT|৳)', re.IGNORECASE)

async def send_single_telegram_message(chat_id: str, text: str, trx_id: str = None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if trx_id:
        payload["reply_markup"] = {
            "inline_keyboard": [
                [
                    {"text": f"📋 Copy TrxID ({trx_id})", "copy_text": {"text": trx_id}}
                ]
            ]
        }
    
    for attempt in range(3):
        try:
            async with HTTP_CLIENT.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as res:
                if res.status == 200:
                    return True
                txt = await res.text()
                logger.error(f"Telegram API Error for {chat_id} (Attempt {attempt+1}): {res.status} - {txt}")
        except Exception as e:
            logger.error(f"Telegram send attempt {attempt+1} to {chat_id} failed: {e}")
        await asyncio.sleep(0.2)
    return False

async def broadcast_telegram_message(text: str, trx_id: str = None):
    chat_ids = get_saved_chat_ids()
    if not chat_ids:
        logger.warning("No Telegram Chat IDs registered yet.")
        return
    tasks = [send_single_telegram_message(cid, text, trx_id=trx_id) for cid in chat_ids]
    await asyncio.gather(*tasks, return_exceptions=True)

async def handle_webhook(request: web.Request):
    """Ultra-fast Async Webhook Handler (<1ms response time)"""
    data = {}
    raw_text = ""
    
    if request.method == "POST":
        try:
            if request.content_type == "application/json":
                data = await request.json()
            else:
                post_data = await request.post()
                data = dict(post_data)
        except Exception:
            pass
        if not data:
            raw_text = await request.text()
            data = {"message": raw_text}
    else:
        data = dict(request.query)
        raw_text = await request.text()
        if not data and raw_text:
            data = {"message": raw_text}

    logger.info(f"Incoming Request: Method={request.method}, Query={dict(request.query)}, Text={raw_text[:200]}, ParsedData={data}")

    # Combine all fields to avoid missing SMS content regardless of JSON key names
    all_str_parts = []
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (str, int, float)):
                all_str_parts.append(str(v))
    
    sms_text = " ".join(all_str_parts) if all_str_parts else raw_text

    match = TRX_REGEX.search(sms_text)
    trx_id = None
    if match:
        trx_id = match.group(1).strip()
    else:
        fallback_match = FALLBACK_TRX_REGEX.search(sms_text)
        if fallback_match:
            trx_id = fallback_match.group(1).strip()

    amount = None
    tk_match = TK_REGEX_1.search(sms_text)
    if not tk_match:
        tk_match = TK_REGEX_2.search(sms_text)
    if tk_match:
        amount = tk_match.group(1).strip()

    if trx_id:
        logger.info(f"Instant TrxID extracted: {trx_id}, Amount: {amount}")
        if amount:
            formatted_message = f"💵 <b>{amount} Tk</b> — <code>{trx_id}</code>"
        else:
            formatted_message = f"<code>{trx_id}</code>"

        asyncio.create_task(broadcast_telegram_message(formatted_message, trx_id=trx_id))
        return web.json_response({"status": "success", "trx_id": trx_id, "amount": amount, "speed": "hyper_async"})
    elif amount and any(keyword in sms_text.upper() for keyword in ["NAGAD", "BKASH", "ROCKET", "UPAY", "CASH OUT", "CASH IN", "RECEIVED", "PAYMENT"]):
        # Forward transaction SMS even if TrxID regex missed exact keyword
        logger.info(f"Transaction SMS detected via amount: {amount}")
        formatted_message = f"💵 <b>{amount} Tk</b>\n\n<code>{sms_text[:300]}</code>"
        asyncio.create_task(broadcast_telegram_message(formatted_message))
        return web.json_response({"status": "success", "amount": amount, "note": "Forwarded via amount match"})
    else:
        logger.info("Non-transaction SMS killed/ignored.")
        return web.json_response({"status": "ignored", "reason": "No TrxID found, text killed"})

async def poll_telegram_updates():
    """Background polling to capture Chat IDs when users send /start"""
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=10"
            async with HTTP_CLIENT.get(url, timeout=aiohttp.ClientTimeout(total=12)) as res:
                if res.status == 200:
                    res_json = await res.json()
                    updates = res_json.get("result", [])
                    for update in updates:
                        offset = update["update_id"] + 1
                        if "message" in update:
                            chat = update["message"].get("chat", {})
                            chat_id = chat.get("id")
                            text = update["message"].get("text", "")
                            if chat_id:
                                save_chat_id(chat_id)
                                logger.info(f"Captured Chat ID: {chat_id}")
                                if "/start" in text:
                                    asyncio.create_task(send_single_telegram_message(
                                        str(chat_id),
                                        "✅ <b>বট সফলভাবে আপনার চ্যাটে কানেক্ট হয়েছে!</b>\n\n"
                                        "এখন থেকে বিকাশ ও নগদ SMS-এর শুধুমাত্র <b>TrxID</b> এবং <b>টাকার পরিমাণ</b> আল্ট্রা-ফাস্ট স্পিডে এখানে চলে আসবে।"
                                    ))
        except Exception:
            pass
        await asyncio.sleep(1)

async def on_startup(app):
    global HTTP_CLIENT
    connector = aiohttp.TCPConnector(limit=100, limit_per_host=50, ttl_dns_cache=300, keepalive_timeout=60, ssl=False)
    HTTP_CLIENT = aiohttp.ClientSession(connector=connector)
    get_saved_chat_ids()
    asyncio.create_task(poll_telegram_updates())

async def on_cleanup(app):
    global HTTP_CLIENT
    if HTTP_CLIENT:
        await HTTP_CLIENT.close()

def create_app():
    app = web.Application()
    app.router.add_route("*", "/webhook", handle_webhook)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app

def main():
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is missing in .env file.")
        sys.exit(1)

    logger.info("=========================================")
    logger.info("🚀 Hyper-Speed bKash/Nagad Telegram Bot Active (aiohttp Async Engine)")
    logger.info("Listening on port 5001 (/webhook)")
    logger.info("=========================================")
    
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=5001, print=None)

if __name__ == "__main__":
    main()
