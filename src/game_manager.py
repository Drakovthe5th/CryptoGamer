# src/game_manager.py
import logging
from config import config
from src.database.firebase import db

logger = logging.getLogger(__name__)

class GameManager:
    GAMES = {
        'clicker': {
            'name': 'TON Clicker',
            'icon': 'icon.png',
            'reward': 5,
            'handler': 'handle_clicker_completion'
        },
        'spin': {
            'name': 'Lucky Spin',
            'icon': 'wheel_icon.png',
            'reward': 8,
            'handler': 'handle_spin_completion'
        },
        'trex': {
            'name': 'T-Rex Runner',
            'icon': 'dino_icon.png',
            'reward': 12,
            'handler': 'handle_trex_completion'
        },
        'trivia': {
            'name': 'Crypto Trivia',
            'icon': 'quiz_icon.png',
            'reward': 10,
            'handler': 'handle_trivia_completion'
        },
        'edge-surf': {
            'name': 'Edge Surf',
            'icon': 'surf_icon.png',
            'reward': 7,
            'handler': 'handle_edge_surf_completion'
        }
    }

    @classmethod
    def get_games_list(cls):
        return [{
            'id': game_id,
            'name': game_data['name'],
            'icon': game_data['icon'],
            'reward': game_data['reward']
        } for game_id, game_data in cls.GAMES.items()]

    @classmethod
    def handle_completion(cls, game_id, data):
        if game_id not in cls.GAMES:
            raise ValueError(f"Unknown game: {game_id}")
        
        handler_name = cls.GAMES[game_id]['handler']
        handler = getattr(cls, handler_name, cls.default_handler)
        return handler(data)

    @staticmethod
    def default_handler(data):
        """Default game completion handler"""
        return {
            'success': True,
            'reward': 0.01
        }

    @staticmethod
    def handle_edge_surf_completion(data):
        # Edge Surf specific logic
        score = data['score']
        reward = min(score * 0.007, 0.1)  # 0.007 TON per second, max 0.1 TON
        return {'reward': reward}

    @staticmethod
    def handle_trex_completion(data):
        # T-Rex specific logic
        score = data['score']
        reward = min(score * 0.005, 0.12)  # 0.005 TON per 100 points, max 0.12 TON
        return {'reward': reward}
    
    # Add handlers for other games...