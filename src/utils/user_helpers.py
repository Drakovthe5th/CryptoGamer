import os
import random
from datetime import datetime, timedelta
from functools import lru_cache  # Added import
from config import config
import logging
import re
import requests
import geoip2.database
# Removed problematic import

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
        from src.database.mongo import db
        
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
        from src.database.mongo import db
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

def update_participation_score(user_id, activity_type):
    """Update user's participation score based on activity"""
    activity_weights = {
        'game_played': 10,
        'ad_watched': 5,
        'daily_bonus': 15,
        'referral': 20,
        'quest_completed': 8
    }
    
    weight = activity_weights.get(activity_type, 5)
    db.users.update_one(
        {'user_id': user_id},
        {'$inc': {'participation_score': weight}}
    )

# Cache results to reduce API calls (max 256 entries, 1 hour TTL)
@lru_cache(maxsize=256)
def get_user_country(user_id, ip_address=None):
    """Get user country using free IP geolocation API with fallback"""
    if not ip_address or ip_address in ('127.0.0.1', '::1'):
        return config.DEFAULT_COUNTRY
    
    try:
        # Use free ip-api.com service
        response = requests.get(
            f"http://ip-api.com/json/{ip_address}?fields=status,countryCode",
            timeout=1.5
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                return data.get('countryCode', config.DEFAULT_COUNTRY)
        
        return config.DEFAULT_COUNTRY
    except Exception as e:
        logger.error(f"Country lookup failed: {str(e)}")
        return config.DEFAULT_COUNTRY

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
            
        # Simple device detection without external package
        user_agent_lower = user_agent.lower()
        
        if any(k in user_agent_lower for k in ['android', 'iphone', 'mobile']):
            return "mobile"
        elif any(k in user_agent_lower for k in ['tablet', 'ipad']):
            return "tablet"
        else:
            return "desktop"
            
    except Exception as e:
        logger.error(f"Device detection error: {str(e)}")
        return "desktop"

def get_user_country(user_id, ip_address):
    """Get user country based on IP address or user settings"""
    # This would be implemented using a geoip database
    return 'US'  # Default to US for now