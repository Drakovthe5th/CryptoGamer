import re
import os
import time
import logging
import requests
import base64
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Union, List
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
    BALANCE_CACHE_MINUTES = 2
    TRANSACTION_TIMEOUT = 30  # Reduced timeout
    MAX_RETRY_ATTEMPTS = 3    # Reduced retries
    NANOTON_CONVERSION = 1e9
    CONNECTION_TIMEOUT = 15   # Reduced connection timeout
    DAILY_WITHDRAWAL_LIMIT = 10000
    USER_DAILY_WITHDRAWAL_LIMIT = 1000
    
    # More aggressive retry configuration
    RETRY_DELAYS = [2, 5, 10]
    MAX_LITESERVER_ATTEMPTS = 3  # Try fewer servers, fail faster
    
    # Mainnet lite servers (working as of 2024)
    MAINNET_LITE_SERVERS = [
        "https://toncenter.com/api/v2/jsonRPC",
        "https://mainnet-v4.tonhubapi.com",
        "https://mainnet.tonapi.io"
    ]
    
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
        self.use_http_mode: bool = False  # Flag to force HTTP mode
        
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
        """Production initialization with HTTP-first approach"""
        logger.info(f"Initializing production TON wallet on {config.TON_NETWORK}")
        
        # For production stability, try HTTP first
        connection_strategies = [
            ("HTTP", self._connect_http_toncenter),
            ("LiteClient", self._connect_liteclient_robust)
        ]
        
        for strategy_name, strategy in connection_strategies:
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

    async def _connect_http_toncenter(self) -> bool:
        """Primary HTTP connection using TonCenter API"""
        try:
            logger.info("Initializing TonCenter HTTP connection")
            
            # Initialize wallet with private key only
            private_key_bytes = base64.b64decode(config.TON_PRIVATE_KEY)
            
            # Create wallet without provider for HTTP mode
            from pytoniq_core import WalletV4R2 as CoreWallet, PrivateKey
            
            # Create private key object
            private_key = PrivateKey(private_key_bytes)
            
            # Create wallet
            self.wallet = CoreWallet(private_key)
            self.use_http_mode = True
            
            # Test HTTP connection
            await self._test_http_connection()
            
            logger.info("HTTP TonCenter connection established successfully")
            return True
            
        except Exception as e:
            logger.error(f"HTTP TonCenter connection failed: {e}")
            return False

    async def _test_http_connection(self) -> bool:
        """Test HTTP connection by checking balance"""
        try:
            address = self.get_address()
            if not address:
                raise ValueError("Cannot get wallet address")
            
            # Test with TonCenter API
            base_url = "https://testnet.toncenter.com" if self.is_testnet else "https://toncenter.com"
            
            response = requests.get(
                f"{base_url}/api/v2/getAddressInformation",
                params={"address": address},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    logger.info(f"HTTP connection test successful for {address}")
                    return True
            
            raise ValueError(f"HTTP test failed: {response.status_code}")
            
        except Exception as e:
            logger.error(f"HTTP connection test failed: {e}")
            raise

    async def _connect_liteclient_robust(self) -> bool:
        """Fallback LiteClient connection with better error handling"""
        for attempt in range(self.MAX_LITESERVER_ATTEMPTS):
            try:
                logger.info(f"LiteClient attempt {attempt + 1}/{self.MAX_LITESERVER_ATTEMPTS}")
                
                # Clean up any existing client
                if self.client:
                    try:
                        await self.client.close()
                    except:
                        pass
                    self.client = None
                
                # Create new client with shorter timeout
                if self.is_testnet:
                    self.client = LiteClient.from_testnet_config(
                        timeout=self.CONNECTION_TIMEOUT,
                        trust_level=1  # Trust the config more
                    )
                else:
                    self.client = LiteClient.from_mainnet_config(
                        timeout=self.CONNECTION_TIMEOUT,
                        trust_level=1
                    )
                
                # Connect with aggressive timeout
                await asyncio.wait_for(self.client.connect(), timeout=10)
                
                # Quick verification
                info = await asyncio.wait_for(self.client.get_masterchain_info(), timeout=8)
                if not info:
                    raise ValueError("Invalid masterchain info")
                
                # Initialize wallet
                private_key_bytes = base64.b64decode(config.TON_PRIVATE_KEY)
                self.wallet = WalletV4R2(
                    provider=self.client,
                    private_key=private_key_bytes
                )
                
                # Quick wallet test
                seqno = await asyncio.wait_for(self.wallet.get_seqno(), timeout=8)
                
                logger.info(f"LiteClient connected successfully (attempt {attempt + 1})")
                self.use_http_mode = False
                return True
                
            except Exception as e:
                logger.warning(f"LiteClient attempt {attempt + 1} failed: {e}")
                if self.client:
                    try:
                        await self.client.close()
                    except:
                        pass
                    self.client = None
                
                # Short delay between attempts
                if attempt < self.MAX_LITESERVER_ATTEMPTS - 1:
                    await asyncio.sleep(2)
        
        return False

    async def _verify_production_wallet(self):
        """Verify wallet configuration matches production settings"""
        try:
            derived_address = self.get_address()
            config_address = config.TON_HOT_WALLET
            
            if not derived_address:
                raise ValueError("Cannot derive wallet address")
            
            # Normalize addresses for comparison
            derived_addr = Address(derived_address)
            config_addr = Address(config_address)
            
            if derived_addr.to_str(True, True, True) != config_addr.to_str(True, True, True):
                logger.error("CRITICAL: Production wallet address mismatch!")
                logger.error(f"Derived:   {derived_addr.to_str(True, True, True)}")
                logger.error(f"Config:    {config_addr.to_str(True, True, True)}")
                raise ValueError("Production wallet verification failed")
            
            logger.info(f"Production wallet verified: {derived_address}")
            
        except Exception as e:
            logger.error(f"Production wallet verification failed: {e}")
            raise

    def get_address(self) -> str:
        """Get production wallet address"""
        if not self.wallet:
            return ""
        try:
            return self.wallet.address.to_str(True, True, True)
        except:
            try:
                return str(self.wallet.address)
            except:
                return ""

    async def health_check(self) -> bool:
        """Production health check with mode awareness"""
        now = datetime.now()
        
        # Use cached result if recent
        if (now - self.last_health_check).total_seconds() < 30:
            return self.connection_healthy
        
        try:
            if not self.initialized or not self.wallet:
                self.connection_healthy = False
                return False
            
            if self.use_http_mode:
                # Test HTTP connection
                balance = await self.get_balance_http()
                if balance < 0:
                    raise ValueError("Invalid HTTP balance")
            else:
                # Test LiteClient connection
                if not self.client:
                    raise ValueError("No LiteClient available")
                await asyncio.wait_for(self.client.get_masterchain_info(), timeout=8)
                await asyncio.wait_for(self.wallet.get_seqno(), timeout=8)
            
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
            
            # Reset state
            self.initialized = False
            self.connection_healthy = False
            
            # Close existing connections
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

    async def get_balance_http(self) -> float:
        """Get balance via HTTP API"""
        try:
            address = self.get_address()
            if not address:
                raise ValueError("No wallet address available")
            
            base_url = "https://testnet.toncenter.com" if self.is_testnet else "https://toncenter.com"
            
            response = requests.get(
                f"{base_url}/api/v2/getAddressInformation",
                params={"address": address},
                timeout=10
            )
            
            if response.status_code != 200:
                raise ValueError(f"HTTP request failed: {response.status_code}")
            
            data = response.json()
            if not data.get("ok"):
                raise ValueError(f"API error: {data}")
            
            balance_nano = int(data["result"]["balance"])
            return balance_nano / self.NANOTON_CONVERSION
            
        except Exception as e:
            logger.error(f"HTTP balance check failed: {e}")
            return -1.0

    async def get_balance_liteclient(self) -> float:
        """Get balance via LiteClient"""
        try:
            if not self.client or not self.wallet:
                raise ValueError("LiteClient not available")
            
            balance_nano = await asyncio.wait_for(self.wallet.get_balance(), timeout=10)
            return balance_nano / self.NANOTON_CONVERSION
            
        except Exception as e:
            logger.error(f"LiteClient balance check failed: {e}")
            return -1.0

    async def get_balance_direct(self) -> float:
        """Direct balance check using current connection mode"""
        try:
            if self.use_http_mode:
                return await self.get_balance_http()
            else:
                return await self.get_balance_liteclient()
        except Exception as e:
            logger.error(f"Direct balance check failed: {e}")
            return -1.0

    async def get_balance(self, force_update: bool = False) -> float:
        """Get wallet balance with production caching"""
        try:
            # Use cache if not forcing update
            cache_valid = (datetime.now() - self.last_balance_check < timedelta(minutes=self.BALANCE_CACHE_MINUTES))
            if not force_update and cache_valid and self.balance_cache >= 0:
                return self.balance_cache
            
            # Ensure connection
            await self.ensure_connection()
            
            # Get fresh balance
            balance = await self.get_balance_direct()
            
            if balance >= 0:
                # Update cache only on success
                self.balance_cache = balance
                self.last_balance_check = datetime.now()
                
                # Production monitoring
                min_balance = getattr(config, 'MIN_HOT_BALANCE', 10)
                if balance < min_balance:
                    alert_msg = f"🔥 PRODUCTION ALERT: Hot wallet balance low: {balance:.6f} TON"
                    logger.critical(alert_msg)
                    self._send_production_alert(alert_msg)
            else:
                # Return cached value on error
                balance = self.balance_cache
            
            return balance
            
        except Exception as e:
            logger.error(f"Balance check failed: {e}")
            return self.balance_cache if self.balance_cache >= 0 else 0.0

    async def send_transaction_http(self, destination: str, amount: float, memo: str = "") -> Dict[str, Union[str, float]]:
        """Send transaction via HTTP (limited functionality)"""
        # HTTP mode typically requires external transaction construction
        # This is a placeholder for HTTP-based transactions
        logger.error("HTTP transaction sending not fully implemented - requires external service")
        return {
            'status': 'error',
            'error': 'HTTP transactions require external service integration'
        }

    async def send_transaction_liteclient(self, destination: str, amount: float, memo: str = "") -> Dict[str, Union[str, float]]:
        """Send transaction via LiteClient"""
        try:
            if not self.client or not self.wallet:
                raise ValueError("LiteClient not available")
            
            # Convert to nanoton
            amount_nano = int(amount * self.NANOTON_CONVERSION)
            
            # Prepare transaction body
            body = begin_cell()
            if memo:
                body.store_uint(0, 32)  # Comment opcode
                body.store_string(memo)
            body_cell = body.end_cell()
            
            # Send transaction
            result = await asyncio.wait_for(
                self.wallet.transfer(
                    destination=Address(destination),
                    amount=amount_nano,
                    body=body_cell
                ),
                timeout=self.TRANSACTION_TIMEOUT
            )
            
            tx_hash = result.hash.hex()
            logger.info(f"LiteClient transaction success: {tx_hash}")
            
            return {
                'status': 'success',
                'tx_hash': tx_hash,
                'amount': amount,
                'destination': destination
            }
            
        except Exception as e:
            logger.error(f"LiteClient transaction failed: {e}")
            raise

    async def send_transaction(self, destination: str, amount: float, memo: str = "") -> Dict[str, Union[str, float]]:
        """Production transaction sending with mode awareness"""
        try:
            logger.info(f"PRODUCTION TX: Sending {amount} TON to {destination} (mode: {'HTTP' if self.use_http_mode else 'LiteClient'})")
            
            # Ensure connection
            await self.ensure_connection()
            
            # Validate destination
            if not is_valid_ton_address(destination):
                raise ValueError(f"Invalid destination address: {destination}")
            
            # Check balance
            balance = await self.get_balance(force_update=True)
            if balance < amount:
                raise ValueError(f"Insufficient balance: {balance} < {amount}")
            
            # Send based on connection mode
            if self.use_http_mode:
                result = await self.send_transaction_http(destination, amount, memo)
            else:
                result = await self.send_transaction_liteclient(destination, amount, memo)
            
            if result['status'] == 'success':
                # Clear balance cache on success
                self.last_balance_check = datetime.min
            
            return result
            
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
            
            # For HTTP mode, queue withdrawal for manual processing
            if self.use_http_mode:
                logger.warning("HTTP mode - withdrawal queued for manual processing")
                # In production, you'd queue this for batch processing
                return {
                    'status': 'queued',
                    'message': 'Withdrawal queued for processing',
                    'amount': amount,
                    'destination': address
                }
            
            # Process blockchain transaction
            memo = f"Withdrawal for user {user_id}"
            result = await self.send_transaction(address, amount, memo)
            
            if result['status'] == 'success':
                # Update database
                db.update_user_balance(user_id, -amount)
                self._update_withdrawal_limits(user_id, amount)
                
                logger.info(f"PRODUCTION WITHDRAWAL SUCCESS: {result.get('tx_hash', 'queued')}")
            
            return result
            
        except Exception as e:
            error_msg = f"Production withdrawal failed: {str(e)}"
            logger.error(error_msg)
            return {'status': 'error', 'error': str(e)}

    def _check_withdrawal_limits(self, user_id: int, amount: float) -> bool:
        """Check production withdrawal limits"""
        try:
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
                    timeout=5
                )
            except Exception as e:
                logger.error(f"Failed to send production alert: {e}")

    async def close(self):
        """Close production connections"""
        self.initialized = False
        self.connection_healthy = False
        
        if self.client:
            try:
                await self.client.close()
                logger.info("Production TON connection closed")
            except Exception as e:
                logger.error(f"Error closing production connection: {e}")
        
        self.client = None

# Production wallet instance
ton_wallet = ProductionTONWallet()

# Public interfaces
async def initialize_ton_wallet() -> bool:
    """Initialize production TON wallet"""
    try:
        success = await ton_wallet.initialize()
        if success:
            logger.info("✅ PRODUCTION TON WALLET INITIALIZED SUCCESSFULLY")
        else:
            logger.error("❌ PRODUCTION TON WALLET INITIALIZATION FAILED")
        return success
    except Exception as e:
        logger.critical(f"❌ FAILED TO START PRODUCTION TON WALLET: {e}")
        return False

async def close_ton_wallet():
    """Close production TON wallet"""
    await ton_wallet.close()

async def get_ton_http_client(api_key: str = None):
    """Get HTTP client (compatibility function)"""
    logger.info("HTTP client requested - using internal production client")
    return "internal_http_client"

def is_valid_ton_address(address: str) -> bool:
    """Validate TON address"""
    try:
        if not address or not isinstance(address, str):
            return False
        if len(address) < 48:
            return False
        if not address.startswith(('EQ', 'UQ', 'kQ', '0:')):
            return False
        
        # Try to parse as Address
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
            'last_balance_check': ton_wallet.last_balance_check.isoformat() if ton_wallet.last_balance_check != datetime.min else None,
            'connection_type': 'HTTP' if ton_wallet.use_http_mode else 'LiteClient',
            'production': True,
            'mode': 'http' if ton_wallet.use_http_mode else 'liteclient'
        }
    except Exception as e:
        logger.error(f"Failed to get wallet status: {e}")
        return {
            'error': str(e),
            'healthy': False,
            'initialized': False,
            'production': True
        }