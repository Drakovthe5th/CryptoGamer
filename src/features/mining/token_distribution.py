from src.database.firebase import update_balance, record_activity
from config import config

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

# Add edge-surf reward calculation
def calculate_edge_surf_reward(score, session_data):
    base = config.REWARD_RATES['edge-surf']['base']
    per_minute = config.REWARD_RATES['edge-surf']['per_minute']
    minutes = score / 60
    
    reward = base + (minutes * per_minute)
    return min(reward, config.MAX_GAME_REWARD['edge-surf'])

def calculate_clicker_reward(score, session_data):
    base = config.REWARD_RATES['clicker']['base']
    per_1000 = config.REWARD_RATES['clicker']['per_1000_points']
    reward = base + (score / 1000) * per_1000
    return min(reward, config.MAX_GAME_REWARD['clicker'])

def calculate_trex_reward(score, session_data):
    base = config.REWARD_RATES['trex-runner']['base']
    per_100_meters = config.REWARD_RATES['trex-runner']['per_100_meters']
    reward = base + (score / 100) * per_100_meters
    return min(reward, config.MAX_GAME_REWARD['trex-runner'])

def calculate_trivia_reward(score, session_data):
    base = config.REWARD_RATES['trivia']['base']
    per_correct = config.REWARD_RATES['trivia']['per_correct_answer']
    reward = base + (score * per_correct)
    return min(reward, config.MAX_GAME_REWARD['trivia'])

def calculate_spin_reward(score, session_data):
    base = config.REWARD_RATES['spin']['base']
    return min(base, config.MAX_GAME_REWARD['spin'])