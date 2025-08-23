from functools import lru_cache
from datetime import datetime, timedelta

class PaginationCache:
    def __init__(self):
        self.cache = {}
        self.expiry_time = timedelta(minutes=5)
    
    def store(self, key, data, hash_val):
        """Store paginated data with hash"""
        self.cache[key] = {
            'data': data,
            'hash': hash_val,
            'timestamp': datetime.now()
        }
    
    def get(self, key, hash_val):
        """Get cached data if hash matches"""
        if key in self.cache:
            cached = self.cache[key]
            
            # Check expiry
            if datetime.now() - cached['timestamp'] > self.expiry_time:
                del self.cache[key]
                return None
            
            # Check hash
            if cached['hash'] == hash_val:
                return cached['data']
        
        return None

# Global cache instance
pagination_cache = PaginationCache()