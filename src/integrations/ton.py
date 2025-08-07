import os
import time
import logging
import requests
import base64
import asyncio
from datetime import datetime, timedelta
from pytoniq import LiteClient, WalletV4R2
from pytoniq_core import begin_cell, Address
from config import config

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
        self.is_testnet = config.TON_NETWORK.lower() == "testnet"

    async def initialize(self):
        """Initialize TON wallet connection and derive hot wallet address automatically."""
        try:
            # Select correct lite servers
            if self.is_testnet:
                self.client = LiteClient.from_testnet_config(ls_i=0, trust_level=2, timeout=60)
            else:
                self.client = LiteClient.from_mainnet_config(ls_i=0, trust_level=2, timeout=60)

            # Retry connection with exponential backoff
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

            # Load private key
            if not config.TON_PRIVATE_KEY:
                raise ValueError("No TON private key provided")
            private_key = base64.b64decode(config.TON_PRIVATE_KEY)

            # Create wallet
            self.wallet = WalletV4R2(provider=self.client, private_key=private_key)

            # Derive network-specific address
            derived_address = self.wallet.address.to_str(test_only=self.is_testnet)

            # Log the hot wallet address
            logger.info(f"TON Hot Wallet ({config.TON_NETWORK}): {derived_address}")

            # Warn if config had a mismatched address
            if getattr(config, "TON_HOT_WALLET", None):
                config_addr_raw = Address(config.TON_HOT_WALLET).to_str(is_user_friendly=False)
                derived_addr_raw = Address(derived_address).to_str(is_user_friendly=False)
                if config_addr_raw != derived_addr_raw:
                    logger.warning(f"Config wallet address does not match derived address: {config.TON_HOT_WALLET} vs {derived_address}")

            # Always overwrite config to avoid mismatch issues
            config.TON_HOT_WALLET = derived_address

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
            ton_balance = balance / 1e9  # nanoton to TON

            self.balance_cache = ton_balance
            self.last_balance_check = datetime.now()

            if ton_balance < config.MIN_HOT_BALANCE:
                self.send_alert(f"🔥 TON HOT WALLET LOW BALANCE: {ton_balance:.6f} TON")

            return ton_balance
        except Exception as e:
            logger.error(f"Failed to get TON balance: {e}")
            return 0.0

    async def send_transaction(self, destination: str, amount: float, memo: str = "") -> dict:
        """Send TON transaction to external address."""
        try:
            if not self.initialized:
                await self.initialize()

            amount_nano = int(amount * 1e9)

            body = begin_cell()
            if memo:
                body.store_uint(0, 32)  # op code for comment
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
                'tx_hash': result['hash'],
                'amount': amount,
                'destination': destination
            }
        except Exception as e:
            logger.error(f"TON transaction failed: {e}")
            return {'status': 'error', 'error': str(e)}

    async def process_withdrawal(self, user_id: int, amount: float, address: str) -> dict:
        """Process TON withdrawal with security checks."""
        try:
            if self.get_user_daily_withdrawal(user_id) + amount > config.USER_DAILY_WITHDRAWAL_LIMIT:
                return {'status': 'error', 'error': f"Daily withdrawal limit exceeded: {config.USER_DAILY_WITHDRAWAL_LIMIT} TON"}

            if self.get_system_daily_withdrawal() + amount > config.DAILY_WITHDRAWAL_LIMIT:
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
        return 0.0  # TODO: implement DB logic

    def get_system_daily_withdrawal(self) -> float:
        return 0.0  # TODO: implement DB logic

    def update_withdrawal_limits(self, user_id: int, amount: float):
        pass  # TODO: implement DB logic

    def send_alert(self, message: str):
        if config.ALERT_WEBHOOK:
            try:
                requests.post(config.ALERT_WEBHOOK, json={'text': message})
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
        Address(address)  # will raise if invalid
        return True
    except:
        return False

async def create_staking_contract(user_id: str, amount: float) -> str:
    logger.info(f"Creating staking contract for user {user_id} with {amount} TON")
    return f"EQ_STAKING_{user_id}_{int(time.time())}"

async def execute_swap(user_id: str, from_token: str, to_token: str, amount: float) -> str:
    logger.info(f"Executing swap for user {user_id}: {amount} {from_token} to {to_token}")
    return f"tx_{user_id}_{int(time.time())}"

async def process_ton_withdrawal(user_id: int, amount: float, address: str):
    return await ton_wallet.process_withdrawal(user_id, amount, address)
