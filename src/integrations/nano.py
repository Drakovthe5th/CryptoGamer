import logging
import nanopy

logger = logging.getLogger(__name__)

class NanoWallet:
    def __init__(self, seed, representative):
        self.seed = seed
        self.representative = representative
        self.rpc = nanopy.rpc(host='https://mynano.ninja/api/node')
        
        try:
            # Create account from seed
            self.account = nanopy.Account(seed=seed)
            
            # Get account address
            self.address = nanopy.account_key(account_key=self.account.key)
            
            logger.info(f"Nano wallet initialized. Address: {self.address}")
        except Exception as e:
            logger.error(f"Failed to initialize Nano wallet: {e}")
            self.account = None
            self.address = None

    def get_balance(self):
        if not self.account:
            return 0.0
        try:
            balance = self.rpc.account_balance(account=self.address)
            return float(balance['balance']) / 10**30
        except Exception as e:
            logger.error(f"Failed to get Nano balance: {e}")
            return 0.0

    def send_transaction(self, to_address, amount):
        if not self.account:
            return False
        try:
            wallet = nanopy.Wallet(seed=self.seed)
            amount_raw = int(amount * 10**30)
            
            # Create and process block
            block = self.account.send(
                wallet=wallet,
                to_addr=to_address,
                amount=amount_raw,
                representative=self.representative
            )
            logger.info(f"Sent {amount} NANO to {to_address}. Block: {block['hash']}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Nano transaction: {e}")
            return False

# Global wallet instance
nano_wallet = None

def initialize_nano_wallet(seed, representative):
    global nano_wallet
    if seed and representative:
        nano_wallet = NanoWallet(seed, representative)
    return nano_wallet