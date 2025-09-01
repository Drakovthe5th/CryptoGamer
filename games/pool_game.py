import random
import math
import time
from enum import Enum
from datetime import datetime
from typing import Dict, Any, List, Optional
from .base_game import BaseGame
from src.database.mongo import get_user_data, update_user_data
from src.integrations.telegram import deduct_stars, add_stars
from src.database.game_db import save_pool_game_result

class PoolGameState(Enum):
    WAITING_FOR_PLAYERS = 0
    WAITING_FOR_BETS = 1
    IN_PROGRESS = 2
    COMPLETED = 3

class PoolGame(BaseGame):
    def __init__(self):
        super().__init__("Pool Game")
        self.max_players = 6
        self.active_games = {}  # game_id -> game_data
        self.player_games = {}  # user_id -> game_id
        self.min_bet = 1  # Minimum bet in Stars
        self.max_bet = 100  # Maximum bet in Stars
        
    def get_init_data(self, user_id: str) -> Dict[str, Any]:
        base_data = super().get_init_data(user_id)
        user_data = get_user_data(user_id)
        
        base_data.update({
            "max_players": self.max_players,
            "min_players": 2,
            "can_bet": True,
            "min_bet": self.min_bet,
            "max_bet": self.max_bet,
            "stars_balance": user_data.get('telegram_stars', 0) if user_data else 0
        })
        return base_data
        
    def create_game(self, user_id: str, bet_amount: int) -> Dict[str, Any]:
        # Validate bet amount
        if bet_amount < self.min_bet or bet_amount > self.max_bet:
            return {"error": f"Bet must be between {self.min_bet} and {self.max_bet} Stars"}
        
        # Check if user has enough Stars
        user_data = get_user_data(user_id)
        if not user_data or user_data.get('telegram_stars', 0) < bet_amount:
            return {"error": "Insufficient Stars"}
        
        # Deduct the bet amount
        if not deduct_stars(user_id, bet_amount):
            return {"error": "Failed to deduct Stars"}
        
        # Generate game ID
        game_id = f"pool_{int(time.time())}_{user_id}"
        
        # Initialize game state
        self.active_games[game_id] = {
            "players": [user_id],
            "bets": {user_id: bet_amount},
            "pot": bet_amount,
            "status": PoolGameState.WAITING_FOR_PLAYERS,
            "current_turn": None,
            "start_time": datetime.now(),
            "bet_amount": bet_amount,  # The agreed bet amount
            "balls": self._setup_initial_balls(),
            "game_data": {
                "shots_taken": 0,
                "balls_potted": 0,
                "last_shot": None
            }
        }
        
        self.player_games[user_id] = game_id
        
        return {
            "success": True,
            "game_id": game_id,
            "status": "waiting_for_players",
            "players": [user_id],
            "pot": bet_amount,
            "required_bet": bet_amount
        }
        
    def join_game(self, user_id: str, game_id: str) -> Dict[str, Any]:
        if game_id not in self.active_games:
            return {"error": "Game not found"}
        
        game = self.active_games[game_id]
        
        if len(game["players"]) >= self.max_players:
            return {"error": "Game is full"}
        
        if user_id in game["players"]:
            return {"error": "Already in game"}
        
        # Check if user has enough Stars for the bet
        bet_amount = game["bet_amount"]
        user_data = get_user_data(user_id)
        if not user_data or user_data.get('telegram_stars', 0) < bet_amount:
            return {"error": "Insufficient Stars"}
        
        # Deduct the bet amount
        if not deduct_stars(user_id, bet_amount):
            return {"error": "Failed to deduct Stars"}
        
        # Add player to the game
        game["players"].append(user_id)
        game["bets"][user_id] = bet_amount
        game["pot"] += bet_amount
        self.player_games[user_id] = game_id
        
        # If the game has enough players, start it
        if len(game["players"]) >= 2 and game["status"] == PoolGameState.WAITING_FOR_PLAYERS:
            game["status"] = PoolGameState.WAITING_FOR_BETS
            
        return {
            "success": True,
            "game_id": game_id,
            "status": game["status"].name,
            "players": game["players"],
            "pot": game["pot"],
            "required_bet": bet_amount
        }
        
    def start_game(self, game_id: str) -> Dict[str, Any]:
        if game_id not in self.active_games:
            return {"error": "Game not found"}
        
        game = self.active_games[game_id]
        
        if len(game["players"]) < 2:
            return {"error": "Not enough players"}
        
        if game["status"] != PoolGameState.WAITING_FOR_BETS:
            return {"error": "Game not in betting phase"}
        
        # Start the game
        game["status"] = PoolGameState.IN_PROGRESS
        game["current_turn"] = game["players"][0]  # First player starts
        
        return {
            "success": True,
            "game_id": game_id,
            "status": "in_progress",
            "current_turn": game["current_turn"],
            "players": game["players"]
        }
        
    def handle_action(self, user_id: str, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        game_id = self.player_games.get(user_id)
        if not game_id:
            return {"error": "Not in a game"}
        
        game = self.active_games.get(game_id)
        if not game:
            return {"error": "Game not found"}
        
        if action == "take_shot":
            # Validate it's the user's turn
            if game["current_turn"] != user_id:
                return {"error": "Not your turn"}
            
            # Process the shot
            angle = data.get("angle", 0)
            power = data.get("power", 0)
            success, result = self._process_shot(game, angle, power)
            
            if success:
                # Update game state
                game["game_data"]["shots_taken"] += 1
                game["game_data"]["last_shot"] = {
                    "player": user_id,
                    "angle": angle,
                    "power": power,
                    "timestamp": datetime.now()
                }
                
                # Move to next player if no ball was potted or foul
                if not result.get("ball_potted", False) or result.get("foul", False):
                    current_index = game["players"].index(user_id)
                    next_index = (current_index + 1) % len(game["players"])
                    game["current_turn"] = game["players"][next_index]
                
                # Check if game is over
                if self._is_game_over(game):
                    winner = self._determine_winner(game)
                    self._distribute_winnings(game_id, winner)
                    return {
                        "status": "game_over", 
                        "winner": winner,
                        "pot": game["pot"]
                    }
                
                return {
                    "success": True, 
                    "next_turn": game["current_turn"],
                    "shot_result": result
                }
            else:
                return {"error": "Invalid shot"}
        
        elif action == "forfeit":
            # Remove player and distribute winnings
            remaining_players = [p for p in game["players"] if p != user_id]
            if remaining_players:
                winner = remaining_players[0]
                self._distribute_winnings(game_id, winner)
                return {"status": "forfeited", "winner": winner}
            else:
                # Refund if no players left
                self._refund_bets(game_id)
                return {"status": "game_cancelled"}
        
        else:
            return {"error": "Unknown action"}
            
    def _setup_initial_balls(self) -> List[Dict[str, Any]]:
        """Set up initial ball positions (standard pool rack)"""
        balls = []
        
        # Cue ball
        balls.append({
            "type": "cue",
            "x": 200, "y": 200,
            "potted": False,
            "number": 0
        })
        
        # Rack of 15 balls in triangle formation
        ball_number = 1
        for row in range(5):
            for col in range(row + 1):
                x = 600 + row * 30
                y = 200 - (row * 15) + (col * 30)
                balls.append({
                    "type": "numbered",
                    "x": x, "y": y,
                    "potted": False,
                    "number": ball_number
                })
                ball_number += 1
        
        return balls
        
    def _process_shot(self, game: Dict[str, Any], angle: float, power: float) -> tuple:
        """Process a shot - simplified physics for MVP"""
        # This is a simplified implementation - real physics would be more complex
        try:
            # Calculate ball movement based on angle and power
            result = {
                "ball_potted": random.random() > 0.7,  # 30% chance to pot a ball
                "foul": random.random() > 0.9,  # 10% chance of foul
                "balls_moved": min(int(power * 5), 5),  # Number of balls affected
                "power": power
            }
            
            if result["ball_potted"]:
                game["game_data"]["balls_potted"] += 1
                
            # Update ball positions (simplified)
            for ball in game["balls"]:
                if not ball["potted"] and random.random() < power * 0.3:
                    ball["x"] += math.cos(angle) * power * 50
                    ball["y"] += math.sin(angle) * power * 50
                    
                    # Check if ball is potted (simplified)
                    if (ball["x"] < 50 or ball["x"] > 750 or 
                        ball["y"] < 50 or ball["y"] > 350):
                        ball["potted"] = True
                        result["ball_potted"] = True
            
            return True, result
            
        except Exception as e:
            return False, {"error": str(e)}
        
    def _is_game_over(self, game: Dict[str, Any]) -> bool:
        """Check if game is over (all balls potted)"""
        numbered_balls = [b for b in game["balls"] if b["type"] == "numbered"]
        potted_balls = [b for b in numbered_balls if b["potted"]]
        return len(potted_balls) >= len(numbered_balls) * 0.8  # 80% of balls potted
        
    def _determine_winner(self, game: Dict[str, Any]) -> str:
        """Determine winner based on balls potted (simplified)"""
        # In a real game, this would be more complex with scoring
        return game["players"][0]  # First player wins for MVP
        
    def _distribute_winnings(self, game_id: str, winner: str):
        """Distribute winnings to the winner"""
        game = self.active_games[game_id]
        pot = game["pot"]
        
        # Add the pot to the winner's Stars balance
        add_stars(winner, pot)
        
        # Record the game result in the database
        save_pool_game_result({
            'game_id': game_id,
            'players': game["players"],
            'bets': game["bets"],
            'pot': pot,
            'winner': winner,
            'start_time': game["start_time"],
            'end_time': datetime.now(),
            'shots_taken': game["game_data"]["shots_taken"],
            'balls_potted': game["game_data"]["balls_potted"]
        })
        
        # Clean up the game
        for player in game["players"]:
            if player in self.player_games:
                del self.player_games[player]
        
        del self.active_games[game_id]
        
    def _refund_bets(self, game_id: str):
        """Refund bets if game is cancelled"""
        game = self.active_games[game_id]
        
        for player_id, bet_amount in game["bets"].items():
            add_stars(player_id, bet_amount)
        
        # Clean up the game
        for player in game["players"]:
            if player in self.player_games:
                del self.player_games[player]
        
        del self.active_games[game_id]
        
    def get_game_state(self, game_id: str) -> Dict[str, Any]:
        """Get current game state"""
        if game_id not in self.active_games:
            return {"error": "Game not found"}
        
        game = self.active_games[game_id]
        return {
            "players": game["players"],
            "pot": game["pot"],
            "status": game["status"].name,
            "current_turn": game["current_turn"],
            "balls": game["balls"],
            "game_data": game["game_data"]
        }