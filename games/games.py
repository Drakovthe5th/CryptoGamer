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

logger = logging.getLogger(__name__)

games_bp = Blueprint('games', __name__, url_prefix='/games')

# Initialize game instances
GAME_REGISTRY = {
    "clicker": ClickerGame(),
    "spin": SpinGame(),
    "trivia": TriviaQuiz(),
    "trex": TRexRunner(),
    "edge_surf": EdgeSurf()
}

@games_bp.route('/')
def games_index():
    """List all available games"""
    games_list = []
    for game_id, game in GAME_REGISTRY.items():
        games_list.append({
            "id": game_id,
            "name": game.name,
            "description": f"Play {game.name} and earn TON!"
        })
    return jsonify({"games": games_list})

@games_bp.route('/<game_name>')
def serve_game(game_name):
    """Serve game HTML file"""
    game = GAME_REGISTRY.get(game_name.lower())
    if not game:
        logger.error(f"Game not found: {game_name}")
        return jsonify({"error": "Game not found"}), 404
    
    try:
        # Serve game HTML from static folder
        return send_from_directory('static', f'{game_name}/index.html')
    except FileNotFoundError:
        logger.error(f"Game file not found: static/{game_name}/index.html")
        return jsonify({"error": "Game file not found"}), 404

@games_bp.route('/<game_name>/static/<path:filename>')
def game_static(game_name, filename):
    """Serve static files for games"""
    try:
        return send_from_directory(f"static/{game_name}", filename)
    except FileNotFoundError:
        logger.error(f"Static file not found: static/{game_name}/{filename}")
        return jsonify({"error": "File not found"}), 404

@games_bp.route('/<game_name>/api/init', methods=['POST'])
def init_game(game_name):
    """Initialize game for a user"""
    game = GAME_REGISTRY.get(game_name.lower())
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400
        
        init_data = game.get_init_data(user_id)
        logger.info(f"Game {game_name} initialized for user {user_id}")
        
        return jsonify({
            'success': True,
            'game_data': init_data
        })
        
    except Exception as e:
        logger.error(f"Error initializing game {game_name}: {str(e)}")
        return jsonify({'error': 'Failed to initialize game'}), 500

@games_bp.route('/<game_name>/api/start', methods=['POST'])
def start_game(game_name):
    """Start a game session"""
    game = GAME_REGISTRY.get(game_name.lower())
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400
        
        result = game.start_game(user_id)
        logger.info(f"Game {game_name} started for user {user_id}")
        
        return jsonify({
            'success': True,
            **result
        })
        
    except Exception as e:
        logger.error(f"Error starting game {game_name}: {str(e)}")
        return jsonify({'error': 'Failed to start game'}), 500

@games_bp.route('/<game_name>/api/action', methods=['POST'])
def game_action(game_name):
    """Handle game actions"""
    game = GAME_REGISTRY.get(game_name.lower())
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        action = data.get('action')
        action_data = data.get('data', {})
        
        if not user_id or not action:
            return jsonify({'error': 'User ID and action required'}), 400
        
        result = game.handle_action(user_id, action, action_data)
        
        if isinstance(result, dict) and result.get('error'):
            logger.warning(f"Game action error in {game_name}: {result['error']}")
            return jsonify(result), 400
        
        return jsonify({
            'success': True,
            **result
        })
        
    except Exception as e:
        logger.error(f"Error handling action in game {game_name}: {str(e)}")
        return jsonify({'error': 'Failed to process action'}), 500

@games_bp.route('/<game_name>/api/end', methods=['POST'])
def end_game(game_name):
    """End a game session and calculate rewards"""
    game = GAME_REGISTRY.get(game_name.lower())
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400
        
        result = game.end_game(user_id)
        logger.info(f"Game {game_name} ended for user {user_id}, reward: {result.get('reward', 0)}")
        
        return jsonify({
            'success': True,
            **result
        })
        
    except Exception as e:
        logger.error(f"Error ending game {game_name}: {str(e)}")
        return jsonify({'error': 'Failed to end game'}), 500

@games_bp.route('/<game_name>/api/leaderboard', methods=['GET'])
def game_leaderboard(game_name):
    """Get game leaderboard"""
    game = GAME_REGISTRY.get(game_name.lower())
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    try:
        # This would need to be implemented in each game class
        # For now, return empty leaderboard
        return jsonify({
            'success': True,
            'leaderboard': []
        })
        
    except Exception as e:
        logger.error(f"Error getting leaderboard for {game_name}: {str(e)}")
        return jsonify({'error': 'Failed to get leaderboard'}), 500

# Health check endpoint for games
@games_bp.route('/health')
def games_health():
    """Health check for games service"""
    try:
        # Check if all games are properly initialized
        game_status = {}
        for game_id, game in GAME_REGISTRY.items():
            game_status[game_id] = {
                'name': game.name,
                'active_players': len(game.players),
                'status': 'healthy'
            }
        
        return jsonify({
            'status': 'healthy',
            'games': game_status,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Games health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500