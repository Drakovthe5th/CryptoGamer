from flask import Flask
from src.web.routes import configure_routes

def create_app():
    app = Flask(__name__)
    configure_routes(app)
    
    # Add security header for Telegram Mini Apps
    @app.after_request
    def add_header(response):
        response.headers['Content-Security-Policy'] = "frame-src 'self' https://telegram.org;"
        return response
    
    return app