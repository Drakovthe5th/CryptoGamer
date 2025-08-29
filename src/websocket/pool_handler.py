import json
import asyncio
import uuid
from datetime import datetime
from websockets import WebSocketServerProtocol
from src.games.pool_game import PoolGame, PoolGameState
from src.database.game_db import save_pool_game_result
from src.integrations.telegram import deduct_stars, add_stars, get_user_stars_balance
from src.utils.logger import get_logger

logger = get_logger(__name__)

class PoolWebSocketHandler:
    def __init__(self):
        self.active_games = {}  # game_id -> PoolGame instance
        self.player_connections = {}  # player_id -> WebSocket
        self.game_players = {}  # game_id -> list of player_ids
        self.player_games = {}  # player_id -> game_id
        
    async def handle_connection(self, websocket: WebSocketServerProtocol, path: str):
        """Handle new WebSocket connection"""
        try:
            player_id = None
            async for message in websocket:
                data = json.loads(message)
                action = data.get('action')
                player_id = data.get('player_id')
                
                if player_id:
                    self.player_connections[player_id] = websocket
                
                if action == 'create_game':
                    await self.create_game(data, websocket)
                elif action == 'join_game':
                    await self.join_game(data, websocket)
                elif action == 'place_bet':
                    await self.place_bet(data, websocket)
                elif action == 'take_shot':
                    await self.take_shot(data, websocket)
                elif action == 'leave_game':
                    await self.leave_game(data, websocket)
                elif action == 'chat_message':
                    await self.chat_message(data, websocket)
                elif action == 'get_game_status':
                    await self.get_game_status(data, websocket)
                elif action == 'start_game':
                    await self.start_game(data, websocket)
                    
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            if player_id and player_id in self.player_connections:
                del self.player_connections[player_id]
                
    async def create_game(self, data, websocket):
        """Create a new pool game"""
        try:
            player_id = data.get('player_id')
            player_name = data.get('player_name')
            max_players = data.get('max_players', 2)
            game_type = data.get('game_type', '1v1')  # '1v1' or 'multiplayer'
            
            # Generate unique game ID
            game_id = str(uuid.uuid4())[:8]
            
            # Create new game instance
            game = PoolGame(game_id, max_players, game_type)
            success, message = game.add_player(player_id, player_name)
            
            if not success:
                await self.send_error(websocket, message)
                return
                
            # Store game and player references
            self.active_games[game_id] = game
            self.game_players[game_id] = [player_id]
            self.player_games[player_id] = game_id
            
            # Send success response
            await self.send_message(websocket, {
                'action': 'game_created',
                'game_id': game_id,
                'message': f'Game created with ID: {game_id}'
            })
            
            logger.info(f"Game {game_id} created by player {player_id}")
            
        except Exception as e:
            logger.error(f"Error creating game: {e}")
            await self.send_error(websocket, "Failed to create game")
            
    async def join_game(self, data, websocket):
        """Join an existing pool game"""
        try:
            game_id = data.get('game_id')
            player_id = data.get('player_id')
            player_name = data.get('player_name')
            
            if game_id not in self.active_games:
                await self.send_error(websocket, "Game not found")
                return
                
            game = self.active_games[game_id]
            
            # Check if game is full
            if len(game.players) >= game.max_players:
                await self.send_error(websocket, "Game is full")
                return
                
            # Add player to game
            success, message = game.add_player(player_id, player_name)
            if not success:
                await self.send_error(websocket, message)
                return
                
            # Update references
            self.game_players[game_id].append(player_id)
            self.player_games[player_id] = game_id
            
            # Notify all players in the game
            await self.broadcast_to_game(game_id, {
                'action': 'player_joined',
                'player_id': player_id,
                'player_name': player_name,
                'players_count': len(game.players),
                'players': [{'id': p['id'], 'name': p['name']} for p in game.players]
            })
            
            # If game is full, automatically start betting phase
            if len(game.players) == game.max_players:
                game.state = PoolGameState.WAITING_FOR_BETS
                await self.broadcast_to_game(game_id, {
                    'action': 'betting_started',
                    'message': 'All players joined. Place your bets.'
                })
                
            logger.info(f"Player {player_id} joined game {game_id}")
            
        except Exception as e:
            logger.error(f"Error joining game: {e}")
            await self.send_error(websocket, "Failed to join game")
            
    async def place_bet(self, data, websocket):
        """Handle player placing a bet"""
        try:
            game_id = data.get('game_id')
            player_id = data.get('player_id')
            amount = data.get('amount')
            
            if game_id not in self.active_games:
                await self.send_error(websocket, "Game not found")
                return
                
            game = self.active_games[game_id]
            
            # Validate bet amount
            if amount <= 0:
                await self.send_error(websocket, "Bet amount must be positive")
                return
                
            # Check player balance
            balance = get_user_stars_balance(player_id)
            if balance < amount:
                await self.send_error(websocket, "Insufficient stars balance")
                return
                
            # Place the bet
            success, message = game.place_bet(player_id, amount)
            
            if success:
                # Broadcast bet placement to all players
                await self.broadcast_to_game(game_id, {
                    'action': 'bet_placed',
                    'player_id': player_id,
                    'amount': amount,
                    'pot': game.pot,
                    'message': message
                })
                
                # If all bets are placed and equal, start the game
                if game.state == PoolGameState.IN_PROGRESS:
                    await self.broadcast_to_game(game_id, {
                        'action': 'game_started',
                        'pot': game.pot,
                        'current_player': game.current_player_index,
                        'message': 'Game started!'
                    })
            else:
                await self.send_error(websocket, message)
                
        except Exception as e:
            logger.error(f"Error placing bet: {e}")
            await self.send_error(websocket, "Failed to place bet")
            
    async def take_shot(self, data, websocket):
        """Handle player taking a shot"""
        try:
            game_id = data.get('game_id')
            player_id = data.get('player_id')
            angle = data.get('angle')
            power = data.get('power')
            
            if game_id not in self.active_games:
                await self.send_error(websocket, "Game not found")
                return
                
            game = self.active_games[game_id]
            
            # Check if it's the player's turn
            current_player = game.players[game.current_player_index]
            if current_player['id'] != player_id:
                await self.send_error(websocket, "Not your turn")
                return
                
            # Process the shot
            success, result = game.take_shot(angle, power)
            
            if success:
                # Broadcast shot result to all players
                await self.broadcast_to_game(game_id, {
                    'action': 'shot_taken',
                    'player_id': player_id,
                    'angle': angle,
                    'power': power,
                    'result': result,
                    'next_player': game.current_player_index
                })
                
                # Check if game is over
                if game.state == PoolGameState.COMPLETED:
                    await self.broadcast_to_game(game_id, {
                        'action': 'game_ended',
                        'winner': game.winner,
                        'pot': game.pot,
                        'message': f"Game over! Winner: {game.winner}"
                    })
                    
                    # Save game result to database
                    save_pool_game_result({
                        'game_id': game_id,
                        'players': game.players,
                        'bet_amount': game.agreed_bet_amount,
                        'pot': game.pot,
                        'winner': game.winner,
                        'start_time': game.start_time,
                        'end_time': game.end_time
                    })
                    
                    # Clean up game
                    self.cleanup_game(game_id)
            else:
                await self.send_error(websocket, "Invalid shot")
                
        except Exception as e:
            logger.error(f"Error taking shot: {e}")
            await self.send_error(websocket, "Failed to process shot")
            
    async def leave_game(self, data, websocket):
        """Handle player leaving the game"""
        try:
            game_id = data.get('game_id')
            player_id = data.get('player_id')
            
            if game_id not in self.active_games:
                await self.send_error(websocket, "Game not found")
                return
                
            game = self.active_games[game_id]
            
            # Refund player's bet if they placed one
            if player_id in game.bets:
                amount = game.bets[player_id]
                add_stars(player_id, amount)
                game.pot -= amount
                del game.bets[player_id]
                
            # Remove player from game
            game.players = [p for p in game.players if p['id'] != player_id]
            
            # Notify other players
            await self.broadcast_to_game(game_id, {
                'action': 'player_left',
                'player_id': player_id,
                'players_count': len(game.players),
                'players': [{'id': p['id'], 'name': p['name']} for p in game.players]
            })
            
            # If no players left, cleanup game
            if len(game.players) == 0:
                self.cleanup_game(game_id)
            else:
                # Update references
                if player_id in self.game_players.get(game_id, []):
                    self.game_players[game_id].remove(player_id)
                if player_id in self.player_games:
                    del self.player_games[player_id]
                    
        except Exception as e:
            logger.error(f"Error leaving game: {e}")
            await self.send_error(websocket, "Failed to leave game")
            
    async def chat_message(self, data, websocket):
        """Handle chat messages"""
        try:
            game_id = data.get('game_id')
            player_id = data.get('player_id')
            message = data.get('message')
            
            if game_id not in self.active_games:
                await self.send_error(websocket, "Game not found")
                return
                
            # Broadcast chat message to all players
            await self.broadcast_to_game(game_id, {
                'action': 'chat_message',
                'player_id': player_id,
                'message': message,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error handling chat message: {e}")
            await self.send_error(websocket, "Failed to send message")
            
    async def get_game_status(self, data, websocket):
        """Send current game status to player"""
        try:
            game_id = data.get('game_id')
            
            if game_id not in self.active_games:
                await self.send_error(websocket, "Game not found")
                return
                
            game = self.active_games[game_id]
            status = game.get_game_status()
            
            await self.send_message(websocket, {
                'action': 'game_status',
                'status': status
            })
            
        except Exception as e:
            logger.error(f"Error getting game status: {e}")
            await self.send_error(websocket, "Failed to get game status")
            
    async def start_game(self, data, websocket):
        """Manually start the game if all players have joined"""
        try:
            game_id = data.get('game_id')
            player_id = data.get('player_id')
            
            if game_id not in self.active_games:
                await self.send_error(websocket, "Game not found")
                return
                
            game = self.active_games[game_id]
            
            # Check if player is the game creator
            if game.players[0]['id'] != player_id:
                await self.send_error(websocket, "Only game creator can start the game")
                return
                
            # Start betting phase
            game.state = PoolGameState.WAITING_FOR_BETS
            
            await self.broadcast_to_game(game_id, {
                'action': 'betting_started',
                'message': 'Place your bets.'
            })
            
        except Exception as e:
            logger.error(f"Error starting game: {e}")
            await self.send_error(websocket, "Failed to start game")
            
    async def broadcast_to_game(self, game_id, message):
        """Broadcast message to all players in a game"""
        if game_id not in self.game_players:
            return
            
        for player_id in self.game_players[game_id]:
            if player_id in self.player_connections:
                try:
                    await self.send_message(self.player_connections[player_id], message)
                except Exception as e:
                    logger.error(f"Error broadcasting to player {player_id}: {e}")
                    
    async def send_message(self, websocket, message):
        """Send a message to a WebSocket client"""
        try:
            await websocket.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            
    async def send_error(self, websocket, error_message):
        """Send an error message to a WebSocket client"""
        try:
            await self.send_message(websocket, {
                'action': 'error',
                'message': error_message
            })
        except Exception as e:
            logger.error(f"Error sending error message: {e}")
            
    def cleanup_game(self, game_id):
        """Clean up game resources"""
        if game_id in self.active_games:
            # Refund all bets if game didn't complete
            game = self.active_games[game_id]
            if game.state != PoolGameState.COMPLETED:
                for player_id, amount in game.bets.items():
                    add_stars(player_id, amount)
                    
            # Remove all references
            if game_id in self.game_players:
                for player_id in self.game_players[game_id]:
                    if player_id in self.player_games:
                        del self.player_games[player_id]
                del self.game_players[game_id]
                
            del self.active_games[game_id]
            
            logger.info(f"Game {game_id} cleaned up")