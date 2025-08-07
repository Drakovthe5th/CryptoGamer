from functools import wraps
from flask import request, jsonify
import re
import logging

logger = logging.getLogger(__name__)

def validate_ton_address(address: str) -> bool:
    """Validate TON wallet address format"""
    pattern = r'^EQ[0-9a-zA-Z]{48}$'
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