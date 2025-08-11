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
        self.TON_PUBLIC_KEY = os.getenv('TON_PUBLIC_KEY')
        
        # Handle TON private key padding issue
        raw_private_key = os.getenv('TON_PRIVATE_KEY', '')
        self.TON_PRIVATE_KEY = self.fix_base64_padding(raw_private_key)
        
        # Security and limits
        self.MIN_HOT_BALANCE = float(os.getenv('MIN_HOT_BALANCE', '10.0'))
        self.FREE_DAILY_EARN_LIMIT = float(os.getenv('FREE_DAILY_EARN_LIMIT', '0.5'))
        self.USER_DAILY_WITHDRAWAL_LIMIT = float(os.getenv('USER_DAILY_WITHDRAWAL_LIMIT', '100.0'))
        self.DAILY_WITHDRAWAL_LIMIT = float(os.getenv('DAILY_WITHDRAWAL_LIMIT', '1000.0'))
        self.ALERT_WEBHOOK = os.getenv('ALERT_WEBHOOK')
        self.SECRET_KEY = os.getenv('SECRET_KEY', 'your_secret_key_here')
        
        # Rewards Configuration (in TON)
        self.REWARDS = {
            "faucet": float(os.getenv("FAUCET_REWARD", 0.01)),
            "trivia_correct": float(os.getenv("TRIVIA_CORRECT_REWARD", 0.005)),
            "trivia_incorrect": float(os.getenv("TRIVIA_INCORRECT_REWARD", 0.001)),
            "spin_win": float(os.getenv("SPIN_WIN_REWARD", 0.02)),
            "spin_loss": float(os.getenv("SPIN_LOSS_REWARD", 0.001)),
            "ad_view": float(os.getenv("AD_VIEW_REWARD", 0.003)),
            "referral": float(os.getenv("REFERRAL_REWARD", 0.05)),
            "quest": float(os.getenv("QUEST_REWARD", 0.03))
        }
        
        # Game Configuration
        self.GAME_COOLDOWN = int(os.getenv("GAME_COOLDOWN", 30))  # minutes
        self.FAUCET_COOLDOWN = int(os.getenv("FAUCET_COOLDOWN", 24))  # hours
        self.MIN_WITHDRAWAL = float(os.getenv("MIN_WITHDRAWAL", 0.1))  # TON
        
        # Web Server Configuration
        self.RENDER_URL = os.getenv("RENDER_URL", "crptgameminer.onrender.com")
        self.RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "crptgameminer.onrender.com/miniapp")
        
        # Payment Processors
        self.PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox")
        self.PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "your_paypal_id")
        self.PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "your_paypal_secret")
        self.PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID", "your_webhook_id")
        self.MPESA_SHORTCODE = os.getenv("MPESA_SHORTCODE", "174379")
        self.MPESA_BUSINESS_SHORTCODE = os.getenv("MPESA_BUSINESS_SHORTCODE", "174379")
        self.MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY", "")
        self.MPESA_INITIATOR_NAME = os.getenv("MPESA_INITIATOR_NAME", "")
        self.MPESA_SECURITY_CREDENTIAL = os.getenv("MPESA_SECURITY_CREDENTIAL", "")
        
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
                'reward': 0.05
            },
            {
                'type': 'social',
                'difficulty': 2,
                'tasks': ['refer_X_friends'],
                'reward': 0.1
            },
            {
                'type': 'exploration',
                'difficulty': 1,
                'tasks': ['play_X_game_types'],
                'reward': 0.03
            },
            {
                'type': 'general',
                'difficulty': 1,
                'tasks': ['complete_any_3_actions'],
                'reward': 0.04
            }
        ]
        self.QUEST_REFRESH_HOUR = 4  # 4 AM UTC
        self.DAILY_QUEST_COUNT = 3
        self.AVAILABLE_GAME_TYPES = {'trivia', 'spin', 'puzzle', 'battle', 'mining'}
        self.LEVEL_XP_BASE = 100
        self.LEVEL_XP_MULTIPLIER = 1.5
        self.MAX_LEVEL = 50

        # Mining Economics
        self.REWARD_PER_BLOCK = 0.1  # TON
        self.DAILY_EMISSION = 50  # TON
        self.USER_ACTIVITY_POOL_RATIO = 0.7  # 70%
        self.MIN_STAKE = 5.0  # Minimum TON for staking
        
        # Game Reward Rates
        self.REWARD_RATES = {
            'edge-surf': {'base': 0.003, 'per_minute': 0.007},
            'trex-runner': {'base': 0.001, 'per_100_meters': 0.005},
            'clicker': {'base': 0.000, 'per_1000_points': 0.015},
            'trivia': {'base': 0.002, 'per_correct_answer': 0.008},
            'spin': {'base': 0.004}
        }

        self.MAX_GAME_REWARD = {
            'edge-surf': 0.5,
            'trex-runner': 0.4,
            'clicker': 0.6,
            'trivia': 0.3,
            'spin': 0.2
        }

        # Anti-Cheating Thresholds
        self.MIN_CLICK_INTERVAL = 0.1  # seconds
        self.SESSION_DURATION_VARIANCE = 0.3  # Allowed deviation
        
        # Ad Monetization Rates (USD)
        self.AD_RATES = {
            'monetag': 0.003,
            'a-ads': 0.0012,
            'ad-mob': 0.0025
        }
        
        # Premium Tiers (USD/month)
        self.PREMIUM_TIERS = {
            'basic': 4.99,
            'pro': 9.99,
            'vip': 19.99
        }
        
        # Data Insights Value
        self.DATA_POINT_VALUE = 0.0001  # USD per point

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
        
        # Logging
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        
        # Wallet Thresholds
        self.MIN_ADMIN_BALANCE = 50.0  # TON (triggers alert)

        self.DEFAULT_COUNTRY = 'KE'
        
        # Log configuration status
        self.log_config_summary()

    def fix_base64_padding(self, value):
        """Ensure base64 string has correct padding"""
        value = value.strip()
        pad_length = 4 - (len(value) % 4)
        if pad_length == 4:
            return value
        return value + ('=' * pad_length)

    def load_firebase_creds(self):
        """Load Firebase credentials with enhanced error handling"""
        creds = {}
        try:
            # Strategy 1: Direct environment variable (single-line JSON)
            creds_str = os.getenv('FIREBASE_CREDS')
            if creds_str:
                logger.info("Attempting to parse FIREBASE_CREDS from env")
                try:
                    creds = json.loads(creds_str)
                    if self.validate_firebase_creds(creds):
                        logger.info("Loaded Firebase credentials from FIREBASE_CREDS env")
                        return creds
                    else:
                        logger.warning("FIREBASE_CREDS env exists but validation failed")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error in FIREBASE_CREDS: {e.doc}")
                    logger.error(f"Error position: {e.pos}, Error: {e.msg}")
            
            # Strategy 2: File path
            creds_path = os.getenv('FIREBASE_CREDS_PATH', '/etc/secrets/firebase_creds.json')
            if creds_path and os.path.exists(creds_path):
                logger.info(f"Attempting to load Firebase creds from {creds_path}")
                try:
                    with open(creds_path, 'r') as f:
                        creds = json.load(f)
                    if self.validate_firebase_creds(creds):
                        logger.info(f"Loaded Firebase credentials from {creds_path}")
                        return creds
                    else:
                        logger.warning(f"Firebase credentials from {creds_path} failed validation")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error in {creds_path}: {e.doc}")
                    logger.error(f"Error position: {e.pos}, Error: {e.msg}")
                except Exception as e:
                    logger.error(f"Error reading {creds_path}: {str(e)}")
            
            # Strategy 3: Direct JSON in alternative env variable
            creds_json_str = os.getenv('FIREBASE_CREDS_JSON')
            if creds_json_str:
                logger.info("Attempting to parse FIREBASE_CREDS_JSON")
                try:
                    creds = json.loads(creds_json_str)
                    if self.validate_firebase_creds(creds):
                        logger.info("Loaded Firebase credentials from FIREBASE_CREDS_JSON")
                        return creds
                    else:
                        logger.warning("FIREBASE_CREDS_JSON exists but validation failed")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error in FIREBASE_CREDS_JSON: {e.doc}")
                    logger.error(f"Error position: {e.pos}, Error: {e.msg}")
                    
        except Exception as e:
            logger.error(f"Critical error loading Firebase credentials: {str(e)}", exc_info=True)
        
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
        logger.info(f"Firebase Creds Available: {bool(self.FIREBASE_CREDS)}")
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