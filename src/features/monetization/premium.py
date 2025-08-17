# src/features/monetization/premium.py
MEMBERSHIP_TIERS = {
    'BASIC': {
        'price_ton': 0,
        'benefits': ['standard_earnings']
    },
    'PREMIUM': {
        'price_ton': 5,
        'benefits': [
            '1.5x_earnings',
            'extra_questions',
            'daily_reset_booster'
        ]
    },
    'ULTIMATE': {
        'price_ton': 10,
        'benefits': [
            '2x_earnings',
            'unlimited_questions',
            'priority_support',
            'free_resets'
        ]
    }
}

def upgrade_user(user_id: int, tier: str) -> bool:
    if tier not in MEMBERSHIP_TIERS:
        return False
    
    # Process payment
    price = MEMBERSHIP_TIERS[tier]['price_ton']
    if price > 0:
        # Process TON payment
        if not process_ton_payment(user_id, price):
            return False
    
    # Update user tier
    db.update_membership(user_id, tier)
    return True