from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from celery import Celery
from src.integrations.ton import (
    create_staking_contract, 
    execute_swap, 
    is_valid_ton_address,
    initialize_ton_wallet,
    close_ton_wallet,
    TONWallet
)
from src.database.firebase import (
    add_whitelist,
    enable_2fa as db_enable_2fa,
    flag_user,
    get_recent_withdrawals,
    save_staking
)
from src.utils.security import get_user_id, generate_2fa_code, verify_2fa_code, is_abnormal_activity
from src.integrations.telegram import send_telegram_message
from src.utils.maintenance import (
    check_server_load,
    check_ton_node,
    check_payment_gateways,
    any_issues_found,
    send_alert_to_admin
)
import datetime
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
celery = Celery(app.name, broker='redis://localhost:6379/0')

# Global TON wallet instance
ton_wallet = TONWallet()

def initialize_ton_wallet():
    """Initialize TON wallet connection"""
    return asyncio.run(ton_wallet.initialize())

def close_ton_wallet():
    """Close TON wallet connection"""
    return asyncio.run(ton_wallet.close())

# Initialize TON wallet on startup
@app._got_first_request
def app_initialize():
    logger.info("Initializing TON wallet...")
    initialize_ton_wallet()

@app.teardown_appcontext
def app_shutdown(exception=None):
    logger.info("Closing TON wallet...")
    close_ton_wallet()

# Blockchain Enhancements
@app.route('/api/blockchain/stake', methods=['POST'])
def stake():
    user_id = get_user_id(request)
    amount = request.json.get('amount')
    
    # Validate input
    if not amount or amount < 5:
        return jsonify({'success': False, 'error': 'Invalid amount'}), 400
    
    # Create staking contract
    contract_address = asyncio.run(create_staking_contract(user_id, amount))
    
    if not contract_address:
        return jsonify({'success': False, 'error': 'Failed to create staking contract'}), 500
    
    # Save to database
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
    
    # Execute swap on DEX
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
    
    # Validate TON address
    if not is_valid_ton_address(address):
        return jsonify({'success': False, 'error': 'Invalid address'}), 400
    
    add_whitelist(user_id, address)
    
    return jsonify({'success': True})

@app.route('/api/security/enable-2fa', methods=['POST'])
def enable_2fa_endpoint():
    user_id = get_user_id(request)
    
    # Generate and send code
    code = generate_2fa_code(user_id)
    send_telegram_message(user_id, f'Your 2FA code: {code}')
    
    return jsonify({'success': True})

@app.route('/api/security/verify-2fa', methods=['POST'])
def verify_2fa_endpoint():
    user_id = get_user_id(request)
    code = request.json.get('code')
    
    if verify_2fa_code(user_id, code):
        db_enable_2fa(user_id)
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Invalid code'}), 401

# Fraud Detection
def detect_fraud(user_id):
    # Analyze user behavior
    recent_withdrawals = get_recent_withdrawals(user_id)
    if len(recent_withdrawals) > 5:  # More than 5 withdrawals in 24h
        flag_user(user_id, 'Excessive withdrawals')
        return True
    
    # More sophisticated checks
    if is_abnormal_activity(user_id):
        flag_user(user_id, 'Abnormal activity pattern')
        return True
    
    return False

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
        # Send alert to specific user
        emit('priceAlert', data, room=user_id)
        logger.info(f"Price alert sent to user {user_id}")
    else:
        logger.warning("Price alert attempt without valid user ID")

# Infrastructure Monitoring
@celery.task
def monitor_infrastructure():
    # Check server health
    check_server_load()
    
    # Check blockchain node status
    check_ton_node()
    
    # Check payment gateway
    check_payment_gateways()
    
    # Send alerts if any issues
    if any_issues_found():
        send_alert_to_admin()

# Load Testing Endpoint
@app.route('/api/loadtest', methods=['POST'])
def run_load_test():
    test_config = request.json
    # Start load test in background
    celery.send_task('run_load_test', args=[test_config])
    return jsonify({'success': True, 'message': 'Load test started'})

# Health Check Endpoint
@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.datetime.utcnow().isoformat()
    })

@app.route('/debug')
def debug_info():
    """Endpoint for debugging environment and imports"""
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
    
    # Try to list pytoniq contents
    try:
        info["pytoniq_contents"] = dir(pytoniq)
    except Exception as e:
        info["pytoniq_contents_error"] = str(e)
    
    return jsonify(info)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"Starting server on port {port}")
    socketio.run(app, host='0.0.0.0', port=port)