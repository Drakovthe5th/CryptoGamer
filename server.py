import os
import sys
import datetime
import asyncio
import logging
import atexit
import base64
import json
from flask import Flask, request, Blueprint, jsonify, render_template, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
from celery import Celery

# Import from main.py instead of flask_app.py
from main import app as main_app, initialize_production_app, shutdown_production_app

# Configure production logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/cryptogamer/app.log') if os.path.exists('/var/log/cryptogamer') else logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Production imports with proper error handling
try:
    from src.database.mongo import initialize_mongodb, get_user_data, save_user_data, update_balance, track_ad_reward
    from src.utils.security import get_user_id, validate_telegram_hash, is_abnormal_activity
    from src.features.quests import claim_daily_bonus, record_click
    from src.features.ads import ad_manager
    MONGO_AVAILABLE = True
except ImportError as e:
    logger.error(f"Database modules not available: {e}")
    MONGO_AVAILABLE = False

try:
    from src.integrations.ton import (
        initialize_ton_wallet,
        process_ton_withdrawal,
        ton_wallet,
        get_wallet_status
    )
    TON_AVAILABLE = True
except ImportError as e:
    logger.error(f"TON integration not available: {e}")
    TON_AVAILABLE = False

try:
    from games.games import games_bp
    GAMES_AVAILABLE = True
except ImportError as e:
    logger.error(f"Games blueprint not available: {e}")
    GAMES_AVAILABLE = False

from config import config

# Use the app instance from main.py
app = main_app
CORS(app, origins="*")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent', logger=True, engineio_logger=True)

# Register games blueprint with proper error handling
if GAMES_AVAILABLE:
    app.register_blueprint(games_bp, url_prefix='/games')
    logger.info("Games blueprint registered successfully")
else:
    # Fallback blueprint for games service
    games_fallback_bp = Blueprint('games_fallback', __name__, url_prefix='/games')
    
    @games_fallback_bp.route('/', defaults={'path': ''})
    @games_fallback_bp.route('/<path:path>')
    def games_service_unavailable(path):
        return jsonify({
            'error': 'Games service temporarily unavailable',
            'status': 'maintenance',
            'timestamp': datetime.datetime.utcnow().isoformat()
        }), 503
        
    app.register_blueprint(games_fallback_bp)
    logger.warning("Using fallback games blueprint")

# Celery configuration for production
celery = Celery(
    app.name, 
    broker=os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.environ.get('REDIS_URL', 'redis://localhost:6379/1'),
    broker_connection_retry_on_startup=True
)

# Production middleware
@app.before_request
def production_security_middleware():
    """Production security middleware"""
    # Skip security for static files, health checks, and known public endpoints
    if (request.path.startswith('/static') or 
        request.path in ['/health', '/status', '/'] or
        request.path.startswith('/games/static')):
        return
    
    # API security checks
    if request.path.startswith('/api'):
        try:
            # Telegram authentication
            init_data = request.headers.get('X-Telegram-InitData')
            if not init_data:
                return jsonify({'error': 'Telegram authentication required'}), 401
            
            if not validate_telegram_hash(init_data, config.TELEGRAM_TOKEN):
                return jsonify({'error': 'Invalid Telegram authentication'}), 401
                
        except Exception as e:
            logger.error(f"Security middleware error: {e}")
            return jsonify({'error': 'Security check failed'}), 500

# Core production routes
@app.route('/')
def production_root():
    """Production root endpoint"""
    return jsonify({
        'service': 'CryptoGameMiner',
        'version': '1.0.0',
        'status': 'running',
        'environment': config.ENV,
        'timestamp': datetime.datetime.utcnow().isoformat()
    })

@app.route('/status')
def production_status():
    """Comprehensive system status"""
    return jsonify({
        "status": "running",
        "service": "CryptoGameMiner",
        "version": "1.0.0",
        "environment": config.ENV,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "components": {
            "mongodb": MONGO_AVAILABLE,
            "ton_blockchain": TON_AVAILABLE,
            "games_service": GAMES_AVAILABLE,
            "maintenance": MAINTENANCE_AVAILABLE if 'MAINTENANCE_AVAILABLE' in globals() else False
        },
        "features": {
            "games": config.FEATURE_GAMES,
            "ads": config.FEATURE_ADS,
            "otc": config.FEATURE_OTC
        }
    })

@app.route('/health')
def production_health_check():
    """Production health check with dependency verification"""
    try:
        # Check MongoDB connectivity
        mongo_healthy = False
        if MONGO_AVAILABLE:
            try:
                from src.database.mongo import db
                mongo_healthy = db.is_connected() if hasattr(db, 'is_connected') else True
            except:
                mongo_healthy = False
        
        # Check TON status
        ton_healthy = False
        if TON_AVAILABLE and config.TON_ENABLED:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                status = loop.run_until_complete(get_wallet_status())
                ton_healthy = status.get('healthy', False)
            except:
                ton_healthy = False
        
        # Determine overall status
        status = 'healthy'
        if not mongo_healthy:
            status = 'degraded'
        if config.TON_ENABLED and not ton_healthy:
            status = 'degraded'
        
        return jsonify({
            'status': status,
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'dependencies': {
                'mongodb': mongo_healthy,
                'ton_blockchain': ton_healthy,
                'games_service': GAMES_AVAILABLE
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': 'Health check failure',
            'timestamp': datetime.datetime.utcnow().isoformat()
        }), 500

# WebSocket events for production
@socketio.on('connect')
def handle_production_connect():
    """Production WebSocket connection handler"""
    try:
        user_id = get_user_id(request) if 'get_user_id' in globals() else None
        if user_id:
            join_room(f"user_{user_id}")
            emit('status', {'message': 'Connected to production server', 'timestamp': datetime.datetime.utcnow().isoformat()})
            logger.info(f"User {user_id} connected via WebSocket")
        else:
            emit('error', {'message': 'Authentication required'})
    except Exception as e:
        logger.error(f"WebSocket connect error: {e}")
        emit('error', {'message': 'Connection failed'})

@socketio.on('disconnect')
def handle_production_disconnect():
    """Production WebSocket disconnect handler"""
    try:
        user_id = get_user_id(request) if 'get_user_id' in globals() else None
        if user_id:
            logger.info(f"User {user_id} disconnected from WebSocket")
    except Exception as e:
        logger.error(f"WebSocket disconnect error: {e}")

# Production error handlers
@app.errorhandler(404)
def production_not_found(error):
    return jsonify({
        'error': 'Endpoint not found',
        'path': request.path,
        'timestamp': datetime.datetime.utcnow().isoformat()
    }), 404

@app.errorhandler(500)
def production_internal_error(error):
    logger.error(f"Production server error: {error}")
    return jsonify({
        'error': 'Internal server error',
        'timestamp': datetime.datetime.utcnow().isoformat()
    }), 500

@app.errorhandler(503)
def production_service_unavailable(error):
    return jsonify({
        'error': 'Service temporarily unavailable',
        'timestamp': datetime.datetime.utcnow().isoformat()
    }), 503

# Production shutdown handler
def production_shutdown():
    """Production-grade shutdown procedure"""
    logger.info("Initiating production shutdown sequence...")
    try:
        shutdown_production_app()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    logger.info("Production shutdown completed")

atexit.register(production_shutdown)

# Production application factory
def create_production_app():
    """Create production-ready Flask application"""
    app = main_app
    
    # Production configuration
    app.config['DEBUG'] = False
    app.config['TESTING'] = False
    app.config['PREFERRED_URL_SCHEME'] = 'https'
    
    # Render-specific settings
    if os.getenv('RENDER', False):
        app.config['SERVER_NAME'] = config.RENDER_URL
        app.config['TON_ENABLED'] = os.getenv('TON_FORCE_INIT', 'false').lower() == 'true'
    
    return app

if __name__ == '__main__':
    # Production initialization
    try:
        logger.info("Starting production initialization...")
        
        # Initialize production application
        app = create_production_app()
        
        # Initialize production services
        if not initialize_production_app():
            logger.critical("Production initialization failed")
            sys.exit(1)
            
        # Initialize MongoDB
        if MONGO_AVAILABLE and not initialize_mongodb():
            logger.critical("MongoDB initialization failed")
            sys.exit(1)
        
        logger.info("Production initialization completed successfully")
        
        # Start production server
        port = int(os.environ.get('PORT', 10000))
        logger.info(f"Starting production server on port {port}")
        
        # Use gevent for production
        from gevent import pywsgi
        from geventwebsocket.handler import WebSocketHandler
        
        server = pywsgi.WSGIServer(
            ('0.0.0.0', port), 
            app, 
            handler_class=WebSocketHandler,
            log=logger,
            error_log=logger
        )
        
        logger.info("Production server is running")
        server.serve_forever()
        
    except Exception as e:
        logger.critical(f"Production startup failed: {e}")
        sys.exit(1)