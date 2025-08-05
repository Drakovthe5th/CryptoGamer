import os
import threading
import logging
from src.main import run_bot
from src.web.flask_app import create_app
from waitress import serve
from config import Config

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def run_web_server():
    app = create_app()
    port = int(os.getenv('PORT', Config.PORT))
    logger.info(f"🌐 Starting web server on port {port}")
    serve(app, host='0.0.0.0', port=port)

if __name__ == '__main__':
    # Start bot in background thread
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    logger.info("🤖 Bot started in background thread")
    
    # Start web server in main thread
    run_web_server()