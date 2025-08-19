from pytoniq import LiteClient
from src.database.mongo import get_hot_wallet, get_user_balance

async def distribute_ton_rewards(user_id, amount):
    """Send TON rewards to user's wallet"""
    client = LiteClient()
    await client.connect()
    
    user_wallet = get_user_balance(user_id)
    hot_wallet = get_hot_wallet()
    
    # Prepare transaction
    result = await client.send_transaction(
        sender=hot_wallet,
        recipient=user_wallet,
        amount=amount * 10**9,  # Convert to nanoton
        memo="Activity Reward"
    )
    
    return result['hash']

async def get_staking_yield(staked_amount):
    """Calculate daily staking yield"""
    # Placeholder - real implementation would query blockchain
    apy = 5.5  # %
    daily_yield = staked_amount * (apy / 365) / 100
    return daily_yield