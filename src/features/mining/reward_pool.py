from src.integrations.tonE2 import usd_to_ton
from src.database.firebase import get_reward_pool, update_reward_pool

class RewardPool:
    def __init__(self):
        self.balance = get_reward_pool()
        self.daily_emission = 50  # TON
        self.user_activity_pool = 0.7  # 70% of emission to active users
        
    def allocate_rewards(self, user_activity_score, total_platform_activity):
        """Distribute rewards based on today's activity"""
        # Calculate user's share of activity pool
        activity_share = (user_activity_score / total_platform_activity) * \
                         (self.daily_emission * self.user_activity_pool)
        
        # Add bonus rewards
        bonus = self.calculate_bonuses(user_activity_score)
        
        return activity_share + bonus

    def replenish_pool(self, revenue_usd):
        """Add funds from monetization sources"""
        # Convert revenue to TON
        ton_amount = usd_to_ton(revenue_usd * 0.5)  # 50% of revenue to rewards
        
        # Update pool balance
        self.balance += ton_amount
        update_reward_pool(self.balance)
        
        # Stake 30% for yield generation
        stake_amount = ton_amount * 0.3
        # This would be sent to staking contracts in real implementation
        return ton_amount

    def calculate_bonuses(self, activity_score):
        """Calculate skill and streak bonuses"""
        # Placeholder - real implementation would use game-specific metrics
        return activity_score * 0.01