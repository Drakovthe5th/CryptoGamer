import os
import threading
import asyncio
import logging
from telegram.ext import Application
from src.database.firebase import initialize_firebase
from src.integrations.nano import initialize_nano_wallet
from src.features.faucets import start_faucet_scheduler
from src.telegram.setup import setup_handlers
from config import config

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global application reference
application = None

async def set_webhook():
    """Properly configure webhook in production environment"""
    try:
        # Construct secure webhook URL with token
        webhook_url = f"https://{config.RENDER_EXTERNAL_URL}{config.WEBHOOK_PATH}"
        
        # Set webhook with secret token for verification
        await application.bot.set_webhook(
            webhook_url,
            secret_token=config.TELEGRAM_TOKEN,
            drop_pending_updates=True
        )
        logger.info(f"Webhook configured successfully: {webhook_url}")
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        # Attempt to delete webhook if setup fails
        try:
            await application.bot.delete_webhook()
            logger.info("Webhook deleted as fallback")
        except Exception as fallback_error:
            logger.error(f"Failed to delete webhook: {fallback_error}")

def run_bot():
    global application
    
    logger.info("Initializing services...")
    
    try:
        # Initialize Firebase
        initialize_firebase(config.FIREBASE_CREDS)
        logger.info("Firebase initialized")
        
        # Initialize Nano wallet if seed exists
        if config.NANO_SEED:
            initialize_nano_wallet(config.NANO_SEED, config.REPRESENTATIVE)
            logger.info("Nano wallet initialized")
        else:
            logger.warning("NANO_SEED not found - Nano functions disabled")
        
        # Start background services
        threading.Thread(target=start_faucet_scheduler, daemon=True).start()
        logger.info("Background services started")
        
        # Set up Telegram bot
        application = Application.builder().token(config.TELEGRAM_TOKEN).build()
        setup_handlers(application)
        logger.info("Telegram handlers configured")
        
        # Configure based on environment
        if config.ENV == 'production':
            logger.info("Starting in PRODUCTION mode with webhook")
            
            # Create event loop for async webhook setup
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(set_webhook())
            
            # Start web server (handled separately by Render)
        else:
            logger.info("Starting in DEVELOPMENT mode with polling")
            application.run_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )
            
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
        # Attempt graceful shutdown
        if application:
            try:
                application.stop()
                application.shutdown()
            except Exception:
                pass
        # Propagate error for visibility
        raise

# Entry point for worker service
if __name__ == '__main__':
    run_bot()