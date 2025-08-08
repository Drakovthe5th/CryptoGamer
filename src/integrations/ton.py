import os
import time
import logging
import requests
import asyncio
from datetime import datetime, timedelta
from tonsdk.wallet import Wallets, WalletVersionEnum
from tonsdk.utils import to_nano
from pytoniq import LiteClient
from pytoniq_core import begin_cell, Address

logger = logging.getLogger(__name__)

class TONWallet:
    def __init__(self):
        self.client = None
        self.wallet = None
        self.last_balance_check = datetime.min
        self.balance_cache = 0.0
        self.last_tx_check = datetime.min
        self.pending_withdrawals = {}
        self.initialized = False
        self.connection_retries = 0
        self.MAX_RETRIES = 3
        self.mnemonic = os.getenv("TON_MNEMONIC")
        self.network = os.getenv("TON_NETWORK", "testnet").lower()
        self.is_testnet = self.network == "testnet"

        if not self.mnemonic:
            raise ValueError("TON_MNEMONIC not set in environment")

    async def initialize(self):
        """Initialize TON wallet from mnemonic."""
        try:
            # Select correct lite servers
            if self.is_testnet:
                self.client = LiteClient.from_testnet_config(ls_i=0, trust_level=2, timeout=60)
            else:
                self.client = LiteClient.from_mainnet_config(ls_i=0, trust_level=2, timeout=60)

            # Retry connection
            while self.connection_retries < self.MAX_RETRIES:
                try:
                    await self.client.connect()
                    break
                except (asyncio.TimeoutError, ConnectionError) as e:
                    self.connection_retries += 1
                    wait_time = 2 ** self.connection_retries
                    logger.warning(
                        f"TON connection failed (attempt {self.connection_retries}/{self.MAX_RETRIES}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)

            if self.connection_retries >= self.MAX_RETRIES:
                raise ConnectionError("Failed to connect to TON network after multiple attempts")

            # Derive wallet from mnemonic
            wallet_instance = Wallets.from_mnemonic(self.mnemonic.split(), WalletVersionEnum.v4r2, self.is_testnet)
            self.wallet = wallet_instance.create()

            derived_address = self.wallet.address.to_string(True, True, self.is_testnet)
            logger.info(f"TON Hot Wallet ({self.network}): {derived_address}")

            self.initialized = True
            return True

        except Exception as e:
            logger.exception("TON wallet initialization failed")
            self.initialized = False
            return False

    async def get_balance(self, force_update=False) -> float:
        """Get current wallet balance in TON."""
        try:
            if not force_update and (datetime.now() - self.last_balance_check < timedelta(minutes=5)):
                return self.balance_cache

            if not self.initialized:
                await self.initialize()

            balance = await self.wallet.get_balance()
            ton_balance = balance / 1e9

            self.balance_cache = ton_balance
            self.last_balance_check = datetime.now()

            min_hot_balance = float(os.getenv("MIN_HOT_BALANCE", 0))
            if ton_balance < min_hot_balance:
                self.send_alert(f"🔥 TON HOT WALLET LOW BALANCE: {ton_balance:.6f} TON")

            return ton_balance
        except Exception as e:
            logger.error(f"Failed to get TON balance: {e}")
            return 0.0

    async def send_transaction(self, destination: str, amount: float, memo: str = "") -> dict:
        """Send TON transaction."""
        try:
            if not self.initialized:
                await self.initialize()

            amount_nano = to_nano(amount, "ton")

            body = begin_cell()
            if memo:
                body.store_uint(0, 32)
                body.store_string(memo)
            body = body.end_cell()

            result = await self.wallet.transfer(
                destination=Address(destination),
                amount=amount_nano,
                body=body,
                timeout=120
            )

            logger.info(f"TON transaction sent: {amount:.6f} TON to {destination}")
            return {
                'status': 'success',
                'tx_hash': result.get('hash', None),
                'amount': amount,
                'destination': destination
            }
        except Exception as e:
            logger.error(f"TON transaction failed: {e}")
            return {'status': 'error', 'error': str(e)}

    async def process_withdrawal(self, user_id: int, amount: float, address: str) -> dict:
        """Process TON withdrawal."""
        try:
            user_limit = float(os.getenv("USER_DAILY_WITHDRAWAL_LIMIT", 100))
            system_limit = float(os.getenv("DAILY_WITHDRAWAL_LIMIT", 1000))

            if self.get_user_daily_withdrawal(user_id) + amount > user_limit:
                return {'status': 'error', 'error': f"Daily withdrawal limit exceeded: {user_limit} TON"}

            if self.get_system_daily_withdrawal() + amount > system_limit:
                return {'status': 'error', 'error': "System daily withdrawal limit reached"}

            result = await self.send_transaction(address, amount, f"Withdrawal for user {user_id}")

            if result['status'] == 'success':
                self.update_withdrawal_limits(user_id, amount)
                logger.info(f"Withdrawal processed: {amount:.6f} TON to {address}")
            else:
                logger.error(f"Withdrawal failed for user {user_id}: {result.get('error')}")

            return result
        except Exception as e:
            logger.error(f"Withdrawal processing failed: {e}")
            return {'status': 'error', 'error': str(e)}

    def get_user_daily_withdrawal(self, user_id: int) -> float:
        return 0.0  # TODO: connect to DB

    def get_system_daily_withdrawal(self) -> float:
        return 0.0  # TODO: connect to DB

    def update_withdrawal_limits(self, user_id: int, amount: float):
        pass  # TODO: connect to DB

    def send_alert(self, message: str):
        webhook = os.getenv("ALERT_WEBHOOK")
        if webhook:
            try:
                requests.post(webhook, json={'text': message})
            except Exception as e:
                logger.error(f"Failed to send alert: {e}")
        logger.warning(message)

    async def close(self):
        if self.client:
            try:
                await self.client.close()
                logger.info("TON client connection closed")
            except Exception as e:
                logger.error(f"Error closing TON client: {e}")

# Global instance
ton_wallet = TONWallet()

async def initialize_ton_wallet():
    return await ton_wallet.initialize()

async def close_ton_wallet():
    return await ton_wallet.close()

def is_valid_ton_address(address: str) -> bool:
    try:
        Address(address)
        return True
    except:
        return False
