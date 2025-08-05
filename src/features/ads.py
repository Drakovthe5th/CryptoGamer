import os
from src.database.firebase import ads_ref, SERVER_TIMESTAMP, update_leaderboard_points

def record_ad_engagement(user_id: int, advertiser: str, action: str):
    ads_ref.add({
        'user_id': user_id,
        'advertiser': advertiser,
        'action': action,
        'timestamp': SERVER_TIMESTAMP
    })
    
    # Award points for engagement
    update_leaderboard_points(user_id, 10)