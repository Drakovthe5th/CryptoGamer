from flask import request, jsonify, render_template, send_from_directory
from src.database.firebase import (
    get_user_data, update_balance, 
    process_ton_withdrawal, track_ad_reward, SERVER_TIMESTAMP
)
from src.database.firebase import get_games_list, record_game_start
from src.utils.security import validate_telegram_hash
from src.features.monetization.ads import ad_manager
from config import config
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
    

    @app.route('/api/games/list', methods=['GET'])
    def get_games_list():
        """Get list of available games"""
        try:
            games = get_games_list()
            return jsonify([{
                'id': g['id'],
                'name': g['name'],
                'icon': g['icon'],
                'reward': g['reward']
            } for g in games])
        except Exception as e:
            logger.error(f"Games list error: {str(e)}")
            return jsonify({'error': 'Failed to load games'}), 500

    @app.route('/api/game/start', methods=['POST'])
    def start_game_session():
        """Record game start event"""
        try:
            data = request.get_json()
            user_id = data.get('user_id')
            game_id = data.get('game_id')
            
            if not user_id or not game_id:
                return jsonify({'error': 'Missing parameters'}), 400
            
            # Security validation
            init_data = request.headers.get('X-Telegram-InitData')
            if not validate_telegram_hash(init_data, config.TELEGRAM_TOKEN):
                return jsonify({'error': 'Invalid Telegram hash'}), 401
            
            # Record game start
            session_id = record_game_start(user_id, game_id)
            return jsonify({
                'success': True,
                'session_id': session_id
            })
        except Exception as e:
            logger.error(f"Game start error: {str(e)}")
            return jsonify({'error': 'Failed to start game session'}), 500

    @app.route('/games/<game_id>', methods=['GET'])
    def serve_game(game_id):
        """Serve game interface"""
        try:
            # Validate game exists
            games = get_games_list()
            if not any(g['id'] == game_id for g in games):
                return "Game not found", 404
            
            # Serve game HTML
            return send_from_directory(f'games/static/{game_id}', 'index.html')
        except Exception as e:
            logger.error(f"Game serve error: {str(e)}")
            return "Error loading game", 500

    @app.route('/games/<game_id>/static/<path:filename>', methods=['GET'])
    def serve_game_static(game_id, filename):
        """Serve game static assets"""
        return send_from_directory(f'games/static/{game_id}/static', filename)
    
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
        if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != config.TELEGRAM_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        return jsonify(success=True), 200

    # Mini-app API routes
    @app.route('/api/user/data', methods=['GET'])
    def get_user_data_api():
        try:
            init_data = request.headers.get('X-Telegram-InitData') 
            user_id = request.headers.get('X-Telegram-User-ID')
            
            from config import config
            if not validate_telegram_hash(init_data, config.TELEGRAM_TOKEN):
                return jsonify({'error': 'Invalid Telegram hash'}), 401

            user_data = get_user_data(int(user_id))
            if not user_data:
                return jsonify({'error': 'User not found'}), 404

            return jsonify({
                'balance': user_data.get('balance', 0),
                'min_withdrawal': config.MIN_WITHDRAWAL,
                'currency': 'TON'
            })
        except Exception as e:
            logger.error(f"User data error: {str(e)}")
            return jsonify({'error': str(e)}), 500
        
    @app.route('/api/ads/slot/<slot_id>')
    def get_ad_slot(slot_id):
        ad = ad_manager.get_available_ad(slot_id)
        return jsonify(ad) if ad else ('', 404)

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
            
            from config import config
            if not validate_telegram_hash(init_data, config.TELEGRAM_TOKEN):
                return jsonify({'error': 'Invalid Telegram hash'}), 401

            now = datetime.datetime.now()
            is_weekend = now.weekday() in [5, 6]
            base_reward = config.AD_REWARD_AMOUNT
            reward = base_reward * (config.WEEKEND_BOOST_MULTIPLIER if is_weekend else 1.0)
            
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
        
    @app.route('/api/quests/claim_bonus', methods=['POST'])
    def claim_daily_bonus():
        try:
            data = request.get_json()
            user_id = int(data['user_id'])
            user_data = get_user_data(user_id)
            
            # Check if bonus already claimed today
            last_claimed = user_data.get('last_bonus_claimed')
            today = datetime.utcnow().date()
            
            if last_claimed and last_claimed.date() == today:
                return jsonify({
                    'success': False,
                    'error': 'Bonus already claimed today'
                }), 400
            
            # Award bonus
            bonus_amount = 0.05
            new_balance = update_balance(user_id, bonus_amount)
            
            # Update last claimed time
            users_ref.document(str(user_id)).update({
                'last_bonus_claimed': datetime.utcnow(),
                'balance': new_balance
            })
            
            return jsonify({
                'success': True,
                'new_balance': new_balance
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
    @app.route('/api/quests/record_click', methods=['POST'])
    def record_click():
        try:
            data = request.get_json()
            user_id = int(data['user_id'])
            user_data = get_user_data(user_id)
            
            # Reset clicks if new day
            today = datetime.utcnow().date()
            last_click_date = user_data.get('last_click_date')
            clicks_today = user_data.get('clicks_today', 0)
            
            if not last_click_date or last_click_date.date() != today:
                clicks_today = 0
            
            # Check daily limit
            if clicks_today >= 100:
                return jsonify({
                    'success': False,
                    'error': 'Daily click limit reached'
                }), 400
            
            # Award click
            click_reward = 0.0001
            new_balance = update_balance(user_id, click_reward)
            clicks_today += 1
            
            # Update user data
            users_ref.document(str(user_id)).update({
                'clicks_today': clicks_today,
                'last_click_date': datetime.utcnow(),
                'balance': new_balance
            })
            
            return jsonify({
                'clicks': clicks_today,
                'balance': new_balance
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
    @app.route('/api/ads/slot/<slot_id>', methods=['GET'])
    def serve_ad(slot_id):
        try:
            # Get ad from ad manager
            ad = ad_manager.get_available_ad(slot_id)
            
            if not ad:
                return jsonify({
                    'html': f'''
                        <div style="width:100%;height:100%;background:#333;border-radius:8px;
                                    display:flex;align-items:center;justify-content:center;">
                            <div style="text-align:center;color:#666;">
                                <div style="font-size:2rem;margin-bottom:8px;">📺</div>
                                <div>No ad available</div>
                            </div>
                        </div>
                    ''',
                    'type': 'html'
                })
            
            return jsonify(ad)
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
    @app.route('/api/ads/view/<slot_id>', methods=['POST'])
    def track_ad_view(slot_id):
        """Track an ad view for a specific slot and reward the user"""
        try:
            # Get user ID from request
            user_id = request.headers.get('X-Telegram-User-ID')
            if not user_id:
                return jsonify({'error': 'User ID required'}), 400
            
            # Get ad slot info
            slot_info = ad_manager.ad_slots.get(slot_id)
            if not slot_info:
                return jsonify({'error': 'Invalid ad slot'}), 400

            # Get user IP and user agent for reward calculation
            user_ip = request.remote_addr
            user_agent = request.headers.get('User-Agent')
            
            # Create AdMonetization instance
            ad_monetization = AdMonetization()
            
            # Record the ad view and award reward
            reward, new_balance = ad_monetization.record_ad_view(
                int(user_id),
                slot_info['network'],
                user_agent,
                user_ip
            )
            
            # Update slot usage
            ad_manager.record_ad_view(slot_id)
            
            # Record in database
            record_ad_engagement(
                user_id=int(user_id),
                ad_network=slot_info['network'],
                reward=reward,
                user_agent=user_agent,
                ip_address=user_ip
            )
            
            return jsonify({
                'status': 'success',
                'reward': reward,
                'new_balance': new_balance,
                'slot': slot_id,
                'network': slot_info['network']
            })
            
        except PermissionError as e:
            return jsonify({'error': str(e)}), 429  # Too Many Requests
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Ad tracking error: {str(e)}")
            return jsonify({'error': 'Internal server error'}), 500

    @app.route('/api/withdraw', methods=['POST'])
    def miniapp_withdraw():
        try:
            init_data = request.headers.get('X-Telegram-Hash')
            user_id = request.headers.get('X-Telegram-User-ID')
            
            from config import config
            if not validate_telegram_hash(init_data, config.TELEGRAM_TOKEN):
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
            
            if balance < config.MIN_WITHDRAWAL:
                return jsonify({
                    'success': False,
                    'error': f'Minimum withdrawal: {config.MIN_WITHDRAWAL} TON'
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
        
    @app.route('/api/ads/slot/<slot_id>', methods=['GET'])
    def get_ad_slot(slot_id):
        try:
            ad = ad_manager.get_available_ad(slot_id)
            if ad:
                return jsonify(ad)
            
            # Fallback if no ad available
            return jsonify({
                'html': f"""
                <div style="width:100%;height:100%;background:#333;border-radius:8px;
                            display:flex;align-items:center;justify-content:center;">
                    <div style="text-align:center;color:#666;">
                        <div style="font-size:2rem;margin-bottom:8px;">📺</div>
                        <div>Ad Loading...</div>
                    </div>
                </div>
                """,
                'type': 'html'
            })
            
        except Exception as e:
            logger.error(f"Ad slot error: {str(e)}")
            return jsonify({
                'html': """
                <div style="width:100%;height:100%;background:#333;border-radius:8px;
                            display:flex;align-items:center;justify-content:center;">
                    <div style="text-align:center;color:#666;">
                        <div style="font-size:2rem;margin-bottom:8px;">❌</div>
                        <div>Ad Failed to Load</div>
                    </div>
                </div>
                """,
                'type': 'html'
            })
        
    @app.route('/api/ads/show/<slot_name>')
    def show_rewarded_ad(slot_name):
        ad = ad_manager.get_available_ad(slot_name)
        if ad and 'rewarded' in slot_name:
            return jsonify(ad)
        return jsonify({'error': 'No rewarded ad available'}), 404

    @app.route('/api/ads/view/<slot_name>')
    def track_ad_view(slot_name):
        ad_manager.record_ad_view(slot_name)
        return jsonify({'status': 'recorded'})

    @app.route('/api/ads/reward')
    def reward_ad_view():
        slot_name = request.args.get('slot')
        ad_type = request.args.get('type')
        # Add reward logic here
        return jsonify({'status': 'rewarded'})