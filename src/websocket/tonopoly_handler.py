import json
import asyncio
import websockets
from typing import Dict
from games.tonopoly_game import TONopolyGame, PlayerColor
from src.features.monetization.purchases import create_bet_invoice, process_bet_payment

class TONopolyWebSocketHandler:
    def __init__(self):
        self.active_games: Dict[str, TONopolyGame] = {}
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        
    async def handle_connection(self, websocket, path):
        try:
            # Extract game_id and user_id from path
            path_parts = path.split('/')
            game_id = path_parts[2] if len(path_parts) > 2 else None
            user_id = path_parts[3] if len(path_parts) > 3 else None
            
            if not game_id or not user_id:
                await websocket.close(code=4000, reason="Invalid connection path")
                return
                
            self.connections[f"{game_id}_{user_id}"] = websocket
            
            async for message in websocket:
                data = json.loads(message)
                await self.process_message(websocket, game_id, user_id, data)
                
        except websockets.exceptions.ConnectionClosed:
            await self.handle_disconnection(game_id, user_id)
        except Exception as e:
            print(f"Error in WebSocket handler: {e}")
            await websocket.close(code=4001, reason=str(e))
            
    async def process_message(self, websocket, game_id, user_id, data):
        message_type = data.get('type')
        
        if message_type == 'join':
            await self.handle_join(websocket, game_id, user_id, data)
        elif message_type == 'set_bet':
            await self.handle_set_bet(game_id, user_id, data)
        elif message_type == 'roll_dice':
            await self.handle_roll_dice(game_id, user_id)
        elif message_type == 'move_piece':
            await self.handle_move_piece(game_id, user_id, data)
        elif message_type == 'stake_coins':
            await self.handle_stake_coins(game_id, user_id, data)
        else:
            await websocket.send(json.dumps({
                'type': 'error',
                'message': f'Unknown message type: {message_type}'
            }))
            
    async def handle_join(self, websocket, game_id, user_id, data):
        username = data.get('username')
        color_str = data.get('color')
        
        if game_id not in self.active_games:
            # Create new game
            self.active_games[game_id] = TONopolyGame(game_id, user_id)
            
        game = self.active_games[game_id]
        
        # Convert color string to enum
        color = None
        if color_str:
            try:
                color = PlayerColor(color_str)
            except ValueError:
                color = None
                
        await game.join_game(user_id, username, color)
        
        # Send game state to the new player
        await websocket.send(json.dumps({
            'type': 'game_state',
            'game_state': game.get_state()
        }))
        
        # Notify all players about the new player
        await self.broadcast(game_id, {
            'type': 'player_joined',
            'user_id': user_id,
            'username': username,
            'color': color.value if color else None
        })
        
    async def handle_set_bet(self, game_id, user_id, data):
        if game_id not in self.active_games:
            await self.send_error(user_id, "Game not found")
            return
            
        game = self.active_games[game_id]
        amount = data.get('amount')
        
        try:
            await game.set_bet(user_id, amount)
            
            # Create bet invoices for all players
            for player_id in game.players:
                if player_id != user_id:  # Creator doesn't need to pay themselves
                    invoice_url = await create_bet_invoice(player_id, amount, game_id)
                    await self.send_to_player(game_id, player_id, {
                        'type': 'bet_invoice',
                        'invoice_url': invoice_url,
                        'amount': amount
                    })
                    
            await self.broadcast(game_id, {
                'type': 'bet_set',
                'amount': amount,
                'set_by': user_id
            })
            
        except Exception as e:
            await self.send_error(user_id, str(e))
            
    async def handle_roll_dice(self, game_id, user_id):
        if game_id not in self.active_games:
            await self.send_error(user_id, "Game not found")
            return
            
        game = self.active_games[game_id]
        
        try:
            dice_value = await game.roll_dice(user_id)
            await self.broadcast(game_id, {
                'type': 'dice_rolled',
                'user_id': user_id,
                'dice_value': dice_value
            })
        except Exception as e:
            await self.send_error(user_id, str(e))
            
    async def handle_move_piece(self, game_id, user_id, data):
        if game_id not in self.active_games:
            await self.send_error(user_id, "Game not found")
            return
            
        game = self.active_games[game_id]
        piece_index = data.get('piece_index')
        
        try:
            success, message = await game.move_piece(user_id, piece_index)
            if success:
                await self.broadcast(game_id, {
                    'type': 'piece_moved',
                    'user_id': user_id,
                    'piece_index': piece_index,
                    'message': message,
                    'game_state': game.get_state()
                })
                
                if game.state == TONopolyGameState.FINISHED:
                    # Game over, distribute winnings
                    await self.broadcast(game_id, {
                        'type': 'game_over',
                        'winner': game.winner,
                        'winnings': game.players[game.winner].winnings if hasattr(game.players[game.winner], 'winnings') else 0
                    })
            else:
                await self.send_error(user_id, message)
                
        except Exception as e:
            await self.send_error(user_id, str(e))
            
    async def handle_stake_coins(self, game_id, user_id, data):
        if game_id not in self.active_games:
            await self.send_error(user_id, "Game not found")
            return
            
        game = self.active_games[game_id]
        amount = data.get('amount')
        
        try:
            success = await game.stake_coins(user_id, amount)
            if success:
                await self.broadcast(game_id, {
                    'type': 'coins_staked',
                    'user_id': user_id,
                    'amount': amount,
                    'game_state': game.get_state()
                })
        except Exception as e:
            await self.send_error(user_id, str(e))
            
    async def handle_disconnection(self, game_id, user_id):
        connection_key = f"{game_id}_{user_id}"
        if connection_key in self.connections:
            del self.connections[connection_key]
            
        # Notify other players about disconnection
        await self.broadcast(game_id, {
            'type': 'player_left',
            'user_id': user_id
        })
        
    async def broadcast(self, game_id, message):
        """Send message to all players in a game"""
        for user_id in self.active_games[game_id].players:
            await self.send_to_player(game_id, user_id, message)
            
    async def send_to_player(self, game_id, user_id, message):
        """Send message to a specific player"""
        connection_key = f"{game_id}_{user_id}"
        if connection_key in self.connections:
            try:
                await self.connections[connection_key].send(json.dumps(message))
            except:
                # Connection might be closed
                pass
                
    async def send_error(self, user_id, message):
        """Send error message to a player"""
        # This would need to know the game_id, which we might not have here
        # Implementation would depend on how we're managing connections
        pass

# Global instance
tonopoly_handler = TONopolyWebSocketHandler()