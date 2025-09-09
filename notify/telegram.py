# notify/telegram.py
import requests

def send_telegram(bot_token: str, chat_id: str, text: str) -> bool:
    bot_token = (bot_token or "").strip()
    chat_id = (str(chat_id) or "").strip()
    if not bot_token or not chat_id:
        print("[warn] telegram: missing bot token or chat id")
        return False
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        r = requests.post(url, json={"chat_id": chat_id, "text": text})
        if r.status_code != 200:
            print("[warn] telegram:", r.status_code, r.text)
            return False
        return True
    except Exception as e:
        print("[warn] telegram exception:", e)
        return False
