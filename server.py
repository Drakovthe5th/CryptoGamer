import os
import threading
import asyncio
import logging
import json
from telegram import Update
from telegram.ext import Application
from src.database.firebase import initialize_firebase
from src.integrations.nano import initialize_nano_wallet
from src.features.faucets import start_faucet_scheduler
from src.telegram.setup import setup_handlers
from src.web.flask_app import create_app
from config import Config
from waitress import serve

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

def run_bot():  # <-- This is the critical function definition
    global telegram_application
    
    logger.info("🤖 Initializing Telegram bot services...")
    
    try:
        # Initialize Firebase - FIXED CREDENTIALS HANDLING
        creds_str = os.environ.get('FIREBASE_CREDS', Config.FIREBASE_CREDS)
        try:
            # Parse JSON if it's a string
            if isinstance(creds_str, str):
                firebase_creds = json.loads(creds_str)
            else:
                firebase_creds = creds_str
        except json.JSONDecodeError:
            logger.error("❌ Failed to parse FIREBASE_CREDS JSON")
            firebase_creds = None
        
        if firebase_creds and initialize_firebase(firebase_creds):
            logger.info("🔥 Firebase initialized")
        else:
            raise RuntimeError("Firebase initialization failed")
        
        # Initialize Nano wallet if seed exists
        if Config.NANO_SEED:
            initialize_nano_wallet(Config.NANO_SEED, Config.REPRESENTATIVE)
            logger.info("💱 Nano wallet initialized")
        else:
            logger.warning("⚠️ NANO_SEED not found - Crypto functions disabled")
        
        # Start background services
        threading.Thread(target=start_faucet_scheduler, daemon=True).start()
        logger.info("⏳ Background services started")
        
        # Set up Telegram bot
        telegram_application = Application.builder().token(Config.TELEGRAM_TOKEN).build()
        setup_handlers(telegram_application)
        logger.info("📱 Telegram handlers configured")
        
        # Configure based on environment
        if Config.ENV == 'production':
            logger.info("🚀 Starting in PRODUCTION mode")
            
            # Create event loop for async webhook setup
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(set_webhook())
        else:
            logger.info("🔧 Starting in DEVELOPMENT mode")
            telegram_application.run_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )
            
    except Exception as e:
        logger.critical(f"❌ Failed to start bot: {e}")
        # Attempt graceful shutdown
        if telegram_application:
            try:
                telegram_application.stop()
                telegram_application.shutdown()
            except Exception:
                pass
        # Propagate error for visibility
        raise

# This is the main entry point
if __name__ == '__main__':
    # Start bot in background thread
    bot_thread = threading.Thread(target=run_bot)  # <-- Now run_bot is defined
    bot_thread.daemon = True
    bot_thread.start()
    logger.info("🤖 Bot started in background thread")
    
    # Start web server in main thread
    run_web_server()