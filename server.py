import os
import datetime
import asyncio
import logging
import atexit
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
from celery import Celery

# Remove conflicting imports that might cause route conflicts
from src.integrations.ton import (
    is_valid_ton_address,
    initialize_ton_wallet,
    close_ton_wallet,
    process_ton_withdrawal,
    ton_wallet,
    get_wallet_status
)
from src.utils.security import get_user_id, is_abnormal_activity
from src.integrations.telegram import send_telegram_message
from src.integrations.ton import get_ton_http_client

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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app with template folder
app = Flask(__name__, template_folder='templates')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")
celery = Celery(app.name, broker='redis://localhost:6379/0')

def initialize_app():
    """Initialize application components"""
    logger.info("Initializing PRODUCTION application...")
    
    # PRODUCTION: TON wallet MUST initialize successfully
    logger.info("Initializing PRODUCTION TON wallet...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        success = loop.run_until_complete(initialize_ton_wallet())
        if not success:
            logger.critical("PRODUCTION TON WALLET INITIALIZATION FAILED")
            send_alert_to_admin("🚨 CRITICAL: TON wallet failed to initialize in production")
            raise RuntimeError("Production TON wallet initialization failed")
        
        status = loop.run_until_complete(get_wallet_status())
        logger.info(f"PRODUCTION Wallet status: {status}")
        
        if not status.get('healthy', False):
            logger.critical("PRODUCTION TON WALLET IS UNHEALTHY")
            raise RuntimeError("Production TON wallet is unhealthy")
            
    except Exception as e:
        logger.critical(f"PRODUCTION TON initialization failed: {e}")
        send_alert_to_admin(f"🚨 PRODUCTION FAILURE: {str(e)}")
        raise  # Don't continue if TON fails in production
    finally:
        loop.close()

    # Initialize Firebase
    try:
        firebase_creds = config.FIREBASE_CREDS
        initialize_firebase(firebase_creds)
        logger.info("Firebase initialized successfully")
    except Exception as e:
        logger.error(f"Firebase init failed: {e}")
        send_alert_to_admin(f"Firebase init failed: {str(e)}")
    
    logger.info("Application initialization complete")

def shutdown_app():
    """Shutdown application components"""
    logger.info("Shutting down application...")
    
    # Close TON wallet connection
    logger.info("Closing TON wallet...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(close_ton_wallet())
    except Exception as e:
        logger.error(f"Error closing TON wallet: {e}")
    finally:
        loop.close()
    
    logger.info("Application shutdown complete")

# Serve miniapp HTML at root endpoint
@app.route('/', endpoint='main_miniapp')
def serve_miniapp():
    return render_template('miniapp.html')

# API status endpoint
@app.route('/status')
def api_status():
    return jsonify({
        "status": "running",
        "service": "CryptoGameMiner",
        "version": "1.0.0",
        "crypto": "TON",
        "maintenance_available": MAINTENANCE_AVAILABLE
    }), 200

# Enhanced health check endpoint
@app.route('/health')
def health_status():
    if MAINTENANCE_AVAILABLE:
        health_data = run_health_checks()
        return jsonify(health_data)
    else:
        return jsonify({
            'status': 'basic',
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'message': 'Limited health check - maintenance module unavailable'
        })

# RENAMED Game endpoints to avoid conflicts
@app.route('/games/<path:game_path>')
def serve_game_files(game_path):
    """Serve game HTML and assets"""
    game_name = game_path.split('/')[0] if '/' in game_path else game_path
    
    valid_games = {
        'clicker': 'clicker/index.html',
        'spin': 'spin/index.html', 
        'edge-surf': 'edge-surf/index.html',  # Fixed typo
        'trex': 'trex/index.html',
        'trivia': 'trivia/index.html'
    }
    
    if game_name not in valid_games:
        return "Game not found", 404
        
    # Serve index.html for game root
    if game_path == game_name:
        return send_from_directory('static', valid_games[game_name])
        
    # Serve other assets
    try:
        return send_from_directory('static', game_path)
    except FileNotFoundError:
        return "File not found", 404

@app.route('/games/static/<path:path>')
def serve_game_static(path):
    """Serve game static files"""
    try:
        return send_from_directory('static', path)
    except FileNotFoundError:
        return "File not found", 404

@app.route('/api/user/balance', methods=['GET'])
def get_balance():
    try:
        user_id = get_user_id(request)
        # Use safe import
        from src.database.firebase import db
        balance = db.get_user_balance(user_id)
        return jsonify({'balance': balance})
    except Exception as e:
        logger.error(f"Balance error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# Blockchain Endpoints
@app.route('/api/blockchain/stake', methods=['POST'])
def stake():
    """Simplified staking endpoint"""
    try:
        user_id = get_user_id(request)
        data = request.get_json() or {}
        amount = data.get('amount', 0)
        
        if not amount or amount < 5:
            return jsonify({'success': False, 'error': 'Invalid amount'}), 400
        
        # Get wallet address
        wallet_address = ton_wallet.get_address()
        
        if not wallet_address:
            return jsonify({'success': False, 'error': 'Wallet not initialized'}), 500
        
        # Save to database
        from src.database.firebase import save_staking
        save_staking(user_id, wallet_address, amount)
        
        return jsonify({
            'success': True,
            'address': wallet_address,
            'staked': amount
        })
    except Exception as e:
        logger.error(f"Staking error: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/api/blockchain/swap', methods=['POST'])
def swap_tokens():
    """Simplified swap endpoint"""
    try:
        user_id = get_user_id(request)
        data = request.get_json() or {}
        to_address = data.get('to')
        amount = data.get('amount', 0)
        
        # Validate address
        if not is_valid_ton_address(to_address):
            return jsonify({'success': False, 'error': 'Invalid TON address'}), 400
        
        # Process as withdrawal
        result = asyncio.run(process_ton_withdrawal(user_id, amount, to_address))
        
        if result['status'] != 'success':
            error = result.get('error', 'Swap failed')
            logger.error(f"Swap failed: {error}")
            return jsonify({'success': False, 'error': error}), 500
        
        return jsonify({
            'success': True,
            'tx_hash': result.get('tx_hash', '')
        })
    except Exception as e:
        logger.error(f"Swap error: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/api/blockchain/wallet_status', methods=['GET'])
def wallet_status():
    """Get current wallet status"""
    try:
        status = asyncio.run(get_wallet_status())
        return jsonify(status)
    except Exception as e:
        logger.error(f"Wallet status error: {e}")
        return jsonify({'error': str(e)}), 500

# Security Endpoints
@app.route('/api/security/whitelist', methods=['POST'])
def add_whitelist_endpoint():
    try:
        user_id = get_user_id(request)
        data = request.get_json() or {}
        address = data.get('address')
        
        if not is_valid_ton_address(address):
            return jsonify({'success': False, 'error': 'Invalid address'}), 400
        
        from src.database.firebase import add_whitelist
        add_whitelist(user_id, address)
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Whitelist error: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

# WebSocket Endpoint
@socketio.on('connect')
def handle_connect():
    try:
        user_id = get_user_id(request)
        if user_id:
            join_room(user_id)
            emit('status', {'message': 'Connected'})
            logger.info(f"User {user_id} connected to WebSocket")
        else:
            logger.warning("WebSocket connection attempt without valid user ID")
    except Exception as e:
        logger.error(f"WebSocket connect error: {e}")

@socketio.on('price_alert')
def handle_price_alert(data):
    try:
        user_id = get_user_id(request)
        if user_id:
            emit('priceAlert', data, room=user_id)
            logger.info(f"Price alert sent to user {user_id}")
        else:
            logger.warning("Price alert attempt without valid user ID")
    except Exception as e:
        logger.error(f"Price alert error: {e}")

# Load Testing Endpoint
@app.route('/api/loadtest', methods=['POST'])
def run_load_test():
    try:
        test_config = request.get_json() or {}
        celery.send_task('run_load_test', args=[test_config])
        return jsonify({'success': True, 'message': 'Load test started'})
    except Exception as e:
        logger.error(f"Load test error: {e}")
        return jsonify({'success': False, 'error': 'Load test failed'}), 500

@app.route('/debug')
def debug_info():
    try:
        import sys
        info = {
            "python_version": sys.version,
            "firebase_creds_available": bool(getattr(config, 'FIREBASE_CREDS', None)),
            "ton_enabled": getattr(config, 'TON_ENABLED', False),
            "maintenance_available": MAINTENANCE_AVAILABLE,
            "environment": os.environ.get('NODE_ENV', 'development')
        }
        
        try:
            import pytoniq
            info["pytoniq_version"] = pytoniq.__version__
            info["pytoniq_path"] = pytoniq.__file__
        except ImportError:
            info["pytoniq_available"] = False
        
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/debug/routes')
def debug_routes():
    output = []
    for rule in app.url_map.iter_rules():
        methods = ','.join(rule.methods)
        output.append(f"{rule.endpoint}: {methods} -> {rule}")
    return jsonify({'routes': output})

# Initialize app after defining routes
try:
    initialize_app()
except Exception as e:
    logger.error(f"App initialization failed: {e}")

# Register shutdown function
atexit.register(shutdown_app)

# REMOVE CONFLICTING IMPORTS - Comment these out to avoid route conflicts
# Register miniapp blueprint
# app.register_blueprint(miniapp_bp, url_prefix='/api')
# app.register_blueprint(games_bp, url_prefix='/games')

# DON'T call configure_routes if it defines conflicting routes
# configure_routes(app)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"Starting server on port {port}")
    logger.info(f"Maintenance module available: {MAINTENANCE_AVAILABLE}")
    
    try:
        # Use Flask's built-in server which is more reliable on Render
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        logger.error(f"Server startup error: {e}")
        raise