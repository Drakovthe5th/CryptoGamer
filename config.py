import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Core Configuration
    ENV = os.getenv("ENV", "development")
    PORT = int(os.getenv("PORT", 5000))
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Telegram Bot Configuration
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7774390892:AAEvc3PcwU99KWVcC_bqYRpj0V7mt68KpP8")
    ADMIN_ID = int(os.getenv("ADMIN_ID", "7255897207"))
    BOT_USERNAME = os.getenv("BOT_USERNAME", "https://t.me/Got3dBot")
    WEBHOOK_SECRET = TELEGRAM_TOKEN
    
    # Firebase Configuration
    FIREBASE_CREDS = json.loads(os.getenv("FIREBASE_CREDS")) if os.getenv("FIREBASE_CREDS") else {
        "type": "service_account",
        "project_id": "crptominerbot",
        "private_key_id": "bf5b5063f1a2465e994bbed99d7a48eb1fa4d117",
        "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace('\\n', '\n'),
        "client_email": "firebase-adminsdk-fbsvc@crptominerbot.iam.gserviceaccount.com",
        "client_id": "111588734777623513052",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40crptominerbot.iam.gserviceaccount.com"
    }
    
    # TON Blockchain Configuration
    TON_ENABLED = os.getenv("TON_ENABLED", "true").lower() == "true"
    TON_NETWORK = os.getenv("TON_NETWORK", "mainnet")
    TON_API_KEY = os.getenv("TON_API_KEY", "7b0ec513486288d686a9174606e31fea6c16e6ab22245ed6ba9e3b9720777578")
    TON_WALLET_MNEMONIC = os.getenv("TON_WALLET_MNEMONIC", "").split()
    TON_PRIVATE_KEY = os.getenv("TON_PRIVATE_KEY", "MHQCAQEEIL2hWPOyceEn0nFgqrxPsQ4ys+YEyCpyo8LDzEcgjt2qoAcGBSuBBAAKoUQDQgAEWtK9cMVBQa9pS+DwbyrsvRIiwGsm1nzlN6K2nYrPWZ3altwVjPcdJe32NXTCVSjm4LSoTTpXEbt2cV3NpZtN8A==")
    TON_PUBLIC_KEY = os.getenv("TON_PUBLIC_KEY", "MFYwEAYHKoZIzj0CAQYFK4EEAAoDQgAEWtK9cMVBQa9pS+DwbyrsvRIiwGsm1nzlN6K2nYrPWZ3altwVjPcdJe32NXTCVSjm4LSoTTpXEbt2cV3NpZtN8A==")
    TON_HOT_WALLET = os.getenv("TON_HOT_WALLET", "UQCbkEuq1sOJRIaXPM4jnzRQs0cjEPAr_C_pmDop_ZdT5V4_")
    TON_ADMIN_ADDRESS = os.getenv("TON_ADMIN_ADDRESS", "UQCbkEuq1sOJRIaXPM4jnzRQs0cjEPAr_C_pmDop_ZdT5V4_")
    TONSCAN_URL = "https://tonscan.org" if TON_NETWORK == "mainnet" else "https://testnet.tonscan.org"
    
    # OTC Desk Configuration
    FEATURE_OTC = os.getenv("FEATURE_OTC", "true").lower() == "true"
    OTC_FEE_PERCENT = float(os.getenv("OTC_FEE_PERCENT", 3.0))
    MIN_OTC_FEE = float(os.getenv("MIN_OTC_FEE", 0.50))
    OTC_RATES = {
        "USD": float(os.getenv("OTC_USD_RATE", 6.80)),
        "EUR": float(os.getenv("OTC_EUR_RATE", 6.20)),
        "KES": float(os.getenv("OTC_KES_RATE", 950.0))
    }
    
    # Payment Processors
    FEATURE_ADS = os.getenv("FEATURE_ADS", "true").lower() == "true"
    MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY", "")
    MPESA_CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET", "")
    MPESA_BUSINESS_SHORTCODE = os.getenv("MPESA_BUSINESS_SHORTCODE", "174379")
    MPESA_INITIATOR_NAME = os.getenv("MPESA_INITIATOR_NAME", "")
    MPESA_SECURITY_CREDENTIAL = os.getenv("MPESA_SECURITY_CREDENTIAL", "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919")
    PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "your_paypal_id")
    PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "your_paypal_secret")
    PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID", "your_webhook_id")
    
    # Rewards Configuration (in TON)
    FEATURE_GAMES = os.getenv("FEATURE_GAMES", "true").lower() == "true"
    REWARDS = {
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
    GAME_COOLDOWN = int(os.getenv("GAME_COOLDOWN", 30))  # minutes
    FAUCET_COOLDOWN = int(os.getenv("FAUCET_COOLDOWN", 24))  # hours
    MIN_WITHDRAWAL = float(os.getenv("MIN_WITHDRAWAL", 0.1))  # TON
    
    # Web Server Configuration
    RENDER_URL = os.getenv("RENDER_URL", "crptgameminer.onrender.com")
    RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "crptgameminer.onrender.com")
    
    # Ad Platforms
    AD_PLATFORMS = {
        "coinzilla": os.getenv("COINZILLA_ZONE_ID", "your_coinzilla_zone"),
        "propeller": os.getenv("PROPELLER_ZONE_ID", "your_propeller_zone"),
        "a-ads": os.getenv("A_ADS_ZONE_ID", "your_aads_zone")
    }
    
    # Security Limits
    FREE_DAILY_EARN_LIMIT = 0.5  # TON per user
    USER_DAILY_WITHDRAWAL_LIMIT = 5.0  # TON per user
    DAILY_WITHDRAWAL_LIMIT = 100.0  # TON system-wide
    
    # Wallet Thresholds
    MIN_HOT_BALANCE = 5.0  # TON (triggers refill)
    MIN_ADMIN_BALANCE = 50.0  # TON (triggers alert)
    
    # Alerting
    ALERT_WEBHOOK = os.getenv("ALERT_WEBHOOK", "")  # Slack/Telegram webhook

# Create singleton instance
config = Config()