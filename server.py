import os
import datetime
import asyncio
import logging
import atexit
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit, join_room
from celery import Celery
from src.integrations.ton import (
    create_staking_contract, 
    execute_swap, 
    is_valid_ton_address,
    initialize_ton_wallet,
    close_ton_wallet
)
from src.utils.security import get_user_id, is_abnormal_activity
from src.integrations.telegram import send_telegram_message
from src.utils.maintenance import (
    check_server_load,
    check_ton_node,
    check_payment_gateways,
    any_issues_found,
    send_alert_to_admin
)
from config import config
from src.web.routes import configure_routes
from src.database.firebase import initialize_firebase
from src.telegram.miniapp import miniapp_bp  # Import the miniapp blueprint

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app with template folder
app = Flask(__name__, template_folder='templates')
socketio = SocketIO(app, cors_allowed_origins="*")
celery = Celery(app.name, broker='redis://localhost:6379/0')

# Register miniapp blueprint
app.register_blueprint(miniapp_bp, url_prefix='/api')

def initialize_app():
    """Initialize application components"""
    logger.info("Initializing application...")
    
    # Initialize TON wallet
    logger.info("Initializing TON wallet...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(initialize_ton_wallet())
    except Exception as e:
        logger.error(f"TON initialization failed: {e}")
        send_alert_to_admin(f"Critical TON init failure: {str(e)}")
    finally:
        loop.close()

    # Initialize Firebase
    try:
        firebase_creds = config.FIREBASE_CREDS
        initialize_firebase(firebase_creds)
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
@app.route('/')
def serve_miniapp():
    return render_template('miniapp.html')

# API status endpoint
@app.route('/status')
def api_status():
    return jsonify({
        "status": "running",
        "service": "CryptoGameMiner",
        "version": "1.0.0",
        "crypto": "TON"
    }), 200

# Configure all routes
configure_routes(app)

# Blockchain Enhancements
@app.route('/api/blockchain/stake', methods=['POST'])
def stake():
    user_id = get_user_id(request)
    amount = request.json.get('amount')
    
    if not amount or amount < 5:
        return jsonify({'success': False, 'error': 'Invalid amount'}), 400
    
    contract_address = asyncio.run(create_staking_contract(user_id, amount))
    
    if not contract_address:
        return jsonify({'success': False, 'error': 'Failed to create staking contract'}), 500
    
    # Save to database
    from src.database.firebase import save_staking
    save_staking(user_id, contract_address, amount)
    
    return jsonify({
        'success': True,
        'contract': contract_address,
        'staked': amount
    })

@app.route('/api/blockchain/swap', methods=['POST'])
def swap_tokens():
    user_id = get_user_id(request)
    from_token = request.json.get('from')
    to_token = request.json.get('to')
    amount = request.json.get('amount')
    
    tx_hash = asyncio.run(execute_swap(user_id, from_token, to_token, amount))
    
    if not tx_hash:
        return jsonify({'success': False, 'error': 'Swap failed'}), 500
    
    return jsonify({
        'success': True,
        'tx_hash': tx_hash
    })

# Security Endpoints
@app.route('/api/security/whitelist', methods=['POST'])
def add_whitelist_endpoint():
    user_id = get_user_id(request)
    address = request.json.get('address')
    
    if not is_valid_ton_address(address):
        return jsonify({'success': False, 'error': 'Invalid address'}), 400
    
    from src.database.firebase import add_whitelist
    add_whitelist(user_id, address)
    
    return jsonify({'success': True})

# WebSocket Endpoint
@socketio.on('connect')
def handle_connect():
    user_id = get_user_id(request)
    if user_id:
        join_room(user_id)
        emit('status', {'message': 'Connected'})
        logger.info(f"User {user_id} connected to WebSocket")
    else:
        logger.warning("WebSocket connection attempt without valid user ID")

@socketio.on('price_alert')
def handle_price_alert(data):
    user_id = get_user_id(request)
    if user_id:
        emit('priceAlert', data, room=user_id)
        logger.info(f"Price alert sent to user {user_id}")
    else:
        logger.warning("Price alert attempt without valid user ID")

# Infrastructure Monitoring
@celery.task
def monitor_infrastructure():
    check_server_load()
    check_ton_node()
    check_payment_gateways()
    if any_issues_found():
        send_alert_to_admin()

# Load Testing Endpoint
@app.route('/api/loadtest', methods=['POST'])
def run_load_test():
    test_config = request.json
    celery.send_task('run_load_test', args=[test_config])
    return jsonify({'success': True, 'message': 'Load test started'})

# Health Check Endpoint
@app.route('/health')
def health_status():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.datetime.utcnow().isoformat()
    })

@app.route('/debug')
def debug_info():
    import sys
    import pytoniq
    
    info = {
        "python_version": sys.version,
        "pytoniq_version": pytoniq.__version__,
        "pytoniq_path": pytoniq.__file__,
        "firebase_creds_available": bool(config.FIREBASE_CREDS),
        "ton_enabled": config.TON_ENABLED,
        "environment_keys": list(os.environ.keys())
    }
    
    try:
        info["pytoniq_contents"] = dir(pytoniq)
    except Exception as e:
        info["pytoniq_contents_error"] = str(e)
    
    return jsonify(info)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"Starting server on port {port}")
    
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    
    server = pywsgi.WSGIServer(
        ('0.0.0.0', port), 
        app,
        handler_class=WebSocketHandler
    )
    server.serve_forever()