import os
import time
import logging
import requests
import base64
import asyncio
from datetime import datetime, timedelta
from pytoniq import LiteClient, WalletV4R2
from pytoniq_core import Cell, begin_cell, Address
from pytoniq_core import Address
from mnemonic import Mnemonic
from src.database.firebase import db
from config import config

# Configure logger
logger = logging.getLogger(__name__)
class TONWallet:
    def __init__(self):
        # Initialize connection parameters
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
        """Initialize TON wallet connection"""
        try:
            # ... (client initialization remains the same)

            if config.TON_PRIVATE_KEY:
                logger.info("Initializing wallet from private key")
                private_key = base64.b64decode(config.TON_PRIVATE_KEY)
                
                # Initialize without providing address
                self.wallet = WalletV4R2(
                    provider=self.client, 
                    private_key=private_key
                )
                
                # Get derived address
                derived_address = self.wallet.address.to_str(is_user_friendly=True, is_bounceable=True)
                logger.info(f"Derived wallet address: {derived_address}")
                
                # Verify against configured address
                config_address = Address(config.TON_HOT_WALLET).to_str(
                    is_user_friendly=True,
                    is_url_safe=True,
                    is_bounceable=True
                )
                
                if derived_address != config_address:
                    logger.error(f"CRITICAL: Wallet address mismatch")
                    logger.error(f"Derived:   {derived_address}")
                    logger.error(f"Configured: {config_address}")
                    raise ValueError("Wallet address mismatch")
                else:
                    logger.info("Wallet address verified successfully")
            else:
                raise ValueError("No TON credentials provided")
            
            # Verify wallet address
            wallet_address = self.wallet.address.to_str()
            config_address = config.TON_HOT_WALLET
            
            # Convert both to raw format for comparison
            if wallet_address.startswith('UQ'):
                wallet_address = Address(wallet_address).to_str(is_user_friendly=False)
            if config_address.startswith('UQ'):
                config_address = Address(config_address).to_str(is_user_friendly=False)
            
            if wallet_address != config_address:
                logger.warning(f"Wallet address mismatch: {self.wallet.address.to_str()} vs {config.TON_HOT_WALLET}")
            else:
                logger.info("Wallet address verified successfully")
            
            logger.info(f"TON wallet initialized: {self.wallet.address.to_str()}")
            self.initialized = True
            return True
        except Exception as e:
            logger.exception(f"TON wallet initialization failed: {str(e)}")
            self.initialized = False
            return False

    def get_address(self):
        """Get wallet address in user-friendly format"""
        if not self.wallet:
            return ""
        return self.wallet.address.to_str(is_user_friendly=True, is_url_safe=True, is_bounceable=True)

    async def get_balance(self, force_update=False) -> float:
        """Get current wallet balance in TON"""
        try:
            # Use cache to avoid frequent requests
            if not force_update and (datetime.now() - self.last_balance_check < timedelta(minutes=5)):
                logger.debug(f"Returning cached balance: {self.balance_cache}")
                return self.balance_cache
                
            if not self.initialized:
                await self.initialize()
                
            logger.info("Fetching wallet balance from blockchain")
            balance = await self.wallet.get_balance()
            ton_balance = balance / 1e9  # Convert nanoton to TON
            
            self.balance_cache = ton_balance
            self.last_balance_check = datetime.now()
            logger.info(f"Wallet balance: {ton_balance:.6f} TON")
            
            # Check if below threshold
            if ton_balance < config.MIN_HOT_BALANCE:
                alert_msg = f"🔥 TON HOT WALLET LOW BALANCE: {ton_balance:.6f} TON"
                logger.warning(alert_msg)
                self.send_alert(alert_msg)
            
            return ton_balance
        except Exception as e:
            logger.error(f"Failed to get TON balance: {str(e)}")
            return 0.0

    async def send_transaction(self, destination: str, amount: float, memo: str = "") -> dict:
        """Send TON transaction to external address"""
        try:
            logger.info(f"Preparing transaction: {amount} TON to {destination}")
            
            if not self.initialized:
                await self.initialize()
                
            # Validate destination address
            if not is_valid_ton_address(destination):
                raise ValueError(f"Invalid TON address: {destination}")
                
            # Convert TON to nanoton
            amount_nano = int(amount * 1e9)
            
            # Prepare message body
            body = begin_cell()
            if memo:
                body.store_uint(0, 32)  # op code for comment
                body.store_string(memo)
            body = body.end_cell()
            
            # Create and send transaction
            logger.info("Creating transfer message")
            result = await self.wallet.transfer(
                destination=Address(destination),
                amount=amount_nano,
                body=body,
                timeout=120
            )
            
            logger.info(f"TON transaction sent: {amount:.6f} TON to {destination}")
            logger.info(f"Transaction hash: {result['hash']}")
            
            return {
                'status': 'success',
                'tx_hash': result['hash'],
                'amount': amount,
                'destination': destination
            }
        except Exception as e:
            logger.error(f"TON transaction failed: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }

    async def send_ton(self, to_address: str, amount: float, memo: str = "") -> str:
        """
        Simplified TON send method
        Returns success message or raises exception on failure
        """
        logger.info(f"Sending {amount} TON to {to_address}")
        result = await self.send_transaction(to_address, amount, memo)
        if result['status'] == 'success':
            return f"Sent {amount} TON to {to_address}"
        else:
            error_msg = f"Failed to send: {result.get('error')}"
            logger.error(error_msg)
            raise Exception(error_msg)

    async def process_withdrawal(self, user_id: int, amount: float, address: str) -> dict:
        db_balance = db.get_user_balance(user_id)
        if amount > db_balance:
            return {
                'status': 'error',
                'error': 'Insufficient funds'
            }
        
        """Process TON withdrawal with rate limiting and security checks"""
        try:
            logger.info(f"Processing withdrawal for user {user_id}: {amount} TON to {address}")
            
            # Validate address before proceeding
            if not is_valid_ton_address(address):
                return {
                    'status': 'error',
                    'error': 'Invalid TON address'
                }
                
            # Check daily user limit
            user_daily = self.get_user_daily_withdrawal(user_id)
            if user_daily + amount > config.USER_DAILY_WITHDRAWAL_LIMIT:
                error_msg = f"Daily withdrawal limit exceeded: {config.USER_DAILY_WITHDRAWAL_LIMIT} TON"
                logger.warning(error_msg)
                return {
                    'status': 'error',
                    'error': error_msg
                }
                
            # Check system daily limit
            system_daily = self.get_system_daily_withdrawal()
            if system_daily + amount > config.DAILY_WITHDRAWAL_LIMIT:
                error_msg = "System daily withdrawal limit reached"
                logger.warning(error_msg)
                return {
                    'status': 'error',
                    'error': error_msg
                }
                
            # Check wallet balance
            balance = await self.get_balance()
            if balance < amount:
                error_msg = f"Insufficient funds. Available: {balance} TON, Required: {amount} TON"
                logger.warning(error_msg)
                return {
                    'status': 'error',
                    'error': error_msg
                }
                
            # Process transaction
            memo = f"Withdrawal for user {user_id}"
            result = await self.send_transaction(address, amount, memo)
            
            if result['status'] == 'success':
                # Update limits
                self.update_withdrawal_limits(user_id, amount)
                logger.info(f"Withdrawal processed: {amount:.6f} TON to {address}")
            else:
                logger.error(f"Withdrawal failed for user {user_id}: {result.get('error')}")
                
            return result
        except Exception as e:
            logger.error(f"Withdrawal processing failed: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def get_user_daily_withdrawal(self, user_id: int) -> float:
        """Get user's daily withdrawal amount (from database)"""
        # Stub implementation - in production, this would query Firestore
        logger.debug(f"Getting daily withdrawal for user {user_id}")
        return 0.0

    def get_system_daily_withdrawal(self) -> float:
        """Get system's daily withdrawal total (from database)"""
        # Stub implementation - in production, this would query Firestore
        logger.debug("Getting system daily withdrawal total")
        return 0.0

    def update_withdrawal_limits(self, user_id: int, amount: float):
        """Update withdrawal limits in database"""
        # Stub implementation - in production, this would update Firestore
        logger.debug(f"Updating withdrawal limits for user {user_id} with amount {amount}")
        pass

    def send_alert(self, message: str):
        """Send alert notification"""
        logger.warning(message)
        if config.ALERT_WEBHOOK:
            try:
                logger.info(f"Sending alert to webhook: {message}")
                requests.post(
                    config.ALERT_WEBHOOK, 
                    json={'text': message}, 
                    timeout=10
                )
            except Exception as e:
                logger.error(f"Failed to send alert: {str(e)}")

    async def close(self):
        """Close TON connection"""
        if self.client:
            try:
                logger.info("Closing TON client connection")
                await self.client.close()
                logger.info("TON client connection closed")
            except Exception as e:
                logger.error(f"Error closing TON client: {str(e)}")

# Global TON wallet instance
ton_wallet = TONWallet()

async def initialize_ton_wallet():
    """Initialize TON wallet connection"""
    return await ton_wallet.initialize()

async def close_ton_wallet():
    """Close TON wallet connection"""
    return await ton_wallet.close()

def is_valid_ton_address(address: str) -> bool:
    """Validate TON wallet address format"""
    try:
        # Basic validation
        if not address.startswith(('EQ', 'UQ')) or len(address) < 48:
            return False
            
        # Advanced validation
        Address(address)
        return True
    except:
        return False

async def create_staking_contract(user_id: str, amount: float) -> str:
    """Create a staking contract (placeholder implementation)"""
    try:
        logger.info(f"Creating staking contract for user {user_id} with {amount} TON")
        # In a real implementation, this would deploy a smart contract
        return f"EQ_STAKING_{user_id}_{int(time.time())}"
    except Exception as e:
        logger.error(f"Staking contract creation failed: {str(e)}")
        return ""

async def execute_swap(user_id: str, from_token: str, to_token: str, amount: float) -> str:
    """Execute token swap (placeholder implementation)"""
    try:
        logger.info(f"Executing swap for user {user_id}: {amount} {from_token} to {to_token}")
        # In a real implementation, this would interact with a DEX
        return f"tx_{user_id}_{int(time.time())}"
    except Exception as e:
        logger.error(f"Token swap failed: {str(e)}")
        return ""

async def process_ton_withdrawal(user_id: int, amount: float, address: str):
    """Process TON withdrawal (public interface)"""
    return await ton_wallet.process_withdrawal(user_id, amount, address)