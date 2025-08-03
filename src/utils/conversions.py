import requests
from config import Config


def to_xno(raw_amount: int) -> float:
    return raw_amount / 10**30

def to_raw(xno_amount: float) -> int:
    return int(xno_amount * 10**30)

def usd_to_xno(amount: float, inverse=False) -> float:
    """Convert between USD and XNO using CoinMarketCap"""
    if not Config.CMC_API_KEY:
        # Fallback rate if API key not available
        return amount * (1/3.0 if inverse else 3.0)
    
    try:
        url = "https://pro-api.coinmarketcap.com/v2/tools/price-conversion"
        params = {
            'amount': amount,
            'symbol': 'XNO' if inverse else 'USD',
            'convert': 'USD' if inverse else 'XNO'
        }
        headers = {'X-CMC_PRO_API_KEY': Config.CMC_API_KEY}
        
        response = requests.get(url, params=params, headers=headers)
        data = response.json()
        
        if response.status_code == 200 and data['status']['error_code'] == 0:
            quote = data['data']['quote']
            if inverse:
                # Converting USD to XNO
                return quote['XNO']['price']
            else:
                # Converting XNO to USD
                return quote['USD']['price']
    except Exception:
        pass
    
    # Fallback if API fails
    return amount * (1/3.0 if inverse else 3.0)