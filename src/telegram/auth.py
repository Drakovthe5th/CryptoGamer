import hashlib
import hmac
from urllib.parse import parse_qsl
from flask import current_app
from src.config import config

def validate_telegram_hash(init_data, bot_token):
    if not init_data:
        return False
    
    try:
        parsed_data = parse_qsl(init_data)
        data_dict = {}
        hash_value = None
        
        for key, value in parsed_data:
            if key == 'hash':
                hash_value = value
            else:
                data_dict[key] = value
        
        if not hash_value:
            return False
        
        data_check_string = "\n".join(
            [f"{key}={value}" for key, value in sorted(data_dict.items())]
        )
        
        secret_key = hmac.new(
            key=b"WebAppData", 
            msg=bot_token.encode(), 
            digestmod=hashlib.sha256
        ).digest()
        
        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        return calculated_hash == hash_value
    
    except Exception:
        current_app.logger.exception("Telegram auth verification failed")
        return False