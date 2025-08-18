# src/database/mongo.py
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import PyMongoError
from datetime import datetime
import os
import logging
from config import config
from src.utils.validators import validate_ton_address

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
            "username": username,
            "balance": 0.0,
            "game_coins": 0,
            "daily_coins_earned": 0,
            "daily_resets": {},
            "wallet_address": None,
            "membership_tier": "BASIC",
            "created_at": SERVER_TIMESTAMP,
            "last_active": SERVER_TIMESTAMP,
            "completed_quests": [],
            "active_quests": [],
            "xp": 0,
            "level": 1,
            "inventory": [],
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
    # This would use actual rate calculation logic
    fiat_amount = ton_amount * 5.0  # Simplified
    fee = max(fiat_amount * 0.05, 0.5)  # 5% fee with $0.5 min
    
    deal_data = {
        "user_id": user_id,
        "amount_ton": ton_amount,
        "currency": currency,
        "payment_method": method,
        "rate": 5.0,
        "fiat_amount": fiat_amount,
        "fee": fee,
        "total": fiat_amount - fee,
        "status": "pending",
        "created_at": SERVER_TIMESTAMP
    }
    
    result = db.otc_deals.insert_one(deal_data)
    return str(result.inserted_id)

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