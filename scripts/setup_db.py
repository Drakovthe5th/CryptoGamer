from src.database.firebase import initialize_firebase
from config import config
import firebase_admin
from firebase_admin import firestore

def create_collections():
    db = firestore.client()
    
    # Create collections with sample documents
    users = db.collection('users')
    if not users.limit(1).get():
        users.add({
            'user_id': 1,
            'username': 'Admin',
            'balance': 0.0,
            'points': 0,
            'last_played': {},
            'referral_count': 0,
            'withdrawal_methods': {},
            'completed_quests': {}
        })
    
    quests = db.collection('quests')
    if not quests.limit(1).get():
        quests.add({
            'title': 'Daily Login',
            'description': 'Visit the app every day',
            'reward_xno': 0.1,
            'reward_points': 10,
            'active': True,
            'completions': 0
        })

if __name__ == '__main__':
    # Initialize Firebase
    initialize_firebase(config.FIREBASE_CREDS)
    
    # Create required collections
    create_collections()
    print("Database setup complete!")