# src/integrations/ton.py
import urllib.parse
from urllib.parse import quote
import os
import asyncio
import base64
import logging
from typing import Dict, Optional
from pytoniq import LiteClient, WalletV4R2, Wallet
from pytoniq_core import Address, Cell, begin_cell
from src.utils.security import validate_ton_address
from config import config
from src.database.firebase import get_user_data, update_user

logger = logging.getLogger(__name__)

# Global wallet instance
ton_wallet = None
client = None

async def initialize_ton_wallet():
    """Initialize TON wallet connection"""
    global ton_wallet, client
    
    try:
        # Initialize LiteClient
        if config.TON_NETWORK == 'testnet':
            client = LiteClient.from_testnet_config(trusted_index=0)
        else:
            client = LiteClient.from_mainnet_config(trusted_index=0)
        
        await client.connect()
        
        # Initialize wallet
        if config.TON_MNEMONIC:
            ton_wallet = await WalletV4R2.from_mnemonic(client, config.TON_MNEMONIC.split())
        elif config.TON_PRIVATE_KEY:
            private_key = base64.b64decode(config.TON_PRIVATE_KEY)
            ton_wallet = WalletV4R2(provider=client, 
                                    private_key=private_key, 
                                    workchain=0)
        
        logger.info(f"TON wallet initialized: {ton_wallet.address}")
        return True
    except Exception as e:
        logger.error(f"TON wallet initialization failed: {str(e)}")
        return False

async def get_wallet_status() -> Dict[str, any]:
    """Get operational wallet status"""
    if not ton_wallet or not client:
        return {'healthy': False, 'error': 'Wallet not initialized'}
    
    try:
        balance = await ton_wallet.get_balance()
        return {
            'healthy': True,
            'address': str(ton_wallet.address),
            'balance': balance,
            'network': config.TON_NETWORK
        }
    except Exception as e:
        return {'healthy': False, 'error': str(e)}

async def process_withdrawal(user_id: int, amount_gc: int) -> Dict[str, any]:
    """Process withdrawal of game coins to TON"""
    try:
        # Validate withdrawal amount
        if amount_gc < config.MIN_WITHDRAWAL_GC:
            return {
                'status': 'failed',
                'error': f'Minimum withdrawal is {config.MIN_WITHDRAWAL_GC} GC'
            }
        
        # Get user data
        user_data = get_user_data(user_id)
        if not user_data:
            return {'status': 'failed', 'error': 'User not found'}
        
        # Check game coin balance
        if user_data.get('game_coins', 0) < amount_gc:
            return {'status': 'failed', 'error': 'Insufficient game coins'}
        
        # Validate wallet address
        wallet_address = user_data.get('wallet_address')
        if not wallet_address or not validate_ton_address(wallet_address):
            return {'status': 'failed', 'error': 'Invalid wallet address'}
        
        # Convert GC to TON
        amount_ton = amount_gc / config.GC_TO_TON_RATE
        
        # Send TON
        tx_result = await send_ton(wallet_address, amount_ton)
        if not tx_result['success']:
            return tx_result
        
        # Deduct GC from user balance
        new_gc_balance = user_data['game_coins'] - amount_gc
        update_user(user_id, {'game_coins': new_gc_balance})
        
        return {
            'status': 'success',
            'tx_hash': tx_result['tx_hash'],
            'amount_ton': amount_ton,
            'new_gc_balance': new_gc_balance
        }
    except Exception as e:
        logger.error(f"Withdrawal processing error: {str(e)}")
        return {'status': 'error', 'error': 'Internal processing error'}

async def send_ton(to_address: str, amount: float) -> Dict[str, any]:
    """Send TON to specified address"""
    global ton_wallet
    
    try:
        if not ton_wallet:
            return {'success': False, 'error': 'Wallet not initialized'}
        
        # Convert amount to nanoton
        amount_nano = int(amount * 1e9)
        
        # Create transfer message
        msg = ton_wallet.create_transfer_message(
            to_addr=Address(to_address),
            value=amount_nano
        )
        
        # Send transaction
        tx = await ton_wallet.raw_transfer(message=msg)
        
        return {
            'success': True,
            'tx_hash': tx['hash'],
            'amount': amount,
            'to_address': to_address
        }
    except Exception as e:
        logger.error(f"TON transfer error: {str(e)}")
        return {'success': False, 'error': str(e)}

async def process_in_game_purchase(user_id: int, item_id: str, price_ton: float) -> Dict[str, any]:
    """Process in-game purchase using TON"""
    try:
        # Get user data
        user_data = get_user_data(user_id)
        if not user_data:
            return {'status': 'failed', 'error': 'User not found'}
        
        # Verify user has connected wallet
        wallet_address = user_data.get('wallet_address')
        if not wallet_address:
            return {'status': 'failed', 'error': 'Wallet not connected'}
        
        # Create payment request
        payment_request = create_payment_request(user_id, item_id, price_ton)
        
        return {
            'status': 'pending',
            'payment_request': payment_request,
            'message': 'Confirm payment in your wallet'
        }
    except Exception as e:
        logger.error(f"In-game purchase error: {str(e)}")
        return {'status': 'error', 'error': 'Purchase processing failed'}
    
async def create_payment_request(user_id: int, item_id: str, amount_ton: float) -> str:
    """Create TON payment request for in-game purchases with proper validation"""
    try:
        # Ensure wallet is initialized
        if not ton_wallet:
            if not await initialize_on_demand():
                logger.error("TON wallet not available for payment requests")
                return ""
        
        # Convert amount to nanoton
        amount_nano = int(amount_ton * 1e9)
        
        # Create structured comment for payment tracking
        comment = f"purchase:{user_id}:{item_id}"
        encoded_comment = quote(comment, safe='')
        
        # Create payment link
        return (f"ton://transfer/{str(ton_wallet.address)}"
                f"?amount={amount_nano}"
                f"&text={encoded_comment}")
                
    except Exception as e:
        logger.error(f"Payment request creation failed: {str(e)}")
        return ""

def game_coins_to_ton(coins: int) -> float:
    """Convert game coins to TON equivalent"""
    return coins / config.GC_TO_TON_RATE

def is_valid_ton_address(address: str) -> bool:
    """Validate TON wallet address"""
    return validate_ton_address(address)

def save_wallet_address(user_id: int, address: str) -> bool:
    """Save user's wallet address to database"""
    try:
        if not validate_ton_address(address):
            return False
            
        update_user(user_id, {'wallet_address': address})
        return True
    except Exception as e:
        logger.error(f"Error saving wallet address: {str(e)}")
        return False

async def initialize_on_demand():
    """Initialize TON wallet if not already initialized"""
    global ton_wallet
    if not ton_wallet:
        return await initialize_ton_wallet()
    return True