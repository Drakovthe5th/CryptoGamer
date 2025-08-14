from flask import request, jsonify, render_template, send_from_directory
from src.database.firebase import (
    get_user_data, update_balance, 
    process_ton_withdrawal, track_ad_reward, SERVER_TIMESTAMP
)
from src.utils.security import validate_telegram_hash
from config import Config
import logging
import datetime
import os

logger = logging.getLogger(__name__)

def configure_routes(app):
    @app.route('/')
    def home_route():  # Changed from 'index' to 'home'
        return "CryptoGameBot is running!"
    
    @app.route('/miniapp')
    def miniapp_route():
        return render_template('miniapp.html')
    
    # Serve static files
    @app.route('/static/<path:filename>')
    def serve_static(filename):
        root_dir = os.path.dirname(os.path.abspath(__file__))
        static_dir = os.path.join(root_dir, '../../../static')
        return send_from_directory(static_dir, filename)
    
    @app.route('/api/game/edge-surf/init', methods=['POST'])
    def init_edge_surf():
        return miniapp.init_edge_surf()
    
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
        if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != Config.TELEGRAM_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        return jsonify(success=True), 200

    # Mini-app API routes
    @app.route('/api/user/data', methods=['GET'])
    def get_user_data_api():
        try:
            init_data = request.headers.get('X-Telegram-InitData') 
            user_id = request.headers.get('X-Telegram-User-ID')
            
            from config import Config
            if not validate_telegram_hash(init_data, Config.TELEGRAM_TOKEN):
                return jsonify({'error': 'Invalid Telegram hash'}), 401

            user_data = get_user_data(int(user_id))
            if not user_data:
                return jsonify({'error': 'User not found'}), 404

            return jsonify({
                'balance': user_data.get('balance', 0),
                'min_withdrawal': Config.MIN_WITHDRAWAL,
                'currency': 'TON'
            })
        except Exception as e:
            logger.error(f"User data error: {str(e)}")
            return jsonify({'error': str(e)}), 500
        
        # Add these to your existing routes.py for game completion handling

    @app.route('/api/game/<game_name>/complete', methods=['POST'])
    def complete_game(game_name):
        """Simple game completion handler"""
        try:
            data = request.get_json()
            user_id = data.get('user_id')
            score = data.get('score', 0)
            
            if not user_id:
                return jsonify({'error': 'User ID required'}), 400
            
            # Simple reward calculation based on game type
            rewards = {
                'clicker': min(score * 0.001, 0.1),      # 0.001 per click, max 0.1 TON
                'spin': min(score * 0.05, 0.15),         # Variable based on spin result  
                'trivia': min(score * 0.002, 0.08),      # 0.002 per correct answer
                'trex': min(score * 0.005, 0.12),        # 0.005 per 100 points
                'edge_surf': min(score * 0.007, 0.1)     # 0.007 per minute played
            }
            
            reward = rewards.get(game_name, 0)
            
            # Update user balance using your existing function
            from src.database.firebase import update_balance
            new_balance = update_balance(int(user_id), reward)
            
            return jsonify({
                'success': True,
                'reward': reward,
                'new_balance': new_balance,
                'message': f'You earned {reward:.6f} TON!'
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/game/<game_name>/init', methods=['POST'])  
    def init_game(game_name):
        """Simple game initialization"""
        try:
            data = request.get_json()
            user_id = data.get('user_id')
            
            if not user_id:
                return jsonify({'error': 'User ID required'}), 400
            
            # Get user balance using your existing function
            from src.database.firebase import get_user_data
            user_data = get_user_data(int(user_id))
            
            return jsonify({
                'success': True,
                'user_balance': user_data.get('balance', 0) if user_data else 0,
                'game_name': game_name
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/ads/reward', methods=['POST'])
    def ad_reward():
        try:
            init_data = request.headers.get('X-Telegram-Hash')
            user_id = request.headers.get('X-Telegram-User-ID')
            
            from config import Config
            if not validate_telegram_hash(init_data, Config.TELEGRAM_TOKEN):
                return jsonify({'error': 'Invalid Telegram hash'}), 401

            now = datetime.datetime.now()
            is_weekend = now.weekday() in [5, 6]
            base_reward = Config.AD_REWARD_AMOUNT
            reward = base_reward * (Config.WEEKEND_BOOST_MULTIPLIER if is_weekend else 1.0)
            
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

    @app.route('/api/withdraw', methods=['POST'])
    def miniapp_withdraw():
        try:
            init_data = request.headers.get('X-Telegram-Hash')
            user_id = request.headers.get('X-Telegram-User-ID')
            
            from config import Config
            if not validate_telegram_hash(init_data, Config.TELEGRAM_TOKEN):
                return jsonify({'error': 'Invalid Telegram hash'}), 401
                
            data = request.get_json()
            method = data['method']
            amount = float(data['amount'])
            address = data['address']  # TON wallet address
            
            # Get balance from user data
            user_data = get_user_data(int(user_id))
            if not user_data:
                return jsonify({
                    'success': False,
                    'error': 'User not found'
                }), 404
                
            balance = user_data.get('balance', 0)
            
            if balance < Config.MIN_WITHDRAWAL:
                return jsonify({
                    'success': False,
                    'error': f'Minimum withdrawal: {Config.MIN_WITHDRAWAL} TON'
                })
                
            if amount > balance:
                return jsonify({
                    'success': False,
                    'error': 'Amount exceeds balance'
                })
            
            # Process TON withdrawal
            result = process_ton_withdrawal(int(user_id), amount, address)
            
            if result and result.get('status') == 'success':
                update_balance(int(user_id), -amount)
                return jsonify({
                    'success': True,
                    'message': f'Withdrawal of {amount:.6f} TON is processing!',
                    'tx_hash': result.get('tx_hash', '')
                })
            else:
                error = result.get('error', 'Withdrawal failed') if result else 'Withdrawal failed'
                return jsonify({
                    'success': False,
                    'error': error
                })
                
        except Exception as e:
            logger.error(f"MiniApp withdrawal error: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # Payment provider webhooks
    @app.route('/paypal/webhook', methods=['POST'])
    def paypal_webhook():
        try:
            event = request.json
            logger.info(f"PayPal webhook received: {event}")
            return jsonify({'status': 'success'}), 200
        except Exception as e:
            logger.error(f"PayPal webhook error: {str(e)}")
            return jsonify({'status': 'error'}), 500
        
    @app.route('/mpesa-callback', methods=['POST'])
    def mpesa_callback():
        try:
            data = request.json
            logger.info(f"M-Pesa callback received: {data}")
            return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"})
        except Exception as e:
            logger.error(f"Error processing M-Pesa callback: {str(e)}")
            return jsonify({"ResultCode": 1, "ResultDesc": "Server error"}), 500
        
        