import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class BaseGame:
    """Base class for all games with common functionality"""
    
    def __init__(self, name: str):
        self.name = name
        self.players = {}  # Store active game sessions
        self.min_reward = 0.001  # Minimum TON reward
        self.max_reward = 0.1    # Maximum TON reward
        self.max_score_per_second = 50  # Anti-cheat threshold
        self.game_timeout = 300  # 5 minutes max game session
        self.suspicious_activities = {}  # Track suspicious behavior
        
        logger.info(f"Initialized {self.name} game")
    
    def get_init_data(self, user_id: str) -> Dict[str, Any]:
        """Get initial game data for a user"""
        try:
            # Load user's best score from database (placeholder)
            high_score = self._get_user_high_score(user_id)
            
            return {
                "name": self.name,
                "instructions": self._get_instructions(),
                "high_score": high_score,
                "min_reward": self.min_reward,
                "max_reward": self.max_reward,
                "user_data": {
                    "user_id": user_id,
                    "games_played": self._get_user_games_count(user_id),
                    "total_earned": self._get_user_total_earned(user_id)
                }
            }
        except Exception as e:
            logger.error(f"Error getting init data for {self.name}: {e}")
            return {
                "name": self.name,
                "instructions": "Game instructions not available",
                "high_score": 0,
                "user_data": {}
            }
    
    def start_game(self, user_id: str) -> Dict[str, Any]:
        """Start a new game session for a user"""
        try:
            current_time = time.time()
            
            # Check if user already has an active game
            if user_id in self.players and self.players[user_id].get("active"):
                logger.warning(f"User {user_id} already has active game in {self.name}")
                return {"error": "Game already active"}
            
            # Check for rate limiting (prevent spam)
            if self._is_rate_limited(user_id):
                return {"error": "Please wait before starting another game"}
            
            # Initialize player session
            self.players[user_id] = {
                "score": 0,
                "start_time": current_time,
                "last_update": current_time,
                "active": True,
                "actions_count": 0,
                "suspicious_flags": 0,
                "high_score": self._get_user_high_score(user_id)
            }
            
            logger.info(f"Started {self.name} game for user {user_id}")
            return {
                "status": "started",
                "start_time": current_time,
                "game_id": f"{self.name}_{user_id}_{int(current_time)}"
            }
            
        except Exception as e:
            logger.error(f"Error starting game {self.name} for user {user_id}: {e}")
            return {"error": "Failed to start game"}
    
    def handle_action(self, user_id: str, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle game actions - to be overridden by specific games"""
        raise NotImplementedError("Subclasses must implement handle_action method")
    
    def end_game(self, user_id: str) -> Dict[str, Any]:
        """End game session and calculate rewards"""
        try:
            player = self.players.get(user_id)
            if not player or not player["active"]:
                return {"error": "No active game found"}
            
            # Mark game as inactive
            player["active"] = False
            end_time = time.time()
            duration = end_time - player["start_time"]
            
            # Validate game session
            if not self._validate_game_session(user_id, duration):
                logger.warning(f"Invalid game session for user {user_id} in {self.name}")
                return {"error": "Invalid game session"}
            
            # Calculate reward
            reward = self._calculate_reward(player["score"], duration)
            
            # Check if new high score
            is_new_high_score = player["score"] > player.get("high_score", 0)
            if is_new_high_score:
                self._update_high_score(user_id, player["score"])
            
            # Log game completion
            logger.info(f"Game {self.name} completed by user {user_id}: score={player['score']}, reward={reward}, duration={duration:.2f}s")
            
            return {
                "status": "completed",
                "score": player["score"],
                "duration": round(duration, 2),
                "reward": reward,
                "new_high_score": is_new_high_score,
                "game_stats": {
                    "actions_performed": player["actions_count"],
                    "average_score_per_second": round(player["score"] / max(duration, 1), 2)
                }
            }
            
        except Exception as e:
            logger.error(f"Error ending game {self.name} for user {user_id}: {e}")
            return {"error": "Failed to end game"}
    
    def validate_anti_cheat(self, user_id: str, current_score: int) -> bool:
        """Validate score updates for anti-cheat"""
        try:
            player = self.players.get(user_id)
            if not player:
                return False
            
            current_time = time.time()
            time_elapsed = current_time - player["last_update"]
            score_increase = current_score - player["score"]
            
            # Check for impossible score increases
            max_possible_increase = self.max_score_per_second * time_elapsed * 1.2  # 20% tolerance
            
            if score_increase > max_possible_increase and time_elapsed > 0:
                logger.warning(f"Suspicious score increase for user {user_id} in {self.name}: +{score_increase} in {time_elapsed:.2f}s")
                player["suspicious_flags"] += 1
                
                # Flag user if too many suspicious activities
                if player["suspicious_flags"] > 3:
                    self._flag_suspicious_user(user_id, "Multiple suspicious score increases")
                    return False
                
                return False
            
            # Update player data
            player["score"] = current_score
            player["last_update"] = current_time
            player["actions_count"] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Anti-cheat validation error for {self.name}: {e}")
            return False
    
    def cleanup_inactive_sessions(self) -> None:
        """Clean up inactive or expired game sessions"""
        try:
            current_time = time.time()
            expired_users = []
            
            for user_id, player in self.players.items():
                # Check if session has expired
                if current_time - player["start_time"] > self.game_timeout:
                    expired_users.append(user_id)
                    logger.info(f"Cleaning up expired game session for user {user_id} in {self.name}")
            
            # Remove expired sessions
            for user_id in expired_users:
                del self.players[user_id]
                
        except Exception as e:
            logger.error(f"Error during cleanup for {self.name}: {e}")
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get game leaderboard - placeholder for implementation"""
        # This would typically fetch from database
        return []
    
    def _get_instructions(self) -> str:
        """Get game instructions - to be overridden by specific games"""
        return f"Play {self.name} and earn TON rewards!"
    
    def _calculate_reward(self, score: int, duration: float) -> float:
        """Calculate reward based on score and duration"""
        try:
            # Base reward calculation
            base_reward = min(
                self.min_reward + (score * 0.00001),  # Small reward per point
                self.max_reward
            )
            
            # Duration bonus (encourage longer play but cap it)
            duration_bonus = min(duration * 0.0001, 0.01)
            
            # Total reward
            total_reward = base_reward + duration_bonus
            
            return round(min(total_reward, self.max_reward), 6)
            
        except Exception as e:
            logger.error(f"Error calculating reward: {e}")
            return self.min_reward
    
    def _validate_game_session(self, user_id: str, duration: float) -> bool:
        """Validate if game session is legitimate"""
        try:
            player = self.players.get(user_id)
            if not player:
                return False
            
            # Check minimum game duration (prevent instant completions)
            if duration < 1.0:
                logger.warning(f"Game too short for user {user_id}: {duration}s")
                return False
            
            # Check maximum game duration
            if duration > self.game_timeout:
                logger.warning(f"Game too long for user {user_id}: {duration}s")
                return False
            
            # Check if user has too many suspicious flags
            if player.get("suspicious_flags", 0) > 5:
                logger.warning(f"User {user_id} has too many suspicious flags")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Session validation error: {e}")
            return False
    
    def _is_rate_limited(self, user_id: str) -> bool:
        """Check if user is rate limited"""
        # Simple rate limiting - allow one game every 30 seconds
        if not hasattr(self, '_last_game_time'):
            self._last_game_time = {}
        
        current_time = time.time()
        last_game = self._last_game_time.get(user_id, 0)
        
        if current_time - last_game < 30:  # 30 second cooldown
            return True
        
        self._last_game_time[user_id] = current_time
        return False
    
    def _flag_suspicious_user(self, user_id: str, reason: str) -> None:
        """Flag user for suspicious activity"""
        if user_id not in self.suspicious_activities:
            self.suspicious_activities[user_id] = []
        
        self.suspicious_activities[user_id].append({
            "reason": reason,
            "timestamp": datetime.utcnow(),
            "game": self.name
        })
        
        logger.warning(f"Flagged user {user_id} for suspicious activity: {reason}")
    
    def _get_user_high_score(self, user_id: str) -> int:
        """Get user's high score - placeholder for database integration"""
        # This would typically fetch from database
        return 0
    
    def _get_user_games_count(self, user_id: str) -> int:
        """Get user's total games played - placeholder"""
        return 0
    
    def _get_user_total_earned(self, user_id: str) -> float:
        """Get user's total earned from this game - placeholder"""
        return 0.0
    
    def _update_high_score(self, user_id: str, score: int) -> None:
        """Update user's high score - placeholder"""
        # This would typically update database
        logger.info(f"New high score for user {user_id} in {self.name}: {score}")
    
    def get_game_stats(self) -> Dict[str, Any]:
        """Get general game statistics"""
        return {
            "name": self.name,
            "active_players": len([p for p in self.players.values() if p.get("active")]),
            "total_sessions": len(self.players),
            "suspicious_users": len(self.suspicious_activities)
        }