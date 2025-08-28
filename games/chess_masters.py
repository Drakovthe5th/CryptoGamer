# /games/chess_masters.py
import games.chess_masters as chess_masters
import uuid
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from .base_game import BaseGame
from config import config
from src.database.mongo import get_user_data, update_user_data
from src.utils.security import get_user_id

logger = logging.getLogger(__name__)

class ChessMasters(BaseGame):
    """Chess game with staking and betting functionality"""
    
    def __init__(self):
        super().__init__("chess_masters")
        self.min_stake = 10  # Minimum stake in Stars
        self.max_stake = 50000  # Maximum stake in Stars
        self.active_games = {}  # In-memory storage for active games
        self.pending_challenges = {}  # Challenges waiting for opponents
        self.time_controls = {
        "bullet": 60,  # 1 minute per player
        "blitz": 300,  # 5 minutes per player  
        "rapid": 600,  # 10 minutes per player
        }
        self.default_time_control = "blitz"
        
    def get_init_data(self, user_id: str) -> Dict[str, Any]:
        """Get initial game data for a user"""
        try:
            user_data = get_user_data(user_id) or {}
            return {
                "name": self.name,
                "instructions": self._get_instructions(),
                "min_stake": self.min_stake,
                "max_stake": self.max_stake,
                "user_data": {
                    "user_id": user_id,
                    "stars_balance": user_data.get('stars_balance', 0),
                    "game_coins": user_data.get('game_coins', 0)
                },
                "active_games": self._get_user_active_games(user_id),
                "available_challenges": self._get_available_challenges(user_id)
            }
        except Exception as e:
            logger.error(f"Error getting init data for {self.name}: {e}")
            return {
                "name": self.name,
                "instructions": self._get_instructions(),
                "min_stake": self.min_stake,
                "max_stake": self.max_stake,
                "user_data": {}
            }
    
    def create_challenge(self, user_id: str, stake: int, color_preference: str = "random") -> Dict[str, Any]:
        """Create a new chess challenge"""
        try:
            # Validate stake amount
            if stake < self.min_stake or stake > self.max_stake:
                return {"error": f"Stake must be between {self.min_stake} and {self.max_stake} Stars"}
            
            # Check if user has enough Stars
            user_data = get_user_data(user_id)
            if user_data.get('stars_balance', 0) < stake:
                return {"error": "Insufficient Stars balance"}
            
            # Determine colors
            if color_preference == "random":
                is_white = bool(int(time.time()) % 2)
            else:
                is_white = color_preference.lower() in ["white", "w"]
            
            # Create challenge ID
            challenge_id = str(uuid.uuid4())
            
            # Store challenge
            self.pending_challenges[challenge_id] = {
                "challenger_id": user_id,
                "stake": stake,
                "challenger_color": "white" if is_white else "black",
                "created_at": datetime.utcnow(),
                "status": "waiting"
            }
            
            logger.info(f"Chess challenge created by user {user_id} with stake {stake}")
            
            return {
                "challenge_id": challenge_id,
                "stake": stake,
                "color": "white" if is_white else "black"
            }
            
        except Exception as e:
            logger.error(f"Error creating chess challenge: {e}")
            return {"error": "Failed to create challenge"}
    
    def accept_challenge(self, user_id: str, challenge_id: str) -> Dict[str, Any]:
        """Accept a chess challenge"""
        try:
            # Check if challenge exists
            if challenge_id not in self.pending_challenges:
                return {"error": "Challenge not found"}
            
            challenge = self.pending_challenges[challenge_id]
            
            # Check if user is trying to accept their own challenge
            if challenge["challenger_id"] == user_id:
                return {"error": "Cannot accept your own challenge"}
            
            # Check if user has enough Stars
            user_data = get_user_data(user_id)
            if user_data.get('stars_balance', 0) < challenge["stake"]:
                return {"error": "Insufficient Stars balance"}
            
            # Determine colors
            challenger_color = challenge["challenger_color"]
            acceptor_color = "black" if challenger_color == "white" else "white"
            
            # Create game ID
            game_id = str(uuid.uuid4())
            
            # Initialize game
            board = chess_masters.Board()
            
            # Store game
            self.active_games[game_id] = {
                "white_player": challenge["challenger_id"] if challenger_color == "white" else user_id,
                "black_player": user_id if challenger_color == "white" else challenge["challenger_id"],
                "white_stake": challenge["stake"],
                "black_stake": challenge["stake"],
                "board_fen": board.fen(),
                "status": "active",
                "created_at": datetime.utcnow(),
                "move_history": [],
                "bets": {}  # user_id: {"amount": X, "on_player": "white/black"}
            }
            
            # Remove challenge from pending
            del self.pending_challenges[challenge_id]
            
            logger.info(f"Chess challenge {challenge_id} accepted by user {user_id}, game {game_id} started")
            
            return {
                "game_id": game_id,
                "white_player": self.active_games[game_id]["white_player"],
                "black_player": self.active_games[game_id]["black_player"],
                "stake": challenge["stake"],
                "your_color": acceptor_color
            }
            
        except Exception as e:
            logger.error(f"Error accepting chess challenge: {e}")
            return {"error": "Failed to accept challenge"}
    
    def make_move(self, user_id: str, game_id: str, move_uci: str) -> Dict[str, Any]:
        """Make a move in a chess game"""
        try:
            # Check if game exists
            if game_id not in self.active_games:
                return {"error": "Game not found"}
            
            game = self.active_games[game_id]
            
            # Check if game is active
            if game["status"] != "active":
                return {"error": "Game is not active"}
            
            # Check if it's the user's turn
            board = chess_masters.Board(game["board_fen"])
            is_white_turn = board.turn == chess_masters.WHITE
            
            # Determine if user is white or black
            if is_white_turn and user_id != game["white_player"]:
                return {"error": "Not your turn"}
            if not is_white_turn and user_id != game["black_player"]:
                return {"error": "Not your turn"}
            
            # Validate move
            try:
                move = chess_masters.Move.from_uci(move_uci)
                if move not in board.legal_moves:
                    return {"error": "Illegal move"}
            except ValueError:
                return {"error": "Invalid move format"}
            
            # Make the move
            board.push(move)
            game["board_fen"] = board.fen()
            game["move_history"].append({
                "player": user_id,
                "move": move_uci,
                "timestamp": datetime.utcnow()
            })
            
            # Check for game end
            outcome = board.outcome()
            result = {
                "success": True,
                "fen": board.fen(),
                "move": move_uci,
                "is_game_over": outcome is not None
            }
            
            if outcome:
                game["status"] = "completed"
                result["game_result"] = self._determine_game_result(outcome)
                
                # Process payouts
                self._process_payouts(game_id, result["game_result"])
            
            return result
            
        except Exception as e:
            logger.error(f"Error making chess move: {e}")
            return {"error": "Failed to make move"}
    
    def place_bet(self, user_id: str, game_id: str, amount: int, on_player: str) -> Dict[str, Any]:
        """Place a bet on a chess game"""
        try:
            # Check if game exists
            if game_id not in self.active_games:
                return {"error": "Game not found"}
            
            game = self.active_games[game_id]
            
            # Check if game is active
            if game["status"] != "active":
                return {"error": "Bets closed for this game"}
            
            # Validate player selection
            if on_player not in ["white", "black"]:
                return {"error": "Invalid player selection"}
            
            # Check if user has enough game coins
            user_data = get_user_data(user_id)
            if user_data.get('game_coins', 0) < amount:
                return {"error": "Insufficient game coins"}
            
            # Record bet
            if user_id not in game["bets"]:
                game["bets"][user_id] = []
            
            game["bets"][user_id].append({
                "amount": amount,
                "on_player": on_player,
                "placed_at": datetime.utcnow()
            })
            
            # Deduct bet amount from user's balance
            update_user_data(user_id, {"game_coins": user_data.get('game_coins', 0) - amount})
            
            logger.info(f"User {user_id} bet {amount} game coins on {on_player} in game {game_id}")
            
            return {
                "success": True,
                "amount": amount,
                "on_player": on_player,
                "new_balance": user_data.get('game_coins', 0) - amount
            }
            
        except Exception as e:
            logger.error(f"Error placing bet: {e}")
            return {"error": "Failed to place bet"}
    
    def get_game_state(self, game_id: str) -> Dict[str, Any]:
        """Get the current state of a game"""
        if game_id not in self.active_games:
            return {"error": "Game not found"}
        
        game = self.active_games[game_id]
        board = chess_masters.Board(game["board_fen"])
        
        return {
            "fen": game["board_fen"],
            "status": game["status"],
            "white_player": game["white_player"],
            "black_player": game["black_player"],
            "white_stake": game["white_stake"],
            "black_stake": game["black_stake"],
            "move_count": len(game["move_history"]),
            "current_turn": "white" if board.turn == chess_masters.WHITE else "black",
            "is_check": board.is_check(),
            "is_checkmate": board.is_checkmate(),
            "is_stalemate": board.is_stalemate(),
            "bets": game["bets"]  # This might need to be sanitized in production
        }
    
    def _get_instructions(self) -> str:
        """Get game instructions"""
        return "Play chess against other players. Stake Telegram Stars to play, and spectators can bet Game Coins on the outcome."
    
    def _get_user_active_games(self, user_id: str) -> List[Dict[str, Any]]:
        """Get active games for a user"""
        user_games = []
        for game_id, game in self.active_games.items():
            if game["status"] == "active" and (user_id == game["white_player"] or user_id == game["black_player"]):
                user_games.append({
                    "game_id": game_id,
                    "opponent": game["black_player"] if user_id == game["white_player"] else game["white_player"],
                    "stake": game["white_stake"] if user_id == game["white_player"] else game["black_stake"],
                    "your_color": "white" if user_id == game["white_player"] else "black"
                })
        return user_games
    
    def _get_available_challenges(self, user_id: str) -> List[Dict[str, Any]]:
        """Get available challenges that a user can accept"""
        challenges = []
        for challenge_id, challenge in self.pending_challenges.items():
            if challenge["challenger_id"] != user_id and challenge["status"] == "waiting":
                challenges.append({
                    "challenge_id": challenge_id,
                    "challenger_id": challenge["challenger_id"],
                    "stake": challenge["stake"],
                    "challenger_color": challenge["challenger_color"]
                })
        return challenges
    
    def _determine_game_result(self, outcome) -> Dict[str, Any]:
        """Determine the game result from chess outcome"""
        if outcome.winner == chess_masters.WHITE:
            return {"winner": "white", "termination": outcome.termination.name}
        elif outcome.winner == chess_masters.BLACK:
            return {"winner": "black", "termination": outcome.termination.name}
        else:
            return {"winner": None, "termination": outcome.termination.name}
    
    def _process_payouts(self, game_id: str, result: Dict[str, Any]) -> None:
        """Process payouts for players and bettors"""
        game = self.active_games[game_id]
        
        # Process player payouts
        if result["winner"] == "white":
            # White player wins both stakes
            white_reward = game["white_stake"] + game["black_stake"]
            # Update white player's Stars balance
            white_data = get_user_data(game["white_player"])
            update_user_data(game["white_player"], {
                "stars_balance": white_data.get('stars_balance', 0) + white_reward
            })
        elif result["winner"] == "black":
            # Black player wins both stakes
            black_reward = game["white_stake"] + game["black_stake"]
            # Update black player's Stars balance
            black_data = get_user_data(game["black_player"])
            update_user_data(game["black_player"], {
                "stars_balance": black_data.get('stars_balance', 0) + black_reward
            })
        # If draw, return stakes to players
        else:
            white_data = get_user_data(game["white_player"])
            black_data = get_user_data(game["black_player"])
            update_user_data(game["white_player"], {
                "stars_balance": white_data.get('stars_balance', 0) + game["white_stake"]
            })
            update_user_data(game["black_player"], {
                "stars_balance": black_data.get('stars_balance', 0) + game["black_stake"]
            })
        
        # Process bettor payouts
        winning_bettors = []
        losing_bettors = []
        total_winning_bets = 0
        total_pot = 0
        
        # Calculate total pot and identify winning/losing bets
        for user_id, bets in game["bets"].items():
            for bet in bets:
                total_pot += bet["amount"]
                if bet["on_player"] == result["winner"]:
                    winning_bettors.append((user_id, bet["amount"]))
                    total_winning_bets += bet["amount"]
                else:
                    losing_bettors.append((user_id, bet["amount"]))
        
        # Distribute winnings to winning bettors
        if winning_bettors and total_winning_bets > 0:
            for user_id, bet_amount in winning_bettors:
                user_share = bet_amount / total_winning_bets
                user_winning = user_share * total_pot
                
                user_data = get_user_data(user_id)
                update_user_data(user_id, {
                    "game_coins": user_data.get('game_coins', 0) + user_winning
                })
        
        logger.info(f"Processed payouts for game {game_id}: {result}")


