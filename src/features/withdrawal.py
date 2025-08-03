from src.integrations.nano import send_transaction
from src.integrations.mpesa import process_mpesa_withdrawal
from src.integrations.paypal import create_payout
from src.utils.conversions import to_raw, usd_to_xno
from src.database.firebase import db, SERVER_TIMESTAMP
from config import Config
import time
import logging

logger = logging.getLogger(__name__)

def process_withdrawal(user_id: int, method: str, amount: float, details: dict):
    # Record withdrawal attempt
    withdrawal_ref = db.collection('withdrawals').document()
    withdrawal_data = {
        'user_id': user_id,
        'method': method,
        'amount': amount,
        'details': details,
        'status': 'processing',
        'created_at': SERVER_TIMESTAMP
    }
    withdrawal_ref.set(withdrawal_data)
    
    # Process based on method
    try:
        if method == 'nano':
            raw_amount = to_raw(amount)
            tx_hash = send_transaction(details['address'], raw_amount)
            result = {'status': 'success', 'tx_id': tx_hash}
        
        elif method == 'mpesa':
            response = process_mpesa_withdrawal(details['phone'], amount)
            if response.get('ResponseCode') == '0':
                result = {'status': 'success', 'tx_id': response.get('CheckoutRequestID', '')}
            else:
                error_msg = response.get('errorMessage', '') or response.get('error', 'Unknown M-Pesa error')
                result = {'status': 'failed', 'error': error_msg}
                
        elif method == 'paypal':
            # Convert XNO to USD
            usd_amount = usd_to_xno(amount, inverse=True)
            
            # Process PayPal payout
            payout = create_payout(details['email'], usd_amount)
            
            if payout['status'] == 'success':
                result = {
                    'status': 'success', 
                    'tx_id': payout['payout_batch_id'],
                    'paypal_status': payout['status']
                }
            else:
                result = {'status': 'failed', 'error': payout.get('error', 'Unknown PayPal error')}
                
        else:
            result = {'status': 'failed', 'error': 'Invalid withdrawal method'}
            
    except Exception as e:
        logger.error(f"Withdrawal processing failed: {str(e)}")
        result = {'status': 'failed', 'error': str(e)}
    
    # Update withdrawal status
    withdrawal_ref.update({
        'status': result['status'],
        'result': result
    })
    
    # Record transaction
    tx_type = 'withdrawal_success' if result['status'] == 'success' else 'withdrawal_failed'
    db.collection('transactions').add({
        'user_id': user_id,
        'type': tx_type,
        'amount': amount,
        'method': method,
        'timestamp': SERVER_TIMESTAMP,
        'status': result['status'],
        'details': result
    })
    
    return result