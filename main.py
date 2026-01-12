"""
Memory XXL Backend - TESTING VERSION
January 12, 2025

Features:
- Team registration with levels
- Leaderboard with SQLite database
- Visual tile pattern display
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import random
import sqlite3
import os

app = FastAPI(title="Memory XXL Backend")

# ==================== DATABASE ====================
DB_PATH = "leaderboard.db"

def init_database():
    """Initialize SQLite database for leaderboard"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leaderboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_name TEXT NOT NULL,
            score INTEGER NOT NULL,
            level TEXT NOT NULL,
            rounds INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("✓ Database initialized")

# Initialize database on startup
init_database()

# ==================== MODELS ====================
class ScoreEntry(BaseModel):
    team_name: str
    score: int
    level: str
    rounds: int = 0



# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/assets", StaticFiles(directory="static"), name="static")


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
        
        # Team info
        self.current_team: str = ""
        self.current_level: str = "easy"
        
        self.games_played = 0
        self.high_score = 0
        self.current_score = 0
        self.round_number = 0
        self.start_time = None

# Level configurations
LEVEL_CONFIG = {
    "easy": {"pattern_length": 4, "points_per_tile": 10},
    "medium": {"pattern_length": 6, "points_per_tile": 15},
    "hard": {"pattern_length": 8, "points_per_tile": 25}
}

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

@app.get("/app.js")
async def read_js():
    return FileResponse('static/app.js')

@app.get("/style.css")
async def read_css():
    return FileResponse('static/style.css')

@app.get("/api/stats")
async def get_stats():
    """Get game statistics"""
    return {
        "games_played": state.games_played,
        "high_score": state.high_score,
        "tiles_connected": sum(1 for t in state.tiles.values() if t.get("connected")),
        "master_connected": state.master_id is not None
    }

# ==================== LEADERBOARD API ====================
@app.get("/api/leaderboard")
async def get_leaderboard(limit: int = 10):
    """Get leaderboard entries"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT team_name, score, level, rounds, created_at 
        FROM leaderboard 
        ORDER BY score DESC 
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    leaderboard = [
        {
            "team_name": row[0],
            "score": row[1],
            "level": row[2],
            "rounds": row[3],
            "created_at": row[4]
        }
        for row in rows
    ]
    
    return {"leaderboard": leaderboard}

@app.post("/api/leaderboard")
async def add_score(entry: ScoreEntry):
    """Add a new score to leaderboard"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO leaderboard (team_name, score, level, rounds)
        VALUES (?, ?, ?, ?)
    ''', (entry.team_name, entry.score, entry.level, entry.rounds))
    conn.commit()
    conn.close()
    
    print(f"✓ Score saved: {entry.team_name} - {entry.score} ({entry.level})")
    
    return {"status": "ok", "message": "Score saved"}

@app.delete("/api/leaderboard")
async def clear_leaderboard():
    """Clear all leaderboard entries (admin)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM leaderboard')
    conn.commit()
    conn.close()
    
    return {"status": "ok", "message": "Leaderboard cleared"}

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
    data = msg.get("data", {})
    
    if event == "request_state":
        # Send current state
        await websocket.send_json({
            "event": "state_update",
            "data": {
                "master_connected": state.master_id is not None,
                "tiles": state.tiles,
                "game_phase": state.game_phase
            }
        })
    
    elif event == "start_game":
        # Register team and level
        state.current_team = data.get("team_name", "Team")
        state.current_level = data.get("level", "easy")
        state.current_score = 0
        state.round_number = 0
        print(f"→ New game: {state.current_team} ({state.current_level})")

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
    state.round_number += 1
    
    # Get pattern length from level config
    level_config = LEVEL_CONFIG.get(state.current_level, LEVEL_CONFIG["easy"])
    pattern_length = min(level_config["pattern_length"], len(connected_tiles))
    
    # Generate pattern (unique tiles)
    state.pattern = random.sample(connected_tiles, pattern_length)
    
    print(f"  Pattern: {state.pattern} (Level: {state.current_level})")
    
    # Tell frontend
    await broadcast_to_frontends({
        "event": "game_started",
        "data": {
            "phase": "showing_pattern",
            "pattern": state.pattern,
            "message": "Kijk naar het patroon!",
            "round": state.round_number
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
            "message": "Stap op de tegels in de juiste volgorde!"
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
    
    # Get points from level config
    level_config = LEVEL_CONFIG.get(state.current_level, LEVEL_CONFIG["easy"])
    
    if correct:
        points = len(state.pattern) * level_config["points_per_tile"]
        state.current_score += points
        if state.current_score > state.high_score:
            state.high_score = state.current_score
        
        print(f"✓ CORRECT! Score: {state.current_score}")
        
        await broadcast_to_frontends({
            "event": "pattern_correct",
            "data": {
                "message": "🎉 Perfect!",
                "score": state.current_score,
                "points_earned": points,
                "pattern": state.pattern,
                "player_steps": state.player_steps
            }
        })
    else:
        print(f"✗ WRONG! Expected: {state.pattern}, Got: {state.player_steps}")
        
        await broadcast_to_frontends({
            "event": "pattern_wrong",
            "data": {
                "message": "❌ Fout! Game Over",
                "expected": state.pattern,
                "player_steps": state.player_steps,
                "score": state.current_score
            }
        })
    
    # Update stats
    state.games_played += 1
    
    # Wait then reset or continue
    await asyncio.sleep(3)
    
    if correct:
        # Continue to next round
        connected_tiles = [tid for tid, info in state.tiles.items() if info["connected"]]
        state.game_phase = "idle"
        state.player_steps = []
        state.pattern = []
        # Don't auto-start, wait for START button
    else:
        # Game over
        state.game_phase = "idle"
        state.player_steps = []
        state.pattern = []
        
        await broadcast_to_frontends({
            "event": "game_ended",
            "data": {
                "score": state.current_score,
                "high_score": state.high_score,
                "games_played": state.games_played,
                "rounds": state.round_number
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
    print("Memory XXL Backend - v2.0")
    print("January 12, 2025")
    print("="*50)
    print("\n✓ Server ready")
    print("✓ Database ready")
    print(f"  Master endpoint: ws://YOUR_IP:8000/ws/master")
    print(f"  Frontend endpoint: ws://YOUR_IP:8000/ws/frontend")
    print(f"  Leaderboard API: http://YOUR_IP:8000/api/leaderboard")
    print(f"  Health check: http://YOUR_IP:8000/")
    print("\nWaiting for connections...\n")
    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)