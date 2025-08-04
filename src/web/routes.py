from flask import request, jsonify, render_template, send_from_directory
from src.database.firebase import (
    get_user_balance, get_user_data, update_balance, 
    process_withdrawal, update_leaderboard_points, 
    track_ad_reward, SERVER_TIMESTAMP
)
from src.utils.security import validate_telegram_hash
from src.utils.conversions import to_xno
from config import Config
import logging
import datetime
import os

logger = logging.getLogger(__name__)

def configure_routes(app):
    @app.route('/')
    def index():
        return "CryptoGameBot is running!"
    
    @app.route('/miniapp')
    def miniapp_route():
        return render_template('miniapp.html')
    
    # Serve static files directly from the static folder
    @app.route('/static/<path:filename>')
    def serve_static(filename):
        root_dir = os.path.dirname(os.path.abspath(__file__))
        static_dir = os.path.join(root_dir, '../../../static')
        return send_from_directory(static_dir, filename)
    
    # Simple error handlers without templates
    @app.errorhandler(404)
    def page_not_found(e):
        return "Page not found", 404
    
    @app.errorhandler(500)
    def internal_error(e):
        return "Internal server error", 500
    
    # Telegram webhook endpoint
    @app.route('/webhook', methods=['POST'])
    def telegram_webhook():
        # Verify secret token
        if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != Config.TELEGRAM_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
            
        # Process Telegram updates (would normally go here)
        return jsonify(success=True), 200

    # =====================
    # MINI-APP API ROUTES
    # =====================
    
    @app.route('/api/user/data', methods=['GET'])
    def get_user_data_api():
        """Get comprehensive user data for mini-app"""
        try:
            # Validate Telegram hash
            init_data = request.headers.get('X-Telegram-Hash')
            user_id = request.headers.get('X-Telegram-User-ID')
            
            # Use raw query string for validation
            query_string = request.query_string.decode('utf-8')
            if not validate_telegram_hash(init_data, query_string):
                return jsonify({'error': 'Invalid hash'}), 401

            # Get user data
            user_data = get_user_data(int(user_id))
            if not user_data:
                return jsonify({'error': 'User not found'}), 404

            # Get active quests
            quests = [
                {
                    'id': "quest1",
                    'title': "Daily Login",
                    'reward': 0.01,
                    'completed': False
                },
                {
                    'id': "quest2",
                    'title': "Play 3 Games",
                    'reward': 0.03,
                    'completed': True
                }
            ]

            # Get available ads
            ads = [{
                'id': 'ad1',
                'title': 'Special Offer',
                'image_url': '/static/img/ads/ad1.jpg',
                'reward': Config.AD_REWARD_AMOUNT
            }]

            return jsonify({
                'balance': user_data.get('balance', 0),
                'min_withdrawal': Config.MIN_WITHDRAWAL,
                'quests': quests,
                'ads': ads
            })
        except Exception as e:
            logger.error(f"User data error: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/ads/reward', methods=['POST'])
    def ad_reward():
        """Handle ad rewards"""
        try:
            # Validate Telegram hash
            init_data = request.headers.get('X-Telegram-Hash')
            user_id = request.headers.get('X-Telegram-User-ID')
            raw_data = request.get_data(as_text=True)
            
            if not validate_telegram_hash(init_data, raw_data):
                return jsonify({'error': 'Invalid hash'}), 401

            # Calculate reward with weekend boost
            now = datetime.datetime.now()
            is_weekend = now.weekday() in [5, 6]  # Saturday/Sunday
            base_reward = Config.AD_REWARD_AMOUNT
            reward = base_reward * (Config.WEEKEND_BOOST_MULTIPLIER if is_weekend else 1.0)
            
            # Update balance
            new_balance = update_balance(int(user_id), reward)
            
            # Track reward
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
        """Handle withdrawal requests from mini-app"""
        try:
            # Validate Telegram hash
            init_data = request.headers.get('X-Telegram-Hash')
            user_id = request.headers.get('X-Telegram-User-ID')
            raw_data = request.get_data(as_text=True)
            
            if not validate_telegram_hash(init_data, raw_data):
                return jsonify({'error': 'Invalid hash'}), 401
                
            data = request.get_json()
            method = data['method']
            amount = float(data['amount'])
            details = data['details']
            
            # Get user balance
            balance = get_user_balance(int(user_id))
            
            if balance < Config.MIN_WITHDRAWAL:
                return jsonify({
                    'success': False,
                    'error': f'Minimum withdrawal: {Config.MIN_WITHDRAWAL} XNO'
                })
                
            if amount > balance:
                return jsonify({
                    'success': False,
                    'error': 'Amount exceeds balance'
                })
            
            # Process withdrawal
            result = process_withdrawal(int(user_id), method, amount, details)
            
            if result and result.get('status') == 'success':
                update_balance(int(user_id), -amount)
                return jsonify({
                    'success': True,
                    'message': f'Withdrawal of {amount:.6f} XNO is processing!',
                    'tx_id': result.get('tx_id', '')
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
    
    # =====================
    # AD PERFORMANCE TRACKING
    # =====================
    
    @app.route('/ad-impression', methods=['POST'])
    def track_ad_impression():
        """Track ad impressions"""
        try:
            data = request.json
            # In a real implementation, you would save this to your database
            logger.info(f"Ad impression: {data}")
            return jsonify(success=True)
        except Exception as e:
            logger.error(f"Ad impression tracking error: {str(e)}")
            return jsonify(success=False), 500
    
    # =====================
    # PAYMENT PROVIDER WEBHOOKS
    # =====================
    
    @app.route('/paypal/webhook', methods=['POST'])
    def paypal_webhook():
        """Handle PayPal payment notifications"""
        try:
            # Verify webhook signature would go here
            event = request.json
            logger.info(f"PayPal webhook received: {event}")
            return jsonify({'status': 'success'}), 200
        except Exception as e:
            logger.error(f"PayPal webhook error: {str(e)}")
            return jsonify({'status': 'error'}), 500
        
    @app.route('/mpesa-callback', methods=['POST'])
    def mpesa_callback():
        """Handle M-Pesa payment notifications"""
        try:
            data = request.json
            logger.info(f"M-Pesa callback received: {data}")
            return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"})
        except Exception as e:
            logger.error(f"Error processing M-Pesa callback: {str(e)}")
            return jsonify({"ResultCode": 1, "ResultDesc": "Server error"}), 500