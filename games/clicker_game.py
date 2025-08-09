from .base_game import BaseGame
import time

class ClickerGame(BaseGame):
    def __init__(self):
        super().__init__("clicker")
        self.max_score_per_second = 15  # Anti-cheat threshold
        self.base_click_value = 0.0001  # TON per click
        self.upgrades = self.load_upgrades()
    
    def load_upgrades(self):
        return [
            {"id": "auto_click", "name": "Auto Click", "cost": 10, "rate": 1, "description": "Earns 1 TON per second automatically"},
            {"id": "mega_click", "name": "Mega Click", "cost": 50, "value": 5, "description": "Each click is worth 5x more"},
            {"id": "ton_boost", "name": "TON Boost", "cost": 200, "multiplier": 2, "description": "Doubles all income sources"},
            {"id": "jackpot", "name": "Jackpot", "cost": 1000, "bonus": 100, "description": "Instantly get 100 TON"}
        ]
    
    def get_init_data(self, user_id):
        return {
            **super().get_init_data(user_id),
            "instructions": "Click to earn TON coins! Buy upgrades to increase your earnings.",
            "upgrades": self.upgrades,
            "base_value": self.base_click_value
        }
    
    def start_game(self, user_id):
        super().start_game(user_id)
        self.players[user_id].update({
            "click_value": self.base_click_value,
            "auto_clickers": 0,
            "income_multiplier": 1.0,
            "last_click_time": time.time(),
            "last_auto_time": time.time(),
            "upgrades": []
        })
        return {"status": "started"}
    
    def handle_action(self, user_id, action, data):
        player = self.players.get(user_id)
        if not player or not player["active"]:
            return {"error": "Game not active"}
        
        current_time = time.time()
        
        if action == "click":
            # Anti-cheat: Check click rate
            if current_time - player["last_click_time"] < 0.05:  # 20 clicks/sec max
                return {"error": "Too fast"}
            
            player["score"] += player["click_value"] * player["income_multiplier"]
            player["last_click_time"] = current_time
            return {"score": player["score"]}
        
        elif action == "buy_upgrade":
            upgrade_id = data["upgrade_id"]
            upgrade = next((u for u in self.upgrades if u["id"] == upgrade_id), None)
            
            if not upgrade:
                return {"error": "Invalid upgrade"}
            
            # Check if player can afford
            if player["score"] < upgrade["cost"]:
                return {"error": "Not enough TON"}
            
            # Apply upgrade
            player["score"] -= upgrade["cost"]
            player["upgrades"].append(upgrade_id)
            
            if upgrade_id == "mega_click":
                player["click_value"] = self.base_click_value * upgrade["value"]
            elif upgrade_id == "auto_click":
                player["auto_clickers"] += upgrade["rate"]
            elif upgrade_id == "ton_boost":
                player["income_multiplier"] *= upgrade["multiplier"]
            elif upgrade_id == "jackpot":
                player["score"] += upgrade["bonus"]
            
            return {
                "score": player["score"],
                "upgrade": upgrade_id,
                "click_value": player["click_value"],
                "auto_clickers": player["auto_clickers"],
                "income_multiplier": player["income_multiplier"]
            }
        
        elif action == "collect_auto":
            # Calculate auto click earnings
            if "auto_click" in player["upgrades"]:
                elapsed = current_time - player["last_auto_time"]
                earnings = player["auto_clickers"] * elapsed * player["income_multiplier"]
                player["score"] += earnings
                player["last_auto_time"] = current_time
                return {"score": player["score"], "auto_earnings": earnings}
        
        return {"error": "Invalid action"}
    
    def end_game(self, user_id):
        return super().end_game(user_id)