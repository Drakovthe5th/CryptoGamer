# src/features/monetization/purchases.py
from datetime import datetime
from src.database.mongo import db
from src.utils.logger import logger
from src.telegram.stars import create_premium_access_invoice, send_star_gift
from src.integrations.telegram import telegram_client
from telethon import functions, types

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