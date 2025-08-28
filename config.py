# config.py
import os
import json
import re
import base64
import urllib.parse
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REWARD_RATES = {
'edge-surf': {'base': 30, 'per_second': 7},
'trex-runner': {'base': 10, 'per_100_meters': 50},
'clicker': {'base': 5, 'per_1000_points': 15},
'trivia': {'base': 20, 'per_correct_answer': 50},
'spin': {'base': 40}
}

MAX_GAME_REWARD = 1.0
MAX_DAILY_GAME_COINS = 20000

# Load environment variables
load_dotenv()

class Config:

    def __init__(self):
        # Core configuration
        self.TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
        self.TELEGRAM_BOT_USERNAME = os.getenv('TELEGRAM_BOT_USERNAME')
        self.ADMIN_ID = os.getenv('ADMIN_ID')
        self.ENV = os.getenv('ENV', 'production')
        self.PORT = int(os.getenv('PORT', 10000))
        self.TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')
        self.TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')
        self.TELEGRAM_SESSION_STRING = os.getenv('TELEGRAM_SESSION_STRING')

        # Telegram Payments Configuration
        self.TELEGRAM_STARS_PROVIDER_TOKEN = os.getenv('TELEGRAM_STARS_PROVIDER_TOKEN')
        self.TELEGRAM_PAYMENTS_TEST_MODE = os.getenv('TELEGRAM_PAYMENTS_TEST_MODE', 'false').lower() == 'true'
        
        # Telegram Stars Configuration
        TELEGRAM_STARS_TEST_MODE = False  # Set to True for testing
        STARS_TO_CREDITS_RATE = 10  # 1 Star = 10 Crew Credits
        MAX_STARS_PURCHASE = 50000  # Maximum Stars per transaction

        # MongoDB configuration - FIXED
        raw_uri = os.getenv('MONGO_URI')
        if raw_uri:
            self.MONGO_URI = self.encode_mongo_uri(raw_uri)
        else:
            self.MONGO_URI = None

        # Set DB name AFTER setting URI
        self.MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'render-user')
        
        # SINGLE validation call AFTER all properties are set
        self.validate_mongo_config()
        
        # MongoDB configuration
        self.MONGO_URI = os.getenv('MONGO_URI')
        self.MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'render-user')
        self.validate_mongo_config()
        
        # TON blockchain configuration
        self.TON_ENABLED = os.getenv('TON_ENABLED', 'true').lower() == 'true'
        self.TON_MNEMONIC = os.getenv('TON_WALLET_MNEMONIC') or os.getenv('TON_MNEMONIC')
        self.TON_HOT_WALLET = os.getenv('TON_HOT_WALLET')
        self.TON_ADMIN_ADDRESS = os.getenv('TON_ADMIN_ADDRESS')
        self.TON_NETWORK = os.getenv('TON_NETWORK', 'mainnet')
        self.TON_API_KEY = os.getenv('TON_API_KEY')
        self.TON_LITE_SERVERS = self.parse_lite_servers(os.getenv('TON_LITE_SERVERS'))
        
        # Ensure TON_API_KEY is set if LiteClient fails
        if not self.TON_API_KEY:
            logger.warning("TON_API_KEY not set - HTTP fallback unavailable")

        # Handle TON private key padding issue
        raw_private_key = os.getenv('TON_PRIVATE_KEY', '')
        self.TON_PRIVATE_KEY = self.fix_base64_padding(raw_private_key)
        
        # Security and limits
        self.MIN_HOT_BALANCE = float(os.getenv('MIN_HOT_BALANCE', '1.0'))
        self.USER_DAILY_WITHDRAWAL_LIMIT = float(os.getenv('USER_DAILY_WITHDRAWAL_LIMIT', '10.0'))
        self.DAILY_WITHDRAWAL_LIMIT = float(os.getenv('DAILY_WITHDRAWAL_LIMIT', '10.0'))
        self.ALERT_WEBHOOK = os.getenv('ALERT_WEBHOOK')
        self.SECRET_KEY = os.getenv('SECRET_KEY', 'your_secret_key_here')
        self.ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', 'default_encryption_key').encode()
        
        # Game Coin System Configuration
        self.GC_TO_TON_RATE = 2000  # 200,000 GC = 100 TON
        self.MAX_DAILY_GC = 20000  # 10 TON equivalent
        self.MAX_RESETS = 3  # Per game per day
        self.MIN_WITHDRAWAL_GC = 200000  # 100 TON equivalent
        self.MIN_GC_PURCHASE = 1000  # Minimum game coins for purchases
        self.MIN_GAMEPLAY_HOURS = 500  # Minimum gameplay hours required for withdrawal
        
        # Membership Tiers and Benefits
        self.MEMBERSHIP_TIERS = {
            "BASIC": {
                "price": 0,
                "benefits": ["standard_earnings"]
            },
            "PREMIUM": {
                "price": 5.0,  # in TON
                "benefits": [
                    "1.5x_earnings", 
                    "extra_questions", 
                    "daily_reset_booster",
                    "ad_free"
                ]
            },
            "ULTIMATE": {
                "price": 10.0,  # in TON
                "benefits": [
                    "2x_earnings",
                    "unlimited_questions",
                    "free_resets",
                    "priority_support",
                    "exclusive_items"
                ]
            }
        }
        
        # Game Configuration
        self.GAME_COOLDOWN = int(os.getenv("GAME_COOLDOWN", 30))  # minutes
        self.FAUCET_COOLDOWN = int(os.getenv("FAUCET_COOLDOWN", 24))  # hours
        
        # In-Game Purchases
        self.IN_GAME_ITEMS = {
            "trivia_questions": {
                "id": "TRIV-EXTRA", 
                "price_stars": 50,  # 50 Stars
                "price_gc": 500, 
                "effect": {"questions": 10}
            },
            "double_earnings": {
                "id": "BOOST-2X", 
                "price_stars": 200,  # 200 Stars
                "price_gc": 2000, 
                "effect": {"multiplier": 2.0, "duration": 3600}
            },
            "extra_life": {
                "id": "LIFE-EXTRA", 
                "price_stars": 30,  # 30 Stars
                "price_gc": 300, 
                "effect": {"lives": 1}
            },
            "auto_clicker": {
                "id": "AUTO-CLICK", 
                "price_stars": 150,  # 150 Stars
                "price_gc": 1500, 
                "effect": {"auto_click": True}
            }
        }

        # Add payment provider configuration
        self.PAYMENT_PROVIDERS = {
            'stars': {
                'enabled': True,
                'name': 'Telegram Stars',
                'min_amount': 10,
                'max_amount': 10000,
                'currency': 'XTR'
            },
            'ton': {
                'enabled': self.TON_ENABLED,
                'name': 'TON Blockchain',
                'min_amount': 0.1,
                'max_amount': 1000,
                'currency': 'TON'
            }
        }
        
        # Web Server Configuration
        self.RENDER_URL = os.getenv("RENDER_URL", "crptgameminer.onrender.com")
        self.RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "crptgameminer.onrender.com/miniapp")
        
        # Ad Platforms
        self.AD_PLATFORMS = {
            "coinzilla": os.getenv("COINZILLA_ZONE_ID", "your_coinzilla_zone"),
            "propeller": os.getenv("PROPELLER_ZONE_ID", "2981090"),
            "a-ads": os.getenv("A_ADS_ZONE_ID", "2405512")
        }
        
        # Ad System
        self.AD_COOLDOWN = 30  # seconds
        self.PREMIUM_AD_BONUS = 1.5
        self.AD_STREAK_BONUS_MEDIUM = 1.2
        self.AD_STREAK_BONUS_HIGH = 1.5
        self.PEAK_HOURS = [18, 19, 20, 21]  # 6PM-10PM
        self.PEAK_HOUR_BONUS = 1.3
        self.WEEKEND_BONUS = 1.2
        self.HIGH_VALUE_REGIONS = ['US', 'CA', 'GB', 'AU', 'DE']
        self.REGIONAL_BONUS = 1.25
        self.MOBILE_BONUS = 1.15
        self.AD_DURATIONS = {
            "coinzilla": 45,
            "propeller": 30,
            "a-ads": 60
        }

        # Quest System
        self.QUEST_TEMPLATES = [
            {
                'type': 'gaming',
                'difficulty': 1,
                'tasks': ['win_X_games'],
                'reward_gc': 500
            },
            {
                'type': 'social',
                'difficulty': 2,
                'tasks': ['refer_X_friends'],
                'reward_gc': 1000
            },
            {
                'type': 'exploration',
                'difficulty': 1,
                'tasks': ['play_X_game_types'],
                'reward_gc': 300
            },
            {
                'type': 'general',
                'difficulty': 1,
                'tasks': ['complete_any_3_actions'],
                'reward_gc': 400
            },
                # New social media quests
            {
                'type': 'social',
                'difficulty': 1,
                'tasks': ['connect_telegram_wallet'],
                'reward': 1000  # GC
            },
            {
                'type': 'social',
                'difficulty': 1,
                'tasks': ['follow_instagram'],
                'reward': 2000  # GC
            },
            {
                'type': 'social',
                'difficulty': 1,
                'tasks': ['follow_facebook'],
                'reward': 2000  # GC
            },
            {
                'type': 'social',
                'difficulty': 1,
                'tasks': ['follow_twitter'],
                'reward': 2000  # GC
            },
            {
                'type': 'social',
                'difficulty': 2,
                'tasks': ['join_telegram_channel'],
                'reward': 2000  # GC
            },
            {
                'type': 'social',
                'difficulty': 2,
                'tasks': ['post_twitter'],
                'reward': 3000  # GC
            },
            {
                'type': 'social',
                'difficulty': 2,
                'tasks': ['retweet_post'],
                'reward': 3000  # GC
            },
            {
                'type': 'social',
                'difficulty': 3,
                'tasks': ['post_tiktok'],
                'reward': 10000  # GC
            },
            
            # New referral quests
            {
                'type': 'referral',
                'difficulty': 1,
                'tasks': ['invite_friend'],
                'reward': 4000  # GC
            },
            {
                'type': 'referral',
                'difficulty': 2,
                'tasks': ['recruit_10_users'],
                'reward': 16000  # GC
            },
            {
                'type': 'referral',
                'difficulty': 3,
                'tasks': ['recruit_100_users'],
                'reward': 32000  # GC
            },
            
            # New Binance quests
            {
                'type': 'exchange',
                'difficulty': 2,
                'tasks': ['signup_binance'],
                'reward': 5000  # GC
            },
            {
                'type': 'exchange',
                'difficulty': 2,
                'tasks': ['invite_binance_trader'],
                'reward': 7000  # GC
            },
            
            # New progression quests
            {
                'type': 'progression',
                'difficulty': 2,
                'tasks': ['reach_level_3'],
                'reward': 10000  # GC
            },
            {
                'type': 'progression',
                'difficulty': 2,
                'tasks': ['post_retweet_earn_repeat'],
                'reward': 10000  # GC
            },
            {
                'type': 'progression',
                'difficulty': 3,
                'tasks': ['earn_10000_ads'],
                'reward': 20000  # GC
            },
            {
                'type': 'progression',
                'difficulty': 3,
                'tasks': ['earn_100000_ads'],
                'reward': 50000  # GC
            },
            {
                'type': 'progression',
                'difficulty': 1,
                'tasks': ['watch_ads'],
                'reward': 5000  # GC
            },
            {
                'type': 'shop',
                'difficulty': 2,
                'tasks': ['boost_channel'],
                'reward': 5000  # GC
            },
            {
                'type': 'shop',
                'difficulty': 2,
                'tasks': ['boost_earnings'],
                'reward': 7000  # GC
            }
        ]
        self.QUEST_REFRESH_HOUR = 4  # 4 AM UTC
        self.DAILY_QUEST_COUNT = 3
        self.AVAILABLE_GAME_TYPES = {'trivia', 'spin', 'clicker', 'trex', 'edge-surf'}
        self.LEVEL_XP_BASE = 100
        self.LEVEL_XP_MULTIPLIER = 1.5
        self.MAX_LEVEL = 50

        # Game Reward Rates (in GC)
        self.REWARD_RATES = {
            'edge-surf': {'base': 30, 'per_second': 7},
            'trex-runner': {'base': 10, 'per_100_meters': 50},
            'clicker': {'base': 5, 'per_1000_points': 15},
            'trivia': {'base': 20, 'per_correct_answer': 50},
            'spin': {'base': 40}
        }

        # Anti-Cheating Thresholds
        self.MIN_CLICK_INTERVAL = 0.1  # seconds
        self.SESSION_DURATION_VARIANCE = 0.3  # Allowed deviation
        
        # OTC Desk
        self.OTC_USD_RATE = float(os.getenv("OTC_USD_RATE", "6.80"))
        self.OTC_EUR_RATE = float(os.getenv("OTC_EUR_RATE", "6.20"))
        self.OTC_KES_RATE = float(os.getenv("OTC_KES_RATE", "950"))
        self.OTC_FEE_PERCENT = float(os.getenv("OTC_FEE_PERCENT", "3.0"))
        self.OTC_MIN_FEE = float(os.getenv("OTC_MIN_FEE", "1.0"))
        self.MIN_OTC_FEE = float(os.getenv("MIN_OTC_FEE", "0.50"))
        
        # Feature Toggles
        self.FEATURE_OTC = os.getenv("FEATURE_OTC", "true").lower() == "true"
        self.FEATURE_ADS = os.getenv("FEATURE_ADS", "true").lower() == "true"
        self.FEATURE_GAMES = os.getenv("FEATURE_GAMES", "true").lower() == "true"
        self.FEATURE_IN_GAME_PURCHASES = os.getenv("FEATURE_IN_GAME_PURCHASES", "true").lower() == "true"
        self.FEATURE_MEMBERSHIPS = os.getenv("FEATURE_MEMBERSHIPS", "true").lower() == "true"

                # Telegram Client Configuration Defaults
        self.TELEGRAM_CLIENT_CONFIG = {
            "about_length_limit_default": 70,
            "about_length_limit_premium": 140,
            "authorization_autoconfirm_period": 604800,
            "autoarchive_setting_available": True,
            "background_connection": True,
            "caption_length_limit_default": 1024,
            "caption_length_limit_premium": 4096,
            "channels_limit_default": 500,
            "channels_limit_premium": 1000,
            "channels_public_limit_default": 10,
            "channels_public_limit_premium": 20,
            "dialog_filters_chats_limit_default": 100,
            "dialog_filters_chats_limit_premium": 200,
            "dialog_filters_enabled": True,
            "dialog_filters_limit_default": 10,
            "dialog_filters_limit_premium": 30,
            "dialog_filters_tooltip": False,
            "dialogs_folder_pinned_limit_default": 100,
            "dialogs_folder_pinned_limit_premium": 200,
            "dialogs_pinned_limit_default": 5,
            "dialogs_pinned_limit_premium": 10,
            "emojies_animated_zoom": 0.625,
            "emojies_send_dice": ["🎲", "🎯", "🏀", "⚽", "⚽", "🎰", "🎳"],
            "gif_search_branding": "tenor",
            "keep_alive_service": True,
            "message_animated_emoji_max": 100,
            "premium_promo_order": [
                "stories", "more_upload", "double_limits", "business", 
                "last_seen", "voice_to_text", "faster_download", "translations",
                "animated_emoji", "emoji_status", "saved_tags", "peer_colors",
                "wallpapers", "profile_badge", "message_privacy", "advanced_chat_management",
                "no_ads", "app_icons", "infinite_reactions", "animated_userpics",
                "premium_stickers", "effects"
            ],
            "premium_bot_username": "PremiumBot",
            "qr_login_camera": True,
            "qr_login_code": "primary",
            "reactions_uniq_max": 11,
            "reactions_in_chat_max": 100,
            "reactions_user_max_default": 1,
            "reactions_user_max_premium": 3,
            "saved_gifs_limit_default": 200,
            "saved_gifs_limit_premium": 400,
            "stickers_faved_limit_default": 5,
            "stickers_faved_limit_premium": 10,
            "upload_max_fileparts_default": 4000,
            "upload_max_fileparts_premium": 8000,
            "web_app_allowed_protocols": ["http", "https"]
        }
        
        # Logging
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        
        # Wallet Thresholds
        self.MIN_ADMIN_BALANCE = 1.0  # TON (triggers alert)

        self.DEFAULT_COUNTRY = 'KE'
        
        # Log configuration status
        self.log_config_summary()

    def encode_mongo_uri(self, uri):
        """Encode special characters in MongoDB URI"""
        if "://" not in uri:
            return uri
            
        parts = uri.split("://")
        protocol = parts[0]
        auth_host = parts[1]
        
        if "@" in auth_host:
            auth, host = auth_host.split("@", 1)
            if ":" in auth:
                user, password = auth.split(":", 1)
                # Encode special characters in password
                password = urllib.parse.quote_plus(password)
                auth = f"{user}:{password}"
            return f"{protocol}://{auth}@{host}"
        return uri

    def validate_mongo_config(self):
        """Validate MongoDB configuration"""
        if not self.MONGO_URI:
            logger.error("MONGO_URI is not set in environment variables")
            raise ValueError("MongoDB connection string is required")
        
        # Clean and validate format
        self.MONGO_URI = self.MONGO_URI.strip()
        
        # Remove surrounding quotes if present
        if self.MONGO_URI.startswith('"') and self.MONGO_URI.endswith('"'):
            self.MONGO_URI = self.MONGO_URI[1:-1]
        
        if not re.match(r'^mongodb(\+srv)?://', self.MONGO_URI):
            # Log first 20 chars for debugging (without exposing credentials)
            sample = self.MONGO_URI[:20]
            logger.error(f"Invalid MONGO_URI format. Starts with: '{sample}...'")
            raise ValueError("Invalid MongoDB URI format")
            
        if not self.MONGO_DB_NAME:
            logger.warning("MONGO_DB_NAME not set, using default 'CryptoGamer'")
            
        logger.info(f"Using MongoDB database: {self.MONGO_DB_NAME}")

    def parse_lite_servers(self, servers_str):
        """Parse TON lite servers from environment variable"""
        if not servers_str:
            return []
            
        try:
            return json.loads(servers_str)
        except json.JSONDecodeError:
            logger.warning("Invalid TON_LITE_SERVERS format, using default")
            return [
                {
                    "ip": 109764204,
                    "port": 48014,
                    "id": {"@type": "pub.ed25519", "key": "peJ2mzyUq4x1ivXgF5oJjBD4l7YdfYf0r4UJt6NpD/o="}
                }
            ]

    def fix_base64_padding(self, value):
        """Ensure base64 string has correct padding"""
        value = value.strip()
        pad_length = 4 - (len(value) % 4)
        if pad_length == 4:
            return value
        return value + ('=' * pad_length)

    def log_config_summary(self):
        """Log a secure summary of the configuration"""
        logger.info("Configuration Summary:")
        logger.info(f"Environment: {self.ENV}")
        logger.info(f"TON Enabled: {self.TON_ENABLED}")
        logger.info(f"TON Network: {self.TON_NETWORK}")
        logger.info(f"Game Coin System: Enabled (Rate: 1 TON = {self.GC_TO_TON_RATE} GC)")
        logger.info(f"Daily GC Limit: {self.MAX_DAILY_GC}")
        logger.info(f"Min Withdrawal: {self.MIN_WITHDRAWAL_GC} GC")
        logger.info(f"Min Gameplay Hours: {self.MIN_GAMEPLAY_HOURS}")
        logger.info(f"Max Resets: {self.MAX_RESETS} per game/day")
        logger.info(f"Features - OTC: {self.FEATURE_OTC}, Ads: {self.FEATURE_ADS}, Games: {self.FEATURE_GAMES}")
        logger.info(f"MongoDB Database: {self.MONGO_DB_NAME}")
        
        # Log partial TON wallet info for security
        if self.TON_HOT_WALLET:
            logger.info(f"TON Hot Wallet: {self.secure_mask(self.TON_HOT_WALLET)}")
        else:
            logger.warning("TON Hot Wallet not configured")

    def secure_mask(self, value, show_first=6, show_last=4):
        """Mask sensitive information for logging"""
        if not value or len(value) < (show_first + show_last):
            return "[REDACTED]"
        return f"{value[:show_first]}...{value[-show_last:]}"

# Create singleton instance
config = Config()