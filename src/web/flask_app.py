from flask import Flask, jsonify
from .routes import configure_routes

def create_app():
    app = Flask(__name__)
    
    # Health check endpoint
    @app.route('/')
    def health_check():
        return jsonify({
            "status": "running",
            "service": "CryptoGameMiner",
            "version": "1.0.0",
            "crypto": "TON"
        }), 200
    
    # Configure all routes
    configure_routes(app)
    
    return app