import json
from typing import Dict
from src.telegram.miniapp import miniapp_bp
from games.mini_royal import MiniRoyalGame

# Global game manager
active_games: Dict[str, MiniRoyalGame] = {}

@miniapp_bp.websocket('/ws/mini-royal/<game_id>')
async def handle_mini_royal_ws(ws, game_id):
    user_id = ws.session.get('user_id')
    username = ws.session.get('username')
    
    if game_id not in active_games:
        await ws.send(json.dumps({"error": "Game not found"}))
        return
        
    game = active_games[game_id]
    
    # Add player to game if not already added
    if user_id not in game.players:
        if not game.add_player(user_id, username):
            await ws.send(json.dumps({"error": "Game full or already started"}))
            return
            
    try:
        async for message in ws:
            data = json.loads(message)
            
            if data['type'] == 'shoot':
                game.player_shoot(user_id, data['direction'])
            elif data['type'] == 'spectate':
                game.spectators.add(user_id)
                
    finally:
        game.remove_player(user_id)
        if user_id in game.spectators:
            game.spectators.remove(user_id)