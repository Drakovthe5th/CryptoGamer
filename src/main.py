import os
import threading
import asyncio
import logging
import json
from telegram import Update
from telegram.ext import Application
from src.database.firebase import initialize_firebase
from src.integrations.ton import initialize_ton_wallet
from src.features.quests import start_quest_scheduler
from src.features.otc_desk import start_otc_scheduler
from src.features import withdrawal
from src.features.withdrawal import start_withdrawal_processor
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

telegram_application = None

def run_web_server():
    try:
        app = create_app()
        port = int(os.environ.get('PORT', Config.PORT))
        logger.info(f"🌐 Starting web server on port {port}")
        serve(app, host='0.0.0.0', port=port)
    except Exception as e:
        logger.critical(f"Web server failed: {e}")

async def set_webhook():
    try:
        webhook_url = f"https://{Config.RENDER_EXTERNAL_URL}/webhook"
        await telegram_application.bot.set_webhook(
            webhook_url,
            secret_token=Config.TELEGRAM_SECRET,
            drop_pending_updates=True
        )
        logger.info(f"Webhook configured: {webhook_url}")
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        try:
            await telegram_application.bot.delete_webhook()
            logger.info("Webhook deleted as fallback")
        except Exception as fallback_error:
            logger.error(f"Failed to delete webhook: {fallback_error}")

def initialize_background_services():
    try:
        threading.Thread(target=start_quest_scheduler, daemon=True).start()
        logger.info("🎯 Quest scheduler started")
        
        threading.Thread(target=start_otc_scheduler, daemon=True).start()
        logger.info("💱 OTC scheduler started")
        
        threading.Thread(target=start_withdrawal_processor, daemon=True).start()
        logger.info("💸 Withdrawal processor started")
    except Exception as e:
        logger.error(f"Failed to start background services: {e}")

def run_bot():
    global telegram_application
    
    logger.info("🤖 Initializing Telegram bot services...")
    
    try:
        creds_str = os.environ.get('FIREBASE_CREDS', Config.FIREBASE_CREDS)
        firebase_creds = json.loads(creds_str) if isinstance(creds_str, str) else creds_str
        
        if not initialize_firebase(firebase_creds):
            raise RuntimeError("Firebase initialization failed")
        logger.info("🔥 Firebase initialized")
        
        if Config.TON_ENABLED:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(initialize_ton_wallet())
            logger.info("💎 TON wallet initialized")
        else:
            logger.warning("⚠️ TON integration disabled")
        
        initialize_background_services()
        
        telegram_application = Application.builder() \
            .token(Config.TELEGRAM_BOT_TOKEN) \
            .build()
        setup_handlers(telegram_application)
        logger.info("📱 Telegram handlers configured")
        
        if Config.ENV == 'production':
            logger.info("🚀 Starting in PRODUCTION mode")
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
        if telegram_application:
            telegram_application.stop()
            telegram_application.shutdown()
        raise

if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    logger.info("🤖 Bot started in background thread")
    run_web_server()