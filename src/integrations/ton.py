from typing import Dict, Optional, Any 
import urllib.parse
import asyncio
import base64
import logging
from pytoniq import LiteClient, WalletV4R2, Address
from pytoniq_core import begin_cell
from src.utils.validators import validate_ton_address
from config import config
from src.database.mongo import db, update_game_coins
from src.utils.security import secure_mask

logger = logging.getLogger(__name__)

class TonWallet:
    def __init__(self):
        self.client = None
        self.wallet = None
        self.healthy = False
        self.status = "uninitialized"
        self.balance = 0.0
        self.address = None
        self.network = config.TON_NETWORK
        self.initialized = False

    async def initialize_ton_wallet():
        """Initialize TON wallet connection with retry logic"""
        global ton_wallet, client
        
        max_retries = 3
        backoff_sec = 2
        
        for attempt in range(max_retries):
            try:
                # Initialize LiteClient with proper network config
                if config.TON_NETWORK == 'testnet':
                    client = LiteClient.from_testnet_config()
                else:
                    client = LiteClient.from_mainnet_config()
                
                await client.connect()
                
                # Initialize wallet with secure handling
                if config.TON_MNEMONIC:
                    ton_wallet = await WalletV4R2.from_mnemonic(
                        client, 
                        config.TON_MNEMONIC.split(),
                        workchain=0
                    )
                elif config.TON_PRIVATE_KEY:
                    # Ensure proper base64 decoding
                    private_key = base64.urlsafe_b64decode(config.TON_PRIVATE_KEY)
                    ton_wallet = WalletV4R2(
                        provider=client, 
                        private_key=private_key,
                        workchain=0
                    )
                
                logger.info(f"TON wallet initialized: {ton_wallet.address}")
                return True
            except Exception as e:
                logger.error(f"TON wallet initialization attempt {attempt+1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(backoff_sec * (2 ** attempt))
                else:
                    logger.critical("TON wallet initialization failed after all retries")
                    return False

    async def _connect_with_retries(self, retries=3, timeout=10):
        """Attempt to connect to TON network with retries and timeouts"""
        for attempt in range(1, retries + 1):
            try:
                for server in config.TON_LITE_SERVERS:
                    ip = server['ip']
                    port = server['port']
                    pubkey = server['id']['key']
                    
                    # Convert IP from integer to string format
                    ip_str = f"{ip >> 24 & 0xFF}.{ip >> 16 & 0xFF}.{ip >> 8 & 0xFF}.{ip & 0xFF}"
                    
                    logger.info(f"Connecting to {ip_str}:{port} (attempt {attempt}/{retries})")
                    
                    try:
                        # Attempt connection with timeout
                        await asyncio.wait_for(
                            self.client.connect(ip_str, port, pubkey),
                            timeout=timeout
                        )
                        
                        # Verify connection
                        await asyncio.wait_for(
                            self.client.get_masterchain_info(),
                            timeout=5
                        )
                        
                        logger.info(f"Connected to TON node {ip_str}:{port}")
                        self.wallet.provider = self.client  # Attach provider to wallet
                        return True
                    except (asyncio.TimeoutError, ConnectionError) as e:
                        logger.warning(f"Connection to {ip_str}:{port} failed: {type(e).__name__}")
                    except Exception as e:
                        logger.error(f"Error connecting to {ip_str}:{port}: {str(e)}")
                
                # Wait before retrying if all servers failed
                if attempt < retries:
                    await asyncio.sleep(2)
                    
            except Exception as e:
                logger.error(f"Connection attempt {attempt} failed: {str(e)}")
        
        logger.error("All connection attempts to TON network failed")
        return False

    async def _get_balance(self):
        """Get wallet balance with fallback to 0 on failure"""
        try:
            if not self.client or not self.client.is_connected():
                return 0.0
                
            state = await self.wallet.get_state(self.client)
            return state.balance.to_tokens()
        except Exception as e:
            logger.error(f"Failed to get wallet balance: {str(e)}")
            return 0.0

    def get_status(self):
        """Get wallet status information"""
        return {
            "healthy": self.healthy,
            "status": self.status,
            "balance": self.balance,
            "address": secure_mask(self.address) if self.address else None,
            "network": self.network,
            "connected": self.client.is_connected() if self.client else False
        }
        
    async def send_ton(self, to_address: str, amount: float) -> dict:
        """Send TON to specified address with robust error handling"""
        if not self.initialized:
            return {'success': False, 'error': 'Wallet not initialized'}
            
        try:
            # Validate address
            if not validate_ton_address(to_address):
                return {'success': False, 'error': 'Invalid recipient address'}
                
            # Convert amount to nanoton
            amount_nano = int(amount * 1e9)
            
            # Create transfer message
            msg = self.wallet.create_transfer_message(
                to_addr=Address(to_address),
                value=amount_nano
            )
            
            # Send transaction
            if self.client and self.client.is_connected():
                tx = await self.wallet.raw_transfer(message=msg)
                return {
                    'success': True,
                    'tx_hash': tx['hash'],
                    'amount': amount,
                    'to_address': to_address
                }
            else:
                return {'success': False, 'error': 'No network connection'}
        except Exception as e:
            logger.error(f"TON transfer error: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}
        
    
    async def robust_send_ton(to_address: str, amount: float) -> Dict[str, Any]:
        """Send TON with connection error handling (production-grade)"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Attempt standard send
                return await send_ton(to_address, amount)
            except (ConnectionResetError, asyncio.IncompleteReadError) as e:
                logger.warning(f"Network error during transfer (attempt {attempt+1}/{max_retries}): {str(e)}")
                
                # Implement exponential backoff
                wait_time = 1 + (attempt * 2)
                await asyncio.sleep(wait_time)
                
                # Re-establish connection
                if client:
                    await client.reconnect()
                else:
                    await initialize_ton_wallet()
                
                # Last attempt: escalate error
                if attempt == max_retries - 1:
                    logger.critical("TON transfer failed after all retries")
                    return {
                        'success': False,
                        'error': 'Network failure after multiple retries',
                        'retries': max_retries
                    }
    
    async def create_payment_request(self, user_id: int, item_id: str, amount_ton: float) -> str:
        """Create TON payment request"""
        if not self.initialized or not self.address:
            return ""
        
        try:
            # Convert amount to nanoton
            amount_nano = int(amount_ton * 1e9)
            
            # Create structured comment
            comment = f"purchase:{user_id}:{item_id}"
            encoded_comment = urllib.parse.quote(comment, safe='')
            
            # Create payment link
            return (f"ton://transfer/{self.address}"
                    f"?amount={amount_nano}"
                    f"&text={encoded_comment}")
        except Exception as e:
            logger.error(f"Payment request creation failed: {str(e)}")
            return ""
            
    def game_coins_to_ton(self, coins: int) -> float:
        """Convert game coins to TON equivalent"""
        return coins / config.GC_TO_TON_RATE

# Global wallet instance
ton_wallet = TonWallet()

async def initialize_ton_wallet():
    """Initialize the TON wallet instance"""
    return await ton_wallet.initialize()

async def get_wallet_status():
    """Get current wallet status"""
    return ton_wallet.get_status()

async def process_ton_withdrawal(user_id: int, amount_gc: int) -> dict:
    """Process game coin withdrawal to TON"""
    if not ton_wallet.initialized:
        return {'status': 'failed', 'error': 'Wallet system unavailable'}
    
    try:
        # Get user data
        user = db.users.find_one({"user_id": user_id})
        if not user:
            return {'status': 'failed', 'error': 'User not found'}
        
        # Validate balance
        if user.get("game_coins", 0) < amount_gc:
            return {'status': 'failed', 'error': 'Insufficient game coins'}
        
        # Validate wallet
        wallet_address = user.get("wallet_address")
        if not wallet_address or not validate_ton_address(wallet_address):
            return {'status': 'failed', 'error': 'Invalid wallet address'}
        
        # Convert and send
        amount_ton = ton_wallet.game_coins_to_ton(amount_gc)
        tx_result = await ton_wallet.send_ton(wallet_address, amount_ton)
        
        if tx_result.get('success'):
            # Deduct GC from user
            update_game_coins(user_id, -amount_gc)
            return {
                'status': 'success',
                'tx_hash': tx_result['tx_hash'],
                'amount_ton': amount_ton,
                'new_gc_balance': user["game_coins"] - amount_gc
            }
        return {
            'status': 'failed',
            'error': tx_result.get('error', 'Withdrawal failed')
        }
    except Exception as e:
        logger.error(f"Withdrawal processing failed: {str(e)}")
        return {'status': 'error', 'error': 'Internal processing error'}

async def process_in_game_purchase(user_id: int, item_id: str, price_ton: float) -> dict:
    """Process in-game purchase using TON"""
    if not ton_wallet.initialized:
        return {'status': 'failed', 'error': 'Payment system unavailable'}
        
    try:
        # Get user data
        user_data = db.users.find_one({"user_id": user_id})
        if not user_data:
            return {'status': 'failed', 'error': 'User not found'}
        
        # Verify wallet connection
        wallet_address = user_data.get('wallet_address')
        if not wallet_address:
            return {'status': 'failed', 'error': 'Wallet not connected'}
        
        # Create payment request
        payment_request = await ton_wallet.create_payment_request(user_id, item_id, price_ton)
        if not payment_request:
            return {'status': 'failed', 'error': 'Payment request creation failed'}
        
        return {
            'status': 'pending',
            'payment_request': payment_request,
            'message': 'Confirm payment in your wallet'
        }
    except Exception as e:
        logger.error(f"In-game purchase error: {str(e)}")
        return {'status': 'error', 'error': 'Purchase processing failed'}
    
def save_wallet_address(user_id: int, address: str) -> bool:
    """Save user's wallet address to database"""
    # Validation happens in MongoDB function
    from src.database.mongo import connect_wallet
    return connect_wallet(user_id, address)

def is_valid_ton_address(address: str) -> bool:
    """Validate TON wallet address"""
    return validate_ton_address(address)