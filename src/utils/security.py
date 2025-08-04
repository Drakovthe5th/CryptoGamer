import hashlib
import hmac
from urllib.parse import parse_qsl
from config import Config

def validate_telegram_hash(init_data: str, data_check_string: str) -> bool:
    """
    Validate Telegram WebApp initData using HMAC-SHA-256 signature
    """
    if not init_data or not data_check_string:
        return False

    try:
        # Calculate HMAC signature
        secret_key = hmac.new(
            "WebAppData".encode(), 
            Config.TELEGRAM_TOKEN.encode(), 
            hashlib.sha256
        ).digest()
        
        computed_hash = hmac.new(
            secret_key, 
            data_check_string.encode(), 
            hashlib.sha256
        ).hexdigest()
        
        # Extract hash from initData
        parsed_data = dict(parse_qsl(init_data))
        received_hash = parsed_data.get('hash', '')
        
        return computed_hash == received_hash
    except Exception:
        return False