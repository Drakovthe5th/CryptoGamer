from .base_game import BaseGame

class TRexRunner(BaseGame):
    def __init__(self):
        super().__init__("trex")
        self.max_score_per_second = 100  # Anti-cheat threshold
        
    def get_init_data(self, user_id):
        return {
            **super().get_init_data(user_id),
            "instructions": "Avoid obstacles and run as far as possible to earn TON!",
            "controls": {
                "jump": ["Space", "Up Arrow", "Tap"],
                "duck": ["Down Arrow"]
            }
        }
    
    def handle_action(self, user_id, action, data):
        player = self.players.get(user_id)
        if not player or not player["active"]:
            return {"error": "Game not active"}
        
        if action == "game_update":
            if not self.validate_anti_cheat(user_id, data["score"]):
                return {"error": "Invalid game state", "status": "cheat_detected"}
            
            return {"status": "update_accepted"}
        
        elif action == "game_over":
            player["score"] = data["score"]
            player["active"] = False
            return self.end_game(user_id)
        
        return {"error": "Invalid action"}