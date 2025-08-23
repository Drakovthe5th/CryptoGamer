import os
import sys
import datetime
import asyncio
import logging
import atexit
import base64
import json
from games.games import games_bp
from flask import Flask, request, Blueprint, jsonify, render_template, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
from celery import Celery
from src.web.routes import configure_routes
from src.database.mongo import initialize_mongodb
from src.utils.security import get_user_id, validate_telegram_hash, is_abnormal_activity
from src.features.quests import claim_daily_bonus, record_click
from src.features.ads import ad_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Production TON imports
try:
    from src.integrations.ton import (
        initialize_ton_wallet,
        process_ton_withdrawal,
        ton_wallet,
        get_wallet_status
    )
except ImportError as e:
    logger.error(f"Import error: {e}")
    raise
except Exception as e:
    logger.error(f"Initialization error: {e}")
    raise

# Graceful import of maintenance functions
try:
    from src.utils.maintenance import (
        check_server_load,
        check_ton_node,
        check_payment_gateways,
        any_issues_found,
        send_alert_to_admin,
        run_health_checks
    )
    MAINTENANCE_AVAILABLE = True
    logger.info("Maintenance module imported successfully")
except ImportError as e:
    MAINTENANCE_AVAILABLE = False
    logger.warning(f"Maintenance module not available: {e}")
    
    # Fallback functions
    def check_server_load(): 
        return False
    def check_ton_node(): 
        return True
    def check_payment_gateways(): 
        return True
    def any_issues_found(): 
        return False
    def send_alert_to_admin(msg): 
        logger.warning(f"ALERT: {msg}")
    def run_health_checks(): 
        return {"status": "limited", "message": "Full health checks unavailable"}

from config import config
from src.database.mongo import initialize_mongodb
from src.database.mongo import get_user_data, save_user_data, update_balance, track_ad_reward

# Create Flask app
app = Flask(__name__, template_folder='templates')
CORS(app, origins="*")
socketio = SocketIO(app, cors_allowed_origins="*")

# Register the games blueprint
app.register_blueprint(games_bp)

miniapp_bp = Blueprint('miniapp', __name__)

# Register games blueprint
app.register_blueprint(games_bp, url_prefix='/games')

# Celery configuration
celery = Celery(
    app.name, 
    broker=os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
)

def initialize_production_app():
    """Initialize production application with more resilience"""
    logger.info("🚀 STARTING PRODUCTION APPLICATION")
    
    # Initialize MongoDB
    if not initialize_mongodb():
        logger.critical("❌ MongoDB initialization failed")
        exit(1)
    
    # TON wallet initialization
    logger.info("Initializing PRODUCTION TON wallet...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Initialize TON wallet
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(initialize_ton_wallet())
        if success:
            status = loop.run_until_complete(get_wallet_status())
            logger.info(f"TON wallet ready | Balance: {status['balance']:.6f} TON")
        else:
            logger.warning("TON wallet initialization failed")
            config.TON_ENABLED = False
    except Exception as e:
        logger.critical(f"TON initialization failed: {str(e)}")
        config.TON_ENABLED = False
    
    logger.info("✅ PRODUCTION APPLICATION INITIALIZATION COMPLETE")

def shutdown_production_app():
    """Graceful shutdown of production application"""
    logger.info("🛑 SHUTTING DOWN PRODUCTION APPLICATION")
    # TON wallet shutdown handled internally
    logger.info("✅ PRODUCTION SHUTDOWN COMPLETE")

# Security middleware
@app.before_request
def check_security():
    """Enhanced security middleware with proper error handling"""
    # Skip security checks for static files and health endpoints
    if (request.path.startswith('/static') or 
        request.path.startswith('/health') or
        request.path.startswith('/games') or
        request.path == '/'):
        return
    
    # Only check security for API endpoints
    if request.path.startswith('/api') and not request.path.startswith('/api/miniapp'):
        try:
            # Telegram authentication
            init_data = request.headers.get('X-Telegram-InitData')
            if not init_data:
                return jsonify({'error': 'Telegram authentication required'}), 401
            
            if not validate_telegram_hash(init_data, config.TELEGRAM_TOKEN):
                return jsonify({'error': 'Invalid Telegram authentication'}), 401
                
            # Security token validation
            security_token = request.headers.get('X-Security-Token')
            if not security_token:
                return jsonify({'error': 'Security token missing'}), 401
                
            try:
                # Use base64.b64decode instead of atob (which is JavaScript)
                security_token = security_token.replace('-', '+').replace('_', '/')
                padding = len(security_token) % 4
                if padding > 0:
                    security_token += '=' * (4 - padding)
                    
                token_data = base64.b64decode(security_token).decode('utf-8').split(':')
                
                if len(token_data) != 2:
                    return jsonify({'error': 'Invalid security token format'}), 401
                    
                token_time = int(token_data[1])
                current_time = int(datetime.datetime.utcnow().timestamp())
                
                # 5 minutes expiry
                if abs(current_time - token_time) > 300:
                    return jsonify({'error': 'Security token expired'}), 401
                    
            except (ValueError, TypeError, base64.binascii.Error) as e:
                logger.warning(f"Invalid security token: {e}")
                return jsonify({'error': 'Invalid security token'}), 401
                
        except Exception as e:
            logger.error(f"Security check failed: {e}")
            return jsonify({'error': 'Security check failed'}), 500

# Core Routes
@app.route('/')
def serve_main_app():
    """Serve main application"""
    return render_template('miniapp.html')

@app.route('/status')
def api_status():
    """Production API status"""
    return jsonify({
        "status": "running",
        "service": "CryptoGameMiner",
        "version": "1.0.0",
        "crypto": "TON", 
        "environment": "production",
        "maintenance_available": MAINTENANCE_AVAILABLE
    }), 200

@app.route('/static/<path:path>')
def serve_static(path):
    root_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(root_dir, 'static')
    return send_from_directory(static_dir, path)

@app.route('/play/<game_name>')
def play_game(game_name):
    """Redirect to the appropriate game page"""
    return redirect(url_for('games.serve_game_page', game_name=game_name))

# API Routes
@app.route('/api/user/balance', methods=['GET'])
def get_user_balance():
    """Get user balance"""
    try:
        user_id = get_user_id(request)
        from src.database.mongo import get_user_balance as get_balance
        balance = get_balance(user_id)
        return jsonify({'balance': balance, 'user_id': user_id})
    except Exception as e:
        logger.error(f"Balance error: {e}")
        return jsonify({'error': 'Failed to get balance'}), 500

# User Data API
@app.route('/api/user/data', methods=['GET'])
def get_user_data_api():
    """Get user data with enhanced error handling"""
    try:
        user_id = get_user_id(request)
        if not user_id:
            return jsonify({'error': 'User ID missing'}), 400

        user_data = get_user_data(int(user_id))
        
        if not user_data:
            # Create new user if doesn't exist
            user_data = {
                'balance': 0,
                'clicks_today': 0,
                'bonus_claimed': False,
                'username': f'Player{user_id}'
            }
            # Save new user data
            save_user_data(int(user_id), user_data)
            logger.info(f"Created new user: {user_id}")

        return jsonify({
            'success': True,
            'balance': user_data.get('balance', 0),
            'clicks_today': user_data.get('clicks_today', 0),
            'bonus_claimed': user_data.get('bonus_claimed', False),
            'username': user_data.get('username', f'Player{user_id}')
        })
        
    except Exception as e:
        logger.error(f"Get user data error: {str(e)}")
        return jsonify({'error': 'Failed to fetch user data'}), 500

# Quests API
@app.route('/api/quests/claim_bonus', methods=['POST'])
def claim_daily_bonus_route():
    """Claim daily bonus with security checks"""
    try:
        user_id = get_user_id(request)
        if not user_id:
            return jsonify({'error': 'User ID missing'}), 400
        
        # Check for suspicious activity
        if is_abnormal_activity(user_id):
            return jsonify({
                'success': False,
                'error': 'Account restricted due to suspicious activity'
            }), 403
        
        success, new_balance = claim_daily_bonus(user_id)
        
        return jsonify({
            'success': success,
            'new_balance': new_balance,
            'message': 'Daily bonus claimed successfully!' if success else 'Bonus already claimed today'
        })
        
    except Exception as e:
        logger.error(f"Claim bonus error: {str(e)}")
        return jsonify({
            'success': False, 
            'error': 'Failed to claim bonus'
        }), 500

@app.route('/api/quests/record_click', methods=['POST'])
def record_click_route():
    """Record user click with anti-cheat measures"""
    try:
        user_id = get_user_id(request)
        if not user_id:
            return jsonify({'error': 'User ID missing'}), 400
        
        # Check for suspicious activity
        if is_abnormal_activity(user_id):
            return jsonify({
                'success': False,
                'error': 'Account restricted due to suspicious activity'
            }), 403
        
        clicks, balance = record_click(user_id)
        
        return jsonify({
            'success': True,
            'clicks': clicks,
            'balance': balance
        })
        
    except Exception as e:
        logger.error(f"Record click error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to record click'
        }), 500

# Ads API
@app.route('/api/ads/reward', methods=['POST'])
def ad_reward_route():
    """Process ad reward with validation"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request data'}), 400
            
        user_id = data.get('user_id')
        ad_id = data.get('ad_id')
        
        if not user_id or not ad_id:
            return jsonify({'error': 'User ID and Ad ID required'}), 400
        
        # Security check
        if is_abnormal_activity(user_id):
            return jsonify({
                'success': False,
                'error': 'Account restricted due to suspicious activity'
            }), 403
        
        # Calculate reward with bonuses
        now = datetime.datetime.now()
        is_weekend = now.weekday() in [5, 6]  # Saturday, Sunday
        base_reward = config.REWARDS['ad_view']
        
        if is_weekend:
            base_reward *= config.WEEKEND_BOOST_MULTIPLIER
        
        # Update balance and track reward
        new_balance = update_balance(user_id, base_reward)
        track_ad_reward(user_id, base_reward, ad_id, is_weekend)
        
        return jsonify({
            'success': True,
            'reward': base_reward,
            'new_balance': new_balance,
            'weekend_boost': is_weekend
        })
        
    except Exception as e:
        logger.error(f"Ad reward error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to process ad reward'
        }), 500

# Security API
@app.route('/api/security/check', methods=['GET'])
def security_check_route():
    """Check user security status"""
    try:
        user_id = get_user_id(request)
        if not user_id:
            return jsonify({'error': 'User ID missing'}), 400
            
        restricted = is_abnormal_activity(user_id)
        
        return jsonify({
            'success': True,
            'restricted': restricted,
            'message': 'Security check completed',
            'timestamp': datetime.datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Security check error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Security check failed'
        }), 500

# Blockchain API Routes
@app.route('/api/blockchain/stake', methods=['POST'])
def blockchain_stake():
    """Blockchain staking endpoint"""
    try:
        user_id = get_user_id(request)
        data = request.get_json() or {}
        amount = data.get('amount', 0)
        
        if not amount or amount < 5:
            return jsonify({'success': False, 'error': 'Minimum stake is 5 TON'}), 400
        
        wallet_address = ton_wallet.wallet_address
        if not wallet_address:
            return jsonify({'success': False, 'error': 'Wallet unavailable'}), 500
        
        # Save staking record
        from src.database.mongo import save_staking
        save_staking(user_id, wallet_address, amount)
        
        return jsonify({
            'success': True,
            'address': wallet_address,
            'staked': amount,
            'message': f'Staked {amount} TON successfully'
        })
        
    except Exception as e:
        logger.error(f"Staking error: {e}")
        return jsonify({'success': False, 'error': 'Staking failed'}), 500

@app.route('/api/blockchain/withdraw', methods=['POST'])
def blockchain_withdraw():
    """Production withdrawal endpoint"""
    try:
        user_id = get_user_id(request)
        data = request.get_json() or {}
        to_address = data.get('address')
        amount = float(data.get('amount', 0))
        
        # Validate inputs
        if not to_address or not ton_wallet.is_valid_ton_address(to_address):
            return jsonify({'success': False, 'error': 'Invalid TON address'}), 400
            
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Invalid amount'}), 400
        
        # Process withdrawal
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                process_ton_withdrawal(user_id, amount, to_address)
            )
        finally:
            loop.close()
        
        if result['status'] == 'success':
            logger.info(f"✅ Withdrawal success: {amount} TON to {to_address}")
            return jsonify({
                'success': True,
                'tx_hash': result.get('tx_hash'),
                'amount': amount,
                'address': to_address
            })
        else:
            error = result.get('error', 'Withdrawal failed')
            logger.error(f"❌ Withdrawal failed: {error}")
            return jsonify({'success': False, 'error': error}), 400
            
    except Exception as e:
        logger.error(f"Withdrawal error: {e}")
        return jsonify({'success': False, 'error': 'Internal error'}), 500

@app.route('/api/blockchain/wallet_status', methods=['GET'])
def blockchain_wallet_status():
    """Get blockchain wallet status"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            status = loop.run_until_complete(get_wallet_status())
        finally:
            loop.close()
            
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Wallet status error: {e}")
        return jsonify({'error': str(e), 'healthy': False}), 500

# WebSocket Events
@socketio.on('connect')
def handle_socket_connect():
    """Handle WebSocket connections"""
    try:
        user_id = get_user_id(request)
        if user_id:
            join_room(f"user_{user_id}")
            emit('status', {'message': 'Connected to production server'})
            logger.info(f"User {user_id} connected via WebSocket")
        else:
            emit('error', {'message': 'Authentication required'})
    except Exception as e:
        logger.error(f"WebSocket connect error: {e}")
        emit('error', {'message': 'Connection failed'})

@socketio.on('disconnect')
def handle_socket_disconnect():
    """Handle WebSocket disconnections"""
    try:
        user_id = get_user_id(request)
        logger.info(f"User {user_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket disconnect error: {e}")

# Debug Routes (Production Safe)
@app.route('/debug/info')
def debug_info():
    """Safe debug information for production"""
    try:
        import sys
        
        info = {
            "python_version": sys.version.split()[0],
            "environment": os.environ.get('NODE_ENV', 'development'),
            "ton_network": getattr(config, 'TON_NETWORK', 'unknown'),
            "maintenance_available": MAINTENANCE_AVAILABLE,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        
        # Don't expose sensitive config in production
        if os.environ.get('NODE_ENV') != 'production':
            info.update({
                "firebase_available": bool(getattr(config, 'FIREBASE_CREDS', None)),
                "ton_enabled": getattr(config, 'TON_ENABLED', False)
            })
        
        return jsonify(info)
        
    except Exception as e:
        return jsonify({"error": "Debug info unavailable"}), 500
    
# Dummy ad endpoint
@app.route('/api/ads/slot/<slot_name>', methods=['GET'])
def get_ad_slot(slot_name):
    """Return dummy ad data"""
    return jsonify({
        'url': 'https://example.com',
        'image': 'https://via.placeholder.com/300x250?text=Ad+Placeholder',
        'reward': 0.001
    })

# Staking data endpoint
@app.route('/api/staking/data', methods=['GET'])
def get_staking_data():
    """Return staking information"""
    return jsonify({
        'apy': 8.5,
        'min_stake': 5,
        'current_stake': 0,
        'rewards_earned': 0
    })

# Referral endpoints
@app.route('/api/referral/generate', endpoint='referral_generate')
def generate_referral():
    """Generate referral link"""
    user_id = request.args.get('user_id', 'default')
    return jsonify({
        'link': f'https://t.me/CryptoGameMinerBot?start=ref-{user_id}'
    })

@app.route('/api/referral/stats', endpoint='referral_stats')
def referral_stats():
    """Return referral statistics"""
    return jsonify({
        'count': 0,
        'earnings': 0,
        'active': 0,
        'level': 1
    })

# OTC rates endpoint
@app.route('/api/otc/rates', endpoint='otc_rates')
def get_otc_rates():
    """Return exchange rates"""
    return jsonify({
        'TON_USD': 6.80,
        'TON_KES': 950,
        'TON_EUR': 6.20,
        'TON_USDT': 6.75
    })

# Error Handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(403)
def forbidden(error):
    return jsonify({
        'error': 'Access forbidden',
        'message': 'You do not have permission to access this resource'
    }), 403

# Health check endpoint
@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        return jsonify({
            'status': 'healthy',
            'service': 'CryptoGameMiner',
            'version': '1.0.0',
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'features': {
                'games': config.FEATURE_GAMES,
                'ads': config.FEATURE_ADS,
                'otc': config.FEATURE_OTC
            }
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.datetime.utcnow().isoformat()
        }), 500

try:
    initialize_production_app()
    configure_routes(app)  # Add routes from routes.py
except Exception as e:
    logger.critical(f"❌ FAILED TO START PRODUCTION APP: {e}")
    exit(1)

# Register shutdown handler
atexit.register(shutdown_production_app)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    debug_mode = os.environ.get('NODE_ENV') != 'production'
    
    logger.info(f"🚀 Starting production server on port {port}")
    logger.info(f"🔧 Debug mode: {'ON' if debug_mode else 'OFF'}")
    
    try:
        # Use socketio.run for WebSocket support
        socketio.run(
            app,
            host='0.0.0.0',
            port=port,
            debug=debug_mode,
            allow_unsafe_werkzeug=True  # Needed for production WebSocket
        )
    except Exception as e:
        logger.critical(f"❌ Server startup failed: {e}")
        exit(1)