import time
from datetime import datetime
from config import config
from src.database.firebase import db, update_balance, record_ad_engagement
from src.features.mining.reward_pool import RewardPool
from src.utils.user_helpers import is_premium_user, get_ad_streak, get_user_country, get_device_type
import logging

logger = logging.getLogger(__name__)

class AdMonetization:
    def __init__(self):
        self.ad_networks = config.AD_NETWORKS
        self.reward_pool = RewardPool()
        self.last_ad_times = {}
        self.ad_cooldown = config.AD_COOLDOWN  # seconds between ads

    def record_ad_view(self, user_id, ad_network, user_agent=None, ip_address=None):
        """Record ad view and distribute rewards with anti-cheat checks"""
        # Validate ad network
        if ad_network not in self.ad_networks:
            raise ValueError(f"Invalid ad network: {ad_network}")
        
        # Anti-cheat: Check ad cooldown
        current_time = time.time()
        last_time = self.last_ad_times.get(user_id, 0)
        if current_time - last_time < self.ad_cooldown:
            raise PermissionError("Ad cooldown period active")
        
        # Get dynamic reward based on network and user status
        reward = self.get_dynamic_reward(user_id, ad_network, user_agent, ip_address)
        
        # Update user balance
        new_balance = update_balance(user_id, reward)
        
        # Record engagement
        record_ad_engagement(user_id, ad_network, reward, user_agent, ip_address)
        
        # Update last ad time
        self.last_ad_times[user_id] = current_time
        
        # Add revenue to reward pool
        self.reward_pool.replenish_pool(self.ad_networks[ad_network])
        
        return reward, new_balance

    def get_dynamic_reward(self, user_id, ad_network, user_agent=None, ip_address=None):
        """Calculate reward based on multiple factors"""
        base_reward = self.ad_networks[ad_network]
        
        # Apply multipliers
        multiplier = 1.0
        
        # 1. Premium user bonus
        if is_premium_user(user_id):
            multiplier *= config.PREMIUM_AD_BONUS
        
        # 2. Engagement streak bonus
        streak = get_ad_streak(user_id)
        if streak >= 7:
            multiplier *= config.AD_STREAK_BONUS_HIGH
        elif streak >= 3:
            multiplier *= config.AD_STREAK_BONUS_MEDIUM
        
        # 3. Time-based bonuses
        now = datetime.now()
        if now.hour in config.PEAK_HOURS:
            multiplier *= config.PEAK_HOUR_BONUS
        
        if now.weekday() in [5, 6]:  # Weekend
            multiplier *= config.WEEKEND_BONUS
        
        # 4. Geographic bonus
        country = get_user_country(user_id, ip_address)
        if country in config.HIGH_VALUE_REGIONS:
            multiplier *= config.REGIONAL_BONUS
        
        # 5. Device type bonus
        device = get_device_type(user_agent)
        if device == "mobile":
            multiplier *= config.MOBILE_BONUS
        
        # Apply network-specific adjustments
        if ad_network == "a-ads" and device != "desktop":
            multiplier *= 0.8  # Penalize mobile for a-ads
        
        # Ensure reasonable min/max
        min_reward = base_reward * 0.5
        max_reward = base_reward * 3.0
        final_reward = base_reward * multiplier
        
        return max(min_reward, min(final_reward, max_reward))

    def get_ad_offer(self, user_id, user_agent=None, ip_address=None):
        """Return available ad offers for user"""
        offers = []
        for network, rate in self.ad_networks.items():
            offers.append({
                'network': network,
                'estimated_reward': self.get_dynamic_reward(
                    user_id, network, user_agent, ip_address
                ),
                'duration': config.AD_DURATIONS.get(network, 30),
                'cooldown': self.get_remaining_cooldown(user_id)
            })
        return sorted(offers, key=lambda x: x['estimated_reward'], reverse=True)

    def get_remaining_cooldown(self, user_id):
        """Get seconds until next ad can be viewed"""
        last_time = self.last_ad_times.get(user_id, 0)
        elapsed = time.time() - last_time
        return max(0, self.ad_cooldown - elapsed)

    def reset_cooldown(self, user_id):
        """Reset cooldown timer (for testing/admin)"""
        if user_id in self.last_ad_times:
            del self.last_ad_times[user_id]