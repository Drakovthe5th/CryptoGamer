import logging
from nanopy import Account
from config import config
import requests

logger = logging.getLogger(__name__)

class NanoWallet:
    def __init__(self, seed, representative):
        self.account = Account(seed=seed, index=0, representative=representative)
        logger.info(f"Nano wallet initialized. Address: {self.account.address}")

    def get_address(self) -> str:
        return self.account.address

    def send_transaction(self, destination: str, amount: int) -> str:
        try:
            # Convert amount to raw
            raw_amount = int(amount * (10**30))
            
            # Create and publish send block
            block = self.account.send(destination, raw_amount)
            return block.hash
        except Exception as e:
            logger.error(f"Error sending transaction: {e}")
            raise

# Singleton wallet instance
nano_wallet = None

def initialize_nano_wallet(seed, representative):
    global nano_wallet
    if not nano_wallet:
        nano_wallet = NanoWallet(seed, representative)

def get_wallet_address() -> str:
    return nano_wallet.get_address() if nano_wallet else ""

def send_transaction(destination: str, amount: int) -> str:
    return nano_wallet.send_transaction(destination, amount) if nano_wallet else ""