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
    """Extract user ID from request"""
    init_data = request.headers.get('X-Telegram-InitData', '')
    params = dict(param.split('=') for param in init_data.split('&') if '=' in param)
    user_str = params.get('user', '{}')
    try:
        import json
        user_data = json.loads(user_str)
        return user_data.get('id')
    except:
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