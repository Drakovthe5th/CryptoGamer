from functools import wraps, lru_cache
from flask import request, jsonify
import re
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
            config.TELEGRAM_BOT_TOKEN.encode(), 
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