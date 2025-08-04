import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin.exceptions import FirebaseError
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from google.cloud.firestore_v1.base_query import FieldFilter
from config import config
import logging

# Global database references
db = None
users_ref = None
transactions_ref = None
withdrawals_ref = None
quests_ref = None  # Added quests reference

def initialize_firebase(creds_dict):
    global db, users_ref, transactions_ref, withdrawals_ref, quests_ref
    
    try:
        if not firebase_admin._apps:
            # Handle both file paths and credential dictionaries
            if isinstance(creds_dict, dict):
                cred = credentials.Certificate(creds_dict)
            elif isinstance(creds_dict, str) and os.path.isfile(creds_dict):
                cred = credentials.Certificate(creds_dict)
            else:
                logging.error("Invalid Firebase credentials format")
                return False
            
            firebase_admin.initialize_app(cred)
        
        db = firestore.client()
        users_ref = db.collection('users')
        transactions_ref = db.collection('transactions')
        withdrawals_ref = db.collection('withdrawals')
        quests_ref = db.collection('quests')
        logging.info("Firebase initialized successfully")
        return True
    except Exception as e:
        logging.error(f"Firebase initialization error: {e}")
        return False

def track_ad_impression(platform: str, ad_type: str, user_id: int, country: str):
    try:
        db.collection('ad_impressions').add({
            'platform': platform,
            'ad_type': ad_type,
            'user_id': user_id,
            'country': country,
            'timestamp': SERVER_TIMESTAMP
        })
    except Exception as e:
        logging.error(f"Ad impression tracking failed: {e}")

def track_ad_reward(user_id: int, amount: float, platform: str, weekend_boost: bool):
    try:
        db.collection('ad_rewards').add({
            'user_id': user_id,
            'amount': amount,
            'platform': platform,
            'weekend_boost': weekend_boost,
            'timestamp': SERVER_TIMESTAMP
        })
    except Exception as e:
        logging.error(f"Ad reward tracking failed: {e}")

# User operations
def get_user_ref(user_id: int):
    return users_ref.document(str(user_id))

def get_user_data(user_id: int):
    try:
        doc = get_user_ref(user_id).get()
        return doc.to_dict() if doc.exists else None
    except FirebaseError as e:
        logging.error(f"Error getting user data: {e}")
        return None

def create_user(user_id: int, username: str):
    user_ref = get_user_ref(user_id)
    try:
        if not user_ref.get().exists:
            user_ref.set({
                'user_id': user_id,
                'username': username,
                'balance': 0.0,
                'points': 0,
                'last_played': {},
                'referral_count': 0,
                'faucet_claimed': None,
                'withdrawal_methods': {},
                'completed_quests': {},
                'created_at': SERVER_TIMESTAMP
            })
        return user_ref
    except FirebaseError as e:
        logging.error(f"Error creating user: {e}")
        return None

def update_user(user_id: int, update_data: dict):
    try:
        get_user_ref(user_id).update(update_data)
    except FirebaseError as e:
        logging.error(f"Error updating user: {e}")

def get_user_balance(user_id: int) -> float:
    user_data = get_user_data(user_id)
    return user_data.get('balance', 0.0) if user_data else 0.0

def update_balance(user_id: int, amount: float):
    try:
        user_ref = get_user_ref(user_id)
        if not user_ref.get().exists:
            create_user(user_id, "")
        current_balance = get_user_balance(user_id)
        new_balance = current_balance + amount
        user_ref.update({'balance': new_balance})
        return new_balance
    except FirebaseError as e:
        logging.error(f"Error updating balance: {e}")
        return current_balance  # return the old balance if update fails

# Leaderboard operations
def update_leaderboard_points(user_id: int, points: int):
    try:
        user_ref = get_user_ref(user_id)
        user_ref.update({
            'points': firestore.Increment(points),
            'last_active': SERVER_TIMESTAMP
        })
    except FirebaseError as e:
        logging.error(f"Error updating leaderboard points: {e}")

def get_leaderboard(limit: int = 10) -> list:
    """Get top users by points"""
    try:
        collection_ref = users_ref if users_ref else db.collection('users')
        query = collection_ref.order_by('points', direction=firestore.Query.DESCENDING).limit(limit)
        results = query.stream()
        
        leaderboard = []
        for doc in results:
            user_data = doc.to_dict()
            leaderboard.append(user_data)
            
        return leaderboard
    except Exception as e:
        logging.error(f"Error getting leaderboard: {e}")
        return []

def get_user_rank(user_id: int) -> int:
    """Get user's rank based on points"""
    try:
        # Get user points
        user_doc = get_user_ref(user_id).get()
        if not user_doc.exists:
            return 0
        user_data = user_doc.to_dict()
        user_points = user_data.get('points', 0)
        
        # Count users with more points
        collection_ref = users_ref if users_ref else db.collection('users')
        count_query = collection_ref.where(filter=FieldFilter('points', '>', user_points))
        count = count_query.count().get()[0][0].value
        
        # Rank is count + 1
        return count + 1
    except Exception as e:
        logging.error(f"Error getting user rank: {e}")
        return 0

# Withdrawal operations
def process_withdrawal(user_id: int, method: str, amount: float, details: dict):
    try:
        # Create withdrawal record
        withdrawal_ref = withdrawals_ref.add({
            'user_id': user_id,
            'method': method,
            'amount': amount,
            'details': details,
            'status': 'pending',
            'created_at': SERVER_TIMESTAMP
        })[1]
        
        # Return success with withdrawal ID
        return {
            'status': 'success',
            'withdrawal_id': withdrawal_ref.id
        }
    except Exception as e:
        logging.error(f"Withdrawal processing error: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }