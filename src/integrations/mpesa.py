import os
import requests
import base64
import datetime
import logging
from config import Config

logger = logging.getLogger(__name__)

def generate_mpesa_credentials():
    """Generate M-Pesa API credentials"""
    consumer_key = Config.MPESA_CONSUMER_KEY
    consumer_secret = Config.MPESA_CONSUMER_SECRET
    credentials = f"{consumer_key}:{consumer_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    return encoded_credentials

def get_mpesa_token():
    """Get M-Pesa access token"""
    try:
        url = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        headers = {
            "Authorization": f"Basic {generate_mpesa_credentials()}"
        }
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            logger.error(f"M-Pesa token error: {response.text}")
            return None
    except Exception as e:
        logger.error(f"M-Pesa token exception: {e}")
        return None

def send_mpesa_payment(phone: str, amount: float, currency: str):
    """Send payment via M-Pesa"""
    try:
        # Convert to KES if needed
        if currency != "KES":
            # In real implementation, convert using exchange rate
            amount_kes = amount * 150  # Simplified conversion
        else:
            amount_kes = amount
            
        access_token = get_mpesa_token()
        if not access_token:
            return {"status": "error", "error": "Failed to get token"}
            
        url = "https://api.safaricom.co.ke/mpesa/b2c/v1/paymentrequest"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "InitiatorName": Config.MPESA_INITIATOR_NAME,
            "SecurityCredential": Config.MPESA_SECURITY_CREDENTIAL,
            "CommandID": "BusinessPayment",
            "Amount": amount_kes,
            "PartyA": Config.MPESA_BUSINESS_SHORTCODE,
            "PartyB": phone,
            "Remarks": "CryptoGameBot Withdrawal",
            "QueueTimeOutURL": Config.MPESA_CALLBACK_URL,
            "ResultURL": Config.MPESA_CALLBACK_URL,
            "Occasion": "Payment"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            logger.info(f"M-Pesa payment initiated: {response.json()}")
            return {"status": "success", "response": response.json()}
        else:
            logger.error(f"M-Pesa payment failed: {response.text}")
            return {"status": "error", "error": response.text}
    except Exception as e:
        logger.error(f"M-Pesa payment exception: {e}")
        return {"status": "error", "error": str(e)}