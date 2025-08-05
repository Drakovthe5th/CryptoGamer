import os
from google.cloud import firestore
from datetime import datetime

class User:
    def __init__(self, data):
        self.user_id = data.get('user_id')
        self.username = data.get('username', '')
        self.balance = data.get('balance', 0.0)
        self.points = data.get('points', 0)
        self.last_played = data.get('last_played', {})
        self.referral_count = data.get('referral_count', 0)
        self.faucet_claimed = data.get('faucet_claimed')
        self.withdrawal_methods = data.get('withdrawal_methods', {})
        self.payment_methods = data.get('payment_methods', {})
        self.completed_quests = data.get('completed_quests', {})
        self.created_at = data.get('created_at', datetime.now())

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'username': self.username,
            'balance': self.balance,
            'points': self.points,
            'last_played': self.last_played,
            'referral_count': self.referral_count,
            'faucet_claimed': self.faucet_claimed,
            'withdrawal_methods': self.withdrawal_methods,
            'payment_methods': self.payment_methods,
            'completed_quests': self.completed_quests,
            'created_at': self.created_at
        }

class Quest:
    def __init__(self, data):
        self.title = data.get('title', '')
        self.description = data.get('description', '')
        self.reward_ton = data.get('reward_ton', 0.0)
        self.reward_points = data.get('reward_points', 0)
        self.active = data.get('active', True)
        self.completions = data.get('completions', 0)
        self.created_at = data.get('created_at', datetime.now())

    def to_dict(self):
        return {
            'title': self.title,
            'description': self.description,
            'reward_ton': self.reward_ton,
            'reward_points': self.reward_points,
            'active': self.active,
            'completions': self.completions,
            'created_at': self.created_at
        }