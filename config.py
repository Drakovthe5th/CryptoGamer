import os
import json
import re
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
        self.TON_MNEMONIC = os.getenv('TON_MNEMONIC')
        self.TON_HOT_WALLET = os.getenv('TON_HOT_WALLET')
        self.TON_ADMIN_ADDRESS = os.getenv('TON_ADMIN_ADDRESS')
        self.TON_NETWORK = os.getenv('TON_NETWORK', 'mainnet')
        self.TON_API_KEY = os.getenv('TON_API_KEY')
        self.TON_PUBLIC_KEY = os.getenv('TON_PUBLIC_KEY')
        self.TON_PRIVATE_KEY = os.getenv('TON_PRIVATE_KEY')
        
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
        
        # config.py additions

        # Ad System
        AD_COOLDOWN = 30  # seconds
        PREMIUM_AD_BONUS = 1.5
        AD_STREAK_BONUS_MEDIUM = 1.2
        AD_STREAK_BONUS_HIGH = 1.5
        PEAK_HOURS = [18, 19, 20, 21]  # 6PM-10PM
        PEAK_HOUR_BONUS = 1.3
        WEEKEND_BONUS = 1.2
        HIGH_VALUE_REGIONS = ['US', 'CA', 'GB', 'AU', 'DE']
        REGIONAL_BONUS = 1.25
        MOBILE_BONUS = 1.15
        AD_DURATIONS = {
            "coinzilla": 45,
            "propeller": 30,
            "a-ads": 60
        }

        # Quest System
        QUEST_TEMPLATES = [
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
        QUEST_REFRESH_HOUR = 4  # 4 AM UTC
        DAILY_QUEST_COUNT = 3
        AVAILABLE_GAME_TYPES = {'trivia', 'spin', 'puzzle', 'battle', 'mining'}
        LEVEL_XP_BASE = 100
        LEVEL_XP_MULTIPLIER = 1.5
        MAX_LEVEL = 50

                # Mining Economics
        REWARD_PER_BLOCK = 0.1  # TON
        DAILY_EMISSION = 50  # TON
        USER_ACTIVITY_POOL_RATIO = 0.7  # 70%
        MIN_STAKE = 5.0  # Minimum TON for staking
        
        # Add for all games
        REWARD_RATES = {
            'edge-surf': {'base': 0.003, 'per_minute': 0.007},
            'trex-runner': {'base': 0.001, 'per_100_meters': 0.005},
            'clicker': {'base': 0.000, 'per_1000_points': 0.015},
            'trivia': {'base': 0.002, 'per_correct_answer': 0.008},
            'spin': {'base': 0.004}
        }

        MAX_GAME_REWARD = {
            'edge-surf': 0.5,
            'trex-runner': 0.4,
            'clicker': 0.6,
            'trivia': 0.3,
            'spin': 0.2
        }

        # Anti-Cheating Thresholds
        MIN_CLICK_INTERVAL = 0.1  # seconds
        SESSION_DURATION_VARIANCE = 0.3  # Allowed deviation
        
        # Ad Monetization Rates (USD)
        AD_RATES = {
            'monetag': 0.003,
            'a-ads': 0.0012,
            'ad-mob': 0.0025
        }
        
        # Premium Tiers (USD/month)
        PREMIUM_TIERS = {
            'basic': 4.99,
            'pro': 9.99,
            'vip': 19.99
        }
        
        # Data Insights Value
        DATA_POINT_VALUE = 0.0001  # USD per point

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

        DEFAULT_COUNTRY = 'KE'
        
        # Log configuration status
        self.log_config_summary()

    def load_firebase_creds(self):
        """Load Firebase credentials with multiple fallback strategies"""
        # Strategy 1: Load from file if specified
        creds_path = os.getenv('FIREBASE_CREDS')
        if creds_path and os.path.exists(creds_path):
            try:
                with open(creds_path, 'r') as f:
                    creds = json.load(f)
                logger.info(f"Loaded Firebase credentials from file: {creds_path}")
                return creds
            except Exception as e:
                logger.error(f"Failed to load Firebase creds from file: {e}")
        
        # Strategy 2: Parse from environment variable
        creds_str = os.getenv('FIREBASE_CREDS')
        if creds_str:
            try:
                # Clean and parse JSON
                cleaned = re.sub(r'(?<!\\)\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', creds_str)
                creds = json.loads(cleaned)
                
                # Fix newlines in private key
                if "private_key" in creds:
                    creds["private_key"] = creds["private_key"].replace('\\n', '\n')
                
                logger.info("Loaded Firebase credentials from environment variable")
                return creds
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error in FIREBASE_CREDS: {e}")
                logger.debug(f"Content: {creds_str[:200]}...")  # Log first 200 characters
            except Exception as e:
                logger.error(f"Error parsing FIREBASE_CREDS: {e}")
        
        # Strategy 3: Direct JSON in environment variable
        try:
            creds = json.loads(os.getenv('FIREBASE_CREDS_JSON', '{}'))
            if creds:
                logger.info("Loaded Firebase credentials from FIREBASE_CREDS_JSON")
                return creds
        except:
            pass
        
        logger.error("No valid Firebase credentials found")
        return {}

    def validate_firebase_creds(self, creds):
        """Validate Firebase credentials structure"""
        required_keys = [
            "type", "project_id", "private_key_id", "private_key",
            "client_email", "client_id", "token_uri"
        ]
        
        if not creds:
            logger.error("Firebase credentials are empty")
            return False
            
        missing_keys = [key for key in required_keys if key not in creds]
        if missing_keys:
            logger.error(f"Firebase credentials missing required keys: {', '.join(missing_keys)}")
            return False
            
        if creds.get("type") != "service_account":
            logger.error("Firebase credentials type is not 'service_account'")
            return False
            
        return True

    def log_config_summary(self):
        """Log a summary of the configuration"""
        logger.info("Configuration Summary:")
        logger.info(f"Environment: {self.ENV}")
        logger.info(f"TON Enabled: {self.TON_ENABLED}")
        logger.info(f"TON Network: {self.TON_NETWORK}")
        logger.info(f"Firebase Creds Available: {bool(self.FIREBASE_CREDS)}")
        logger.info(f"Features - OTC: {self.FEATURE_OTC}, Ads: {self.FEATURE_ADS}, Games: {self.FEATURE_GAMES}")
        
        # Log partial TON wallet info for security
        if self.TON_HOT_WALLET:
            logger.info(f"TON Hot Wallet: {self.TON_HOT_WALLET[:6]}...{self.TON_HOT_WALLET[-6:]}")
        else:
            logger.warning("TON Hot Wallet not configured")
        
        # Validate Firebase credentials
        if self.FIREBASE_CREDS:
            if not self.validate_firebase_creds(self.FIREBASE_CREDS):
                logger.error("Invalid Firebase credentials structure")
        else:
            logger.error("Firebase credentials are missing")

# Create singleton instance
config = Config()