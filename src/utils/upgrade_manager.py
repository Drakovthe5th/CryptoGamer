from src.database.firebase import db
from datetime import datetime
import time

class UpgradeManager:
    MEMBERSHIP_TIERS = {
        "BASIC": {
            "multiplier": 1.0,
            "price": 0,
            "perks": []
        },
        "PREMIUM": {
            "multiplier": 1.5,
            "price": 5000,  # in game coins
            "perks": ["extra_questions", "double_earnings"]
        },
        "ULTIMATE": {
            "multiplier": 2.0,
            "price": 15000,  # in game coins
            "perks": ["triple_earnings", "unlimited_resets"]
        }
    }
    
    def upgrade_user(self, user_id: str, tier: str):
        """Upgrade user membership"""
        if tier not in self.MEMBERSHIP_TIERS:
            return False
        
        user_ref = db.collection("users").document(str(user_id))
        user_ref.update({
            "membership_tier": tier,
            "upgraded_at": datetime.now()
        })
        return True
    
    def get_user_tier(self, user_id: str) -> str:
        """Get user membership tier"""
        user_ref = db.collection("users").document(str(user_id))
        user_data = user_ref.get().to_dict()
        return user_data.get("membership_tier", "BASIC")
    
    def get_tier_multiplier(self, user_id: str) -> float:
        """Get earning multiplier for user's tier"""
        tier = self.get_user_tier(user_id)
        return self.MEMBERSHIP_TIERS[tier]["multiplier"]
    
    def get_upgrade_options(self, user_id: str):
        """Get available upgrade options for user"""
        current_tier = self.get_user_tier(user_id)
        tiers = list(self.MEMBERSHIP_TIERS.keys())
        current_index = tiers.index(current_tier)
        
        return [
            {
                "tier": tier,
                "multiplier": self.MEMBERSHIP_TIERS[tier]["multiplier"],
                "price": self.MEMBERSHIP_TIERS[tier]["price"],
                "perks": self.MEMBERSHIP_TIERS[tier]["perks"]
            }
            for i, tier in enumerate(tiers) if i > current_index
        ]

# Global upgrade manager
upgrade_manager = UpgradeManager()