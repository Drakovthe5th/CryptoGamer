# src/database/game_db.py
from google.cloud import firestore
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
db = firestore.Client()

def record_game_start(user_id: int, game_id: str) -> str:
    """Record game start and return session ID"""
    session_ref = db.collection('game_sessions').document()
    session_ref.set({
        'user_id': user_id,
        'game_id': game_id,
        'start_time': datetime.now(),
        'status': 'active'
    })
    return session_ref.id

def save_game_session(user_id: int, game_id: str, score: int, 
                     reward: float, session_id: str):
    """Save completed game session"""
    session_ref = db.collection('game_sessions').document(session_id)
    session_ref.update({
        'end_time': datetime.now(),
        'score': score,
        'reward': reward,
        'status': 'completed'
    })
    
    # Update user stats
    user_ref = db.collection('users').document(str(user_id))
    user_ref.update({
        'total_games': firestore.Increment(1),
        'total_rewards': firestore.Increment(reward),
        'last_played': datetime.now()
    })

def get_games_list():
    """Get list of available games from Firestore"""
    games_ref = db.collection('games').where('enabled', '==', True)
    return [doc.to_dict() for doc in games_ref.stream()]