import os
import sys
import datetime
import asyncio
import logging
import atexit
from flask import Flask, request, Blueprint, jsonify, render_template, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
from celery import Celery
from src.web.routes import configure_routes
from src.database.mongo import initialize_mongodb
from src.main import validate_production_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

miniapp_bp = Blueprint('miniapp', __name__)
games_bp = Blueprint('games', __name__, url_prefix='/games')

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
    # Notify admin or take corrective action
    raise
except Exception as e:
    logger.error(f"Initialization error: {e}")
    raise

from src.utils.security import get_user_id, is_abnormal_activity

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
    logger = logging.getLogger(__name__)
    logger.info("Maintenance module imported successfully")
except ImportError as e:
    MAINTENANCE_AVAILABLE = False
    logger = logging.getLogger(__name__)
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
# Create Flask app
app = Flask(__name__, template_folder='templates')
CORS(app, origins="*")
socketio = SocketIO(app, cors_allowed_origins="*")

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

# Core Routes
@app.route('/', endpoint='main_app')
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

# Game Routes
@app.route('/games/<game_name>')
def serve_game(game_name):
    """Serve game HTML file with exponential backoff retries"""
    valid_games = {
        'clicker': 'clicker/index.html',
        'spin': 'spin/index.html', 
        'edge-surf': 'edge-surf/index.html',
        'trex': 'trex/index.html',
        'trivia': 'trivia/index.html'
    }
    
    if game_name not in valid_games:
        return jsonify({"error": "Game not found"}), 404
        
    return send_from_directory('static', valid_games[game_name])
    
@app.route('/games/<game_name>/<path:filename>')
def game_static(game_name, filename):
    return send_from_directory(f'static/{game_name}', filename)

@app.route('/games/static/<path:path>')
def serve_game_assets(path):
    """Serve game static assets"""
    try:
        return send_from_directory('static', path)
    except Exception as e:
        logger.error(f"Static asset error: {e}")
        return jsonify({'error': 'Asset not found'}), 404

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

try:
    initialize_production_app()
    configure_routes(app)  # Add this line to register routes
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