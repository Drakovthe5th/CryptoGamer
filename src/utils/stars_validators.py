import re
from config import Config

def validate_stars_amount(amount):
    """Validate Stars amount for transactions"""
    try:
        stars = int(amount)
        if stars <= 0:
            return False, "Amount must be positive"
        if stars > Config.MAX_STARS_TRANSACTION:
            return False, f"Amount exceeds maximum of {Config.MAX_STARS_TRANSACTION} Stars"
        return True, stars
    except ValueError:
        return False, "Invalid amount format"

def can_use_stars(user_data, required_stars):
    """Check if user can use the specified amount of Stars"""
    available_stars = user_data.get('telegram_stars', 0)
    return available_stars >= required_stars, available_stars