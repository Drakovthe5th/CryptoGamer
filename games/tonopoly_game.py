import random
import asyncio
from enum import Enum
from typing import List, Dict, Optional, Tuple, Any  # ADD 'Any' to the imports
from datetime import datetime
from .base_game import BaseGame, GameType, BettingType

class PlayerColor(Enum):
    BITCOIN = "#F7931A"  # Bitcoin orange
    ETHEREUM = "#627EEA" # Ethereum blue
    TON = "#0088CC"      # TON blue
    STABLECOIN = "#27AE60" # Stablecoin green

class BoardSpaceType(Enum):
    NORMAL = "normal"
    MINING = "mining"      # Earn bonus coins
    BEAR_TRAP = "bear_trap" # Lose a turn
    BULL_MARKET = "bull_market" # Move extra spaces
    HALVING = "halving"    # Double next reward
    RUG_PULL = "rug_pull"  # Go back to start
    ATH = "ath"            # Big bonus

class TONopolyPlayer:
    def __init__(self, user_id: int, username: str, color: PlayerColor):
        self.user_id = user_id
        self.username = username
        self.color = color
        self.pieces = [0, 0, 0, 0]  # 0=home, 57=complete
        self.staked_coins = 0
        self.skip_turns = 0
        self.bonus_multiplier = 1.0
        self.is_bot = False
        self.has_paid_bet = False

class TONopolyGameState(Enum):
    LOBBY = 0
    WAITING_FOR_BET = 1
    PLAYING = 2
    FINISHED = 3

class TONopolyGame(BaseGame):
    def __init__(self):
        super().__init__("tonopoly")
        self.game_type = GameType.MULTIPLAYER
        self.betting_type = BettingType.TELEGRAM_STARS
        self.max_players = 4
        self.min_players = 2
        self.supported_bet_amounts = [10, 25, 50, 100]  # Telegram Stars amounts
        
        self.players: Dict[int, TONopolyPlayer] = {}
        self.creator_id = None
        self.current_turn_index = 0
        self.state = TONopolyGameState.LOBBY
        self.dice_value = 0
        self.winner = None
        self.bet_amount = 0
        self.total_pot = 0
        self.board = self._generate_board()
        self.created_at = datetime.now()
        
    def _generate_board(self) -> List[Dict]:
        """Generate the crypto-themed game board"""
        board = []
        # Generate 52 spaces (like a deck of cards)
        space_types = [BoardSpaceType.NORMAL] * 30
        space_types.extend([BoardSpaceType.MINING] * 6)
        space_types.extend([BoardSpaceType.BEAR_TRAP] * 4)
        space_types.extend([BoardSpaceType.BULL_MARKET] * 4)
        space_types.extend([BoardSpaceType.HALVING] * 3)
        space_types.extend([BoardSpaceType.RUG_PULL] * 3)
        space_types.extend([BoardSpaceType.ATH] * 2)
        
        random.shuffle(space_types)
        
        for i, space_type in enumerate(space_types):
            board.append({
                "position": i + 1,
                "type": space_type,
                "name": self._get_space_name(space_type, i + 1)
            })
            
        return board
    
    def _get_space_name(self, space_type: BoardSpaceType, position: int) -> str:
        """Get display name for board space"""
        names = {
            BoardSpaceType.NORMAL: [
                "Satoshi's Vision", "Blockchain", "Node", "Wallet", "Mempool",
                "Gas Fee", "Private Key", "Public Key", "Hash", "Nonce",
                "Consensus", "Fork", "Token", "Coin", "DeFi",
                "Smart Contract", "dApp", "Oracle", "Liquidity", "Yield"
            ],
            BoardSpaceType.MINING: ["Bitcoin Mining", "Ethereum Staking", "TON Validation", "Cloud Mining", "GPU Farm", "ASIC Warehouse"],
            BoardSpaceType.BEAR_TRAP: ["Bear Market", "Crypto Winter", "FUD", "Regulation"],
            BoardSpaceType.BULL_MARKET: ["Bull Run", "Market Pump", "Institutional Adoption", "Mainstream News"],
            BoardSpaceType.HALVING: ["Bitcoin Halving", "Reward Reduction", "Supply Shock"],
            BoardSpaceType.RUG_PULL: ["Scam Token", "Exit Scam", "Smart Contract Exploit"],
            BoardSpaceType.ATH: ["New ATH", "Price Discovery"]
        }
        
        if space_type == BoardSpaceType.NORMAL:
            return names[space_type][position % len(names[space_type])]
        return random.choice(names[space_type])
    
    async def join_game(self, user_id: int, username: str, color: PlayerColor = None):
        if len(self.players) >= self.max_players:
            raise Exception("Game is full")
        
        if not color:
            # Assign first available color
            used_colors = [p.color for p in self.players.values()]
            for color in PlayerColor:
                if color not in used_colors:
                    break
        
        if self.creator_id is None:
            self.creator_id = user_id
            
        self.players[user_id] = TONopolyPlayer(user_id, username, color)
        
    async def set_bet(self, user_id: int, amount: int):
        """Set the bet amount (only creator can do this)"""
        if user_id != self.creator_id:
            raise Exception("Only game creator can set bet")
            
        if self.state != TONopolyGameState.LOBBY:
            raise Exception("Cannot set bet after game has started")
            
        if not self.validate_bet(user_id, amount):
            raise Exception(f"Invalid bet amount. Supported amounts: {self.supported_bet_amounts}")
            
        self.bet_amount = amount
        self.state = TONopolyGameState.WAITING_FOR_BET
        
    async def add_bet_payment(self, user_id: int, amount: int):
        """Record a player's bet payment"""
        if user_id not in self.players:
            raise Exception("Player not in game")
            
        if amount != self.bet_amount:
            raise Exception(f"Incorrect bet amount. Expected {self.bet_amount}, got {amount}")
            
        self.players[user_id].has_paid_bet = True
        self.total_pot += amount
        
        # Check if all players have paid
        if all(player.has_paid_bet for player in self.players.values()):
            await self.start_game()
            
    async def start_game(self):
        if len(self.players) < self.min_players:
            raise Exception(f"Need at least {self.min_players} players")
            
        self.state = TONopolyGameState.PLAYING
        self.current_turn_index = 0
        
    async def roll_dice(self, user_id: int) -> int:
        current_player = list(self.players.values())[self.current_turn_index]
        if user_id != current_player.user_id:
            raise Exception("Not your turn")
            
        if current_player.skip_turns > 0:
            current_player.skip_turns -= 1
            if current_player.skip_turns > 0:
                raise Exception(f"You must skip {current_player.skip_turns} more turns")
        
        self.dice_value = random.randint(1, 6)
        return self.dice_value
        
    async def move_piece(self, user_id: int, piece_index: int) -> Tuple[bool, str]:
        player = self.players[user_id]
        current_pos = player.pieces[piece_index]
        
        # Need 6 to leave home
        if current_pos == 0 and self.dice_value != 6:
            return False, "Need a 6 to leave home"
            
        # Calculate new position
        new_pos = current_pos + self.dice_value
        
        # Handle board space effects
        message = ""
        if new_pos <= len(self.board):
            space = self.board[new_pos - 1]
            message = f"Landed on {space['name']}!"
            
            if space["type"] == BoardSpaceType.MINING:
                # Bonus coins for mining
                bonus = 1000 * self.dice_value
                message += f" Mined {bonus} game coins!"
                
            elif space["type"] == BoardSpaceType.BEAR_TRAP:
                player.skip_turns = 1
                message += " Bear market! Skip next turn."
                
            elif space["type"] == BoardSpaceType.BULL_MARKET:
                # Extra move
                extra_move = random.randint(1, 3)
                new_pos += extra_move
                message += f" Bull market! Move ahead {extra_move} spaces."
                
            elif space["type"] == BoardSpaceType.HALVING:
                player.bonus_multiplier = 2.0
                message += " Halving! Next reward doubled."
                
            elif space["type"] == BoardSpaceType.RUG_PULL:
                new_pos = 0  # Back to start
                message += " Rug pull! Back to start."
                
            elif space["type"] == BoardSpaceType.ATH:
                bonus = 5000
                message += f" New ATH! Earn {bonus} game coins."
        
        # Check for captures
        for other_user_id, other_player in self.players.items():
            if other_user_id != user_id:
                for i, pos in enumerate(other_player.pieces):
                    if pos == new_pos and new_pos != 0:
                        other_player.pieces[i] = 0  # Send back to start
                        message += f" Captured {other_player.username}'s piece!"
                        break
        
        player.pieces[piece_index] = min(new_pos, 57)  # Cap at finish
        
        # Check for win condition
        if all(pos == 57 for pos in player.pieces):
            self.winner = user_id
            self.state = TONopolyGameState.FINISHED
            message += " You won the game!"
            
            # Distribute winnings
            await self.process_bet_payout(user_id, self.total_pot)
            
        # Next player's turn if didn't roll 6
        if self.dice_value != 6:
            self.current_turn_index = (self.current_turn_index + 1) % len(self.players)
            
        return True, message
        
    async def stake_coins(self, user_id: int, amount: int) -> bool:
        """Stake coins to earn interest but skip a turn"""
        player = self.players[user_id]
        
        # This would interface with your existing staking system
        player.staked_coins += amount
        player.skip_turns = 1
        return True
        
    def process_bet_payout(self, winner_id: str, total_pot: int) -> Dict[str, Any]:
        """Process betting payout according to house rules"""
        house_fee = total_pot * self.house_fee_percent // 100
        winnings = total_pot - house_fee
        
        # This would interface with Telegram Stars API
        # For now, we'll just record it
        self.players[winner_id].winnings = winnings
        
        # Record house fee for platform revenue
        # This would interface with your revenue tracking system
        
        return {
            "winner": winner_id,
            "total_pot": total_pot,
            "house_fee": house_fee,
            "winnings": winnings
        }
    
    def get_state(self) -> Dict:
        """Return the current game state for frontend"""
        return {
            "game_id": self.name,
            "state": self.state.value,
            "players": [
                {
                    "user_id": p.user_id,
                    "username": p.username,
                    "color": p.color.value,
                    "pieces": p.pieces,
                    "staked_coins": p.staked_coins,
                    "skip_turns": p.skip_turns,
                    "bonus_multiplier": p.bonus_multiplier,
                    "has_paid_bet": p.has_paid_bet
                } for p in self.players.values()
            ],
            "current_turn_index": self.current_turn_index,
            "dice_value": self.dice_value,
            "winner": self.winner,
            "bet_amount": self.bet_amount,
            "total_pot": self.total_pot,
            "board": self.board
        }
    
    def get_game_config(self) -> Dict[str, Any]:
        """Get game configuration including betting options"""
        base_config = super().get_game_config()
        base_config.update({
            "supported_colors": [color.value for color in PlayerColor],
            "max_pieces": 4,
            "board_size": 57,
            "max_dice_value": 6
        })
        return base_config