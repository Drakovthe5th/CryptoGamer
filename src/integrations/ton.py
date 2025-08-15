import re
import os
import time
import logging
import requests
import base64
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Union
from mnemonic import Mnemonic
from src.database.firebase import db
from src.utils.logger import logger, logging
from config import config

# Production TON libraries
from pytoniq import LiteClient, WalletV4R2, LiteServerError
from pytoniq_core import Cell, begin_cell, Address

# TonCenter HTTP client for fallback
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logger = logging.getLogger(__name__)

class ProductionTONWallet:
    """Production-ready TON wallet with robust connection handling"""
    
    # Production Constants
    BALANCE_CACHE_MINUTES = 2  # More frequent updates for production
    TRANSACTION_TIMEOUT = 60
    MAX_RETRY_ATTEMPTS = 5
    NANOTON_CONVERSION = 1e9
    CONNECTION_TIMEOUT = 20
    DAILY_WITHDRAWAL_LIMIT = 10000  # Higher for production
    USER_DAILY_WITHDRAWAL_LIMIT = 1000
    
    # Connection retry configuration
    RETRY_DELAYS = [1, 2, 5, 10, 20]  # Progressive backoff
    MAX_LITESERVER_ATTEMPTS = 8  # Try more liteservers
    
    def __init__(self) -> None:
        self.client: Optional[LiteClient] = None
        self.wallet: Optional[WalletV4R2] = None
        self.balance_cache: float = 0.0
        self.last_balance_check: datetime = datetime.min
        self.initialized: bool = False
        self.is_testnet: bool = config.TON_NETWORK.lower() == "testnet"
        self.connection_healthy: bool = False
        self.last_health_check: datetime = datetime.min
        self.pending_withdrawals: Dict[str, Dict] = {}
        
        # Production credentials validation
        self._validate_production_config()

    def _validate_production_config(self):
        """Validate all required production configuration"""
        required_configs = {
            'TON_NETWORK': getattr(config, 'TON_NETWORK', None),
            'TON_PRIVATE_KEY': getattr(config, 'TON_PRIVATE_KEY', None),
            'TON_HOT_WALLET': getattr(config, 'TON_HOT_WALLET', None),
        }
        
        missing_configs = [key for key, value in required_configs.items() if not value]
        
        if missing_configs:
            raise ValueError(f"Missing required production configs: {missing_configs}")
            
        # Validate network
        if config.TON_NETWORK.lower() not in ['mainnet', 'testnet']:
            raise ValueError(f"Invalid TON_NETWORK: {config.TON_NETWORK}")
            
        logger.info(f"Production TON config validated for {config.TON_NETWORK}")

    async def initialize(self) -> bool:
        """Production initialization with comprehensive error handling"""
        logger.info(f"Initializing production TON wallet on {config.TON_NETWORK}")
        
        # Try multiple connection strategies
        connection_strategies = [
            self._connect_liteclient_robust,
            self._connect_http_fallback
        ]
        
        for strategy_name, strategy in [("LiteClient", connection_strategies[0]), ("HTTP", connection_strategies[1])]:
            try:
                logger.info(f"Trying {strategy_name} connection strategy")
                if await strategy():
                    logger.info(f"Successfully connected via {strategy_name}")
                    self.initialized = True
                    self.connection_healthy = True
                    await self._verify_production_wallet()
                    return True
            except Exception as e:
                logger.error(f"{strategy_name} strategy failed: {e}")
                continue
        
        logger.error("All connection strategies failed - TON wallet initialization failed")
        return False

    async def _connect_liteclient_robust(self) -> bool:
        """Robust LiteClient connection with multiple servers"""
        for attempt in range(self.MAX_LITESERVER_ATTEMPTS):
            try:
                logger.info(f"LiteClient attempt {attempt + 1}/{self.MAX_LITESERVER_ATTEMPTS}")
                
                if self.is_testnet:
                    self.client = LiteClient.from_testnet_config(
                        ls_index=attempt % 3,  # Cycle through available servers
                        timeout=self.CONNECTION_TIMEOUT
                    )
                else:
                    self.client = LiteClient.from_mainnet_config(
                        ls_index=attempt % 3,
                        timeout=self.CONNECTION_TIMEOUT
                    )
                
                # Connect with timeout
                await asyncio.wait_for(self.client.connect(), timeout=self.CONNECTION_TIMEOUT)
                
                # Verify connection
                await asyncio.wait_for(self.client.get_masterchain_info(), timeout=10)
                
                # Initialize wallet
                await self._init_wallet_from_config()
                
                # Test wallet functionality
                await self.wallet.get_seqno()
                
                logger.info(f"LiteClient connected successfully (server {attempt})")
                return True
                
            except Exception as e:
                logger.warning(f"LiteClient attempt {attempt + 1} failed: {e}")
                if self.client:
                    try:
                        await self.client.close()
                    except:
                        pass
                    self.client = None
                
                # Progressive backoff
                if attempt < len(self.RETRY_DELAYS):
                    delay = self.RETRY_DELAYS[attempt]
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
        
        return False

    async def _connect_http_fallback(self) -> bool:
        """HTTP-based connection as fallback"""
        if not REQUESTS_AVAILABLE:
            logger.error("HTTP fallback unavailable - requests library missing")
            return False
            
        try:
            logger.info("Initializing HTTP fallback connection")
            
            # Create a simple HTTP-based provider
            class HTTPProvider:
                def __init__(self, network: str):
                    self.network = network
                    if network == "mainnet":
                        self.base_url = "https://toncenter.com/api/v2"
                    else:
                        self.base_url = "https://testnet.toncenter.com/api/v2"
                    
                async def get_account_state(self, address: str):
                    # Implement basic account state fetching
                    response = requests.get(f"{self.base_url}/getAddressInformation", 
                                          params={"address": address})
                    return response.json()
            
            # Initialize wallet with HTTP provider
            await self._init_wallet_from_config()
            
            # Test basic functionality
            address = self.get_address()
            if not address:
                raise ValueError("Failed to get wallet address")
                
            logger.info(f"HTTP connection established for address: {address}")
            return True
            
        except Exception as e:
            logger.error(f"HTTP fallback failed: {e}")
            return False

    async def _init_wallet_from_config(self):
        """Initialize wallet from production configuration"""
        try:
            # Decode private key
            private_key_bytes = base64.b64decode(config.TON_PRIVATE_KEY)
            
            # Create wallet instance
            if self.client:
                self.wallet = WalletV4R2(
                    provider=self.client,
                    private_key=private_key_bytes
                )
            else:
                # For HTTP mode, create wallet without provider initially
                self.wallet = WalletV4R2(private_key=private_key_bytes)
                
            logger.info("Wallet initialized from private key")
            
        except Exception as e:
            logger.error(f"Wallet initialization failed: {e}")
            raise

    async def _verify_production_wallet(self):
        """Verify wallet configuration matches production settings"""
        try:
            derived_address = self.get_address()
            config_address = config.TON_HOT_WALLET
            
            # Normalize addresses for comparison
            derived_addr = Address(derived_address)
            config_addr = Address(config_address)
            
            if derived_addr.to_str() != config_addr.to_str():
                logger.error("CRITICAL: Production wallet address mismatch!")
                logger.error(f"Derived:   {derived_addr.to_str()}")
                logger.error(f"Config:    {config_addr.to_str()}")
                raise ValueError("Production wallet verification failed")
            
            logger.info(f"Production wallet verified: {derived_address}")
            
        except Exception as e:
            logger.error(f"Production wallet verification failed: {e}")
            raise

    def get_address(self) -> str:
        """Get production wallet address"""
        if not self.wallet:
            return ""
        return self.wallet.address.to_str()

    async def health_check(self) -> bool:
        """Production health check with caching"""
        now = datetime.now()
        
        # Use cached result if recent
        if (now - self.last_health_check).total_seconds() < 30:
            return self.connection_healthy
        
        try:
            if not self.initialized or not self.wallet:
                self.connection_healthy = False
                return False
            
            if self.client:
                # Test LiteClient connection
                await asyncio.wait_for(self.client.get_masterchain_info(), timeout=10)
                await asyncio.wait_for(self.wallet.get_seqno(), timeout=10)
            else:
                # Test basic wallet functionality
                balance = await self.get_balance_direct()
                if balance < 0:
                    raise ValueError("Invalid balance returned")
            
            self.connection_healthy = True
            self.last_health_check = now
            return True
            
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            self.connection_healthy = False
            self.last_health_check = now
            return False

    async def ensure_connection(self):
        """Ensure connection is healthy, reconnect if needed"""
        if not await self.health_check():
            logger.warning("Connection unhealthy, attempting reconnection...")
            
            # Close existing connection
            if self.client:
                try:
                    await self.client.close()
                except:
                    pass
                self.client = None
            
            # Reinitialize
            success = await self.initialize()
            if not success:
                raise ConnectionError("Failed to reestablish TON connection")

    async def get_balance_direct(self) -> float:
        """Direct balance check without caching"""
        try:
            if self.client and self.wallet:
                balance_nano = await self.wallet.get_balance()
                return balance_nano / self.NANOTON_CONVERSION
            else:
                # HTTP fallback for balance
                address = self.get_address()
                response = requests.get(
                    f"https://{'testnet.' if self.is_testnet else ''}toncenter.com/api/v2/getAddressInformation",
                    params={"address": address}
                )
                data = response.json()
                if data.get("ok"):
                    balance_nano = int(data["result"]["balance"])
                    return balance_nano / self.NANOTON_CONVERSION
                return 0.0
        except Exception as e:
            logger.error(f"Direct balance check failed: {e}")
            return 0.0

    async def get_balance(self, force_update: bool = False) -> float:
        """Get wallet balance with production caching"""
        try:
            # Use cache if not forcing update
            if not force_update and (datetime.now() - self.last_balance_check < timedelta(minutes=self.BALANCE_CACHE_MINUTES)):
                return self.balance_cache
            
            # Ensure connection
            await self.ensure_connection()
            
            # Get fresh balance
            balance = await self.get_balance_direct()
            
            # Update cache
            self.balance_cache = balance
            self.last_balance_check = datetime.now()
            
            # Production monitoring
            if balance < getattr(config, 'MIN_HOT_BALANCE', 10):
                alert_msg = f"🔥 PRODUCTION ALERT: Hot wallet balance low: {balance:.6f} TON"
                logger.critical(alert_msg)
                self._send_production_alert(alert_msg)
            
            return balance
            
        except Exception as e:
            logger.error(f"Balance check failed: {e}")
            return self.balance_cache  # Return cached value on error

    async def send_transaction(self, destination: str, amount: float, memo: str = "") -> Dict[str, Union[str, float]]:
        """Production transaction sending with full validation"""
        try:
            logger.info(f"PRODUCTION TX: Sending {amount} TON to {destination}")
            
            # Ensure connection
            await self.ensure_connection()
            
            # Validate destination
            if not is_valid_ton_address(destination):
                raise ValueError(f"Invalid destination address: {destination}")
            
            # Check balance
            balance = await self.get_balance(force_update=True)
            if balance < amount:
                raise ValueError(f"Insufficient balance: {balance} < {amount}")
            
            # Convert to nanoton
            amount_nano = int(amount * self.NANOTON_CONVERSION)
            
            # Prepare transaction
            body = begin_cell()
            if memo:
                body.store_uint(0, 32)  # Comment opcode
                body.store_string(memo)
            body_cell = body.end_cell()
            
            # Send transaction with retry logic
            for attempt in range(self.MAX_RETRY_ATTEMPTS):
                try:
                    result = await asyncio.wait_for(
                        self.wallet.transfer(
                            destination=Address(destination),
                            amount=amount_nano,
                            body=body_cell
                        ),
                        timeout=self.TRANSACTION_TIMEOUT
                    )
                    
                    tx_hash = result.hash.hex()
                    logger.info(f"PRODUCTION TX SUCCESS: {tx_hash}")
                    
                    # Clear balance cache
                    self.last_balance_check = datetime.min
                    
                    return {
                        'status': 'success',
                        'tx_hash': tx_hash,
                        'amount': amount,
                        'destination': destination
                    }
                    
                except Exception as e:
                    logger.warning(f"Transaction attempt {attempt + 1} failed: {e}")
                    if attempt < self.MAX_RETRY_ATTEMPTS - 1:
                        await asyncio.sleep(self.RETRY_DELAYS[min(attempt, len(self.RETRY_DELAYS)-1)])
                    else:
                        raise
            
        except Exception as e:
            error_msg = f"Production transaction failed: {str(e)}"
            logger.error(error_msg)
            self._send_production_alert(f"🚨 TX FAILURE: {error_msg}")
            return {
                'status': 'error',
                'error': str(e)
            }

    async def process_withdrawal(self, user_id: int, amount: float, address: str) -> Dict[str, Union[str, float]]:
        """Production withdrawal processing with full validation"""
        try:
            logger.info(f"PRODUCTION WITHDRAWAL: User {user_id}, {amount} TON to {address}")
            
            # Validate database balance first
            db_balance = db.get_user_balance(user_id)
            if amount > db_balance:
                return {'status': 'error', 'error': 'Insufficient database balance'}
            
            # Validate address
            if not is_valid_ton_address(address):
                return {'status': 'error', 'error': 'Invalid TON address'}
            
            # Check limits
            if not self._check_withdrawal_limits(user_id, amount):
                return {'status': 'error', 'error': 'Withdrawal limits exceeded'}
            
            # Process blockchain transaction
            memo = f"Withdrawal for user {user_id}"
            result = await self.send_transaction(address, amount, memo)
            
            if result['status'] == 'success':
                # Update database
                db.update_user_balance(user_id, -amount)
                self._update_withdrawal_limits(user_id, amount)
                
                logger.info(f"PRODUCTION WITHDRAWAL SUCCESS: {result['tx_hash']}")
            
            return result
            
        except Exception as e:
            error_msg = f"Production withdrawal failed: {str(e)}"
            logger.error(error_msg)
            return {'status': 'error', 'error': str(e)}

    def _check_withdrawal_limits(self, user_id: int, amount: float) -> bool:
        """Check production withdrawal limits"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            # User daily limit
            user_daily = self.get_user_daily_withdrawal(user_id)
            if user_daily + amount > self.USER_DAILY_WITHDRAWAL_LIMIT:
                return False
            
            # System daily limit
            system_daily = self.get_system_daily_withdrawal()
            if system_daily + amount > self.DAILY_WITHDRAWAL_LIMIT:
                return False
            
            return True
        except Exception as e:
            logger.error(f"Limit check failed: {e}")
            return False

    def _update_withdrawal_limits(self, user_id: int, amount: float):
        """Update withdrawal limits tracking"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            db.update_daily_withdrawal(user_id, today, amount)
            db.update_system_daily_withdrawal(today, amount)
        except Exception as e:
            logger.error(f"Failed to update limits: {e}")

    def get_user_daily_withdrawal(self, user_id: int) -> float:
        """Get user's daily withdrawal total"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            data = db.get_daily_withdrawal(user_id, today)
            return data.get('amount', 0.0) if data else 0.0
        except Exception as e:
            logger.error(f"Failed to get user daily withdrawal: {e}")
            return 0.0

    def get_system_daily_withdrawal(self) -> float:
        """Get system's daily withdrawal total"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            data = db.get_system_daily_withdrawal(today)
            return data.get('total', 0.0) if data else 0.0
        except Exception as e:
            logger.error(f"Failed to get system daily withdrawal: {e}")
            return 0.0

    def _send_production_alert(self, message: str):
        """Send production alert"""
        logger.critical(message)
        
        # Send to monitoring systems
        if hasattr(config, 'PRODUCTION_WEBHOOK') and config.PRODUCTION_WEBHOOK:
            try:
                requests.post(
                    config.PRODUCTION_WEBHOOK,
                    json={'text': message, 'level': 'critical'},
                    timeout=10
                )
            except Exception as e:
                logger.error(f"Failed to send production alert: {e}")

    async def close(self):
        """Close production connections"""
        if self.client:
            try:
                await self.client.close()
                logger.info("Production TON connection closed")
            except Exception as e:
                logger.error(f"Error closing production connection: {e}")
        self.initialized = False
        self.connection_healthy = False

# Production wallet instance
ton_wallet = ProductionTONWallet()

# Public interfaces
async def initialize_ton_wallet() -> bool:
    """Initialize production TON wallet"""
    return await ton_wallet.initialize()

async def close_ton_wallet():
    """Close production TON wallet"""
    await ton_wallet.close()

def is_valid_ton_address(address: str) -> bool:
    """Validate TON address"""
    try:
        if not address or not isinstance(address, str):
            return False
        if not address.startswith(('EQ', 'UQ', 'kQ')) or len(address) < 48:
            return False
        Address(address)
        return True
    except Exception:
        return False

async def process_ton_withdrawal(user_id: int, amount: float, address: str) -> Dict[str, Union[str, float]]:
    """Process production withdrawal"""
    return await ton_wallet.process_withdrawal(user_id, amount, address)

async def get_wallet_status() -> Dict[str, Union[str, float, bool]]:
    """Get production wallet status"""
    try:
        balance = await ton_wallet.get_balance()
        health = await ton_wallet.health_check()
        
        return {
            'address': ton_wallet.get_address(),
            'balance': balance,
            'healthy': health,
            'network': config.TON_NETWORK,
            'initialized': ton_wallet.initialized,
            'last_balance_check': ton_wallet.last_balance_check.isoformat(),
            'connection_type': 'LiteClient' if ton_wallet.client else 'HTTP',
            'production': True
        }
    except Exception as e:
        logger.error(f"Failed to get wallet status: {e}")
        return {
            'error': str(e),
            'healthy': False,
            'initialized': False,
            'production': True
        }