from src.features.mining import reward_pool
from src.features.monetization import ad_revenue, data_insights
from src.database.firebase import db
import logging
from src.database.firebase import reset_all_daily_limits
from datetime import datetime
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

# Schedule to run daily at midnight
schedule.every().day.at("00:00").do(reset_daily_limits)