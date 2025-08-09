import random
import time
from .base_game import BaseGame

class SpinGame(BaseGame):
    def __init__(self):
        super().__init__("spin")
        self.wheel_sections = self.load_wheel_sections()
        self.spin_cost = 0.0001  # TON per spin
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
        player = self.players.get(user_id)
        if not player or not player["active"]:
            return {"error": "Player not active"}
        
        current_time = time.time()
        
        # Rate limiting
        if self.last_spin_time.get(user_id, 0) > current_time - 1:
            return {"error": "Spin too fast. Wait 1 second between spins."}
        
        if action == "spin":
            # Deduct spin cost
            if player["score"] < self.spin_cost:
                return {"error": "Insufficient balance"}
            
            player["score"] -= self.spin_cost
            result = self.calculate_spin()
            
            # Award winnings
            player["score"] += result["value"]
            player["spins"] += 1
            self.last_spin_time[user_id] = current_time
            
            return {
                "result": result,
                "score": player["score"],
                "spins": player["spins"]
            }
        
        return {"error": "Invalid action"}
    
    def calculate_spin(self):
        rand = random.random()
        cumulative = 0
        for section in self.wheel_sections:
            cumulative += section["probability"]
            if rand <= cumulative:
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