import os
import paypalrestsdk
import time
import logging
from config import Config

logger = logging.getLogger(__name__)

def initialize_paypal():
    try:
        paypalrestsdk.configure({
            "mode": Config.PAYPAL_MODE,
            "client_id": Config.PAYPAL_CLIENT_ID,
            "client_secret": Config.PAYPAL_CLIENT_SECRET
        })
        logger.info("PayPal initialized successfully")
        return True
    except Exception as e:
        logger.error(f"PayPal initialization failed: {e}")
        return False

def create_payout(email: str, amount: float, currency="USD"):
    """Create a PayPal payout to a user's email"""
    try:
        payout = paypalrestsdk.Payout({
            "sender_batch_header": {
                "sender_batch_id": f"BATCH-{int(time.time())}",
                "email_subject": "CryptoGameBot Withdrawal"
            },
            "items": [
                {
                    "recipient_type": "EMAIL",
                    "amount": {
                        "value": f"{amount:.2f}",
                        "currency": currency
                    },
                    "receiver": email,
                    "note": "Reward from CryptoGameBot",
                    "sender_item_id": f"ITEM-{int(time.time())}"
                }
            ]
        })
        
        if payout.create(sync_mode=True):
            logger.info(f"PayPal payout created: {payout.batch_header.payout_batch_id}")
            return {
                "status": "success",
                "payout_batch_id": payout.batch_header.payout_batch_id,
                "status": payout.batch_header.batch_status
            }
        else:
            logger.error(f"PayPal payout failed: {payout.error}")
            return {
                "status": "failed",
                "error": payout.error
            }
    except Exception as e:
        logger.error(f"PayPal payout exception: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

def get_payout_status(payout_batch_id: str):
    """Check the status of a PayPal payout"""
    try:
        payout = paypalrestsdk.Payout.find(payout_batch_id)
        return payout.batch_header.batch_status
    except Exception as e:
        logger.error(f"Error getting payout status: {e}")
        return "UNKNOWN"

def verify_paypal_webhook(headers, body):
    """Verify PayPal webhook signature"""
    try:
        return paypalrestsdk.WebhookEvent.verify(
            headers,
            body,
            Config.PAYPAL_WEBHOOK_ID
        )
    except Exception as e:
        logger.error(f"PayPal webhook verification failed: {e}")
        return False
    
def process_paypal_payment(email: str, amount: float, currency: str = "USD"):
    """Process PayPal payment (wrapper for create_payout)"""
    payout_result = create_payout(email, amount, currency)
    
    if payout_result['status'] == 'success':
        return {
            'status': 'success',
            'transaction_id': payout_result['payout_batch_id']
        }
    return {
        'status': 'failed',
        'error': payout_result.get('error', 'Unknown PayPal error')
    }
