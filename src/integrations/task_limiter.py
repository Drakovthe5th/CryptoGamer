from datetime import datetime, timedelta
from src.database.firebase import db
from config import config

class TaskLimiter:
    def __init__(self):
        self.free_daily_limit = config.FREE_DAILY_EARN_LIMIT  # 0.5 TON
        self.task_rewards = config.REWARDS
        self.ad_rewards = config.REWARDS["ad_view"]
        
    def can_perform_task(self, user_id: str, task_type: str) -> bool:
        """Check if user can perform a task"""
        user_ref = db.collection("users").document(str(user_id))
        user_data = user_ref.get().to_dict()
        
        # Premium users have no limits
        if user_data.get("account_type") == "premium":
            return True
        
        # Reset daily earnings if new day
        today = datetime.now().strftime("%Y-%m-%d")
        if user_data.get("last_activity_date") != today:
            user_ref.update({
                "last_activity_date": today,
                "today_earned": 0.0
            })
            return True
        
        # Check if reached daily limit
        today_earned = user_data.get("today_earned", 0.0)
        task_reward = self.task_rewards.get(task_type, 0.001)
        
        return today_earned + task_reward <= self.free_daily_limit
    
    def record_task_completion(self, user_id: str, task_type: str):
        """Record task completion and update earnings"""
        user_ref = db.collection("users").document(str(user_id))
        task_reward = self.task_rewards.get(task_type, 0.001)
        
        user_ref.update({
            "today_earned": user_ref.get().to_dict().get("today_earned", 0.0) + task_reward,
            "total_earned": user_ref.get().to_dict().get("total_earned", 0.0) + task_reward
        })
    
    def can_watch_ad(self, user_id: str) -> bool:
        """Check if user can watch an ad"""
        return self.can_perform_task(user_id, "ad_view")
    
    def record_ad_watch(self, user_id: str):
        """Record ad watch and update earnings"""
        self.record_task_completion(user_id, "ad_view")

# Global limiter instance
task_limiter = TaskLimiter()