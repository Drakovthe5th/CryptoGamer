import base64
import hashlib
import hmac
import logging
import asyncio
from flask import Blueprint, request, jsonify
from src.database import mongo as db
from src.telegram.auth import validate_init_data
from src.utils import security, validators
from src.security import anti_cheat
from src.features import quests
from src.utils.validators import validate_json_input
from config import config
import logging
from datetime import datetime

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
        
    # Validate using Telegram's initData mechanism
    if not validate_init_data(init_data, config.TELEGRAM_TOKEN):
        return jsonify({'error': 'Invalid Telegram authentication'}), 401

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
    
@miniapp_bp.route('/quests/verify', methods=['POST'])
@validate_json_input({
    'quest_type': {'type': 'str', 'required': True},
    'evidence': {'type': 'dict', 'required': True}
})
def verify_quest():
    data = request.get_json()
    quest_type = data['quest_type']
    evidence = data['evidence']
    user_id = evidence.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
    
    try:
        # Use the quest system to verify completion
        success, result = quest_system.check_quest_completion(
            user_id, quest_type, evidence
        )
        
        if success:
            return jsonify({
                'success': True,
                'reward': result.get('reward', 0),
                'message': result.get('message', 'Quest completed')
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('message', 'Verification failed')
            }), 400
            
    except Exception as e:
        logger.error(f"Quest verification error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
    
def validate_game_session(user_id, session_id):
    """Validate game session exists and belongs to user"""
    session = db.get_game_session(session_id)
    
    if not session:
        return False
    if str(session['user_id']) != str(user_id):
        return False
    if session['status'] != 'active':
        return False
        
    # Duration validation
    game_id = session['game_id']
    expected_duration = {
        'trex': (30, 600),
        'edge-surf': (60, 1800),
        'clicker': (120, 86400),
        'spin': (10, 300),
        'trivia': (60, 600)
    }
    min_dur, max_dur = expected_duration.get(game_id, (10, 3600))
    actual_duration = (datetime.now() - session['start_time']).total_seconds()

    return min_dur <= actual_duration <= max_dur

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

@miniapp_bp.route('/security/check', methods=['GET'])
def security_check():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
        
    try:
        restricted = security.is_abnormal_activity(int(user_id))
        return jsonify({'restricted': restricted})
    except Exception as e:
        logger.error(f"Security check error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

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
        db.save_staking(user_id, contract_address, amount)
        
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
@validate_json_input({
    'user_id': {'type': 'int', 'required': True},
    'game_id': {'type': 'str', 'required': True},
    'score': {'type': 'int', 'required': True},
    'session_id': {'type': 'str', 'required': True}
})
def game_completed():
    data = request.get_json()
    user_id = data['user_id']
    game_id = data['game_id']
    score = data['score']
    session_id = data['session_id']
    
    if not validate_game_session(user_id, session_id):
        return jsonify({'success': False, 'error': 'Invalid game session'}), 400

    # Anti-cheat verification
    if anti_cheat.AntiCheatSystem().detect_farming(user_id):
        return jsonify({'success': False, 'error': 'Suspicious activity detected'}), 403
    
    try:
        # Calculate reward based on game type and score
        from src.features.mining import token_distribution
        reward = token_distribution.calculate_reward(
            user_id=user_id,
            game_id=game_id,
            score=score,
            session_id=session_id
        )
        
        # Update balance
        new_balance = db.update_balance(user_id, reward)
        
        # Save game session
        db.save_game_session(
            user_id=user_id,
            game_id=game_id,
            score=score,
            reward=reward,
            session_id=session_id
        )
        
        return jsonify({
            'success': True,
            'reward': reward,
            'new_balance': new_balance
        })
        
    except Exception as e:
        logger.error(f"Game completion error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
    
@miniapp_bp.route('/user/balance', methods=['GET'])
def get_user_balance():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
        
    try:
        user_id_int = int(user_id)
        user_data = db.get_user_data(user_id_int)
        if not user_data:
            return jsonify({'error': 'User not found'}), 404
            
        return jsonify({
            'game_coins': user_data.get('game_coins', 0),
            'ton_equivalent': game_coins_to_ton(user_data.get('game_coins', 0))
        })
    except Exception as e:
        logger.error(f"User balance error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@miniapp_bp.route('/otc/quote', methods=['GET'])
def get_otc_quote():
    user_id = request.args.get('user_id')
    currency = request.args.get('currency', 'USD')
    
    from src.features.otc_desk import get_otc_quote as get_quote
    quote = get_quote(int(user_id), currency)
    
    if not quote:
        return jsonify({'error': 'Could not generate quote'}), 400
        
    return jsonify(quote)

def game_coins_to_ton(coins):
    """Convert game coins to TON equivalent"""
    return coins * config.GAME_COIN_TO_TON_RATE

def validate_init_data(init_data, bot_token):
    """Validate Telegram WebApp initData"""
    try:
        # Parse input data
        data_pairs = init_data.split('&')
        data_dict = {}
        for pair in data_pairs:
            key, value = pair.split('=')
            data_dict[key] = value
        
        # Check hash
        check_hash = data_dict.pop('hash', '')
        data_str = '\n'.join(f"{k}={v}" for k, v in sorted(data_dict.items()))
        
        secret_key = hmac.new(
            b"WebAppData", 
            bot_token.encode(), 
            hashlib.sha256
        ).digest()
        
        computed_hash = hmac.new(
            secret_key, 
            data_str.encode(), 
            hashlib.sha256
        ).hexdigest()
        
        return computed_hash == check_hash
        
    except Exception:
        return False