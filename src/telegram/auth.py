import hashlib
import hmac
from urllib.parse import parse_qsl
from flask import current_app
from config import config

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
    
def validate_init_data(init_data: str) -> bool:
    """
    Validate Telegram WebApp init data
    """
    try:
        from urllib.parse import parse_qsl
        from hashlib import sha256
        import hmac
        
        # Parse query string
        data = parse_qsl(init_data)
        data_dict = {k: v for k, v in data if k != 'hash'}
        
        # Generate hash
        secret = sha256(config.TELEGRAM_BOT_TOKEN.encode()).digest()
        data_check = "\n".join(f"{k}={v}" for k, v in sorted(data_dict.items()))
        computed_hash = hmac.new(secret, data_check.encode(), sha256).hexdigest()
        
        # Compare hashes
        return computed_hash == dict(data).get('hash', '')
    except:
        return False