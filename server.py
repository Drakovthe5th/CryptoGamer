import os
import datetime
import asyncio
import logging
import atexit
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
from celery import Celery

# Production TON imports
from src.integrations.ton import (
    initialize_ton_wallet,
    process_ton_withdrawal,
    ton_wallet,
    get_wallet_status
)
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
from src.database.firebase import initialize_firebase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
    """Initialize production application with strict validation"""
    logger.info("🚀 STARTING PRODUCTION APPLICATION")
    
    # CRITICAL: TON wallet MUST work in production
    logger.info("Initializing PRODUCTION TON wallet...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Initialize TON wallet
        success = loop.run_until_complete(initialize_ton_wallet())

        if not success:
            logger.critical("❌ PRODUCTION TON WALLET INITIALIZATION FAILED")
            send_alert_to_admin("🚨 CRITICAL: TON wallet failed to initialize")
            raise RuntimeError("Production TON wallet initialization failed")
        
        # Verify wallet status
        status = loop.run_until_complete(get_wallet_status())
        logger.info(f"✅ PRODUCTION Wallet Status: {status}")
        
        if not status.get('healthy', False):
            logger.critical("❌ PRODUCTION TON WALLET IS UNHEALTHY")
            raise RuntimeError("Production TON wallet is unhealthy")
        
        # Log production wallet details
        logger.info(f"🏦 Production Wallet: {status.get('address', 'N/A')}")
        logger.info(f"💰 Wallet Balance: {status.get('balance', 0):.6f} TON")
        logger.info(f"🌐 Network: {status.get('network', 'unknown')}")
        
    except Exception as e:
        logger.critical(f"❌ PRODUCTION TON INITIALIZATION FAILED: {e}")
        send_alert_to_admin(f"🚨 PRODUCTION FAILURE: {str(e)}")
        raise
    finally:
        loop.close()

    # Initialize Firebase
    try:
        firebase_creds = config.FIREBASE_CREDS
        initialize_firebase(firebase_creds)
        logger.info("✅ Firebase initialized successfully")
    except Exception as e:
        logger.error(f"❌ Firebase initialization failed: {e}")
        send_alert_to_admin(f"Firebase init failed: {str(e)}")
        # Don't fail the app for Firebase issues in production
    
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

@app.route('/health')
def health_check():
    """Production health check"""
    try:
        # Get TON wallet status
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            wallet_status = loop.run_until_complete(get_wallet_status())
        finally:
            loop.close()
        
        health_data = {
            'status': 'healthy' if wallet_status.get('healthy', False) else 'unhealthy',
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'wallet': {
                'healthy': wallet_status.get('healthy', False),
                'balance': wallet_status.get('balance', 0),
                'network': wallet_status.get('network', 'unknown')
            },
            'maintenance_available': MAINTENANCE_AVAILABLE
        }
        
        if MAINTENANCE_AVAILABLE:
            additional_checks = run_health_checks()
            health_data.update(additional_checks)
        
        status_code = 200 if health_data['status'] == 'healthy' else 503
        return jsonify(health_data), status_code
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.datetime.utcnow().isoformat()
        }), 500

# Game Routes
@app.route('/games/<path:game_path>')
def serve_games(game_path):
    """Serve game files"""
    try:
        game_name = game_path.split('/')[0] if '/' in game_path else game_path
        
        valid_games = {
            'clicker': 'clicker/index.html',
            'spin': 'spin/index.html', 
            'edge-surf': 'edge-surf/index.html',
            'trex': 'trex/index.html',
            'trivia': 'trivia/index.html'
        }
        
        if game_name not in valid_games:
            return jsonify({'error': 'Game not found'}), 404
            
        # Serve index for game root
        if game_path == game_name:
            return send_from_directory('static', valid_games[game_name])
            
        # Serve other game assets
        return send_from_directory('static', game_path)
        
    except Exception as e:
        logger.error(f"Game serving error: {e}")
        return jsonify({'error': 'Game file not found'}), 404

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
        from src.database.firebase import db
        balance = db.get_user_balance(user_id)
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
        from src.database.firebase import save_staking
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

# Error Handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

# Initialize application
try:
    initialize_production_app()
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