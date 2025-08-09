import os
import random
from datetime import datetime, timedelta
from config import config
import logging
import re
import geoip2.database
from user_agents import parse

# Initialize logger
logger = logging.getLogger(__name__)

# Premium user IDs loaded from environment variables
PREMIUM_USER_IDS = set(os.getenv('PREMIUM_USER_IDS', '').split(',')) if os.getenv('PREMIUM_USER_IDS') else set()

# GeoIP database path
GEOIP_DB_PATH = os.getenv('GEOIP_DB_PATH', 'GeoLite2-Country.mmdb')

def is_premium_user(user_id):
    """
    Checks if a user has premium status by querying Firestore.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        bool: True if premium user, False otherwise
    """
    try:
        from src.database.firebase import db
        
        # Check cache first
        if str(user_id) in PREMIUM_USER_IDS:
            return True
            
        # Query Firestore
        user_ref = db.collection('users').document(str(user_id))
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            premium_status = user_data.get('premium', False)
            
            # Update cache
            if premium_status:
                PREMIUM_USER_IDS.add(str(user_id))
                
            return premium_status
            
        return False
        
    except Exception as e:
        logger.error(f"Premium check error for {user_id}: {str(e)}")
        return False

def get_ad_streak(user_id):
    """
    Calculates consecutive days with ad views from Firestore.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        int: Current streak length in days
    """
    try:
        from src.database.firebase import db
        from datetime import datetime, timedelta
        
        # Get ad view records
        ads_ref = db.collection('ad_engagements')
        query = ads_ref.where('user_id', '==', str(user_id)) \
                      .where('timestamp', '>', datetime.now() - timedelta(days=30)) \
                      .order_by('timestamp', direction='DESC') \
                      .limit(100)
        
        docs = query.stream()
        
        # Convert to date strings
        view_dates = set()
        for doc in docs:
            ad_data = doc.to_dict()
            view_date = ad_data['timestamp'].strftime('%Y-%m-%d')
            view_dates.add(view_date)
        
        # Calculate streak
        streak = 0
        current_date = datetime.now().date()
        
        while streak < 30:  # Max 30 day streak
            check_date = (current_date - timedelta(days=streak)).strftime('%Y-%m-%d')
            if check_date in view_dates:
                streak += 1
            else:
                break
                
        return streak
        
    except Exception as e:
        logger.error(f"Ad streak error for {user_id}: {str(e)}")
        return 0

def get_user_country(user_id, ip_address=None):
    """
    Determines user's country based on IP geolocation or stored profile.
    
    Args:
        user_id: Telegram user ID
        ip_address: Current request IP (optional)
        
    Returns:
        str: ISO 3166-1 country code (e.g., "US")
    """
    try:
        from src.database.firebase import db
        
        # Try to get from user profile first
        user_ref = db.collection('users').document(str(user_id))
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            if user_data.get('country'):
                return user_data['country']
        
        # Fallback to IP geolocation
        if ip_address:
            try:
                with geoip2.database.Reader(GEOIP_DB_PATH) as reader:
                    response = reader.country(ip_address)
                    return response.country.iso_code
            except:
                pass
        
        # Last resort: country from phone number
        if user_doc.exists and user_data.get('phone'):
            phone = user_data['phone']
            if phone.startswith('+1'):
                return 'US'
            elif phone.startswith('+44'):
                return 'GB'
            elif phone.startswith('+7'):
                return 'RU'
            elif phone.startswith('+91'):
                return 'IN'
                
        return 'US'  # Default
        
    except Exception as e:
        logger.error(f"Country lookup error for {user_id}: {str(e)}")
        return 'US'

def get_device_type(user_agent):
    """
    Identifies user's device type from User-Agent string.
    
    Args:
        user_agent: HTTP User-Agent string
        
    Returns:
        str: Device type ("desktop", "mobile", "tablet")
    """
    try:
        if not user_agent:
            return "desktop"
            
        ua = parse(user_agent)
        
        if ua.is_tablet:
            return "tablet"
        elif ua.is_mobile:
            return "mobile"
        else:
            return "desktop"
            
    except Exception as e:
        logger.error(f"Device detection error: {str(e)}")
        return "desktop"