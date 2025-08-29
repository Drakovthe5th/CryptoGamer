# Add to existing WebSocket handler or create new poker_websocket.py
@socketio.on('poker_action')
def handle_poker_action(data):
    user_id = validate_websocket_user(request)
    if not user_id:
        return
    
    game = GAME_REGISTRY.get('poker')
    if not game:
        emit('error', {'message': 'Game not found'})
        return
        
    action = data.get('action')
    table_id = data.get('table_id')
    
    result = game.handle_action(user_id, action, data)
    if 'error' in result:
        emit('error', result)
    else:
        # Broadcast updated table state to all players
        table_state = game.get_table_state(table_id)
        emit('table_update', table_state, room=table_id, broadcast=True)