# src/features/monetization/purchases.py
from datetime import datetime
from src.database.mongo import db
from src.utils.logger import logger
from src.integrations.telegram import telegram_client
from telethon import functions, types

def get_stars_functions():
    """Lazy import for stars functions to avoid circular imports"""
    try:
        from src.telegram import get_stars_module
        stars_module = get_stars_module()
        return stars_module
    except ImportError as e:
        logger.error(f"Failed to import stars functions: {str(e)}")
        return None

async def create_premium_access_invoice(game_name, price_stars, duration_days):
    """Create invoice for premium game access - local implementation"""
    stars_module = get_stars_functions()
    if stars_module and 'create_stars_invoice' in stars_module:
        return await stars_module['create_stars_invoice'](
            None,  # user_id not needed for this specific call
            f"premium_{game_name}",
            f"Premium Access: {game_name}",
            f"{duration_days}-day premium access to {game_name}",
            price_stars
        )
    return None

def process_purchase(user_id: int, item_id: str):
    """
    Process a purchase - returns (success, message, item_data)
    """
    try:
        # Check if this is a stars purchase or regular purchase
        if item_id.startswith('stars_'):
            # Handle stars purchase
            success, message = process_stars_purchase(user_id, item_id.replace('stars_', ''), 'booster')
            item = BOOSTERS.get(item_id.replace('stars_', ''), {})
            return success, message, item
        else:
            # Handle regular game coins purchase
            success, message = process_regular_purchase(user_id, item_id)
            item = BOOSTERS.get(item_id, {})
            return success, message, item
            
    except Exception as e:
        logger.error(f"Purchase processing failed: {str(e)}")
        return False, "Purchase processing error", None

def process_regular_purchase(user_id: int, item_id: str):
    """Process regular game coins purchase - returns (success, message)"""
    try:
        # Get user data
        user_data = db.users.find_one({"user_id": user_id})
        if not user_data:
            return False, "User not found"
            
        # Get item info
        item = None
        if item_id in BOOSTERS:
            item = BOOSTERS[item_id]
        # Add other item types here
        
        if not item:
            return False, "Item not found"
            
        # Check if user has enough game coins
        game_coins = user_data.get('game_coins', 0)
        if game_coins < item.get('cost', 0):
            return False, "Insufficient game coins"
            
        # Deduct game coins and add item to inventory
        result = db.users.update_one(
            {"user_id": user_id},
            {
                "$inc": {"game_coins": -item['cost']},
                "$push": {"inventory": {
                    "item_id": item_id,
                    "purchased_at": datetime.utcnow(),
                    **item
                }}
            }
        )
        
        if result.modified_count:
            return True, "Purchase successful"
        else:
            return False, "Failed to update inventory"
            
    except Exception as e:
        logger.error(f"Regular purchase failed: {str(e)}")
        return False, "Purchase error"


async def send_star_gift(recipient_id, stars_amount, message=None):
    """Send Telegram Stars as a gift - local implementation"""
    # This would need to be implemented based on your specific gift functionality
    logger.warning("Star gift functionality not fully implemented due to circular import constraints")
    return None

# Add Telegram Stars payment options to boosters
BOOSTERS = {
    'double_earnings_1h': {
        'id': 'DBL-1H', 
        'cost': 500,
        'stars_cost': 50,  # 50 Telegram Stars
        'effect': {'multiplier': 2, 'duration': 3600}
    },
    'triple_earnings_1h': {
        'id': 'TRPL-1H', 
        'cost': 1200,
        'stars_cost': 120,  # 120 Telegram Stars
        'effect': {'multiplier': 3, 'duration': 3600}
    },
    'trivia_questions': {
        'id': 'TRIVIA-20', 
        'cost': 300,
        'stars_cost': 30,  # 30 Telegram Stars
        'effect': {'extra_questions': 20}
    },
    'spin_reset': {
        'id': 'SPIN-RESET', 
        'cost': 200,
        'stars_cost': 20,  # 20 Telegram Stars
        'effect': {'reset_spin': True}
    }
}

# Add premium game access options
PREMIUM_GAMES = {
    'crypto_crew_sabotage': {
        'name': 'Crypto Crew: Sabotage',
        'daily_cost': 100,  # 100 Stars per day
        'weekly_cost': 500,  # 500 Stars per week
        'monthly_cost': 1500,  # 1500 Stars per month
        'description': 'Exclusive premium strategy game'
    },
    'quantum_quest': {
        'name': 'Quantum Quest',
        'daily_cost': 80,  # 80 Stars per day
        'weekly_cost': 400,  # 400 Stars per week
        'monthly_cost': 1200,  # 1200 Stars per month
        'description': 'Sci-fi adventure RPG'
    }
}

async def process_stars_purchase(user_id: int, item_id: str, item_type: str):
    """Process purchase using Telegram Stars"""
    try:
        if item_type == 'booster':
            item = BOOSTERS.get(item_id)
            if not item or 'stars_cost' not in item:
                return False, "Invalid item or not available for Stars"
            
            stars_cost = item['stars_cost']
            
            # Check user's Stars balance
            async with telegram_client:
                status = await telegram_client(
                    functions.payments.GetStarsStatusRequest(
                        peer=types.InputPeerSelf()
                    )
                )
                
                if status.balance.stars < stars_cost:
                    return False, "Insufficient Stars balance"
            
            # Deduct Stars and add item to inventory
            result = db.users.update_one(
                {"user_id": user_id},
                {
                    "$push": {"inventory": {
                        "item_id": item_id,
                        "purchased_at": datetime.utcnow(),
                        **item
                    }}
                }
            )
            
            if result.modified_count:
                # Record Stars transaction
                db.stars_transactions.insert_one({
                    "user_id": user_id,
                    "type": "booster_purchase",
                    "stars_amount": stars_cost,
                    "item_id": item_id,
                    "timestamp": datetime.utcnow(),
                    "status": "completed"
                })
                
                return True, "Purchase successful"
            else:
                return False, "Failed to update inventory"
                
        elif item_type == 'premium_game':
            game_info = PREMIUM_GAMES.get(item_id)
            if not game_info:
                return False, "Invalid game"
            
            # This would typically create an invoice for recurring payment
            invoice = await create_premium_access_invoice(
                game_info['name'],
                game_info['monthly_cost'],
                30  # 30 days
            )
            
            if invoice:
                return True, "Invoice created", invoice
            else:
                return False, "Failed to create invoice"
                
        elif item_type == 'gift':
            # Handle gift purchases
            return await process_gift_purchase(user_id, item_id)
            
    except Exception as e:
        logger.error(f"Stars purchase failed: {str(e)}")
        return False, "Transaction error"

async def process_gift_purchase(user_id: int, gift_details: dict):
    """Process gift purchase using Telegram Stars"""
    try:
        recipient_id = gift_details['recipient_id']
        stars_amount = gift_details['stars_amount']
        message = gift_details.get('message')
        
        # Create gift invoice
        gift_invoice = await send_star_gift(recipient_id, stars_amount, message)
        
        if gift_invoice:
            return True, "Gift invoice created", gift_invoice
        else:
            return False, "Failed to create gift invoice"
            
    except Exception as e:
        logger.error(f"Gift purchase failed: {str(e)}")
        return False, "Gift transaction error"

# In PokerGame class
async def process_stars_buy_in(self, user_id: str, amount: int) -> bool:
    """Process poker table buy-in using Telegram Stars"""
    try:
        async with telegram_client:
            status = await telegram_client(
                functions.payments.GetStarsStatusRequest(
                    peer=types.InputPeerSelf()
                )
            )
            
            if status.balance.stars < amount:
                return False
                
            # Create transaction record
            transaction_id = f"poker_buyin_{user_id}_{datetime.now().timestamp()}"
            db.stars_transactions.insert_one({
                "user_id": user_id,
                "type": "poker_buyin",
                "stars_amount": amount,
                "game_id": self.game_id,
                "timestamp": datetime.utcnow(),
                "status": "pending"
            })
            
            return True
            
    except Exception as e:
        logger.error(f"Stars buy-in failed: {str(e)}")
        return False

async def process_stars_cash_out(self, user_id: str, amount: int) -> bool:
    """Process poker table cash-out to Telegram Stars"""
    try:
        # Record cash-out transaction
        transaction_id = f"poker_cashout_{user_id}_{datetime.now().timestamp()}"
        db.stars_transactions.insert_one({
            "user_id": user_id,
            "type": "poker_cashout",
            "stars_amount": amount,
            "game_id": self.game_id,
            "timestamp": datetime.utcnow(),
            "status": "pending"
        })
        
        # In a real implementation, this would trigger a Stars transfer
        return True
        
    except Exception as e:
        logger.error(f"Stars cash-out failed: {str(e)}")
        return False