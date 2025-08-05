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