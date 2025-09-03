from src.features.mining import reward_pool
from src.features.monetization import ad_revenue, data_insights
from src.database.mongo import db
import logging
from src.database.mongo import reset_all_daily_limits
from src.integrations import ton_mining
from datetime import datetime, timedelta
from src.integrations.geolocation import geo_manager
import schedule
import time

logger = logging.getLogger(__name__)

def daily_maintenance():
    """Run daily economic maintenance"""
    # Generate staking yield
    staked_amount = db.get_total_staked()
    daily_yield = ton_mining.get_staking_yield(staked_amount)
    db.update_reward_pool(db.get_reward_pool() + daily_yield)
    
    # Replenish reward pool from revenue
    revenue = ad_revenue.get_daily_revenue() + \
              data_insights.get_daily_revenue()
              
    pool = reward_pool.RewardPool()
    pool.replenish_pool(revenue)
    
    # Reset daily counters
    db.reset_daily_activity_counters()

def reset_daily_limits():
    try:
        logger.info(f"Starting daily reset at {datetime.utcnow()}")
        if reset_all_daily_limits():
            logger.info("Daily limits reset successfully")
        else:
            logger.error("Daily reset partially failed")
    except Exception as e:
        logger.exception(f"Critical error in daily reset: {str(e)}")
    
    logger.info("Daily limits reset successfully")

def run_scheduler():
    schedule.every().day.at("00:00").do(reset_daily_limits)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

async def cleanup_expired_locations():
    """Clean up expired user locations"""
    try:
        current_time = datetime.now()
        expired_users = [
            user_id for user_id, location_data in geo_manager.active_locations.items()
            if location_data['expires_at'] <= current_time
        ]
        
        for user_id in expired_users:
            del geo_manager.active_locations[user_id]
            
        logger.info(f"Cleaned up {len(expired_users)} expired locations")
    except Exception as e:
        logger.error(f"Error cleaning up expired locations: {str(e)}")

# Add this task to your scheduled tasks
scheduled_tasks = {
    'cleanup_expired_locations': {
        'task': cleanup_expired_locations,
        'schedule': timedelta(minutes=30)
    }
}

# Schedule to run daily at midnight
schedule.every().day.at("00:00").do(reset_daily_limits)