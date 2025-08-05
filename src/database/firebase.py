import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
import logging
import os
from config import config

logger = logging.getLogger(__name__)

# Initialize Firebase
# Global database instance
db = None

def initialize_firebase():
    global db
    try:
        # Load Firebase credentials from config
        if config.FIREBASE_CREDS:
            cred_dict = json.loads(config.FIREBASE_CREDS)
            cred = credentials.Certificate(cred_dict)
        else:
            raise ValueError("Firebase credentials not configured")
        
        # Initialize Firebase app
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        
        # Create Firestore client
        db = firestore.client()
        logger.info("Firebase initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Firebase initialization failed: {e}")
        return False

def get_firestore_db():
    """Get the Firestore database instance"""
    if db is None:
        initialize_firebase()
    return db

# Initialize Firebase on import
initialize_firebase()

try:
    if not firebase_admin._apps:
        # Use credentials from config
        if config.FIREBASE_CREDS:
            # Create temporary credentials file
            temp_creds_path = "/tmp/firebase_creds.json"
            with open(temp_creds_path, 'w') as f:
                json.dump(config.FIREBASE_CREDS, f)
            
            cred = credentials.Certificate(temp_creds_path)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized using config credentials")
        else:
            logger.error("No Firebase credentials available")
            raise RuntimeError("Missing Firebase credentials")
    
    db = firestore.client()
    logger.info("Firestore client created successfully")
except Exception as e:
    logger.error(f"Firebase initialization failed: {e}")
    db = None

def add_whitelist(user_id: str, address: str):
    """Add address to user's whitelist"""
    if not db:
        return
    try:
        doc_ref = db.collection('users').document(user_id)
        doc_ref.update({
            'whitelist': firestore.ArrayUnion([address])
        })
        logger.info(f"Added {address} to whitelist for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to add to whitelist: {e}")

def enable_2fa(user_id: str):
    """Enable 2FA for user"""
    if not db:
        return
    try:
        doc_ref = db.collection('users').document(user_id)
        doc_ref.update({'2fa_enabled': True})
        logger.info(f"Enabled 2FA for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to enable 2FA: {e}")

def flag_user(user_id: str, reason: str):
    """Flag user for suspicious activity"""
    if not db:
        return
    try:
        doc_ref = db.collection('users').document(user_id)
        doc_ref.update({
            'flagged': True,
            'flag_reason': reason,
            'flagged_at': datetime.now()
        })
        logger.warning(f"Flagged user {user_id}: {reason}")
    except Exception as e:
        logger.error(f"Failed to flag user: {e}")

def get_recent_withdrawals(user_id: str) -> list:
    """Get recent withdrawals for user"""
    if not db:
        return []
    try:
        # Get withdrawals from last 24 hours
        now = datetime.now()
        one_day_ago = now - timedelta(days=1)
        
        withdrawals_ref = db.collection('withdrawals')
        query = withdrawals_ref.where('user_id', '==', user_id) \
                              .where('timestamp', '>=', one_day_ago) \
                              .order_by('timestamp', direction=firestore.Query.DESCENDING)
        
        results = query.stream()
        return [doc.to_dict() for doc in results]
    except Exception as e:
        logger.error(f"Failed to get recent withdrawals: {e}")
        return []

def save_staking(user_id: str, contract_address: str, amount: float):
    """Save staking contract to Firestore"""
    if not db:
        return
    try:
        staking_ref = db.collection('staking').document(contract_address)
        staking_ref.set({
            'user_id': user_id,
            'amount': amount,
            'contract_address': contract_address,
            'created_at': datetime.now(),
            'status': 'active'
        })
        logger.info(f"Saved staking contract {contract_address} for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to save staking contract: {e}")