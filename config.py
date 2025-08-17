import os
import json
import re
import base64
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class Config:
    def __init__(self):
        # Load Firebase credentials first
        self.FIREBASE_CREDS = self.load_firebase_creds()
        
        # Core configuration
        self.TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
        self.TELEGRAM_BOT_USERNAME = os.getenv('TELEGRAM_BOT_USERNAME')
        self.ADMIN_ID = os.getenv('ADMIN_ID')
        self.ENV = os.getenv('ENV', 'production')
        self.PORT = int(os.getenv('PORT', 10000))
        
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
        
        # Rewards Configuration (in Game Coins)
        self.REWARDS = {
            "faucet": float(os.getenv("FAUCET_REWARD", 1000)),
            "trivia_correct": float(os.getenv("TRIVIA_CORRECT_REWARD", 50)),
            "trivia_incorrect": float(os.getenv("TRIVIA_INCORRECT_REWARD", 10)),
            "spin_win": float(os.getenv("SPIN_WIN_REWARD", 200)),
            "spin_loss": float(os.getenv("SPIN_LOSS_REWARD", 10)),
            "ad_view": float(os.getenv("AD_VIEW_REWARD", 30)),
            "referral": float(os.getenv("REFERRAL_REWARD", 500)),
            "quest": float(os.getenv("QUEST_REWARD", 300)),
            "daily_bonus": float(os.getenv("DAILY_BONUS", 500))
        }
        
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
            "trivia_questions": {"id": "TRIV-EXTRA", "price_gc": 500, "effect": {"questions": 10}},
            "double_earnings": {"id": "BOOST-2X", "price_gc": 2000, "effect": {"multiplier": 2.0, "duration": 3600}},
            "extra_life": {"id": "LIFE-EXTRA", "price_gc": 300, "effect": {"lives": 1}},
            "auto_clicker": {"id": "AUTO-CLICK", "price_gc": 1500, "effect": {"auto_click": True}}
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
        
        # Logging
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        
        # Wallet Thresholds
        self.MIN_ADMIN_BALANCE = 1.0  # TON (triggers alert)

        self.DEFAULT_COUNTRY = 'KE'
        
        # Log configuration status
        self.log_config_summary()

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

    def load_firebase_creds(self):
        """Load Firebase credentials with enhanced error handling"""
        try:
            # Strategy 1: Direct JSON in environment variable
            creds_json = os.getenv('FIREBASE_CREDS_JSON')
            if creds_json:
                logger.info("Attempting to parse FIREBASE_CREDS_JSON")
                try:
                    creds = json.loads(creds_json)
                    if self.validate_firebase_creds(creds):
                        logger.info("Loaded Firebase credentials from FIREBASE_CREDS_JSON")
                        return creds
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error in FIREBASE_CREDS_JSON: {e}")

            # Strategy 2: File path
            creds_path = os.getenv('FIREBASE_CREDS_PATH', '/etc/secrets/firebase_creds.json')
            if os.path.exists(creds_path):
                logger.info(f"Loading Firebase creds from {creds_path}")
                try:
                    with open(creds_path, 'r') as f:
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Error reading {creds_path}: {str(e)}")
            
            # Strategy 3: Direct environment variable (deprecated)
            creds_str = os.getenv('FIREBASE_CREDS')
            if creds_str:
                logger.warning("FIREBASE_CREDS is deprecated. Use FIREBASE_CREDS_JSON instead.")
                try:
                    return json.loads(creds_str)
                except json.JSONDecodeError:
                    pass
                    
        except Exception as e:
            logger.error(f"Error loading Firebase credentials: {str(e)}")
        
        logger.error("No valid Firebase credentials found")
        return {}

    def validate_firebase_creds(self, creds):
        """Validate Firebase credentials structure"""
        if not isinstance(creds, dict):
            logger.error("Firebase credentials are not a dictionary")
            return False
            
        required_keys = [
            "type", "project_id", "private_key_id", "private_key",
            "client_email", "client_id", "token_uri"
        ]
        
        missing_keys = [key for key in required_keys if key not in creds]
        if missing_keys:
            logger.error(f"Firebase credentials missing required keys: {', '.join(missing_keys)}")
            return False
            
        if creds.get("type") != "service_account":
            logger.error("Firebase credentials type is not 'service_account'")
            return False
            
        # Validate private key format
        private_key = creds.get("private_key", "")
        if not private_key.startswith("-----BEGIN PRIVATE KEY-----") or \
           not private_key.endswith("-----END PRIVATE KEY-----\n"):
            logger.warning("Firebase private key format appears incorrect")
            
        return True

    def log_config_summary(self):
        """Log a secure summary of the configuration"""
        logger.info("Configuration Summary:")
        logger.info(f"Environment: {self.ENV}")
        logger.info(f"TON Enabled: {self.TON_ENABLED}")
        logger.info(f"TON Network: {self.TON_NETWORK}")
        logger.info(f"Game Coin System: Enabled (Rate: 1 TON = {self.GC_TO_TON_RATE} GC)")
        logger.info(f"Daily GC Limit: {self.MAX_DAILY_GC}")
        logger.info(f"Min Withdrawal: {self.MIN_WITHDRAWAL_GC} GC")
        logger.info(f"Max Resets: {self.MAX_RESETS} per game/day")
        logger.info(f"Features - OTC: {self.FEATURE_OTC}, Ads: {self.FEATURE_ADS}, Games: {self.FEATURE_GAMES}")
        
        # Log partial TON wallet info for security
        if self.TON_HOT_WALLET:
            logger.info(f"TON Hot Wallet: {self.secure_mask(self.TON_HOT_WALLET)}")
        else:
            logger.warning("TON Hot Wallet not configured")
        
        # Validate Firebase credentials
        if self.FIREBASE_CREDS:
            if not self.validate_firebase_creds(self.FIREBASE_CREDS):
                logger.error("Invalid Firebase credentials structure")
        else:
            logger.error("Firebase credentials are missing")

    def secure_mask(self, value, show_first=6, show_last=4):
        """Mask sensitive information for logging"""
        if not value or len(value) < (show_first + show_last):
            return "[REDACTED]"
        return f"{value[:show_first]}...{value[-show_last:]}"

# Create singleton instance
config = Config()