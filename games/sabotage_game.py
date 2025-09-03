import asyncio
import random
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple
from src.database.mongo import get_user_data
import json
from pymongo import MongoClient
from bson import ObjectId

# Initialize MongoDB connection
client = MongoClient('mongodb://localhost:27017/')
db = client['cryptogamer']
sabotage_games = db['sabotage_games']
players_collection = db['players']

class GameState(Enum):
    LOBBY = "lobby"
    TASKS = "tasks"
    MEETING = "meeting"
    GAME_END = "game_end"

class PlayerRole(Enum):
    MINER = "miner"
    SABOTEUR = "saboteur"
    TRAITOR = "traitor"  # A bribed miner

class SabotageGame:
    @classmethod
    def create_for_registry(cls):
        """Create a dummy instance for the game registry with default values"""
        instance = cls(game_id="sabotage_registry", chat_id=-1)
        instance._name = "Sabotage"
        instance._min_reward = 100
        instance._max_reward = 1000
        return instance

    @property
    def name(self):
        return getattr(self, '_name', "Sabotage")

    @property
    def min_reward(self):
        return getattr(self, '_min_reward', 100)

    @property
    def max_reward(self):
        return getattr(self, '_max_reward', 1000)

    def __init__(self, game_id: str = "default_game", chat_id: str = "default_chat", duration_minutes: int = 15):
        self.game_id = game_id
        self.chat_id = chat_id
        self.duration = timedelta(minutes=duration_minutes)
        self.state = GameState.LOBBY
        self.players: Dict[str, dict] = {}
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.vault_gold = 0
        self.saboteurs_stash = 0
        self.emergency_meeting_called = False
        self.meeting_end_time: Optional[datetime] = None
        self.votes: Dict[str, str] = {}  # voter_id -> voted_player_id
        self.bribe_offers: Dict[str, dict] = {}  # target_player_id -> BribeOffer
        self.entry_fee_credits = 100  # Crew Credits required to join
        self.sabotage_action_cost = 50  # Cost to perform sabotage actions
        
        # Character system
        self.characters = {
            1: {"name": "Basic Miner", "premium": False, "base": "🚶", "skins": ["😐", "😊", "😎"], "mining": "⛏️", "walking": "🚶"},
            2: {"name": "Advanced Miner", "premium": True, "base": "🚶‍♂️", "skins": ["🥷", "👮", "🦸"], "mining": "⚒️", "walking": "🏃‍♂️"},
            3: {"name": "Animal Miner", "premium": True, "base": "🐵", "skins": ["🐯", "🦁", "🐼"], "mining": "⛏️", "walking": "🐒"},
            4: {"name": "Fantasy Miner", "premium": True, "base": "🧝", "skins": ["🧛", "🧙", "🦹"], "mining": "🔮", "walking": "🧝‍♂️"},
            5: {"name": "Professional Miner", "premium": True, "base": "👨‍💼", "skins": ["👨‍🚀", "👨‍✈️", "🕵️"], "mining": "⛏️", "walking": "👨‍💼"},
            6: {"name": "Special Miner", "premium": True, "base": "🧑", "skins": ["🎅", "🤶", "🦸"], "mining": "✨", "walking": "🧑‍🦯"}
        }
        
        # Game constants
        self.MINING_RATE = 134  # Gold per minute per miner
        self.STEALING_RATE = 267  # Gold per steal per saboteur
        self.STEAL_COOLDOWN = 120  # seconds
        self.MEETING_DURATION = 120  # seconds
        self.BRIBE_COST = 500  # Gold cost for a bribe from saboteur's stash
        
        # Only initialize game document in MongoDB if not a registry instance
        if game_id != "sabotage_registry":
            game_data = {
                'game_id': game_id,
                'chat_id': chat_id,
                'state': self.state.value,
                'vault_gold': self.vault_gold,
                'saboteurs_stash': self.saboteurs_stash,
                'start_time': None,
                'end_time': None,
                'players': {},
                'created_at': datetime.now()
            }
            sabotage_games.insert_one(game_data)

    def assign_character(self, is_premium: bool):
        """Assign a character to a player based on premium status"""
        if is_premium:
            # Premium users can get any character
            available_chars = list(self.characters.keys())
        else:
            # Regular users get only non-premium characters
            available_chars = [char_id for char_id, char in self.characters.items() if not char["premium"]]
        
        # Random selection
        character_id = random.choice(available_chars)
        
        # Random skin selection
        skin = random.choice(self.characters[character_id]["skins"])
        
        return character_id, skin

    async def add_player(self, player_id: str, player_name: str):
        """Add a player to the game lobby after checking Crew Credits"""
        # Check if player has enough Crew Credits
        user_data = get_user_data(player_id)
        if user_data.get('crew_credits', 0) < self.entry_fee_credits:
            raise Exception(f"Not enough Crew Credits. Need {self.entry_fee_credits} to join.")
            
        # Deduct entry fee from Crew Credits
        players_collection.update_one(
            {'player_id': player_id},
            {'$inc': {'crew_credits': -self.entry_fee_credits}},
            upsert=True
        )
        
        # Check if player is premium and assign character accordingly
        is_premium = user_data.get('is_premium', False)
        character_id, skin = self.assign_character(is_premium)
        
        # Then add player to game
        self.players[player_id] = {
            'id': player_id,
            'name': player_name,
            'role': None,
            'is_alive': True,
            'last_action_time': None,
            'gold_mined': 0,
            'gold_stolen': 0,
            'is_mining': False,
            'is_stealing': False,
            'character': character_id,
            'skin': skin,
            'state': 'idle'
        }
        
        # Update MongoDB
        sabotage_games.update_one(
            {'game_id': self.game_id},
            {'$set': {f'players.{player_id}': self.players[player_id]}}
        )

    async def start_game(self):
        """Start the game with 6 players"""
        if len(self.players) != 6:
            raise Exception("Need exactly 6 players to start")
            
        # Assign roles (4 miners, 2 saboteurs)
        player_ids = list(self.players.keys())
        random.shuffle(player_ids)
        
        saboteurs = player_ids[:2]
        miners = player_ids[2:]
        
        for player_id in saboteurs:
            self.players[player_id]['role'] = PlayerRole.SABOTEUR.value
            
        for player_id in miners:
            self.players[player_id]['role'] = PlayerRole.MINER.value
            
        # Set game state and timers
        self.state = GameState.TASKS
        self.start_time = datetime.now()
        self.end_time = self.start_time + self.duration
        
        # Update MongoDB
        sabotage_games.update_one(
            {'game_id': self.game_id},
            {'$set': {
                'state': self.state.value,
                'start_time': self.start_time,
                'end_time': self.end_time,
                'players': self.players
            }}
        )
        
        # Start the game loop
        asyncio.create_task(self.game_loop())
        
        # Notify players of their roles
        for player_id, player in self.players.items():
            role_msg = "You are a Miner. Complete tasks to mine gold for the vault!" if player['role'] == PlayerRole.MINER.value else "You are a Saboteur! Steal gold from the vault without getting caught."
            
            # In a real implementation, you would send this via Telegram bot
            print(f"DM to {player_id}: {role_msg}")
            
            # Saboteurs get a special message with their partner
            if player['role'] == PlayerRole.SABOTEUR.value:
                partner_id = next(pid for pid in saboteurs if pid != player_id)
                partner_name = self.players[partner_id]['name']
                print(f"DM to {player_id}: Your partner is {partner_name}")

    async def game_loop(self):
        """Main game loop that runs until game ends"""
        while self.state != GameState.GAME_END and datetime.now() < self.end_time:
            # Check if saboteurs have won by stealing more than half
            if self.saboteurs_stash > self.vault_gold / 2:
                await self.end_game(saboteurs_win=True)
                break
                
            # Update mining and stealing
            await self.update_resources()
            
            # Check for emergency meetings
            if self.emergency_meeting_called and self.meeting_end_time and datetime.now() >= self.meeting_end_time:
                await self.resolve_meeting()
                
            await asyncio.sleep(1)  # Sleep for 1 second between iterations
            
        # If we get here, time ran out
        if self.state != GameState.GAME_END:
            # Check if saboteurs stole more than half
            if self.saboteurs_stash > self.vault_gold / 2:
                await self.end_game(saboteurs_win=True)
            else:
                await self.end_game(stalemate=True)

    async def update_resources(self):
        """Update gold based on player actions"""
        current_time = datetime.now()
        
        for player_id, player in self.players.items():
            if not player['is_alive']:
                continue
                
            # Miners generate gold for the vault
            if player['role'] == PlayerRole.MINER.value and player.get('is_mining', False):
                time_since_last_action = (current_time - player['last_action_time']).total_seconds() if player['last_action_time'] else 0
                gold_mined = (self.MINING_RATE / 60) * time_since_last_action
                self.vault_gold += gold_mined
                player['gold_mined'] += gold_mined
                player['last_action_time'] = current_time
                
            # Saboteurs steal gold from vault
            elif player['role'] in [PlayerRole.SABOTEUR.value, PlayerRole.TRAITOR.value] and player.get('is_stealing', False):
                # Check if cooldown has passed
                if player['last_action_time'] and (current_time - player['last_action_time']).total_seconds() < self.STEAL_COOLDOWN:
                    continue
                    
                # Steal gold (but not more than what's available)
                steal_amount = min(self.STEALING_RATE, self.vault_gold)
                self.vault_gold -= steal_amount
                self.saboteurs_stash += steal_amount
                player['gold_stolen'] += steal_amount
                player['last_action_time'] = current_time
        
        # Update MongoDB
        sabotage_games.update_one(
            {'game_id': self.game_id},
            {'$set': {
                'vault_gold': self.vault_gold,
                'saboteurs_stash': self.saboteurs_stash,
                'players': self.players
            }}
        )

    async def player_action(self, player_id: str, action: str, **kwargs):
        """Handle player actions like mining, stealing, or calling meetings"""
        if self.state != GameState.TASKS:
            raise Exception("Action not allowed in current game state")
            
        if player_id not in self.players or not self.players[player_id]['is_alive']:
            raise Exception("Player not in game or not alive")
            
        player = self.players[player_id]
        
        if action == "mine":
            player['is_mining'] = True
            player['is_stealing'] = False
            player['last_action_time'] = datetime.now()
            player['state'] = 'mining'
            
        elif action == "steal":
            if player['role'] not in [PlayerRole.SABOTEUR.value, PlayerRole.TRAITOR.value]:
                raise Exception("Only saboteurs can steal")
                
            player['is_mining'] = False
            player['is_stealing'] = True
            player['last_action_time'] = datetime.now()
            player['state'] = 'mining'
            
        elif action == "call_meeting":
            await self.call_emergency_meeting(player_id)
            
        elif action == "bribe":
            if player['role'] != PlayerRole.SABOTEUR.value:
                raise Exception("Only saboteurs can bribe")
                
            target_player_id = kwargs.get('target_player_id')
            await self.offer_bribe(player_id, target_player_id)
            
        elif action == "update_character":
            character = kwargs.get('character')
            skin = kwargs.get('skin')
            player['character'] = character
            player['skin'] = skin
            
        elif action == "move":
            player['state'] = 'walking'
            # After move completes, set back to idle
            asyncio.get_event_loop().call_later(
                0.8,  # Match animation duration
                lambda: setattr(player, 'state', 'idle')
            )
        
        # Update MongoDB
        sabotage_games.update_one(
            {'game_id': self.game_id},
            {'$set': {f'players.{player_id}': player}}
        )

    async def call_emergency_meeting(self, caller_id: str):
        """Call an emergency meeting"""
        if self.emergency_meeting_called:
            raise Exception("Meeting already in progress")
            
        self.state = GameState.MEETING
        self.emergency_meeting_called = True
        self.meeting_end_time = datetime.now() + timedelta(seconds=self.MEETING_DURATION)
        self.votes = {}
        
        # Pause all actions
        for player_id in self.players:
            self.players[player_id]['is_mining'] = False
            self.players[player_id]['is_stealing'] = False
            self.players[player_id]['state'] = 'idle'
            
        # Update MongoDB
        sabotage_games.update_one(
            {'game_id': self.game_id},
            {'$set': {
                'state': self.state.value,
                'emergency_meeting_called': self.emergency_meeting_called,
                'meeting_end_time': self.meeting_end_time,
                'votes': self.votes,
                'players': self.players
            }}
        )
        
        # Notify all players
        print(f"Emergency meeting called by {self.players[caller_id]['name']}!")

    async def vote(self, voter_id: str, suspect_id: str):
        """Cast a vote during a meeting"""
        if self.state != GameState.MEETING:
            raise Exception("No meeting in progress")
            
        if voter_id not in self.players or not self.players[voter_id]['is_alive']:
            raise Exception("Voter not in game or not alive")
            
        if suspect_id not in self.players or not self.players[suspect_id]['is_alive']:
            raise Exception("Suspect not in game or not alive")
            
        self.votes[voter_id] = suspect_id
        
        # Update MongoDB
        sabotage_games.update_one(
            {'game_id': self.game_id},
            {'$set': {'votes': self.votes}}
        )
        
        # Check if all alive players have voted
        alive_players = [pid for pid, p in self.players.items() if p['is_alive']]
        if len(self.votes) == len(alive_players):
            await self.resolve_meeting()

    async def resolve_meeting(self):
        """Resolve the meeting by counting votes and ejecting player if needed"""
        # Count votes
        vote_count = {}
        for suspect_id in self.votes.values():
            vote_count[suspect_id] = vote_count.get(suspect_id, 0) + 1
            
        # Find player with most votes
        ejected_id = None
        max_votes = 0
        
        for suspect_id, votes in vote_count.items():
            if votes > max_votes:
                max_votes = votes
                ejected_id = suspect_id
                
        # Eject player if there's a clear majority
        if ejected_id and max_votes > len(self.votes) / 2:
            self.players[ejected_id]['is_alive'] = False
            
            # Check if game should end
            saboteurs_alive = [pid for pid, p in self.players.items() 
                              if p['is_alive'] and p['role'] in [PlayerRole.SABOTEUR.value, PlayerRole.TRAITOR.value]]
                              
            if len(saboteurs_alive) == 0:
                await self.end_game(saboteurs_win=False)
                return
                
            # Reveal role of ejected player
            ejected_role = self.players[ejected_id]['role']
            print(f"{self.players[ejected_id]['name']} was ejected. They were a {ejected_role}!")
        
        # Resume game
        self.state = GameState.TASKS
        self.emergency_meeting_called = False
        self.meeting_end_time = None
        self.votes = {}
        
        # Update MongoDB
        sabotage_games.update_one(
            {'game_id': self.game_id},
            {'$set': {
                'state': self.state.value,
                'emergency_meeting_called': self.emergency_meeting_called,
                'meeting_end_time': self.meeting_end_time,
                'votes': self.votes,
                'players': self.players
            }}
        )

    async def offer_bribe(self, saboteur_id: str, target_player_id: str):
        """Offer a bribe to a miner to become a traitor"""
        if target_player_id not in self.players:
            raise Exception("Target player not found")
            
        target_player = self.players[target_player_id]
        
        if target_player['role'] != PlayerRole.MINER.value:
            raise Exception("Can only bribe miners")
            
        if self.saboteurs_stash < self.BRIBE_COST:
            raise Exception("Not enough gold in saboteurs stash for bribe")
            
        # Create bribe offer
        bribe_offer = {
            'saboteur_id': saboteur_id,
            'target_player_id': target_player_id,
            'amount': self.BRIBE_COST,
            'expires_at': datetime.now() + timedelta(seconds=30)  # Bribe offer expires in 30 seconds
        }
        
        self.bribe_offers[target_player_id] = bribe_offer
        self.saboteurs_stash -= self.BRIBE_COST
        
        # Update MongoDB
        sabotage_games.update_one(
            {'game_id': self.game_id},
            {'$set': {
                'saboteurs_stash': self.saboteurs_stash,
                'bribe_offers': self.bribe_offers
            }}
        )
        
        # Notify target player
        saboteur_name = self.players[saboteur_id]['name']
        print(f"DM to {target_player_id}: {saboteur_name} has offered you a bribe of {self.BRIBE_COST} gold to become a traitor!")

    async def respond_to_bribe(self, target_player_id: str, accept: bool):
        """Respond to a bribe offer"""
        if target_player_id not in self.bribe_offers:
            raise Exception("No active bribe offer for this player")
            
        bribe_offer = self.bribe_offers[target_player_id]
        
        if datetime.now() > bribe_offer['expires_at']:
            del self.bribe_offers[target_player_id]
            raise Exception("Bribe offer has expired")
            
        if accept:
            # Convert miner to traitor
            self.players[target_player_id]['role'] = PlayerRole.TRAITOR.value
            
            # Give the bribe gold to the traitor (this would be added to their personal GC balance)
            print(f"DM to {target_player_id}: You have accepted the bribe and are now a traitor!")
            
            # In a real implementation, you would update the player's GC balance here
            # For example: await add_gc_to_player(target_player_id, bribe_offer['amount'])
        else:
            # Return the gold to the saboteurs stash
            self.saboteurs_stash += bribe_offer['amount']
            print(f"DM to {target_player_id}: You have rejected the bribe.")
            
        # Remove the bribe offer
        del self.bribe_offers[target_player_id]
        
        # Update MongoDB
        sabotage_games.update_one(
            {'game_id': self.game_id},
            {'$set': {
                'saboteurs_stash': self.saboteurs_stash,
                'bribe_offers': self.bribe_offers,
                f'players.{target_player_id}': self.players[target_player_id]
            }}
        )

    async def end_game(self, saboteurs_win: bool = False, stalemate: bool = False):
        """End the game and distribute rewards"""
        self.state = GameState.GAME_END
        
        # Determine winners and distribute GC
        winners = []
        gc_rewards = {}
        
        if stalemate:
            # All players get equal share
            reward = 8000 // len(self.players)
            for player_id in self.players:
                gc_rewards[player_id] = reward
                winners.append(player_id)
        elif saboteurs_win:
            # Saboteurs and traitors win
            reward = 8000 // len([pid for pid, p in self.players.items() 
                                 if p['role'] in [PlayerRole.SABOTEUR.value, PlayerRole.TRAITOR.value]])
            for player_id, player in self.players.items():
                if player['role'] in [PlayerRole.SABOTEUR.value, PlayerRole.TRAITOR.value]:
                    gc_rewards[player_id] = reward
                    winners.append(player_id)
        else:
            # Miners win
            reward = 8000 // len([pid for pid, p in self.players.items() 
                                 if p['role'] == PlayerRole.MINER.value and p['is_alive']])
            for player_id, player in self.players.items():
                if player['role'] == PlayerRole.MINER.value and player['is_alive']:
                    gc_rewards[player_id] = reward
                    winners.append(player_id)
        
        # Update MongoDB with game results
        sabotage_games.update_one(
            {'game_id': self.game_id},
            {'$set': {
                'state': self.state.value,
                'winners': winners,
                'gc_rewards': gc_rewards,
                'ended_at': datetime.now()
            }}
        )
        
        # Distribute GC rewards (in a real implementation, this would call your GC distribution system)
        for player_id, gc_amount in gc_rewards.items():
            print(f"Awarding {gc_amount} GC to player {player_id}")
            # Update player's GC balance in MongoDB
            players_collection.update_one(
                {'player_id': player_id},
                {'$inc': {'game_coins': gc_amount}},
                upsert=True
            )
            
        # Notify all players of the outcome
        if stalemate:
            outcome_msg = "The game ended in a stalemate! All players receive an equal share of the reward."
        elif saboteurs_win:
            outcome_msg = "The saboteurs have won! They successfully stole more than half of the gold."
        else:
            outcome_msg = "The miners have won! They identified and ejected all saboteurs."
            
        print(f"Game ended: {outcome_msg}")
        
        # Clean up
        await self.cleanup()

    async def cleanup(self):
        """Clean up game resources"""
        # Remove game from active games list
        # This would depend on how you're managing active games
        pass

# Game manager to handle multiple games
class GameManager:
    def __init__(self):
        self.active_games: Dict[str, SabotageGame] = {}
        
    async def create_game(self, chat_id: str) -> str:
        """Create a new game and return its ID"""
        game_id = f"sabotage_{int(time.time())}_{random.randint(1000, 9999)}"
        game = SabotageGame(game_id, chat_id)
        self.active_games[game_id] = game
        return game_id
        
    def get_game(self, game_id: str) -> Optional[SabotageGame]:
        """Get a game by ID"""
        return self.active_games.get(game_id)
        
    async def end_all_games(self):
        """End all active games (for cleanup)"""
        for game in self.active_games.values():
            if game.state != GameState.GAME_END:
                await game.end_game(stalemate=True)

# Global game manager
game_manager = GameManager()