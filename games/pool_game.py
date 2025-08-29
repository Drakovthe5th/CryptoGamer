import random
import math
from enum import Enum
from datetime import datetime
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
        super().__init__("Pool Game", "pool")
        self.max_players = 6
        self.active_games = {}  # game_id -> game_data
        self.player_games = {}  # user_id -> game_id
        
    def get_init_data(self, user_id: str) -> Dict[str, Any]:
        base_data = super().get_init_data(user_id)
        base_data.update({
            "max_players": self.max_players,
            "min_players": 2,
            "can_bet": True,
            "min_bet": 1,  # Minimum bet in Stars
            "max_bet": 100  # Maximum bet in Stars
        })
        return base_data
        
    def create_game(self, user_id: str, bet_amount: int) -> Dict[str, Any]:
        # Check if user has enough Stars
        user_data = get_user_data(user_id)
        if user_data.get('telegram_stars', 0) < bet_amount:
            return {"error": "Insufficient Stars"}
        
        # Deduct the bet amount
        if not deduct_stars(user_id, bet_amount):
            return {"error": "Failed to deduct Stars"}
        
        # Generate game ID
        game_id = f"pool_{datetime.now().timestamp()}_{user_id}"
        
        # Initialize game state
        self.active_games[game_id] = {
            "players": [user_id],
            "bets": {user_id: bet_amount},
            "pot": bet_amount,
            "status": PoolGameState.WAITING_FOR_PLAYERS,
            "current_turn": None,
            "start_time": datetime.now(),
            "bet_amount": bet_amount,  # The agreed bet amount
            "game_data": {}  # Will store the game state (balls positions, etc.)
        }
        
        self.player_games[user_id] = game_id
        
        return {
            "game_id": game_id,
            "status": "waiting",
            "players": [user_id],
            "pot": bet_amount
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
        if user_data.get('telegram_stars', 0) < bet_amount:
            return {"error": "Insufficient Stars"}
        
        # Deduct the bet amount
        if not deduct_stars(user_id, bet_amount):
            return {"error": "Failed to deduct Stars"}
        
        # Add player to the game
        game["players"].append(user_id)
        game["bets"][user_id] = bet_amount
        game["pot"] += bet_amount
        self.player_games[user_id] = game_id
        
        # If the game is now full, start it
        if len(game["players"]) == self.max_players:
            game["status"] = PoolGameState.IN_PROGRESS
            # Set the first player's turn
            game["current_turn"] = game["players"][0]
        
        return {
            "game_id": game_id,
            "status": game["status"].name,
            "players": game["players"],
            "pot": game["pot"]
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
            
            # Process the shot (update game state)
            success = self._process_shot(game, data)
            
            if success:
                # Move to next player
                current_index = game["players"].index(user_id)
                next_index = (current_index + 1) % len(game["players"])
                game["current_turn"] = game["players"][next_index]
                
                # Check if game is over (all balls potted)
                if self._is_game_over(game):
                    winner = self._determine_winner(game)
                    self._distribute_winnings(game_id, winner)
                    return {"status": "game_over", "winner": winner}
                
                return {"status": "success", "next_turn": game["current_turn"]}
            else:
                return {"error": "Invalid shot"}
        
        elif action == "forfeit":
            # Remove player from the game and distribute winnings to the remaining players
            winner = [p for p in game["players"] if p != user_id][0]
            self._distribute_winnings(game_id, winner)
            return {"status": "forfeited", "winner": winner}
        
        else:
            return {"error": "Unknown action"}
            
    def _process_shot(self, game: Dict[str, Any], shot_data: Dict[str, Any]) -> bool:
        # Placeholder for actual pool game physics and logic
        # This would update the game state (ball positions, etc.)
        return True
        
    def _is_game_over(self, game: Dict[str, Any]) -> bool:
        # Placeholder: check if all balls are potted
        return False
        
    def _determine_winner(self, game: Dict[str, Any]) -> str:
        # Placeholder: determine the winner based on the game state
        # For now, just return the first player
        return game["players"][0]
        
    def _distribute_winnings(self, game_id: str, winner: str):
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
            'end_time': datetime.now()
        })
        
        # Clean up the game
        for player in game["players"]:
            if player in self.player_games:
                del self.player_games[player]
        
        del self.active_games[game_id]