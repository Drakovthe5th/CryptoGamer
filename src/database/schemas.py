import os
from google.cloud.firestore_v1 import SERVER_TIMESTAMP

USER_SCHEMA = {
    'user_id': int,
    'username': str,
    'balance': float,
    'points': int,
    'last_played': dict,
    'referral_count': int,
    'faucet_claimed': SERVER_TIMESTAMP,
    'withdrawal_methods': dict,
    'payment_methods': dict,
    'completed_quests': dict,
    'created_at': SERVER_TIMESTAMP
}

QUEST_SCHEMA = {
    'title': str,
    'description': str,
    'reward_ton': float,
    'reward_points': int,
    'active': bool,
    'completions': int,
    'created_at': SERVER_TIMESTAMP
}

TRANSACTION_SCHEMA = {
    'user_id': int,
    'type': str,
    'amount': float,
    'method': str,
    'status': str,
    'timestamp': SERVER_TIMESTAMP,
    'details': dict
}

STARS_TRANSACTION_SCHEMA = {
    'transaction_id': str,
    'user_id': int,
    'amount': int,
    'currency': str,
    'product_id': str,
    'status': str,
    'provider_data': dict,
    'created_at': SERVER_TIMESTAMP,
    'completed_at': SERVER_TIMESTAMP
}

PAYMENT_METHOD_SCHEMA = {
    'user_id': int,
    'method_type': str,
    'is_default': bool,
    'details': dict,
    'created_at': SERVER_TIMESTAMP
}

INVOICE_SCHEMA = {
    'user_id': int,
    'product_id': str,
    'amount': int,
    'currency': str,
    'status': str,
    'telegram_invoice_data': dict,
    'created_at': SERVER_TIMESTAMP,
    'expires_at': SERVER_TIMESTAMP
}

SABOTAGE_SESSION_SCHEMA = {
    'game_id': str,
    'chat_id': str,
    'state': str,
    'vault_gold': int,
    'saboteurs_stash': int,
    'start_time': SERVER_TIMESTAMP,
    'end_time': SERVER_TIMESTAMP,
    'players': dict,
    'winners': list,
    'gc_rewards': dict,
    'created_at': SERVER_TIMESTAMP
}

SABOTAGE_PLAYER_SCHEMA = {
    'user_id': int,
    'game_id': str,
    'role': str,
    'is_alive': bool,
    'gold_mined': int,
    'gold_stolen': int,
    'joined_at': SERVER_TIMESTAMP
}