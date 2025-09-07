import random
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from .base_game import BaseGame
from src.database.mongo import db, get_user_data, update_game_coins


logger = logging.getLogger(__name__)

class PokerHand(Enum):
    HIGH_CARD = 1
    PAIR = 2
    TWO_PAIR = 3
    THREE_OF_A_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9
    ROYAL_FLUSH = 10

class PokerGameState(Enum):
    WAITING = "waiting"
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    COMPLETED = "completed"

class PokerGame(BaseGame):
    def __init__(self):
        super().__init__("poker")
        self.tables = {}  # table_id -> PokerTable
        self.max_players_per_table = 6
        self.small_blind = 10  # in game coins
        self.big_blind = 20    # in game coins
        self.ante = 5          # in game coins
        self.max_buy_in = 1000 # in game coins
        
    def get_init_data(self, user_id: str) -> Dict[str, Any]:
        """Get initial poker game data"""
        base_data = super().get_init_data(user_id)
        base_data.update({
            "tables_available": self.get_available_tables(),
            "max_players": self.max_players_per_table,
            "blinds": {"small": self.small_blind, "big": self.big_blind},
            "max_buy_in": self.max_buy_in,
            "user_balance": self._get_user_balance(user_id)
        })
        return base_data
        
    def handle_action(self, user_id: str, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle poker game actions"""
        if action == "join_table":
            return self.join_table(user_id, data.get('table_id'))
        elif action == "leave_table":
            return self.leave_table(user_id, data.get('table_id'))
        elif action == "sit_out":
            return self.sit_out(user_id, data.get('table_id'))
        elif action == "come_back":
            return self.come_back(user_id, data.get('table_id'))
        elif action == "fold":
            return self.fold(user_id, data.get('table_id'))
        elif action == "check":
            return self.check(user_id, data.get('table_id'))
        elif action == "call":
            return self.call(user_id, data.get('table_id'))
        elif action == "raise":
            return self.raise_bet(user_id, data.get('table_id'), data.get('amount'))
        elif action == "all_in":
            return self.all_in(user_id, data.get('table_id'))
        else:
            return {"error": "Invalid poker action"}
    
    def join_table(self, user_id: str, table_id: str) -> Dict[str, Any]:
        """Join a poker table"""
        if table_id not in self.tables:
            return {"error": "Table not found"}
            
        table = self.tables[table_id]
        user_balance = self._get_user_balance(user_id)
        
        if len(table.players) >= self.max_players_per_table:
            return {"error": "Table is full"}
            
        if user_balance < table.big_blind * 10:  # Minimum 10 big blinds to join
            return {"error": "Insufficient funds"}
            
        # Add player to table
        player = {
            "user_id": user_id,
            "balance": min(self.max_buy_in, user_balance),
            "cards": [],
            "folded": False,
            "all_in": False,
            "current_bet": 0,
            "total_bet": 0,
            "sitting_out": False
        }
        
        table.players.append(player)
        
        # If table was empty, start the game
        if len(table.players) == 1:
            self.start_new_hand(table_id)
            
        return {"success": True, "table_state": self.get_table_state(table_id)}
    
    def start_new_hand(self, table_id: str) -> None:
        """Start a new hand at the table"""
        table = self.tables[table_id]
        table.deck = self.create_deck()
        random.shuffle(table.deck)
        table.community_cards = []
        table.pot = 0
        table.state = PokerGameState.PREFLOP
        table.current_player_idx = 0
        table.min_raise = table.big_blind
        
        # Deal cards to players
        for player in table.players:
            if not player["sitting_out"]:
                player["cards"] = [table.deck.pop(), table.deck.pop()]
                player["folded"] = False
                player["all_in"] = False
                player["current_bet"] = 0
                player["total_bet"] = 0
        
        # Post blinds
        self.post_blinds(table)
        
        logger.info(f"Started new hand at table {table_id}")
    
    def post_blinds(self, table) -> None:
        """Post small and big blinds"""
        # Small blind
        sb_player = table.players[table.dealer_position]
        sb_amount = min(table.small_blind, sb_player["balance"])
        sb_player["balance"] -= sb_amount
        sb_player["current_bet"] = sb_amount
        sb_player["total_bet"] = sb_amount
        table.pot += sb_amount
        
        # Big blind
        bb_idx = (table.dealer_position + 1) % len(table.players)
        bb_player = table.players[bb_idx]
        bb_amount = min(table.big_blind, bb_player["balance"])
        bb_player["balance"] -= bb_amount
        bb_player["current_bet"] = bb_amount
        bb_player["total_bet"] = bb_amount
        table.pot += bb_amount
        
        # Set current player to after big blind
        table.current_player_idx = (bb_idx + 1) % len(table.players)
    
    def evaluate_hand(self, player_cards: List[str], community_cards: List[str]) -> Tuple[PokerHand, List[int]]:
        """Evaluate poker hand strength"""
        # Implementation of hand evaluation logic
        # This would determine the best 5-card hand from 7 cards (2 hole + 5 community)
        # Return hand strength and kickers for tie-breaking
        return PokerHand.HIGH_CARD, [1, 2, 3, 4, 5]  # Placeholder
    
    def determine_winner(self, table) -> List[Dict]:
        """Determine winner(s) and distribute pot"""
        active_players = [p for p in table.players if not p["folded"] and not p["sitting_out"]]
        
        if len(active_players) == 1:
            # Only one player left, they win
            return [{"user_id": active_players[0]["user_id"], "amount": table.pot}]
        
        # Evaluate all active hands
        evaluated_hands = []
        for player in active_players:
            hand_strength, kickers = self.evaluate_hand(player["cards"], table.community_cards)
            evaluated_hands.append({
                "player": player,
                "hand_strength": hand_strength.value,
                "kickers": kickers
            })
        
        # Sort by hand strength (descending)
        evaluated_hands.sort(key=lambda x: (x["hand_strength"], *x["kickers"]), reverse=True)
        
        # Determine winners (could be multiple in case of tie)
        winners = []
        best_hand = evaluated_hands[0]
        
        for hand in evaluated_hands:
            if hand["hand_strength"] == best_hand["hand_strength"] and hand["kickers"] == best_hand["kickers"]:
                winners.append(hand["player"])
        
        # Distribute pot among winners
        prize_per_winner = table.pot // len(winners)
        remainder = table.pot % len(winners)
        
        results = []
        for i, winner in enumerate(winners):
            amount = prize_per_winner + (1 if i < remainder else 0)
            results.append({"user_id": winner["user_id"], "amount": amount})
            
        return results
    
    def get_available_tables(self) -> List[Dict]:
        """Get list of available poker tables"""
        tables = []
        for table_id, table in self.tables.items():
            tables.append({
                "id": table_id,
                "players": len(table.players),
                "max_players": self.max_players_per_table,
                "blinds": {"small": table.small_blind, "big": table.big_blind},
                "average_pot": table.average_pot,
                "hands_per_hour": table.hands_per_hour
            })
        return tables
    
    def get_table_state(self, table_id: str) -> Dict[str, Any]:
        """Get current state of a poker table"""
        if table_id not in self.tables:
            return {"error": "Table not found"}
            
        table = self.tables[table_id]
        return {
            "id": table_id,
            "state": table.state.value,
            "community_cards": table.community_cards,
            "pot": table.pot,
            "current_player": table.current_player_idx,
            "players": [
                {
                    "user_id": p["user_id"],
                    "balance": p["balance"],
                    "current_bet": p["current_bet"],
                    "folded": p["folded"],
                    "all_in": p["all_in"],
                    "sitting_out": p["sitting_out"]
                } for p in table.players
            ],
            "min_raise": table.min_raise,
            "dealer_position": table.dealer_position
        }
    
    def _get_user_balance(self, user_id: str) -> int:
        """Get user's game coin balance"""
        user_data = get_user_data(user_id)
        return user_data.get("game_coins", 0) if user_data else 0

class PokerTable:
    def __init__(self, table_id: str, small_blind: int, big_blind: int):
        self.id = table_id
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.players = []
        self.community_cards = []
        self.deck = []
        self.pot = 0
        self.state = PokerGameState.WAITING
        self.current_player_idx = 0
        self.dealer_position = 0
        self.min_raise = big_blind
        self.average_pot = 0
        self.hands_per_hour = 0
        self.hand_history = []
        
    def create_deck(self) -> List[str]:
        """Create a standard 52-card deck"""
        suits = ['h', 'd', 'c', 's']  # hearts, diamonds, clubs, spades
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        return [f"{rank}{suit}" for suit in suits for rank in ranks]