import hashlib
from typing import List, Union
from src.telegram.stars import *
from src.features.monetization.gifts import *
from src.telegram.attachment_menu import AttachmentMenuManager
from src.telegram.web_events import handle_web_event

class Paginator:
    def __init__(self, limit: int = 20, offset: int = 0, max_id: int = None, min_id: int = None):
        self.limit = limit
        self.offset = offset
        self.max_id = max_id
        self.min_id = min_id
        self.hash = None
    
    def generate_hash(self, ids: List[Union[int, str]]) -> int:
        """Generate 64-bit hash for result validation"""
        hash_val = 0
        
        for id_val in ids:
            # Convert strings to long using MD5
            if isinstance(id_val, str):
                md5_hash = hashlib.md5(id_val.encode()).digest()
                id_val = int.from_bytes(md5_hash[:8], 'big')
            
            hash_val = hash_val ^ (hash_val >> 21)
            hash_val = hash_val ^ (hash_val << 35)
            hash_val = hash_val ^ (hash_val >> 4)
            hash_val = hash_val + id_val
        
        return hash_val
    
    def validate_hash(self, ids: List[Union[int, str]], received_hash: int) -> bool:
        """Validate if hash matches the current result set"""
        return self.generate_hash(ids) == received_hash
    
    def apply_pagination(self, query_set):
        """Apply pagination parameters to a query set"""
        if self.max_id is not None:
            query_set = query_set.filter(id__lt=self.max_id)
        if self.min_id is not None:
            query_set = query_set.filter(id__gt=self.min_id)
        
        return query_set[self.offset:self.offset + self.limit]