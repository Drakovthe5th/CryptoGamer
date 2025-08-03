import base64
import os
import json
import time
from config import config
import requests
import logging

logger = logging.getLogger(__name__)

class MPESA:
    def __init__(self, environment="sandbox"):
        self.environment = environment
        self.base_url = "https://sandbox.safaricom.co.ke" if environment == "sandbox" else "https://api.safaricom.co.ke"
        self.access_token = self.get_access_token()
    
    def get_access_token(self):
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        headers = {
            'Authorization': 'Basic ' + base64.b64encode(
                f"{config.MPESA_CONSUMER_KEY}:{config.MPESA_CONSUMER_SECRET}".encode()
            ).decode()
        }
        response = requests.get(url, headers=headers)
        return response.json().get('access_token')
    
    def customer_to_bussiness(self, transaction):
        url = f"{self.base_url}/mpesa/c2b/v1/simulate"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        payload = {
            "CommandID": "CustomerPayBillOnline",
            "Amount": transaction["input_Amount"],
            "Msisdn": transaction["input_CustomerMSISDN"],
            "BillRefNumber": transaction["input_TransactionReference"],
            "ShortCode": transaction["input_ServiceProviderCode"]
        }
        response = requests.post(url, json=payload, headers=headers)
        return response.json()

def process_mpesa_withdrawal(phone: str, amount: float):
    try:
        # Initialize MPESA client
        mpesa = MPESA(environment="sandbox" if config.MPESA_SANDBOX else "production")
        
        # Prepare transaction data
        transaction = {
            "input_Amount": str(amount),
            "input_Country": "KEN",
            "input_Currency": "KES",
            "input_CustomerMSISDN": phone,
            "input_ServiceProviderCode": config.MPESA_SHORTCODE,
            "input_ThirdPartyConversationID": f"cryptogame_{int(time.time())}",
            "input_TransactionReference": f"CRYPTO_{int(time.time())}",
            "input_PurchasedItemsDesc": "Crypto Rewards"
        }
        
        # Process C2B transaction
        return mpesa.customer_to_bussiness(transaction)
    except Exception as e:
        logger.error(f"M-Pesa withdrawal error: {str(e)}")
        return {
            'ResponseCode': '1',
            'errorMessage': str(e)
        }