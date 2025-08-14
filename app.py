from flask import Flask, jsonify, request, send_from_directory, render_template
from src.database.firebase import initialize_firebase
from src.features import quests, ads
from src.utils import security, validation
from games.games import games_bp
from config import config
import os
import json
import base64
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    """Application factory pattern"""
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='static')
    
    app.secret_key = config.SECRET_KEY
    
    # Initialize Firebase
    try:
        firebase_creds = config.FIREBASE_CREDS
        if firebase_creds:
            initialize_firebase(firebase_creds)
            logger.info("Firebase initialized successfully")
        else:
            logger.warning("Firebase credentials not found")
    except Exception as e:
        logger.error(f"Firebase initialization failed: {e}")
    
    # Register blueprints
    app.register_blueprint(games_bp)
    
    # Security middleware
    @app.before_request
    def check_security():
        """Enhanced security middleware with proper error handling"""
        # Skip security checks for static files and health endpoints
        if (request.path.startswith('/static') or 
            request.path.startswith('/health') or
            request.path == '/'):
            return
        
        # Only check security for API endpoints
        if request.path.startswith('/api'):
            try:
                # Telegram authentication
                init_data = request.headers.get('X-Telegram-InitData')
                if not init_data:
                    return jsonify({'error': 'Telegram authentication required'}), 401
                
                if not security.validate_telegram_hash(init_data, config.TELEGRAM_BOT_TOKEN):
                    return jsonify({'error': 'Invalid Telegram authentication'}), 401
                    
                # Security token validation
                security_token = request.headers.get('X-Security-Token')
                if not security_token:
                    return jsonify({'error': 'Security token missing'}), 401
                    
                try:
                    # Use base64.b64decode instead of atob (which is JavaScript)
                    security_token = security_token.replace('-', '+').replace('_', '/')
                    padding = len(security_token) % 4
                    if padding > 0:
                        security_token += '=' * (4 - padding)
                        
                    token_data = base64.b64decode(security_token).decode('utf-8').split(':')
                    
                    if len(token_data) != 2:
                        return jsonify({'error': 'Invalid security token format'}), 401
                        
                    token_time = int(token_data[1])
                    current_time = int(datetime.utcnow().timestamp())
                    
                    # 5 minutes expiry
                    if abs(current_time - token_time) > 300:
                        return jsonify({'error': 'Security token expired'}), 401
                        
                except (ValueError, TypeError, base64.binascii.Error) as e:
                    logger.warning(f"Invalid security token: {e}")
                    return jsonify({'error': 'Invalid security token'}), 401
                    
            except Exception as e:
                logger.error(f"Security check failed: {e}")
                return jsonify({'error': 'Security check failed'}), 500
    
    # Main routes
    @app.route('/')
    def serve_miniapp():
        """Serve the main miniapp"""
        return render_template('miniapp.html')
    
    @app.route('/health')
    def health_check():
        """Health check endpoint"""
        try:
            return jsonify({
                'status': 'healthy',
                'service': 'CryptoGameMiner',
                'version': '1.0.0',
                'timestamp': datetime.utcnow().isoformat(),
                'features': {
                    'games': config.FEATURE_GAMES,
                    'ads': config.FEATURE_ADS,
                    'otc': config.FEATURE_OTC
                }
            }), 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }), 500
    
    # API Endpoints
    @app.route('/api/user/data', methods=['GET'])
    def get_user_data():
        """Get user data with enhanced error handling"""
        try:
            user_id = security.get_user_id(request)
            if not user_id:
                return jsonify({'error': 'User ID missing'}), 400

            from src.database.firebase import get_user_data
            user_data = get_user_data(int(user_id))
            
            if not user_data:
                # Create new user if doesn't exist
                user_data = {
                    'balance': 0,
                    'clicks_today': 0,
                    'bonus_claimed': False,
                    'username': f'Player{user_id}'
                }
                # Save new user data
                from src.database.firebase import save_user_data
                save_user_data(int(user_id), user_data)
                logger.info(f"Created new user: {user_id}")

            return jsonify({
                'success': True,
                'balance': user_data.get('balance', 0),
                'clicks_today': user_data.get('clicks_today', 0),
                'bonus_claimed': user_data.get('bonus_claimed', False),
                'username': user_data.get('username', f'Player{user_id}')
            })
            
        except Exception as e:
            logger.error(f"Get user data error: {str(e)}")
            return jsonify({'error': 'Failed to fetch user data'}), 500

    @app.route('/api/quests/claim_bonus', methods=['POST'])
    def claim_daily_bonus():
        """Claim daily bonus with security checks"""
        try:
            user_id = security.get_user_id(request)
            if not user_id:
                return jsonify({'error': 'User ID missing'}), 400
            
            # Check for suspicious activity
            if security.is_abnormal_activity(user_id):
                return jsonify({
                    'success': False,
                    'error': 'Account restricted due to suspicious activity'
                }), 403
            
            success, new_balance = quests.claim_daily_bonus(user_id)
            
            return jsonify({
                'success': success,
                'new_balance': new_balance,
                'message': 'Daily bonus claimed successfully!' if success else 'Bonus already claimed today'
            })
            
        except Exception as e:
            logger.error(f"Claim bonus error: {str(e)}")
            return jsonify({
                'success': False, 
                'error': 'Failed to claim bonus'
            }), 500

    @app.route('/api/quests/record_click', methods=['POST'])
    def record_click():
        """Record user click with anti-cheat measures"""
        try:
            user_id = security.get_user_id(request)
            if not user_id:
                return jsonify({'error': 'User ID missing'}), 400
            
            # Check for suspicious activity
            if security.is_abnormal_activity(user_id):
                return jsonify({
                    'success': False,
                    'error': 'Account restricted due to suspicious activity'
                }), 403
            
            clicks, balance = quests.record_click(user_id)
            
            return jsonify({
                'success': True,
                'clicks': clicks,
                'balance': balance
            })
            
        except Exception as e:
            logger.error(f"Record click error: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Failed to record click'
            }), 500

    @app.route('/api/ads/reward', methods=['POST'])
    def ad_reward():
        """Process ad reward with validation"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Invalid request data'}), 400
                
            user_id = data.get('user_id')
            ad_id = data.get('ad_id')
            
            if not user_id or not ad_id:
                return jsonify({'error': 'User ID and Ad ID required'}), 400
            
            # Security check
            if security.is_abnormal_activity(user_id):
                return jsonify({
                    'success': False,
                    'error': 'Account restricted due to suspicious activity'
                }), 403
            
            # Calculate reward with bonuses
            now = datetime.now()
            is_weekend = now.weekday() in [5, 6]  # Saturday, Sunday
            base_reward = config.REWARDS['ad_view']
            
            if is_weekend:
                base_reward *= config.WEEKEND_BOOST_MULTIPLIER
            
            # Update balance and track reward
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
            logger.error(f"Ad reward error: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Failed to process ad reward'
            }), 500
    
    @app.route('/api/security/check', methods=['GET'])
    def security_check():
        """Check user security status"""
        try:
            user_id = security.get_user_id(request)
            if not user_id:
                return jsonify({'error': 'User ID missing'}), 400
                
            restricted = security.is_abnormal_activity(user_id)
            
            return jsonify({
                'success': True,
                'restricted': restricted,
                'message': 'Security check completed',
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Security check error: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Security check failed'
            }), 500

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Endpoint not found',
            'message': 'The requested resource was not found'
        }), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred'
        }), 500

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            'error': 'Access forbidden',
            'message': 'You do not have permission to access this resource'
        }), 403

    return app

# Create the app instance
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = config.ENV != 'production'
    
    logger.info(f"Starting CryptoGameMiner on port {port}, debug={debug_mode}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)