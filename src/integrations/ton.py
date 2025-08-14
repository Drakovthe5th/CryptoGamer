import os
import time
import logging
import requests
import base64
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Union, Tuple
from mnemonic import Mnemonic
from src.database.firebase import db
from config import config

# Production TON libraries
from pytoniq import LiteClient, WalletV4R2, Contract, LiteServerError
from pytoniq.toncenter import TonCenterClient
from pytoniq_core import Cell, begin_cell, Address, Slice, Builder, Boc
from pytoniq_core.tlb import MsgAddress

# Configure logger
logger = logging.getLogger(__name__)

# Production contract addresses (mainnet)
STONFI_ROUTER_ADDRESS = "EQvFSDqX7H2rYgGzF16h4sHv2WCRmm1QcTZzY5vEOhB8V-xn"
DEDUST_ROUTER_ADDRESS = "EQBfBWT7X2BHg9tXAxzhz1aHhuGbrLmB6EnO3IRZkcL75q7n"

# Supported tokens with contract addresses
SUPPORTED_TOKENS = {
    "TON": "ton",
    "jUSDT": "EQDJ3vLO3e2uA0-VtJg7_XzD6vGmJ0dMe1qPz_4eJ4UPA5mI",
    "jETH": "EQDo5J4HJx_1jJD8nAGViqJ3JjKZ2dOqMLa6cNQzY0w3_2cK",
    "jBTC": "EQD9hZk9iP2gQrGk2Wx4YkQdXkZqG9w0V2RlZv8S5Qm8vC5j",
    "STON": "EQA5V9tBNTe8rhGvZ90mOPdB1xqVYU0qUDDQU5sXQ7-8r-0t"
}

class TONWallet:
    # Constants
    BALANCE_CACHE_MINUTES = 5
    TRANSACTION_TIMEOUT = 120
    MAX_RETRY_ATTEMPTS = 3
    NANOTON_CONVERSION = 1e9
    CONNECTION_TIMEOUT = 15  # seconds
    DAILY_WITHDRAWAL_LIMIT = 1000  # TON per day
    USER_DAILY_WITHDRAWAL_LIMIT = 100  # TON per user per day
    
    def __init__(self) -> None:
        # Initialize connection parameters
        self.client: Optional[LiteClient] = None
        self.http_client: Optional[TonCenterClient] = None
        self.wallet: Optional[WalletV4R2] = None
        self.balance_cache: float = 0.0
        self.last_balance_check: datetime = datetime.min
        self.initialized: bool = False
        self.is_testnet: bool = config.TON_NETWORK.lower() == "testnet"
        self.use_http_fallback: bool = False
        self.liteserver_indices = [0, 1, 2]  # Multiple liteservers to try
        self.pending_withdrawals: Dict[str, Dict] = {}
        self.halted: bool = False  # Emergency halt flag

    async def initialize(self) -> bool:
        """Initialize TON wallet connection with multiple fallback options"""
        if self.halted:
            logger.warning("Skipping initialization: System is halted")
            return False
            
        logger.info(f"Initializing TON wallet on {'testnet' if self.is_testnet else 'mainnet'}")
        
        # First try LiteClient with multiple servers
        if await self._try_liteclient_connection():
            logger.info("Successfully connected via LiteClient")
            self.use_http_fallback = False
            self.initialized = True
            return True
        
        # Then try HTTP client (TonCenter) as fallback
        if await self._try_http_connection():
            logger.info("Successfully connected via HTTP client")
            self.use_http_fallback = True
            self.initialized = True
            return True
        
        logger.error("All connection methods failed")
        return False

    async def _try_liteclient_connection(self) -> bool:
        """Try connecting to LiteClient with multiple servers"""
        for ls_index in self.liteserver_indices:
            try:
                logger.info(f"Trying LiteClient connection (index: {ls_index})")
                
                if self.is_testnet:
                    self.client = LiteClient.from_testnet_config(ls_index, timeout=self.CONNECTION_TIMEOUT)
                else:
                    self.client = LiteClient.from_mainnet_config(ls_index, timeout=self.CONNECTION_TIMEOUT)
                
                await self.client.connect()
                
                # Initialize wallet credentials
                if not await self._init_wallet_credentials():
                    return False
                
                # Verify wallet address
                await self._verify_wallet_address()
                
                return True
                
            except (asyncio.TimeoutError, ConnectionError) as e:
                logger.warning(f"LiteClient connection failed (index {ls_index}): {e}")
            except Exception as e:
                logger.error(f"Unexpected LiteClient error: {e}")
        
        return False

    async def _try_http_connection(self) -> bool:
        """Try connecting via HTTP (TonCenter)"""
        try:
            logger.info("Trying HTTP client connection")
            
            # Use testnet or mainnet endpoint
            if self.is_testnet:
                self.http_client = TonCenterClient(base_url='https://testnet.toncenter.com/api/v2/', timeout=self.CONNECTION_TIMEOUT)
            else:
                self.http_client = TonCenterClient(base_url='https://toncenter.com/api/v2/', timeout=self.CONNECTION_TIMEOUT)
            
            # Add API key if configured
            if hasattr(config, 'TONCENTER_API_KEY') and config.TONCENTER_API_KEY:
                self.http_client.api_key = config.TONCENTER_API_KEY
            
            # Initialize wallet credentials
            if not await self._init_wallet_credentials():
                return False
                
            # Verify wallet address
            await self._verify_wallet_address()
            
            return True
            
        except Exception as e:
            logger.error(f"HTTP client connection failed: {e}")
            return False

    async def _init_wallet_credentials(self) -> bool:
        """Initialize wallet credentials"""
        try:
            if hasattr(config, 'TON_MNEMONIC') and config.TON_MNEMONIC:
                await self._init_from_mnemonic()
            elif hasattr(config, 'TON_PRIVATE_KEY') and config.TON_PRIVATE_KEY:
                await self._init_from_private_key()
            else:
                raise ValueError("No TON credentials provided")
            return True
        except Exception as e:
            logger.error(f"Wallet credential initialization failed: {e}")
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
        private_key = seed[:32]
        
        # Initialize wallet
        if self.client:
            self.wallet = WalletV4R2(
                provider=self.client,
                private_key=private_key
            )
        elif self.http_client:
            self.wallet = WalletV4R2(
                provider=self.http_client,
                private_key=private_key
            )

    async def _init_from_private_key(self) -> None:
        """Initialize wallet from private key"""
        logger.info("Initializing wallet from private key")
        private_key = base64.b64decode(config.TON_PRIVATE_KEY)
        
        # Initialize wallet
        if self.client:
            self.wallet = WalletV4R2(
                provider=self.client,
                private_key=private_key
            )
        elif self.http_client:
            self.wallet = WalletV4R2(
                provider=self.http_client,
                private_key=private_key
            )

    async def _verify_wallet_address(self) -> None:
        """Verify wallet address matches configuration"""
        if not self.wallet:
            raise ValueError("Wallet not initialized")
            
        # Get derived address
        derived_address = self.wallet.address.to_str()
        logger.info(f"Derived wallet address: {derived_address}")
        
        # Verify against configured address if available
        if hasattr(config, 'TON_HOT_WALLET') and config.TON_HOT_WALLET:
            config_address = Address(config.TON_HOT_WALLET).to_str()
            
            if derived_address != config_address:
                logger.error(f"CRITICAL: Wallet address mismatch")
                logger.error(f"Derived:   {derived_address}")
                logger.error(f"Configured: {config_address}")
                raise ValueError("Wallet address mismatch - check your credentials")
            else:
                logger.info("Wallet address verified successfully")
        else:
            logger.warning("No TON_HOT_WALLET configured - skipping address verification")

    def get_address(self) -> str:
        """Get wallet address in user-friendly format"""
        if not self.wallet:
            return ""
        return self.wallet.address.to_str()

    async def health_check(self) -> bool:
        """Check if TON connection is healthy"""
        if self.halted:
            logger.warning("Health check failed: System is halted")
            return False
            
        try:
            if not self.initialized or not self.wallet:
                return False
            
            # Different checks based on connection type
            if self.client and not self.use_http_fallback:
                await self.wallet.get_seqno()
                return True
            elif self.http_client:
                # Simple balance check for HTTP client
                balance = await self.wallet.get_balance()
                return balance >= 0
            return False
        except Exception as e:
            logger.warning(f"TON health check failed: {e}")
            return False

    async def ensure_connection(self) -> None:
        """Ensure TON connection is active"""
        if self.halted:
            logger.warning("Skipping connection check: System is halted")
            return
            
        if not await self.health_check():
            logger.warning("TON connection lost, reinitializing...")
            await self.initialize()

    async def get_balance(self, force_update: bool = False) -> float:
        """Get current wallet balance in TON"""
        if self.halted:
            logger.warning("System halted - balance check skipped")
            return 0.0
            
        try:
            # Use cache to avoid frequent requests
            if not force_update and (datetime.now() - self.last_balance_check < timedelta(minutes=self.BALANCE_CACHE_MINUTES)):
                return self.balance_cache
                
            # Ensure connection is healthy
            await self.ensure_connection()
                
            logger.info("Fetching wallet balance")
            balance = await self.wallet.get_balance()
            ton_balance = balance / self.NANOTON_CONVERSION
            
            self.balance_cache = ton_balance
            self.last_balance_check = datetime.now()
            logger.info(f"Wallet balance: {ton_balance:.6f} TON")
            
            # Alert if balance is low
            if hasattr(config, 'MIN_HOT_BALANCE') and ton_balance < config.MIN_HOT_BALANCE:
                alert_msg = f"🔥 TON HOT WALLET LOW BALANCE: {ton_balance:.6f} TON"
                logger.warning(alert_msg)
                self.send_alert(alert_msg)
            
            return ton_balance
        except Exception as e:
            logger.error(f"Failed to get TON balance: {e}")
            return 0.0

    async def send_transaction(self, destination: str, amount: float, memo: str = "", body: Optional[Cell] = None) -> Dict[str, Union[str, float]]:
        """Send TON transaction with fallback mechanism"""
        if self.halted:
            return {'status': 'error', 'error': 'System temporarily suspended'}
            
        try:
            logger.info(f"Sending {amount} TON to {destination}")
            
            # Ensure connection is healthy
            await self.ensure_connection()
                
            # Validate destination address
            if not is_valid_ton_address(destination):
                raise ValueError(f"Invalid TON address: {destination}")
                
            # Convert TON to nanoton
            amount_nano = int(amount * self.NANOTON_CONVERSION)
            
            # Prepare message body
            if not body:
                body_cell = begin_cell()
                if memo:
                    body_cell.store_uint(0, 32)  # op code for comment
                    body_cell.store_string(memo)
                body = body_cell.end_cell()
            
            # Create and send transaction
            result = await self.wallet.transfer(
                destination=Address(destination),
                amount=amount_nano,
                body=body,
                timeout=self.TRANSACTION_TIMEOUT
            )
            
            # Clear balance cache
            self.last_balance_check = datetime.min
            
            logger.info(f"TON transaction sent successfully: {result.hash.hex()}")
            
            return {
                'status': 'success',
                'tx_hash': result.hash.hex(),
                'amount': amount,
                'destination': destination
            }
            
        except Exception as e:
            # Try HTTP fallback if LiteClient failed
            if not self.use_http_fallback and self.http_client:
                logger.warning("Retrying with HTTP client...")
                self.wallet = WalletV4R2(
                    provider=self.http_client,
                    private_key=self.wallet.private_key
                )
                self.use_http_fallback = True
                return await self.send_transaction(destination, amount, memo, body)
                
            error_message = str(e).lower()
            if "insufficient funds" in error_message:
                return {'status': 'error', 'error': 'Insufficient wallet balance'}
            elif "invalid address" in error_message:
                return {'status': 'error', 'error': 'Invalid destination address'}
            elif "seqno" in error_message:
                return {'status': 'error', 'error': 'Sequence number mismatch - please retry'}
            elif "timeout" in error_message:
                return {'status': 'error', 'error': 'Transaction timed out - please check later'}
            else:
                return {'status': 'error', 'error': f'Transaction failed: {str(e)}'}

    async def send_ton(self, to_address: str, amount: float, memo: str = "") -> str:
        """
        Simplified TON send method
        Returns success message or raises exception on failure
        """
        if self.halted:
            raise Exception("System temporarily suspended")
            
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
        if self.halted:
            return {'status': 'error', 'error': 'System temporarily suspended'}
            
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
            if user_daily + amount > self.USER_DAILY_WITHDRAWAL_LIMIT:
                error_msg = f"Daily withdrawal limit exceeded: {self.USER_DAILY_WITHDRAWAL_LIMIT} TON"
                logger.warning(error_msg)
                return {
                    'status': 'error',
                    'error': error_msg
                }
                
            # Check system daily limit
            system_daily = self.get_system_daily_withdrawal()
            if system_daily + amount > self.DAILY_WITHDRAWAL_LIMIT:
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
        if self.halted:
            return [{'error': 'System temporarily suspended'}]
            
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
        """Close TON connections"""
        if self.client:
            try:
                logger.info("Closing LiteClient connection")
                await self.client.close()
            except Exception as e:
                logger.error(f"Error closing LiteClient: {e}")
        if self.http_client:
            try:
                logger.info("Closing HTTP client connection")
                await self.http_client.close()
            except Exception as e:
                logger.error(f"Error closing HTTP client: {e}")
        self.initialized = False

    # ---------- Simplified Staking Implementation ----------
        async def deploy_staking_contract(self, min_stake: float, reward_rate: int) -> str:
            """Deploy a new staking contract to the blockchain"""
        if self.halted:
            return ""
            
        try:
            logger.info(f"Deploying staking contract with min stake: {min_stake} TON, reward rate: {reward_rate}%")
            await self.ensure_connection()
            
            # Load staking contract code
            code_cell = await self._load_staking_contract_code()
            if not code_cell:
                raise RuntimeError("Failed to load staking contract code")
            
            # Use wallet address as owner
            owner_address = self.get_address()
            
            # Prepare initial data
            data = begin_cell()\
                .store_address(Address(owner_address))\
                .store_coins(int(min_stake * self.NANOTON_CONVERSION))\
                .store_uint(reward_rate, 8)\
                .store_dict(None).end_cell()
                
            # Prepare state init
            state_init = begin_cell()\
                .store_bit(0)\
                .store_bit(0)\
                .store_bit(1)\
                .store_ref(code_cell)\
                .store_ref(data)\
                .end_cell()
            
            # Calculate contract address
            contract_address = Contract.derive_address(workchain=0, code=code_cell, data=data)
            
            # Deploy contract
            deploy_msg = begin_cell()\
                .store_uint(0x10, 6)\
                .store_address(contract_address)\
                .store_coins(int(0.1 * self.NANOTON_CONVERSION))\
                .store_uint(0, 1 + 4 + 4 + 64 + 32 + 1 + 1)\
                .store_ref(state_init)\
                .end_cell()
            
            # Send deploy transaction
            result = await self.wallet.transfer(
                destination=contract_address,
                amount=0.1 * self.NANOTON_CONVERSION,  # 0.1 TON for initial balance
                body=Cell.empty(),
                state_init=state_init
            )
            
            logger.info(f"Staking contract deployed at: {contract_address.to_str()}")
            return contract_address.to_str()
            
        except Exception as e:
            logger.error(f"Staking contract deployment failed: {str(e)}")
            return ""

    async def _load_staking_contract_code(self) -> Optional[Cell]:
        """Load staking contract code from file or network"""
        try:
            # Try to load from file
            try:
                with open('src/contracts/staking_contract.code.boc', 'rb') as f:
                    return Boc.deserialize(f.read()).roots[0]
            except:
                logger.warning("Local staking contract code not found, fetching from network")
                
            # Fetch from network (mainnet staking contract)
            if self.is_testnet:
                raise RuntimeError("Staking contract not available on testnet")
                
            # Get code from known staking contract
            contract_address = Address("EQDvRFURH5Y3oIqH3n5C3ZfV7Q2LtD7ZJwY1J6X7Z8k9C3d")
            state = await self.client.get_account_state(contract_address)
            return state.code
        except Exception as e:
            logger.error(f"Failed to load staking contract code: {str(e)}")
            return None

    async def stake_tokens(self, user_id: str, amount: float, contract_address: str) -> str:
        """Stake TON tokens in a staking contract"""
        if self.halted:
            return ""
            
        try:
            logger.info(f"Staking {amount} TON for user {user_id} in contract {contract_address}")
            await self.ensure_connection()
            
            # Validate contract address
            if not is_valid_ton_address(contract_address):
                raise ValueError("Invalid staking contract address")
                
            # Build stake message
            body = begin_cell()\
                .store_uint(0x4f4f4f, 32)\
                .store_uint(0, 64)\
                .end_cell()
            
            # Send transaction to staking contract
            result = await self.send_transaction(
                destination=contract_address,
                amount=amount,
                memo="",
                body=body
            )
            
            if result['status'] == 'success':
                # Update database
                db.create_stake(user_id, amount, contract_address)
                return result['tx_hash']
            else:
                raise Exception(f"Staking failed: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Staking operation failed: {str(e)}")
            return ""

    # ---------- Production Swap Implementation ----------
    async def execute_swap(self, user_id: str, from_token: str, to_token: str, amount: float, slippage: float = 0.01) -> str:
        """Execute token swap on STON.fi or DeDust with slippage protection"""
        if self.halted:
            return ""
            
        try:
            logger.info(f"Executing swap for user {user_id}: {amount} {from_token} to {to_token}")
            await self.ensure_connection()
            
            # Validate tokens
            if from_token not in SUPPORTED_TOKENS or to_token not in SUPPORTED_TOKENS:
                raise ValueError(f"Unsupported token pair: {from_token}/{to_token}")
                
            # Get token addresses
            from_token_addr = SUPPORTED_TOKENS[from_token]
            to_token_addr = SUPPORTED_TOKENS[to_token]
            
            # Choose DEX (STON.fi for TON pairs, DeDust for others)
            use_stonfi = (from_token == "TON" or to_token == "TON")
            dex_name = "STON.fi" if use_stonfi else "DeDust"
            router_address = STONFI_ROUTER_ADDRESS if use_stonfi else DEDUST_ROUTER_ADDRESS
            
            # Prepare swap parameters
            min_out = 0  # Will be set after price calculation
            deadline = int(time.time()) + 1800  # 30 minutes deadline
            
            # Get price quote
            quoted_amount = await self._get_swap_quote(
                from_token_addr, 
                to_token_addr, 
                amount, 
                dex_name.lower()
            )
            
            if quoted_amount <= 0:
                raise RuntimeError("Invalid swap quote received")
            
            # Apply slippage tolerance
            min_out = int(quoted_amount * (1 - slippage))
            
            # Build swap body
            if use_stonfi:
                body = self._build_stonfi_swap_body(
                    from_token_addr, 
                    to_token_addr, 
                    amount, 
                    min_out, 
                    deadline
                )
            else:
                body = self._build_dedust_swap_body(
                    from_token_addr, 
                    to_token_addr, 
                    amount, 
                    min_out, 
                    deadline
                )
            
            # Send swap transaction
            tx_amount = amount if from_token == "TON" else 0.05  # 0.05 TON for gas
            result = await self.send_transaction(
                destination=router_address,
                amount=tx_amount,
                memo="",
                body=body
            )
            
            if result['status'] == 'success':
                # Update database
                db.record_swap(user_id, from_token, to_token, amount, result['tx_hash'])
                return result['tx_hash']
            else:
                raise Exception(f"Swap failed: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Token swap failed: {str(e)}")
            return ""

    async def _get_swap_quote(self, from_token: str, to_token: str, amount: float, dex: str) -> int:
        """Get swap quote from DEX API"""
        try:
            # Convert amount to appropriate units
            if from_token == "ton":
                amount_in = int(amount * self.NANOTON_CONVERSION)
            else:
                # For Jetton, use 9 decimals (most use 9)
                amount_in = int(amount * 1e9)
            
            # Use DEX API to get quote
            if dex == "ston.fi":
                url = f"https://api.ston.fi/v1/quote?token_in={from_token}&token_out={to_token}&amount_in={amount_in}"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                return int(data['amount_out'])
                
            elif dex == "dedust":
                url = f"https://api.dedust.io/v2/quote?tokenIn={from_token}&tokenOut={to_token}&amountIn={amount_in}"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                return int(data['amountOut'])
                
            else:
                raise ValueError("Unsupported DEX")
                
        except Exception as e:
            logger.error(f"Failed to get swap quote: {str(e)}")
            return 0

    def _build_stonfi_swap_body(self, from_token: str, to_token: str, amount: float, min_out: int, deadline: int) -> Cell:
        """Build swap body for STON.fi router"""
        # TON to Jetton
        if from_token == "ton":
            return begin_cell()\
                .store_uint(0xf8a7ea5, 32)\
                .store_uint(0, 64)\
                .store_coins(min_out)\
                .store_address(Address(to_token))\
                .store_address(Address(self.get_address()))\
                .store_address(None)\
                .end_cell()
        # Jetton to TON
        elif to_token == "ton":
            return begin_cell()\
                .store_uint(0xdf069f3, 32)\
                .store_uint(0, 64)\
                .store_coins(min_out)\
                .store_address(Address(self.get_address()))\
                .store_address(None)\
                .end_cell()
        # Jetton to Jetton
        else:
            return begin_cell()\
                .store_uint(0xe3a0d482, 32)\
                .store_uint(0, 64)\
                .store_address(Address(to_token))\
                .store_coins(min_out)\
                .store_address(Address(self.get_address()))\
                .store_address(None)\
                .store_uint(deadline, 32)\
                .end_cell()

    def _build_dedust_swap_body(self, from_token: str, to_token: str, amount: float, min_out: int, deadline: int) -> Cell:
        """Build swap body for DeDust router"""
        # Common swap parameters
        swap_params = begin_cell()\
            .store_address(Address(to_token))\
            .store_coins(min_out)\
            .store_address(Address(self.get_address()))\
            .store_uint(deadline, 32)\
            .end_cell()
        
        # TON to Jetton
        if from_token == "ton":
            return begin_cell()\
                .store_uint(0xea06185, 32)\
                .store_ref(swap_params)\
                .end_cell()
        # Jetton to TON or Jetton
        else:
            return begin_cell()\
                .store_uint(0x9d90a8a7, 32)\
                .store_address(Address(from_token))\
                .store_coins(int(amount * 1e9))\
                .store_ref(swap_params)\
                .end_cell()

    # ---------- Emergency System Halt ----------
    async def emergency_halt(self, reason: str = "") -> None:
        """Activate emergency halt system"""
        self.halted = True
        alert_msg = f"🚨 SYSTEM HALT ACTIVATED: {reason}" if reason else "🚨 EMERGENCY SYSTEM HALT ACTIVATED"
        logger.critical(alert_msg)
        self.send_alert(alert_msg)
        
    async def resume_operations(self) -> None:
        """Resume normal operations after halt"""
        self.halted = False
        logger.info("System operations resumed")
        self.send_alert("✅ System operations resumed")

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
            
        # Basic format check
        if not address.startswith(('EQ', 'UQ', 'kQ')) or len(address) < 48:
            return False
            
        # Try to parse
        Address(address)
        return True
        
    except Exception:
        return False

async def create_staking_contract(min_stake: float, reward_rate: int) -> str:
    """Create a staking contract (production implementation)"""
    return await ton_wallet.deploy_staking_contract(
        min_stake=min_stake,
        reward_rate=reward_rate
    )

async def stake_tokens(user_id: str, amount: float, contract_address: str) -> str:
    """Stake tokens in a staking contract (production implementation)"""
    return await ton_wallet.stake_tokens(user_id, amount, contract_address)

async def execute_swap(user_id: str, from_token: str, to_token: str, amount: float, slippage: float = 0.01) -> str:
    """Execute token swap (production implementation)"""
    return await ton_wallet.execute_swap(user_id, from_token, to_token, amount, slippage)

async def process_ton_withdrawal(user_id: int, amount: float, address: str) -> Dict[str, Union[str, float]]:
    """Process TON withdrawal (public interface)"""
    return await ton_wallet.process_withdrawal(user_id, amount, address)

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
            'last_balance_check': ton_wallet.last_balance_check.isoformat(),
            'connection_type': 'HTTP' if ton_wallet.use_http_fallback else 'LiteClient',
            'halted': ton_wallet.halted
        }
    except Exception as e:
        logger.error(f"Failed to get wallet status: {e}")
        return {
            'error': str(e),
            'healthy': False,
            'initialized': False,
            'halted': True
        }

async def activate_emergency_halt(reason: str = "") -> None:
    """Public interface for emergency halt"""
    await ton_wallet.emergency_halt(reason)

async def resume_system_operations() -> None:
    """Public interface to resume operations"""
    await ton_wallet.resume_operations()