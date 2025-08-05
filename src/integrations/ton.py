import os
import time
import logging
import requests
import base64
import asyncio
from datetime import datetime, timedelta
from tontools import TonCenterClient, Wallet
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

    async def initialize(self):
        """Initialize TON wallet connection using TonTools"""
        try:
            # Initialize TonCenter client
            self.client = TonCenterClient(
                base_url='https://toncenter.com/api/v2/',
                api_key=config.TON_API_KEY,
                testnet=(config.TON_NETWORK != "mainnet")
            )
            
            # Initialize wallet from mnemonic or private key
            if config.TON_WALLET_MNEMONIC:
                self.wallet = Wallet(
                    provider=self.client,
                    mnemonics=config.TON_WALLET_MNEMONIC.split(),
                    version='v4r2'
                )
            elif config.TON_PRIVATE_KEY:
                # Convert base64 encoded private key to bytes
                private_key = base64.b64decode(config.TON_PRIVATE_KEY)
                self.wallet = Wallet(
                    provider=self.client,
                    private_key=private_key,
                    version='v4r2'
                )
            else:
                raise ValueError("No wallet credentials provided")
            
            # Verify wallet address
            wallet_address = self.wallet.address
            if wallet_address != config.TON_HOT_WALLET:
                logger.warning(f"Wallet address mismatch: {wallet_address} vs {config.TON_HOT_WALLET}")
            
            logger.info(f"TON wallet initialized: {wallet_address}")
            self.initialized = True
            return True
        except Exception as e:
            logger.error(f"TON wallet initialization failed: {e}")
            self.initialized = False
            return False

    async def get_balance(self, force_update=False) -> float:
        """Get current wallet balance in TON"""
        try:
            # Use cache to avoid frequent requests
            if not force_update and (datetime.now() - self.last_balance_check < timedelta(minutes=5)):
                return self.balance_cache
                
            if not self.initialized:
                await self.initialize()
                
            balance = await self.wallet.get_balance()
            ton_balance = balance / 1e9  # Convert nanoton to TON
            
            self.balance_cache = ton_balance
            self.last_balance_check = datetime.now()
            
            # Check if below threshold
            if ton_balance < config.MIN_HOT_BALANCE:
                self.send_alert(f"🔥 TON HOT WALLET LOW BALANCE: {ton_balance:.6f} TON")
            
            return ton_balance
        except Exception as e:
            logger.error(f"Failed to get TON balance: {e}")
            return 0.0

    async def send_transaction(self, destination: str, amount: float, memo: str = "") -> dict:
        """Send TON transaction to external address"""
        try:
            if not self.initialized:
                await self.initialize()
                
            # Convert TON to nanoton
            amount_nano = int(amount * 1e9)
            
            # Send transaction with memo
            tx_hash = await self.wallet.transfer_ton(
                destination_address=destination,
                amount=amount_nano,
                message=memo
            )
            
            logger.info(f"TON transaction sent: {amount:.6f} TON to {destination}")
            return {
                'status': 'success',
                'tx_hash': tx_hash,
                'amount': amount,
                'destination': destination
            }
        except Exception as e:
            logger.error(f"TON transaction failed: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

    async def process_withdrawal(self, user_id: int, amount: float, address: str) -> dict:
        """Process TON withdrawal with rate limiting and security checks"""
        try:
            # Check daily user limit
            user_daily = self.get_user_daily_withdrawal(user_id)
            if user_daily + amount > config.USER_DAILY_WITHDRAWAL_LIMIT:
                return {
                    'status': 'error',
                    'error': f"Daily withdrawal limit exceeded: {config.USER_DAILY_WITHDRAWAL_LIMIT} TON"
                }
                
            # Check system daily limit
            system_daily = self.get_system_daily_withdrawal()
            if system_daily + amount > config.DAILY_WITHDRAWAL_LIMIT:
                return {
                    'status': 'error',
                    'error': "System daily withdrawal limit reached"
                }
                
            # Process transaction
            result = await self.send_transaction(address, amount, f"Withdrawal for user {user_id}")
            
            if result['status'] == 'success':
                # Update limits
                self.update_withdrawal_limits(user_id, amount)
                logger.info(f"Withdrawal processed: {amount:.6f} TON to {address}")
            else:
                logger.error(f"Withdrawal failed for user {user_id}: {result.get('error')}")
                
            return result
        except Exception as e:
            logger.error(f"Withdrawal processing failed: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def get_user_daily_withdrawal(self, user_id: int) -> float:
        """Get user's daily withdrawal amount (from database)"""
        # In production, this would query Firestore
        return 0.0  # Stub implementation

    def get_system_daily_withdrawal(self) -> float:
        """Get system's daily withdrawal total (from database)"""
        # In production, this would query Firestore
        return 0.0  # Stub implementation

    def update_withdrawal_limits(self, user_id: int, amount: float):
        """Update withdrawal limits in database"""
        # Stub implementation - would update Firestore
        pass

    def send_alert(self, message: str):
        """Send alert notification"""
        if config.ALERT_WEBHOOK:
            try:
                requests.post(config.ALERT_WEBHOOK, json={'text': message})
            except Exception as e:
                logger.error(f"Failed to send alert: {e}")
        logger.warning(message)

    async def close(self):
        """Close TON connection"""
        # TonTools doesn't require explicit closing
        logger.info("TON client connection closed")

# Global TON wallet instance
ton_wallet = TONWallet()

async def initialize_ton_wallet():
    """Initialize TON wallet connection"""
    return await ton_wallet.initialize()

async def close_ton_wallet():
    """Close TON wallet connection"""
    return await ton_wallet.close()

def validate_ton_address(address: str) -> bool:
    """Validate TON wallet address format"""
    try:
        # Basic validation
        if not address.startswith(('EQ', 'UQ')) or len(address) < 48:
            return False
            
        # Advanced validation would happen during transaction
        return True
    except:
        return False

async def process_ton_withdrawal(user_id: int, amount: float, address: str):
    """Process TON withdrawal (public interface)"""
    return await ton_wallet.process_withdrawal(user_id, amount, address)