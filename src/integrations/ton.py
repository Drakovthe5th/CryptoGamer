import os
import time
import logging
import requests
import base64
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple, Union
from pytoniq import LiteClient, WalletV4R2
from pytoniq_core import Cell, begin_cell, Address
from mnemonic import Mnemonic
try:
    # Try the correct PyNaCl import
    from nacl.signing import SigningKey
    PYNACL_AVAILABLE = True
except ImportError:
    try:
        # Alternative: use pytoniq's crypto functions
        from pytoniq_core.crypto.keys import private_key_to_public_key
        PYNACL_AVAILABLE = False
    except ImportError:
        # Fallback: use basic crypto
        import hashlib
        PYNACL_AVAILABLE = False
from src.database.firebase import db
from config import config

# Configure logger
logger = logging.getLogger(__name__)

class TONWallet:
    # Constants
    BALANCE_CACHE_MINUTES = 5
    TRANSACTION_TIMEOUT = 120
    MAX_RETRY_ATTEMPTS = 3
    NANOTON_CONVERSION = 1e9
    
    def __init__(self) -> None:
        # Initialize connection parameters
        self.client: Optional[LiteClient] = None
        self.wallet: Optional[WalletV4R2] = None
        self.last_balance_check: datetime = datetime.min
        self.balance_cache: float = 0.0
        self.last_tx_check: datetime = datetime.min
        self.pending_withdrawals: Dict[str, Dict] = {}
        self.initialized: bool = False
        self.connection_retries: int = 0
        self.MAX_RETRIES: int = 3
        self.is_testnet: bool = config.TON_NETWORK.lower() == "testnet"

    async def initialize(self) -> bool:
        """Initialize TON wallet connection"""
        try:
            logger.info(f"Initializing TON wallet on {'testnet' if self.is_testnet else 'mainnet'}")
            
            # Initialize LiteClient
            if self.is_testnet:
                logger.info("Connecting to TON testnet")
                self.client = LiteClient.from_testnet_config(
                    ls_index=0,
                    trust_level=2,
                    timeout=30
                )
            else:
                logger.info("Connecting to TON mainnet")
                self.client = LiteClient.from_mainnet_config(
                    ls_index=0,
                    trust_level=2,
                    timeout=30
                )
            
            # Connect to the network
            await self.client.connect()
            logger.info("Successfully connected to TON network")
            
            # Initialize wallet from mnemonic or private key
            if config.TON_MNEMONIC:
                await self._init_from_mnemonic()
            elif config.TON_PRIVATE_KEY:
                await self._init_from_private_key()
            else:
                raise ValueError("No TON credentials provided (mnemonic or private key)")
            
            # Verify wallet address
            await self._verify_wallet_address()
            
            logger.info(f"TON wallet initialized successfully: {self.get_address()}")
            self.initialized = True
            self.connection_retries = 0
            return True
            
        except Exception as e:
            logger.exception(f"TON wallet initialization failed: {str(e)}")
            self.initialized = False
            self.connection_retries += 1
            
            # Retry logic
            if self.connection_retries < self.MAX_RETRY_ATTEMPTS:
                logger.info(f"Retrying initialization (attempt {self.connection_retries + 1}/{self.MAX_RETRY_ATTEMPTS})")
                await asyncio.sleep(5)  # Wait 5 seconds before retry
                return await self.initialize()
            
            return False

    async def _init_from_mnemonic(self) -> None:
        """Initialize wallet from mnemonic phrase"""
        logger.info("Initializing wallet from mnemonic phrase")
        mnemo = Mnemonic("english")
        
        # Validate mnemonic
        if not mnemo.check(config.TON_MNEMONIC):
            raise ValueError("Invalid mnemonic phrase")
        
        # Generate seed from mnemonic
        seed = mnemo.to_seed(config.TON_MNEMONIC, passphrase="")
        
        # Derive key pair using the best available method
        if PYNACL_AVAILABLE:
            # Use PyNaCl (preferred method)
            signing_key = SigningKey(seed[:32])
            private_key = bytes(signing_key)
            public_key = bytes(signing_key.verify_key)
        else:
            try:
                # Use pytoniq's crypto functions
                private_key = seed[:32]
                public_key = private_key_to_public_key(private_key)
            except:
                # Fallback: use basic derivation (not recommended for production)
                private_key = seed[:32]
                public_key = hashlib.sha256(private_key).digest()
                logger.warning("Using fallback key derivation - install PyNaCl for security")
        
        self.wallet = WalletV4R2(
            provider=self.client,
            public_key=public_key,
            private_key=private_key
        )

    async def _init_from_private_key(self) -> None:
        """Initialize wallet from private key"""
        logger.info("Initializing wallet from private key")
        private_key_bytes = base64.b64decode(config.TON_PRIVATE_KEY)
        
        # If we have 64-byte key, split into private/public
        if len(private_key_bytes) == 64:
            public_key = private_key_bytes[32:]
            private_key = private_key_bytes[:32]
        else:
            # Generate public key from private key using the best available method
            private_key = private_key_bytes
            if PYNACL_AVAILABLE:
                signing_key = SigningKey(private_key)
                public_key = bytes(signing_key.verify_key)
            else:
                try:
                    # Use pytoniq's crypto functions
                    public_key = private_key_to_public_key(private_key)
                except:
                    # Fallback method
                    public_key = hashlib.sha256(private_key).digest()
                    logger.warning("Using fallback key derivation - install PyNaCl for security")
        
        self.wallet = WalletV4R2(
            provider=self.client,
            public_key=public_key,
            private_key=private_key
        )

    async def _verify_wallet_address(self) -> None:
        """Verify wallet address matches configuration"""
        if not self.wallet:
            raise ValueError("Wallet not initialized")
            
        # Get derived address
        derived_address = self.wallet.address.to_str(
            is_user_friendly=True,
            is_url_safe=True,
            is_bounceable=True
        )
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
            raise ValueError("Wallet address mismatch - check your credentials")
        else:
            logger.info("Wallet address verified successfully")

    def get_address(self) -> str:
        """Get wallet address in user-friendly format"""
        if not self.wallet:
            return ""
        return self.wallet.address.to_str(
            is_user_friendly=True, 
            is_url_safe=True, 
            is_bounceable=True
        )

    async def health_check(self) -> bool:
        """Check if TON connection is healthy"""
        try:
            if not self.client or not self.initialized or not self.wallet:
                return False
            
            # Try to get current seqno to test connection
            await self.wallet.get_seqno()
            return True
        except Exception as e:
            logger.warning(f"TON health check failed: {e}")
            return False

    async def ensure_connection(self) -> None:
        """Ensure TON connection is active"""
        if not await self.health_check():
            logger.info("Reconnecting to TON network...")
            await self.initialize()

    async def get_balance(self, force_update: bool = False) -> float:
        """Get current wallet balance in TON"""
        try:
            # Use cache to avoid frequent requests
            if not force_update and (datetime.now() - self.last_balance_check < timedelta(minutes=self.BALANCE_CACHE_MINUTES)):
                logger.debug(f"Returning cached balance: {self.balance_cache}")
                return self.balance_cache
                
            # Ensure connection is healthy
            await self.ensure_connection()
                
            logger.info("Fetching wallet balance from blockchain")
            balance = await self.wallet.get_balance()
            ton_balance = balance / self.NANOTON_CONVERSION  # Convert nanoton to TON
            
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

    async def send_transaction(self, destination: str, amount: float, memo: str = "") -> Dict[str, Union[str, float]]:
        """Send TON transaction to external address"""
        try:
            logger.info(f"Preparing transaction: {amount} TON to {destination}")
            
            # Ensure connection is healthy
            await self.ensure_connection()
                
            # Validate destination address
            if not is_valid_ton_address(destination):
                raise ValueError(f"Invalid TON address: {destination}")
                
            # Convert TON to nanoton
            amount_nano = int(amount * self.NANOTON_CONVERSION)
            
            # Get current seqno for transaction
            seqno = await self.wallet.get_seqno()
            logger.debug(f"Current seqno: {seqno}")
            
            # Prepare message body
            body = begin_cell()
            if memo:
                body.store_uint(0, 32)  # op code for comment
                body.store_string(memo)
            body = body.end_cell()
            
            # Create and send transaction
            logger.info("Creating and sending transfer message")
            result = await self.wallet.transfer(
                destination=Address(destination),
                amount=amount_nano,
                body=body,
                timeout=self.TRANSACTION_TIMEOUT
            )
            
            # Clear balance cache to force update
            self.last_balance_check = datetime.min
            
            logger.info(f"TON transaction sent successfully: {amount:.6f} TON to {destination}")
            logger.info(f"Transaction hash: {result.hash.hex()}")
            
            return {
                'status': 'success',
                'tx_hash': result.hash.hex(),
                'amount': amount,
                'destination': destination,
                'seqno': seqno
            }
            
        except Exception as e:
            logger.error(f"TON transaction failed: {str(e)}")
            
            # Add specific error handling for common TON errors
            error_message = str(e).lower()
            if "insufficient funds" in error_message:
                return {'status': 'error', 'error': 'Insufficient wallet balance'}
            elif "invalid address" in error_message:
                return {'status': 'error', 'error': 'Invalid destination address'}
            elif "timeout" in error_message:
                return {'status': 'error', 'error': 'Transaction timeout - please try again'}
            elif "seqno" in error_message:
                return {'status': 'error', 'error': 'Sequence number error - please retry'}
            else:
                return {'status': 'error', 'error': f'Transaction failed: {str(e)}'}

    async def send_ton(self, to_address: str, amount: float, memo: str = "") -> str:
        """
        Simplified TON send method
        Returns success message or raises exception on failure
        """
        logger.info(f"Sending {amount} TON to {to_address}")
        result = await self.send_transaction(to_address, amount, memo)
        
        if result['status'] == 'success':
            return f"Successfully sent {amount} TON to {to_address}. TX: {result['tx_hash']}"
        else:
            error_msg = f"Failed to send {amount} TON: {result.get('error')}"
            logger.error(error_msg)
            raise Exception(error_msg)

    async def process_withdrawal(self, user_id: int, amount: float, address: str) -> Dict[str, Union[str, float]]:
        """Process TON withdrawal with rate limiting and security checks"""
        try:
            logger.info(f"Processing withdrawal for user {user_id}: {amount} TON to {address}")
            
            # Check database balance FIRST
            db_balance = db.get_user_balance(user_id)
            if amount > db_balance:
                return {
                    'status': 'error',
                    'error': 'Insufficient database balance'
                }
            
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
                error_msg = f"Insufficient wallet funds. Available: {balance:.6f} TON, Required: {amount:.6f} TON"
                logger.warning(error_msg)
                return {
                    'status': 'error',
                    'error': error_msg
                }
                
            # Process transaction
            memo = f"Withdrawal for user {user_id}"
            result = await self.send_transaction(address, amount, memo)
            
            if result['status'] == 'success':
                # Update database balance
                db.update_user_balance(user_id, -amount)
                
                # Update withdrawal limits
                self.update_withdrawal_limits(user_id, amount)
                
                logger.info(f"Withdrawal processed successfully: {amount:.6f} TON to {address}")
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
        """Get user's daily withdrawal amount from database"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            withdrawal_data = db.get_daily_withdrawal(user_id, today)
            return withdrawal_data.get('amount', 0.0) if withdrawal_data else 0.0
        except Exception as e:
            logger.error(f"Failed to get user daily withdrawal: {e}")
            return 0.0

    def get_system_daily_withdrawal(self) -> float:
        """Get system's daily withdrawal total from database"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            system_data = db.get_system_daily_withdrawal(today)
            return system_data.get('total', 0.0) if system_data else 0.0
        except Exception as e:
            logger.error(f"Failed to get system daily withdrawal: {e}")
            return 0.0

    def update_withdrawal_limits(self, user_id: int, amount: float) -> None:
        """Update withdrawal limits in database"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Update user daily withdrawal
            db.update_daily_withdrawal(user_id, today, amount)
            
            # Update system daily withdrawal
            db.update_system_daily_withdrawal(today, amount)
            
            logger.debug(f"Updated withdrawal limits for user {user_id} with amount {amount}")
        except Exception as e:
            logger.error(f"Failed to update withdrawal limits: {e}")

    def send_alert(self, message: str) -> None:
        """Send alert notification"""
        logger.warning(message)
        if hasattr(config, 'ALERT_WEBHOOK') and config.ALERT_WEBHOOK:
            try:
                logger.info(f"Sending alert to webhook: {message}")
                response = requests.post(
                    config.ALERT_WEBHOOK, 
                    json={'text': message}, 
                    timeout=10
                )
                response.raise_for_status()
                logger.info("Alert sent successfully")
            except Exception as e:
                logger.error(f"Failed to send alert: {str(e)}")

    async def get_transaction_history(self, limit: int = 10) -> list:
        """Get recent transaction history"""
        try:
            await self.ensure_connection()
            
            # Get recent transactions
            transactions = await self.wallet.get_transactions(limit=limit)
            
            formatted_txs = []
            for tx in transactions:
                formatted_txs.append({
                    'hash': tx.hash.hex(),
                    'timestamp': tx.now,
                    'value': tx.in_msg.value / self.NANOTON_CONVERSION if tx.in_msg else 0,
                    'type': 'incoming' if tx.in_msg else 'outgoing'
                })
            
            return formatted_txs
        except Exception as e:
            logger.error(f"Failed to get transaction history: {e}")
            return []

    async def close(self) -> None:
        """Close TON connection"""
        if self.client:
            try:
                logger.info("Closing TON client connection")
                await self.client.close()
                self.initialized = False
                logger.info("TON client connection closed")
            except Exception as e:
                logger.error(f"Error closing TON client: {str(e)}")

# Global TON wallet instance
ton_wallet = TONWallet()

async def initialize_ton_wallet() -> bool:
    """Initialize TON wallet connection"""
    return await ton_wallet.initialize()

async def close_ton_wallet() -> None:
    """Close TON wallet connection"""
    await ton_wallet.close()

def is_valid_ton_address(address: str) -> bool:
    """Validate TON wallet address format"""
    try:
        if not address or not isinstance(address, str):
            return False
            
        # Check basic format
        if not (address.startswith(('EQ', 'UQ', 'kQ')) and len(address) >= 48):
            return False
            
        # Try to parse with pytoniq
        parsed_addr = Address(address)
        return parsed_addr.wc in [-1, 0]  # Valid workchains (masterchain and basechain)
        
    except Exception as e:
        logger.debug(f"Address validation failed for {address}: {e}")
        return False

async def create_staking_contract(user_id: str, amount: float) -> str:
    """Create a staking contract (placeholder implementation)"""
    try:
        logger.info(f"Creating staking contract for user {user_id} with {amount} TON")
        
        # Ensure wallet is connected
        await ton_wallet.ensure_connection()
        
        # In a real implementation, this would deploy a smart contract
        # For now, return a placeholder contract address
        contract_address = f"EQ_STAKING_{user_id}_{int(time.time())}"
        
        logger.info(f"Staking contract created: {contract_address}")
        return contract_address
        
    except Exception as e:
        logger.error(f"Staking contract creation failed: {str(e)}")
        return ""

async def execute_swap(user_id: str, from_token: str, to_token: str, amount: float) -> str:
    """Execute token swap (placeholder implementation)"""
    try:
        logger.info(f"Executing swap for user {user_id}: {amount} {from_token} to {to_token}")
        
        # Ensure wallet is connected
        await ton_wallet.ensure_connection()
        
        # In a real implementation, this would interact with a DEX like DeDust or STON.fi
        # For now, return a placeholder transaction hash
        tx_hash = f"tx_{user_id}_{from_token}_{to_token}_{int(time.time())}"
        
        logger.info(f"Swap executed: {tx_hash}")
        return tx_hash
        
    except Exception as e:
        logger.error(f"Token swap failed: {str(e)}")
        return ""

async def process_ton_withdrawal(user_id: int, amount: float, address: str) -> Dict[str, Union[str, float]]:
    """Process TON withdrawal (public interface)"""
    return await ton_wallet.process_withdrawal(user_id, amount, address)

# Utility functions for monitoring
async def get_wallet_status() -> Dict[str, Union[str, float, bool]]:
    """Get comprehensive wallet status"""
    try:
        balance = await ton_wallet.get_balance()
        health = await ton_wallet.health_check()
        
        return {
            'address': ton_wallet.get_address(),
            'balance': balance,
            'healthy': health,
            'network': 'testnet' if ton_wallet.is_testnet else 'mainnet',
            'initialized': ton_wallet.initialized,
            'last_balance_check': ton_wallet.last_balance_check.isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get wallet status: {e}")
        return {
            'error': str(e),
            'healthy': False,
            'initialized': False
        }