import os
import datetime
import asyncio
import logging
import atexit
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_socketio import SocketIO, emit, join_room
from celery import Celery
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
from src.web.routes import configure_routes
from src.database.firebase import initialize_firebase
from src.telegram.miniapp import miniapp_bp  # Import the miniapp blueprint
from games.games import games_bp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app with template folder
app = Flask(__name__, template_folder='templates')
socketio = SocketIO(app, cors_allowed_origins="*")
celery = Celery(app.name, broker='redis://localhost:6379/0')

# Register miniapp blueprint
app.register_blueprint(miniapp_bp, url_prefix='/api')
app.register_blueprint(games_bp, url_prefix='/games')

def initialize_app():
    """Initialize application components"""
    logger.info("Initializing application...")
    
    # Initialize TON wallet
    logger.info("Initializing TON wallet...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Try LiteClient first
        success = loop.run_until_complete(initialize_ton_wallet())
        if not success:
            logger.warning("Falling back to HTTP client")
            # Initialize HTTP client if LiteClient fails
            client = loop.run_until_complete(get_ton_http_client(config.TON_API_KEY))
        status = loop.run_until_complete(get_wallet_status())
        logger.info(f"Wallet status: {status}")
    except Exception as e:
        logger.error(f"TON initialization failed: {e}")
        send_alert_to_admin(f"TON init failure: {str(e)}")
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

# Run initialization when app starts
initialize_app()

# Register shutdown function
atexit.register(shutdown_app)

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

# Game endpoints
@app.route('/games/<game_name>', endpoint='serve_game_main')
def serve_game(game_name):
    """Serve game HTML based on game name"""
    valid_games = {
        'clicker': 'clicker/clicker.html',
        'spin': 'spin/spin.html',
        'edge-surf': 'egde-surf/index.html',
        'trex': 'trex/index.html',
        'trivia': 'trivia/index.html'
    }
    
    if game_name not in valid_games:
        return "Game not found", 404
        
    return send_from_directory('static', valid_games[game_name])

# Serve static files for games
@app.route('/games/static/<path:path>')
def game_static(path):
    return send_from_directory('static', path)

# Configure all routes - moved after other route definitions
configure_routes(app)

# Blockchain Endpoints
@app.route('/api/blockchain/stake', methods=['POST'])
def stake():
    """
    Simplified staking endpoint that uses the TON wallet address
    instead of creating a staking contract
    """
    try:
        user_id = get_user_id(request)
        amount = request.json.get('amount')
        
        if not amount or amount < 5:
            return jsonify({'success': False, 'error': 'Invalid amount'}), 400
        
        # Get wallet address instead of creating contract
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
    """
    Simplified swap endpoint that processes the transaction as a withdrawal
    to the specified address
    """
    try:
        user_id = get_user_id(request)
        to_address = request.json.get('to')  # Destination address
        amount = request.json.get('amount')
        
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
        address = request.json.get('address')
        
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

# Infrastructure Monitoring
if MAINTENANCE_AVAILABLE:
    @celery.task
    def monitor_infrastructure():
        try:
            check_server_load()
            check_ton_node()
            check_payment_gateways()
            if any_issues_found():
                send_alert_to_admin("Infrastructure monitoring alert")
        except Exception as e:
            logger.error(f"Infrastructure monitoring error: {e}")

# Load Testing Endpoint
@app.route('/api/loadtest', methods=['POST'])
def run_load_test():
    try:
        test_config = request.json
        celery.send_task('run_load_test', args=[test_config])
        return jsonify({'success': True, 'message': 'Load test started'})
    except Exception as e:
        logger.error(f"Load test error: {e}")
        return jsonify({'success': False, 'error': 'Load test failed'}), 500

@app.route('/debug')
def debug_info():
    try:
        import sys
        import pytoniq
        
        info = {
            "python_version": sys.version,
            "pytoniq_version": pytoniq.__version__,
            "pytoniq_path": pytoniq.__file__,
            "firebase_creds_available": bool(config.FIREBASE_CREDS),
            "ton_enabled": config.TON_ENABLED,
            "maintenance_available": MAINTENANCE_AVAILABLE,
            "environment": os.environ.get('NODE_ENV', 'development')
        }
        
        try:
            info["pytoniq_contents"] = dir(pytoniq)
        except Exception as e:
            info["pytoniq_contents_error"] = str(e)
        
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"Starting server on port {port}")
    logger.info(f"Maintenance module available: {MAINTENANCE_AVAILABLE}")
    
    try:
        from gevent import pywsgi
        from geventwebsocket.handler import WebSocketHandler
        
        server = pywsgi.WSGIServer(
            ('0.0.0.0', port), 
            app,
            handler_class=WebSocketHandler
        )
        logger.info("Starting gevent WSGI server")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Server startup error: {e}")
        # Fallback to Flask development server
        logger.info("Falling back to Flask development server")
        app.run(host='0.0.0.0', port=port, debug=False)