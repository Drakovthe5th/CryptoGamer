import os
import threading
import asyncio
import logging
import json
import time
import binascii
from telegram import Update
from telegram.ext import Application
from src.database.mongo import initialize_mongodb, db
from src.integrations.ton import (
    initialize_ton_wallet, 
    close_ton_wallet,
    get_wallet_status,
    validate_ton_address
)
from src.telegram.stars import start_stars_service
from src.features.quests import start_quest_scheduler
from src.features.otc_desk import start_otc_scheduler
from src.integrations.withdrawal import start_withdrawal_processor
from src.telegram.setup import setup_handlers
from src.utils.maintenance import start_monitoring 
from src.telegram.config_manager import config_manager
from src.integrations.telegram import telegram_client
from config import config
import atexit

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

telegram_application = None

def run_web_server():
    """Production-grade web server runner using Gunicorn"""
    try:
        from app import create_app
        app = create_app()
        port = int(os.environ.get('PORT', config.PORT))
        logger.info(f"🌐 Starting production web server on port {port}")
        
        # Use Gunicorn programmatically
        from gunicorn.app.base import BaseApplication
        
        class FlaskApplication(BaseApplication):
            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super().__init__()
            
            def load_config(self):
                for key, value in self.options.items():
                    self.cfg.set(key, value)
            
            def load(self):
                return self.application
        
        options = {
            'bind': f'0.0.0.0:{port}',
            'workers': 4,
            'worker_class': 'gevent',
            'timeout': 300
        }
        FlaskApplication(app, options).run()
        
    except Exception as e:
        logger.critical(f"Web server failed: {e}")
        raise RuntimeError("Web server startup failed") from e

async def set_webhook():
    """Configure Telegram webhook with production-grade error handling"""
    if not telegram_application:
        return
        
    try:
        webhook_url = f"https://{config.RENDER_EXTERNAL_URL}/webhook"
        await telegram_application.bot.set_webhook(
            webhook_url,
            secret_token=config.TELEGRAM_SECRET,
            drop_pending_updates=True
        )
        logger.info(f"✅ Production webhook configured: {webhook_url}")
    except Exception as e:
        logger.error(f"⚠️ Error setting webhook: {e}")
        try:
            await telegram_application.bot.delete_webhook()
            logger.warning("🗑️ Webhook deleted as fallback")
        except Exception as fallback_error:
            logger.error(f"❌ Failed to delete webhook: {fallback_error}")

async def validate_ton_config():
    """Production-grade TON configuration validation"""
    if config.ENV == 'production':
        # Validate credentials
        if not config.TON_PRIVATE_KEY and not config.TON_MNEMONIC:
            raise RuntimeError("Production requires TON wallet credentials")
        
        # Validate network
        if config.TON_NETWORK not in ['mainnet', 'testnet']:
            raise ValueError("Invalid TON_NETWORK configuration")
        
        # Validate wallet address
        if config.TON_HOT_WALLET and not validate_ton_address(config.TON_HOT_WALLET):
            raise ValueError("Invalid TON hot wallet address")
        
async def initialize_telegram_config():
    """Initialize Telegram configuration on startup"""
    try:
        await config_manager.get_client_config(force_refresh=True)
        logger.info("Telegram client configuration initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Telegram config: {str(e)}")

def validate_production_config():
    """Comprehensive production configuration validation"""
    if config.ENV == 'production':
        # Validate MongoDB connection
        if not db.is_connected():
            raise ConnectionError("Production database not connected")
        
        # Validate TON configuration
        if config.TON_ENABLED:
            asyncio.run(validate_ton_config())
            
        # Validate Telegram configuration
        if not config.TELEGRAM_TOKEN or not config.TELEGRAM_SECRET:
            raise ValueError("Telegram credentials are required in production")
            
        logger.info("✅ Production configuration validated")

def initialize_background_services():
    """Start background services with production monitoring"""
    try:
        # Start services with thread monitoring
        services = {
            "Quest Scheduler": start_quest_scheduler,
            "OTC Scheduler": start_otc_scheduler,
            "Withdrawal Processor": start_withdrawal_processor
        }
        
        for name, starter in services.items():
            thread = threading.Thread(target=starter, daemon=True)
            thread.start()
            logger.info(f"🚀 {name} started (Thread ID: {thread.ident})")
        
        # Security monitoring
        if config.ENABLE_SECURITY_MONITOR:
            from src.utils.security import start_security_monitoring
            security_thread = threading.Thread(
                target=start_security_monitoring, 
                daemon=True,
                name="SecurityMonitor"
            )
            security_thread.start()
            logger.info(f"🔒 Security monitoring started (Thread ID: {security_thread.ident})")
            
        logger.info("✅ All background services started")
    except Exception as e:
        logger.error(f"❌ Failed to start background services: {e}")
        raise

async def initialize_ton_with_retry(max_retries=3):
    """Production-grade TON initialization with exponential backoff"""
    for attempt in range(max_retries):
        try:
            logger.info(f"🔑 Initializing TON wallet (Attempt {attempt+1}/{max_retries})")
            success = await initialize_ton_wallet()
            if success:
                status = await get_wallet_status()
                logger.info(f"💎 TON wallet initialized | Balance: {status.get('balance', 0):.6f} TON")
                return True
        except Exception as e:
            logger.error(f"TON initialization error: {str(e)}")
        
        if attempt < max_retries - 1:
            wait_time = 2 ** (attempt + 1)
            logger.warning(f"⏳ Retrying TON initialization in {wait_time}s...")
            await asyncio.sleep(wait_time)
    
    logger.critical("❌ TON wallet initialization failed after all retries")
    return False

async def production_initialization():
    """Production-grade service initialization sequence"""
    logger.info("🚀 Starting production initialization sequence")
    
    # Phase 1: Configuration validation
    try:
        validate_production_config()
        logger.info("✅ Configuration validated")
    except Exception as e:
        logger.critical(f"❌ Configuration validation failed: {str(e)}")
        return False

    # Phase 2: MongoDB initialization
    try:
        if not initialize_mongodb():
            raise ConnectionError("MongoDB initialization failed")
        logger.info("✅ MongoDB initialized")
    except Exception as e:
        logger.critical(f"❌ Database initialization failed: {str(e)}")
        return False

    # Phase 3: TON wallet initialization (with retries)
    if config.TON_ENABLED:
        if not await initialize_ton_with_retry():
            config.TON_ENABLED = False
            logger.warning("⚠️ Continuing in degraded mode without TON")
    else:
        logger.info("⏭️ TON integration disabled by configuration")

    # Phase 4: Background services
    try:
        initialize_background_services()
    except Exception as e:
        logger.error(f"⚠️ Background services partially failed: {str(e)}")

    # Phase 5: Stars service
    try:
        await start_stars_service()
        logger.info("✅ Telegram Stars service initialized")
    except Exception as e:
        logger.error(f"⚠️ Stars service initialization failed: {str(e)}")
    
    return True

def shutdown_app():
    """Graceful shutdown procedure for production"""
    logger.info("🛑 Initiating production shutdown sequence...")
    
    # Close TON wallet connection
    if config.TON_ENABLED:
        logger.info("🔒 Closing TON wallet connection...")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(close_ton_wallet())
            logger.info("✅ TON wallet closed")
        except Exception as e:
            logger.error(f"❌ Error closing TON wallet: {e}")
        finally:
            loop.close()
    
    logger.info("✅ Production shutdown complete")

async def run_bot():
    """Main bot execution with production-grade error handling"""
    global telegram_application
    
    logger.info("🤖 Starting Telegram bot services...")
    
    try:
        # Production initialization
        if not await production_initialization():
            logger.critical("❌ Production initialization failed")
            return False

        # Initialize Telegram application
        telegram_application = Application.builder() \
            .token(config.TELEGRAM_TOKEN) \
            .build()
        setup_handlers(telegram_application)
        logger.info("✅ Telegram handlers configured")
        
        # Configure webhook for production
        if config.ENV == 'production':
            logger.info("🚀 Starting in PRODUCTION mode")
            await set_webhook()
            return True
        else:
            logger.info("🔧 Starting in DEVELOPMENT mode")
            await telegram_application.run_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )
            return True
            
    except Exception as e:
        logger.critical(f"❌ Bot startup failed: {e}")
        if telegram_application:
            await telegram_application.stop()
            await telegram_application.shutdown()
        return False

async def main_async():
    """Asynchronous main entry point with production monitoring"""
    # Register shutdown handler
    atexit.register(shutdown_app)
    initialize_telegram_config()
    
    # Start bot as asynchronous task
    bot_task = asyncio.create_task(run_bot())
    logger.info("🤖 Bot startup initiated")
    
    # Production monitoring
    if config.ENV == 'production':
        logger.info("📊 Starting production monitoring")
        monitoring_task = asyncio.create_task(start_monitoring())
    
    # Start web server in main thread
    try:
        run_web_server()
    except Exception as e:
        logger.critical(f"❌ Web server crashed: {e}")
    finally:
        # Wait for bot task to complete
        await bot_task
        if config.ENV == 'production':
            await monitoring_task

if __name__ == '__main__':
    # Create and run event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        logger.info("🏁 Starting production application")
        loop.run_until_complete(main_async())
    except KeyboardInterrupt:
        logger.info("🛑 Shutdown requested by user")
    except Exception as e:
        logger.critical(f"❌ Catastrophic failure: {e}")
    finally:
        # Cleanup resources
        tasks = asyncio.all_tasks(loop)
        for task in tasks:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        loop.close()
        logger.info("✅ Application fully stopped")