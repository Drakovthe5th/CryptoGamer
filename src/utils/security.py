import hashlib
import hmac
from config import Config

def validate_telegram_hash(init_hash: str, data_str: str) -> bool:
    try:
        secret_key = hashlib.sha256(Config.TOKEN.encode()).digest()
        computed_hash = hmac.new(secret_key, data_str.encode(), hashlib.sha256).hexdigest()
        return computed_hash == init_hash
    except Exception as e:
        return False