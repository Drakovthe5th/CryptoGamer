# src/database/game_db.py
from .mongo import db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def record_game_start(user_id: int, game_id: str) -> str:
    session_data = {
        "user_id": user_id,
        "game_id": game_id,
        "start_time": datetime.utcnow(),
        "status": "active"
    }
    result = db.game_sessions.insert_one(session_data)
    return str(result.inserted_id)

def save_game_session(user_id: int, game_id: str, score: int, 
                     reward: float, session_id: str):
    # Update session
    db.game_sessions.update_one(
        {"_id": session_id},
        {
            "$set": {
                "end_time": datetime.utcnow(),
                "score": score,
                "reward": reward,
                "status": "completed"
            }
        }
    )
    
    # Update user
    db.users.update_one(
        {"user_id": user_id},
        {
            "$inc": {
                "total_games": 1,
                "total_rewards": reward
            },
            "$set": {"last_played": datetime.utcnow()}
        }
    )

def save_pool_game_result(game_data):
    """Save pool game result to database"""
    try:
        # Direct database implementation instead of importing from pool_game
        pool_game_result = {
            'game_id': game_data['game_id'],
            'players': game_data['players'],
            'bets': game_data.get('bets', {}),
            'pot': game_data['pot'],
            'winner': game_data['winner'],
            'start_time': game_data['start_time'],
            'end_time': game_data['end_time'],
            'shots_taken': game_data.get('shots_taken', 0),
            'balls_potted': game_data.get('balls_potted', 0),
            'created_at': datetime.utcnow()
        }
        
        result = db.pool_game_results.insert_one(pool_game_result)
        logger.info(f"Pool game result saved: {result.inserted_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving pool game result: {e}")
        return False

def get_games_list():
    return list(db.games.find({"enabled": True}))