import json
import logging
from websockets import WebSocketServerProtocol
from src.games.pool_game import PoolGame, PoolGameState
from src.utils.security import validate_telegram_hash
from config import config

logger = logging.getLogger(__name__)

class PoolWebSocketHandler:
    def __init__(self):
        self.pool_game = PoolGame()
        self.connections = {}  # user_id -> WebSocket
        self.user_sessions = {}  # websocket -> user_id

    async def handle_connection(self, websocket: WebSocketServerProtocol, path: str):
        try:
            # Authenticate user from query parameters
            user_id = await self.authenticate(websocket)
            if not user_id:
                await websocket.close()
                return

            self.connections[user_id] = websocket
            self.user_sessions[websocket] = user_id
            
            logger.info(f"User {user_id} connected to Pool WebSocket")

            async for message in websocket:
                await self.handle_message(user_id, message)
                
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
        finally:
            user_id = self.user_sessions.get(websocket)
            if user_id:
                if user_id in self.connections:
                    del self.connections[user_id]
                del self.user_sessions[websocket]
                logger.info(f"User {user_id} disconnected from Pool WebSocket")

    async def handle_message(self, user_id: str, message: str):
        try:
            data = json.loads(message)
            action = data.get('action')

            if action == 'create_game':
                bet_amount = data.get('bet_amount')
                if not bet_amount:
                    await self.send(user_id, {'error': 'Bet amount required'})
                    return
                
                result = self.pool_game.create_game(user_id, bet_amount)
                await self.send(user_id, result)

            elif action == 'join_game':
                game_id = data.get('game_id')
                if not game_id:
                    await self.send(user_id, {'error': 'Game ID required'})
                    return
                
                result = self.pool_game.join_game(user_id, game_id)
                await self.send(user_id, result)
                
                # Notify all players in the game about the new player
                if result.get('success'):
                    game_state = self.pool_game.get_game_state(game_id)
                    await self.broadcast_to_game(game_id, {
                        'action': 'player_joined',
                        'player_id': user_id,
                        'game_state': game_state
                    })

            elif action == 'start_game':
                game_id = data.get('game_id')
                if not game_id:
                    await self.send(user_id, {'error': 'Game ID required'})
                    return
                
                result = self.pool_game.start_game(game_id)
                await self.send(user_id, result)
                
                # Notify all players that the game has started
                if result.get('success'):
                    game_state = self.pool_game.get_game_state(game_id)
                    await self.broadcast_to_game(game_id, {
                        'action': 'game_started',
                        'game_state': game_state
                    })

            elif action == 'take_shot':
                shot_data = data.get('shot_data', {})
                result = self.pool_game.handle_action(user_id, 'take_shot', shot_data)
                await self.send(user_id, result)

                # Broadcast game state update to all players
                if 'success' in result or 'status' in result:
                    game_id = self.pool_game.player_games.get(user_id)
                    if game_id:
                        game_state = self.pool_game.get_game_state(game_id)
                        await self.broadcast_to_game(game_id, {
                            'action': 'game_state_update',
                            'game_state': game_state,
                            'shot_result': result.get('shot_result')
                        })

            elif action == 'forfeit':
                result = self.pool_game.handle_action(user_id, 'forfeit', {})
                await self.send(user_id, result)
                
                # Notify all players about the forfeit
                if 'status' in result:
                    game_id = self.pool_game.player_games.get(user_id)
                    if game_id:
                        await self.broadcast_to_game(game_id, {
                            'action': 'player_forfeited',
                            'player_id': user_id,
                            'winner': result.get('winner')
                        })

            elif action == 'get_game_state':
                game_id = data.get('game_id')
                if not game_id:
                    await self.send(user_id, {'error': 'Game ID required'})
                    return
                
                result = self.pool_game.get_game_state(game_id)
                await self.send(user_id, {'action': 'game_state', 'game_state': result})

            else:
                await self.send(user_id, {'error': 'Unknown action'})

        except json.JSONDecodeError:
            await self.send(user_id, {'error': 'Invalid JSON'})
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await self.send(user_id, {'error': 'Internal server error'})

    async def broadcast_to_game(self, game_id: str, message: dict):
        """Broadcast message to all players in a game"""
        try:
            game_state = self.pool_game.get_game_state(game_id)
            if 'error' in game_state:
                return
                
            for player_id in game_state.get('players', []):
                if player_id in self.connections:
                    try:
                        await self.connections[player_id].send(json.dumps(message))
                    except Exception as e:
                        logger.error(f"Error sending to player {player_id}: {e}")
        except Exception as e:
            logger.error(f"Error broadcasting to game {game_id}: {e}")

    async def send(self, user_id: str, message: dict):
        """Send message to a specific user"""
        if user_id in self.connections:
            try:
                await self.connections[user_id].send(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to user {user_id}: {e}")

    async def authenticate(self, websocket: WebSocketServerProtocol) -> str:
        """Authenticate user from WebSocket query parameters"""
        try:
            # Extract user_id and hash from query string
            query_string = websocket.path.split('?')[1] if '?' in websocket.path else ''
            params = dict(param.split('=') for param in query_string.split('&') if '=' in param)
            
            user_id = params.get('user_id')
            auth_hash = params.get('hash')
            
            if not user_id or not auth_hash:
                return None
                
            # Validate the authentication hash
            if validate_telegram_hash(user_id, auth_hash, config.TELEGRAM_TOKEN):
                return user_id
            else:
                return None
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None