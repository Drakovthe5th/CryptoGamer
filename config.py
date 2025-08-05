import os
import json
from dotenv import load_dotenv
import logging
import re  # Added missing import

logger = logging.getLogger(__name__)

load_dotenv()

class Config:
    def __init__(self):
        # Try to get Firebase creds from file first
        self.FIREBASE_CREDS = self.load_firebase_creds_from_file()
        
        # If file not available, try environment variable
        if not self.FIREBASE_CREDS:
            self.FIREBASE_CREDS = self.parse_firebase_creds(os.getenv('FIREBASE_CREDS'))
        
        # Core configuration
        self.TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
        self.ADMIN_ID = os.getenv('ADMIN_ID')
        
        # TON blockchain configuration
        self.TON_ENABLED = os.getenv('TON_ENABLED', 'true').lower() == 'true'
        self.TON_WALLET_MNEMONIC = os.getenv('TON_WALLET_MNEMONIC')
        self.TON_HOT_WALLET = os.getenv('TON_HOT_WALLET')
        self.TON_NETWORK = os.getenv('TON_NETWORK', 'mainnet')
        self.TON_API_KEY = os.getenv('TON_API_KEY')
        self.TON_PUBLIC_KEY = os.getenv('TON_PUBLIC_KEY')
        self.TON_PRIVATE_KEY = os.getenv('TON_PRIVATE_KEY')
        
        # Security and limits
        self.MIN_HOT_BALANCE = float(os.getenv('MIN_HOT_BALANCE', '10.0'))
        self.FREE_DAILY_EARN_LIMIT = 0.5  # TON per user
        self.USER_DAILY_WITHDRAWAL_LIMIT = float(os.getenv('USER_DAILY_WITHDRAWAL_LIMIT', '100.0'))
        self.DAILY_WITHDRAWAL_LIMIT = float(os.getenv('DAILY_WITHDRAWAL_LIMIT', '1000.0'))
        self.ALERT_WEBHOOK = os.getenv('ALERT_WEBHOOK')
        
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
        self.RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "crptgameminer.onrender.com")
        
        # Ad Platforms
        self.AD_PLATFORMS = {
            "coinzilla": os.getenv("COINZILLA_ZONE_ID", "your_coinzilla_zone"),
            "propeller": os.getenv("PROPELLER_ZONE_ID", "2981090"),
            "a-ads": os.getenv("A_ADS_ZONE_ID", "2405512")
        }
        
        # Wallet Thresholds
        self.MIN_ADMIN_BALANCE = 50.0  # TON (triggers alert)

    def load_firebase_creds_from_file(self):
        """Load Firebase credentials from file if available"""
        creds_path = os.getenv('FIREBASE_CREDS_FILE')
        if creds_path and os.path.exists(creds_path):
            try:
                with open(creds_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load Firebase creds from file: {e}")
        return None

    def parse_firebase_creds(self, creds_str):
        """Parse Firebase credentials with error handling"""
        try:
            if not creds_str:
                return None
                
            # Clean and parse JSON
            cleaned = re.sub(r'(?<!\\)\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', creds_str)
            creds = json.loads(cleaned)
            
            # Fix newlines in private key
            if "private_key" in creds:
                creds["private_key"] = creds["private_key"].replace('\\n', '\n')
                
            return creds
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing FIREBASE_CREDS: {e}")
            logger.debug(f"Problematic JSON: {creds_str}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing FIREBASE_CREDS: {e}")
            return None
    
# Create singleton instance
config = Config()