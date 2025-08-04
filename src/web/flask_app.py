from flask import Flask
from src.web.routes import configure_routes
import os

def create_app():
    # Get absolute paths to templates and static directories
    base_dir = os.path.abspath(os.path.dirname(__file__))
    template_dir = os.path.join(base_dir, '../../templates')
    static_dir = os.path.join(base_dir, '../../static')
    
    app = Flask(__name__, 
                template_folder=template_dir,
                static_folder=static_dir)
    
    configure_routes(app)
    
    # Add security header for Telegram Mini Apps
    @app.after_request
    def add_header(response):
        response.headers['Content-Security-Policy'] = "frame-src 'self' https://telegram.org;"
        return response
    
    return app