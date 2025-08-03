from google.cloud.firestore_v1 import SERVER_TIMESTAMP

USER_SCHEMA = {
    'user_id': int,
    'username': str,
    'balance': float,
    'points': int,
    'last_played': dict,  # {game_type: timestamp}
    'referral_count': int,
    'faucet_claimed': SERVER_TIMESTAMP,
    'withdrawal_methods': dict,  # {method: details}
    'completed_quests': dict,  # {quest_id: timestamp}
    'created_at': SERVER_TIMESTAMP
}

QUEST_SCHEMA = {
    'title': str,
    'description': str,
    'reward_xno': float,
    'reward_points': int,
    'active': bool,
    'completions': int,
    'created_at': SERVER_TIMESTAMP
}

TRANSACTION_SCHEMA = {
    'user_id': int,
    'type': str,  # 'deposit', 'withdrawal', 'game_reward'
    'amount': float,
    'method': str,  # 'nano', 'mpesa', 'paypal'
    'status': str,  # 'pending', 'success', 'failed'
    'timestamp': SERVER_TIMESTAMP,
    'details': dict  # Additional transaction details
}