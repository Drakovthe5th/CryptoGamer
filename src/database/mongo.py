# src/database/mongo.py
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import PyMongoError
from datetime import datetime
import os
import logging
from datetime import timedelta
from config import config

logger = logging.getLogger(__name__)

# Global MongoDB connection
client = None
db = None

# Constants
MAX_RESETS = 3
MAX_DAILY_GAME_COINS = 20000
MIN_WITHDRAWAL_GC = 200000  # GC
GC_TO_TON_RATE = 2000  # GC per TON
SERVER_TIMESTAMP = datetime.utcnow()

def initialize_mongodb():
    global client, db
    try:
        # Use config.MONGO_URI instead of os.getenv
        client = MongoClient(config.MONGO_URI)
        db = client[config.MONGO_DB_NAME]
        
        # Create indexes
        db.users.create_index("user_id", unique=True)
        db.game_sessions.create_index("user_id")
        db.game_sessions.create_index("status")
        db.otc_deals.create_index("user_id")
        db.withdrawals.create_index("user_id")
        db.staking.create_index("user_id")
        db.users.create_index("leaderboard_points")
        
        logger.info("✅ MongoDB initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ MongoDB initialization failed: {str(e)}")
        return False

def get_db():
    return db

# User operations
def create_user(user_id, username):
    if not db.users.find_one({"user_id": user_id}):
        db.users.insert_one({
            "user_id": user_id,
            "username": username or f'User{user_id}',
            "balance": 0.0,
            "game_coins": 2000,  # Welcome bonus of 2000 GC
            "daily_coins_earned": 0,
            "daily_resets": {},
            'daily_bonus_claimed': False,
            "wallet_address": None,
            "membership_tier": "BASIC",
            "created_at": SERVER_TIMESTAMP,
            "last_active": SERVER_TIMESTAMP,
            'clicks_today': 0,
            "completed_quests": [],
            "active_quests": [],
            "xp": 0,
            "level": 1,
            'referrals': 0,
            'ref_earnings': 0.0,
            "leaderboard_points": 0.0,
            "inventory": [],
            'participation_score': 0,
            'game_stats': {},
            'welcome_bonus_received': True,
            "payment_methods": {}
        })

def get_user_data(user_id: int):
    return db.users.find_one({"user_id": user_id})

def update_game_coins(user_id: int, coins: int) -> tuple:
    user = db.users.find_one({"user_id": user_id})
    if not user:
        return 0, 0
    
    # Apply daily limit
    daily_earned = user.get("daily_coins_earned", 0)
    current_coins = user.get("game_coins", 0)
    
    if coins > 0:
        remaining_daily = MAX_DAILY_GAME_COINS - daily_earned
        actual_coins = min(coins, remaining_daily)
        new_daily_earned = daily_earned + actual_coins
    else:
        actual_coins = coins
        new_daily_earned = daily_earned
    
    new_coins = current_coins + actual_coins
    
    db.users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "game_coins": new_coins,
                "daily_coins_earned": new_daily_earned
            }
        }
    )
    return new_coins, actual_coins

def update_leaderboard_points(user_id: int, points: float):
    """Update user's leaderboard points"""
    try:
        db.users.update_one(
            {"user_id": user_id},
            {"$set": {"leaderboard_points": points}}
        )
        return True
    except Exception as e:
        logger.error(f"Error updating leaderboard points: {str(e)}")
        return False

def get_game_coins(user_id):
    user = db.users.find_one({"user_id": user_id})
    return user.get("game_coins", 0) if user else 0

def record_reset(user_id: int, game_type: str) -> bool:
    result = db.users.update_one(
        {"user_id": user_id, f"daily_resets.{game_type}": {"$lt": MAX_RESETS}},
        {
            "$inc": {f"daily_resets.{game_type}": 1},
            "$setOnInsert": {f"daily_resets.{game_type}": 1}
        },
        upsert=True
    )
    return result.modified_count > 0 or result.upserted_id is not None

def reset_all_daily_limits():
    try:
        db.users.update_many(
            {},
            {
                "$set": {
                    "daily_coins_earned": 0,
                    "daily_resets": {}
                }
            }
        )
        logger.info("Daily limits reset for all users")
        return True
    except Exception as e:
        logger.error(f"Daily reset failed: {str(e)}")
        return False

def connect_wallet(user_id: int, wallet_address: str):
    from src.utils.validators import validate_ton_address  # Add this line
    
    if not validate_ton_address(wallet_address):
        logger.error(f"Invalid wallet address: {wallet_address}")
        return False

    db.users.update_one(
        {"user_id": user_id},
        {"$set": {"wallet_address": wallet_address}}
    )
    return True

def get_user_balance(user_id: int) -> float:
    user = db.users.find_one({"user_id": user_id})
    return user.get("balance", 0.0) if user else 0.0

def update_balance(user_id: int, amount: float) -> float:
    result = db.users.find_one_and_update(
        {"user_id": user_id},
        {"$inc": {"balance": amount}},
        return_document=ReturnDocument.AFTER
    )
    return result.get("balance", 0.0) if result else 0.0

# Game operations
def get_games_list() -> list:
    return list(db.games.find({"enabled": True}))

def record_game_start(user_id: int, game_id: str) -> str:
    session_data = {
        "user_id": user_id,
        "game_id": game_id,
        "start_time": SERVER_TIMESTAMP,
        "status": "active"
    }
    result = db.game_sessions.insert_one(session_data)
    return str(result.inserted_id)

def get_game_session(session_id: str):
    return db.game_sessions.find_one({"_id": session_id})

def save_game_session(user_id: int, game_id: str, score: int, reward: float, session_id: str) -> bool:
    try:
        # Update game session
        db.game_sessions.update_one(
            {"_id": session_id},
            {
                "$set": {
                    "end_time": SERVER_TIMESTAMP,
                    "score": score,
                    "reward": reward,
                    "status": "completed"
                }
            }
        )
        
        # Update user stats
        db.users.update_one(
            {"user_id": user_id},
            {
                "$inc": {
                    "total_games": 1,
                    "total_rewards": reward
                },
                "$set": {"last_played": SERVER_TIMESTAMP}
            }
        )
        return True
    except Exception as e:
        logger.error(f"Error saving game session: {str(e)}")
        return False

def save_user_data(user_id: int, user_data: dict):
    """Save user data to database"""
    try:
        db.users.update_one(
            {"user_id": user_id},
            {"$set": user_data},
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error saving user data: {str(e)}")
        return False

# Activity operations
def get_user_activity(user_id: int, limit=100) -> list:
    return list(db.user_activities.find(
        {"user_id": user_id}
    ).sort("timestamp", -1).limit(limit))

# Withdrawal history
def get_withdrawal_history(user_id: int) -> list:
    return list(db.withdrawals.find(
        {"user_id": user_id}
    ).sort("created_at", -1))

# Quest operations
def save_quest_progress(user_id: int, user_data: dict) -> bool:
    update_data = {
        "balance": user_data.get("balance", 0.0),
        "completed_quests": user_data.get("completed_quests", []),
        "active_quests": user_data.get("active_quests", []),
        "xp": user_data.get("xp", 0)
    }
    
    if "level" in user_data:
        update_data["level"] = user_data["level"]
    
    db.users.update_one(
        {"user_id": user_id},
        {"$set": update_data}
    )
    return True

# Ad operations
def track_ad_reward(user_id: int, amount: float, source: str, is_weekend: bool):
    try:
        db.ad_rewards.insert_one({
            "user_id": user_id,
            "amount": amount,
            "source": source,
            "is_weekend": is_weekend,
            "timestamp": SERVER_TIMESTAMP
        })
        return True
    except Exception as e:
        logger.error(f"Error tracking ad reward: {str(e)}")
        return False

# Security operations
def add_whitelist(user_id: int, address: str):
    db.users.update_one(
        {"user_id": user_id},
        {"$addToSet": {"whitelisted_addresses": address}}
    )
    return True

# Staking operations
def save_staking(user_id: int, contract_address: str, amount: float):
    try:
        db.staking.insert_one({
            "user_id": user_id,
            "contract_address": contract_address,
            "amount": amount,
            "start_date": SERVER_TIMESTAMP,
            "status": "active"
        })
        return True
    except Exception as e:
        logger.error(f"Error saving staking: {str(e)}")
        return False

def record_activity(user_id, activity_type, amount):
    db.user_activities.insert_one({
        "user_id": user_id,
        "type": activity_type,
        "amount": amount,
        "timestamp": SERVER_TIMESTAMP
    })

def record_staking(user_id, contract_address, amount):
    db.staking.insert_one({
        "user_id": user_id,
        "contract": contract_address,
        "amount": amount,
        "created": SERVER_TIMESTAMP,
        "status": "active"
    })

def get_reward_pool():
    system = db.system.find_one({"name": "reward_pool"})
    return system.get("balance", 1000) if system else 1000

def update_reward_pool(balance):
    db.system.update_one(
        {"name": "reward_pool"},
        {"$set": {"balance": balance, "updated": SERVER_TIMESTAMP}},
        upsert=True
    )

# OTC Desk operations
def create_otc_deal(user_id: int, ton_amount: float, currency: str, method: str) -> str:
    """Create an OTC deal with actual rate calculation logic"""
    try:
        # Get current exchange rate
        rate = get_current_exchange_rate(currency.upper())
        if rate <= 0:
            raise ValueError(f"Invalid exchange rate for {currency}")
        
        # Calculate fiat amount
        fiat_amount = ton_amount * rate
        
        # Calculate fee (5% with $0.5 minimum)
        fee_percent = 5.0
        min_fee = 0.5
        fee = max(fiat_amount * (fee_percent / 100), min_fee)
        
        # Apply weekend boost (10% higher rates on weekends)
        is_weekend = datetime.utcnow().weekday() in [5, 6]  # Sat/Sun
        if is_weekend:
            fiat_amount *= 1.10  # 10% boost
            fee *= 0.8  # 20% fee discount on weekends
        
        # Get user's payment details
        user = db.users.find_one({"user_id": user_id})
        payment_details = user.get("payment_methods", {}).get(method, {})
        
        # Create deal data
        deal_data = {
            "user_id": user_id,
            "amount_ton": ton_amount,
            "currency": currency.upper(),
            "payment_method": method,
            "rate": rate,
            "fiat_amount": round(fiat_amount, 2),
            "fee": round(fee, 2),
            "total": round(fiat_amount - fee, 2),
            "status": "pending",
            "created_at": datetime.utcnow(),
            "payment_details": payment_details,
            "weekend_boost": is_weekend,
            "expires_at": datetime.utcnow() + timedelta(minutes=15)  # 15min expiration
        }
        
        # Insert deal and return ID
        result = db.otc_deals.insert_one(deal_data)
        return str(result.inserted_id)
        
    except Exception as e:
        logger.error(f"OTC deal creation failed: {str(e)}")
        # Fallback to simplified version
        return create_simple_otc_deal(user_id, ton_amount, currency, method)

def create_simple_otc_deal(user_id: int, ton_amount: float, currency: str, method: str) -> str:
    """Fallback OTC deal creation with simplified logic"""
    try:
        rate = config.OTC_RATES.get(currency.upper(), 5.0)
        fiat_amount = ton_amount * rate
        fee = max(fiat_amount * 0.05, 0.5)
        
        deal_data = {
            "user_id": user_id,
            "amount_ton": ton_amount,
            "currency": currency.upper(),
            "payment_method": method,
            "rate": rate,
            "fiat_amount": round(fiat_amount, 2),
            "fee": round(fee, 2),
            "total": round(fiat_amount - fee, 2),
            "status": "pending",
            "created_at": datetime.utcnow(),
            "is_fallback": True  # Mark as fallback
        }
        
        result = db.otc_deals.insert_one(deal_data)
        return str(result.inserted_id)
    except Exception as e:
        logger.critical(f"Fallback OTC deal creation failed: {str(e)}")
        return ""

def get_current_exchange_rate(currency: str) -> float:
    """Get current exchange rate from database or API"""
    try:
        # First try to get from database cache
        rate_doc = db.exchange_rates.find_one(
            {"currency": currency},
            sort=[("timestamp", -1)]
        )
        
        # Use if recent (within 5 minutes)
        if rate_doc and (datetime.utcnow() - rate_doc["timestamp"]).seconds < 300:
            return rate_doc["rate"]
        
        # If not available or stale, get from API
        rate = fetch_live_exchange_rate(currency)
        
        # Cache the new rate
        db.exchange_rates.insert_one({
            "currency": currency,
            "rate": rate,
            "timestamp": datetime.utcnow(),
            "source": "live_api"
        })
        
        return rate
        
    except Exception as e:
        logger.warning(f"Exchange rate fetch failed: {str(e)}")
        # Fallback to config rates
        return config.OTC_RATES.get(currency, 5.0)

def fetch_live_exchange_rate(currency: str) -> float:
    """Fetch live exchange rate from external API (simulated)"""
    # In production, this would call a real exchange rate API
    # For now, simulate with random variation around base rate
    base_rate = config.OTC_RATES.get(currency, 5.0)
    
    # Simulate market fluctuation (±2%)
    import random
    fluctuation = random.uniform(-0.02, 0.02)
    return base_rate * (1 + fluctuation)

def get_otc_quote(game_coins, currency):
    ton_amount = game_coins / GC_TO_TON_RATE
    rate = 5.0  # Simplified rate
    fee = max(ton_amount * rate * 0.05, 0.5)
    
    return {
        "game_coins": game_coins,
        "amount_ton": ton_amount,
        "currency": currency,
        "rate": rate,
        "fee": fee,
        "total": (ton_amount * rate) - fee
    }

def get_leaderboard(limit=10):
    """Get top users by leaderboard points"""
    top_users = db.users.find().sort("leaderboard_points", -1).limit(limit)
    return [user for user in top_users]

def get_user_rank(user_id: int):
    """Get user's leaderboard rank"""
    all_users = list(db.users.find().sort("leaderboard_points", -1))
    for rank, user in enumerate(all_users, start=1):
        if user['user_id'] == user_id:
            return rank
    return -1


def update_user_data(user_id: int, update_data: dict, upsert: bool = False) -> bool:
    """
    Update user data with flexible fields
    
    Args:
        user_id: Telegram user ID
        update_data: Dictionary of fields to update
        upsert: Whether to create the user if not exists
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Add timestamp for last activity if not explicitly set
        if "last_active" not in update_data:
            update_data["last_active"] = SERVER_TIMESTAMP
        
        result = db.users.update_one(
            {"user_id": user_id},
            {"$set": update_data},
            upsert=upsert
        )
        
        return result.modified_count > 0 or result.upserted_id is not None
    except Exception as e:
        logger.error(f"Error updating user data: {str(e)}")
        return False

def check_db_connection():
    try:
        db.command('ping')
        return True
    except PyMongoError:
        return False