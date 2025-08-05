import os
import json
import requests
from config import config
from typing import Dict, Optional

class TONClient:
    def __init__(self):
        self.network = config.TON_NETWORK
        self.api_key = config.TON_API_KEY
        self.base_url = "https://toncenter.com/api/v3" if self.network == "mainnet" else "https://testnet.toncenter.com/api/v3"
        
    def get_balance(self, address: str) -> float:
        """Get balance in TON"""
        endpoint = f"{self.base_url}/getAddressBalance"
        headers = {"X-API-Key": self.api_key}
        params = {"address": address}
        
        try:
            response = requests.get(endpoint, headers=headers, params=params)
            data = response.json()
            if data.get("ok"):
                return int(data["result"]) / 1e9  # Convert nanoton to TON
        except Exception as e:
            print(f"Balance check error: {e}")
        return 0.0
    
    def send_transaction(self, from_address: str, to_address: str, amount: float, private_key: str) -> Optional[Dict]:
        """Send TON transaction"""
        endpoint = f"{self.base_url}/sendTransaction"
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "source": from_address,
            "destination": to_address,
            "amount": int(amount * 1e9),  # Convert to nanoton
            "privateKey": private_key,
            "message": "CryptoGameBot Withdrawal"
        }
        
        try:
            response = requests.post(endpoint, headers=headers, json=payload)
            data = response.json()
            if data.get("ok"):
                return {
                    "tx_hash": data["result"]["hash"],
                    "explorer_url": f"{config.TONSCAN_URL}/tx/{data['result']['hash']}"
                }
        except Exception as e:
            print(f"Transaction error: {e}")
        return None
    
    def get_transaction_fee_estimate(self, amount: float) -> float:
        """Get estimated transaction fee"""
        # TON fees are typically very low (0.0001-0.001 TON)
        return max(0.0005, amount * 0.005)  # 0.5% or min 0.0005 TON

# Singleton instance
ton_client = TONClient()