from src.database.firebase import initialize_firebase, db
from src.features.withdrawal import process_withdrawal
from config import Config
import logging
from google.cloud.firestore_v1 import SERVER_TIMESTAMP

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def process_pending_withdrawals():
    initialize_firebase(Config.FIREBASE_CREDS)
    
    # Query pending withdrawals
    withdrawals_ref = db.collection('withdrawals')
    pending_withdrawals = withdrawals_ref.where('status', '==', 'pending').stream()
    
    processed_count = 0
    failed_count = 0
    
    for withdrawal in pending_withdrawals:
        wd_data = withdrawal.to_dict()
        try:
            # Process withdrawal
            result = process_withdrawal(
                wd_data['user_id'],
                wd_data['method'],
                wd_data['amount'],
                wd_data['details']
            )
            
            if result and result.get('status') == 'success':
                # Update withdrawal status
                withdrawal_ref = withdrawals_ref.document(withdrawal.id)
                withdrawal_ref.update({
                    'status': 'processing',
                    'processed_at': SERVER_TIMESTAMP,
                    'result': result
                })
                processed_count += 1
                logging.info(f"Processed withdrawal {withdrawal.id} for user {wd_data['user_id']}")
            else:
                raise Exception("Withdrawal processor returned failure")
                
        except Exception as e:
            # Mark as failed after 3 attempts
            attempts = wd_data.get('attempts', 0) + 1
            status = 'failed' if attempts >= 3 else 'pending'
            
            withdrawals_ref.document(withdrawal.id).update({
                'status': status,
                'attempts': attempts,
                'last_error': str(e)
            })
            
            failed_count += 1
            logging.error(f"Failed to process withdrawal {withdrawal.id}: {str(e)}")
    
    logging.info(f"Processed {processed_count} withdrawals, {failed_count} failed")

if __name__ == '__main__':
    process_pending_withdrawals()