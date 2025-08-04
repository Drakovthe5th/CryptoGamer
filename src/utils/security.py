import hashlib
import hmac
import logging
from urllib.parse import parse_qsl, unquote
from config import Config

logger = logging.getLogger(__name__)

def validate_telegram_hash(init_data: str) -> bool:
    """
    Validate Telegram WebApp initData using HMAC-SHA-256 signature
    """
    if not init_data:
        return False

    try:
        # Parse and decode URL-encoded values
        parsed_data = dict(parse_qsl(init_data))
        for key in parsed_data:
            parsed_data[key] = unquote(parsed_data[key])
        
        # Extract and remove hash
        received_hash = parsed_data.pop('hash', '')
        if not received_hash:
            return False
        
        # Create data check string
        data_check = []
        for key in sorted(parsed_data.keys()):
            value = parsed_data[key]
            # Skip empty values
            if value:
                data_check.append(f"{key}={value}")
        data_check_string = "\n".join(data_check)
        
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
        
        logger.debug(f"Computed hash: {computed_hash}")
        logger.debug(f"Received hash: {received_hash}")
        logger.debug(f"Data check string: {data_check_string}")
        
        return computed_hash == received_hash
    except Exception as e:
        logger.error(f"Hash validation error: {str(e)}")
        return False