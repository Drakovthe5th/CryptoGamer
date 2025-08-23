from src.database.mongo import update_game_coins, record_activity
from config import config

def distribute_rewards(user_id, activity_type, score=None):
    rewards_config = {
        'click': 50,
        'trivia_correct': 100 + (50 * (score/100)) if score else 100,
        'ad_view': 250,
        'referral': 1000,
        'daily_streak': 500
    }
    
    coins = rewards_config.get(activity_type, 0)
    if coins > 0:
        new_balance = update_game_coins(user_id, coins)
        record_activity(user_id, activity_type, coins)
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

# Add sabotage reward calculation
def calculate_sabotage_reward(game_data):
    """Calculate rewards for sabotage game based on outcome"""
    if game_data.get('stalemate'):
        # All players get equal share
        total_reward = 8000
        player_count = len(game_data.get('players', []))
        return {player_id: total_reward // player_count for player_id in game_data['players']}
    elif game_data.get('saboteurs_win'):
        # Saboteurs and traitors win
        saboteurs = [p for p in game_data['players'] if game_data['players'][p]['role'] in ['saboteur', 'traitor']]
        reward_per_player = 8000 // len(saboteurs) if saboteurs else 0
        return {player_id: reward_per_player for player_id in saboteurs}
    else:
        # Miners win
        miners = [p for p in game_data['players'] if game_data['players'][p]['role'] == 'miner' and game_data['players'][p]['is_alive']]
        reward_per_player = 8000 // len(miners) if miners else 0
        return {player_id: reward_per_player for player_id in miners}