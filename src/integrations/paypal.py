import paypalrestsdk
from config import Config
import logging

logger = logging.getLogger(__name__)

def initialize_paypal():
    paypalrestsdk.configure({
        "mode": Config.PAYPAL_MODE,
        "client_id": Config.PAYPAL_CLIENT_ID,
        "client_secret": Config.PAYPAL_CLIENT_SECRET
    })

def create_payout(email: str, amount: float, currency="USD"):
    """Create a PayPal payout to a user's email"""
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
                "note": "Thank you for playing CryptoGameBot!",
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

def get_payout_status(payout_batch_id: str):
    """Check the status of a PayPal payout"""
    payout = paypalrestsdk.Payout.find(payout_batch_id)
    return payout.batch_header.batch_status

def verify_paypal_webhook(headers, body):
    """Verify PayPal webhook signature"""
    return paypalrestsdk.WebhookEvent.verify(
        headers,
        body,
        Config.PAYPAL_WEBHOOK_ID
    )