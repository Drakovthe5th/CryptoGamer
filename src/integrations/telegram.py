import requests
import logging
from config import config
from src.database.mongo import db

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
    
async def handle_webapp_data(data):
    if data['type'] == 'connect_wallet':
        user_id = data['user_id']
        wallet_address = data['address']
        
        from src.utils.validators import validate_ton_address
        if validate_ton_address(wallet_address):
            from src.database.firebase import connect_wallet as save_wallet
            if save_wallet(user_id, wallet_address):
                return "Wallet connected successfully!"
            return "Database error"
        return "Invalid wallet address"
    
    return "Unknown action"

async def connect_wallet(update, context):
    user_id = update.effective_user.id
    wallet_address = update.message.text.strip()
    
    if not validate_wallet(wallet_address):
        return "Invalid wallet address"
    
    user = get_user(user_id)
    user.wallet_address = wallet_address
    user.save()
    return "✅ Wallet connected successfully!"