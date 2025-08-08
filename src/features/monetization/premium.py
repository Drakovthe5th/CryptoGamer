class PremiumSubscriptions:
    def __init__(self):
        self.tiers = {
            'basic': 4.99,
            'pro': 9.99,
            'vip': 19.99
        }
    
    def process_subscription(self, user_id, tier):
        amount = self.tiers.get(tier, 0)
        if amount > 0:
            # Grant premium benefits
            activate_premium_features(user_id, tier)
            return amount
        return 0