import os
import requests
import base64
from datetime import time
import logging
from config import config

logger = logging.getLogger(__name__)

def generate_mpesa_credentials() -> str:
    """Generate M-Pesa API credentials"""
    consumer_key = config.MPESA_CONSUMER_KEY
    consumer_secret = config.MPESA_CONSUMER_SECRET
    return base64.b64encode(f"{consumer_key}:{consumer_secret}".encode()).decode()

def get_mpesa_token() -> str:
    """Get M-Pesa access token with retry logic"""
    for _ in range(3):  # 3 retries
        try:
            response = requests.get(
                "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials",
                headers={"Authorization": f"Basic {generate_mpesa_credentials()}"},
                timeout=5
            )
            if response.status_code == 200:
                return response.json().get("access_token")
            logger.error(f"M-Pesa token error: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"M-Pesa token exception: {e}")
        time.sleep(1)  # Wait before retry
    return None

def send_mpesa_payment(phone: str, amount: float, currency: str = "KES") -> dict:
    """Send payment via M-Pesa with proper error handling"""
    try:
        # Convert to KES if needed
        if currency != "KES":
            # Use actual exchange rate service in production
            amount_kes = amount * config.EXCHANGE_RATES['USD_TO_KES']
        else:
            amount_kes = amount
            
        access_token = get_mpesa_token()
        if not access_token:
            return {"status": "error", "error": "Failed to get token"}
            
        payload = {
            "InitiatorName": config.MPESA_INITIATOR_NAME,
            "SecurityCredential": config.MPESA_SECURITY_CREDENTIAL,
            "CommandID": "BusinessPayment",
            "Amount": amount_kes,
            "PartyA": config.MPESA_BUSINESS_SHORTCODE,
            "PartyB": phone,
            "Remarks": "CryptoGameBot Withdrawal",
            "QueueTimeOutURL": config.MPESA_CALLBACK_URL,
            "ResultURL": config.MPESA_CALLBACK_URL,
            "Occasion": "Payment"
        }
        
        response = requests.post(
            "https://api.safaricom.co.ke/mpesa/b2c/v1/paymentrequest",
            json=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"M-Pesa payment initiated: {response.json()}")
            return {"status": "success", "response": response.json()}
        else:
            logger.error(f"M-Pesa payment failed: {response.text}")
            return {"status": "error", "error": response.text}
    except Exception as e:
        logger.error(f"M-Pesa payment exception: {e}")
        return {"status": "error", "error": str(e)}