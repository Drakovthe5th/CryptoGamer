import hashlib
import hmac
from urllib.parse import parse_qsl
from flask import current_app
from config import config

def validate_telegram_data(init_data: str) -> bool:
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
            msg=config.TELEGRAM_TOKEN.encode(),
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

# Maintain backward compatibility with existing imports
validate_init_data = validate_telegram_data