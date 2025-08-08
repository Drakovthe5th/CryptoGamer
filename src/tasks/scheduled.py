from src.features.mining import reward_pool
from src.features.monetization import ad_revenue, data_insights

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