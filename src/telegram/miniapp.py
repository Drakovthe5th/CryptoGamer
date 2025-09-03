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
from src.database.mongo import get_user_data
from src.features.monetization.ad_revenue import AdRevenue
from config import config
from src.telegram.config_manager import config_manager
import logging
from fastapi import APIRouter
from games.chess_masters import router as chess_router
from src.telegram.stars import (
    create_stars_invoice as create_stars_invoice_service,
    process_stars_payment as process_stars_payment_service,
    get_stars_balance
)
from src.telegram.subscriptions import (
    create_subscription_invoice,
    get_user_subscriptions,
    cancel_subscription
)
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

def get_user_id(request):
    """Extract and validate user ID from Telegram WebApp init data"""
    init_data = request.headers.get('X-Telegram-InitData')
    
    # Return early if no init data
    if not init_data:
        logger.warning("No Telegram init data found in headers")
        return None
    
    try:
        # Validate the init data hash first
        if not validate_telegram_init_data(init_data):
            logger.warning("Invalid Telegram init data hash")
            return None
        
        # Parse the init data
        parsed_data = parse_qs(init_data)
        
        # Extract user data
        user_str = parsed_data.get('user', [None])[0]
        if not user_str:
            logger.warning("No user data found in init data")
            return None
        
        # Parse user JSON
        user_data = json.loads(user_str)
        
        # Extract and validate user ID
        user_id = user_data.get('id')
        if not user_id or not isinstance(user_id, int):
            logger.warning(f"Invalid user ID format: {user_id}")
            return None
        
        # Additional security checks
        if not validate_user_data(user_data):
            logger.warning(f"User data validation failed for user {user_id}")
            return None
        
        logger.info(f"Successfully extracted user ID: {user_id}")
        return user_id
        
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
        logger.error(f"Error parsing Telegram init data: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_user_id: {str(e)}")
        return None

@miniapp_bp.route('/api/telegram/config', methods=['GET'])
async def get_telegram_config():
    """Get Telegram client configuration"""
    try:
        user_id = get_user_id(request)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
            
        # Get user data to check premium status
        user_data = get_user_data(user_id)
        
        # Get appropriate limits based on premium status
        limits = config_manager.get_user_limits(user_data)
        
        return jsonify({
            'success': True,
            'config': limits,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting Telegram config: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@miniapp_bp.route('/api/user/limits', methods=['GET'])
def get_user_limits():
    """Get user-specific limits based on Telegram config"""
    user_id = get_user_id(request)
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401
        
    user_data = get_user_data(user_id)
    limits = config_manager.get_user_limits(user_data)
    
    return jsonify({
        'success': True,
        'limits': {
            'upload_size': limits.get('upload_max_fileparts', 4000) * 524288,
            'caption_length': limits.get('caption_length_limit', 1024),
            'bio_length': limits.get('about_length_limit', 70),
            'dialog_filters': limits.get('dialog_filters_limit', 10),
            'pinned_chats': limits.get('dialogs_pinned_limit', 5),
            'saved_gifs': limits.get('saved_gifs_limit', 200),
            'favorite_stickers': limits.get('stickers_faved_limit', 5)
        },
        'is_premium': user_data.get('is_premium', False)
    })

@miniapp_bp.route('/user/secure-data', methods=['GET'])
def get_user_secure_data():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400

    try:
        user_id_int = int(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid user ID'}), 400

    user_data = get_user_data(user_id_int)
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
        success, result = quests.check_quest_completion(
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
        return jsonify({
            'success': True,
            'contract': "EQABC...",
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
        user_data = get_user_data(int(user_id))
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
    
@miniapp_bp.route('/user/balance', methods=['GET'])
def get_user_balance():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
        
    try:
        user_id_int = int(user_id)
        user_data = get_user_data(user_id_int)
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
            if '=' in pair:
                key, value = pair.split('=', 1)
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

@miniapp_bp.route('/shop/create-invoice', methods=['POST'])
@validators.validate_json_input({
    'product_id': {'type': 'str', 'required': True},
    'user_id': {'type': 'int', 'required': True}
})
def create_stars_invoice():
    """Create a Telegram Stars invoice for shop items"""
    data = request.get_json()
    product_id = data['product_id']
    user_id = data['user_id']
    
    try:
        # Get product details
        product = Config.IN_GAME_ITEMS.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
            
        # Create Stars invoice
        invoice = create_stars_invoice_service(
            user_id=user_id,
            product_id=product_id,
            title=product.get('name', product_id),
            description=product.get('description', ''),
            price_stars=product.get('price_stars', 0),
            photo_url=product.get('image_url')
        )
        
        return jsonify({
            'success': True,
            'invoice': invoice,
            'product': product
        })
        
    except Exception as e:
        logger.error(f"Invoice creation failed: {str(e)}")
        return jsonify({'error': 'Invoice creation failed'}), 500

@miniapp_bp.route('/shop/process-payment', methods=['POST'])
@validators.validate_json_input({
    'user_id': {'type': 'int', 'required': True},
    'credentials': {'type': 'dict', 'required': True},
    'product_id': {'type': 'str', 'required': True}
})
def process_payment():
    """Process Telegram Stars payment"""
    data = request.get_json()
    user_id = data['user_id']
    credentials = data['credentials']
    product_id = data['product_id']
    
    # Anti-cheat validation
    if security.is_abnormal_activity(user_id):
        return jsonify({
            'restricted': True,
            'error': 'Account restricted due to suspicious activity'
        }), 403
    
    # Process payment
    result = process_stars_purchase(user_id, credentials, product_id)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400

@miniapp_bp.route('/payment/methods', methods=['GET'])
def get_payment_methods():
    """Get available payment methods for user"""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
        
    try:
        user_data = get_user_data(int(user_id))
        if not user_data:
            return jsonify({'error': 'User not found'}), 404
            
        methods = [
            {
                'type': 'stars',
                'name': 'Telegram Stars',
                'enabled': True,
                'currency': 'XTR'
            },
            {
                'type': 'ton',
                'name': 'TON Coin',
                'enabled': user_data.get('wallet_address') is not None,
                'currency': 'TON'
            }
        ]
        
        return jsonify({
            'success': True,
            'methods': methods,
            'default_method': 'stars'
        })
    except Exception as e:
        logger.error(f"Payment methods error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
    
@miniapp_bp.route('/web-events/handle', methods=['POST'])
def web_events_handler():
    """Handle incoming web events from Telegram Mini Apps"""
    return handle_web_event()

@miniapp_bp.route('/payment/process-stars', methods=['POST'])
@validators.validate_json_input({
    'user_id': {'type': 'int', 'required': True},
    'credentials': {'type': 'dict', 'required': True},
    'title': {'type': 'str', 'required': True},
    'amount': {'type': 'float', 'required': True}
})
def process_stars_payment():
    """Process Telegram Stars payment"""
    data = request.get_json()
    user_id = data['user_id']
    credentials = data['credentials']
    title = data['title']
    amount = data['amount']
    
    # Validate payment
    if not anti_cheat.validate_payment_request(user_id, credentials):
        return jsonify({'success': False, 'error': 'Payment validation failed'})
    
    # Process Stars payment
    success = process_telegram_stars_payment(user_id, credentials, title, amount)
    
    if success:
        # Add the purchased value to user's balance
        db.update_balance(user_id, amount)
        return jsonify({'success': True, 'message': 'Payment processed successfully'})
    else:
        return jsonify({'success': False, 'error': 'Payment processing failed'})

def process_telegram_stars_payment(user_id, credentials, title, amount):
    """Process Telegram Stars payment"""
    from src.telegram.web_events import handle_payment_submit
    return handle_payment_submit(user_id, credentials, title, amount)
    # Implement actual Telegram Stars payment processing
    logger.info(f"Processing Stars payment for user {user_id}: {title} - {amount} Stars")
    return True  # Placeholder - implement actual payment processing

@miniapp_bp.route('/stars/balance', methods=['GET'])
def get_stars_balance_route():
    """Get user's Telegram Stars balance"""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
        
    try:
        balance = get_stars_balance(int(user_id))
        return jsonify({
            'success': True,
            'balance': balance,
            'currency': 'XTR'
        })
    except Exception as e:
        logger.error(f"Stars balance error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@miniapp_bp.route('/stars/create-invoice', methods=['POST'])
@validators.validate_json_input({
    'user_id': {'type': 'int', 'required': True},
    'product_id': {'type': 'str', 'required': True},
    'title': {'type': 'str', 'required': True},
    'description': {'type': 'str', 'required': True},
    'price_stars': {'type': 'int', 'required': True}
})
def create_stars_invoice_route():
    """Create a Telegram Stars invoice"""
    data = request.get_json()
    user_id = data['user_id']
    product_id = data['product_id']
    title = data['title']
    description = data['description']
    price_stars = data['price_stars']
    
    try:
        invoice = create_stars_invoice_service(
            user_id=user_id,
            product_id=product_id,
            title=title,
            description=description,
            price_stars=price_stars
        )
        
        return jsonify({
            'success': True,
            'invoice': invoice
        })
    except Exception as e:
        logger.error(f"Stars invoice creation error: {str(e)}")
        return jsonify({'error': 'Invoice creation failed'}), 500

@miniapp_bp.route('/stars/process-payment', methods=['POST'])
@validators.validate_json_input({
    'user_id': {'type': 'int', 'required': True},
    'form_id': {'type': 'int', 'required': True},
    'invoice': {'type': 'dict', 'required': True}
})
def process_stars_payment_route():
    """Process Telegram Stars payment"""
    data = request.get_json()
    user_id = data['user_id']
    form_id = data['form_id']
    invoice_data = data['invoice']
    
    try:
        result = process_stars_payment_service(
            user_id=user_id,
            form_id=form_id,
            invoice_data=invoice_data
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Stars payment error: {str(e)}")
        return jsonify({'error': 'Payment processing failed'}), 500

@miniapp_bp.route('/subscriptions/create', methods=['POST'])
@validators.validate_json_input({
    'user_id': {'type': 'int', 'required': True},
    'channel_id': {'type': 'int', 'required': True},
    'period': {'type': 'int', 'required': True},
    'amount': {'type': 'int', 'required': True}
})
def create_subscription_route():
    """Create a channel subscription"""
    data = request.get_json()
    user_id = data['user_id']
    channel_id = data['channel_id']
    period = data['period']
    amount = data['amount']
    
    try:
        invoice = create_subscription_invoice(
            user_id=user_id,
            channel_id=channel_id,
            period=period,
            amount=amount
        )
        
        return jsonify({
            'success': True,
            'invoice': invoice
        })
    except Exception as e:
        logger.error(f"Subscription creation error: {str(e)}")
        return jsonify({'error': 'Subscription creation failed'}), 500

@miniapp_bp.route('/subscriptions/list', methods=['GET'])
def list_subscriptions_route():
    """Get user's active subscriptions"""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
        
    try:
        subscriptions = get_user_subscriptions(int(user_id))
        return jsonify({
            'success': True,
            'subscriptions': subscriptions
        })
    except Exception as e:
        logger.error(f"Subscriptions list error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@miniapp_bp.route('/subscriptions/cancel', methods=['POST'])
@validators.validate_json_input({
    'user_id': {'type': 'int', 'required': True},
    'subscription_id': {'type': 'str', 'required': True}
})
def cancel_subscription_route():
    """Cancel a subscription"""
    data = request.get_json()
    user_id = data['user_id']
    subscription_id = data['subscription_id']
    
    try:
        success = cancel_subscription(user_id, subscription_id)
        return jsonify({
            'success': success
        })
    except Exception as e:
        logger.error(f"Subscription cancellation error: {str(e)}")
        return jsonify({'error': 'Cancellation failed'}), 500
    
@miniapp_bp.route('/api/attach-menu/bots', methods=['GET'])
def get_attach_menu_bots():
    """Get available attachment menu bots"""
    try:
        user_id = get_user_id(request)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        
        # Get installed bots
        installed_bots = []  # This would come from database
        
        # Get available bots (would typically call Telegram API)
        available_bots = []  # This would come from messages.getAttachMenuBots
        
        return jsonify({
            'success': True,
            'installed': installed_bots,
            'available': available_bots
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@miniapp_bp.route('/api/attach-menu/install', methods=['POST'])
@validators.validate_json_input({
    'bot_id': {'type': 'int', 'required': True}
})
def install_attach_bot():
    """Install an attachment menu bot"""
    try:
        user_id = get_user_id(request)
        bot_id = request.json['bot_id']
        
        # Call Telegram API to install
        success = True  # Placeholder
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Installation failed'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def is_admin(user_id):
    """Check if user is admin"""
    # Implement admin check logic
    return user_id in config.ADMINS

async def get_channel_peer():
    """Get channel peer for admin functions"""
    # Implement channel peer retrieval
    return None

@miniapp_bp.route('/admin/revenue/stats', methods=['GET'])
async def get_admin_revenue_stats():
    """Get ad revenue stats (admin only)"""
    user_id = get_user_id(request)
    if not is_admin(user_id):
        return jsonify({'error': 'Admin access required'}), 403
        
    try:
        # Get channel/bot peer
        peer = await get_channel_peer()
        
        # Get stats (placeholder)
        stats = {
            'revenue': 1000,
            'currency': 'XTR',
            'period': 'month'
        }
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Revenue stats error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@miniapp_bp.route('/admin/revenue/withdraw', methods=['POST'])
@validators.validate_json_input({
    'password': {'type': 'str', 'required': True}
})
async def admin_withdraw_revenue():
    """Withdraw ad revenue (admin only)"""
    user_id = get_user_id(request)
    if not is_admin(user_id):
        return jsonify({'error': 'Admin access required'}), 403
        
    data = request.get_json()
    password = data['password']
    
    try:
        peer = await get_channel_peer()
        
        # Placeholder implementation
        return jsonify({
            'success': True,
            'url': 'https://fragment.com/withdraw'
        })
    except Exception as e:
        logger.error(f"Revenue withdrawal error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
    
# Add TONopoly betting handling
@miniapp_bp.route('/tonopoly/bet', methods=['POST'])
@validators.validate_json_input({
    'user_id': {'type': 'int', 'required': True},
    'game_id': {'type': 'str', 'required': True},
    'amount': {'type': 'int', 'required': True}
})
def tonopoly_place_bet():
    """Place a bet for a TONopoly game"""
    data = request.get_json()
    user_id = data['user_id']
    game_id = data['game_id']
    amount = data['amount']
    
    try:
        # Get game from storage
        game = active_games.get(game_id)
        if not game:
            return jsonify({'error': 'Game not found'}), 404
            
        # Validate bet
        if not game.validate_bet(user_id, amount):
            return jsonify({'error': 'Invalid bet amount'}), 400
            
        # Create Stars invoice
        invoice = create_stars_invoice_service(
            user_id=user_id,
            product_id=f"tonopoly_bet_{game_id}",
            title=f"TONopoly Bet - Game {game_id}",
            description=f"Bet for TONopoly game",
            price_stars=amount
        )
        
        return jsonify({
            'success': True,
            'invoice': invoice
        })
        
    except Exception as e:
        logger.error(f"TONopoly bet placement error: {str(e)}")
        return jsonify({'error': 'Bet placement failed'}), 500

@miniapp_bp.route('/tonopoly/bet/process', methods=['POST'])
@validators.validate_json_input({
    'user_id': {'type': 'int', 'required': True},
    'game_id': {'type': 'str', 'required': True},
    'credentials': {'type': 'dict', 'required': True}
})
def tonopoly_process_bet():
    """Process a TONopoly bet payment"""
    data = request.get_json()
    user_id = data['user_id']
    game_id = data['game_id']
    credentials = data['credentials']
    
    try:
        # Get game from storage
        game = active_games.get(game_id)
        if not game:
            return jsonify({'error': 'Game not found'}), 404
            
        # Process payment
        result = process_stars_payment_service(
            user_id=user_id,
            form_id=0,  # This would come from the invoice
            invoice_data={
                'product_id': f"tonopoly_bet_{game_id}",
                'title': f"TONopoly Bet - Game {game_id}",
                'description': f"Bet for TONopoly game",
                'price_stars': game.bet_amount
            }
        )
        
        if result['success']:
            # Record bet payment
            await game.add_bet_payment(user_id, game.bet_amount)
            
            return jsonify({
                'success': True,
                'message': 'Bet payment processed successfully'
            })
        else:
            return jsonify({'error': 'Payment processing failed'}), 400
            
    except Exception as e:
        logger.error(f"TONopoly bet processing error: {str(e)}")
        return jsonify({'error': 'Bet processing failed'}), 500
    
# miniapp.py - Updated with 7-page structure endpoints

@miniapp_bp.route('/api/home/data', methods=['GET'])
def get_home_data():
    """Get home page data including daily bonus status"""
    try:
        user_id = get_user_id(request)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
            
        # Get user data
        user_data = get_user_data(int(user_id))
        if not user_data:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if daily bonus is available
        last_bonus_claim = user_data.get('last_bonus_claim')
        bonus_available = True
        
        if last_bonus_claim:
            from datetime import datetime, timedelta
            last_claim_date = datetime.fromisoformat(last_bonus_claim)
            if datetime.now() - last_claim_date < timedelta(hours=24):
                bonus_available = False
        
        # Get featured games
        featured_games = [
            {'id': 'trivia', 'name': 'Crypto Trivia', 'icon': '❓', 'type': 'free'},
            {'id': 'spin', 'name': 'Lucky Spin', 'icon': '🎡', 'type': 'free'},
            {'id': 'clicker', 'name': 'TON Clicker', 'icon': '🖱️', 'type': 'free'},
            {'id': 'trex', 'name': 'T-Rex Runner', 'icon': '🦖', 'type': 'free'}
        ]
        
        return jsonify({
            'success': True,
            'bonus_available': bonus_available,
            'bonus_amount': 0.05,  # 0.05 TON
            'featured_games': featured_games,
            'user_data': {
                'game_coins': user_data.get('game_coins', 0),
                'clicks_today': user_data.get('clicks_today', 0),
                'click_limit': user_data.get('is_premium', False) and 200 or 100
            }
        })
    except Exception as e:
        logger.error(f"Error getting home data: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@miniapp_bp.route('/api/home/claim-bonus', methods=['POST'])
def claim_daily_bonus():
    """Claim daily bonus"""
    try:
        user_id = get_user_id(request)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
            
        # Check if bonus already claimed today
        user_data = get_user_data(int(user_id))
        last_bonus_claim = user_data.get('last_bonus_claim')
        
        if last_bonus_claim:
            from datetime import datetime, timedelta
            last_claim_date = datetime.fromisoformat(last_bonus_claim)
            if datetime.now() - last_claim_date < timedelta(hours=24):
                return jsonify({
                    'success': False,
                    'error': 'Bonus already claimed today'
                }), 400
        
        # Award bonus (0.05 TON = 100 GC)
        bonus_gc = 100
        new_balance = user_data.get('game_coins', 0) + bonus_gc
        
        # Update user data
        update_user_data(int(user_id), {
            'game_coins': new_balance,
            'last_bonus_claim': datetime.now().isoformat()
        })
        
        return jsonify({
            'success': True,
            'bonus_amount': bonus_gc,
            'new_balance': new_balance,
            'message': 'Daily bonus claimed successfully!'
        })
    except Exception as e:
        logger.error(f"Error claiming bonus: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@miniapp_bp.route('/api/watch/ads', methods=['GET'])
def get_available_ads():
    """Get available video ads"""
    try:
        user_id = get_user_id(request)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
            
        # This would typically come from an ad network API
        available_ads = [
            {'id': 'ad_1', 'duration': 30, 'reward': 50},
            {'id': 'ad_2', 'duration': 45, 'reward': 75},
            {'id': 'ad_3', 'duration': 60, 'reward': 100}
        ]
        
        return jsonify({
            'success': True,
            'ads': available_ads
        })
    except Exception as e:
        logger.error(f"Error getting ads: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@miniapp_bp.route('/api/watch/reward', methods=['POST'])
def reward_ad_view():
    """Reward user for watching an ad"""
    try:
        user_id = get_user_id(request)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
            
        data = request.get_json()
        ad_id = data.get('ad_id')
        
        if not ad_id:
            return jsonify({'error': 'Ad ID required'}), 400
            
        # Get user data
        user_data = get_user_data(int(user_id))
        
        # Calculate reward (this would normally come from ad data)
        reward = 50  # Default reward
        
        # Apply weekend bonus if applicable
        from datetime import datetime
        if datetime.now().weekday() in [5, 6]:  # Saturday or Sunday
            reward = int(reward * 1.2)  # 20% bonus
        
        # Update user balance
        new_balance = user_data.get('game_coins', 0) + reward
        ads_watched = user_data.get('ads_watched', 0) + 1
        
        update_user_data(int(user_id), {
            'game_coins': new_balance,
            'ads_watched': ads_watched,
            'ads_today': user_data.get('ads_today', 0) + 1
        })
        
        return jsonify({
            'success': True,
            'reward': reward,
            'new_balance': new_balance,
            'message': f'You earned {reward} GC for watching the ad!'
        })
    except Exception as e:
        logger.error(f"Error rewarding ad view: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@miniapp_bp.route('/api/games/list', methods=['GET'])
def get_games_list():
    """Get list of all games"""
    try:
        user_id = get_user_id(request)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
            
        # Get user data to check premium status
        user_data = get_user_data(int(user_id))
        is_premium = user_data.get('is_premium', False)
        
        # Free games
        free_games = [
            {'id': 'trivia', 'name': 'Crypto Trivia', 'icon': '❓', 'type': 'free', 'reward': 'Up to 100 GC per game'},
            {'id': 'spin', 'name': 'Lucky Spin', 'icon': '🎡', 'type': 'free', 'reward': 'Up to 500 GC per spin'},
            {'id': 'clicker', 'name': 'TON Clicker', 'icon': '🖱️', 'type': 'free', 'reward': '1 GC per 10 clicks'},
            {'id': 'trex', 'name': 'T-Rex Runner', 'icon': '🦖', 'type': 'free', 'reward': 'Up to 200 GC per game'},
            {'id': 'edge-surf', 'name': 'Edge Surf', 'icon': '🏄', 'type': 'free', 'reward': 'Up to 150 GC per game'}
        ]
        
        # Premium games (only available to premium users)
        premium_games = [
            {'id': 'sabotage', 'name': 'Crypto Crew: Sabotage', 'icon': '🕵️', 'type': 'premium', 'reward': 'Up to 8000 GC per game', 'premium_required': True},
            {'id': 'chess', 'name': 'Chess Masters', 'icon': '♟️', 'type': 'premium', 'reward': 'Up to 5000 GC per game', 'premium_required': True},
            {'id': 'pool', 'name': 'Pool Masters', 'icon': '🎱', 'type': 'premium', 'reward': 'Up to 5000 GC per game', 'premium_required': True},
            {'id': 'poker', 'name': 'Poker Royale', 'icon': '🃏', 'type': 'premium', 'reward': 'Up to 10000 GC per game', 'premium_required': True}
        ]
        
        # Include premium games only if user has premium
        games = free_games + (premium_games if is_premium else [])
        
        return jsonify({
            'success': True,
            'games': games,
            'is_premium': is_premium
        })
    except Exception as e:
        logger.error(f"Error getting games list: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@miniapp_bp.route('/api/quests/list', methods=['GET'])
def get_quests_list():
    """Get list of quests and missions"""
    try:
        user_id = get_user_id(request)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
            
        # Get user data for progress tracking
        user_data = get_user_data(int(user_id))
        
        # Daily quests
        daily_quests = [
            {
                'id': 'daily_bonus',
                'name': 'Claim Daily Bonus',
                'description': 'Claim your daily bonus of 0.05 TON',
                'reward': 100,  # GC
                'completed': user_data.get('last_bonus_claim') is not None and 
                            (datetime.now() - datetime.fromisoformat(user_data.get('last_bonus_claim'))).days < 1,
                'type': 'daily'
            },
            {
                'id': 'watch_ads',
                'name': 'Watch 3 Ads',
                'description': 'Watch video ads to earn extra rewards',
                'reward': 150,
                'completed': user_data.get('ads_today', 0) >= 3,
                'progress': user_data.get('ads_today', 0),
                'target': 3,
                'type': 'daily'
            },
            {
                'id': 'play_games',
                'name': 'Play 2 Games',
                'description': 'Play any 2 games to complete this quest',
                'reward': 200,
                'completed': user_data.get('games_today', 0) >= 2,
                'progress': user_data.get('games_today', 0),
                'target': 2,
                'type': 'daily'
            }
        ]
        
        # Social media quests
        social_quests = [
            {
                'id': 'follow_twitter',
                'name': 'Follow on Twitter',
                'description': 'Follow our Twitter account',
                'reward': 2000,
                'completed': user_data.get('quests', {}).get('follow_twitter', False),
                'type': 'social'
            },
            {
                'id': 'join_telegram',
                'name': 'Join Telegram Channel',
                'description': 'Join our official Telegram channel',
                'reward': 2000,
                'completed': user_data.get('quests', {}).get('join_telegram', False),
                'type': 'social'
            },
            {
                'id': 'post_twitter',
                'name': 'Post on Twitter',
                'description': 'Create a post about CryptoGamer on Twitter',
                'reward': 3000,
                'completed': user_data.get('quests', {}).get('post_twitter', False),
                'type': 'social'
            }
        ]
        
        return jsonify({
            'success': True,
            'daily_quests': daily_quests,
            'social_quests': social_quests
        })
    except Exception as e:
        logger.error(f"Error getting quests list: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@miniapp_bp.route('/api/otc/rates', methods=['GET'])
def get_otc_rates():
    """Get OTC exchange rates"""
    try:
        # This would typically fetch from an external API
        rates = {
            'TON_USD': 6.80,
            'TON_KES': 950,
            'TON_EUR': 6.20,
            'TON_USDT': 6.75
        }
        
        return jsonify({
            'success': True,
            'rates': rates
        })
    except Exception as e:
        logger.error(f"Error getting OTC rates: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@miniapp_bp.route('/api/otc/swap', methods=['POST'])
def swap_ton_cash():
    """Swap TON for cash"""
    try:
        user_id = get_user_id(request)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
            
        data = request.get_json()
        amount = data.get('amount')
        currency = data.get('currency')
        payment_details = data.get('payment_details')
        
        if not amount or not currency or not payment_details:
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Validate amount
        user_data = get_user_data(int(user_id))
        ton_equivalent = amount / 2000  # Convert GC to TON
        
        if user_data.get('game_coins', 0) < amount:
            return jsonify({'error': 'Insufficient balance'}), 400
            
        # Process swap (this would typically integrate with OTC partner)
        # For now, we'll just simulate the transaction
        
        # Update user balance
        new_balance = user_data.get('game_coins', 0) - amount
        update_user_data(int(user_id), {
            'game_coins': new_balance,
            'otc_transactions': user_data.get('otc_transactions', []) + [{
                'date': datetime.now().isoformat(),
                'amount': amount,
                'currency': currency,
                'status': 'processing'
            }]
        })
        
        return jsonify({
            'success': True,
            'message': f'Swap request for {amount} GC ({ton_equivalent:.6f} TON) to {currency} submitted',
            'transaction_id': f"otc_{datetime.now().timestamp()}",
            'new_balance': new_balance
        })
    except Exception as e:
        logger.error(f"Error processing OTC swap: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@miniapp_bp.route('/api/referrals/data', methods=['GET'])
def get_referral_data():
    """Get referral data for user"""
    try:
        user_id = get_user_id(request)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
            
        user_data = get_user_data(int(user_id))
        
        referral_code = user_data.get('referral_code', f'ref_{user_id}')
        referral_link = f"https://t.me/CryptoGameMinerBot?start={referral_code}"
        
        referrals = user_data.get('referrals', [])
        referral_count = len(referrals)
        
        # Calculate referral earnings (20% of referred users' earnings)
        ref_earnings = user_data.get('ref_earnings', 0)
        
        # Check milestone progress
        milestones = [
            {'count': 3, 'reward': 0.01, 'reached': referral_count >= 3},
            {'count': 10, 'reward': 0.03, 'reached': referral_count >= 10},
            {'count': 50, 'reward': 0.25, 'reached': referral_count >= 50},
            {'count': 100, 'reward': 1.00, 'reached': referral_count >= 100}
        ]
        
        return jsonify({
            'success': True,
            'referral_code': referral_code,
            'referral_link': referral_link,
            'referral_count': referral_count,
            'referral_earnings': ref_earnings,
            'milestones': milestones
        })
    except Exception as e:
        logger.error(f"Error getting referral data: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500