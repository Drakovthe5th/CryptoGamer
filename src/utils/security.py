import os
import hashlib
import hmac
import urllib.parse
import jwt
import random
from datetime import datetime, timedelta
from flask import request
from config import Config
from src.database.firebase import db

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

# def generate_2fa_code(user_id: int) -> str:
#     """Generate a 6-digit 2FA code and store it in Firestore with expiration"""
#     try:
#         db = get_firestore_db()
#         code = ''.join(random.choices('0123456789', k=6))
#         expires_at = datetime.utcnow() + timedelta(minutes=5)
        
#         # Store code in Firestore
#         db.collection('two_factor_codes').document(str(user_id)).set({
#             'code': code,
#             'expires_at': expires_at
#         })
        
#         return code
#     except Exception as e:
#         print(f"2FA generation error: {e}")
#         return "000000"  # Fallback code

# def verify_2fa_code(user_id: int, code: str) -> bool:
#     """Verify if the 2FA code is valid and not expired"""
#     try:
#         db = get_firestore_db()
#         doc_ref = db.collection('two_factor_codes').document(str(user_id))
#         doc = doc_ref.get()
        
#         if not doc.exists:
#             return False
            
#         data = doc.to_dict()
#         stored_code = data.get('code', '')
#         expires_at = data.get('expires_at')
        
#         # Check if code matches and is not expired
#         if stored_code == code and datetime.utcnow() < expires_at:
#             # Delete the code after successful verification
#             doc_ref.delete()
#             return True
#         return False
#     except Exception as e:
#         print(f"2FA verification error: {e}")
#         return False

def is_abnormal_activity(user_id: int) -> bool:
    """Detect abnormal activity patterns (stub implementation)"""
    # In production, this would analyze login patterns, locations, etc.
    return False