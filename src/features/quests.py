import os
import time
import threading
import logging
from datetime import datetime
from firebase_admin import firestore
from src.database.firebase import quests_ref, users_ref, update_balance, update_leaderboard_points

logger = logging.getLogger(__name__)

def get_active_quests():
    """Get all active quests"""
    try:
        return quests_ref.where('active', '==', True).stream()
    except Exception as e:
        logger.error(f"Failed to get active quests: {e}")
        return []

def complete_quest(user_id: int, quest_id: str) -> bool:
    """Mark a quest as completed for a user"""
    try:
        quest_doc = quests_ref.document(quest_id).get()
        if not quest_doc.exists:
            return False
            
        quest_data = quest_doc.to_dict()
        user_ref = users_ref.document(str(user_id))
        
        # Check if already completed
        user_data = user_ref.get().to_dict()
        if quest_id in user_data.get('completed_quests', {}):
            return False
            
        # Update quest completions
        quests_ref.document(quest_id).update({
            'completions': firestore.Increment(1)
        })
        
        # Update user data
        user_ref.update({
            f'completed_quests.{quest_id}': datetime.now(),
            'balance': firestore.Increment(quest_data['reward_ton']),
            'points': firestore.Increment(quest_data['reward_points'])
        })
        
        return True
    except Exception as e:
        logger.error(f"Failed to complete quest: {e}")
        return False

def refresh_quests():
    """Refresh quests based on schedule"""
    try:
        # In production, this would rotate quests based on schedule
        logger.info("Quests refreshed successfully")
    except Exception as e:
        logger.error(f"Failed to refresh quests: {e}")

def start_quest_scheduler():
    """Start quest scheduler"""
    while True:
        refresh_quests()
        time.sleep(3600)  # Refresh hourly