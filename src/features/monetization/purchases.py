from datetime import datetime
from google.cloud import firestore
from src.database.firebase import db, get_user, save_user
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
    """Process in-game purchase"""

    try:
        # Validate item
        if item_id not in BOOSTERS:
            return False, "Invalid item"
            
        item = BOOSTERS[item_id]
        user_ref = db.collection('users').document(str(user_id))
        transaction = db.transaction()
        
        @firestore.transactional
        def purchase_transaction(transaction, user_ref):
            # Get current user data
            user_snap = user_ref.get(transaction=transaction)
            user_data = user_snap.to_dict()
            current_coins = user_data.get('game_coins', 0)
            
            # Check affordability
            if current_coins < item['cost']:
                return False, "Insufficient coins"
            
            # Deduct coins
            new_coins = current_coins - item['cost']
            transaction.update(user_ref, {'game_coins': new_coins})
            
            # Add to inventory
            inventory = user_data.get('inventory', [])
            new_item = {
                'item_id': item_id,
                'purchased_at': datetime.utcnow(),
                **item
            }
            inventory.append(new_item)
            transaction.update(user_ref, {'inventory': inventory})
            
            return True, "Purchase successful", new_item
        
        return purchase_transaction(transaction, user_ref)
    except Exception as e:
        logger.error(f"Purchase failed: {str(e)}")
        return False, "Transaction error"