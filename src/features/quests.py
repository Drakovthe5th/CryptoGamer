import logging
from datetime import datetime, timedelta
from src.database.firebase import get_user_data, update_balance
from src.utils.security import get_user_id, is_abnormal_activity
from config import config
from flask import request

logger = logging.getLogger(__name__)

def claim_daily_bonus():
    user_id = get_user_id()
    if not user_id:
        return False, 0.0
    
    # Security check
    if is_abnormal_activity(user_id):
        logger.warning(f"Abnormal activity detected for user {user_id} during bonus claim")
        return False, 0.0
    
    user = get_user_data(user_id)
    if not user:
        return False, 0.0
    
    now = datetime.utcnow()
    last_claim = user.get('last_bonus_claim')
    
    if last_claim and (now - last_claim).days < 1:
        return False, user.get('balance', 0.0)
    
    # Apply daily limits
    today = now.strftime("%Y-%m-%d")
    last_activity = user.get('last_activity_date')
    today_earned = user.get('today_earned', 0.0)
    
    if last_activity != today:
        today_earned = 0.0
        
    reward = config.REWARDS["faucet"]
    
    if user.get('account_type') != 'premium':
        max_daily = config.FREE_DAILY_EARN_LIMIT
        if today_earned + reward > max_daily:
            reward = max(max_daily - today_earned, 0)
            if reward <= 0:
                return False, user.get('balance', 0.0)
            
        today_earned += reward
    
    new_balance = update_balance(user_id, reward)
    
    # Update user record
    from src.database.firebase import get_firestore_db
    db = get_firestore_db()
    user_ref = db.collection('users').document(str(user_id))
    user_ref.update({
        'last_bonus_claim': now,
        'last_activity_date': today,
        'today_earned': today_earned
    })
    
    # Log transaction
    transaction_ref = db.collection('transactions').document()
    transaction_ref.set({
        'user_id': str(user_id),
        'type': 'bonus',
        'amount': reward,
        'timestamp': now,
        'details': 'Daily bonus claim'
    })
    
    return True, new_balance

def record_click():
    user_id = get_user_id()
    if not user_id:
        return 0, 0.0
    
    # Security check
    if is_abnormal_activity(user_id):
        logger.warning(f"Abnormal activity detected for user {user_id} during click")
        return 0, 0.0
    
    user = get_user_data(user_id)
    if not user:
        return 0, 0.0
    
    now = datetime.utcnow()
    today = now.strftime("%Y-%m-%d")
    last_click_date = user.get('last_click_date', '')
    clicks_today = user.get('clicks_today', 0)
    
    if last_click_date != today:
        clicks_today = 0
    
    if clicks_today >= 100:
        return clicks_today, user.get('balance', 0.0)
    
    # Apply daily limits
    last_activity = user.get('last_activity_date')
    today_earned = user.get('today_earned', 0.0)
    
    if last_activity != today:
        today_earned = 0.0
        
    reward = config.REWARDS["click"]
    
    if user.get('account_type') != 'premium':
        max_daily = config.FREE_DAILY_EARN_LIMIT
        if today_earned + reward > max_daily:
            reward = max(max_daily - today_earned, 0)
            if reward <= 0:
                return clicks_today, user.get('balance', 0.0)
            
        today_earned += reward
    
    new_balance = update_balance(user_id, reward)
    
    # Update user record
    from src.database.firebase import get_firestore_db
    db = get_firestore_db()
    user_ref = db.collection('users').document(str(user_id))
    user_ref.update({
        'clicks_today': clicks_today + 1,
        'last_click_date': today,
        'last_activity_date': today,
        'today_earned': today_earned
    })
    
    # Log transaction
    transaction_ref = db.collection('transactions').document()
    transaction_ref.set({
        'user_id': str(user_id),
        'type': 'click',
        'amount': reward,
        'timestamp': now,
        'details': f'Click #{clicks_today + 1}'
    })
    
    return clicks_today + 1, new_balance