"""
Memory XXL Backend - 4-ESP Architecture
Switch-based system with tile registration

Architecture:
- 4 Tile ESPs, each managing 4 tiles (16 total)
- Tiles must be registered by stepping on them
- Master ESP coordinates via ESP-NOW
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import random

app = FastAPI(title="Memory XXL Backend - 4-ESP Architecture")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== STATE ====================
class TileEsp:
    def __init__(self, esp_id: int):
        self.esp_id = esp_id
        self.connected = False
        self.registered_tile_count = 0
        self.last_seen = None

class Tile:
    def __init__(self, tile_id: int, esp_id: int):
        self.id = tile_id
        self.esp_id = esp_id
        self.registered = False  # Has user stepped on it?
        self.battery = 100

class GameState:
    def __init__(self):
        self.master_ws: Optional[WebSocket] = None
        self.master_id: Optional[str] = None
        self.frontend_connections: List[WebSocket] = []
        
        # Initialize 4 Tile ESPs
        self.tile_esps: Dict[int, TileEsp] = {
            i: TileEsp(i) for i in range(1, 5)
        }
        
        # Initialize 16 tiles
        self.tiles: Dict[int, Tile] = {}
        for i in range(1, 17):
            esp_id = ((i - 1) // 4) + 1  # 1-4->ESP1, 5-8->ESP2, etc.
            self.tiles[i] = Tile(i, esp_id)
        
        # Game session
        self.pattern: List[int] = []
        self.player_progress = 0
        self.round_score = 0
        self.game_active = False
        self.start_time = None
        
        # Statistics
        self.games_played = 0
        self.high_score = 0

state = GameState()

# ==================== ROUTES ====================
@app.get("/")
async def root():
    """Health check"""
    connected_esps = sum(1 for esp in state.tile_esps.values() if esp.connected)
    registered_tiles = sum(1 for tile in state.tiles.values() if tile.registered)
    
    return {
        "status": "online",
        "version": "4-esp-architecture",
        "master_connected": state.master_id is not None,
        "frontends": len(state.frontend_connections),
        "tile_esps": {
            "connected": connected_esps,
            "total": 4
        },
        "tiles": {
            "registered": registered_tiles,
            "total": 16
        }
    }

@app.get("/api/stats")
async def get_stats():
    """Get game statistics"""
    connected_esps = sum(1 for esp in state.tile_esps.values() if esp.connected)
    registered_tiles = sum(1 for tile in state.tiles.values() if tile.registered)
    
    return {
        "games_played": state.games_played,
        "high_score": state.high_score,
        "tile_esps_connected": connected_esps,
        "tiles_registered": registered_tiles,
        "master_connected": state.master_id is not None,
        "architecture": "4-ESP"
    }

@app.get("/api/registration_status")
async def get_registration_status():
    """Get detailed registration status"""
    esp_status = []
    for esp_id, esp in state.tile_esps.items():
        tile_ids = [t.id for t in state.tiles.values() if t.esp_id == esp_id]
        registered = [t.id for t in state.tiles.values() if t.esp_id == esp_id and t.registered]
        
        esp_status.append({
            "esp_id": esp_id,
            "connected": esp.connected,
            "tiles": tile_ids,
            "registered_tiles": registered,
            "progress": f"{len(registered)}/4"
        })
    
    return {
        "tile_esps": esp_status,
        "total_registered": sum(1 for t in state.tiles.values() if t.registered),
        "total_tiles": 16
    }

# ==================== MASTER WEBSOCKET ====================
@app.websocket("/ws/master")
async def master_websocket(websocket: WebSocket):
    await websocket.accept()
    print("→ Master connected")
    
    try:
        # Wait for master identification
        data = await websocket.receive_json()
        
        if data.get("event") == "master_connected":
            state.master_ws = websocket
            state.master_id = data["data"]["master_id"]
            architecture = data["data"].get("architecture", "unknown")
            print(f"✓ Master registered: {state.master_id} ({architecture})")
            
            # Notify frontends
            await broadcast_to_frontends({
                "event": "master_status",
                "data": {
                    "connected": True,
                    "master_id": state.master_id,
                    "architecture": architecture
                }
            })
            
            # Main loop
            while True:
                msg = await websocket.receive_json()
                await handle_master_message(msg)
                
    except WebSocketDisconnect:
        print("✗ Master disconnected")
        state.master_ws = None
        state.master_id = None
        
        # Reset ESP and tile states
        for esp in state.tile_esps.values():
            esp.connected = False
        
        await broadcast_to_frontends({
            "event": "master_status",
            "data": {"connected": False}
        })
    except Exception as e:
        print(f"Master error: {e}")
        state.master_ws = None
        state.master_id = None

async def handle_master_message(msg: dict):
    """Handle messages from master ESP32"""
    event = msg.get("event")
    data = msg.get("data", {})
    
    print(f"← Master: {event}")
    
    if event == "system_status":
        # Update Tile ESP status
        for esp_info in data.get("tile_esps", []):
            esp_id = esp_info["id"]
            if esp_id in state.tile_esps:
                state.tile_esps[esp_id].connected = esp_info["connected"]
                state.tile_esps[esp_id].registered_tile_count = esp_info["registered_tiles"]
                state.tile_esps[esp_id].last_seen = datetime.now()
        
        # Update tile status
        for tile_info in data.get("tiles", []):
            tile_id = tile_info["id"]
            if tile_id in state.tiles:
                state.tiles[tile_id].registered = tile_info["registered"]
                state.tiles[tile_id].battery = tile_info.get("battery", 100)
        
        # Get summary
        summary = data.get("summary", {})
        
        # Broadcast to frontends
        await broadcast_to_frontends({
            "event": "system_status",
            "data": {
                "tile_esps": [
                    {
                        "id": esp.esp_id,
                        "connected": esp.connected,
                        "registered_tiles": esp.registered_tile_count
                    }
                    for esp in state.tile_esps.values()
                ],
                "tiles": [
                    {
                        "id": tile.id,
                        "esp_id": tile.esp_id,
                        "registered": tile.registered,
                        "battery": tile.battery
                    }
                    for tile in state.tiles.values()
                ],
                "summary": summary
            }
        })
    
    elif event == "start_button_pressed":
        print("→ START button pressed!")
        await start_new_game()
    
    elif event == "player_step":
        await handle_player_step(data)
    
    elif event == "pattern_shown":
        print("✓ Pattern displayed")
        await broadcast_to_frontends({
            "event": "pattern_complete",
            "data": {"message": "Watch and remember!"}
        })

# ==================== FRONTEND WEBSOCKET ====================
@app.websocket("/ws/frontend")
async def frontend_websocket(websocket: WebSocket):
    await websocket.accept()
    state.frontend_connections.append(websocket)
    print(f"→ Frontend connected (Total: {len(state.frontend_connections)})")
    
    # Send initial state
    await websocket.send_json({
        "event": "initial_state",
        "data": {
            "master_connected": state.master_id is not None,
            "tile_esps": [
                {
                    "id": esp.esp_id,
                    "connected": esp.connected,
                    "registered_tiles": esp.registered_tile_count
                }
                for esp in state.tile_esps.values()
            ],
            "tiles": [
                {
                    "id": tile.id,
                    "esp_id": tile.esp_id,
                    "registered": tile.registered,
                    "battery": tile.battery
                }
                for tile in state.tiles.values()
            ],
            "game_active": state.game_active,
            "games_played": state.games_played,
            "high_score": state.high_score,
            "architecture": "4-ESP"
        }
    })
    
    try:
        while True:
            msg = await websocket.receive_json()
            await handle_frontend_message(msg, websocket)
    except WebSocketDisconnect:
        state.frontend_connections.remove(websocket)
        print(f"✗ Frontend disconnected (Remaining: {len(state.frontend_connections)})")
    except Exception as e:
        print(f"Frontend error: {e}")
        if websocket in state.frontend_connections:
            state.frontend_connections.remove(websocket)

async def handle_frontend_message(msg: dict, websocket: WebSocket):
    """Handle messages from frontend"""
    event = msg.get("event")
    
    if event == "request_state":
        await websocket.send_json({
            "event": "state_update",
            "data": {
                "master_connected": state.master_id is not None,
                "game_active": state.game_active
            }
        })
    
    elif event == "start_game":
        await start_new_game()
    
    elif event == "reset_registration":
        await reset_registration()

async def reset_registration():
    """Reset all tile registrations"""
    if not state.master_ws:
        return
    
    print("→ Resetting all tile registrations")
    
    # Reset local state
    for tile in state.tiles.values():
        tile.registered = False
    
    for esp in state.tile_esps.values():
        esp.registered_tile_count = 0
    
    # Send command to master
    await state.master_ws.send_json({
        "event": "reset_registration",
        "data": {}
    })
    
    await broadcast_to_frontends({
        "event": "registration_reset",
        "data": {"message": "Registration reset. Please step on tiles again."}
    })

# ==================== GAME LOGIC ====================
async def start_new_game():
    """Start a new game session"""
    if not state.master_ws:
        print("✗ Cannot start - no master")
        return
    
    # Get registered tiles only
    registered_tiles = [tid for tid, tile in state.tiles.items() if tile.registered]
    
    if len(registered_tiles) < 2:
        print(f"✗ Need at least 2 registered tiles (have {len(registered_tiles)})")
        await broadcast_to_frontends({
            "event": "error",
            "data": {
                "message": f"Need at least 2 registered tiles. You have {len(registered_tiles)}/16 registered.",
                "registered_count": len(registered_tiles)
            }
        })
        return
    
    print(f"→ Starting game with {len(registered_tiles)} registered tiles")
    
    # Reset game state
    state.game_active = True
    state.player_progress = 0
    state.round_score = 0
    state.start_time = datetime.now()
    
    # Generate pattern (start with 3 tiles)
    pattern_length = min(3, len(registered_tiles))
    state.pattern = [random.choice(registered_tiles) for _ in range(pattern_length)]
    
    print(f"  Pattern: {state.pattern}")
    
    # Notify frontend
    await broadcast_to_frontends({
        "event": "game_started",
        "data": {
            "pattern_length": pattern_length,
            "registered_tiles": len(registered_tiles),
            "message": "Watch the pattern!"
        }
    })
    
    # Send pattern to master
    await state.master_ws.send_json({
        "event": "show_pattern",
        "data": {
            "pattern": state.pattern,
            "duration": 800
        }
    })
    
    # After pattern is shown, game starts
    await asyncio.sleep(pattern_length * 1.2 + 1)
    
    await broadcast_to_frontends({
        "event": "player_turn",
        "data": {
            "message": "Your turn! Step on the tiles in order",
            "pattern_length": len(state.pattern)
        }
    })

async def handle_player_step(data: dict):
    """Handle player stepping on a tile"""
    if not state.game_active:
        return
    
    tile_id = data["tile_id"]
    
    # Only process steps from registered tiles
    if tile_id not in state.tiles or not state.tiles[tile_id].registered:
        return
    
    expected = state.pattern[state.player_progress]
    
    print(f"  Step: {tile_id}, Expected: {expected}")
    
    if tile_id == expected:
        # Correct!
        state.player_progress += 1
        state.round_score += 10
        
        await broadcast_to_frontends({
            "event": "step_correct",
            "data": {
                "tile_id": tile_id,
                "progress": state.player_progress,
                "total": len(state.pattern),
                "score": state.round_score
            }
        })
        
        # Check if pattern complete
        if state.player_progress >= len(state.pattern):
            await round_complete()
    else:
        # Wrong!
        state.round_score = max(0, state.round_score - 15)
        
        await broadcast_to_frontends({
            "event": "step_incorrect",
            "data": {
                "tile_id": tile_id,
                "expected": expected,
                "score": state.round_score
            }
        })
        
        await end_game()

async def round_complete():
    """Player completed the pattern"""
    print("✓ Round complete!")
    
    await broadcast_to_frontends({
        "event": "round_complete",
        "data": {
            "score": state.round_score,
            "message": "Perfect! Next round..."
        }
    })
    
    await asyncio.sleep(2)
    
    # Start next round with longer pattern
    registered_tiles = [tid for tid, tile in state.tiles.items() if tile.registered]
    state.pattern = [random.choice(registered_tiles) for _ in range(len(state.pattern) + 1)]
    state.player_progress = 0
    
    print(f"  New pattern: {state.pattern}")
    
    # Show pattern
    await state.master_ws.send_json({
        "event": "show_pattern",
        "data": {"pattern": state.pattern}
    })
    
    await broadcast_to_frontends({
        "event": "new_round",
        "data": {
            "pattern_length": len(state.pattern),
            "message": "Watch carefully!"
        }
    })

async def end_game():
    """End the current game"""
    if not state.game_active:
        return
    
    state.game_active = False
    state.games_played += 1
    
    if state.round_score > state.high_score:
        state.high_score = state.round_score
    
    print(f"✓ Game ended - Score: {state.round_score}")
    
    # Turn off all tiles
    if state.master_ws:
        await state.master_ws.send_json({
            "event": "end_game",
            "data": {}
        })
    
    # Notify frontends
    await broadcast_to_frontends({
        "event": "game_ended",
        "data": {
            "score": state.round_score,
            "high_score": state.high_score,
            "games_played": state.games_played
        }
    })

# ==================== HELPERS ====================
async def broadcast_to_frontends(message: dict):
    """Send message to all connected frontends"""
    dead_connections = []
    for ws in state.frontend_connections:
        try:
            await ws.send_json(message)
        except:
            dead_connections.append(ws)
    
    for ws in dead_connections:
        if ws in state.frontend_connections:
            state.frontend_connections.remove(ws)

# ==================== STARTUP ====================
@app.on_event("startup")
async def startup():
    print("\n" + "="*60)
    print("Memory XXL Backend - 4-ESP Architecture")
    print("Switch-based with Tile Registration")
    print("="*60)
    print("\n✓ Server ready")
    print(f"  Master endpoint: ws://YOUR_IP:8000/ws/master")
    print(f"  Frontend endpoint: ws://YOUR_IP:8000/ws/frontend")
    print(f"  Health check: http://YOUR_IP:8000/")
    print("\nTile mapping:")
    print("  ESP #1: Tiles 1-4")
    print("  ESP #2: Tiles 5-8")
    print("  ESP #3: Tiles 9-12")
    print("  ESP #4: Tiles 13-16")
    print("\nWaiting for connections...\n")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
