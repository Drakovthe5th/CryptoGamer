from datetime import datetime
from src.database.mongo import db
from src.utils.logger import logger

BOOSTERS = {
    'double_earnings_1h': {
        'id': 'DBL-1H', 
        'cost': 500,
        'effect': {'multiplier': 2, 'duration': 3600}
    },
    'triple_earnings_1h': {
        'id': 'TRPL-1H', 
        'cost': 1200,
        'effect': {'multiplier': 3, 'duration': 3600}
    },
    'trivia_questions': {
        'id': 'TRIVIA-20', 
        'cost': 300,
        'effect': {'extra_questions': 20}
    },
    'spin_reset': {
        'id': 'SPIN-RESET', 
        'cost': 200,
        'effect': {'reset_spin': True}
    }
}

def process_purchase(user_id: int, item_id: str):
    if item_id not in BOOSTERS:
        return False, "Invalid item"
        
    item = BOOSTERS[item_id]
    
    try:
        # Transaction-like operation using find_one_and_update
        result = db.users.find_one_and_update(
            {"user_id": user_id, "game_coins": {"$gte": item['cost']}},
            {
                "$inc": {"game_coins": -item['cost']},
                "$push": {"inventory": {
                    "item_id": item_id,
                    "purchased_at": datetime.utcnow(),
                    **item
                }}
            },
            return_document=ReturnDocument.AFTER
        )
        
        if result:
            return True, "Purchase successful", result["inventory"][-1]
        else:
            return False, "Insufficient coins"
    except Exception as e:
        logger.error(f"Purchase failed: {str(e)}")
        return False, "Transaction error"
    
# In PokerGame class
def process_buy_in(self, user_id: str, amount: int) -> bool:
    """Process poker table buy-in"""
    user_balance = self._get_user_balance(user_id)
    
    if amount > user_balance:
        return False
        
    # Deduct from user's balance
    success, new_balance = update_game_coins(user_id, -amount)
    return success

def process_cash_out(self, user_id: str, amount: int) -> bool:
    """Process poker table cash-out"""
    # Add to user's balance
    success, new_balance = update_game_coins(user_id, amount)
    return success