import firebase_admin
from firebase_admin import credentials, firestore, storage
from google.cloud.firestore_v1.base_query import FieldFilter
from datetime import datetime, timedelta
import os
import logging
from config import config

logger = logging.getLogger(__name__)

# Initialize Firebase app
firebase_app = None
db = None
bucket = None

def initialize_firebase(firebase_creds):
    global firebase_app, db, bucket
    try:
        # Handle credentials
        if isinstance(firebase_creds, dict):
            cred = credentials.Certificate(firebase_creds)
        else:
            cred = credentials.Certificate(firebase_creds)
        
        # Get storage bucket from env or use default
        storage_bucket = os.getenv('FIREBASE_STORAGE_BUCKET', None)
        app_config = {'storageBucket': storage_bucket} if storage_bucket else {}
        
        firebase_app = firebase_admin.initialize_app(cred, app_config)
        db = firestore.client()
        
        # Initialize bucket only if name is available
        if storage_bucket:
            bucket = storage.bucket()
        else:
            bucket = None
            logger.warning("Firebase storage bucket not configured. Storage functions disabled.")
        
        logger.info("Firebase initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Firebase initialization failed: {str(e)}")
        return False

def get_firestore_db():
    global db
    return db

# User operations
def get_user_data(user_id: int):
    try:
        doc_ref = db.collection('users').document(str(user_id))
        doc = doc_ref.get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        logger.error(f"Error getting user data: {str(e)}")
        return None

def get_user_balance(user_id: int) -> float:
    try:
        user_data = get_user_data(user_id)
        return user_data.get('balance', 0.0) if user_data else 0.0
    except Exception as e:
        logger.error(f"Error getting user balance: {str(e)}")
        return 0.0

def update_balance(user_id: int, amount: float) -> float:
    try:
        doc_ref = db.collection('users').document(str(user_id))
        transaction = db.transaction()
        
        @firestore.transactional
        def update_in_transaction(transaction, doc_ref):
            snapshot = doc_ref.get(transaction=transaction)
            current_balance = snapshot.get('balance', 0.0)
            new_balance = max(0.0, current_balance + amount)
            transaction.update(doc_ref, {'balance': new_balance})
            return new_balance
        
        return update_in_transaction(transaction, doc_ref)
    except Exception as e:
        logger.error(f"Error updating balance: {str(e)}")
        return 0.0

# Withdrawal operations
def process_ton_withdrawal(user_id: int, amount: float, address: str) -> dict:
    try:
        withdrawal_data = {
            'user_id': str(user_id),
            'amount': amount,
            'address': address,
            'status': 'pending',
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        doc_ref = db.collection('withdrawals').document()
        doc_ref.set(withdrawal_data)
        
        return {
            'status': 'success',
            'withdrawal_id': doc_ref.id,
            'message': 'Withdrawal request submitted'
        }
    except Exception as e:
        logger.error(f"Withdrawal processing failed: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }

# Ad operations
def track_ad_reward(user_id: int, amount: float, source: str, is_weekend: bool):
    try:
        reward_data = {
            'user_id': str(user_id),
            'amount': amount,
            'source': source,
            'is_weekend': is_weekend,
            'timestamp': datetime.utcnow()
        }
        
        db.collection('ad_rewards').add(reward_data)
        logger.info(f"Tracked ad reward for user {user_id}: {amount} TON")
        return True
    except Exception as e:
        logger.error(f"Error tracking ad reward: {str(e)}")
        return False

# Security operations
def add_whitelist(user_id: int, address: str):
    try:
        doc_ref = db.collection('users').document(str(user_id))
        doc_ref.update({
            'whitelisted_addresses': firestore.ArrayUnion([address])
        })
        return True
    except Exception as e:
        logger.error(f"Error adding to whitelist: {str(e)}")
        return False

def get_recent_withdrawals(user_id: int, hours=24) -> list:
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        withdrawals_ref = db.collection('withdrawals')
        query = withdrawals_ref.where('user_id', '==', str(user_id)) \
            .where('created_at', '>=', start_time) \
            .where('created_at', '<=', end_time)
        
        return [doc.to_dict() for doc in query.stream()]
    except Exception as e:
        logger.error(f"Error getting recent withdrawals: {str(e)}")
        return []

# Staking operations
def save_staking(user_id: int, contract_address: str, amount: float):
    try:
        staking_data = {
            'user_id': str(user_id),
            'contract_address': contract_address,
            'amount': amount,
            'start_date': datetime.utcnow(),
            'status': 'active'
        }
        
        db.collection('staking').add(staking_data)
        return True
    except Exception as e:
        logger.error(f"Error saving staking: {str(e)}")
        return False

def record_activity(user_id, activity_type, amount):
    """Log user activity for reward distribution"""
    doc_ref = db.collection('user_activities').document()
    doc_ref.set({
        'user_id': user_id,
        'type': activity_type,
        'amount': amount,
        'timestamp': SERVER_TIMESTAMP
    })

def record_staking(user_id, contract_address, amount):
    """Record staking contract creation"""
    doc_ref = db.collection('staking').document()
    doc_ref.set({
        'user_id': user_id,
        'contract': contract_address,
        'amount': amount,
        'created': SERVER_TIMESTAMP,
        'status': 'active'
    })

def get_reward_pool():
    """Get current reward pool balance"""
    doc = db.collection('system').document('reward_pool').get()
    return doc.to_dict().get('balance', 1000) if doc.exists else 1000

def update_reward_pool(balance):
    """Update reward pool balance"""
    db.collection('system').document('reward_pool').set({
        'balance': balance,
        'updated': SERVER_TIMESTAMP
    })

# Timestamp constant
SERVER_TIMESTAMP = firestore.SERVER_TIMESTAMP