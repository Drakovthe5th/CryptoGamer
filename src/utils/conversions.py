GAME_COIN_TO_TON_RATE = 2000  # 200,000 GC = 100 TON
MAX_DAILY_GAME_COINS = 20000  # 10 TON equivalent
MIN_WITHDRAWAL = 200000  # GC (100 TON equivalent)

def game_coins_to_ton(coins):
    """Convert game coins to TON cryptocurrency"""
    return coins / GAME_COIN_TO_TON_RATE

def ton_to_game_coins(ton):
    """Convert TON to game coins"""
    return ton * GAME_COIN_TO_TON_RATE

def calculate_reward(score, multiplier=1):
    """Calculate game reward with daily limit enforcement"""
    raw_coins = score * 10 * multiplier
    return min(raw_coins, MAX_DAILY_GAME_COINS)

def convert_currency(amount, rate):
    """Convert TON to fiat currency using exchange rate"""
    return amount * rate

def calculate_fee(fiat_amount, fee_percent, min_fee):
    """Calculate OTC fee with minimum threshold"""
    fee = fiat_amount * (fee_percent / 100)
    return max(fee, min_fee)

def check_daily_limit(user):
    """Check if user has reached daily earning limit"""
    return user.daily_coins_earned >= MAX_DAILY_GAME_COINS

# Add Stars to Credits conversion
STARS_TO_CREDITS_RATE = 100  # 1 Star = 100 Crew Credits

def stars_to_credits(stars):
    """Convert Telegram Stars to Crew Credits for Crypto Crew game"""
    return stars * STARS_TO_CREDITS_RATE

def credits_to_stars(credits):
    """Convert Crew Credits back to Stars (for revenue calculation)"""
    return credits / STARS_TO_CREDITS_RATE

# Keep existing GC functions
def game_coins_to_ton(coins):
    return coins / GAME_COIN_TO_TON_RATE

def ton_to_game_coins(ton):
    return ton * GAME_COIN_TO_TON_RATE