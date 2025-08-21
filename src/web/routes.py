import hmac
from datetime import datetime, timedelta
import time
from functools import wraps
from urllib.parse import parse_qs, unquote
from functools import lru_cache
import asyncio
from flask import request, jsonify, render_template, send_from_directory, json
from src.database.mongo import update_game_coins, record_reset, connect_wallet,update_balance
from src.database.mongo import get_games_list, record_game_start, get_user_data, create_user
from src.database.mongo import db, check_db_connection
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
    @app.route('/')
    def home():
        return "CryptoGameBot is running!"
    
    @app.route('/miniapp')
    def miniapp_route():
        return render_template('miniapp.html')
    
    @app.route('/api/user/init', methods=['POST'])
    def init_user():
        """Initialize user - create if doesn't exist"""
        data = request.get_json()
        user_id = data.get('user_id')
        username = data.get('username')
        
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400
            
        user = create_user(user_id, username)
        is_new_user = user.get('welcome_bonus_received', False)
        
        return jsonify({
            'user_id': user_id,
            'game_coins': user.get('game_coins', 0),
            'balance': user.get('balance', 0),
            'is_new_user': is_new_user
        })
    
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

    # Serve global assets from /static/ with caching
    @app.route('/static/<path:filename>')
    @lru_cache(maxsize=100)  # Cache route responses
    def serve_global_static(filename):
        try:
            response = send_from_directory(os.path.join(base_dir, 'static'), filename)
            # Add caching headers for better performance on Render
            response.headers['Cache-Control'] = 'public, max-age=3600'  # 1 hour
            return response
        except Exception as e:
            # Fallback to CDN or error page
            return jsonify({'error': 'Asset not found', 'file': filename}), 404
    
    @app.route('/api/games/list', methods=['GET'])
    def get_games_list_route():
        """Get list of available games"""
        try:
            games = get_games_list()
            return jsonify([{
                'id': g['id'],
                'name': g['name'],
                'icon': g['icon'],
                'reward': g['reward']
            } for g in games])
        except Exception as e:
            logger.error(f"Games list error: {str(e)}")
            return jsonify({'error': 'Failed to load games'}), 500
    
    # Serve game assets from /games/static/ via /game-assets/ with retry logic
    @app.route('/game-assets/<game>/<path:filename>')
    def serve_game_assets(game, filename):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = send_from_directory(
                    os.path.join(base_dir, 'games', 'static', game), 
                    filename
                )
                response.headers['Cache-Control'] = 'public, max-age=3600'
                return response
            except Exception as e:
                if attempt == max_retries - 1:
                    # Last attempt failed
                    return jsonify({
                        'error': 'Game asset not found', 
                        'game': game, 
                        'file': filename
                    }), 404
                # Wait before retrying (exponential backoff)
                time.sleep(0.1 * (2 ** attempt))

    # Serve game HTML pages with enhanced error handling
    @app.route('/games/<game>')
    def serve_game_page(game):
        try:
            response = send_from_directory(
                os.path.join(base_dir, 'games', 'static', game), 
                'index.html'
            )
            # Don't cache HTML files as heavily
            response.headers['Cache-Control'] = 'public, max-age=300'  # 5 minutes
            return response
        except Exception as e:
            # Fallback to a generic game loader
            return '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Game Loading...</title>
                <style>
                    body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                    .loader { border: 5px solid #f3f3f3; border-top: 5px solid #3498db; 
                            border-radius: 50%; width: 50px; height: 50px; 
                            animation: spin 1s linear infinite; margin: 20px auto; }
                    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
                </style>
            </head>
            <body>
                <h1>Loading Game...</h1>
                <div class="loader"></div>
                <p>If the game doesn't load, please try refreshing the page.</p>
                <button onclick="window.location.reload()">Reload</button>
            </body>
            </html>
            ''', 200

    @app.route('/api/game/start', methods=['POST'])
    def start_game_session():
        """Record game start event"""
        try:
            data = request.get_json()
            user_id = data.get('user_id')
            game_id = data.get('game_id')
            
            if not user_id or not game_id:
                return jsonify({'error': 'Missing parameters'}), 400
            
            # Security validation
            init_data = request.headers.get('X-Telegram-InitData')
            if not validate_telegram_hash(init_data, config.TELEGRAM_TOKEN):
                return jsonify({'error': 'Invalid Telegram hash'}), 401
            
            # Record game start
            session_id = record_game_start(user_id, game_id)
            return jsonify({
                'success': True,
                'session_id': session_id
            })
        except Exception as e:
            logger.error(f"Game start error: {str(e)}")
            return jsonify({'error': 'Failed to start game session'}), 500

    @app.route('/games/<game_id>/static/<path:filename>', methods=['GET'], endpoint='serve_game_static')
    def serve_game_static(game_id, filename):
        """Serve game static assets"""
        return send_from_directory(f'games/static/{game_id}/static', filename)
    
    @app.route('/api/games/launch/<game_id>', methods=['GET'], endpoint='launch_game')
    def launch_game_route(game_id):
        """Generate game launch URL"""
        try:
            user_id = get_user_id(request)
            if not user_id:
                return jsonify({"error": "Unauthorized"}), 401
            
            # Generate secure token
            token = generate_security_token(user_id)
            game_url = f"https://crptgameminer.onrender.com/games/{game_id}?user_id={user_id}&token={token}"
            
            return jsonify({
                "success": True,
                "url": game_url
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @ app.route('/api/games/token', methods=['GET'])
    def get_game_token():
        """Generate secure game token"""
        try:
            game_id = request.args.get('game')
            user_id = get_user_id(request)
            token = generate_security_token(user_id)  # Implement this function
            return jsonify({'token': token})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
    @ app.route('/api/convert/gc-to-ton', methods=['POST'])
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

    @ app.route('/api/shop/items', methods=['GET'])
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

        
    @app.route('/api/game/<game_name>/complete', methods=['POST'])
    def complete_game(game_name):
        try:
            data = request.get_json()
            user_id = data.get('user_id')
            score = data.get('score', 0)
            
            if not user_id:
                return jsonify({'error': 'User ID required'}), 400
            
            # Calculate game coin reward (score * 10 coins)
            coins = score * 10
            
            # Update user balance in game coins
            new_balance = update_game_coins(int(user_id), coins)
            
            return jsonify({
                'success': True,
                'coins': coins,
                'new_balance': new_balance,
                'message': f'You earned {coins} game coins!'
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # Game initialization with reset info
    @app.route('/api/game/<game_name>/init', methods=['POST'])  
    def init_game(game_name):
        try:
            data = request.get_json()
            user_id = data.get('user_id')
            
            if not user_id:
                return jsonify({'error': 'User ID required'}), 400
            
            # Get user data
            user_data = get_user_data(int(user_id))
            
            # Get reset count
            resets = user_data.get('daily_resets', {}).get(game_name, 0)
            resets_left = MAX_RESETS - resets
            
            return jsonify({
                'success': True,
                'game_coins': user_data.get('game_coins', 0),
                'resets_left': resets_left,
                'max_resets': MAX_RESETS
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/ads/reward', methods=['POST'])
    def ad_reward():
        try:
            init_data = request.headers.get('X-Telegram-Hash')
            user_id = request.headers.get('X-Telegram-User-ID')
            
            if not validate_telegram_hash(init_data, config.TELEGRAM_TOKEN):
                return jsonify({'error': 'Invalid Telegram hash'}), 401

            now = datetime.datetime.now()
            is_weekend = now.weekday() in [5, 6]
            base_reward = config.AD_REWARD_AMOUNT
            reward = base_reward * (config.WEEKEND_BOOST_MULTIPLIER if is_weekend else 1.0)
            
            new_balance = update_balance(int(user_id), reward)
            track_ad_reward(int(user_id), reward, 'telegram_miniapp', is_weekend)
            
            return jsonify({
                'success': True,
                'reward': reward,
                'new_balance': new_balance,
                'weekend_boost': is_weekend
            })
        except Exception as e:
            logger.error(f"Ad reward error: {str(e)}")
            return jsonify({'error': str(e)}), 500
        
    @app.route('/api/quests/claim_bonus', methods=['POST'])
    def claim_daily_bonus():
        data = request.get_json()
        user_id = data['user_id']
        
        # Check if bonus already claimed today
        user_data = get_user_data(user_id)
        last_claimed = user_data.get('last_bonus_claimed')
        today = datetime.utcnow().date()
        
        if last_claimed and last_claimed.date() == today:
            return jsonify({'error': 'Bonus already claimed today'}), 400
        
        # Award daily bonus (1000 GC)
        bonus_amount = 1000
        success, new_balance = update_game_coins(user_id, bonus_amount)
        
        if success:
            # Update last claimed time
            update_balance(user_id, {
                'last_bonus_claimed': datetime.utcnow(),
                'daily_bonus_claimed': True
            })
            
            return jsonify({
                'success': True,
                'bonus': bonus_amount,
                'new_balance': new_balance
            })
        else:
            return jsonify({'error': 'Failed to claim bonus'}), 500
        
    @app.route('/api/quests/record_click', methods=['POST'])
    def record_click():
        try:
            data = request.get_json()
            user_id = int(data['user_id'])
            user_data = get_user_data(user_id)
            
            # Reset clicks if new day
            today = datetime.utcnow().date()
            last_click_date = user_data.get('last_click_date')
            clicks_today = user_data.get('clicks_today', 0)
            
            if not last_click_date or last_click_date.date() != today:
                clicks_today = 0
            
            # Check daily limit
            if clicks_today >= 100:
                return jsonify({
                    'success': False,
                    'error': 'Daily click limit reached'
                }), 400
            
            # Award click
            click_reward = 0.0001
            new_balance = update_balance(user_id, click_reward)
            clicks_today += 1
            
            # Update user data
            users_ref = db.collection('users').document(str(user_id))
            users_ref.update({
                'clicks_today': clicks_today,
                'last_click_date': datetime.utcnow(),
                'balance': new_balance
            })
            
            return jsonify({
                'clicks': clicks_today,
                'balance': new_balance
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
    @app.route('/api/ads/slot/<slot_id>', methods=['GET'])
    def serve_ad(slot_id):
        try:
            # Get ad from ad manager
            ad = ad_manager.get_available_ad(slot_id)
            
            if not ad:
                return jsonify({
                    'html': f'''
                        <div style="width:100%;height:100%;background:#333;border-radius:8px;
                                    display:flex;align-items:center;justify-content:center;">
                            <div style="text-align:center;color:#666;">
                                <div style="font-size:2rem;margin-bottom:8px;">📺</div>
                                <div>No ad available</div>
                            </div>
                        </div>
                    ''',
                    'type': 'html'
                })
            
            return jsonify(ad)
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
    @app.route('/api/game/reset', methods=['POST'])
    def reset_game():
        """Reset game progress for a user"""
        try:
            data = request.get_json()
            user_id = data.get('user_id')
            game_id = data.get('game_id')
            
            if not user_id or not game_id:
                return jsonify({'error': 'Missing parameters'}), 400
                
            # Get user data
            user_ref = db.collection('users').document(str(user_id))
            user_data = user_ref.get().to_dict()
            
            # Check reset count
            reset_count = user_data.get('daily_resets', {}).get(game_id, 0)
            if reset_count >= MAX_RESETS:
                return jsonify({
                    'success': False,
                    'error': 'Maximum resets reached for today'
                }), 400
            
            # Update reset count
            new_resets = user_data.get('daily_resets', {})
            new_resets[game_id] = reset_count + 1
            user_ref.update({'daily_resets': new_resets})
            
            return jsonify({'success': True, 'resets_left': MAX_RESETS - (reset_count + 1)})
        except Exception as e:
            logger.error(f"Game reset error: {str(e)}")
            return jsonify({'error': 'Failed to reset game'}), 500

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
        
        if not wallet_address or not ton_wallet.is_valid_ton_address(wallet_address):
            return jsonify({"error": "Invalid wallet address"}), 400
            
        try:
            ton_wallet.save_wallet_address(user_id, wallet_address)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        
    @app.route('/api/game/complete', methods=['POST'])
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
        
        # Calculate game coin reward
        base_reward = score * 10  # 10 coins per point
        multiplier = 1.0
        
        # Apply membership multiplier
        user_data = db.get_user_data(user_id)
        if user_data and user_data.get('membership_tier') == 'PREMIUM':
            multiplier = 1.5
        elif user_data and user_data.get('membership_tier') == 'ULTIMATE':
            multiplier = 2.0
            
        coins = int(base_reward * multiplier)
        
        # Update user balance
        new_balance, actual_coins = db.update_game_coins(user_id, coins)
        
        return jsonify({
            'success': True,
            'reward': actual_coins,
            'new_balance': new_balance
        })

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
                db.grant_item(user_id, item_id)
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
                db.users.update_one(
                    {"user_id": user_id},
                    {"$inc": {"game_coins": -amount_gc}}
                )
                return jsonify({
                    "success": True,
                    "tx_hash": result['tx_hash'],
                    "amount_ton": ton_wallet.game_coins_to_ton(amount_gc)
                })
            return jsonify({"error": result.get('error', 'Withdrawal failed')}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            loop.close()

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
