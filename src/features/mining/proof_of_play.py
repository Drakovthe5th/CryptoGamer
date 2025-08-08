class ProofOfPlay:
    def __init__(self):
        self.difficulty_adjustment_interval = 1000  # blocks
        self.reward_per_block = 0.1  # TON
        
    def calculate_reward(self, user_activity_score, streak_count):
        """
        Calculate rewards based on:
        - Game performance
        - Time spent
        - Skill demonstrated
        """
        # Base reward
        reward = self.reward_per_block
        
        # Multipliers
        if user_activity_score > 90:
            reward *= 1.5  # Expert bonus
        elif user_activity_score > 70:
            reward *= 1.2  # Skilled bonus
            
        # Daily streak bonus
        reward *= (1 + (streak_count * 0.05))
        
        return reward

    def verify_play(self, game_data):
        """Anti-cheat verification"""
        # Check for human-like patterns
        if game_data.get('click_interval', 0) < 0.1:
            return False  # Too fast for human
            
        # Verify score progression
        max_possible = game_data.get('possible_max_score', 100)
        if game_data.get('score', 0) > max_possible:
            return False  # Impossible score
            
        # Check time consistency
        min_time = game_data.get('min_expected_time', 30)
        if game_data.get('duration', 0) < min_time:
            return False  # Completed too quickly
            
        return True