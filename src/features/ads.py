import time
import logging
import random
from datetime import datetime
from config import config
from src.database.mongo import db, update_balance, track_ad_reward
from src.utils.user_helpers import is_premium_user, get_ad_streak, get_user_country, get_device_type
from src.integrations.tonclient import telegram_client

logger = logging.getLogger(__name__)



class TelegramSponsoredMessages:
    def __init__(self):
        self.cache = {}
        self.cache_duration = 300  # 5 minutes as per Telegram docs
        
    async def get_sponsored_messages(self, peer):
        """Fetch sponsored messages from Telegram API"""
        current_time = time.time()
        cached = self.cache.get(peer)
        
        if cached and current_time - cached['timestamp'] < self.cache_duration:
            return cached['data']
            
        try:
            # Use Telegram client to get sponsored messages
            result = await telegram_client(
                functions.messages.GetSponsoredMessagesRequest(peer=peer)
            )
            
            # Cache the result
            self.cache[peer] = {
                'data': result,
                'timestamp': current_time
            }
            
            return result
        except Exception as e:
            logger.error(f"Failed to get sponsored messages: {e}")
            return None
            
    async def view_sponsored_message(self, peer, random_id):
        """Record a sponsored message view"""
        try:
            await telegram_client(
                functions.messages.ViewSponsoredMessageRequest(
                    peer=peer,
                    random_id=random_id
                )
            )
            return True
        except Exception as e:
            logger.error(f"Failed to record sponsored message view: {e}")
            return False
            
    async def click_sponsored_message(self, peer, random_id, media=False, fullscreen=False):
        """Record a sponsored message click"""
        try:
            await telegram_client(
                functions.messages.ClickSponsoredMessageRequest(
                    peer=peer,
                    random_id=random_id,
                    media=media,
                    fullscreen=fullscreen
                )
            )
            return True
        except Exception as e:
            logger.error(f"Failed to record sponsored message click: {e}")
            return False
class AdMonetization:
    def __init__(self):
        self.ad_networks = config.AD_NETWORKS
        self.last_ad_times = {}
        self.ad_cooldown = config.AD_COOLDOWN  # seconds between ads
        self.ad_durations = config.AD_DURATIONS
        self.telegram_ads = TelegramSponsoredMessages()

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
                'duration': self.ad_durations.get(network, 30),
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

    async def get_telegram_ads(self, user_id):
        """Get Telegram sponsored messages for user"""
        try:
            # Get user's peer info
            user_peer = await telegram_client.get_peer(user_id)
            ads = await self.telegram_ads.get_sponsored_messages(user_peer)
            return ads
        except Exception as e:
            logger.error(f"Failed to get Telegram ads: {e}")
            return None

    async def record_telegram_ad_view(self, user_id, random_id):
        """Record a Telegram ad view and reward user with gc"""
        try:
            user_peer = await telegram_client.get_peer(user_id)
            success = await self.telegram_ads.view_sponsored_message(user_peer, random_id)
            
            if success:
                # Reward user with game coins (not ad revenue)
                base_reward = config.REWARDS['telegram_ad_view']
                new_balance = db.update_balance(user_id, base_reward)
                
                return {
                    'success': True,
                    'reward': base_reward,
                    'new_balance': new_balance
                }
            return {'success': False, 'error': 'Failed to record view'}
        except Exception as e:
            logger.error(f"Failed to record Telegram ad view: {e}")
            return {'success': False, 'error': str(e)}

class AdManager:
    def __init__(self):
        self.networks = {
            'monetag': {
                'rewarded_interstitial': self._monetag_interstitial,
                'rewarded_popup': self._monetag_popup,
                'banner': self._monetag_banner
            },
            'a-ads': {
                'banner': self._aads_banner
            },
            'coinzilla': {
                'banner': self._coinzilla_banner
            }
        }
        self.ad_slots = {}
        
        # Register all required ad slots
        self.register_ad_slot('home_top_banner', 'banner', 'monetag', 'home_top')
        self.register_ad_slot('home_bottom_banner', 'banner', 'monetag', 'home_bottom')
        self.register_ad_slot('wallet_mid_banner', 'banner', 'a-ads', 'wallet_mid')
        self.register_ad_slot('game_bottom_banner', 'banner', 'coinzilla', 'game_bottom')
        self.register_ad_slot('quest_bottom_banner', 'banner', 'a-ads', 'quest_bottom')
        self.register_ad_slot('rewarded_interstitial', 'rewarded_interstitial', 'monetag', 'any')
        self.register_ad_slot('quest_reward_popup', 'rewarded_popup', 'monetag', 'quest_completion')
    
    def register_ad_slot(self, slot_name, slot_type, network, position):
        """Register a new ad slot in the app"""
        self.ad_slots[slot_name] = {
            'type': slot_type,
            'network': network,
            'position': position,
            'last_used': 0,
            'cooldown': 30  # seconds
        }
    
    def get_available_ad(self, slot_name):
        """Get ad implementation for a slot if available"""
        slot = self.ad_slots.get(slot_name)
        if not slot:
            return None
            
        current_time = time.time()
        if current_time - slot['last_used'] < slot['cooldown']:
            return None
            
        network = self.networks.get(slot['network'])
        if not network:
            return None
            
        ad_handler = network.get(slot['type'])
        if not ad_handler:
            return None
            
        return ad_handler(slot_name)
    
    def record_ad_view(self, slot_name):
        """Update slot usage timestamp"""
        if slot_name in self.ad_slots:
            self.ad_slots[slot_name]['last_used'] = time.time()

    # Monetag implementations
    def _monetag_interstitial(self, slot_name):
        return {
            'html': f"""
            <script>
            show_9644715().then(() => {{
                fetch('/api/ads/reward?slot={slot_name}&type=interstitial');
            }})
            </script>
            """,
            'type': 'script'
        }
    
    def _monetag_popup(self, slot_name):
        return {
            'html': f"""
            <script>
            show_9644715('pop').then(() => {{
                fetch('/api/ads/reward?slot={slot_name}&type=popup');
            }})
            </script>
            """,
            'type': 'script'
        }
    
    def _monetag_banner(self, slot_name):
        return {
            'html': f"""
            <div id="monetag-{slot_name}"></div>
            <script>
                window.monetag = window.monetag || {{
                    mode: "banner",
                    publisher: "{config.MONETAG_PUBLISHER_ID}",
                    slot: "{slot_name}",
                    format: "display"
                }};
                (function() {{
                    var script = document.createElement('script');
                    script.src = 'https://monetag.com/loader.js';
                    document.body.appendChild(script);
                }})();
            </script>
            """,
            'type': 'html'
        }
    
    # A-ADS implementation
    def _aads_banner(self, slot_name):
        return {
            'html': f"""
            <div style="width:100%;height:100%;">
                <iframe data-aa='2405512' src='//acceptable.a-ads.com/2405512' 
                    style='border:0;padding:0;width:100%;height:100%;overflow:hidden;background:transparent;'>
                </iframe>
            </div>
            """,
            'type': 'iframe'
        }
    
    # Coinzilla implementation
    def _coinzilla_banner(self, slot_name):
        return {
            'html': f"""
            <script src="https://coinzilla.com/static/js/coinzilla.js"></script>
            <div class="coinzilla" data-zone="C-123456"></div>
            """,
            'type': 'script'
        }

# Initialize ad manager
ad_manager = AdManager()