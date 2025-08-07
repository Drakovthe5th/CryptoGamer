import base64
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from src.database import firebase as db
from src.telegram.auth import validate_telegram_hash
from src.utils import security, validation
from src.config import config
import logging

miniapp_bp = Blueprint('miniapp', __name__)
logger = logging.getLogger(__name__)

# Security middleware for miniapp endpoints
@miniapp_bp.before_request
def miniapp_security():
    # Skip OPTIONS requests
    if request.method == 'OPTIONS':
        return
    
    # Telegram authentication
    init_data = request.headers.get('X-Telegram-InitData')
    if not init_data:
        return jsonify({'error': 'Missing Telegram init data'}), 401
        
    if not validate_telegram_hash(init_data, config.TELEGRAM_BOT_TOKEN):
        return jsonify({'error': 'Invalid Telegram authentication'}), 401
        
    # Security token validation
    security_token = request.headers.get('X-Security-Token')
    if not security_token:
        return jsonify({'error': 'Security token missing'}), 401
        
    try:
        # Decode the base64 string
        decoded_token = base64.b64decode(security_token).decode('utf-8')
        token_data = decoded_token.split(':')
        if len(token_data) != 2:
            return jsonify({'error': 'Invalid security token'}), 401
            
        token_time = int(token_data[1])
        current_time = int(datetime.utcnow().timestamp())
        
        if abs(current_time - token_time) > 300:  # 5 minutes
            return jsonify({'error': 'Security token expired'}), 401
    except Exception as e:
        logger.error(f"Security token error: {str(e)}")
        return jsonify({'error': 'Invalid security token'}), 401

@miniapp_bp.route('/user/data', methods=['GET'])
def get_user_data_api():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400

    try:
        user_id_int = int(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid user ID'}), 400

    user_data = db.get_user_data(user_id_int)
    if not user_data:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({
        'balance': user_data.get('balance', 0),
        'clicks_today': user_data.get('clicks_today', 0),
        'bonus_claimed': user_data.get('bonus_claimed', False),
        'username': user_data.get('username', 'Player')
    })

@miniapp_bp.route('/quests/claim_bonus', methods=['POST'])
@validation.validate_json_input({'user_id': {'type': 'int', 'required': True}})
def claim_daily():
    data = request.get_json()
    user_id = data['user_id']
    
    # Security check for abnormal activity
    if security.is_abnormal_activity(user_id):
        return jsonify({
            'restricted': True,
            'error': 'Account restricted due to suspicious activity'
        }), 403
    
    try:
        success, new_balance = quests.claim_daily_bonus(user_id)
        return jsonify({
            'success': success,
            'new_balance': new_balance
        })
    except Exception as e:
        logger.error(f"Bonus claim error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@miniapp_bp.route('/quests/record_click', methods=['POST'])
@validation.validate_json_input({'user_id': {'type': 'int', 'required': True}})
def record_click():
    data = request.get_json()
    user_id = data['user_id']
    
    # Security check for abnormal activity
    if security.is_abnormal_activity(user_id):
        return jsonify({
            'restricted': True,
            'error': 'Account restricted due to suspicious activity'
        }), 403
    
    try:
        clicks, balance = quests.record_click(user_id)
        return jsonify({
            'clicks': clicks,
            'balance': balance
        })
    except Exception as e:
        logger.error(f"Click error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@miniapp_bp.route('/ads/reward', methods=['POST'])
@validation.validate_json_input({
    'user_id': {'type': 'int', 'required': True},
    'ad_id': {'type': 'str', 'required': True}
})
def ad_reward():
    data = request.get_json()
    user_id = data['user_id']
    ad_id = data['ad_id']
    
    # Security check for abnormal activity
    if security.is_abnormal_activity(user_id):
        return jsonify({
            'restricted': True,
            'error': 'Account restricted due to suspicious activity'
        }), 403
    
    try:
        # Weekend bonus calculation
        now = datetime.now()
        is_weekend = now.weekday() in [5, 6]  # 5=Saturday, 6=Sunday
        base_reward = config.REWARDS['ad_view']
        reward = base_reward * (config.WEEKEND_BOOST_MULTIPLIER if is_weekend else 1.0)
        
        new_balance = db.update_balance(user_id, reward)
        return jsonify({
            'success': True,
            'reward': reward,
            'new_balance': new_balance,
            'weekend_boost': is_weekend
        })
    except Exception as e:
        logger.error(f"Ad reward error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500