from flask import Flask
from src.web.routes import configure_routes
import os

def create_app():
    # Get absolute path to templates directory
    base_dir = os.path.abspath(os.path.dirname(__file__))
    template_dir = os.path.join(base_dir, '../../templates')
    
    app = Flask(__name__, template_folder=template_dir)
    configure_routes(app)
    
    # Add security header for Telegram Mini Apps
    @app.after_request
    def add_header(response):
        response.headers['Content-Security-Policy'] = "frame-src 'self' https://telegram.org;"
        return response
    
    return app