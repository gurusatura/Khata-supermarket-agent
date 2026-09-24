import os
import time
import json
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()

from agent.harness import run_agent

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    print("Error: TELEGRAM_BOT_TOKEN not set in .env")
    exit(1)

API_URL = f"https://api.telegram.org/bot{TOKEN}"
CHAT_HISTORIES = {}

def get_updates(offset=None):
    url = f"{API_URL}/getUpdates?timeout=30"
    if offset:
        url += f"&offset={offset}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NebulaBot/1.0"})
        with urllib.request.urlopen(req, timeout=35) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("ok"):
                return data.get("result", [])
    except Exception as e:
        print(f"[Polling Error] {e}")
    return []

def send_message(chat_id, text):
    url = f"{API_URL}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req)
        print(f"[Telegram] Sent reply to {chat_id}")
    except Exception as e:
        print(f"[Telegram Error] Failed to send message: {e}")

def main():
    print("Starting Telegram Bot Polling...")
    last_update_id = None
    
    while True:
        updates = get_updates(offset=last_update_id)
        for update in updates:
            update_id = update["update_id"]
            last_update_id = update_id + 1
            
            message = update.get("message")
            if not message or "text" not in message:
                continue
                
            chat_id = str(message["chat"]["id"])
            text = message["text"]
            
            print(f"\n[Telegram] Received from {chat_id}: {text}")
            
            if chat_id not in CHAT_HISTORIES:
                CHAT_HISTORIES[chat_id] = []
            
            # Run the agent
            try:
                reply_text, new_history = run_agent(text, chat_id, CHAT_HISTORIES[chat_id])
                CHAT_HISTORIES[chat_id] = new_history
                send_message(chat_id, reply_text)
            except Exception as e:
                print(f"[Agent Error] {e}")
                send_message(chat_id, "Sorry, something went wrong, please try again")
                
        time.sleep(1)

if __name__ == "__main__":
    main()
