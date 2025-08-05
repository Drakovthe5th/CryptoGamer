import os
import hashlib
import hmac
import urllib.parse
from flask import request
from config import Config
import jwt
import datetime

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

def get_user_id(req=request) -> int:
    """Extract user ID from JWT token in Authorization header"""
    auth_header = req.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return 0
    
    try:
        token = auth_header.split(' ')[1]
        payload = jwt.decode(
            token,
            Config.JWT_SECRET_KEY,
            algorithms=['HS256'],
            options={'verify_exp': True}
        )
        return payload.get('user_id', 0)
    except jwt.ExpiredSignatureError:
        return 0
    except jwt.InvalidTokenError:
        return 0