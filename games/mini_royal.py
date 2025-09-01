import asyncio
import random
import math
import json
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

class GameState(Enum):
    WAITING = "waiting"
    COUNTDOWN = "countdown"
    ACTIVE = "active"
    ENDED = "ended"

class Player:
    def __init__(self, user_id: int, username: str, skin: str = None, weapon: str = None):
        self.user_id = user_id
        self.username = username
        self.skin = skin or "🧍"  # Default standing emoji
        self.weapon = weapon
        self.position = (random.uniform(0.2, 0.8), random.uniform(0.2, 0.8))
        self.direction = random.uniform(0, 2 * math.pi)
        self.speed = 0.005
        self.alive = True
        self.last_shot = 0
        self.shot_cooldown = 0.5
        self.kills = 0
        self.state = "idle"
        self.animation_frame = 0

class MiniRoyalGame:
    def __init__(self, game_id: str, max_players: int = 10, map_id: str = "classic"):
        self.game_id = game_id
        self.max_players = max_players
        self.players: Dict[int, Player] = {}
        self.state = GameState.WAITING
        self.start_time = None
        self.duration = 90
        self.circle_radius = 1.0
        self.circle_shrink_rate = 0.001
        self.circle_final_radius = 0.2
        self.bullets = []
        self.spectators = set()
        self.map_id = map_id
        self.animation_time = 0
        
        # Animation states
        self.animation_states = {
            "idle": ["🧍", "🧍", "🧍", "🧍", "🧍", "🧍", "🧍", "🧍"],
            "walking": ["🚶", "🚶", "🚶‍➡️", "🚶‍➡️", "🚶", "🚶", "🚶‍⬅️", "🚶‍⬅️"],
            "running": ["🏃", "🏃", "🏃‍➡️", "🏃‍➡️", "🏃", "🏃", "🏃‍⬅️", "🏃‍⬅️"],
            "shooting": ["🧍", "🧍", "🔫", "🔫", "🧍", "🧍", "🧍", "🧍"],
            "dead": ["💀", "💀", "💀", "💀", "💀", "💀", "💀", "💀"]
        }
        
        # Available skins
        self.skin_categories = {
            "basic": ["😎", "🤓", "🧐", "😤", "🤬", "😺", "😼", "😾", "🙉", "🫩", "🤕"],
            "advanced": ["🥷", "👮", "🧑‍✈️", "🫅", "🧛", "🎅", "🦹", "🦸", "🕵️"],
            "animal": ["🦍", "🐯", "🦁", "🐼", "🐨", "🦂", "🐵", "🐶", "🐱"],
            "legendary": ["👾", "🤖", "🦄", "🐲", "🦅", "🦸‍♂️", "🦸‍♀️", "🧙‍♂️", "🧙‍♀️"]
        }
        
        # Available weapons
        self.weapons = {
            "pistol": {"emoji": "🔫", "damage": 10, "cooldown": 0.5},
            "knife": {"emoji": "🔪", "damage": 15, "cooldown": 0.3},
            "bow": {"emoji": "🏹", "damage": 20, "cooldown": 0.7},
            "laser": {"emoji": "⚡", "damage": 25, "cooldown": 1.0}
        }
        
        # Map configurations
        self.maps = {
            "classic": {
                "name": "Classic Arena",
                "backgroundColor": "#000000",
                "safeZoneColor": "#00ff00",
                "dangerZoneColor": "rgba(255, 0, 0, 0.3)",
                "features": ["grid"]
            },
            "desert": {
                "name": "Desert Dunes",
                "backgroundColor": "#EDC9AF",
                "safeZoneColor": "#FFD700",
                "dangerZoneColor": "rgba(139, 69, 19, 0.4)",
                "features": ["dunes"]
            },
            "arctic": {
                "name": "Frozen Tundra",
                "backgroundColor": "#F0F8FF",
                "safeZoneColor": "#00BFFF",
                "dangerZoneColor": "rgba(176, 224, 230, 0.4)",
                "features": ["snowflakes", "ice_cracks"]
            }
        }
        
    def add_player(self, user_id: int, username: str, skin: str = None, weapon: str = None) -> bool:
        if len(self.players) >= self.max_players or self.state != GameState.WAITING:
            return False
            
        self.players[user_id] = Player(user_id, username, skin, weapon)
        return True
        
    def remove_player(self, user_id: int):
        if user_id in self.players:
            del self.players[user_id]
            
    def start_game(self):
        if len(self.players) < 2:
            return False
            
        self.state = GameState.COUNTDOWN
        self.start_time = datetime.now()
        return True
        
    async def game_loop(self):
        # Countdown
        for i in range(3, 0, -1):
            await self.broadcast({
                "type": "countdown", 
                "value": i,
                "map": self.maps[self.map_id]
            })
            await asyncio.sleep(1)
            
        self.state = GameState.ACTIVE
        start_time = datetime.now()
        self.animation_time = datetime.now().timestamp()
        
        # Main game loop
        while self.state == GameState.ACTIVE:
            current_time = datetime.now()
            elapsed = (current_time - start_time).total_seconds()
            remaining = self.duration - elapsed
            
            # Update animation time
            new_animation_time = current_time.timestamp()
            animation_delta = new_animation_time - self.animation_time
            self.animation_time = new_animation_time
            
            if remaining <= 0:
                self.state = GameState.ENDED
                break
                
            # Update safe zone
            shrink_progress = elapsed / self.duration
            self.circle_radius = self.circle_radius - (
                (self.circle_radius - self.circle_final_radius) * shrink_progress
            )
            
            # Update player positions and states
            for player in self.players.values():
                if not player.alive:
                    player.state = "dead"
                    continue
                    
                # Update animation frame
                player.animation_frame = (player.animation_frame + 1) % 8
                
                # Determine player state
                player.state = "idle"
                
                # Move player
                new_x = player.position[0] + math.cos(player.direction) * player.speed
                new_y = player.position[1] + math.sin(player.direction) * player.speed
                
                # Bounce off walls
                if new_x < 0 or new_x > 1:
                    player.direction = math.pi - player.direction
                    new_x = max(0, min(1, new_x))
                    player.state = "walking"
                if new_y < 0 or new_y > 1:
                    player.direction = -player.direction
                    new_y = max(0, min(1, new_y))
                    player.state = "walking"
                    
                player.position = (new_x, new_y)
                
                # Check if outside safe zone
                center = (0.5, 0.5)
                distance = math.sqrt((new_x - center[0])**2 + (new_y - center[1])**2)
                if distance > self.circle_radius:
                    # Take damage outside zone
                    player.alive = False
                    await self.broadcast({
                        "type": "player_eliminated", 
                        "user_id": player.user_id,
                        "reason": "zone"
                    })
            
            # Update bullets
            new_bullets = []
            for bullet in self.bullets:
                bullet_lifetime = 2.0
                if datetime.now().timestamp() - bullet["time"] < bullet_lifetime:
                    # Check for collisions
                    for player in self.players.values():
                        if (player.alive and player.user_id != bullet["shooter_id"] and
                            self.distance(bullet["position"], player.position) < 0.03):
                            player.alive = False
                            # Award kill to shooter
                            if bullet["shooter_id"] in self.players:
                                self.players[bullet["shooter_id"]].kills += 1
                            await self.broadcast({
                                "type": "player_eliminated", 
                                "user_id": player.user_id,
                                "reason": "shot",
                                "killer_id": bullet["shooter_id"]
                            })
                            break
                    else:
                        new_bullets.append(bullet)
            
            self.bullets = new_bullets
            
            # Check win condition
            alive_players = [p for p in self.players.values() if p.alive]
            if len(alive_players) <= 1:
                self.state = GameState.ENDED
                winner = alive_players[0] if alive_players else None
                await self.broadcast({
                    "type": "game_end",
                    "winner_id": winner.user_id if winner else None,
                    "players": {p.user_id: {
                        "kills": p.kills, 
                        "alive": p.alive,
                        "skin": p.skin,
                        "weapon": p.weapon
                    } for p in self.players.values()}
                })
                break
                
            # Send game state to all players
            await self.broadcast({
                "type": "game_state",
                "players": {user_id: {
                    "position": player.position,
                    "alive": player.alive,
                    "skin": player.skin,
                    "weapon": player.weapon,
                    "state": player.state,
                    "animation_frame": player.animation_frame,
                    "direction": player.direction
                } for user_id, player in self.players.items()},
                "bullets": [{
                    "position": b["position"],
                    "direction": b["direction"],
                    "shooter_id": b["shooter_id"]
                } for b in self.bullets],
                "circle_radius": self.circle_radius,
                "time_remaining": remaining,
                "map": self.maps[self.map_id],
                "animation_time": self.animation_time
            })
            
            await asyncio.sleep(0.05)
            
    async def broadcast(self, data):
        # Implementation depends on your WebSocket setup
        # This would send data to all connected clients
        pass
        
    def player_shoot(self, user_id: int, direction: float):
        if user_id not in self.players or not self.players[user_id].alive:
            return False
            
        player = self.players[user_id]
        current_time = datetime.now().timestamp()
        
        if current_time - player.last_shot < player.shot_cooldown:
            return False
            
        player.last_shot = current_time
        player.state = "shooting"
        
        self.bullets.append({
            "shooter_id": user_id,
            "position": player.position,
            "direction": direction,
            "time": current_time
        })
        
        return True
        
    def distance(self, pos1, pos2):
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
    
    def change_map(self, map_id: str):
        if map_id in self.maps:
            self.map_id = map_id
            return True
        return False