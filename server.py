from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from celery import Celery
from src.database.firebase import db
from src.integrations.ton import create_staking_contract, execute_swap, is_valid_ton_address
from src.utils.security import get_user_id, generate_2fa_code, verify_2fa_code, is_abnormal_activity
from src.utils.logger import logger
from src.integrations.mpesa import send_telegram_message
from src.utils.maintenance import (
    check_server_load,
    check_ton_node,
    check_payment_gateways,
    any_issues_found,
    send_alert_to_admin
)
import datetime

app = Flask(__name__)
socketio = SocketIO(app)
celery = Celery(app.name, broker='redis://localhost:6379/0')

# Blockchain Enhancements
@app.route('/api/blockchain/stake', methods=['POST'])
def stake():
    user_id = get_user_id(request)
    amount = request.json.get('amount')
    
    # Validate input
    if not amount or amount < 5:
        return jsonify({'success': False, 'error': 'Invalid amount'}), 400
    
    # Create staking contract
    contract_address = create_staking_contract(user_id, amount)
    
    # Save to database
    db.save_staking(user_id, contract_address, amount)
    
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
    tx_hash = execute_swap(user_id, from_token, to_token, amount)
    
    return jsonify({
        'success': True,
        'tx_hash': tx_hash
    })

# Security Endpoints
@app.route('/api/security/whitelist', methods=['POST'])
def add_whitelist():
    user_id = get_user_id(request)
    address = request.json.get('address')
    
    # Validate TON address
    if not is_valid_ton_address(address):
        return jsonify({'success': False, 'error': 'Invalid address'}), 400
    
    db.add_whitelist(user_id, address)
    
    return jsonify({'success': True})

@app.route('/api/security/enable-2fa', methods=['POST'])
def enable_2fa():
    user_id = get_user_id(request)
    
    # Generate and send code
    code = generate_2fa_code(user_id)
    send_telegram_message(user_id, f'Your 2FA code: {code}')
    
    return jsonify({'success': True})

@app.route('/api/security/verify-2fa', methods=['POST'])
def verify_2fa():
    user_id = get_user_id(request)
    code = request.json.get('code')
    
    if verify_2fa_code(user_id, code):
        db.enable_2fa(user_id)
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Invalid code'}), 401

# Fraud Detection
def detect_fraud(user_id):
    # Analyze user behavior
    recent_withdrawals = db.get_recent_withdrawals(user_id)
    if len(recent_withdrawals) > 5:  # More than 5 withdrawals in 24h
        db.flag_user(user_id, 'Excessive withdrawals')
        return True
    
    # More sophisticated checks
    if is_abnormal_activity(user_id):
        db.flag_user(user_id, 'Abnormal activity pattern')
        return True
    
    return False

# WebSocket Endpoint
@socketio.on('connect')
def handle_connect():
    user_id = get_user_id(request)
    join_room(user_id)
    emit('status', {'message': 'Connected'})

@socketio.on('price_alert')
def handle_price_alert(data):
    user_id = get_user_id(request)
    # Send alert to specific user
    emit('priceAlert', data, room=user_id)

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

if __name__ == '__main__':
    socketio.run(app)