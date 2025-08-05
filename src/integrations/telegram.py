import requests
import logging
from config import config
from src.database.firebase import get_firestore_db

logger = logging.getLogger(__name__)

def send_telegram_message(user_id: int, message: str) -> bool:
    """Send message to user via Telegram"""
    try:
        # Get Telegram chat ID from database
        db = get_firestore_db()
        user_ref = db.collection('users').document(str(user_id))
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            logger.warning(f"No user record found for {user_id}")
            return False
            
        user_data = user_doc.to_dict()
        chat_id = user_data.get('telegram_chat_id')
        
        if not chat_id:
            logger.warning(f"No Telegram chat ID for user {user_id}")
            return False
            
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info(f"Telegram message sent to user {user_id}")
            return True
        else:
            logger.error(f"Telegram API error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Telegram message exception: {e}")
        return False