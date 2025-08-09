from flask import Flask, jsonify, request, send_from_directory
from src.database.firebase import initialize_firebase
from src.features import quests, ads
from src.utils import security, validation
from games import games_bp
from tonconnect import TonConnect
from config import config
import os
import json
import logging
from datetime import datetime

def create_app():
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY
    
    # Initialize Firebase
    firebase_creds = json.loads(os.environ.get('FIREBASE_CREDS', '{}'))
    initialize_firebase(firebase_creds)
    
    # Security middleware
    @app.before_request
    def check_security():
        # Skip security checks for static files
        if request.path.startswith('/static'):
            return
        
        # Telegram authentication
        if request.path.startswith('/api'):
            init_data = request.headers.get('X-Telegram-InitData')
            if not security.validate_telegram_hash(init_data, config.TELEGRAM_BOT_TOKEN):
                return jsonify({'error': 'Invalid Telegram authentication'}), 401
                
            # Security token validation
            security_token = request.headers.get('X-Security-Token')
            if not security_token:
                return jsonify({'error': 'Security token missing'}), 401
                
            try:
                token_data = atob(security_token).split(':')
                if len(token_data) != 2:
                    return jsonify({'error': 'Invalid security token'}), 401
                    
                token_time = int(token_data[1])
                current_time = int(datetime.utcnow().timestamp())
                
                if abs(current_time - token_time) > 300:  # 5 minutes
                    return jsonify({'error': 'Security token expired'}), 401
            except:
                return jsonify({'error': 'Invalid security token'}), 401
    
    # MiniApp Endpoint - Changed to avoid conflict with server.py
    @app.route('/alt-miniapp')
    def serve_miniapp():
        return send_from_directory('templates', 'miniapp.html')
    
    # API Endpoints
    @app.route('/api/user/data', methods=['GET'])
    def get_user_data_api():
        try:
            user_id = security.get_user_id()
            if not user_id:
                return jsonify({'error': 'User ID missing'}), 400

            from src.database.firebase import get_user_data
            user_data = get_user_data(int(user_id))
            if not user_data:
                return jsonify({'error': 'User not found'}), 404

            return jsonify({
                'balance': user_data.get('balance', 0),
                'clicks_today': user_data.get('clicks_today', 0),
                'bonus_claimed': user_data.get('bonus_claimed', False),
                'username': user_data.get('username', 'Player')
            })
        except Exception as e:
            logging.error(f"User data error: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/quests/claim_bonus', methods=['POST'])
    def claim_daily():
        try:
            success, new_balance = quests.claim_daily_bonus()
            return jsonify({
                'success': success,
                'new_balance': new_balance
            })
        except Exception as e:
            logging.error(f"Bonus claim error: {str(e)}")
            return jsonify({'error': 'Internal server error'}), 500

    @app.route('/api/quests/record_click', methods=['POST'])
    def record_click():
        try:
            clicks, balance = quests.record_click()
            return jsonify({
                'clicks': clicks,
                'balance': balance
            })
        except Exception as e:
            logging.error(f"Click error: {str(e)}")
            return jsonify({'error': 'Internal server error'}), 500

    @app.route('/api/ads/reward', methods=['POST'])
    @validation.validate_json_input({
        'user_id': {'type': 'int', 'required': True},
        'ad_id': {'type': 'str', 'required': True}
    })
    def ad_reward():
        try:
            data = request.get_json()
            user_id = data['user_id']
            ad_id = data['ad_id']
            
            # Security check
            if security.is_abnormal_activity(user_id):
                return jsonify({
                    'restricted': True,
                    'error': 'Account restricted due to suspicious activity'
                }), 403
            
            # Weekend bonus calculation
            now = datetime.now()
            is_weekend = now.weekday() in [5, 6]  # 5=Saturday, 6=Sunday
            base_reward = config.REWARDS['ad_view']
            if is_weekend:
                base_reward *= config.WEEKEND_BOOST_MULTIPLIER
            
            from src.database.firebase import update_balance, track_ad_reward
            new_balance = update_balance(user_id, base_reward)
            track_ad_reward(user_id, base_reward, ad_id, is_weekend)
            
            return jsonify({
                'success': True,
                'reward': base_reward,
                'new_balance': new_balance,
                'weekend_boost': is_weekend
            })
        except Exception as e:
            logging.error(f"Ad reward error: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/security/check', methods=['GET'])
    def security_check():
        try:
            user_id = security.get_user_id()
            if not user_id:
                return jsonify({'error': 'User ID missing'}), 400
                
            restricted = security.is_abnormal_activity(user_id)
            return jsonify({
                'restricted': restricted,
                'message': 'Security check completed'
            })
        except Exception as e:
            logging.error(f"Security check error: {str(e)}")
            return jsonify({'error': 'Security check failed'}), 500

    # Health Check Endpoint - Changed to avoid conflict
    @app.route('/health-check')
    def health_status():
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat()
        })
    
    app.register_blueprint(games_bp)

    @app.route('/')
    def index():
        return render_template('index.html', games=[
            {"id": "clicker", "name": "TON Clicker"},
            {"id": "spin", "name": "Lucky Spin"},
            {"id": "trivia", "name": "Crypto Trivia"},
            {"id": "trex", "name": "TON Runner"},
            {"id": "edge_surf", "name": "Edge Surf"}
        ])
    
    @app.route('/claim-reward', methods=['POST'])
    def claim_reward():
        user_id = request.json.get('user_id')
        game_id = request.json.get('game_id')
        signature = request.json.get('signature')
        
        # Verify signature
        if not verify_signature(user_id, signature):
            return {"error": "Invalid signature"}, 401
        
        # Get reward amount
        reward = games_bp.GAME_REGISTRY[game_id].calculate_reward(user_id)
        
        # Send TON
        connector = TonConnect()
        result = connector.send_transaction(
            to_address=get_user_wallet(user_id),
            amount=int(reward * 1e9)  # In nanoTON
        )
        
        return {
            "success": True,
            "tx_hash": result["tx_hash"],
            "amount": reward
        }

    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)