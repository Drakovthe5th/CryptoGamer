import hashlib
import hmac
import re
import json
import base58
from tonclient.types import ParamsOfVerifySignature, ParamsOfHash
from flask import request
from urllib.parse import parse_qsl
from flask import current_app
from src.integrations.telegram import TelegramIntegration
from src.database.mongo import get_user_data, create_user
from config import config
import logging

logger = logging.getLogger(__name__)

def validate_telegram_data(init_data: str, bot_token: str) -> bool:
    """
    Validate Telegram WebApp init data using HMAC-SHA256 signature
    Reference: https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
    """
    if not init_data:
        return False
    
    try:
        # Parse query string
        parsed_data = parse_qsl(init_data)
        data_dict = {}
        received_hash = None
        
        # Extract hash and build sorted key-value dictionary
        for key, value in parsed_data:
            if key == 'hash':
                received_hash = value
            else:
                data_dict[key] = value
        
        if not received_hash:
            current_app.logger.warning("No hash found in initData")
            return False
        
        # Create data check string
        data_check = "\n".join(
            f"{key}={value}" for key, value in sorted(data_dict.items())
        )
        
        # Generate secret key from bot token
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=bot_token.encode(),
            digestmod=hashlib.sha256
        ).digest()
        
        # Calculate HMAC
        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(calculated_hash, received_hash)
    
    except Exception as e:
        current_app.logger.error(f"Telegram validation failed: {str(e)}")
        return False
    
def get_or_create_user(user_id, username=None):
    """Get user data or create new user if doesn't exist"""
    user = get_user_data(user_id)
    if not user:
        # New user - create with welcome bonus
        user = create_user(user_id, username)
        
        # Show welcome message
        if Telegram.WebApp:
            Telegram.WebApp.showPopup({
                'title': 'Welcome to CryptoGamer!',
                'message': 'You received 2000 GC as a welcome bonus!',
                'buttons': [{'type': 'ok'}]
            })
    
    return user

# In PokerGame class
def validate_action(self, user_id: str, table_id: str, action: str, amount: int = 0) -> bool:
    """Validate if a poker action is legitimate"""
    table = self.tables.get(table_id)
    if not table:
        return False
        
    # Check if it's the player's turn
    current_player = table.players[table.current_player_idx]
    if current_player["user_id"] != user_id:
        return False
        
    # Action-specific validation
    if action == "raise":
        min_raise = table.min_raise
        current_bet = current_player["current_bet"]
        if amount < min_raise or amount > current_player["balance"]:
            return False
            
    # Add more validation logic for other actions
    
    return True

def get_authenticated_user_id():
    """
    Get authenticated user ID from request with multiple fallbacks
    This is a simplified version of the security.py function for use in routes
    """
    try:
        # Check for Telegram WebApp initData
        init_data = request.headers.get('X-Telegram-InitData') or request.args.get('initData')
        if init_data and config.TELEGRAM_TOKEN:
            # Parse user ID from validated initData
            if validate_telegram_data(init_data, config.TELEGRAM_TOKEN):
                parsed = dict(parse_qsl(init_data))
                user_data = parsed.get('user', '{}')
                
                # Extract user ID from JSON string
                try:
                    user_json = json.loads(user_data)
                    return user_json.get('id')
                except json.JSONDecodeError:
                    # Fallback: try to extract ID directly
                    import re
                    id_match = re.search(r'"id":\s*(\d+)', user_data)
                    if id_match:
                        return int(id_match.group(1))
        
        # Check for Authorization header (JWT token)
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(" ")[1]
            try:
                # This would be replaced with actual JWT decoding
                # For now, use a simple implementation
                if token.count('.') == 2:
                    parts = token.split(".")
                    # Simple validation - in production, use proper JWT validation
                    return int(parts[0]) if parts[0].isdigit() else None
            except Exception as e:
                logger.warning(f"JWT decoding failed: {str(e)}")
        
        # Check session cookies
        session_id = request.cookies.get('session_id')
        if session_id:
            try:
                return int(session_id.split("_")[0])
            except:
                pass
                
        # Check JSON body
        if request.json:
            user_id = request.json.get('user_id')
            if user_id:
                return int(user_id)
                
        # Check query parameters
        user_id = request.args.get('user_id')
        if user_id:
            return int(user_id)
            
        logger.warning("No valid user ID found in request")
        return None
        
    except Exception as e:
        logger.error(f"Error getting authenticated user ID: {str(e)}")
        return None

def validate_ton_address(address: str) -> bool:
    """
    Validate a TON wallet address format
    """
    if not address:
        return False
    
    # Check for common TON address formats
    ton_patterns = [
        r'^[0-9a-fA-F]{64}$',  # Raw hex format
        r'^[0-9a-zA-Z+/=_-]{48}$',  # Base64 format
        r'^(0|1|2|3):[0-9a-fA-F]{64}$',  # User-friendly format
        r'^EQ[0-9a-zA-Z+/=_-]{48}$'  # EQ-prefixed format
    ]
    
    return any(re.match(pattern, address) for pattern in ton_patterns)

def verify_wallet_signature(public_key: str, signature: str, message: str) -> bool:
    """
    Verify a wallet signature using TON client
    """
    try:
        # Initialize TON client if not already done
        if not hasattr(verify_wallet_signature, 'client'):
            from src.integrations.tonclient import get_ton_client
            verify_wallet_signature.client = get_ton_client()
        
        # Verify the signature
        result = verify_wallet_signature.client.crypto.verify_signature(
            ParamsOfVerifySignature(
                signed=message,
                public=public_key,
                signature=signature
            )
        )
        
        return result.unsigned == message
    except Exception as e:
        logger.error(f"Signature verification failed: {str(e)}")
        return False

def get_wallet_auth_data():
    """
    Extract wallet authentication data from request
    """
    try:
        # Check for wallet auth in headers
        wallet_address = request.headers.get('X-Wallet-Address')
        wallet_signature = request.headers.get('X-Wallet-Signature')
        wallet_message = request.headers.get('X-Wallet-Message')
        wallet_public_key = request.headers.get('X-Wallet-Public-Key')
        
        # Check for wallet auth in JSON body
        if not all([wallet_address, wallet_signature, wallet_message]):
            if request.json:
                wallet_address = request.json.get('wallet_address')
                wallet_signature = request.json.get('wallet_signature')
                wallet_message = request.json.get('wallet_message')
                wallet_public_key = request.json.get('wallet_public_key')
        
        return {
            'address': wallet_address,
            'signature': wallet_signature,
            'message': wallet_message,
            'public_key': wallet_public_key
        }
    except Exception as e:
        logger.error(f"Error getting wallet auth data: {str(e)}")
        return None

def authenticate_wallet():
    """
    Authenticate a wallet connection request
    """
    # Get Telegram user ID first
    telegram_user_id = get_authenticated_user_id()
    if not telegram_user_id:
        return None, "Telegram authentication required"
    
    # Get wallet auth data
    wallet_data = get_wallet_auth_data()
    if not wallet_data or not all(wallet_data.values()):
        return None, "Missing wallet authentication data"
    
    # Validate TON address format
    if not validate_ton_address(wallet_data['address']):
        return None, "Invalid TON address format"
    
    # Verify signature if provided
    if wallet_data['signature'] and wallet_data['message']:
        if not verify_wallet_signature(
            wallet_data['public_key'] or wallet_data['address'],
            wallet_data['signature'],
            wallet_data['message']
        ):
            return None, "Invalid wallet signature"
    
    # Return the wallet address and telegram user ID
    return {
        'telegram_user_id': telegram_user_id,
        'wallet_address': wallet_data['address'],
        'wallet_public_key': wallet_data['public_key']
    }, None

# Maintain backward compatibility with existing imports
validate_init_data = validate_telegram_data