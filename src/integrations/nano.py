import logging
from nanopy import account_from_seed
from config import config

logger = logging.getLogger(__name__)

def get_wallet_address() -> str:
    try:
        # Directly generate address from seed
        address = account_from_seed(config.NANO_SEED, 0)
        return address
    except Exception as e:
        logger.error(f"Error getting wallet address: {e}")
        return ""

def send_transaction(destination: str, amount: int) -> str:
    try:
        # This needs a full implementation with state management
        # For now, just return a dummy hash
        logger.warning("Nano transactions are not fully implemented")
        return "0xDUMMY_TX_HASH"
    except Exception as e:
        logger.error(f"Error sending transaction: {e}")
        raise