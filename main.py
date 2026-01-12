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

app.mount("/static", StaticFiles(directory="static"), name="static")
# ==================== STATE ====================
class GameState:
    def __init__(self):
        self.master_ws: Optional[WebSocket] = None
        self.master_id: Optional[str] = None
        self.frontend_connections: List[WebSocket] = []
        
        self.tiles: Dict[int, dict] = {}  # tile_id -> {connected, battery}
        
        # Game states
        self.game_phase: str = "idle"  # idle, showing_pattern, memorizing, checking
        self.pattern: List[int] = []
        self.player_steps: List[int] = []
        
        self.games_played = 0
        self.high_score = 0
        self.current_score = 0
        self.start_time = None

state = GameState()

# ==================== ROUTES ====================
@app.get("/status")
async def root():
    """Health check"""
    return {
        "status": "online",
        "version": "testing-jan9",
        "master_connected": state.master_id is not None,
        "master_id": state.master_id,
        "frontends": len(state.frontend_connections),
        "tiles": len(state.tiles),
        "connected_tiles": sum(1 for t in state.tiles.values() if t.get("connected", False))
    }
@app.get('/')
async def read_index():
    return FileResponse('static/index.html')
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
        tiles_data = data.get("tiles", [])
        print(f"  Received {len(tiles_data)} tiles")
        
        for tile in tiles_data:
            tile_id = tile["id"]
            state.tiles[tile_id] = {
                "connected": tile["connected"],
                "battery": tile.get("battery", 100)
            }
            print(f"    Tile {tile_id}: {tile['connected']}")
        
        print(f"  Total tiles in state: {len(state.tiles)}")
        
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
        await handle_start_button()
    
    elif event == "player_step":
        await handle_player_step(data)
    
    elif event == "pattern_shown":
        print("✓ Pattern displayed on tiles")
        # Pattern is now showing - tell frontend
        await broadcast_to_frontends({
            "event": "pattern_displayed",
            "data": {
                "message": "Now memorize the pattern!",
                "pattern": state.pattern
            }
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
async def handle_start_button():
    """Handle START button press - two modes"""
    if not state.master_ws:
        print("✗ No master connected")
        return
    
    connected_tiles = [tid for tid, info in state.tiles.items() if info["connected"]]
    if len(connected_tiles) < 2:
        print("✗ Need at least 2 tiles")
        await broadcast_to_frontends({
            "event": "error",
            "data": {"message": "Need at least 2 connected tiles"}
        })
        return
    
    if state.game_phase == "idle":
        # First press: Show pattern
        await start_show_pattern(connected_tiles)
    
    elif state.game_phase == "memorizing":
        # Second press: Check pattern
        await check_pattern()

async def start_show_pattern(connected_tiles: List[int]):
    """Generate and show pattern"""
    print("→ Showing pattern...")
    
    state.game_phase = "showing_pattern"
    state.player_steps = []
    state.current_score = 0
    
    # Generate pattern (start with 4 tiles)
    pattern_length = 4
    state.pattern = [random.choice(connected_tiles) for _ in range(pattern_length)]
    
    print(f"  Pattern: {state.pattern}")
    
    # Tell frontend
    await broadcast_to_frontends({
        "event": "game_started",
        "data": {
            "phase": "showing_pattern",
            "pattern": state.pattern,
            "message": "Watch the pattern!"
        }
    })
    
    # Tell master to show pattern on tiles
    await state.master_ws.send_json({
        "event": "show_pattern",
        "data": {
            "pattern": state.pattern,
            "duration": 800
        }
    })
    
    # After pattern shown, enter memorizing phase
    await asyncio.sleep(pattern_length * 1.2 + 1)
    state.game_phase = "memorizing"
    
    await broadcast_to_frontends({
        "event": "memorizing_phase",
        "data": {
            "pattern": state.pattern,
            "message": "Now step on the tiles in order! Press START again when done."
        }
    })

async def handle_player_step(data: dict):
    """Player stepped on a tile"""
    tile_id = data["tile_id"]
    
    if state.game_phase != "memorizing":
        print(f"  Step ignored (wrong phase: {state.game_phase})")
        return
    
    print(f"  Player stepped: Tile {tile_id}")
    
    # Record step
    state.player_steps.append(tile_id)
    
    # Send to frontend to show
    await broadcast_to_frontends({
        "event": "player_stepped",
        "data": {
            "tile_id": tile_id,
            "step_number": len(state.player_steps),
            "steps_so_far": state.player_steps
        }
    })
    
    # Tell master to light up tile
    await state.master_ws.send_json({
        "event": "light_tile",
        "data": {
            "tile_id": tile_id,
            "on": True
        }
    })

async def check_pattern():
    """Check if player's pattern is correct"""
    print("→ Checking pattern...")
    state.game_phase = "checking"
    
    # Turn off all tiles
    await state.master_ws.send_json({
        "event": "end_game",
        "data": {}
    })
    
    # Check correctness
    correct = state.player_steps == state.pattern
    
    if correct:
        state.current_score = len(state.pattern) * 10
        if state.current_score > state.high_score:
            state.high_score = state.current_score
        
        print(f"✓ CORRECT! Score: {state.current_score}")
        
        await broadcast_to_frontends({
            "event": "pattern_correct",
            "data": {
                "message": "Perfect! You got it right! 🎉",
                "score": state.current_score,
                "pattern": state.pattern,
                "player_steps": state.player_steps
            }
        })
    else:
        print(f"✗ WRONG! Expected: {state.pattern}, Got: {state.player_steps}")
        
        await broadcast_to_frontends({
            "event": "pattern_wrong",
            "data": {
                "message": "Oops! That's not quite right.",
                "expected": state.pattern,
                "player_steps": state.player_steps,
                "score": 0
            }
        })
    
    # Update stats
    state.games_played += 1
    
    # Wait then reset
    await asyncio.sleep(3)
    state.game_phase = "idle"
    state.player_steps = []
    state.pattern = []
    
    await broadcast_to_frontends({
        "event": "game_ended",
        "data": {
            "score": state.current_score,
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