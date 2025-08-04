from flask import Flask, jsonify

def create_app():
    app = Flask(__name__)
    
    # Health check endpoint
    @app.route('/')
    def health_check():
        return jsonify({
            "status": "running",
            "service": "CryptoGameMiner",
            "version": "1.0.0"
        }), 200
    
    # Webhook endpoint for Telegram
    @app.route('/webhook', methods=['POST'])
    def webhook():
        # Telegram will send updates here in production
        return jsonify({"status": "webhook received"}), 200
    
    return app