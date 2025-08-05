import os
import hashlib
import hmac
import urllib.parse
from config import Config

def validate_telegram_hash(init_data: str, bot_token: str) -> bool:
    """Validate Telegram WebApp initData hash"""
    if not init_data:
        return False
        
    # Parse the query string
    parsed_data = urllib.parse.parse_qsl(init_data)
    data_dict = {k: v for k, v in parsed_data}
    
    # Extract hash and remove from dict
    received_hash = data_dict.pop('hash', '')
    if not received_hash:
        return False
        
    # Create data check string
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data_dict.items()))
    
    # Calculate expected hash
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    expected_hash = hmac.new(
        secret_key, 
        data_check_string.encode(), 
        hashlib.sha256
    ).hexdigest()
    
    return received_hash == expected_hash