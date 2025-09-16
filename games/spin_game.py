from config import config
from src.database.mongo import get_user_data, update_user_data
from src.utils.security import validate_session_token
import random
import time
from .base_game import BaseGame

TON_TO_GC_RATE = 2000  # 2000 Game Coins = 1 TON
SPIN_COST_GC = 0.2  # 0.0001 TON * 2000 = 0.2 GC

class SpinGame(BaseGame):
    def __init__(self):
        super().__init__("spin")
        self.wheel_sections = self.load_wheel_sections()
        self.spin_cost = SPIN_COST_GC
        self.last_spin_time = {}
        
    def load_wheel_sections(self):
        return [
            {"id": "jackpot", "value": 100, "probability": 0.01, "color": "#FFD700"},
            {"id": "high", "value": 50, "probability": 0.1, "color": "#FF6347"},
            {"id": "medium", "value": 20, "probability": 0.2, "color": "#4682B4"},
            {"id": "low", "value": 10, "probability": 0.3, "color": "#32CD32"},
            {"id": "min", "value": 5, "probability": 0.39, "color": "#87CEEB"}
        ]
    
    def get_init_data(self, user_id):
        return {
            **super().get_init_data(user_id),
            "instructions": "Spin the wheel to win TON coins! Each spin costs 0.0001 TON.",
            "wheel": self.wheel_sections,
            "spin_cost": self.spin_cost
        }
    
    def start_game(self, user_id):
        # Spin game doesn't have a traditional start, but we initialize player
        if user_id not in self.players:
            self.players[user_id] = {
                "score": 0.0,  # Total TON won
                "spins": 0,
                "active": True
            }
        return {"status": "ready"}
    
    def handle_action(self, user_id, action, data):
        # Add session validation
        if not validate_session_token(user_id, data.get('token')):
            return {"error": "Invalid session token"}
        
        player = self.players.get(user_id)
        if not player or not player["active"]:
            return {"error": "Player not active"}
        
        current_time = time.time()
        
        # Rate limiting
        if self.last_spin_time.get(user_id, 0) > current_time - 1:
            return {"error": "Spin too fast. Wait 1 second between spins."}
        
        if action == "spin":
            # Check user balance from database
            user_data = get_user_data(user_id)
            if user_data.get('game_coins', 0) < self.spin_cost_gc:
                return {"error": "Insufficient balance"}
            
            # Deduct spin cost
            update_user_data(user_id, {'game_coins': user_data['game_coins'] - self.spin_cost_gc})
            
            result = self.calculate_spin()
            
            # Award winnings
            new_balance = user_data['game_coins'] - self.spin_cost_gc + result["gc_value"]
            update_user_data(user_id, {'game_coins': new_balance})
            
            player["spins"] += 1
            self.last_spin_time[user_id] = current_time
            
            return {
                "result": result,
                "new_balance": new_balance,
                "spins": player["spins"]
            }
        
        return {"error": "Invalid action"}
    
    def calculate_spin(self):
        rand = random.random()
        cumulative = 0
        for section in self.wheel_sections:
            cumulative += section["probability"]
            if rand <= cumulative:
                # Convert TON value to GC
                section["gc_value"] = section["value"] * TON_TO_GC_RATE
                return section
        return self.wheel_sections[-1]  # Fallback
    
    def end_game(self, user_id):
        player = self.players.get(user_id)
        if not player:
            return {"error": "Player not found"}
        
        # Cash out the winnings
        winnings = player["score"]
        player["active"] = False
        return {
            "status": "cashed_out",
            "total_winnings": winnings,
            "total_spins": player["spins"]
        }