from datetime import datetime
from src.database.mongo import db
from src.utils.logger import logger

class ReferralSystem:
    def __init__(self):
        self.referral_rewards = {
            3: {'ton': 0.01, 'stars': 50},
            10: {'ton': 0.03, 'stars': 150},
            50: {'ton': 0.15, 'stars': 500},
            100: {'ton': 0.30, 'stars': 1000}
        }

    def add_referral(self, referrer_id, referred_id):
        """Track a new referral relationship"""
        referral_data = {
            'referrer_id': referrer_id,
            'referred_id': referred_id,
            'created_at': datetime.utcnow(),
            'status': 'pending',
            'rewarded': False
        }
        
        db.referrals.insert_one(referral_data)
        logger.info(f"New referral tracked: {referrer_id} -> {referred_id}")

    def get_user_referral_count(self, user_id):
        """Get total successful referrals for a user"""
        return db.referrals.count_documents({
            'referrer_id': user_id,
            'status': 'completed'
        })

    def update_referral_status(self, referred_id, status='completed'):
        """Update referral status when referred user completes action"""
        db.referrals.update_one(
            {'referred_id': referred_id},
            {'$set': {'status': status, 'completed_at': datetime.utcnow()}}
        )

    def check_and_reward_referrals(self, user_id):
        """Check if user has reached any referral milestones and reward them"""
        referral_count = self.get_user_referral_count(user_id)
        rewards_claimed = []
        
        for milestone, rewards in self.referral_rewards.items():
            if referral_count >= milestone:
                # Check if already rewarded for this milestone
                if not self.is_milestone_rewarded(user_id, milestone):
                    self.distribute_referral_reward(user_id, rewards)
                    rewards_claimed.append({
                        'milestone': milestone,
                        'rewards': rewards
                    })
        
        return rewards_claimed

    def distribute_referral_reward(self, user_id, rewards):
        """Distribute referral rewards to user"""
        from src.database.mongo import update_balance
        
        # Update balance
        update_balance(user_id, rewards['ton'])
        
        # Update stars balance if applicable
        if rewards.get('stars'):
            db.users.update_one(
                {'user_id': user_id},
                {'$inc': {'telegram_stars': rewards['stars']}}
            )
        
        # Mark milestone as rewarded
        db.user_milestones.insert_one({
            'user_id': user_id,
            'milestone': list(self.referral_rewards.keys())[list(self.referral_rewards.values()).index(rewards)],
            'rewarded_at': datetime.utcnow(),
            'rewards': rewards
        })

    def is_milestone_rewarded(self, user_id, milestone):
        """Check if milestone was already rewarded"""
        return bool(db.user_milestones.find_one({
            'user_id': user_id,
            'milestone': milestone
        }))

    def get_referral_stats(self, user_id):
        """Get comprehensive referral statistics for a user"""
        total_referrals = db.referrals.count_documents({'referrer_id': user_id})
        active_referrals = db.referrals.count_documents({
            'referrer_id': user_id,
            'status': 'completed'
        })
        
        # Calculate earnings (simplified - would need actual transaction tracking)
        total_earnings = 0
        for milestone, rewards in self.referral_rewards.items():
            if self.is_milestone_rewarded(user_id, milestone):
                total_earnings += rewards['stars']
        
        return {
            'total_referrals': total_referrals,
            'active_referrals': active_referrals,
            'total_earnings': total_earnings,
            'pending_earnings': self.calculate_pending_earnings(user_id)
        }

    def calculate_pending_earnings(self, user_id):
        """Calculate pending earnings from unrewarded milestones"""
        referral_count = self.get_user_referral_count(user_id)
        pending = 0
        
        for milestone, rewards in self.referral_rewards.items():
            if referral_count >= milestone and not self.is_milestone_rewarded(user_id, milestone):
                pending += rewards['stars']
        
        return pending

# Global referral system instance
referral_system = ReferralSystem()