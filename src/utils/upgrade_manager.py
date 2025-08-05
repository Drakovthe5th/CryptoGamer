from src.database.firebase import db
from datetime import datetime  # Add this
import time

class UpgradeManager:
    TIERS = {
        "free": {"daily_limit": 0.5, "ads_per_day": 5},
        "basic": {"daily_limit": 5.0, "ads_per_day": 20, "price": 1.0},
        "premium": {"daily_limit": float('inf'), "ads_per_day": float('inf'), "price": 5.0}
    }
    
    def upgrade_user(self, user_id: str, tier: str):
        """Upgrade user account"""
        if tier not in self.TIERS:
            return False
        
        user_ref = db.collection("users").document(str(user_id))
        user_ref.update({
            "account_tier": tier,
            "upgraded_at": datetime.now()
        })
        return True
    
    def get_user_tier(self, user_id: str) -> str:
        """Get user account tier"""
        user_ref = db.collection("users").document(str(user_id))
        user_data = user_ref.get().to_dict()
        return user_data.get("account_tier", "free")
    
    def get_upgrade_options(self):
        """Get available upgrade options"""
        return [
            {
                "tier": tier,
                "daily_limit": self.TIERS[tier]["daily_limit"],
                "ads_per_day": self.TIERS[tier]["ads_per_day"],
                "price": self.TIERS[tier].get("price", 0)
            }
            for tier in self.TIERS if tier != "free"
        ]

# Global upgrade manager
upgrade_manager = UpgradeManager()