import hashlib, hmac
from functools import wraps, lru_cache
from flask import request, jsonify
from datetime import datetime, timedelta
from src.database.mongo import db, get_user_data
from src.utils.security import is_abnormal_activity
from urllib.parse import parse_qs
import datetime
import re
from config import config
import logging

logger = logging.getLogger(__name__)

def validate_ton_address(address: str) -> bool:
    """Validate TON wallet address format"""
    pattern = r'^UQ[0-9a-zA-Z]{48}$'
    return re.match(pattern, address) is not None

def validate_mpesa_number(number: str) -> bool:
    """Validate M-Pesa number format (Kenya)"""
    pattern = r'^2547\d{8}$'
    return re.match(pattern, number) is not None

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_amount(amount: str, min_amount: float) -> bool:
    """Validate amount format and minimum"""
    try:
        amount_float = float(amount)
        return amount_float >= min_amount
    except ValueError:
        return False

def validate_json_input(schema):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Check content type
            if not request.is_json:
                return jsonify({'error': 'Content type must be application/json'}), 400
            
            data = request.get_json()
            errors = {}
            
            for field, rules in schema.items():
                value = data.get(field)
                
                # Check required
                if rules.get('required') and value is None:
                    errors[field] = 'This field is required'
                    continue
                
                # Type checking
                if 'type' in rules:
                    if rules['type'] == 'int':
                        try:
                            data[field] = int(value)
                        except (TypeError, ValueError):
                            errors[field] = 'Must be an integer'
                    elif rules['type'] == 'float':
                        try:
                            data[field] = float(value)
                        except (TypeError, ValueError):
                            errors[field] = 'Must be a float'
                    elif rules['type'] == 'str':
                        if not isinstance(value, str):
                            errors[field] = 'Must be a string'
                
                # Additional validations
                if 'min' in rules and value < rules['min']:
                    errors[field] = f'Must be at least {rules["min"]}'
                if 'max' in rules and value > rules['max']:
                    errors[field] = f'Must be at most {rules["max"]}'
                if 'allowed' in rules and value not in rules['allowed']:
                    errors[field] = f'Must be one of: {", ".join(rules["allowed"])}'
            
            if errors:
                logger.warning(f"Validation errors: {errors}")
                return jsonify({'errors': errors}), 400
            
            # Attach validated data to request
            request.validated_data = data
            return f(*args, **kwargs)
        return wrapper
    return decorator


def validate_telegram_init_data(init_data: str) -> bool:
    """
    Validate Telegram WebApp init data using HMAC-SHA256 signature verification
    
    Based on Telegram documentation:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
    """
    try:
        # Parse the init data
        parsed_data = parse_qs(init_data)
        
        # Extract hash and remove it from data to be validated
        received_hash = parsed_data.pop('hash', [None])[0]
        if not received_hash:
            logger.warning("No hash found in init data")
            return False
        
        # Prepare data check string
        data_check_string = "\n".join(
            f"{key}={value[0]}" 
            for key, value in sorted(parsed_data.items())
        )
        
        # Calculate secret key
        secret_key = hmac.new(
            b"WebAppData", 
            config.TELEGRAM_TOKEN.encode(), 
            hashlib.sha256
        ).digest()
        
        # Calculate HMAC signature
        calculated_hash = hmac.new(
            secret_key, 
            data_check_string.encode(), 
            hashlib.sha256
        ).hexdigest()
        
        # Compare hashes
        return hmac.compare_digest(calculated_hash, received_hash)
        
    except Exception as e:
        logger.error(f"Error validating Telegram init data: {str(e)}")
        return False

def validate_user_data(user_data: dict) -> bool:
    """Perform additional validation on user data"""
    # Check for required fields
    required_fields = ['id', 'first_name', 'auth_date']
    if not all(field in user_data for field in required_fields):
        logger.warning("Missing required fields in user data")
        return False
    
    # Check authentication date (should be within last 24 hours)
    auth_date = user_data.get('auth_date')
    if auth_date:
        auth_time = datetime.fromtimestamp(auth_date)
        if datetime.now() - auth_time > timedelta(hours=24):
            logger.warning("User auth data is too old")
            return False
    
    # Check for suspicious user data patterns
    if user_data.get('is_bot', False):
        logger.warning("Bot users are not allowed")
        return False
    
    # Additional checks can be added here based on your requirements
    # For example, check username format, etc.
    
    return True

# Cache validation results to reduce computational overhead
@lru_cache(maxsize=1024)
def cached_validate_init_data(init_data: str) -> bool:
    """Cached version of init data validation for performance"""
    return validate_telegram_init_data(init_data)


def validate_caption_length(caption, user_data=None):
    """Validate caption length against user's limits"""
    from src.telegram.config_manager import config_manager  # Add this line
    
    if user_data is None:
        max_length = 1024  # Default
    else:
        limits = config_manager.get_user_limits(user_data)
        max_length = limits.get('caption_length_limit', 1024)
    
    return len(caption) <= max_length

def validate_upload_size(file_size, user_data=None):
    """Validate file size against user's limits"""
    from src.telegram.config_manager import config_manager  # Add this line
    
    if user_data is None:
        max_parts = 4000  # Default
    else:
        limits = config_manager.get_user_limits(user_data)
        max_parts = limits.get('upload_max_fileparts', 4000)
    
    max_size = max_parts * 524288  # Convert parts to bytes
    return file_size <= max_size

def validate_bio_length(bio, user_data=None):
    """Validate bio length against user's limits"""
    from src.telegram.config_manager import config_manager  # Add this line
    
    if user_data is None:
        max_length = 70  # Default
    else:
        limits = config_manager.get_user_limits(user_data)
        max_length = limits.get('about_length_limit', 70)
    
    return len(bio) <= max_length

# Add these validation functions to validators.py

def validate_stars_payment_data(payment_data: dict) -> bool:
    """Validate Telegram Stars payment data structure"""
    required_fields = ['init_data', 'query_id', 'credentials']
    if not all(field in payment_data for field in required_fields):
        return False
    
    # Validate init data format
    if not validate_telegram_init_data(payment_data['init_data']):
        return False
    
    # Validate query ID is a positive integer
    try:
        query_id = int(payment_data['query_id'])
        if query_id <= 0:
            return False
    except (ValueError, TypeError):
        return False
    
    return True

def validate_purchase_request(user_id: int, product_id: str, amount: int) -> bool:
    """Validate purchase request parameters"""
    from config import config
    
    # Validate product exists
    if product_id not in config.IN_GAME_ITEMS:
        return False
    
    # Validate amount matches product price
    product = config.IN_GAME_ITEMS[product_id]
    if amount != product.get('price_stars', 0):
        return False
    
    # Validate user exists and is not restricted
    user_data = db.get_user_data(user_id)
    if not user_data or is_abnormal_activity(user_id):
        return False
    
    return True

def validate_currency(currency: str) -> bool:
    """Validate currency codes"""
    valid_currencies = {'XTR', 'TON', 'USD'}
    return currency in valid_currencies

def validate_stars_amount(amount):
    """Validate Stars amount for transactions"""
    try:
        stars = int(amount)
        if stars <= 0:
            return False, "Amount must be positive"
        if stars > config.MAX_STARS_TRANSACTION:
            return False, f"Amount exceeds maximum of {config.MAX_STARS_TRANSACTION} Stars"
        return True, stars
    except ValueError:
        return False, "Invalid amount format"

def can_use_stars(user_data, required_stars):
    """Check if user can use the specified amount of Stars"""
    available_stars = user_data.get('telegram_stars', 0)
    return available_stars >= required_stars, available_stars

# Add these functions to validators.py

def is_rate_limited(key: str, max_attempts: int, period: int) -> bool:
    """
    Check if a specific action is rate limited
    
    Args:
        key: Unique identifier for the rate limit bucket
        max_attempts: Maximum number of attempts allowed
        period: Time period in seconds for the rate limit
        
    Returns:
        bool: True if rate limited, False otherwise
    """
    try:
        current_time = datetime.time()
        
        # Get or create rate limit entry
        rate_limit = db.rate_limits.find_one({"key": key})
        
        if not rate_limit:
            # Create new rate limit entry
            db.rate_limits.insert_one({
                "key": key,
                "attempts": 1,
                "first_attempt": current_time,
                "last_attempt": current_time,
                "expires_at": current_time + period
            })
            return False
        
        # Check if rate limit period has expired
        if current_time > rate_limit["expires_at"]:
            # Reset rate limit
            db.rate_limits.update_one(
                {"key": key},
                {
                    "$set": {
                        "attempts": 1,
                        "first_attempt": current_time,
                        "last_attempt": current_time,
                        "expires_at": current_time + period
                    }
                }
            )
            return False
        
        # Check if max attempts exceeded
        if rate_limit["attempts"] >= max_attempts:
            return True
        
        # Increment attempt count
        db.rate_limits.update_one(
            {"key": key},
            {
                "$inc": {"attempts": 1},
                "$set": {"last_attempt": current_time}
            }
        )
        
        return False
        
    except Exception as e:
        logger.error(f"Rate limit check failed: {str(e)}")
        # Fail open - don't rate limit if there's an error
        return False

def validate_credentials_format(credentials: dict) -> bool:
    """
    Validate the format of payment credentials
    
    Args:
        credentials: Payment credentials dictionary
        
    Returns:
        bool: True if credentials format is valid, False otherwise
    """
    try:
        # Check for required fields based on payment method
        if not credentials or not isinstance(credentials, dict):
            return False
        
        # Check for Telegram Stars credentials
        if "init_data" in credentials and "query_id" in credentials:
            # Validate Telegram init data format
            init_data = credentials.get("init_data", "")
            if not init_data or not isinstance(init_data, str):
                return False
                
            # Validate query ID format
            query_id = credentials.get("query_id")
            try:
                int(query_id)
            except (ValueError, TypeError):
                return False
                
            return True
        
        # Check for Stripe credentials
        elif "payment_method_id" in credentials and "customer_id" in credentials:
            # Validate Stripe format
            payment_method_id = credentials.get("payment_method_id", "")
            customer_id = credentials.get("customer_id", "")
            
            if (not payment_method_id.startswith("pm_") or 
                not customer_id.startswith("cus_")):
                return False
                
            return True
        
        # Check for crypto payment credentials
        elif "transaction_hash" in credentials and "wallet_address" in credentials:
            transaction_hash = credentials.get("transaction_hash", "")
            wallet_address = credentials.get("wallet_address", "")
            
            if (len(transaction_hash) < 64 or 
                not validate_ton_address(wallet_address)):
                return False
                
            return True
        
        # Unknown credentials format
        return False
        
    except Exception as e:
        logger.error(f"Credentials validation failed: {str(e)}")
        return False

def detect_suspicious_payment_pattern(user_id: int, credentials: dict) -> bool:
    """
    Detect suspicious patterns in payment requests
    
    Args:
        user_id: User ID making the payment
        credentials: Payment credentials
        
    Returns:
        bool: True if suspicious pattern detected, False otherwise
    """
    try:
        # Get user's payment history
        user_data = get_user_data(user_id)
        if not user_data:
            return True  # Suspicious if user doesn't exist
            
        payment_history = user_data.get("stars_transactions", [])
        
        # Check for rapid successive payments
        current_time = datetime.time()
        recent_payments = [
            p for p in payment_history 
            if current_time - p.get("timestamp", current_time).timestamp() < 300  # Last 5 minutes
        ]
        
        if len(recent_payments) > 5:  # More than 5 payments in 5 minutes
            logger.warning(f"Suspicious payment pattern: {len(recent_payments)} payments in 5 minutes for user {user_id}")
            return True
        
        # Check for unusual payment amounts
        if "amount" in credentials:
            amount = credentials["amount"]
            avg_amount = statistics.mean([p.get("amount", 0) for p in payment_history]) if payment_history else 0
            
            if amount > avg_amount * 10 and amount > 1000:  # 10x average and over 1000
                logger.warning(f"Suspicious payment amount: {amount} for user {user_id}")
                return True
        
        # Check for credentials reuse across multiple users
        if "init_data" in credentials:
            init_data = credentials["init_data"]
            
            # Count how many users have used this init_data recently
            recent_users = db.users.count_documents({
                "stars_transactions.init_data": init_data,
                "user_id": {"$ne": user_id},
                "stars_transactions.timestamp": {
                    "$gt": datetime.utcnow() - timedelta(hours=24)
                }
            })
            
            if recent_users > 3:  # Same init_data used by more than 3 users in 24h
                logger.warning(f"Suspicious init_data reuse: used by {recent_users} users")
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Suspicious pattern detection failed: {str(e)}")
        # Fail closed - treat as suspicious if detection fails
        return True