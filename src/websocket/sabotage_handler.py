import asyncio
import json
from src.database.mongo import get_sabotage_game, update_sabotage_game
from src.features.mining.token_distribution import calculate_sabotage_reward

class SabotageWebSocketHandler:
    def __init__(self):
        self.active_games = {}
        self.entry_fee = 100  # Crew Credits required to join a game
    
    async def handle_connection(self, websocket, path):
        try:
            async for message in websocket:
                data = json.loads(message)
                await self.handle_message(websocket, data)
        except Exception as e:
            print(f"WebSocket error: {str(e)}")
    
    async def handle_message(self, websocket, data):
        message_type = data.get('type')
        game_id = data.get('game_id')
        user_id = data.get('user_id')
        
        if message_type == 'join':
            await self.handle_join(websocket, game_id, user_id)
        elif message_type == 'action':
            await self.handle_action(game_id, user_id, data.get('action'), data.get('data'))
        elif message_type == 'vote':
            await self.handle_vote(game_id, user_id, data.get('vote_for'))
    
    async def handle_join(self, websocket, game_id, user_id):
        # Add player to game
        if game_id not in self.active_games:
            game_data = get_sabotage_game(game_id)
            if game_data:
                self.active_games[game_id] = {
                    'game': SabotageGame(game_id, game_data['chat_id']),
                    'connections': {}
                }
        
        if game_id in self.active_games:
            self.active_games[game_id]['connections'][user_id] = websocket
            # Send current game state to player
            await websocket.send(json.dumps({
                'type': 'game_state',
                'game_data': self.active_games[game_id]['game'].to_dict()
            }))
    
    async def handle_action(self, game_id, user_id, action, action_data):
        if game_id in self.active_games:
            game = self.active_games[game_id]['game']
            await game.player_action(user_id, action, **action_data)
            
            # Broadcast update to all players
            await self.broadcast_game_state(game_id)
    
    async def handle_vote(self, game_id, user_id, vote_for):
        if game_id in self.active_games:
            game = self.active_games[game_id]['game']
            await game.vote(user_id, vote_for)
            
            # Broadcast vote update
            await self.broadcast_to_game(game_id, {
                'type': 'vote_update',
                'votes': game.votes
            })
    
    async def broadcast_game_state(self, game_id):
        if game_id in self.active_games:
            game_data = self.active_games[game_id]['game'].to_dict()
            await self.broadcast_to_game(game_id, {
                'type': 'game_update',
                'game_data': game_data
            })
    
    async def broadcast_to_game(self, game_id, message):
        if game_id in self.active_games:
            for user_id, websocket in self.active_games[game_id]['connections'].items():
                try:
                    await websocket.send(json.dumps(message))
                except Exception as e:
                    print(f"Error sending to {user_id}: {str(e)}")

    async def add_player(self, player_id: str, player_name: str):
        """Add a player to the game lobby after deducting entry fee"""
        # Check if player has enough Crew Credits
        user_data = get_user_data(player_id)
        if user_data.get('crew_credits', 0) < self.entry_fee:
            raise Exception(f"Not enough Crew Credits. Need {self.entry_fee} to join.")
            
        # Deduct entry fee
        update_user_data(player_id, {
            'crew_credits': user_data.get('crew_credits', 0) - self.entry_fee
        })
        
        # Then add player to game
        self.players[player_id] = {
            'id': player_id,
            'name': player_name,
            'role': None,
            'is_alive': True,
            'last_action_time': None,
            'gold_mined': 0,
            'gold_stolen': 0
        }
        
        # Update MongoDB
        sabotage_games.update_one(
            {'game_id': self.game_id},
            {'$set': {f'players.{player_id}': self.players[player_id]}}
        )