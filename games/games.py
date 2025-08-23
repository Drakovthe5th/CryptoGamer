import os
import time
import hmac
import logging
import backoff
from flask import (
    Blueprint, render_template, send_from_directory, request, 
    jsonify, redirect, url_for
)
from datetime import datetime
from config import config
from src.database.mongo import (
    get_user_data, save_user_data, update_game_coins, 
    save_game_session, record_game_start, MAX_RESETS,
    record_reset, get_game_coins
)
from src.utils.security import get_user_id, validate_telegram_hash
from .clicker_game import ClickerGame
from .spin_game import SpinGame
from .trivia_quiz import TriviaQuiz
from .trex_runner import TRexRunner
from .edge_surf import EdgeSurf
from .sabotage_game import SabotageGame

logger = logging.getLogger(__name__)

# Get base directory for proper path resolution
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Create blueprint with unique name and prefix
games_bp = Blueprint('games', __name__, url_prefix='/games')

# Initialize game instances
GAME_REGISTRY = {
    "clicker": ClickerGame(),
    "spin": SpinGame(),
    "trivia": TriviaQuiz(),
    "trex": TRexRunner(),
    "edge-surf": EdgeSurf(),
    "edge_surf": EdgeSurf(),  # Alias for consistency
    "sabotage": SabotageGame()  # Add sabotage game
}

# Configure retry settings for all games
for game in GAME_REGISTRY.values():
    game.max_retry_attempts = 3
    game.retry_delay = 1.5

# Game directory mapping for consistent naming
GAME_DIR_MAP = {
    'clicker': 'clicker',
    'spin': 'spin', 
    'trivia': 'trivia',
    'trex': 'trex',
    'edge-surf': 'edge-surf',
    'edge_surf': 'edge-surf',
    'sabotage': 'sabotage'  # Add sabotage mapping
}

# Security middleware for game routes
@games_bp.before_request
def check_game_security():
    """Security check for game routes"""
    if request.endpoint and 'api' in request.endpoint:
        # Validate Telegram authentication for API calls
        init_data = request.headers.get('X-Telegram-InitData')
        if not init_data or not validate_telegram_hash(init_data, config.TELEGRAM_TOKEN):
            return jsonify({'error': 'Telegram authentication required'}), 401

# Utility functions
def generate_security_token(user_id):
    """Generate secure session token"""
    timestamp = str(int(time.time()))
    signature = hmac.new(
        config.SECRET_KEY.encode(),
        f"{user_id}{timestamp}".encode(),
        'sha256'
    ).hexdigest()
    return f"{user_id}.{timestamp}.{signature}"

def validate_security_token(user_id, token):
    """Validate security token"""
    try:
        user_id_part, timestamp, signature = token.split('.')
        if user_id_part != str(user_id):
            return False
            
        # Validate timestamp (10 minute window)
        if time.time() - int(timestamp) > 600:
            return False
            
        # Validate signature
        expected = hmac.new(
            config.SECRET_KEY.encode(),
            f"{user_id}{timestamp}".encode(),
            'sha256'
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected)
    except:
        return False

# Game routes
@games_bp.route('/')
def games_index():
    """List all available games"""
    games_list = []
    for game_id, game in GAME_REGISTRY.items():
        games_list.append({
            "id": game_id,
            "name": game.name,
            "description": f"Play {game.name} and earn TON!",
            "min_reward": game.min_reward,
            "max_reward": game.max_reward,
            "url": url_for('games.serve_game_page', game_name=game_id)
        })
    return jsonify({"games": games_list})

@games_bp.route('/<game_name>')
def serve_game_page(game_name):
    """Serve the main game HTML page with token validation"""
    # Map game names to directory names
    actual_dir = GAME_DIR_MAP.get(game_name.lower(), game_name.lower())
    game_path = os.path.join(base_dir, 'games', 'static', actual_dir)
    
    # Validate user token if provided
    user_id = request.args.get('user_id')
    token = request.args.get('token')
    
    if user_id and token:
        if not validate_security_token(user_id, token):
            return jsonify({"error": "Invalid security token"}), 401
        
        # Initialize game session
        game = GAME_REGISTRY.get(game_name.lower())
        if game:
            session_id = record_game_start(user_id, game_name)
            logger.info(f"Game session started: {session_id} for user {user_id}")
    
    @backoff.on_exception(backoff.expo,
                          FileNotFoundError,
                          max_tries=3,
                          jitter=backoff.full_jitter,
                          max_time=10)
    def try_serve():
        return send_from_directory(game_path, 'index.html')
    
    try:
        return try_serve()
    except FileNotFoundError:
        logger.error(f"Game file not found: {game_path}/index.html")
        return jsonify({"error": "Game not found"}), 404

@games_bp.route('/assets/<game_name>/<path:filename>')
def serve_game_assets(game_name, filename):
    """Serve game assets (CSS, JS) from the game directory"""
    actual_dir = GAME_DIR_MAP.get(game_name.lower(), game_name.lower())
    game_assets_path = os.path.join(base_dir, 'games', 'static', actual_dir)
    
    @backoff.on_exception(backoff.expo,
                          FileNotFoundError,
                          max_tries=3,
                          jitter=backoff.full_jitter,
                          max_time=10)
    def try_serve_assets():
        return send_from_directory(game_assets_path, filename)
    
    try:
        return try_serve_assets()
    except FileNotFoundError:
        logger.error(f"Game asset not found: {game_name}/{filename}")
        return jsonify({"error": "Asset not found"}), 404

@games_bp.route('/images/<game_name>/<path:filename>')
def serve_game_images(game_name, filename):
    """Serve game images from the images subdirectory"""
    actual_dir = GAME_DIR_MAP.get(game_name.lower(), game_name.lower())
    images_path = os.path.join(base_dir, 'games', 'static', actual_dir, 'images')
    
    @backoff.on_exception(backoff.expo,
                          FileNotFoundError,
                          max_tries=3,
                          jitter=backoff.full_jitter,
                          max_time=10)
    def try_serve_images():
        return send_from_directory(images_path, filename)
    
    try:
        return try_serve_images()
    except FileNotFoundError:
        logger.error(f"Game image not found: {game_name}/{filename}")
        return jsonify({"error": "Image not found"}), 404

# Game API routes
@games_bp.route('/api/<game_name>/init', methods=['POST'])
def init_game(game_name):
    """Initialize game for a user"""
    game = GAME_REGISTRY.get(game_name.lower())
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    user_id = get_user_id(request)
    if not user_id:
        return jsonify({'error': 'User authentication required'}), 401
    
    @backoff.on_exception(backoff.expo,
                          Exception,
                          max_tries=game.max_retry_attempts,
                          jitter=backoff.full_jitter,
                          max_time=10)
    def try_init():
        return game.get_init_data(user_id)
    
    try:
        init_data = try_init()
        logger.info(f"Game {game_name} initialized for user {user_id}")
        return jsonify({'success': True, 'game_data': init_data})
    except Exception as e:
        logger.error(f"Error initializing game {game_name}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@games_bp.route('/api/<game_name>/action', methods=['POST'])
def game_action(game_name):
    """Handle game actions"""
    game = GAME_REGISTRY.get(game_name.lower())
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    user_id = get_user_id(request)
    if not user_id:
        return jsonify({'error': 'User authentication required'}), 401
    
    @backoff.on_exception(backoff.expo,
                          Exception,
                          max_tries=game.max_retry_attempts,
                          jitter=backoff.full_jitter,
                          max_time=10)
    def try_action():
        data = request.get_json()
        action = data.get('action')
        action_data = data.get('data', {})
        
        if not action:
            raise ValueError('Action required')
        
        return game.handle_action(user_id, action, action_data)
    
    try:
        result = try_action()
        if isinstance(result, dict) and result.get('error'):
            return jsonify(result), 400
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error(f"Error handling action in game {game_name}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@games_bp.route('/api/<game_name>/complete', methods=['POST'])
def complete_game(game_name):
    """Complete game session and award rewards"""
    game = GAME_REGISTRY.get(game_name.lower())
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    user_id = get_user_id(request)
    if not user_id:
        return jsonify({'error': 'User authentication required'}), 401
    
    @backoff.on_exception(backoff.expo,
                          Exception,
                          max_tries=game.max_retry_attempts,
                          jitter=backoff.full_jitter,
                          max_time=10)
    def try_complete():
        data = request.get_json()
        score = data.get('score', 0)
        session_id = data.get('session_id')
        
        # Calculate reward based on game-specific logic
        reward_data = game.calculate_reward(user_id, score)
        gc_reward = reward_data.get('reward', 0)
        
        # Update user's game coins
        success, new_balance = update_game_coins(user_id, gc_reward)
        if not success:
            raise Exception("Failed to update game coins")
        
        # Save game session record
        if session_id:
            save_game_session(user_id, game_name, score, gc_reward, session_id)
        
        return {
            'gc_reward': gc_reward,
            'new_balance': new_balance,
            'score': score
        }
    
    try:
        result = try_complete()
        logger.info(f"Game {game_name} completed by user {user_id}, reward: {result['gc_reward']} GC")
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error(f"Error completing game {game_name}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@games_bp.route('/api/reset', methods=['POST'])
def reset_game():
    """Reset game progress for a user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        game_id = data.get('game_id')
        
        if not user_id or not game_id:
            return jsonify({'error': 'Missing parameters'}), 400
            
        # Get user data
        user_data = get_user_data(user_id)
        if not user_data:
            return jsonify({'error': 'User not found'}), 404
        
        # Check reset count
        reset_count = user_data.get('daily_resets', {}).get(game_id, 0)
        if reset_count >= MAX_RESETS:
            return jsonify({
                'success': False,
                'error': 'Maximum resets reached for today'
            }), 400
        
        # Update reset count
        success = record_reset(user_id, game_id)
        if not success:
            return jsonify({'error': 'Failed to record reset'}), 500
        
        # Get remaining resets
        user_data = get_user_data(user_id)
        new_reset_count = user_data.get('daily_resets', {}).get(game_id, 0)
        resets_left = MAX_RESETS - new_reset_count
        
        return jsonify({
            'success': True, 
            'resets_left': resets_left,
            'message': f'Game reset successful. {resets_left} resets remaining today.'
        })
    except Exception as e:
        logger.error(f"Game reset error: {str(e)}")
        return jsonify({'error': 'Failed to reset game'}), 500

@games_bp.route('/api/token', methods=['GET'])
def get_game_token():
    """Generate secure game token"""
    try:
        game_id = request.args.get('game')
        user_id = get_user_id(request)
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401
        
        token = generate_security_token(user_id)
        return jsonify({'token': token})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@games_bp.route('/api/launch/<game_id>', methods=['GET'])
def launch_game_route(game_id):
    """Generate game launch URL"""
    try:
        user_id = get_user_id(request)
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Generate secure token
        token = generate_security_token(user_id)
        
        # Use the blueprint's URL for the game
        game_url = url_for('games.serve_game_page', game_name=game_id, _external=True)
        game_url += f"?user_id={user_id}&token={token}"
        
        # Record game start
        session_id = record_game_start(user_id, game_id)
        
        return jsonify({
            "success": True,
            "url": game_url,
            "session_id": session_id
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@games_bp.route('/api/complete', methods=['POST'])
def game_completed():
    """Handle game completion with reward calculation"""
    data = request.get_json()
    user_id = data['user_id']
    game_id = data['game_id']
    score = data['score']
    session_id = data['session_id']
    
    # Calculate game coin reward
    base_reward = score * 10  # 10 coins per point
    multiplier = 1.0
    
    # Apply membership multiplier
    user_data = get_user_data(user_id)
    if user_data and user_data.get('membership_tier') == 'PREMIUM':
        multiplier = 1.5
    elif user_data and user_data.get('membership_tier') == 'ULTIMATE':
        multiplier = 2.0
        
    coins = int(base_reward * multiplier)
    
    # Update user balance
    new_balance, actual_coins = update_game_coins(user_id, coins)
    
    # Save game session
    save_game_session(user_id, game_id, score, actual_coins, session_id)
    
    return jsonify({
        'success': True,
        'reward': actual_coins,
        'new_balance': new_balance
    })

@games_bp.route('/health')
def games_health():
    """Health check for games service"""
    try:
        game_status = {}
        for game_id, game in GAME_REGISTRY.items():
            try:
                test_data = game.get_init_data("healthcheck")
                game_status[game_id] = {
                    'name': game.name,
                    'status': 'healthy',
                    'test_data': bool(test_data)
                }
            except Exception as e:
                game_status[game_id] = {
                    'name': game.name,
                    'status': 'unhealthy',
                    'error': str(e)
                }
        
        return jsonify({
            'status': 'healthy' if all(g['status'] == 'healthy' for g in game_status.values()) else 'degraded',
            'games': game_status,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500