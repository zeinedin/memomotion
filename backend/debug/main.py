"""
Memory XXL Backend - TESTING VERSION
January 9, 2025

Simplified for demo day - focus on reliability
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

app = FastAPI(title="Memory XXL Backend")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== STATE ====================
class GameState:
    def __init__(self):
        self.master_ws: Optional[WebSocket] = None
        self.master_id: Optional[str] = None
        self.frontend_connections: List[WebSocket] = []
        
        self.tiles: Dict[int, dict] = {}  # tile_id -> {connected, battery}
        self.current_game: Optional[dict] = None
        self.games_played = 0
        self.high_score = 0
        
        # Game session
        self.pattern: List[int] = []
        self.player_progress = 0
        self.round_score = 0
        self.game_active = False
        self.start_time = None

state = GameState()

# ==================== ROUTES ====================
@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "online",
        "version": "testing-jan9",
        "master_connected": state.master_id is not None,
        "frontends": len(state.frontend_connections),
        "tiles": len(state.tiles)
    }

@app.get("/api/stats")
async def get_stats():
    """Get game statistics"""
    return {
        "games_played": state.games_played,
        "high_score": state.high_score,
        "tiles_connected": sum(1 for t in state.tiles.values() if t.get("connected")),
        "master_connected": state.master_id is not None
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
            print(f"✓ Master registered: {state.master_id}")
            
            # Notify frontends
            await broadcast_to_frontends({
                "event": "master_status",
                "data": {"connected": True, "master_id": state.master_id}
            })
            
            # Main loop
            while True:
                msg = await websocket.receive_json()
                await handle_master_message(msg)
                
    except WebSocketDisconnect:
        print("✗ Master disconnected")
        state.master_ws = None
        state.master_id = None
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
    
    if event == "tile_status":
        # Update tile status
        tiles = data.get("tiles", [])
        for tile in tiles:
            tile_id = tile["id"]
            state.tiles[tile_id] = {
                "connected": tile["connected"],
                "battery": tile.get("battery", 100)
            }
        
        # Broadcast to frontends
        await broadcast_to_frontends({
            "event": "tile_status",
            "data": {
                "tiles": state.tiles,
                "total": len(state.tiles),
                "connected": sum(1 for t in state.tiles.values() if t["connected"])
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
            "tiles": state.tiles,
            "game_active": state.game_active,
            "games_played": state.games_played,
            "high_score": state.high_score
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
        # Send current state
        await websocket.send_json({
            "event": "state_update",
            "data": {
                "master_connected": state.master_id is not None,
                "tiles": state.tiles,
                "game_active": state.game_active
            }
        })
    
    elif event == "start_game":
        await start_new_game()

# ==================== GAME LOGIC ====================
async def start_new_game():
    """Start a new game session"""
    if not state.master_ws:
        print("✗ Cannot start - no master")
        return
    
    connected_tiles = [tid for tid, info in state.tiles.items() if info["connected"]]
    if len(connected_tiles) < 2:
        print("✗ Need at least 2 tiles")
        await broadcast_to_frontends({
            "event": "error",
            "data": {"message": "Need at least 2 tiles connected"}
        })
        return
    
    print(f"→ Starting game with {len(connected_tiles)} tiles")
    
    # Reset game state
    state.game_active = True
    state.player_progress = 0
    state.round_score = 0
    state.start_time = datetime.now()
    
    # Generate pattern (start with 3 tiles)
    pattern_length = 3
    state.pattern = [random.choice(connected_tiles) for _ in range(pattern_length)]
    
    print(f"  Pattern: {state.pattern}")
    
    # Notify frontend
    await broadcast_to_frontends({
        "event": "game_started",
        "data": {
            "pattern_length": pattern_length,
            "message": "Watch the pattern!"
        }
    })
    
    # Send pattern to master
    await state.master_ws.send_json({
        "event": "show_pattern",
        "data": {
            "pattern": state.pattern,
            "duration": 800  # ms per tile
        }
    })
    
    # After pattern is shown, game starts
    await asyncio.sleep(pattern_length * 1.2 + 1)  # Wait for pattern + buffer
    
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
        
        # End game
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
    
    # Wait a bit
    await asyncio.sleep(2)
    
    # Start next round with longer pattern
    connected_tiles = [tid for tid, info in state.tiles.items() if info["connected"]]
    state.pattern = [random.choice(connected_tiles) for _ in range(len(state.pattern) + 1)]
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
    
    # Remove dead connections
    for ws in dead_connections:
        if ws in state.frontend_connections:
            state.frontend_connections.remove(ws)

# ==================== STARTUP ====================
@app.on_event("startup")
async def startup():
    print("\n" + "="*50)
    print("Memory XXL Backend - Testing Version")
    print("January 9, 2025")
    print("="*50)
    print("\n✓ Server ready")
    print(f"  Master endpoint: ws://YOUR_IP:8000/ws/master")
    print(f"  Frontend endpoint: ws://YOUR_IP:8000/ws/frontend")
    print(f"  Health check: http://YOUR_IP:8000/")
    print("\nWaiting for connections...\n")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
