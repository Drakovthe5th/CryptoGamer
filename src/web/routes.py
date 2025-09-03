import hmac
from datetime import datetime, timedelta
import time
from functools import wraps
from urllib.parse import parse_qs, unquote
from functools import lru_cache
import asyncio
from flask import request, jsonify, render_template, send_from_directory, json, send_file
from src.database.mongo import update_game_coins, record_reset, connect_wallet, update_balance
from src.database.mongo import get_games_list, record_game_start, get_user_data, create_user
from src.database.mongo import db, check_db_connection, update_user_data
from src.utils.security import validate_telegram_hash
from src.utils.validators import validate_telegram_init_data, validate_user_data, validate_json_input
from src.features.ads import ad_manager
from src.database.mongo import track_ad_reward
from src.features.monetization.purchases import process_purchase
from src.utils.conversions import check_daily_limit, calculate_reward
from src.utils.upgrade_manager import upgrade_manager
from src.integrations.withdrawal import get_withdrawal_processor
from src.integrations.ton import ton_wallet, initialize_on_demand, MAINNET_CONFIG, LiteClient, get_wallet_status
from src.utils.conversions import GAME_COIN_TO_TON_RATE, MAX_DAILY_GAME_COINS
from src.utils.validators import validate_ton_address
from src.telegram.config_manager import config_manager
from src.features.monetization.gifts import gift_manager
from src.features.monetization.giveaways import giveaway_manager
from src.features.referrals import ReferralSystem, referral_system
from games.tonopoly_game import TONopolyGame
from config import config
import logging
import os

logger = logging.getLogger(__name__)
client_pool = None

MAX_RESETS = 3

def validate_json_input(schema):
    """JSON validation decorator for Flask routes"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            data = request.get_json()
            if not data:
                return jsonify({"error": "Missing JSON body"}), 400
                
            for key, rules in schema.items():
                if rules.get('required') and key not in data:
                    return jsonify({"error": f"Missing required field: {key}"}), 400
                
                if key in data:
                    # Add type validation here if needed
                    pass
                    
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def configure_routes(app):
    @app.route('/api/user/init', methods=['POST'])
    def init_user():
        """Initialize user - create if doesn't exist"""
        data = request.get_json()
        user_id = data.get('user_id')
        username = data.get('username')
        
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400
            
        create_user(user_id, username)
        user = get_user_data(user_id)
        is_new_user = not user.get('welcome_bonus_received', False)
        
        return jsonify({
            'user_id': user_id,
            'game_coins': user.get('game_coins', 0),
            'balance': user.get('balance', 0.0),
            'is_new_user': is_new_user
        })
    
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

    # Serve global assets from /static/
    @app.route('/static/<path:filename>')
    @lru_cache(maxsize=100)
    def serve_global_static(filename):
        try:
            return send_from_directory(os.path.join(base_dir, 'static'), filename)
        except Exception as e:
            # Fallback for missing files
            if filename == 'images/default-avatar.png':
                return send_from_directory(os.path.join(base_dir, 'static', 'images'), 'default-avatar.png')
            elif filename == 'favicon.ico':
                return send_from_directory(os.path.join(base_dir, 'static'), 'favicon.ico')
            logger.warning(f"Static file not found: {filename}")
            return jsonify({'error': 'File not found'}), 404
        
    @app.route('/api/convert/gc-to-ton', methods=['POST'])
    def convert_gc_to_ton():
        """Convert game coins to TON"""
        try:
            data = request.get_json()
            gc_amount = data.get('gc_amount')
            ton_amount = gc_amount / 2000  # Conversion rate
            return jsonify({
                'success': True,
                'ton_amount': ton_amount,
                'conversion_rate': 2000
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/shop/items', methods=['GET'])
    def get_shop_items():
        """Return available shop items"""
        return jsonify([
            {'id': 'global_booster', 'name': '2x Earnings Booster', 'price': 2000},
            {'id': 'trivia_extra_time', 'name': 'Trivia Time Extender', 'price': 500},
            {'id': 'spin_extra_spin', 'name': 'Extra Spin', 'price': 300},
            {'id': 'clicker_auto_upgrade', 'name': 'Auto-Clicker', 'price': 1000}
        ])
    
    async def get_client():
        """Get client from connection pool"""
        global client_pool
        if not client_pool:
            client_pool = await LiteClient.from_config(MAINNET_CONFIG, pool_size=5)
        return client_pool
            
    # Error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return "Page not found", 404
    
    @app.errorhandler(500)
    def internal_error(e):
        return "Internal server error", 500
    
    # Telegram webhook endpoint
    @app.route('/webhook', methods=['POST'])
    def telegram_webhook():
        if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != config.TELEGRAM_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        return jsonify(success=True), 200

    @app.route('/api/wallet/connect', methods=['POST'])
    def connect_wallet_endpoint():
        try:
            user_id = get_user_id(request)
            if not user_id:
                return jsonify({"error": "Unauthorized"}), 401
                
            data = request.get_json()
            wallet_address = data.get('address')
            
            if not wallet_address:
                return jsonify({"error": "Wallet address required"}), 400
                
            # Save wallet address to database
            connect_wallet(user_id, wallet_address)
            
            return jsonify({"success": True, "message": "Wallet connected successfully"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/purchase', methods=['POST'])
    def make_purchase():
        user_id = get_user_id(request)
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401
            
        data = request.get_json()
        item_id = data.get('item_id')
        
        if not item_id:
            return jsonify({"error": "Missing item ID"}), 400
            
        try:
            success, message, item = process_purchase(user_id, item_id)
            if not success:
                return jsonify({"error": message}), 400
                
            return jsonify({
                "success": True,
                "message": message,
                "item": item
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/wallet/connect', methods=['POST'])
    def wallet_connect():
        user_id = get_user_id(request)
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401
            
        data = request.get_json()
        wallet_address = data.get('address')
        
        if not wallet_address or not validate_ton_address(wallet_address):
            return jsonify({"error": "Invalid wallet address"}), 400
            
        try:
            connect_wallet(user_id, wallet_address)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/upgrade', methods=['POST'])
    def upgrade_membership():
        user_id = get_user_id(request)
        tier = request.json['tier']
        
        success = upgrade_manager.upgrade_user(user_id, tier)
        if not success:
            return jsonify({"success": False, "message": "Upgrade failed"}), 400
            
        return jsonify({"success": True})
    
    @app.route('/api/withdraw', methods=['POST'])
    def withdraw_gc():
        """WITHDRAW GAME COINS AS TON"""
        user_id = get_user_id(request)
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401
        
        try:
            processor = get_withdrawal_processor()
            success, result = processor.process_gc_withdrawal(user_id)
            if not success:
                return jsonify({"error": result}), 400
                
            return jsonify({"success": True, "tx_hash": result})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/wallet/status')
    async def wallet_status():
        status = await get_wallet_status()
        return jsonify(status)

    @app.route('/api/purchase/item', methods=['POST'])
    def purchase_item():
        data = request.get_json()
        user_id = data.get('user_id')
        item_id = data.get('item_id')
        item_price = data.get('price')  # Price in TON
        
        if not user_id or not item_id or not item_price:
            return jsonify({"error": "Missing parameters"}), 400
            
        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Initialize wallet if needed
            if not loop.run_until_complete(initialize_on_demand()):
                return jsonify({"error": "Payment system unavailable"}), 500
                
            # Process purchase
            result = loop.run_until_complete(
                ton_wallet.process_in_game_purchase(user_id, item_id, item_price)
            )
            
            if result['status'] == 'success':
                # Grant item to user
                update_user_data(user_id, {'inventory': {'$push': item_id}})
                return jsonify({
                    "success": True,
                    "tx_hash": result['tx_hash'],
                    "item": item_id
                })
            return jsonify({"error": result.get('error', 'Purchase failed')}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            loop.close()
    
    @app.route('/api/shop/purchase/<item_id>', methods=['POST'])
    def purchase_item_route(item_id):
        """Process item purchase"""
        try:
            user_id = get_user_id(request)
            if not user_id:
                return jsonify({"error": "Unauthorized"}), 401

            # Process purchase
            success, message, new_balance = process_purchase(user_id, item_id)
            
            if not success:
                return jsonify({"error": message}), 400
                
            return jsonify({
                "success": True,
                "message": message,
                "new_gc_balance": new_balance,
                "item_id": item_id
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        
    @app.route('/api/withdraw/gc', methods=['POST'])
    def withdraw_game_coins():
        data = request.get_json()
        user_id = data.get('user_id')
        amount_gc = data.get('amount')
        
        if not user_id or not amount_gc:
            return jsonify({"error": "Missing parameters"}), 400
            
        if amount_gc < 200000:
            return jsonify({"error": "Minimum withdrawal is 200,000 GC (100 TON)"}), 400
            
        # Initialize wallet if needed using event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Check initialization synchronously
            if not loop.run_until_complete(initialize_on_demand()):
                return jsonify({"error": "Withdrawal system unavailable"}), 500
                
            # Process withdrawal synchronously
            result = loop.run_until_complete(ton_wallet.process_withdrawal(user_id, amount_gc))
            
            if result['status'] == 'success':
                # Deduct game coins
                update_user_data(user_id, {'game_coins': {'$inc': -amount_gc}})
                return jsonify({
                    "success": True,
                    "tx_hash": result['tx_hash'],
                    "amount_ton": amount_gc / 2000  # Convert GC to TON
                })
            return jsonify({"error": result.get('error', 'Withdrawal failed')}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            loop.close()

    @app.route('/api/config/client', methods=['GET'])
    async def get_client_config():
        """Get Telegram client configuration"""
        try:
            user_id = get_user_id(request)
            if not user_id:
                return jsonify({'error': 'Unauthorized'}), 401
                
            user_data = get_user_data(user_id)
            config_data = await config_manager.get_client_config()
            
            return jsonify({
                'success': True,
                'config': config_data,
                'user_limits': config_manager.get_user_limits(user_data)
            })
        except Exception as e:
            logger.error(f"Error getting client config: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/config/suggestions', methods=['GET'])
    def get_suggestions():
        """Get pending suggestions for user"""
        try:
            user_id = get_user_id(request)
            if not user_id:
                return jsonify({'error': 'Unauthorized'}), 401
                
            client_config = config_manager.config_cache or config.TELEGRAM_CLIENT_CONFIG
            suggestions = client_config.get('pending_suggestions', [])
            
            return jsonify({
                'success': True,
                'suggestions': suggestions,
                'dismissed': client_config.get('dismissed_suggestions', [])
            })
        except Exception as e:
            logger.error(f"Error getting suggestions: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/config/suggestions/dismiss', methods=['POST'])
    def dismiss_suggestion():
        """Dismiss a suggestion"""
        try:
            user_id = get_user_id(request)
            if not user_id:
                return jsonify({'error': 'Unauthorized'}), 401
                
            data = request.get_json()
            suggestion = data.get('suggestion')
            
            if not suggestion:
                return jsonify({'error': 'Suggestion required'}), 400
                
            # In a real implementation, you would call help.dismissSuggestion here
            # For now, we'll just track it locally
            client_config = config_manager.config_cache or config.TELEGRAM_CLIENT_CONFIG
            dismissed = client_config.get('dismissed_suggestions', [])
            
            if suggestion not in dismissed:
                dismissed.append(suggestion)
                # Update config (in real implementation, this would be via Telegram API)
                client_config['dismissed_suggestions'] = dismissed
                
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error dismissing suggestion: {str(e)}")
            return jsonify({'error': str(e)}), 500
        
    @app.route('/api/telegram/config', methods=['GET'])
    async def get_telegram_config():
        """Get Telegram client configuration"""
        try:
            user_id = get_user_id(request)
            if not user_id:
                return jsonify({'error': 'Unauthorized'}), 401
                
            user_data = get_user_data(user_id)
            config_data = await config_manager.get_client_config()
            
            return jsonify({
                'success': True,
                'config': config_data,
                'user_limits': config_manager.get_user_limits(user_data)
            })
        except Exception as e:
            logger.error(f'Error getting client config: {str(e)}')
            return jsonify({'error': str(e)}), 500

    @app.route('/api/giveaways/create', methods=['POST'])
    async def create_giveaway():
        data = await request.get_json()
        giveaway_type = data.get('type')
        
        if giveaway_type == 'premium':
            result = await giveaway_manager.create_premium_giveaway(
                user_id=data['user_id'],
                boost_peer=data['boost_peer'],
                users_count=data['users_count'],
                months=data['months']
            )
        else:
            result = await giveaway_manager.create_stars_giveaway(
                user_id=data['user_id'],
                stars_amount=data['stars_amount'],
                winners_count=data['winners_count'],
                boost_peer=data['boost_peer'],
                per_user_stars=data['per_user_stars']
            )
        
        return jsonify(result)

    @app.route('/api/gifts/available', methods=['GET'])
    async def get_available_gifts():
        result = await gift_manager.get_available_gifts()
        return jsonify(result)

    @app.route('/api/gifts/send', methods=['POST'])
    async def send_gift():
        data = await request.get_json()
        result = await gift_manager.send_star_gift(
            user_id=data['user_id'],
            recipient_id=data['recipient_id'],
            gift_id=data['gift_id'],
            hide_name=data.get('hide_name', False),
            message=data.get('message')
        )
        return jsonify(result)

    @app.route('/api/wallet/health')
    async def wallet_health():
        """Wallet health check for production monitoring"""
        try:
            status = await get_wallet_status()
            return jsonify({
                'status': 'healthy' if status.get('healthy') else 'degraded',
                'balance': status.get('balance', 0),
                'last_block': status.get('last_block', 0)
            })
        except Exception as e:
            return jsonify({'status': 'unavailable', 'error': str(e)}), 500
        
    # Add TONopoly route
    @app.route('/tonopoly')
    def tonopoly_game():
        return send_file('../static/tonopoly/index.html')

    # Add TONopoly API endpoints
    @app.route('/api/tonopoly/config', methods=['GET'])
    def get_tonopoly_config():
        """Get TONopoly game configuration"""
        game = TONopolyGame()
        return jsonify({
            'success': True,
            'config': game.get_game_config()
        })

    @app.route('/api/tonopoly/leaderboard', methods=['GET'])
    def get_tonopoly_leaderboard():
        """Get TONopoly leaderboard"""
        try:
            # This would typically fetch from database
            return jsonify({
                'success': True,
                'leaderboard': [
                    {'username': 'Player1', 'score': 15000, 'games_won': 5},
                    {'username': 'Player2', 'score': 12000, 'games_won': 3},
                    {'username': 'Player3', 'score': 9000, 'games_won': 2}
                ]
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/navigation/pages', methods=['GET'])
    def get_navigation_pages():
        """Get navigation structure for the miniapp"""
        try:
            user_id = get_user_id(request)
            if not user_id:
                return jsonify({'error': 'Unauthorized'}), 401
                
            # Get user data to check premium status
            user_data = get_user_data(int(user_id))
            is_premium = user_data.get('is_premium', False)
            
            pages = [
                {'id': 'home', 'name': 'Home', 'icon': '🏠', 'url': '/miniapp/home'},
                {'id': 'watch', 'name': 'Watch', 'icon': '📺', 'url': '/miniapp/watch'},
                {'id': 'wallet', 'name': 'Wallet', 'icon': '💰', 'url': '/miniapp/wallet'},
                {'id': 'games', 'name': 'Games', 'icon': '🎮', 'url': '/miniapp/games'},
                {'id': 'quests', 'name': 'Quests', 'icon': '📋', 'url': '/miniapp/quests'},
                {'id': 'otc', 'name': 'Trade', 'icon': '💱', 'url': '/miniapp/otc'},
                {'id': 'referrals', 'name': 'Invite', 'icon': '👥', 'url': '/miniapp/referrals'},
                {'id': 'shop', 'name': 'Shop', 'icon': '🛒', 'url': '/miniapp/shop', 'floating': True}
            ]
            
            return jsonify({
                'success': True,
                'pages': pages,
                'user_premium': is_premium
            })
        except Exception as e:
            logger.error(f"Error getting navigation pages: {str(e)}")
            return jsonify({'error': 'Internal server error'}), 500

    @app.route('/api/navigation/status', methods=['GET'])
    def get_navigation_status():
        """Get navigation status (notifications, etc)"""
        try:
            user_id = get_user_id(request)
            if not user_id:
                return jsonify({'error': 'Unauthorized'}), 401
                
            user_data = get_user_data(int(user_id))
            
            # Check for daily bonus availability
            last_bonus_claim = user_data.get('last_bonus_claim')
            bonus_available = True
            
            if last_bonus_claim:
                from datetime import datetime, timedelta
                last_claim_date = datetime.fromisoformat(last_bonus_claim)
                if datetime.now() - last_claim_date < timedelta(hours=24):
                    bonus_available = False
            
            # Check for completed quests
            completed_quests = 0
            # This would check actual quest completion status
            
            return jsonify({
                'success': True,
                'notifications': {
                    'home': bonus_available,
                    'quests': completed_quests > 0,
                    'count': (1 if bonus_available else 0) + completed_quests
                }
            })
        except Exception as e:
            logger.error(f"Error getting navigation status: {str(e)}")
            return jsonify({'error': 'Internal server error'}), 500
        
    @app.route('/api/affiliate/stats')
    def affiliate_stats():
        user_id = get_authenticated_user_id()  # Implement your auth logic
        stats = referral_system.get_referral_stats(user_id)
        stats['referral_link'] = f"https://t.me/yourbotname?start=ref_{user_id}"
        return jsonify(stats)
        
# HELPER FUNCTION
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

    
def generate_security_token(user_id):
    """Generate secure session token"""
    timestamp = str(int(time.time()))
    signature = hmac.new(
        config.SECRET_KEY.encode(),
        f"{user_id}{timestamp}".encode(),
        'sha256'
    ).hexdigest()
    return f"{user_id}.{timestamp}.{signature}"