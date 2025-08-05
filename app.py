from flask import Flask, jsonify, request, send_from_directory
from src.database.firebase import (
    initialize_firebase, get_user_data, 
    update_balance, get_active_quests,
    track_ad_impression, track_ad_reward
)
from src.utils.security import validate_telegram_hash
from config import Config
import os
import json
import datetime
import logging

def create_app():
    app = Flask(__name__)
    
    # Initialize Firebase
    firebase_creds = json.loads(os.environ.get('FIREBASE_CREDS', '{}'))
    initialize_firebase(firebase_creds)
    
    @app.route('/miniapp')
    def serve_miniapp():
        return send_from_directory('static', 'miniapp.html')

    @app.route('/api/user/data', methods=['GET'])
    def get_user_data_api():
        try:
            init_data = request.headers.get('X-Telegram-InitData')
            if not validate_telegram_hash(init_data, Config.TELEGRAM_BOT_TOKEN):
                return jsonify({'error': 'Invalid hash'}), 401

            user_id = request.args.get('user_id')
            if not user_id:
                return jsonify({'error': 'User ID required'}), 400

            user_data = get_user_data(int(user_id))
            if not user_data:
                return jsonify({'error': 'User not found'}), 404

            quests = [
                {
                    'id': quest.id,
                    'title': quest.get('title'),
                    'reward': quest.get('reward_ton'),
                    'completed': quest.id in user_data.get('completed_quests', {})
                }
                for quest in get_active_quests()
            ]

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
        try:
            init_data = request.headers.get('X-Telegram-InitData')
            if not validate_telegram_hash(init_data, Config.TELEGRAM_BOT_TOKEN):
                return jsonify({'error': 'Invalid hash'}), 401

            user_id = request.json.get('user_id')
            ad_id = request.json.get('ad_id')
            if not user_id or not ad_id:
                return jsonify({'error': 'Missing parameters'}), 400

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
            logging.error(f"Ad reward error: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/campaign-stats')
    def campaign_stats():
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