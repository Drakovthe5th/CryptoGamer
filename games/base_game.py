class BaseGame:
    def __init__(self, name):
        self.name = name
        self.players = {}
        self.min_reward = 0.001  # Min TON reward
        self.max_reward = 0.1    # Max TON reward
    
    def get_init_data(self, user_id):
        return {
            "name": self.name,
            "instructions": "",
            "high_score": 0,
            "user_data": {}
        }
    
    def start_game(self, user_id):
        self.players[user_id] = {
            "score": 0,
            "start_time": time.time(),
            "active": True
        }
        return {"status": "started"}
    
    def handle_action(self, user_id, action, data):
        raise NotImplementedError
    
    def end_game(self, user_id):
        player = self.players.get(user_id)
        if not player or not player["active"]:
            return {"error": "Game not active"}
        
        player["active"] = False
        duration = time.time() - player["start_time"]
        
        # Calculate TON reward
        reward = min(
            self.min_reward + (player["score"] * 0.0001),
            self.max_reward
        )
        
        return {
            "score": player["score"],
            "duration": duration,
            "reward": reward,
            "new_high_score": player["score"] > player.get("high_score", 0)
        }
    
    def validate_anti_cheat(self, user_id, current_score):
        # Implement cheat detection logic
        player = self.players.get(user_id)
        if not player:
            return False
        
        # Check for impossible score jumps
        if current_score - player["score"] > self.max_score_per_second * 2:
            return False
        
        player["score"] = current_score
        return True
    
    def validate_score(self, user_id, new_score):
        player = self.players.get(user_id)
        if not player:
            return False
        
        # Calculate max possible score increase
        elapsed = time.time() - player["last_update"]
        max_possible = player["score"] + (self.max_score_per_second * elapsed)
        
        if new_score > max_possible:
            # Flag for review
            self.flag_suspicious(user_id, f"Score jump: {player['score']} to {new_score}")
            return False
        
        player["score"] = new_score
        player["last_update"] = time.time()
        return True