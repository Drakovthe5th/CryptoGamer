from pytoniq import Contract
from pytoniq import LiteClient
from src.database.firebase import get_hot_wallet

STAKING_CONTRACT_CODE = """(storing contract code would go here)"""

async def create_staking_contract(user_id, amount):
    """Deploy staking contract on TON blockchain"""
    client = LiteClient()
    await client.connect()
    
    # Deploy contract
    contract = await Contract.from_code(
        code=STAKING_CONTRACT_CODE,
        initial_data={
            'owner': get_hot_wallet(),
            'user_id': user_id,
            'amount': amount
        }
    )
    
    # Fund contract
    await client.transfer(
        sender=get_hot_wallet(),
        recipient=contract.address,
        amount=amount * 10**9  # nanoton
    )
    
    return contract.address