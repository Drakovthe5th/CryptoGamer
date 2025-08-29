import os
from pymongo import MongoClient
from datetime import datetime
from typing import Optional
from datetime import datetime
import enum
from src.utils.pagination import Paginator

class User:
    def __init__(self, data):
        self.user_id = data.get('user_id')
        self.username = data.get('username', '')
        self.game_coins = data.get('game_coins', 0)
        self.last_played = data.get('last_played', {})
        self.referral_count = data.get('referral_count', 0)
        self.faucet_claimed = data.get('faucet_claimed')
        self.wallet_address = data.get('wallet_address', '')
        self.daily_coins_earned = data.get('daily_coins_earned', 0)
        self.daily_resets = data.get('daily_resets', {})
        self.inventory = data.get('inventory', [])
        self.membership_tier = data.get('membership_tier', 'BASIC')
        self.created_at = data.get('created_at', datetime.now())
        self.crew_credits = data.get('crew_credits', 0)
        self.telegram_stars = data.get('telegram_stars', 0)
        self.stars_transactions = data.get('stars_transactions', [])

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'username': self.username,
            'game_coins': self.game_coins,
            'last_played': self.last_played,
            'referral_count': self.referral_count,
            'faucet_claimed': self.faucet_claimed,
            'wallet_address': self.wallet_address,
            'daily_coins_earned': self.daily_coins_earned,
            'daily_resets': self.daily_resets,
            'inventory': self.inventory,
            'membership_tier': self.membership_tier,
            'created_at': self.created_at,
            'crew_credits': self.crew_credits,
            'telegram_stars': self.telegram_stars,
            'stars_transactions': self.stars_transactions
        }

class Quest:
    def __init__(self, data):
        self.title = data.get('title', '')
        self.description = data.get('description', '')
        self.reward_ton = data.get('reward_ton', 0.0)
        self.reward_points = data.get('reward_points', 0)
        self.active = data.get('active', True)
        self.completions = data.get('completions', 0)
        self.created_at = data.get('created_at', datetime.now())

    def to_dict(self):
        return {
            'title': self.title,
            'description': self.description,
            'reward_ton': self.reward_ton,
            'reward_points': self.reward_points,
            'active': self.active,
            'completions': self.completions,
            'created_at': self.created_at
        }

class StarsTransaction:
    def __init__(self, data):
        self.transaction_id = data.get('transaction_id')
        self.user_id = data.get('user_id')
        self.amount = data.get('amount', 0)
        self.currency = data.get('currency', 'XTR')
        self.product_id = data.get('product_id')
        self.status = data.get('status', 'pending')
        self.provider_data = data.get('provider_data', {})
        self.created_at = data.get('created_at', datetime.now())
        self.completed_at = data.get('completed_at')

    def to_dict(self):
        return {
            'transaction_id': self.transaction_id,
            'user_id': self.user_id,
            'amount': self.amount,
            'currency': self.currency,
            'product_id': self.product_id,
            'status': self.status,
            'provider_data': self.provider_data,
            'created_at': self.created_at,
            'completed_at': self.completed_at
        }
    
class PaymentMethod:
    def __init__(self, data):
        self.user_id = data.get('user_id')
        self.method_type = data.get('method_type')
        self.is_default = data.get('is_default', False)
        self.details = data.get('details', {})
        self.created_at = data.get('created_at', datetime.now())

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'method_type': self.method_type,
            'is_default': self.is_default,
            'details': self.details,
            'created_at': self.created_at
        }
    
class Giveaway:
    def __init__(self, data):
        self.giveaway_id = data.get('giveaway_id')
        self.creator_id = data.get('creator_id')
        self.giveaway_type = data.get('giveaway_type')
        self.winners_count = data.get('winners_count')
        self.prize_value = data.get('prize_value')
        self.status = data.get('status', 'active')
        self.participants = data.get('participants', [])
        self.winners = data.get('winners', [])
        self.created_at = data.get('created_at', datetime.now())
        self.end_date = data.get('end_date')

    def to_dict(self):
        return {
            'giveaway_id': self.giveaway_id,
            'creator_id': self.creator_id,
            'giveaway_type': self.giveaway_type,
            'winners_count': self.winners_count,
            'prize_value': self.prize_value,
            'status': self.status,
            'participants': self.participants,
            'winners': self.winners,
            'created_at': self.created_at,
            'end_date': self.end_date
        }

class GiftTransaction:
    def __init__(self, data):
        self.transaction_id = data.get('transaction_id')
        self.sender_id = data.get('sender_id')
        self.recipient_id = data.get('recipient_id')
        self.gift_id = data.get('gift_id')
        self.stars_amount = data.get('stars_amount')
        self.message = data.get('message', '')
        self.hide_sender_name = data.get('hide_sender_name', False)
        self.status = data.get('status', 'sent')
        self.sent_at = data.get('sent_at', datetime.now())
        self.received_at = data.get('received_at')
        self.converted_at = data.get('converted_at')

    def to_dict(self):
        return {
            'transaction_id': self.transaction_id,
            'sender_id': self.sender_id,
            'recipient_id': self.recipient_id,
            'gift_id': self.gift_id,
            'stars_amount': self.stars_amount,
            'message': self.message,
            'hide_sender_name': self.hide_sender_name,
            'status': self.status,
            'sent_at': self.sent_at,
            'received_at': self.received_at,
            'converted_at': self.converted_at
        }

class SabotageGameSession:
    def __init__(self, data):
        self.game_id = data.get('game_id')
        self.chat_id = data.get('chat_id')
        self.state = data.get('state')
        self.vault_gold = data.get('vault_gold', 0)
        self.saboteurs_stash = data.get('saboteurs_stash', 0)
        self.start_time = data.get('start_time')
        self.end_time = data.get('end_time')
        self.players = data.get('players', {})
        self.winners = data.get('winners', [])
        self.gc_rewards = data.get('gc_rewards', {})
        self.created_at = data.get('created_at', datetime.now())

class SabotagePlayer:
    def __init__(self, data):
        self.user_id = data.get('user_id')
        self.game_id = data.get('game_id')
        self.role = data.get('role')
        self.is_alive = data.get('is_alive', True)
        self.gold_mined = data.get('gold_mined', 0)
        self.gold_stolen = data.get('gold_stolen', 0)
        self.joined_at = data.get('joined_at', datetime.now())

# In your User model, add these fields:
stars_balance: int = 0  # Telegram Stars balance
active_chess_games: List[str] = []  # List of active chess game IDs
chess_stats: Dict[str, Any] = {  # Chess statistics
    "wins": 0,
    "losses": 0,
    "draws": 0,
    "total_stakes": 0,
    "total_winnings": 0
}

class ChessGameStatus(enum.Enum):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    WHITE_WON = "white_won"
    BLACK_WON = "black_won"
    DRAW = "draw"

class ChessGame(BaseModel):
    """Model for an active chess game between two players."""
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    white_player_id: int  # Telegram user ID
    black_player_id: int  # Telegram user ID
    white_stake: int = 0  # Amount of Stars staked
    black_stake: int = 0  # Amount of Stars staked
    fen: str = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"  # Standard starting position
    status: ChessGameStatus = ChessGameStatus.WAITING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        use_enum_values = True

class ChessMove(BaseModel):
    """Model for storing individual moves (for history/analysis)."""
    game_id: PyObjectId
    move: str  # UCI format (e.g., "e2e4")
    fen_after: str  # Board state after move
    player_id: int  # Who made the move
    created_at: datetime = Field(default_factory=datetime.utcnow)

def get_leaderboard(self, limit=10, offset=0, max_id=None, min_id=None, hash_val=None):
    """Get paginated leaderboard with hash validation"""
    # Base query
    query = User.select().order_by(User.points.desc())
    
    # Apply filters
    if max_id is not None:
        query = query.where(User.id < max_id)
    if min_id is not None:
        query = query.where(User.id > min_id)
    
    # Get results
    results = query.offset(offset).limit(limit)
    
    # Generate hash for validation
    id_list = [user.id for user in results]
    calculated_hash = Paginator.generate_hash(id_list)
    
    # Check if not modified
    if hash_val and hash_val == calculated_hash:
        return {'not_modified': True}
    
    return {
        'users': [user.to_dict() for user in results],
        'hash': calculated_hash,
        'has_more': len(results) == limit
    }

class PoolGameResult:
    def __init__(self, data):
        self.game_id = data.get('game_id')
        self.players = data.get('players', [])
        self.bets = data.get('bets', {})
        self.pot = data.get('pot', 0)
        self.winner = data.get('winner')
        self.start_time = data.get('start_time')
        self.end_time = data.get('end_time')

    def to_dict(self):
        return {
            'game_id': self.game_id,
            'players': self.players,
            'bets': self.bets,
            'pot': self.pot,
            'winner': self.winner,
            'start_time': self.start_time,
            'end_time': self.end_time
        }
    
class PokerTable:
    def __init__(self, data):
        self.table_id = data.get('table_id')
        self.small_blind = data.get('small_blind', 10)
        self.big_blind = data.get('big_blind', 20)
        self.max_players = data.get('max_players', 6)
        self.players = data.get('players', [])
        self.community_cards = data.get('community_cards', [])
        self.pot = data.get('pot', 0)
        self.state = data.get('state', 'waiting')
        self.current_player = data.get('current_player', 0)
        self.dealer_position = data.get('dealer_position', 0)
        self.created_at = data.get('created_at', datetime.now())

class PokerHandResult:
    def __init__(self, data):
        self.hand_id = data.get('hand_id')
        self.table_id = data.get('table_id')
        self.players = data.get('players', [])
        self.community_cards = data.get('community_cards', [])
        self.pot = data.get('pot', 0)
        self.winners = data.get('winners', [])
        self.winning_hand = data.get('winning_hand')
        self.timestamp = data.get('timestamp', datetime.now())