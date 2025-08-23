# src/features/monetization/premium.py
from src.integrations.payment_processors import process_stars_purchase
from src.database.mongo import db

MEMBERSHIP_TIERS = {
    'BASIC': {
        'price_stars': 0,
        'benefits': ['standard_earnings']
    },
    'PREMIUM': {
        'price_stars': 500,  # 500 Stars
        'benefits': [
            '1.5x_earnings',
            'extra_questions',
            'daily_reset_booster',
            'ad_free'
        ]
    },
    'ULTIMATE': {
        'price_stars': 1000,  # 1000 Stars
        'benefits': [
            '2x_earnings',
            'unlimited_questions',
            'priority_support',
            'free_resets',
            'exclusive_items'
        ]
    }
}

def upgrade_user_with_stars(user_id: int, tier: str, credentials: dict) -> dict:
    """
    Upgrade user membership using Telegram Stars
    """
    if tier not in MEMBERSHIP_TIERS:
        return {'success': False, 'error': 'Invalid tier'}
    
    # Process Stars payment
    tier_info = MEMBERSHIP_TIERS[tier]
    if tier_info['price_stars'] > 0:
        result = process_stars_purchase(
            user_id=user_id,
            credentials=credentials,
            product_id=f"membership_{tier.lower()}"
        )
        
        if not result['success']:
            return result
    
    # Update user membership
    from src.database.mongo import update_user_membership
    success = update_user_membership(user_id, tier)
    
    if success:
        return {
            'success': True,
            'tier': tier,
            'benefits': tier_info['benefits'],
            'stars_spent': tier_info['price_stars']
        }
    else:
        return {'success': False, 'error': 'Failed to update membership'}

def get_membership_options(user_id: int) -> dict:
    """
    Get available membership options with localized pricing
    """
    user_data = db.get_user_data(user_id)
    current_tier = user_data.get('membership_tier', 'BASIC')
    
    options = {}
    for tier, info in MEMBERSHIP_TIERS.items():
        options[tier] = {
            'price_stars': info['price_stars'],
            'benefits': info['benefits'],
            'current': tier == current_tier,
            'upgradeable': tier != current_tier
        }
    
    return options