import os
import json
import logging

class Config:
        # Ad configuration
    AD_ENABLED = os.getenv('AD_ENABLED', 'true').lower() == 'true'
    AD_REWARD_AMOUNT = float(os.getenv('AD_REWARD_AMOUNT', 0.01))
    WEEKEND_BOOST_MULTIPLIER = float(os.getenv('WEEKEND_BOOST', 1.5))
    
    # Platform IDs
    COINZILLA_PUB_ID = os.getenv('COINZILLA_PUB_ID')
    PROPELLER_ZONE_ID = os.getenv('PROPELLER_ZONE_ID')
    A_ADS_ZONE_ID = os.getenv('A_ADS_ZONE_ID')
    
    # Geo-targeting preferences
    HIGH_CPM_COUNTRIES = ['US', 'CA', 'UK', 'AU', 'DE', 'FR', 'JP', 'SG']
    
    # Ad refresh settings
    AD_REFRESH_INTERVAL = int(os.getenv('AD_REFRESH_MIN', 60))  # Minutes

    # Load environment variables
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    NANO_SEED = os.getenv('NANO_SEED')
    CMC_API_KEY = os.getenv('CMC_API_KEY')
    REPRESENTATIVE = "nano_3ur1a7tsboowmxokmhfppfpcctoiuuwhhgyhzf6oux8edzhp61nqkoyzb3os"  # Default representative
    FAUCET_COOLDOWN = int(os.getenv('FAUCET_COOLDOWN', 24))  # hours
    
    # M-Pesa configuration
    MPESA_CONSUMER_KEY = os.getenv('MPESA_CONSUMER_KEY')
    MPESA_SANDBOX = os.getenv('MPESA_SANDBOX', 'true').lower() == 'true'
    MPESA_CONSUMER_SECRET = os.getenv('MPESA_CONSUMER_SECRET')
    MPESA_SHORTCODE = os.getenv('MPESA_SHORTCODE', '174379')
    MPESA_LNM_SHORTCODE = os.getenv('MPESA_LNM_SHORTCODE', '174379')
    MPESA_LNM_PASSKEY = os.getenv('MPESA_LNM_PASSKEY')
    
    # PayPal configuration
    PAYPAL_CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID')
    PAYPAL_CLIENT_SECRET = os.getenv('PAYPAL_CLIENT_SECRET')
    PAYPAL_MODE = os.getenv('PAYPAL_MODE', 'sandbox')  # sandbox or live
    PAYPAL_WEBHOOK_ID = os.getenv('PAYPAL_WEBHOOK_ID')
    
    # Application settings
    ENV = os.getenv('ENV', 'production')
    PORT = int(os.getenv('PORT', 10000))
    RENDER_EXTERNAL_URL = os.getenv('RENDER_EXTERNAL_URL', 'crptgameminer.onrender.com')
    REPRESENTATIVE = os.getenv('NANO_REPRESENTATIVE', 'nano_3ur1a7tsboowmxokmhfppfpcctoiuuwhhgyhzf6oux8edzhp61nqkoyzb3os')
    WEBHOOK_PATH = "/webhook"
    
    # Game configuration
    MIN_WITHDRAWAL = float(os.getenv('MIN_WITHDRAWAL', 0.1))
    GAME_COOLDOWN = int(os.getenv('GAME_COOLDOWN', 60))  # minutes
    REWARDS = {
        'mining_reward': float(os.getenv('MINING_REWARD', 0.01)),
        'trivia_reward': float(os.getenv('TRIVIA_REWARD', 0.05)),
        'puzzle_reward': float(os.getenv('PUZZLE_REWARD', 0.02))
    }
    
    # Firebase configuration
    @property
    def FIREBASE_CREDS(self):
        creds_json = os.getenv('FIREBASE_CREDS_JSON')
        if not creds_json:
            logging.error("FIREBASE_CREDS_JSON environment variable not set!")
            return {}
        try:
            return json.loads(creds_json)
        except json.JSONDecodeError:
            logging.error("Failed to parse FIREBASE_CREDS_JSON")
            return {}

# Singleton instance
config = Config()