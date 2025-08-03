from flask import Flask, jsonify, request
from src.database.firebase import (
    get_user_data, 
    update_balance,
    get_active_quests,
    track_ad_impression,
    track_ad_reward
)
from src.utils.security import validate_telegram_hash
from config import Config
import datetime
import logging

def create_app():
    app = Flask(__name__)
    
    @app.route('/miniapp')
    def serve_miniapp():
        """Serve the mini-app HTML"""
        return app.send_static_file('miniapp.html')

    @app.route('/api/user/data', methods=['GET'])
    def get_user_data_api():
        """Get comprehensive user data for mini-app"""
        try:
            # Validate Telegram hash
            init_data = request.headers.get('X-Telegram-Hash')
            user_id = request.headers.get('X-Telegram-User-ID')
            if not validate_telegram_hash(init_data, request.query_string.decode()):
                return jsonify({'error': 'Invalid hash'}), 401

            # Get user data
            user_data = get_user_data(int(user_id))
            if not user_data:
                return jsonify({'error': 'User not found'}), 404

            # Get active quests
            quests = [
                {
                    'id': quest.id,
                    'title': quest.get('title'),
                    'reward': quest.get('reward_xno'),
                    'completed': quest.id in user_data.get('completed_quests', {})
                }
                for quest in get_active_quests()
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
                'quests': quests,
                'ads': ads
            })
        except Exception as e:
            logging.error(f"User data error: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/ads/reward', methods=['POST'])
    def ad_reward():
        """Handle ad rewards"""
        try:
            # Validate Telegram hash
            init_data = request.headers.get('X-Telegram-Hash')
            user_id = request.headers.get('X-Telegram-User-ID')
            if not validate_telegram_hash(init_data, request.get_data(as_text=True)):
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
            logging.error(f"Ad reward error: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/campaign-stats')
    def campaign_stats():
        """Provide campaign statistics for charts"""
        return jsonify({
            "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
            "datasets": [
                {
                    "label": "Impressions",
                    "data": [65, 59, 80, 81, 56, 55],
                    "backgroundColor": "rgba(52, 152, 219, 0.7)"
                },
                {
                    "label": "Conversions",
                    "data": [28, 48, 40, 19, 86, 27],
                    "backgroundColor": "rgba(46, 204, 113, 0.7)"
                }
            ]
        })

    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)