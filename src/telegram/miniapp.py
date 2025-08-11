import base64
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from src.database import firebase as db
from src.telegram.auth import validate_telegram_hash
from src.utils import security, validators
from src.features.mining import token_distribution, proof_of_play
from src.security import anti_cheat
from src.features import quests
from src.utils.validators import validate_json_input
from config import config
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
        
    # Security token validators
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

@miniapp_bp.route('/user/secure-data', methods=['GET'])
def get_user_secure_data():
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

    # Create JWT token for secure data transfer
    token = security.generate_jwt({
        'user_id': user_id_int,
        'username': user_data.get('username', 'Player'),
        'balance': user_data.get('balance', 0),
        'clicks_today': user_data.get('clicks_today', 0),
        'referrals': user_data.get('referrals', 0),
        'ref_earnings': user_data.get('ref_earnings', 0),
        'bonus_claimed': user_data.get('bonus_claimed', False)
    })
    
    return jsonify({'token': token})

@miniapp_bp.route('/quests/claim_bonus', methods=['POST'])
@validators.validate_json_input({'user_id': {'type': 'int', 'required': True}})
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
@validators.validate_json_input({'user_id': {'type': 'int', 'required': True}})
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
@validators.validate_json_input({
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
    
@miniapp_bp.route('/activity/reward', methods=['POST'])
@validate_json_input({  # Fixed decorator name
    'user_id': {'type': 'int', 'required': True},
    'activity_type': {'type': 'str', 'required': True},
    'game_data': {'type': 'dict', 'required': False}
})  # Fixed closing parenthesis
def reward_activity():
    data = request.get_json()
    user_id = data['user_id']
    activity_type = data['activity_type']
    game_data = data.get('game_data', {})
    
    # Anti-cheat verification
    validator = proof_of_play.ProofOfPlay()
    if not validator.verify_play(game_data):
        return jsonify({'error': 'Activity verification failed'}), 400
    
    # Anti-farming detection
    if anti_cheat.AntiCheatSystem().detect_farming(user_id):
        return jsonify({'error': 'Suspicious activity detected'}), 403
    
    # Distribute rewards
    try:
        new_balance = token_distribution.distribute_rewards(
            user_id, 
            activity_type,
            game_data.get('score')
        )
        return jsonify({
            'success': True,
            'new_balance': new_balance
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@miniapp_bp.route('/security/check', methods=['GET'])
def security_check():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
        
    restricted = security.is_abnormal_activity(int(user_id))
    return jsonify({'restricted': restricted})

@miniapp_bp.route('/staking/create', methods=['POST'])
@validators.validate_json_input({
    'user_id': {'type': 'int', 'required': True},
    'amount': {'type': 'float', 'required': True}
})
def create_staking():
    data = request.get_json()
    user_id = data['user_id']
    amount = data['amount']
    
    # Security check for abnormal activity
    if security.is_abnormal_activity(user_id):
        return jsonify({
            'restricted': True,
            'error': 'Account restricted due to suspicious activity'
        }), 403
    
    try:
        from src.integrations.ton import create_staking_contract
        contract_address = asyncio.run(create_staking_contract(user_id, amount))
        
        if not contract_address:
            return jsonify({'success': False, 'error': 'Failed to create staking contract'}), 500
        
        # Save to database
        from src.database.firebase import save_staking
        save_staking(user_id, contract_address, amount)
        
        return jsonify({
            'success': True,
            'contract': contract_address,
            'staked': amount
        })
    except Exception as e:
        logger.error(f"Staking error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@miniapp_bp.route('/referral/generate', methods=['GET'])
def generate_referral():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
        
    try:
        from src.utils.security import generate_referral_code
        code = generate_referral_code(int(user_id))
        ref_link = f"https://t.me/{config.TELEGRAM_BOT_USERNAME}?start=ref-{code}"
        return jsonify({
            'success': True,
            'referral_code': code,
            'referral_link': ref_link
        })
    except Exception as e:
        logger.error(f"Referral generation error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@miniapp_bp.route('/referral/stats', methods=['GET'])
def referral_stats():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
        
    try:
        user_data = db.get_user_data(int(user_id))
        if not user_data:
            return jsonify({'error': 'User not found'}), 404
            
        return jsonify({
            'success': True,
            'referrals': user_data.get('referrals', 0),
            'ref_earnings': user_data.get('ref_earnings', 0)
        })
    except Exception as e:
        logger.error(f"Referral stats error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@miniapp_bp.route('/otc/rates', methods=['GET'])
def get_otc_rates():
    try:
        # This would typically fetch from an external API
        return jsonify({
            'success': True,
            'rates': {
                'USD': 5.82,
                'KES': 750,
                'USDT': 5.80
            }
        })
    except Exception as e:
        logger.error(f"OTC rates error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
    
@miniapp_bp.route('/game/complete', methods=['POST'])
@validators.validate_json_input({
    'user_id': {'type': 'int', 'required': True},
    'game_id': {'type': 'str', 'required': True},
    'score': {'type': 'int', 'required': False}
})
def record_game_completion():
    data = request.get_json()
    user_id = data['user_id']
    game_id = data['game_id']
    score = data.get('score', 0)
    
    # Security check for abnormal activity
    if security.is_abnormal_activity(user_id):
        return jsonify({
            'restricted': True,
            'error': 'Account restricted due to suspicious activity'
        }), 403
    
    try:
        # Distribute rewards based on game
        reward = 0
        if game_id == 'clicker':
            reward = config.REWARDS['clicker_base'] + (score * config.REWARDS['clicker_multiplier'])
        elif game_id == 'spin':
            reward = config.REWARDS['spin_base'] * (1 + (score / 100))
        # Add other games...
        
        # Update balance
        new_balance = db.update_balance(user_id, reward)
        
        # Update quest progress
        quest_system = QuestSystem()
        quest_system.update_quest_progress(user_id, f"{game_id}_quest", 100)
        
        return jsonify({
            'success': True,
            'reward': reward,
            'new_balance': new_balance
        })
    except Exception as e:
        logger.error(f"Game completion error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500