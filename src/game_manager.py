# src/game_manager.py
import logging
import time
import datetime
import hashlib
import uuid
import hmac
from config import config
from src.database.mongo import db, get_user_data, update_game_coins
from src.utils.security import validate_session_token

logger = logging.getLogger(__name__)

# Constants
MAX_RESETS = 3
TON_TO_GC_RATE = 2000  # 2000 Game Coins = 1 TON
MAX_DAILY_GC = 20000  # Maximum game coins per day
DIFFICULTY_LEVELS = {
    'easy': 0.8,
    'medium': 1.0,
    'hard': 1.3
}

class GameManager:
    GAMES = {
        'clicker': {
            'name': 'TON Clicker',
            'icon': 'clicker_icon.png',
            'base_reward': 5,
            'handler': 'handle_clicker_completion',
            'base_difficulty': 'medium',
            'score_multiplier': 0.05  # 0.05 GC per point
        },
        'spin': {
            'name': 'Lucky Spin',
            'icon': 'spin_icon.png',
            'base_reward': 8,
            'handler': 'handle_spin_completion',
            'base_difficulty': 'easy',
            'score_multiplier': 0.1  # 0.1 GC per spin point
        },
        'trex': {
            'name': 'T-Rex Runner',
            'icon': 'trex_icon.png',
            'base_reward': 12,
            'handler': 'handle_trex_completion',
            'base_difficulty': 'hard',
            'score_multiplier': 0.03  # 0.03 GC per point
        },
        'trivia': {
            'name': 'Crypto Trivia',
            'icon': 'trivia_icon.png',
            'base_reward': 10,
            'handler': 'handle_trivia_completion',
            'base_difficulty': 'medium',
            'score_multiplier': 0.15  # 0.15 GC per correct answer
        },
        'edge-surf': {
            'name': 'Edge Surf',
            'icon': 'surf_icon.png',
            'base_reward': 7,
            'handler': 'handle_edge_surf_completion',
            'base_difficulty': 'hard',
            'score_multiplier': 0.04  # 0.04 GC per second
        }
    }

    @classmethod
    def get_games_list(cls):
        return [{
            'id': game_id,
            'name': game_data['name'],
            'icon': game_data['icon'],
            'reward': game_data['base_reward'],
            'difficulty': game_data['base_difficulty']
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
    def handle_clicker_completion(data):
        """Handle clicker game completion"""
        try:
            score = data['score']
            # Calculate reward based on score and multiplier
            reward = score * GameManager.GAMES['clicker']['score_multiplier']
            return {'reward': min(reward, 50)}  # Max 50 GC per game
        except KeyError as e:
            logger.error(f"Missing data in clicker completion: {e}")
            return {'reward': 0}

    @staticmethod
    def handle_spin_completion(data):
        """Handle spin game completion"""
        try:
            spin_result = data['result']
            # Calculate reward based on spin result
            reward = spin_result * GameManager.GAMES['spin']['score_multiplier']
            return {'reward': min(reward, 30)}  # Max 30 GC per spin
        except KeyError as e:
            logger.error(f"Missing data in spin completion: {e}")
            return {'reward': 0}

    @staticmethod
    def handle_trex_completion(data):
        """Handle T-Rex game completion"""
        try:
            score = data['score']
            # Calculate reward based on score and multiplier
            reward = score * GameManager.GAMES['trex']['score_multiplier']
            return {'reward': min(reward, 40)}  # Max 40 GC per game
        except KeyError as e:
            logger.error(f"Missing data in trex completion: {e}")
            return {'reward': 0}

    @staticmethod
    def handle_trivia_completion(data):
        """Handle trivia game completion"""
        try:
            correct_answers = data['correct']
            # Calculate reward based on correct answers
            reward = correct_answers * GameManager.GAMES['trivia']['score_multiplier']
            return {'reward': min(reward, 35)}  # Max 35 GC per game
        except KeyError as e:
            logger.error(f"Missing data in trivia completion: {e}")
            return {'reward': 0}

    @staticmethod
    def handle_edge_surf_completion(data):
        """Handle edge surf game completion"""
        try:
            duration = data['duration']
            # Calculate reward based on duration
            reward = duration * GameManager.GAMES['edge-surf']['score_multiplier']
            return {'reward': min(reward, 25)}  # Max 25 GC per game
        except KeyError as e:
            logger.error(f"Missing data in edge surf completion: {e}")
            return {'reward': 0}


class BaseGame:
    """Base class for all games with common functionality"""
    
    def __init__(self, name: str):
        self.name = name
        self.players = {}
        self.min_reward = 0.001
        self.max_reward = 0.1
        self.max_score_per_second = 50
        self.game_timeout = 300  # 5 minutes
        self.suspicious_activities = {}
        self.max_retry_attempts = 3
        self.retry_delay = 1.5
        self.gc_multiplier = 1.0
        self.active_challenges = {}
        self.difficulty_multiplier = 1.0
        self.anti_cheat_enabled = True
        
        logger.info(f"Initialized {self.name} game")
    
    def get_init_data(self, user_id: str) -> Dict[str, Any]:
        """Get initial game data for a user"""
        try:
            # Load user's best score from database
            high_score = self._get_user_high_score(user_id)
            
            # Apply dynamic difficulty
            self.apply_dynamic_difficulty(user_id)
            
            # Generate anti-cheat challenge
            challenge = self.generate_anti_cheat_challenge()
            
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
                "difficulty": self.difficulty_multiplier,
                "anti_cheat_challenge": challenge
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
                "high_score": self._get_user_high_score(user_id),
                "challenge": self.generate_anti_cheat_challenge()
            }
            
            logger.info(f"Started {self.name} game for user {user_id}")
            return {
                "status": "started",
                "start_time": current_time,
                "session_token": session_token,
                "game_id": f"{self.name}_{user_id}_{int(current_time)}",
                "anti_cheat_challenge": self.players[user_id]["challenge"]
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
    
    def end_game(self, user_id: str, anti_cheat_response: str = None) -> Dict[str, Any]:
        """End game session and calculate rewards"""
        try:
            player = self.players.get(user_id)
            if not player or not player["active"]:
                return {"error": "No active game found"}
            
            # Anti-cheat verification
            if self.anti_cheat_enabled:
                if not self.verify_anti_cheat_response(player["challenge"], anti_cheat_response):
                    self._flag_suspicious_user(user_id, "Anti-cheat challenge failed")
                    return {"error": "Anti-cheat verification failed"}
            
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
            # Convert to game coins with multiplier
            gc_reward = int(reward * TON_TO_GC_RATE * self.gc_multiplier * self.difficulty_multiplier)
            
            # Check if new high score
            is_new_high_score = player["score"] > player.get("high_score", 0)
            if is_new_high_score:
                self._update_high_score(user_id, player["score"])

            # Update user's game coins
            user = get_user_data(user_id)
            if user:
                # Apply daily limit
                available_daily = MAX_DAILY_GC - user.get('daily_gc_earned', 0)
                if gc_reward > available_daily:
                    gc_reward = available_daily
                
                # Update game coins
                success, new_balance = update_game_coins(user_id, gc_reward)
                
                if not success:
                    logger.error(f"Failed to update GC for user {user_id}")
            else:
                logger.error(f"User not found: {user_id}")
            
            # Log game completion
            logger.info(f"Game {self.name} completed by user {user_id}: score={player['score']}, GC reward={gc_reward}")
            
            return {
                "status": "completed",
                "score": player["score"],
                "duration": round(duration, 2),
                "gc_reward": gc_reward,
                "multiplier": self.gc_multiplier,
                "difficulty_multiplier": self.difficulty_multiplier,
                "total_gc": new_balance if success else 0,
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
            "timestamp": datetime.datetime.utcnow(),
            "game": self.name
        })
        
        logger.warning(f"Flagged user {user_id} for suspicious activity: {reason}")
    
    def _get_user_high_score(self, user_id: str) -> int:
        """Get user's high score from database"""
        try:
            # Get user data from Firestore
            user_ref = db.collection('users').document(str(user_id))
            user_data = user_ref.get().to_dict()
            
            if user_data and 'game_stats' in user_data:
                return user_data['game_stats'].get(self.name, {}).get('high_score', 0)
            return 0
        except Exception as e:
            logger.error(f"Error getting high score: {e}")
            return 0
    
    def _get_user_games_count(self, user_id: str) -> int:
        """Get user's total games played"""
        try:
            user_ref = db.collection('users').document(str(user_id))
            user_data = user_ref.get().to_dict()
            
            if user_data and 'game_stats' in user_data:
                return user_data['game_stats'].get(self.name, {}).get('games_played', 0)
            return 0
        except Exception as e:
            logger.error(f"Error getting games count: {e}")
            return 0
    
    def _get_user_total_earned(self, user_id: str) -> float:
        """Get user's total earned from this game"""
        try:
            user_ref = db.collection('users').document(str(user_id))
            user_data = user_ref.get().to_dict()
            
            if user_data and 'game_stats' in user_data:
                return user_data['game_stats'].get(self.name, {}).get('total_earned', 0.0)
            return 0.0
        except Exception as e:
            logger.error(f"Error getting total earned: {e}")
            return 0.0
    
    def _update_high_score(self, user_id: str, score: int) -> None:
        """Update user's high score in database"""
        try:
            user_ref = db.collection('users').document(str(user_id))
            user_ref.update({
                f'game_stats.{self.name}.high_score': score,
                f'game_stats.{self.name}.last_updated': datetime.datetime.utcnow()
            })
            logger.info(f"Updated high score for user {user_id} in {self.name}: {score}")
        except Exception as e:
            logger.error(f"Error updating high score: {e}")
    
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
            
        # Check for active boosters in user's inventory
        if 'inventory' in user:
            for item in user['inventory']:
                if item.get('type') == 'booster' and item.get('active'):
                    # Apply multiplier from booster
                    self.gc_multiplier = max(self.gc_multiplier, item.get('multiplier', 1.0))
    
    def apply_dynamic_difficulty(self, user_id: str):
        """Adjust game difficulty based on user skill"""
        try:
            user_data = get_user_data(user_id)
            if not user_data:
                return
                
            # Calculate win rate (placeholder implementation)
            games_played = self._get_user_games_count(user_id)
            games_won = user_data.get('game_stats', {}).get(self.name, {}).get('games_won', 0)
            win_rate = games_won / games_played if games_played > 0 else 0.5
            
            # Adjust difficulty based on win rate
            if win_rate > 0.7:
                self.difficulty_multiplier = DIFFICULTY_LEVELS['hard']
            elif win_rate < 0.3:
                self.difficulty_multiplier = DIFFICULTY_LEVELS['easy']
            else:
                self.difficulty_multiplier = DIFFICULTY_LEVELS['medium']
                
            logger.info(f"Set difficulty for {user_id} to {self.difficulty_multiplier}x (win rate: {win_rate:.2f})")
        except Exception as e:
            logger.error(f"Error applying dynamic difficulty: {e}")
            self.difficulty_multiplier = DIFFICULTY_LEVELS['medium']
    
    def generate_anti_cheat_challenge(self) -> str:
        """Generate client-side anti-cheat challenge"""
        try:
            challenge = str(uuid.uuid4())
            self.active_challenges[challenge] = datetime.datetime.utcnow()
            return challenge
        except Exception as e:
            logger.error(f"Error generating anti-cheat challenge: {e}")
            return ""
    
    def verify_anti_cheat_response(self, challenge: str, response: str) -> bool:
        """Verify anti-cheat challenge response"""
        try:
            # Validate challenge exists
            if challenge not in self.active_challenges:
                return False
                
            # Validate timestamp (challenge expires after 5 minutes)
            challenge_time = self.active_challenges[challenge]
            if (datetime.datetime.utcnow() - challenge_time).total_seconds() > 300:
                del self.active_challenges[challenge]
                return False
                
            # Simple proof-of-work check
            expected = hashlib.sha256(
                challenge.encode() + config.ANTI_CHEAT_SALT.encode()
            ).hexdigest()
            
            # Clean up challenge
            del self.active_challenges[challenge]
            
            return hmac.compare_digest(response, expected)
        except Exception as e:
            logger.error(f"Anti-cheat verification failed: {e}")
            return False


# Game-specific implementations
class ClickerGame(BaseGame):
    def __init__(self):
        super().__init__("clicker")
        self.max_score_per_second = 20  # Max 20 clicks per second
    
    def _get_instructions(self) -> str:
        return "Click as fast as you can to earn coins! Each click is worth points."
    
    def handle_action(self, user_id: str, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if action == "click":
            player = self.players.get(user_id)
            if not player or not player["active"]:
                return {"error": "No active game"}
            
            # Validate anti-cheat
            if not self.validate_anti_cheat(user_id, player["score"] + 1):
                return {"error": "Suspicious activity detected"}
            
            # Update score
            player["score"] += 1
            player["last_update"] = time.time()
            player["actions_count"] += 1
            
            return {"success": True, "score": player["score"]}
        
        return {"error": "Invalid action"}


class SpinGame(BaseGame):
    def __init__(self):
        super().__init__("spin")
        self.max_score_per_second = 2  # Max 2 spins per second
    
    def _get_instructions(self) -> str:
        return "Spin the wheel and win prizes! Each spin costs 1 coin."
    
    def handle_action(self, user_id: str, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if action == "spin":
            player = self.players.get(user_id)
            if not player or not player["active"]:
                return {"error": "No active game"}
            
            # Deduct spin cost
            if player["score"] < 1:
                return {"error": "Not enough coins"}
                
            player["score"] -= 1
            
            # Generate random result (0-100)
            result = random.randint(0, 100)
            
            # Calculate winnings based on result
            if result > 95:
                winnings = 100  # Jackpot
            elif result > 80:
                winnings = 20
            elif result > 50:
                winnings = 5
            else:
                winnings = 2
                
            player["score"] += winnings
            player["last_update"] = time.time()
            player["actions_count"] += 1
            
            return {"success": True, "result": result, "winnings": winnings, "score": player["score"]}
        
        return {"error": "Invalid action"}


class TRexGame(BaseGame):
    def __init__(self):
        super().__init__("trex")
        self.max_score_per_second = 30  # Max 30 points per second
    
    def _get_instructions(self) -> str:
        return "Jump over cacti and avoid birds! Survive as long as possible."
    
    def handle_action(self, user_id: str, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        player = self.players.get(user_id)
        if not player or not player["active"]:
            return {"error": "No active game"}
        
        if action == "jump":
            # Handle jump action
            pass
        elif action == "duck":
            # Handle duck action
            pass
        elif action == "update_score":
            new_score = data.get("score", 0)
            
            # Validate anti-cheat
            if not self.validate_anti_cheat(user_id, new_score):
                return {"error": "Suspicious activity detected"}
                
            player["score"] = new_score
            player["last_update"] = time.time()
            
        return {"success": True, "score": player["score"]}


class TriviaGame(BaseGame):
    def __init__(self):
        super().__init__("trivia")
        self.max_score_per_second = 3  # Max 3 answers per second
    
    def _get_instructions(self) -> str:
        return "Answer crypto-related questions correctly to earn rewards!"
    
    def handle_action(self, user_id: str, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if action == "answer":
            player = self.players.get(user_id)
            if not player or not player["active"]:
                return {"error": "No active game"}
            
            # Validate anti-cheat
            if not self.validate_anti_cheat(user_id, player["score"] + 1):
                return {"error": "Suspicious activity detected"}
            
            is_correct = data.get("correct", False)
            if is_correct:
                player["score"] += 1
                
            player["last_update"] = time.time()
            player["actions_count"] += 1
            
            return {"success": True, "score": player["score"], "correct": is_correct}
        
        return {"error": "Invalid action"}


class EdgeSurfGame(BaseGame):
    def __init__(self):
        super().__init__("edge-surf")
        self.max_score_per_second = 10  # Max 10 points per second
    
    def _get_instructions(self) -> str:
        return "Surf the edge of the platform and avoid falling! Earn points for distance."
    
    def handle_action(self, user_id: str, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        player = self.players.get(user_id)
        if not player or not player["active"]:
            return {"error": "No active game"}
        
        if action == "update_score":
            new_score = data.get("score", 0)
            
            # Validate anti-cheat
            if not self.validate_anti_cheat(user_id, new_score):
                return {"error": "Suspicious activity detected"}
                
            player["score"] = new_score
            player["last_update"] = time.time()
            
        return {"success": True, "score": player["score"]}


# Game registry
GAME_REGISTRY = {
    "clicker": ClickerGame(),
    "spin": SpinGame(),
    "trex": TRexGame(),
    "trivia": TriviaGame(),
    "edge-surf": EdgeSurfGame()
}


def get_game(game_id: str) -> BaseGame:
    """Get game instance by ID"""
    return GAME_REGISTRY.get(game_id)


def record_game_result(user_id: str, game_id: str, score: int, session_id: str) -> bool:
    """Record game result in database"""
    try:
        game = get_game(game_id)
        if not game:
            logger.error(f"Game not found: {game_id}")
            return False
            
        # Calculate GC reward
        reward_data = GameManager.handle_completion(game_id, {"score": score})
        gc_reward = int(reward_data.get("reward", 0))
        
        # Update user's game coins
        success, new_balance = update_game_coins(user_id, gc_reward)
        
        if success:
            # Update game stats
            user_ref = db.collection('users').document(str(user_id))
            user_ref.update({
                f'game_stats.{game_id}.last_played': datetime.datetime.utcnow(),
                f'game_stats.{game_id}.last_score': score,
                f'game_stats.{game_id}.total_earned': firestore.Increment(gc_reward),
                f'game_stats.{game_id}.games_played': firestore.Increment(1)
            })
            
            # Check for high score
            high_score = game._get_user_high_score(user_id)
            if score > high_score:
                user_ref.update({
                    f'game_stats.{game_id}.high_score': score
                })
            
            logger.info(f"Recorded game result for {user_id}: {game_id} score={score}, GC={gc_reward}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error recording game result: {e}")
        return False