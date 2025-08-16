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
from src.database.firebase import db
from src.utils.logger import logger, logging
from config import config

# Core TON libraries
from pytoniq import LiteClient, LiteServerError
from pytoniq_core import Cell, begin_cell, Address, Boc
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
        # Connection state
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
        
        # Transaction tracking
        self.pending_transactions = {}
        self.transaction_lock = asyncio.Lock()
        
        # Initialize encryption if key is available
        if hasattr(config, 'ENCRYPTION_KEY'):
            self.cipher = Fernet(config.ENCRYPTION_KEY)
        else:
            self.cipher = None

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

    async def _init_liteclient(self) -> bool:
        """Initialize using pytoniq LiteClient"""
        try:
            if self.is_testnet:
                self.lite_client = LiteClient.from_testnet_config(0, timeout=self.CONNECTION_TIMEOUT)
            else:
                self.lite_client = LiteClient.from_mainnet_config(0, timeout=self.CONNECTION_TIMEOUT)
            
            await self.lite_client.connect()
            logger.info("LiteClient initialized successfully")
            return True
        except Exception as e:
            logger.error(f"LiteClient init failed: {e}")
            return False

    async def _init_wallet_credentials(self) -> None:
        """Secure credential loading with environment precedence"""
        # Priority 1: Environment variables
        if os.getenv('TON_MNEMONIC'):
            await self._init_from_mnemonic(os.getenv('TON_MNEMONIC'))
        # Priority 2: Config file
        elif hasattr(config, 'TON_MNEMONIC') and config.TON_MNEMONIC:
            await self._init_from_mnemonic(config.TON_MNEMONIC)
        else:
            raise ValueError("No TON credentials provided")

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

    async def _verify_wallet_address(self) -> None:
        """Verify wallet address matches configuration"""
        if hasattr(config, 'TON_HOT_WALLET') and config.TON_HOT_WALLET:
            config_addr = Address(config.TON_HOT_WALLET).to_string()
            if self.wallet_address != config_addr:
                logger.error(f"CRITICAL: Wallet address mismatch")
                logger.error(f"Derived:   {self.wallet_address}")
                logger.error(f"Configured: {config_addr}")
                raise ValueError("Wallet address mismatch")
            else:
                logger.info("Wallet address verified")

    async def send_transaction(self, destination: str, amount: float, memo: str = "") -> Dict[str, Any]:
        """Robust transaction sending"""
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
            
            # Check balance
            balance_nano = int((await self.get_balance(True)) * self.NANOTON_CONVERSION)
            if balance_nano < amount_nano:
                return {'status': 'error', 'error': 'Insufficient balance'}
            
            # Create wallet instance
            wallet = Wallets.create(self.wallet_version, self.public_key, 0)
            
            # Build transfer
            query = wallet.create_transfer_message(
                self.private_key,
                destination,
                amount_nano,
                seqno=await self.get_seqno(),
                payload=body_cell
            )
            
            # Send transaction
            try:
                await self.lite_client.send_message(Boc.raw_parse(query["message"].to_boc(False)))
                tx_hash = "liteclient_" + str(int(time.time()))
                
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
                    'method': self.connection_type
                }
            except Exception as e:
                logger.error(f"Transaction failed: {e}")
                return {'status': 'error', 'error': str(e)}

    async def get_seqno(self) -> int:
        """Get current wallet seqno"""
        if self.lite_client:
            account = await self.lite_client.get_account_state(Address(self.wallet_address))
            return account.seqno
        return 0

    def _create_message_body(self, memo: str) -> Cell:
        """Create message payload cell"""
        if not memo:
            return Cell.empty()
            
        return begin_cell()\
            .store_uint(0, 32)\
            .store_string(memo)\
            .end_cell()

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

# Global TON wallet instance
ton_wallet = TONWallet()

async def initialize_ton_wallet() -> bool:
    """Initialize TON wallet"""
    return await ton_wallet.initialize()

async def process_ton_withdrawal(user_id: int, amount: float, address: str) -> Dict[str, Any]:
    """Enhanced withdrawal with security checks"""
    # Sanity check amount
    if amount <= 0 or amount > ton_wallet.USER_DAILY_WITHDRAWAL_LIMIT:
        return {'status': 'error', 'error': 'Invalid amount'}
    
    # Validate address
    if not ton_wallet.is_valid_ton_address(address):
        return {'status': 'error', 'error': 'Invalid TON address'}
    
    return await ton_wallet.send_transaction(
        destination=address,
        amount=amount,
        memo=f"Withdrawal for user {user_id}"
    )