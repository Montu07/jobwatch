import os, requests

def send_telegram(bot_token, chat_id, text):
    if not bot_token or not chat_id:
        # Day 1: we simply print so you can see the message without configuring Telegram yet.
        print("[telegram stub]", text)
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    r = requests.post(url, json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True}, timeout=20)
    r.raise_for_status()
