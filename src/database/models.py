import os
from pymongo import MongoClient
from datetime import datetime

class User(BaseModel):
    def __init__(self, data):
        self.user_id = data.get('user_id')
        self.username = data.get('username', '')
        self.game_coins = data.get('game_coins', 0)
        self.last_played = data.get('last_played', {})
        self.referral_count = data.get('referral_count', 0)
        self.faucet_claimed = data.get('faucet_claimed')
        self.wallet_address = data.get('wallet_address', '')
        self.daily_coins_earned = data.get('daily_coins_earned', 0)
        self.daily_resets = data.get('daily_resets', {})
        self.inventory = data.get('inventory', [])
        self.membership_tier = data.get('membership_tier', 'BASIC')
        self.created_at = data.get('created_at', datetime.now())
        wallet_address = CharField(null=True)
        game_coins = IntegerField(default=0)
        daily_gc_earned = IntegerField(default=0)
        daily_resets = JSONField(default={})  # {game_type: reset_count}
        membership_tier = CharField(default='BASIC')
        inventory = JSONField(default=[])  # List of purchased items

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'username': self.username,
            'game_coins': self.game_coins,
            'last_played': self.last_played,
            'referral_count': self.referral_count,
            'faucet_claimed': self.faucet_claimed,
            'wallet_address': self.wallet_address,
            'daily_coins_earned': self.daily_coins_earned,
            'daily_resets': self.daily_resets,
            'inventory': self.inventory,
            'membership_tier': self.membership_tier,
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