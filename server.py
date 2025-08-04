import os
import threading
import asyncio
import logging
from telegram import Update
from telegram.ext import Application
from src.database.firebase import initialize_firebase
from src.integrations.nano import initialize_nano_wallet
from src.features.faucets import start_faucet_scheduler
from src.telegram.setup import setup_handlers
from src.web.flask_app import create_app
from config import Config
from waitress import serve
import json

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global application reference
telegram_application = None

def run_web_server():
    """Start the Flask web server"""
    try:
        app = create_app()
        port = int(os.environ.get('PORT', Config.PORT))
        logger.info(f"🌐 Starting web server on port {port}")
        serve(app, host='0.0.0.0', port=port)
    except Exception as e:
        logger.critical(f"Web server failed: {e}")

async def set_webhook():
    """Configure webhook in production environment"""
    try:
        # Construct secure webhook URL
        webhook_url = f"https://{Config.RENDER_EXTERNAL_URL}/webhook"
        
        # Set webhook with secret token
        await telegram_application.bot.set_webhook(
            webhook_url,
            secret_token=Config.TELEGRAM_TOKEN,
            drop_pending_updates=True
        )
        logger.info(f"Webhook configured: {webhook_url}")
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        # Fallback to delete webhook if setup fails
        try:
            await telegram_application.bot.delete_webhook()
            logger.info("Webhook deleted as fallback")
        except Exception as fallback_error:
            logger.error(f"Failed to delete webhook: {fallback_error}")

def initialize_firebase(creds_dict):
    global db, users_ref, transactions_ref, withdrawals_ref, quests_ref
    
    try:
        if not firebase_admin._apps:
            # Handle both file paths and credential dictionaries
            if isinstance(creds_dict, dict):
                cred = credentials.Certificate(creds_dict)
            elif isinstance(creds_dict, str) and os.path.isfile(creds_dict):
                cred = credentials.Certificate(creds_dict)
            else:
                logging.error("Invalid Firebase credentials format")
                return False
            
            firebase_admin.initialize_app(cred)
        
        db = firestore.client()
        users_ref = db.collection('users')
        transactions_ref = db.collection('transactions')
        withdrawals_ref = db.collection('withdrawals')
        quests_ref = db.collection('quests')
        logging.info("Firebase initialized successfully")
        return True
    except Exception as e:
        logging.error(f"Firebase initialization error: {e}")
        return False
        # Propagate error for visibility
        raise

if __name__ == '__main__':
    # Start bot in background thread
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    logger.info("🤖 Bot started in background thread")
    
    # Start web server in main thread
    run_web_server()