def to_ton(amount: float) -> float:
    """Convert raw amount to TON (1 TON = 1,000,000,000 nanoton)"""
    return amount  # Our system uses TON as base unit

def ton_to_nano(amount: float) -> int:
    """Convert TON to nanoton for blockchain operations"""
    return int(amount * 10**9)

def convert_currency(amount_ton: float, rate: float) -> float:
    """Convert TON to fiat currency"""
    return amount_ton * rate

def calculate_fee(amount: float, fee_percent: float, min_fee: float) -> float:
    """Calculate transaction fee"""
    fee = amount * fee_percent / 100
    return max(fee, min_fee)