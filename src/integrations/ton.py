import os
import re
import time
import logging
import requests
import base64
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Union, Any, Tuple
from mnemonic import Mnemonic
from cryptography.fernet import Fernet
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.database.firebase import db
from src.utils.logger import logger, logging
from config import config

# Core TON libraries
from pytoniq import LiteClient, LiteServerError
from pytoniq_core import Cell, begin_cell, Address
from pytoniq_core.boc import begin_cell, Builder, Slice
from pytonlib import TonlibClient
from tonsdk.utils import bytes_to_b64str, b64str_to_bytes
from tonsdk.contract.wallet import Wallets, WalletVersionEnum

# Configure logger
logger = logging.getLogger(__name__)

class TONWallet:
    # Enhanced constants
    BALANCE_CACHE_MINUTES = 2
    TRANSACTION_TIMEOUT = 90
    MAX_RETRY_ATTEMPTS = 5
    NANOTON_CONVERSION = 1e9
    CONNECTION_TIMEOUT = 15
    DAILY_WITHDRAWAL_LIMIT = 5000
    USER_DAILY_WITHDRAWAL_LIMIT = 500
    GAS_RESERVE = 0.05  # TON reserve for gas
    MAINNET_LITE_SERVERS = config.TON_LITE_SERVERS
    
    def __init__(self) -> None:
        # Enhanced connection state
        self.connection_type = "none"
        self.balance_cache = 0.0
        self.last_balance_check = datetime.min
        self.initialized = False
        self.is_testnet = config.TON_NETWORK.lower() == "testnet"
        self.halted = False
        self.degraded_mode = False
        self.wallet_address = ""
        self.wallet_version = WalletVersionEnum.v4r2
        
        # Connection providers
        self.lite_client = None
        self.tonlib_client = None
        
        # Transaction tracking
        self.pending_transactions = {}
        self.transaction_lock = asyncio.Lock()
        
        # Initialize encryption
        key = get_valid_fernet_key(config.ENCRYPTION_KEY)
        self.cipher = Fernet(key)
        self.cipher = Fernet(config.ENCRYPTION_KEY)

    async def initialize(self) -> bool:
        """Initialize with enhanced fallback and monitoring"""
        if self.halted:
            logger.warning("Skipping initialization: System halted")
            return False
            
        logger.info(f"Initializing TON wallet on {'testnet' if self.is_testnet else 'mainnet'}")
        
        try:
            # Secure credential loading
            await self._init_wallet_credentials()
            
            # Connection strategies with priority
            strategies = [
                ("LiteClient", self._init_liteclient),
                ("Tonlib", self._init_tonlib),
                ("DirectHTTP", self._init_direct_http),
            ]
            
            for name, strategy in strategies:
                try:
                    logger.info(f"Trying {name} connection")
                    if await strategy():
                        logger.info(f"Successfully connected via {name}")
                        self.connection_type = name
                        break
                except Exception as e:
                    logger.error(f"{name} connection failed: {e}")
            
            # Final initialization check
            self.initialized = self.connection_type != "none"
            if not self.initialized:
                logger.critical("All connection methods failed - entering degraded mode")
                self.degraded_mode = True
            
            # Verify wallet address
            await self._verify_wallet_address()
            
            # Initial balance check
            await self.get_balance(force_update=True)
            
            return True
        except Exception as e:
            logger.exception("Wallet initialization failed")
            self.degraded_mode = True
            return False

    async def _init_tonlib(self) -> bool:
        """Initialize using pytonlib for advanced operations"""
        try:
            loop = asyncio.get_running_loop()
            config_data = await self._get_network_config()
            
            self.tonlib_client = TonlibClient(
                ls_index=0,
                config=config_data,
                keystore=f"/tmp/ton_keystore_{os.getpid()}",
                loop=loop
            )
            
            await self.tonlib_client.init()
            logger.info("TonlibClient initialized successfully")
            return True
        except Exception as e:
            logger.error(f"TonlibClient init failed: {e}")
            return False

    async def _get_network_config(self) -> dict:
        """Get network configuration dynamically"""
        config_url = config.TON_CONFIG_URL or (
            "https://ton.org/testnet-global.config.json" 
            if self.is_testnet 
            else "https://ton.org/mainnet-global.config.json"
        )
        
        try:
            response = requests.get(config_url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception:
            # Fallback to embedded config
            return {
                "liteservers": config.TON_LITE_SERVERS,
                "validator": {
                    "init_block": config.TON_INIT_BLOCK
                }
            }
        
    def get_valid_fernet_key(key: str) -> bytes:
        """Ensure we have a valid Fernet key by handling padding issues"""
        # Add proper padding if needed
        if len(key) % 4 != 0:
            key += '=' * (4 - len(key) % 4)
        
        # Try to decode to validate
        try:
            decoded = base64.urlsafe_b64decode(key)
            if len(decoded) != 32:
                raise ValueError("Key must be 32 bytes when decoded")
            return key.encode()
        except Exception as e:
            # Generate a new key if existing one is invalid
            new_key = Fernet.generate_key()
            logger.critical(f"Invalid encryption key: {e}. Generated new key: {new_key.decode()}")
            return new_key

    async def _init_wallet_credentials(self) -> None:
        """Secure credential loading with environment precedence"""
        # Priority 1: Encrypted environment variables
        if os.getenv('TON_ENCRYPTED_MNEMONIC'):
            encrypted_mnemonic = os.getenv('TON_ENCRYPTED_MNEMONIC')
            await self._init_from_encrypted(encrypted_mnemonic)
        # Priority 2: Standard environment variables
        elif os.getenv('TON_MNEMONIC'):
            await self._init_from_mnemonic(os.getenv('TON_MNEMONIC'))
        # Priority 3: Config file
        elif hasattr(config, 'TON_MNEMONIC') and config.TON_MNEMONIC:
            await self._init_from_mnemonic(config.TON_MNEMONIC)
        else:
            raise ValueError("No TON credentials provided")

    async def _init_from_encrypted(self, encrypted_data: str) -> None:
        """Initialize from encrypted credential"""
        try:
            decrypted_data = self.cipher.decrypt(encrypted_data.encode()).decode()
            
            if decrypted_data.startswith("mnemonic:"):
                phrase = decrypted_data.split(":", 1)[1]
                await self._init_from_mnemonic(phrase)
            elif decrypted_data.startswith("privatekey:"):
                key = decrypted_data.split(":", 1)[1]
                await self._init_from_private_key(key)
            else:
                raise ValueError("Invalid encrypted data format")
        except Exception as e:
            logger.error("Encrypted credential decryption failed")
            raise

    async def _init_from_mnemonic(self, phrase: str) -> None:
        """Enhanced mnemonic initialization with tonsdk"""
        try:
            words = phrase.strip().split()
            
            # Validate word count
            if len(words) not in [12, 15, 18, 21, 24]:
                raise ValueError(f"Invalid mnemonic word count: {len(words)}")
            
            # Use tonsdk for wallet creation
            mnemonics = words
            priv_key, pub_key = Wallets.mnemonic_to_private_key(mnemonics)
            self.private_key = priv_key
            self.public_key = pub_key
            
            # Create wallet
            wallet = Wallets.create(self.wallet_version, pub_key, 0)
            self.wallet_address = wallet.address.to_string(True, True, True)
            
            logger.info(f"Initialized {self.wallet_version.name} wallet: {self.wallet_address}")
        except Exception as e:
            logger.error(f"Mnemonic initialization failed: {e}")
            raise

    def _derive_wallet_address(self) -> None:
        """Standardized address derivation"""
        wallet = Wallets.create(self.wallet_version, self.public_key, 0)
        self.wallet_address = wallet.address.to_string(True, True, True)
        logger.info(f"Derived wallet address: {self.wallet_address}")

    # ========== ENHANCED TRANSACTION METHODS ========== #
    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((LiteServerError, asyncio.TimeoutError, ConnectionError))
    )
    async def send_transaction(self, destination: str, amount: float, memo: str = "") -> Dict[str, Any]:
        """Robust transaction sending with retries"""
        async with self.transaction_lock:
            if self.degraded_mode or self.halted:
                return {'status': 'error', 'error': 'System unavailable'}
                
            # Validate destination
            if not self.is_valid_ton_address(destination):
                return {'status': 'error', 'error': 'Invalid address'}
                
            # Convert amount
            amount_nano = int(amount * self.NANOTON_CONVERSION)
            
            # Create transfer message
            body_cell = self._create_message_body(memo)
            
            # Estimate fees
            fees = await self.estimate_fees(destination, amount_nano, body_cell)
            total_amount = amount_nano + fees
            
            # Check balance
            balance_nano = int((await self.get_balance(True)) * self.NANOTON_CONVERSION)
            if balance_nano < total_amount:
                return {'status': 'error', 'error': 'Insufficient balance'}
            
            # Create wallet instance
            wallet = Wallets.create(self.wallet_version, self.public_key, 0)
            
            # Build transfer
            query = wallet.create_transfer_message(
                self.private_key,
                destination,
                amount_nano,
                fees=fees,
                seqno=await self.get_seqno(),
                payload=body_cell
            )
            
            # Send transaction
            try:
                if self.connection_type == "Tonlib":
                    # FIXED: Use Cell instead of Boc
                    cell = Cell.one_from_boc(query["message"].to_boc(False))
                    result = await self.tonlib_client.raw_send_message(cell.to_boc())
                    tx_hash = result["hash"]
                else:
                    # FIXED: Use Cell directly
                    cell = Cell.one_from_boc(query["message"].to_boc(False))
                    await self.lite_client.send_message(cell)
                    tx_hash = "liteclient_" + str(int(time.time())
                )


                # Track transaction
                self.pending_transactions[tx_hash] = {
                    "destination": destination,
                    "amount": amount,
                    "timestamp": datetime.now(),
                    "status": "pending"
                }
                
                return {
                    'status': 'success',
                    'tx_hash': tx_hash,
                    'method': self.connection_type,
                    'fees': fees / self.NANOTON_CONVERSION
                }
            except Exception as e:
                logger.error(f"Transaction failed: {e}")
                return {'status': 'error', 'error': str(e)}

    async def estimate_fees(self, destination: str, amount_nano: int, body: Cell) -> int:
        """Estimate transaction fees"""
        try:
            # Try Tonlib for accurate estimation
            if self.tonlib_client:
                wallet = Wallets.create(self.wallet_version, self.public_key, 0)
                account_state = await self.tonlib_client.raw_get_account_state(wallet.address.to_string())
                source = account_state["raw"]
                
                result = await self.tonlib_client.raw_estimate_fees(
                    source=source,
                    destination=destination,
                    amount=amount_nano,
                    body=b64str_to_bytes(body.to_boc())
                )
                return result["fwd_fee"] + result["gas_fee"]
        except Exception:
            logger.warning("Fee estimation failed, using fallback")
        
        # Fallback flat fee
        return int(0.05 * self.NANOTON_CONVERSION)  # 0.05 TON

    async def get_seqno(self) -> int:
        """Get current wallet seqno"""
        if self.tonlib_client:
            account = await self.tonlib_client.raw_get_account_state(self.wallet_address)
            return account.get("seqno", 0)
        return 0

    def _create_message_body(self, memo: str) -> Cell:
        """Create message payload cell"""
        if not memo:
            return Cell.empty()
            
        return begin_cell()\
            .store_uint(0, 32)\
            .store_string(memo)\
            .end_cell()

    # ========== STAKING INTEGRATION ========== #
    async def stake_ton(self, amount: float) -> Dict[str, Any]:
        """Stake TON to configured contract"""
        if not hasattr(config, 'STAKING_CONTRACT'):
            return {'status': 'error', 'error': 'Staking contract not configured'}
            
        return await self.send_transaction(
            destination=config.STAKING_CONTRACT,
            amount=amount,
            memo="Staking deposit"
        )

    async def withdraw_stake(self, amount: float) -> Dict[str, Any]:
        """Withdraw staked TON"""
        if not hasattr(config, 'STAKING_CONTRACT'):
            return {'status': 'error', 'error': 'Staking contract not configured'}
            
        # This would require contract-specific message
        # Placeholder implementation
        return await self.send_transaction(
            destination=config.STAKING_CONTRACT,
            amount=0.01,  # Gas
            memo="Withdraw stake"
        )

    # ========== SECURITY ENHANCEMENTS ========== #
    def is_valid_ton_address(self, address: str) -> bool:
        """Comprehensive address validation"""
        try:
            # Basic format check
            if not re.match(r"^(?:-1|0):[0-9a-f]{64}$", address):
                return False
                
            # Try parsing
            addr = Address(address)
            
            # Workchain validation
            if addr.is_test_only() and not self.is_testnet:
                return False
                
            return True
        except Exception:
            return False

    async def monitor_transactions(self):
        """Background task to monitor transaction status"""
        while True:
            try:
                await asyncio.sleep(30)
                if not self.initialized or self.degraded_mode:
                    continue
                    
                for tx_hash, tx_info in list(self.pending_transactions.items()):
                    # Skip if older than 1 hour
                    if (datetime.now() - tx_info["timestamp"]).total_seconds() > 3600:
                        self.pending_transactions[tx_hash]["status"] = "timeout"
                        continue
                        
                    # Check confirmation status
                    confirmed = await self.check_transaction_confirmed(tx_hash)
                    if confirmed:
                        self.pending_transactions[tx_hash]["status"] = "confirmed"
            except Exception as e:
                logger.error(f"Transaction monitoring failed: {e}")

    async def check_transaction_confirmed(self, tx_hash: str) -> bool:
        """Check if transaction is confirmed"""
        try:
            if self.tonlib_client:
                result = await self.tonlib_client.raw_get_transactions(
                    self.wallet_address,
                    from_transaction_lt=None,
                    from_transaction_hash=None,
                    limit=10
                )
                for tx in result.get("transactions", []):
                    if tx["transaction_id"]["hash"] == tx_hash:
                        return True
            return False
        except Exception:
            return False

    # ========== PRODUCTION READINESS ========== #
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        status = {
            "initialized": self.initialized,
            "degraded_mode": self.degraded_mode,
            "halted": self.halted,
            "connection_type": self.connection_type,
            "wallet_address": self.wallet_address,
            "balance": await self.get_balance(),
            "pending_transactions": len(self.pending_transactions),
            "last_balance_check": self.last_balance_check.isoformat(),
            "testnet": self.is_testnet
        }
        
        # Detailed connection check
        if self.tonlib_client:
            status["tonlib_ready"] = self.tonlib_client.inited
        if self.lite_client:
            status["lite_client_ready"] = self.lite_client.connected
            
        return status

    async def emergency_halt(self, reason: str = "") -> None:
        """Activate emergency halt with state persistence"""
        self.halted = True
        logger.critical(f"🚨 EMERGENCY HALT: {reason}")
        
        # Attempt to close connections gracefully
        if self.tonlib_client:
            await self.tonlib_client.close()
        if self.lite_client:
            await self.lite_client.close()

# Global TON wallet instance with automatic initialization
ton_wallet = TONWallet()

async def initialize_ton_wallet() -> bool:
    """Initialize and start background tasks"""
    success = await ton_wallet.initialize()
    if success:
        asyncio.create_task(ton_wallet.monitor_transactions())
    return success

async def process_ton_withdrawal(user_id: int, amount: float, address: str) -> Dict[str, Any]:
    """Enhanced withdrawal with security checks"""
    # Sanity check amount
    if amount <= 0 or amount > ton_wallet.USER_DAILY_WITHDRAWAL_LIMIT:
        return {'status': 'error', 'error': 'Invalid amount'}
    
    # Validate address
    if not ton_wallet.is_valid_ton_address(address):
        return {'status': 'error', 'error': 'Invalid TON address'}
    
    # Process with fee consideration
    net_amount = amount - (0.05 if amount > 0.1 else 0)  # 0.05 TON fee
    if net_amount <= 0:
        return {'status': 'error', 'error': 'Amount too small after fees'}
    
    return await ton_wallet.send_transaction(
        destination=address,
        amount=net_amount,
        memo=f"Withdrawal for user {user_id}"
    )

async def stake_user_ton(user_id: int, amount: float) -> Dict[str, Any]:
    """Stake user TON with security checks"""
    if amount <= 0 or amount > ton_wallet.USER_DAILY_WITHDRAWAL_LIMIT:
        return {'status': 'error', 'error': 'Invalid amount'}
    
    return await ton_wallet.stake_ton(amount)