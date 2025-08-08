import hashlib
import hmac
import re
import os
import time
import jwt
from urllib.parse import parse_qsl
from flask import request
from config import config
import logging
from datetime import datetime, timedelta
from google.cloud.firestore_v1.base_query import FieldFilter
from src.database.firebase import get_firestore_db

logger = logging.getLogger(__name__)

def get_user_id():
    """Extract user ID from Telegram WebApp initData"""
    init_data = request.headers.get('X-Telegram-InitData', '')
    parsed_data = parse_qsl(init_data)
    user_data = {}
    
    for key, value in parsed_data:
        if key == 'user':
            try:
                user_data = json.loads(value)
            except json.JSONDecodeError:
                logger.warning("Failed to parse user data")
    
    return user_data.get('id') if user_data else None

def generate_user_token(user_data):
    payload = {
        'id': user_data['id'],
        'username': user_data['username'],
        'balance': user_data['balance'],
        'exp': datetime.utcnow() + timedelta(minutes=15)
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm='HS256')

def verify_user_token(token):
    try:
        return jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def validate_telegram_hash(init_data, bot_token):
    """Verify Telegram WebApp authentication"""
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
    except Exception as e:
        logger.error(f"Telegram auth verification failed: {str(e)}")
        return False

def is_abnormal_activity(user_id):
    """Check for abnormal activity patterns"""
    try:
        db = get_firestore_db()
        
        # Get last 10 transactions
        transactions_ref = db.collection('transactions')
        query = transactions_ref.where('user_id', '==', str(user_id)) \
            .order_by('timestamp', direction=firestore.Query.DESCENDING) \
            .limit(10)
        
        transactions = [doc.to_dict() for doc in query.stream()]
        
        # Check for rapid consecutive actions
        if len(transactions) > 5:
            last_timestamp = transactions[0]['timestamp']
            first_timestamp = transactions[-1]['timestamp']
            time_diff = (last_timestamp - first_timestamp).total_seconds()
            
            if time_diff < 10:  # 10 seconds for 10 actions
                return True
        
        # Check for large withdrawal requests
        withdrawals_ref = db.collection('withdrawals')
        withdrawal_query = withdrawals_ref.where('user_id', '==', str(user_id)) \
            .where('status', '==', 'pending') \
            .where('timestamp', '>', datetime.utcnow() - timedelta(minutes=5))
        
        withdrawal_amount = sum(
            [doc.get('amount', 0) for doc in withdrawal_query.stream()]
        )
        
        if withdrawal_amount > config.USER_DAILY_WITHDRAWAL_LIMIT / 2:
            return True
        
        return False
    except Exception as e:
        logger.error(f"Abnormal activity check failed: {str(e)}")
        return False

def validate_ton_address(address: str) -> bool:
    """Validate TON wallet address format"""
    pattern = r'^EQ[0-9a-zA-Z]{48}$'
    return re.match(pattern, address) is not None

def validate_mpesa_number(number: str) -> bool:
    """Validate M-Pesa number format (Kenya)"""
    pattern = r'^2547\d{8}$'
    return re.match(pattern, number) is not None

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_amount(amount: str, min_amount: float) -> bool:
    """Validate amount format and minimum"""
    try:
        amount_float = float(amount)
        return amount_float >= min_amount
    except ValueError:
        return False