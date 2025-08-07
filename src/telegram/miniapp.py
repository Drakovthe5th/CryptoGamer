from flask import Blueprint, request, jsonify
from src.database import firebase as db
from src.telegram.auth import validate_telegram_hash
from src.features import quests, ads
from src.utils import security, validation
from src.config import config
import logging

miniapp_bp = Blueprint('miniapp', __name__)
logger = logging.getLogger(__name__)

@miniapp_bp.route('/api/user/data', methods=['GET'])
def get_user_data_api():
    init_data = request.headers.get('X-Telegram-InitData')
    if not validate_telegram_hash(init_data, config.TELEGRAM_BOT_TOKEN):
        return jsonify({'error': 'Invalid hash'}), 401

    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400

    user_data = db.get_user_data(int(user_id))
    if not user_data:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({
        'balance': user_data.get('balance', 0),
        'clicks_today': user_data.get('clicks_today', 0),
        'bonus_claimed': user_data.get('bonus_claimed', False),
        'username': user_data.get('username', 'Player')
    })

@miniapp_bp.route('/api/quests/claim_bonus', methods=['POST'])
@validation.validate_json_input({'user_id': {'type': 'int', 'required': True}})
def claim_daily():
    data = request.get_json()
    user_id = data['user_id']
    
    try:
        success, new_balance = quests.claim_daily_bonus(user_id)
        return jsonify({
            'success': success,
            'new_balance': new_balance
        })
    except Exception as e:
        logger.error(f"Bonus claim error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@miniapp_bp.route('/api/quests/record_click', methods=['POST'])
@validation.validate_json_input({'user_id': {'type': 'int', 'required': True}})
def record_click():
    data = request.get_json()
    user_id = data['user_id']
    
    try:
        clicks, balance = quests.record_click(user_id)
        return jsonify({
            'clicks': clicks,
            'balance': balance
        })
    except Exception as e:
        logger.error(f"Click error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@miniapp_bp.route('/api/ads/reward', methods=['POST'])
@validation.validate_json_input({
    'user_id': {'type': 'int', 'required': True},
    'ad_id': {'type': 'str', 'required': True}
})
def ad_reward():
    data = request.get_json()
    user_id = data['user_id']
    ad_id = data['ad_id']
    
    try:
        # Weekend bonus calculation
        now = datetime.now()
        is_weekend = now.weekday() in [5, 6]
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