import time
import hmac
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from config import config
from config import REWARD_RATES, MAX_GAME_REWARD, MAX_DAILY_GAME_COINS
from src.database.mongo import get_user_data, get_game_session, update_user_data
from src.utils.security import get_user_id

logger = logging.getLogger(__name__)
TON_TO_GC_RATE = 2000  # 2000 Game Coins = 1 TON
MAX_DAILY_GC = 20000  # Maximum game coins per day

class BaseGame:
    """Base class for all games with common functionality"""
    
    def __init__(self, name: str):
        self.name = name
        self.players = {}
        self.min_reward = 0.001
        self.max_reward = 0.1
        self.max_score_per_second = 50
        self.game_timeout = 300
        self.suspicious_activities = {}
        self.max_retry_attempts = 3
        self.retry_delay = 1.5
        self.gc_multiplier = 1.0  # ADDED: Default multiplier
        
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
        
    def get_game_url(self, user_id, token):
        return f"/games/{self.name}?user_id={user_id}&token={token}"

    def get_asset_url(self, asset_path):
        return f"/game-assets/{self.name}/{asset_path}"
    
    def start_game(self, user_id: str) -> Dict[str, Any]:
        """Start a new game session for a user"""
        try:
            current_time = time.time()

            # Generate secure session token
            session_token = self._generate_session_token(user_id)
            
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
        
    def _generate_session_token(self, user_id: str) -> str:
        timestamp = str(int(time.time()))
        signature = hmac.new(
            config.SECRET_KEY.encode(),
            f"{user_id}{timestamp}".encode(),
            'sha256'
        ).hexdigest()
        return f"{user_id}.{timestamp}.{signature}"

    def validate_session(self, user_id: str, token: str) -> bool:
        try:
            user_id_part, timestamp, signature = token.split('.')
            if user_id_part != user_id:
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
            
            # Calculate reward in game coins
            reward = self._calculate_reward(player["score"], duration)
            gc_reward = int(reward * TON_TO_GC_RATE * self.gc_multiplier)
            
            # Check if new high score
            is_new_high_score = player["score"] > player.get("high_score", 0)
            if is_new_high_score:
                self._update_high_score(user_id, player["score"])

            # Log game completion
            logger.info(f"Game {self.name} completed by user {user_id}: score={player['score']}, GC reward={gc_reward}")
            
            return {
                "status": "completed",
                "score": player["score"],
                "duration": round(duration, 2),
                "gc_reward": gc_reward,
                "multiplier": self.gc_multiplier,
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
        """Calculate reward based on score and duration using config rates"""
        try:
            game_rates = REWARD_RATES.get(self.name, {})
            
            # Calculate base reward
            base_reward = game_rates.get('base', 0)
            
            # Add score-based reward if defined
            if 'per_1000_points' in game_rates:
                base_reward += (score / 1000) * game_rates['per_1000_points']
            
            # Add duration-based reward if defined
            if 'per_minute' in game_rates:
                base_reward += (duration / 60) * game_rates['per_minute']
            
            # Add distance-based reward for trex runner
            if self.name == 'trex' and 'per_100_meters' in game_rates:
                base_reward += (score / 100) * game_rates['per_100_meters']  # score is distance in meters
            
            # Cap at maximum reward for this game
            max_reward_gc = MAX_GAME_REWARD.get(self.name, 100)
            base_reward = min(base_reward, max_reward_gc)
            
            # Convert to TON
            reward_ton = base_reward / TON_TO_GC_RATE
            
            # Check daily limit
            daily_earnings = self._get_daily_earnings(user_id)
            if daily_earnings >= MAX_DAILY_GAME_COINS:
                logger.info(f"User {user_id} reached daily GC limit")
                return {
                    "status": "daily_limit_reached",
                    "score": player["score"],
                    "daily_earnings": daily_earnings,
                    "max_daily": MAX_DAILY_GAME_COINS
                }
            
            # Then calculate reward as before
            reward = self._calculate_reward(player["score"], duration)
            gc_reward = int(reward * TON_TO_GC_RATE * self.gc_multiplier)

            # Update daily earnings
            self._update_daily_earnings(user_id, gc_reward)
            return round(reward_ton, 6)
            
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
        
    def validate_session_token(user_id, token):
        return hmac.compare_digest(
            generate_session_token(user_id),
            token
    )
    
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
    
    def apply_boosters(self, user_id):
        """Apply active boosters to current session"""
        user = get_user_data(user_id)
        if not user:
            return
            
        for item in user.inventory:
            if 'multiplier' in item.get('effect', {}):
                self.gc_multiplier = max(self.gc_multiplier, item['effect']['multiplier'])

    # Add these methods to your BaseGame class in base_game.py
    def _get_daily_earnings(self, user_id: str) -> int:
        """Get user's daily earnings from database"""
        try:
            user_data = get_user_data(user_id)
            if user_data:
                # Get today's date as string for key
                today = datetime.utcnow().strftime("%Y-%m-%d")
                return user_data.get('daily_earnings', {}).get(today, 0)
            return 0
        except Exception as e:
            logger.error(f"Error getting daily earnings: {e}")
            return 0

    def _update_daily_earnings(self, user_id: str, amount: int) -> None:
        """Update user's daily earnings in database"""
        try:
            user_data = get_user_data(user_id)
            if user_data:
                today = datetime.utcnow().strftime("%Y-%m-%d")
                daily_earnings = user_data.get('daily_earnings', {})
                current = daily_earnings.get(today, 0)
                daily_earnings[today] = current + amount
                
                # Update user data
                update_user_data(user_id, {'daily_earnings': daily_earnings})
        except Exception as e:
            logger.error(f"Error updating daily earnings: {e}")