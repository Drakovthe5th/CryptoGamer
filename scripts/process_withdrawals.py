import time
import logging
from src.database.firebase import db
from src.integrations.tonE2 import ton_manager
from src.integrations.mpesa import send_mpesa_payment
from src.integrations.paypal import create_payout
from src.integrations.banking import process_bank_transfer
from config import Config

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def process_ton_withdrawals():
    """Process pending TON withdrawals"""
    pending_withdrawals = db.collection('withdrawals').where('status', '==', 'pending').where('method', '==', 'ton').stream()
    
    for withdrawal in pending_withdrawals:
        data = withdrawal.to_dict()
        try:
            # Send TON transaction
            tx_hash = ton_manager.send_transaction(
                to_address=data['details']['address'],
                amount=data['amount']
            )
            
            if tx_hash:
                withdrawal.reference.update({
                    'status': 'completed',
                    'tx_hash': tx_hash,
                    'completed_at': time.time()
                })
                logger.info(f"TON withdrawal processed: {withdrawal.id}")
            else:
                withdrawal.reference.update({
                    'status': 'failed',
                    'error': 'Blockchain transaction failed'
                })
                logger.error(f"TON withdrawal failed: {withdrawal.id}")
                
        except Exception as e:
            withdrawal.reference.update({
                'status': 'failed',
                'error': str(e)
            })
            logger.error(f"TON withdrawal error: {e}")

def process_otc_withdrawals():
    """Process pending OTC desk withdrawals"""
    pending_otc = db.collection('otc_deals').where('status', '==', 'pending').stream()
    
    for deal in pending_otc:
        data = deal.to_dict()
        try:
            # Process based on payment method
            if data['payment_method'] == 'M-Pesa':
                result = send_mpesa_payment(
                    phone=data['details']['phone'],
                    amount=data['quote']['total'],
                    currency=data['currency']
                )
            elif data['payment_method'] == 'PayPal':
                result = create_payout(
                    email=data['details']['email'],
                    amount=data['quote']['total'],
                    currency=data['currency']
                )
            elif data['payment_method'] == 'Bank Transfer':
                result = process_bank_transfer(
                    iban=data['details']['iban'],
                    amount=data['quote']['total'],
                    currency=data['currency']
                )
            
            if result and result.get('status') == 'success':
                deal.reference.update({'status': 'completed'})
                logger.info(f"OTC deal processed: {deal.id}")
            else:
                deal.reference.update({
                    'status': 'failed',
                    'error': result.get('error', 'Payment failed')
                })
                logger.error(f"OTC deal failed: {deal.id}")
                
        except Exception as e:
            deal.reference.update({
                'status': 'failed',
                'error': str(e)
            })
            logger.error(f"OTC deal error: {e}")

def main():
    logger.info("Starting withdrawal processing service")
    while True:
        try:
            process_ton_withdrawals()
            process_otc_withdrawals()
            time.sleep(60)  # Process every minute
        except Exception as e:
            logger.error(f"Processing loop error: {e}")
            time.sleep(300)  # Wait 5 minutes on error

if __name__ == '__main__':
    main()