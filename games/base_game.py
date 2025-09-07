# /games/base_game.py - COMPLETE REWRITE
import time
import hmac
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
from config import config
from src.database.mongo import get_user_data, update_user_data
from src.utils.security import get_user_id, generate_session_token

logger = logging.getLogger(__name__)

# Constants used by multiple games
TON_TO_GC_RATE = 2000  # 2000 Game Coins = 1 TON
MAX_DAILY_GC = 20000   # Maximum game coins per day

# Add these constants that are referenced in games
REWARD_RATES = {
    'trivia': {'base': 100, 'per_correct_answer': 50},
    'clicker': {'base': 50, 'per_1000_points': 10},
    'spin': {'base': 20},
    'trex': {'base': 30, 'per_100_meters': 15},
    'edge_surf': {'base': 40, 'per_minute': 25}
}

MAX_GAME_REWARD = {
    'trivia': 500,
    'clicker': 1000,
    'spin': 300,
    'trex': 800,
    'edge_surf': 600
}

class GameType(Enum):
    SINGLEPLAYER = "singleplayer"
    MULTIPLAYER = "multiplayer"
    TOURNAMENT = "tournament"

class BettingType(Enum):
    NONE = "none"
    TELEGRAM_STARS = "telegram_stars"
    GAME_COINS = "game_coins"

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
        self.gc_multiplier = 1.0
        self.game_type = GameType.SINGLEPLAYER
        self.betting_type = BettingType.NONE
        self.max_players = 1
        self.min_players = 1
        self.supported_bet_amounts = []
        self.house_fee_percent = 5
        
        # Additional attributes used by various games
        self.active_games = {}  # For multiplayer games
        self.tables = {}  # For poker-like games
        self.pending_challenges = {}  # For challenge-based games
        self.last_game_time = {}  # Rate limiting
        
        logger.info(f"Initialized {self.name} game with type: {self.game_type.value}")
    
    def get_init_data(self, user_id: str) -> Dict[str, Any]:
        """Get initial game data for a user"""
        try:
            # Load user's best score from database
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
                },
                "game_config": self.get_game_config()
            }
        except Exception as e:
            logger.error(f"Error getting init data for {self.name}: {e}")
            return {
                "name": self.name,
                "instructions": "Game instructions not available",
                "high_score": 0,
                "user_data": {}
            }
    
    def get_game_config(self) -> Dict[str, Any]:
        """Get game configuration including betting options"""
        return {
            "name": self.name,
            "type": self.game_type.value,
            "betting_type": self.betting_type.value,
            "max_players": self.max_players,
            "min_players": self.min_players,
            "supported_bet_amounts": self.supported_bet_amounts,
            "house_fee_percent": self.house_fee_percent,
            "can_bet": self.betting_type != BettingType.NONE
        }
    
    def validate_bet(self, user_id: str, amount: int) -> bool:
        """Validate if a bet amount is acceptable"""
        if self.betting_type == BettingType.NONE:
            return False
            
        if not self.supported_bet_amounts:
            return amount > 0
            
        return amount in self.supported_bet_amounts
    
    def process_bet_payout(self, winner_id: str, total_pot: int) -> Dict[str, Any]:
        """Process betting payout"""
        house_fee = total_pot * self.house_fee_percent // 100
        winnings = total_pot - house_fee
        
        return {
            "winner": winner_id,
            "total_pot": total_pot,
            "house_fee": house_fee,
            "winnings": winnings
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
            
            # Check for rate limiting
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
        """Handle game actions - must be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement handle_action method")
    
    def end_game(self, user_id: str) -> Dict[str, Any]:
        """End game session and calculate rewards - must be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement end_game method")
    
    def _get_instructions(self) -> str:
        """Get game instructions - must be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement _get_instructions method")
    
    def _generate_session_token(self, user_id: str) -> str:
        timestamp = str(int(time.time()))
        signature = hmac.new(
            config.SECRET_KEY.encode(),
            f"{user_id}{timestamp}".encode(),
            'sha256'
        ).hexdigest()
        return f"{user_id}.{timestamp}.{signature}"
    
    def validate_session_token(self, user_id: str, token: str) -> bool:
        """Validate session token"""
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
            max_possible_increase = self.max_score_per_second * time_elapsed * 1.2
            
            if score_increase > max_possible_increase and time_elapsed > 0:
                logger.warning(f"Suspicious score increase for user {user_id} in {self.name}: +{score_increase} in {time_elapsed:.2f}s")
                player["suspicious_flags"] += 1
                
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
    
    def _calculate_reward(self, score: int, duration: float) -> float:
        """Calculate reward based on game type and performance"""
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
                base_reward += (score / 100) * game_rates['per_100_meters']
            
            # Cap at maximum reward for this game
            max_reward_gc = MAX_GAME_REWARD.get(self.name, 100)
            base_reward = min(base_reward, max_reward_gc)
            
            # Convert to TON
            reward_ton = base_reward / TON_TO_GC_RATE
            
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
            
            # Check minimum game duration
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
        current_time = time.time()
        last_game = self.last_game_time.get(user_id, 0)
        
        if current_time - last_game < 30:  # 30 second cooldown
            return True
        
        self.last_game_time[user_id] = current_time
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
        """Get user's high score from database"""
        try:
            user_data = get_user_data(user_id)
            if user_data:
                return user_data.get('game_stats', {}).get(self.name, {}).get('high_score', 0)
            return 0
        except Exception as e:
            logger.error(f"Error getting high score for user {user_id}: {e}")
            return 0
    
    def _get_user_games_count(self, user_id: str) -> int:
        """Get user's total games played"""
        try:
            user_data = get_user_data(user_id)
            if user_data:
                return user_data.get('game_stats', {}).get(self.name, {}).get('games_played', 0)
            return 0
        except Exception as e:
            logger.error(f"Error getting games count for user {user_id}: {e}")
            return 0
    
    def _get_user_total_earned(self, user_id: str) -> float:
        """Get user's total earned from this game"""
        try:
            user_data = get_user_data(user_id)
            if user_data:
                return user_data.get('game_stats', {}).get(self.name, {}).get('total_earned', 0.0)
            return 0.0
        except Exception as e:
            logger.error(f"Error getting total earned for user {user_id}: {e}")
            return 0.0
    
    def _update_high_score(self, user_id: str, score: int) -> None:
        """Update user's high score in database"""
        try:
            user_data = get_user_data(user_id)
            if user_data:
                game_stats = user_data.get('game_stats', {})
                game_stats.setdefault(self.name, {})
                game_stats[self.name]['high_score'] = score
                
                # Update user data
                update_user_data(user_id, {'game_stats': game_stats})
                logger.info(f"Updated high score for user {user_id} in {self.name}: {score}")
        except Exception as e:
            logger.error(f"Error updating high score for user {user_id}: {e}")
    
    def _get_daily_earnings(self, user_id: str) -> int:
        """Get user's daily earnings from database"""
        try:
            user_data = get_user_data(user_id)
            if user_data:
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
                
                update_user_data(user_id, {'daily_earnings': daily_earnings})
        except Exception as e:
            logger.error(f"Error updating daily earnings: {e}")
    
    def apply_boosters(self, user_id):
        """Apply active boosters to current session"""
        user = get_user_data(user_id)
        if not user:
            return
            
        for item in user.get('inventory', []):
            if 'multiplier' in item.get('effect', {}):
                self.gc_multiplier = max(self.gc_multiplier, item['effect']['multiplier'])
    
    def cleanup_inactive_sessions(self) -> None:
        """Clean up inactive or expired game sessions"""
        try:
            current_time = time.time()
            expired_users = []
            
            for user_id, player in self.players.items():
                if current_time - player["start_time"] > self.game_timeout:
                    expired_users.append(user_id)
                    logger.info(f"Cleaning up expired game session for user {user_id} in {self.name}")
            
            for user_id in expired_users:
                del self.players[user_id]
                
        except Exception as e:
            logger.error(f"Error during cleanup for {self.name}: {e}")
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get game leaderboard"""
        # This would typically fetch from database
        return []
    
    def get_game_stats(self) -> Dict[str, Any]:
        """Get general game statistics"""
        return {
            "name": self.name,
            "active_players": len([p for p in self.players.values() if p.get("active")]),
            "total_sessions": len(self.players),
            "suspicious_users": len(self.suspicious_activities)
        }
    
    def get_available_tables(self) -> List[Dict]:
        """Get available tables for table-based games"""
        tables = []
        for table_id, table in getattr(self, 'tables', {}).items():
            tables.append({
                "id": table_id,
                "players": len(getattr(table, 'players', [])),
                "max_players": getattr(self, 'max_players_per_table', 6),
                "blinds": {
                    "small": getattr(table, 'small_blind', 10),
                    "big": getattr(table, 'big_blind', 20)
                }
            })
        return tables

# Add utility function that was missing
def validate_session_token(user_id, token):
    """Standalone session token validation"""
    try:
        user_id_part, timestamp, signature = token.split('.')
        if user_id_part != str(user_id):
            return False
            
        if time.time() - int(timestamp) > 600:
            return False
            
        expected = hmac.new(
            config.SECRET_KEY.encode(),
            f"{user_id}{timestamp}".encode(),
            'sha256'
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected)
    except:
        return False