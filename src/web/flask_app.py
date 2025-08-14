from flask import Flask, jsonify
from .routes import configure_routes
from flask import send_from_directory

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
    
    @app.after_request
    def add_security_headers(response):
        csp = "default-src 'self'; script-src 'self' https://telegram.org https://libtl.com 'sha256-5Y8b7JhLLcZ6f6dY8eA8d5f5b5f5b5f5b5f5b5f5b5f5b5f5b5f5b5f5b5f5b5f5b';"
        response.headers['Content-Security-Policy'] = csp
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        return response
    
    @app.route('/static/<path:filename>')
    def serve_static(filename):
        response = send_from_directory('static', filename)
        response.headers['Cache-Control'] = 'public, max-age=2592000'  # 30 days
        return response
    
    @app.route('/admin/dashboard')
    def admin_dashboard():
        return jsonify({
            'active_users': get_active_users(),
            'pending_withdrawals': get_pending_withdrawals(),
            'ton_reserves': get_wallet_balance()
        })
    
    @app.after_request
    def add_security_headers(response):
        ...
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'  # Add HSTS
        return response
        
    # Configure all routes
    configure_routes(app)
    
    return app