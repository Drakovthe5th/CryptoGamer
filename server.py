import threading
from src.web.flask_app import create_app
from src.main import run_bot
from waitress import serve

# Initialize Flask app
app = create_app()

# Start bot in background thread
bot_thread = threading.Thread(target=run_bot)
bot_thread.daemon = True
bot_thread.start()

if __name__ == '__main__':
    # Start web server
    serve(app, host='0.0.0.0', port=config.PORT)