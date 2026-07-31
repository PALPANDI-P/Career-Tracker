"""Career Tracker — Telegram Notifier."""
from __future__ import annotations
import time
import requests
from config.settings import get_settings

def send_alert(chat_id, message):
    settings = get_settings()
    token = settings.telegram_bot_token
    if not token:
        raise RuntimeError('TELEGRAM_BOT_TOKEN missing from .env')
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True,
    }
    last_exc = None
    for attempt in range(1, 4):
        try:
            resp = requests.post(url, json=payload, timeout=20)
            resp.raise_for_status()
            return
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < 3:
                time.sleep(2 ** attempt)
    raise RuntimeError(f'Telegram send failed: {last_exc}')
