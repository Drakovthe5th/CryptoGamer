from src.database.firebase import update_balance, record_activity

def distribute_rewards(user_id, activity_type, score=None):
    """Award TON for user activities"""
    rewards_config = {
        'click': 0.001,
        'trivia_correct': 0.01 + (0.005 * (score/100)) if score else 0.01,
        'ad_view': 0.005,
        'referral': 0.05,
        'daily_streak': 0.02
    }
    
    amount = rewards_config.get(activity_type, 0)
    if amount > 0:
        new_balance = update_balance(user_id, amount)
        record_activity(user_id, activity_type, amount)
        return new_balance
    return None