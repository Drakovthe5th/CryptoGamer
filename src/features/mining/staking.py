# src/features/mining/staking.py
from src.database.mongo import get_user_balance, update_balance, record_staking
from src.integrations.staking_contracts import create_staking_contract

def validate_stake(user_id, amount):
    user_balance = get_user_balance(user_id)
    if amount < 5:
        return False, "Minimum stake is 5 TON"
    if amount > user_balance:
        return False, "Insufficient balance"
    return True, ""

async def process_stake(user_id, amount):
    # Deduct user balance
    new_balance = update_balance(user_id, -amount)
    
    # Create staking contract
    contract_address = await create_staking_contract(user_id, amount)
    
    if contract_address:
        record_staking(user_id, contract_address, amount)
        return True, contract_address
    else:
        # Refund if failed
        update_balance(user_id, amount)
        return False, "Staking contract creation failed"