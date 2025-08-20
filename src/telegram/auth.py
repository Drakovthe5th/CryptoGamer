import hashlib
import hmac
from urllib.parse import parse_qsl
from flask import current_app
from telegram import Telegram
from src.database.mongo import get_user_data, create_user
from config import config

def validate_telegram_data(init_data: str, bot_token: str) -> bool:
    """
    Validate Telegram WebApp init data using HMAC-SHA256 signature
    Reference: https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
    """
    if not init_data:
        return False
    
    try:
        # Parse query string
        parsed_data = parse_qsl(init_data)
        data_dict = {}
        received_hash = None
        
        # Extract hash and build sorted key-value dictionary
        for key, value in parsed_data:
            if key == 'hash':
                received_hash = value
            else:
                data_dict[key] = value
        
        if not received_hash:
            current_app.logger.warning("No hash found in initData")
            return False
        
        # Create data check string
        data_check = "\n".join(
            f"{key}={value}" for key, value in sorted(data_dict.items())
        )
        
        # Generate secret key from bot token
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=bot_token.encode(),
            digestmod=hashlib.sha256
        ).digest()
        
        # Calculate HMAC
        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(calculated_hash, received_hash)
    
    except Exception as e:
        current_app.logger.error(f"Telegram validation failed: {str(e)}")
        return False
    
def get_or_create_user(user_id, username=None):
    """Get user data or create new user if doesn't exist"""
    user = get_user_data(user_id)
    if not user:
        # New user - create with welcome bonus
        user = create_user(user_id, username)
        
        # Show welcome message
        if Telegram.WebApp:
            Telegram.WebApp.showPopup({
                'title': 'Welcome to CryptoGamer!',
                'message': 'You received 2000 GC as a welcome bonus!',
                'buttons': [{'type': 'ok'}]
            })
    
    return user

# Maintain backward compatibility with existing imports
validate_init_data = validate_telegram_data