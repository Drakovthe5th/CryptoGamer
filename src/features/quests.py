from datetime import datetime, timedelta
import random
import hashlib
import logging
import threading
import time
from config import config
from src.database.mongo import db, update_balance, get_user_data, save_quest_progress

logger = logging.getLogger(__name__)

class ReferralSystem:
    """Mock ReferralSystem class to avoid import issues"""
    def __init__(self):
        pass

class QuestSystem:
    def __init__(self):
        self.quest_templates = getattr(config, 'QUEST_TEMPLATES', [
            {
                'type': 'general',
                'difficulty': 1,
                'tasks': ['complete_any_3_actions'],
                'reward': 0.05
            },
            {
                'type': 'gaming',
                'difficulty': 2,
                'tasks': ['win_3_games'],
                'reward': 0.10
            },
            {
                'type': 'social',
                'difficulty': 2,
                'tasks': ['refer_2_friends'],
                'reward': 0.15
            },
            {
                'type': 'exploration',
                'difficulty': 1,
                'tasks': ['play_2_different_games'],
                'reward': 0.08
            }
        ])
        self.daily_refresh_time = getattr(config, 'QUEST_REFRESH_HOUR', 3)
        self.referral_system = ReferralSystem()

    def generate_dynamic_quest(self, user_id, ip_address=None):
        """Create personalized quest for user"""
        user_data = get_user_data(user_id)
        if not user_data:
            user_data = {'level': 1, 'completed_quests': []}
        
        user_level = user_data.get('level', 1)
        last_quests = user_data.get('completed_quests', [])
        
        difficulty = max(1, min(5, user_level // 10))
        
        # Select quest type based on user preferences and country
        preferred_types = user_data.get('preferred_quests', self.get_default_preferences(user_id, ip_address))
        available_types = [
            t for t in set([q['type'] for q in self.quest_templates]) 
            if t in preferred_types
        ]
        
        if not available_types:
            available_types = ['general']
            
        quest_type = random.choice(available_types)
        
        # Get template
        valid_templates = [
            t for t in self.quest_templates 
            if t['type'] == quest_type and t['difficulty'] <= difficulty
        ]
        
        if not valid_templates:
            # Fallback to any template of same type
            valid_templates = [
                t for t in self.quest_templates 
                if t['type'] == quest_type
            ]
            
        if not valid_templates:
            # Emergency fallback
            valid_templates = [{
                'type': 'general',
                'difficulty': 1,
                'tasks': ['complete_any_3_actions'],
                'reward': 0.05
            }]
        
        template = random.choice(valid_templates)
        
        # Customize parameters
        quest = template.copy()
        reward_factor = 1 + (difficulty * 0.2)
        
        # Dynamic parameters
        if quest['type'] == "gaming":
            win_rate = user_data.get('win_rate', 0.5)
            required_wins = max(1, min(5, int(3 * (1 + win_rate))))
            quest['tasks'] = [f"win_{required_wins}_games"]
            quest['reward'] = round(0.15 * reward_factor * (1 + win_rate), 4)
        
        elif quest['type'] == "social":
            friend_count = user_data.get('friend_count', 1)
            required_refs = max(1, min(3, int(5 / max(1, friend_count))))
            quest['tasks'] = [f"refer_{required_refs}_friends"]
            quest['reward'] = round(0.2 * reward_factor * (min(friend_count, 10)/10), 4)
        
        elif quest['type'] == "exploration":
            played_games = set(user_data.get('played_games', []))
            available_games = getattr(config, 'AVAILABLE_GAME_TYPES', {'clicker', 'spin', 'trivia', 'trex', 'edge_surf'})
            
            if difficulty > 3 and played_games:
                # Find unplayed games
                new_games = available_games - played_games
                if new_games:
                    quest['tasks'] = [f"play_{min(2, len(new_games))}_new_games"]
                else:
                    quest['tasks'] = ["play_2_different_games"]
            else:
                quest['tasks'] = ["play_3_different_games"]
                
            quest['reward'] = round(0.1 * reward_factor, 4)
        
        # Add time limit for challenging quests
        if difficulty > 2:
            quest['time_limit_hours'] = difficulty * 2
        
        # Generate unique ID and ensure not a repeat
        quest_id = self.generate_quest_id(quest, user_id)
        attempts = 0
        while quest_id in last_quests and attempts < 5:
            quest = self.adjust_quest_difficulty(quest, difficulty)
            quest_id = self.generate_quest_id(quest, user_id)
            attempts += 1
            
        quest['id'] = quest_id
        quest['created_at'] = datetime.utcnow().isoformat()
        quest['expires_at'] = (
            datetime.utcnow() + timedelta(hours=quest.get('time_limit_hours', 48))
        ).isoformat() if 'time_limit_hours' in quest else None
        
        return quest

    def get_default_preferences(self, user_id, ip_address):
        """Get default quest preferences based on user country"""
        return ['general', 'gaming', 'social', 'exploration']

    def adjust_quest_difficulty(self, quest, difficulty):
        """Adjust quest parameters to vary difficulty"""
        new_quest = quest.copy()
        
        if quest['type'] == "gaming":
            current_wins = int(quest['tasks'][0].split('_')[1])
            new_wins = max(1, current_wins + random.choice([-1, 1]))
            new_quest['tasks'] = [f"win_{new_wins}_games"]
            new_quest['reward'] = round(quest['reward'] * (new_wins / current_wins), 4)
        
        elif quest['type'] == "social":
            current_refs = int(quest['tasks'][0].split('_')[1])
            new_refs = max(1, current_refs + random.choice([-1, 0, 1]))
            new_quest['tasks'] = [f"refer_{new_refs}_friends"]
            new_quest['reward'] = round(quest['reward'] * (new_refs / current_refs), 4)
        
        return new_quest

    def generate_daily_quests(self, user_id, ip_address=None):
        """Generate daily quest set for user"""
        quests = []
        daily_quest_count = getattr(config, 'DAILY_QUEST_COUNT', 3)
        for _ in range(daily_quest_count):
            quest = self.generate_dynamic_quest(user_id, ip_address)
            quests.append(quest)
        return quests

    def check_quest_completion(self, user_id, quest_id, evidence=None):
        """Check if a quest has been completed and award rewards"""
        user_data = get_user_data(user_id)
        if not user_data:
            raise ValueError("User not found")
        
        # Find quest in active_quests
        quest = next((q for q in user_data.get("active_quests", []) if q['id'] == quest_id), None)
        if not quest:
            raise ValueError("Quest not found")
        
        # Check expiration
        if 'expires_at' in quest and datetime.fromisoformat(quest['expires_at']) < datetime.utcnow():
            return False, "Quest expired"
        
        # Verify completion
        is_valid, message = self.verify_completion(quest, evidence)
        if not is_valid:
            return False, message
        
        # Update user document
        reward = quest['reward']
        xp_earned = int(reward * 100)
        new_level = self.check_level_up(user_data.get('xp', 0) + xp_earned)
        
        update_data = {
            "$inc": {"balance": reward, "xp": xp_earned},
            "$addToSet": {"completed_quests": quest_id},
            "$pull": {"active_quests": {"id": quest_id}}
        }
        
        if new_level > user_data.get("level", 1):
            update_data["$set"] = {"level": new_level}
        
        db.users.update_one(
            {"user_id": user_id},
            update_data
        )

        # Add Stars reward for certain quest types
        if quest.get('reward_stars', 0) > 0:
            stars_reward = quest['reward_stars']
            db.users.update_one(
                {"user_id": user_id},
                {"$inc": {"telegram_stars": stars_reward}}
            )
        
        return True, {
            'reward': reward,
            'reward_stars': quest.get('reward_stars', 0),
            'xp_earned': xp_earned,
            'new_level': new_level if new_level > user_data.get("level", 1) else None
        }

    def verify_completion(self, quest, evidence):
        """Verify quest completion with anti-cheat measures"""
        task = quest['tasks'][0]
        
        if "win_" in task:
            return self.validate_game_wins(quest, evidence)
        elif "refer_" in task:
            return self.validate_referrals(quest, evidence)
        elif "play_" in task:
            return self.validate_game_plays(quest, evidence)
        elif "complete_" in task:
            return self.validate_generic_completion(evidence)
        
        # New verification methods
        elif "connect_telegram_wallet" in task:
            return self.validate_wallet_connection(evidence)
        elif "follow_instagram" in task:
            return self.validate_social_follow('instagram', evidence)
        elif "follow_facebook" in task:
            return self.validate_social_follow('facebook', evidence)
        elif "follow_twitter" in task:
            return self.validate_social_follow('twitter', evidence)
        elif "join_telegram_channel" in task:
            return self.validate_channel_join(evidence)
        elif "post_twitter" in task:
            return self.validate_social_post('twitter', evidence)
        elif "retweet_post" in task:
            return self.validate_retweet(evidence)
        elif "post_tiktok" in task:
            return self.validate_social_post('tiktok', evidence)
        elif "signup_binance" in task:
            return self.validate_binance_signup(evidence)
        elif "invite_binance_trader" in task:
            return self.validate_binance_referral(evidence)
        elif "reach_level_3" in task:
            return self.validate_level(3, evidence)
        elif "post_retweet_earn_repeat" in task:
            return self.validate_social_engagement(evidence)
        elif "earn_10000_ads" in task:
            return self.validate_ad_earnings(10000, evidence)
        elif "earn_100000_ads" in task:
            return self.validate_ad_earnings(100000, evidence)
        elif "watch_ads" in task:
            return self.validate_ad_watch(evidence)
        elif "boost_channel" in task:
            return self.validate_boost('channel', evidence)
        elif "boost_earnings" in task:
            return self.validate_boost('earnings', evidence)
        
        return False, "Invalid quest type"

    def validate_game_wins(self, quest, evidence):
        """Validate game wins with anti-cheat"""
        required_wins = int(quest['tasks'][0].split('_')[1])
        
        # Evidence should be list of game session IDs
        if not evidence or len(evidence) < required_wins:
            return False, "Insufficient wins"
        
        # For now, assume validation passes - in production, integrate with game service
        # This avoids circular imports
        return True, "Validated"

    def validate_referrals(self, quest, evidence):
        """Validate referrals with anti-fraud"""
        required_refs = int(quest['tasks'][0].split('_')[1])
        
        # Evidence should be list of referral user IDs
        if not evidence or len(evidence) < required_refs:
            return False, "Insufficient referrals"
        
        # Verify referrals with database
        valid_refs = []
        for ref_id in evidence:
            ref_data = get_user_data(ref_id)
            if ref_data and ref_data.get('referred_by') == evidence.get('user_id'):
                valid_refs.append(ref_id)
        
        if len(valid_refs) >= required_refs:
            return True, "Validated"
        
        return False, "Invalid referrals"

    def validate_game_plays(self, quest, evidence):
        """Validate game plays"""
        if evidence and evidence.get('games_played', 0) >= int(quest['tasks'][0].split('_')[1]):
            return True, "Validated"
        return False, "Insufficient games played"

    def validate_generic_completion(self, evidence):
        """Validate generic completion"""
        if evidence and evidence.get('completed', False):
            return True, "Validated"
        return False, "Not completed"

    def validate_wallet_connection(self, evidence):
        """Validate Telegram wallet connection"""
        if not evidence:
            return False, "No evidence provided"
            
        user_data = get_user_data(evidence.get('user_id'))
        if user_data and user_data.get('wallet_address'):
            return True, "Validated"
        return False, "Wallet not connected"

    def validate_social_follow(self, platform, evidence):
        """Validate social media follow"""
        if evidence and evidence.get('verification_code') == f"follow_{platform}_{evidence.get('user_id')}":
            return True, "Validated"
        return False, "Follow not verified"

    def validate_channel_join(self, evidence):
        """Validate Telegram channel join"""
        if evidence and evidence.get('verification_code') == f"channel_join_{evidence.get('user_id')}":
            return True, "Validated"
        return False, "Channel membership not verified"

    def validate_social_post(self, platform, evidence):
        """Validate social media post"""
        if evidence and evidence.get('post_url') and f"{platform}.com" in evidence.get('post_url', ''):
            return True, "Validated"
        return False, "Post not verified"

    def validate_retweet(self, evidence):
        """Validate retweet"""
        if evidence and evidence.get('retweet_url') and "twitter.com" in evidence.get('retweet_url', ''):
            return True, "Validated"
        return False, "Retweet not verified"

    def validate_binance_signup(self, evidence):
        """Validate Binance signup using referral"""
        if evidence and evidence.get('binance_id') and evidence.get('used_referral') == 'CRYPTOGAMER':
            return True, "Validated"
        return False, "Binance signup not verified"

    def validate_binance_referral(self, evidence):
        """Validate Binance referral"""
        if evidence and evidence.get('referral_count', 0) >= 1:
            return True, "Validated"
        return False, "Binance referral not verified"

    def validate_level(self, required_level, evidence):
        """Validate user level"""
        if not evidence:
            return False, "No evidence provided"
            
        user_data = get_user_data(evidence.get('user_id'))
        if user_data and user_data.get('level', 0) >= required_level:
            return True, "Validated"
        return False, f"Level {required_level} not reached"

    def validate_social_engagement(self, evidence):
        """Validate social engagement cycle"""
        if (evidence and evidence.get('posted') and evidence.get('retweeted') and 
            evidence.get('earned') and evidence.get('repeated')):
            return True, "Validated"
        return False, "Social engagement not completed"

    def validate_ad_earnings(self, required_earnings, evidence):
        """Validate ad earnings"""
        if not evidence:
            return False, "No evidence provided"
            
        user_data = get_user_data(evidence.get('user_id'))
        if user_data and user_data.get('ad_earnings', 0) >= required_earnings:
            return True, "Validated"
        return False, f"Ad earnings of {required_earnings} not reached"

    def validate_ad_watch(self, evidence):
        """Validate ad watch"""
        if evidence and evidence.get('ads_watched', 0) >= 5:
            return True, "Validated"
        return False, "Not enough ads watched"

    def validate_boost(self, boost_type, evidence):
        """Validate boost purchase"""
        if not evidence:
            return False, "No evidence provided"
            
        user_data = get_user_data(evidence.get('user_id'))
        if user_data and boost_type in user_data.get('active_boosts', []):
            return True, "Validated"
        return False, f"{boost_type} boost not active"

    def generate_quest_id(self, quest, user_id):
        """Create unique quest ID"""
        base_str = f"{user_id}-{quest['type']}-{quest['tasks'][0]}"
        return hashlib.sha256(base_str.encode()).hexdigest()[:16]

    def check_level_up(self, total_xp):
        """Calculate level based on XP"""
        level_xp_base = getattr(config, 'LEVEL_XP_BASE', 1000)
        level_xp_multiplier = getattr(config, 'LEVEL_XP_MULTIPLIER', 1.5)
        max_level = getattr(config, 'MAX_LEVEL', 50)
        
        level = 1
        xp_required = level_xp_base
        
        while total_xp >= xp_required and level < max_level:
            level += 1
            xp_required *= level_xp_multiplier
            
        return min(level, max_level)
    
    def get_active_quests(self, user_id):
        """Get active quests for user"""
        user_data = get_user_data(user_id)
        if not user_data:
            return []
        return user_data.get('active_quests', [])

    def get_daily_quests(self, user_id):
        """Get today's generated quests for user"""
        user_data = get_user_data(user_id)
        if not user_data:
            return []
        return user_data.get('daily_quests', [])
        
    def update_quest_progress(self, user_id, quest_id, progress):
        """Update progress for a specific quest"""
        user_data = get_user_data(user_id)
        if not user_data:
            return False
            
        # Find the quest and update progress
        active_quests = user_data.get('active_quests', [])
        for quest in active_quests:
            if quest['id'] == quest_id:
                quest['progress'] = progress
                if progress >= 100:
                    quest['completed'] = True
                save_quest_progress(user_id, user_data)
                return True
                
        return False

    def generate_affiliate_quests(self, user_id):
        """Generate affiliate-related quests"""
        user_data = get_user_data(user_id)
        if not user_data:
            return []
            
        referral_count = user_data.get('referral_count', 0)
        completed_affiliate_quests = user_data.get('completed_affiliate_quests', [])
        
        milestones = [
            (3, 0.01, 50),
            (10, 0.03, 150),
            (50, 0.15, 500),
            (100, 0.30, 1000)
        ]

        affiliate_quests = []
        for target, reward, stars in milestones:
            quest_id = f"affiliate_ref_{target}"
            
            # Skip if already completed
            if quest_id in completed_affiliate_quests:
                continue
                
            affiliate_quests.append({
                'id': quest_id,
                'type': 'affiliate',
                'title': f'Refer {target} Friends',
                'description': f'Invite {target} friends to join CryptoGamer',
                'tasks': [f'refer_{target}_friends'],
                'reward': reward,
                'reward_stars': stars,
                'target': target,
                'current': min(referral_count, target),
                'progress': (min(referral_count, target) / target) * 100
            })

        return affiliate_quests

def refresh_daily_quests():
    """Background task to refresh daily quests"""
    while True:
        try:
            now = datetime.utcnow()
            # Calculate next refresh time (3 AM UTC)
            next_refresh = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if now.hour >= 3:
                next_refresh += timedelta(days=1)
            
            # Calculate sleep duration
            sleep_seconds = (next_refresh - now).total_seconds()
            logger.info(f"Quest refresh scheduled in {sleep_seconds/3600:.2f} hours")
            time.sleep(sleep_seconds)
            
            # Refresh quests for all users in batches
            logger.info("Refreshing daily quests for all users")
            quest_system = QuestSystem()
            batch_size = 100
            skip = 0
            
            while True:
                users_batch = list(db.users.find({}, {"user_id": 1}).skip(skip).limit(batch_size))
                if not users_batch:
                    break
                
                for user in users_batch:
                    user_id = user["user_id"]
                    try:
                        daily_quests = quest_system.generate_daily_quests(user_id)
                        db.users.update_one(
                            {"user_id": user_id},
                            {"$set": {"daily_quests": daily_quests}}
                        )
                    except Exception as e:
                        logger.error(f"Error refreshing quests for {user_id}: {str(e)}")
                
                skip += batch_size
            
            logger.info("Daily quest refresh completed")
        except Exception as e:
            logger.error(f"Error in quest scheduler: {str(e)}")
            time.sleep(3600)  # Sleep 1 hour on error

def start_quest_scheduler():
    """Start background thread to refresh daily quests"""
    scheduler_thread = threading.Thread(target=refresh_daily_quests, daemon=True)
    scheduler_thread.start()
    logger.info("Quest scheduler started")
    return scheduler_thread

def claim_daily_bonus(user_id):
    """Claim daily bonus for a user"""
    user_data = get_user_data(user_id)
    if not user_data:
        return False, 0.0

    last_claimed = user_data.get('last_bonus_claimed')
    today = datetime.utcnow().date()

    if last_claimed and last_claimed.date() == today:
        return False, user_data.get('balance', 0.0)

    bonus_amount = 0.05  # TON
    new_balance = update_balance(user_id, bonus_amount)

    db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            'last_bonus_claimed': datetime.utcnow(),
            'daily_bonus_claimed': True
        }}
    )

    return True, new_balance

def record_click(user_id):
    """Record a click and update balance"""
    user_data = get_user_data(user_id)
    if not user_data:
        return 0, 0.0

    today = datetime.utcnow().date()
    last_click_date = user_data.get('last_click_date')
    clicks_today = user_data.get('clicks_today', 0)

    if not last_click_date or last_click_date.date() != today:
        clicks_today = 0

    if clicks_today >= 100:
        return clicks_today, user_data.get('balance', 0.0)

    click_reward = 0.0001  # TON
    new_balance = update_balance(user_id, click_reward)

    db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            'clicks_today': clicks_today + 1,
            'last_click_date': datetime.utcnow()
        }}
    )

    return clicks_today + 1, new_balance

# Global quest system instance
quest_system = QuestSystem()

# Module-level functions for easier importing
def get_active_quests(user_id):
    return quest_system.get_active_quests(user_id)

def get_daily_quests(user_id):
    return quest_system.get_daily_quests(user_id)

def update_quest_progress(user_id, quest_id, progress):
    return quest_system.update_quest_progress(user_id, quest_id, progress)

def check_quest_completion(user_id, quest_id, evidence=None):
    return quest_system.check_quest_completion(user_id, quest_id, evidence)

def generate_dynamic_quest(user_id, ip_address=None):
    return quest_system.generate_dynamic_quest(user_id, ip_address)

def generate_affiliate_quests(user_id):
    return quest_system.generate_affiliate_quests(user_id)

complete_quest = check_quest_completion