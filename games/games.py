import os
from flask import Blueprint, render_template, send_from_directory, request, jsonify
from .clicker_game import ClickerGame
from .spin_game import SpinGame
from .trivia_quiz import TriviaQuiz
from .trex_runner import TRexRunner
from .edge_surf import EdgeSurf
from datetime import datetime
import time
import logging
import backoff  # For exponential backoff

logger = logging.getLogger(__name__)

# Create blueprint with unique name and prefix
games_bp = Blueprint('games', __name__, url_prefix='/games')

# Initialize game instances with retry configuration
GAME_REGISTRY = {
    "clicker": ClickerGame(),
    "spin": SpinGame(),
    "trivia": TriviaQuiz(),
    "trex": TRexRunner(),
    "edge_surf": EdgeSurf()
}

# Configure retry settings for all games
for game in GAME_REGISTRY.values():
    game.max_retry_attempts = 3
    game.retry_delay = 1.5

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
            "max_reward": game.max_reward
        })
    return jsonify({"games": games_list})

# Use unique endpoint name to avoid conflicts
@games_bp.route('/<game_name>', endpoint='game_serve')
def serve_game(game_name):
    """Serve game HTML file with exponential backoff retries"""
    game = GAME_REGISTRY.get(game_name.lower())
    if not game:
        logger.error(f"Game not found: {game_name}")
        return jsonify({"error": "Game not found"}), 404
    
    @backoff.on_exception(backoff.expo,
                          FileNotFoundError,
                          max_tries=game.max_retry_attempts,
                          jitter=backoff.full_jitter,
                          max_time=10)
    def try_serve():
        return send_from_directory('static', f'{game_name}/index.html')
    
    try:
        return try_serve()
    except FileNotFoundError:
        logger.error(f"Game file not found: static/{game_name}/index.html")
        return jsonify({"error": "Game file not found"}), 404

# Unique endpoint name for static files
@games_bp.route('/<game_name>/static/<path:filename>', endpoint='game_static_files')
def game_static(game_name, filename):
    """Serve static files for games with retries"""
    game = GAME_REGISTRY.get(game_name.lower())
    if not game:
        return jsonify({"error": "Game not found"}), 404
    
    @backoff.on_exception(backoff.expo,
                          FileNotFoundError,
                          max_tries=game.max_retry_attempts,
                          jitter=backoff.full_jitter,
                          max_time=10)
    def try_serve_static():
        return send_from_directory(f"static/{game_name}", filename)
    
    try:
        return try_serve_static()
    except FileNotFoundError:
        logger.error(f"Static file not found: static/{game_name}/{filename}")
        return jsonify({"error": "File not found"}), 404

@games_bp.route('/<game_name>/api/init', methods=['POST'])
def init_game(game_name):
    """Initialize game for a user with retry logic"""
    game = GAME_REGISTRY.get(game_name.lower())
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    @backoff.on_exception(backoff.expo,
                          Exception,
                          max_tries=game.max_retry_attempts,
                          jitter=backoff.full_jitter,
                          max_time=10)
    def try_init():
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            raise ValueError('User ID required')
        
        return game.get_init_data(user_id)
    
    try:
        init_data = try_init()
        logger.info(f"Game {game_name} initialized for user")
        return jsonify({'success': True, 'game_data': init_data})
    except Exception as e:
        logger.error(f"Error initializing game {game_name}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@games_bp.route('/<game_name>/api/start', methods=['POST'])
def start_game(game_name):
    """Start a game session with retry logic"""
    game = GAME_REGISTRY.get(game_name.lower())
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    @backoff.on_exception(backoff.expo,
                          Exception,
                          max_tries=game.max_retry_attempts,
                          jitter=backoff.full_jitter,
                          max_time=10)
    def try_start():
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            raise ValueError('User ID required')
        
        return game.start_game(user_id)
    
    try:
        result = try_start()
        logger.info(f"Game {game_name} started")
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error(f"Error starting game {game_name}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@games_bp.route('/<game_name>/api/action', methods=['POST'])
def game_action(game_name):
    """Handle game actions with retry logic"""
    game = GAME_REGISTRY.get(game_name.lower())
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    @backoff.on_exception(backoff.expo,
                          Exception,
                          max_tries=game.max_retry_attempts,
                          jitter=backoff.full_jitter,
                          max_time=10)
    def try_action():
        data = request.get_json()
        user_id = data.get('user_id')
        action = data.get('action')
        action_data = data.get('data', {})
        
        if not user_id or not action:
            raise ValueError('User ID and action required')
        
        return game.handle_action(user_id, action, action_data)
    
    try:
        result = try_action()
        if isinstance(result, dict) and result.get('error'):
            logger.warning(f"Game action error: {result['error']}")
            return jsonify(result), 400
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error(f"Error handling action in game {game_name}: {str(e)}")
        return jsonify({'error': str(e)}), 500


@games_bp.route('/<game_name>/api/end', methods=['POST'])
def end_game(game_name):
    """End game session with retry logic"""
    game = GAME_REGISTRY.get(game_name.lower())
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    @backoff.on_exception(backoff.expo,
                          Exception,
                          max_tries=game.max_retry_attempts,
                          jitter=backoff.full_jitter,
                          max_time=10)
    def try_end():
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            raise ValueError('User ID required')
        
        return game.end_game(user_id)
    
    try:
        result = try_end()
        if isinstance(result, dict) and result.get('error'):
            logger.warning(f"Game end error: {result['error']}")
            return jsonify(result), 400

        # Update user's game coins
        gc_reward = result.get('gc_reward', 0)
        from src.database.mongo import update_game_coins
        success, new_balance = update_game_coins(user_id, gc_reward)
        if success:
            result['total_gc'] = new_balance
        else:
            logger.error(f"Failed to update game coins for user {user_id}")

        logger.info(f"Game ended, GC reward: {gc_reward}")
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error(f"Error ending game {game_name}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@games_bp.route('/<game_name>/api/leaderboard', methods=['GET'])
def game_leaderboard(game_name):
    """Get game leaderboard with retry logic"""
    game = GAME_REGISTRY.get(game_name.lower())
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    @backoff.on_exception(backoff.expo,
                          Exception,
                          max_tries=game.max_retry_attempts,
                          jitter=backoff.full_jitter,
                          max_time=10)
    def try_leaderboard():
        # This would need to be implemented in each game class
        return game.get_leaderboard()
    
    try:
        leaderboard = try_leaderboard()
        return jsonify({'success': True, 'leaderboard': leaderboard})
    except Exception as e:
        logger.error(f"Error getting leaderboard: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Health check with enhanced diagnostics
@games_bp.route('/health')
def games_health():
    """Comprehensive health check for games service"""
    try:
        game_status = {}
        for game_id, game in GAME_REGISTRY.items():
            try:
                # Test game functionality
                test_data = game.get_init_data("healthcheck")
                game_status[game_id] = {
                    'name': game.name,
                    'active_players': len(game.players),
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
            'status': 'healthy' if all(
                g['status'] == 'healthy' for g in game_status.values()
            ) else 'degraded',
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