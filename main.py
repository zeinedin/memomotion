"""
Memory XXL Backend - ROBUST VERSION
Production-ready with proper state machine and error handling
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
import json
import asyncio
from datetime import datetime
import random
import os
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(title="Memory XXL Backend - Robust")

# ==================== ENUMS & CONSTANTS ====================
class GamePhase(str, Enum):
    IDLE = "idle"
    REGISTERED = "registered"  # Team registered, waiting for start
    SHOWING_PATTERN = "showing_pattern"
    SELECTING = "selecting"
    VALIDATING = "validating"
    ROUND_COMPLETE = "round_complete"
    GAME_OVER = "game_over"

class GameMode(str, Enum):
    CLASSIC = "classic"
    SPEEDRUN = "speedrun"
    ENDLESS = "endless"
    SIMON = "simon"

# Level configurations
LEVEL_CONFIG = {
    "easy": {"base_pattern": 3, "multiplier": 1, "base_points": 20, "show_time": 5},
    "medium": {"base_pattern": 4, "multiplier": 2, "base_points": 30, "show_time": 6},
    "hard": {"base_pattern": 5, "multiplier": 3, "base_points": 50, "show_time": 8}
}

WRONG_PENALTY = 15
TOTAL_TILES = 12  # Expected total tiles
STATUS_BROADCAST_INTERVAL = 3.0  # Seconds between status broadcasts (reduced from 0.5)

# ==================== MODELS ====================
class ScoreEntry(BaseModel):
    team_name: str
    score: int
    level: str
    rounds: int = 0

@dataclass
class TileInfo:
    id: int
    connected: bool = False
    last_seen: float = 0
    battery: int = 100

@dataclass
class GameSession:
    team_name: str = ""
    level: str = "easy"
    mode: GameMode = GameMode.CLASSIC
    phase: GamePhase = GamePhase.IDLE
    score: int = 0
    round_number: int = 0
    pattern: List[int] = field(default_factory=list)
    player_sequence: List[int] = field(default_factory=list)  # For Simon Says order tracking
    selected_tiles: Set[int] = field(default_factory=set)
    score_submitted: bool = False
    phase_start_time: float = 0
    
    def reset(self):
        self.team_name = ""
        self.level = "easy"
        self.mode = GameMode.CLASSIC
        self.phase = GamePhase.IDLE
        self.score = 0
        self.round_number = 0
        self.pattern = []
        self.player_sequence = []
        self.selected_tiles = set()
        self.score_submitted = False
        self.phase_start_time = 0

# ==================== GLOBAL STATE ====================
class AppState:
    def __init__(self):
        self.master_ws: Optional[WebSocket] = None
        self.master_id: Optional[str] = None
        self.frontend_connections: List[WebSocket] = []
        self.tiles: Dict[int, TileInfo] = {}
        self.game: GameSession = GameSession()
        self.games_played: int = 0
        self.high_score: int = 0
        self._status_task: Optional[asyncio.Task] = None
        self._last_tile_status: Dict = {}  # Track last sent status to avoid spam
        
    def get_connected_tiles(self) -> List[int]:
        """Get list of connected tile IDs"""
        return [tid for tid, info in self.tiles.items() if info.connected]
    
    def get_connected_count(self) -> int:
        return len(self.get_connected_tiles())

state = AppState()

# ==================== CORS & STATIC FILES ====================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files if directory exists
if os.path.exists("static"):
    app.mount("/assets", StaticFiles(directory="static"), name="static")

# ==================== COSMOS DB (Optional) ====================
cosmos_initialized = False
container = None

def init_cosmos_db():
    """Initialize Cosmos DB connection - optional"""
    global cosmos_initialized, container
    try:
        from azure.cosmos import CosmosClient, exceptions
        
        endpoint = os.getenv("COSMOS_ENDPOINT", "")
        key = os.getenv("COSMOS_KEY", "")
        
        if not endpoint or not key or "your-" in endpoint:
            logger.info("Cosmos DB not configured - using in-memory storage")
            return False
        
        client = CosmosClient(endpoint, key)
        database = client.get_database_client(os.getenv("COSMOS_DATABASE", "memomotion"))
        container = database.get_container_client(os.getenv("COSMOS_CONTAINER", "leaderboard"))
        container.read()
        cosmos_initialized = True
        logger.info("✓ Cosmos DB connected")
        return True
    except Exception as e:
        logger.warning(f"Cosmos DB unavailable: {e}")
        return False

# In-memory leaderboard fallback
in_memory_leaderboard: List[dict] = []

# ==================== HELPER FUNCTIONS ====================
async def broadcast_to_frontends(message: dict):
    """Send message to all connected frontends"""
    if not state.frontend_connections:
        return
    
    dead = []
    for ws in state.frontend_connections:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    
    for ws in dead:
        if ws in state.frontend_connections:
            state.frontend_connections.remove(ws)

async def send_to_master(message: dict):
    """Send message to master ESP"""
    if state.master_ws:
        try:
            await state.master_ws.send_json(message)
            return True
        except Exception as e:
            logger.error(f"Failed to send to master: {e}")
    return False

def calculate_pattern_length() -> int:
    """Calculate pattern length based on mode, level, and round
    
    Progressive difficulty: starts with base pattern and adds 1 tile each round
    """
    base = LEVEL_CONFIG[state.game.level]["base_pattern"]
    max_tiles = state.get_connected_count()
    
    if state.game.mode == GameMode.SIMON:
        # Simon Says: starts at 1, grows by 1 each round
        return min(state.game.round_number, max_tiles)
    elif state.game.mode == GameMode.ENDLESS:
        # Endless: starts at 2, grows each round
        return min(1 + state.game.round_number, max_tiles)
    else:
        # Classic/Speedrun: starts at base, adds 1 tile per round (progressive difficulty)
        # Round 1: base tiles, Round 2: base+1, Round 3: base+2, etc.
        pattern_length = base + (state.game.round_number - 1)
        return min(pattern_length, max_tiles)

def calculate_points(correct: bool) -> int:
    """Calculate points for round"""
    if not correct:
        return -WRONG_PENALTY
    
    config = LEVEL_CONFIG[state.game.level]
    # Points = (round * multiplier * 10) + base
    return (state.game.round_number * config["multiplier"] * 10) + config["base_points"]

async def broadcast_tile_status(force: bool = False):
    """Broadcast tile status to frontends - with deduplication"""
    connected = state.get_connected_tiles()
    
    status_data = {
        "tiles": {tid: {"connected": info.connected, "battery": info.battery} 
                  for tid, info in state.tiles.items()},
        "total": TOTAL_TILES,
        "connected": len(connected),
        "connected_tiles": connected,
        "master_connected": state.master_id is not None
    }
    
    # Only send if changed or forced
    if not force and status_data == state._last_tile_status:
        return
    
    state._last_tile_status = status_data.copy()
    
    await broadcast_to_frontends({
        "event": "tile_status",
        "data": status_data
    })

# ==================== ROUTES ====================
@app.get("/")
async def read_index():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "Memory XXL Backend Running", "status": "ok"}

@app.get("/app.js")
async def read_js():
    return FileResponse("static/app.js")

@app.get("/style.css")
async def read_css():
    return FileResponse("static/style.css")

@app.get("/tilehub_styles.css")
async def read_tilehub_css():
    return FileResponse("static/tilehub_styles.css")

@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)

@app.get("/status")
async def get_status():
    return {
        "status": "online",
        "version": "robust-v2",
        "master_connected": state.master_id is not None,
        "frontends": len(state.frontend_connections),
        "tiles_connected": state.get_connected_count(),
        "connected_tiles": state.get_connected_count(),  # Alias for admin page
        "total_tiles": TOTAL_TILES,
        "games_played": state.games_played,
        "game_phase": state.game.phase.value,
        "cosmos_db": cosmos_initialized
    }

@app.get("/admin")
async def admin_page():
    if os.path.exists("static/admin.html"):
        return FileResponse("static/admin.html")
    return {"message": "Admin page not found"}

# ==================== LEADERBOARD API ====================
@app.get("/api/leaderboard")
async def get_leaderboard(limit: int = 10, level: Optional[str] = None):
    if cosmos_initialized and container:
        try:
            query = "SELECT * FROM c ORDER BY c.score DESC OFFSET 0 LIMIT @limit"
            params = [{"name": "@limit", "value": limit}]
            if level:
                query = "SELECT * FROM c WHERE c.level = @level ORDER BY c.score DESC OFFSET 0 LIMIT @limit"
                params.append({"name": "@level", "value": level})
            
            items = list(container.query_items(query=query, parameters=params, enable_cross_partition_query=True))
            return {"leaderboard": items}
        except Exception as e:
            logger.error(f"Leaderboard query error: {e}")
    
    # Fallback to in-memory
    filtered = in_memory_leaderboard if not level else [e for e in in_memory_leaderboard if e.get("level") == level]
    sorted_lb = sorted(filtered, key=lambda x: x.get("score", 0), reverse=True)[:limit]
    return {"leaderboard": sorted_lb}

@app.get("/api/leaderboard/check-name")
async def check_team_name(name: str):
    name_lower = name.strip().lower()
    
    if cosmos_initialized and container:
        try:
            query = "SELECT VALUE COUNT(1) FROM c WHERE LOWER(c.team_name) = @name"
            result = list(container.query_items(
                query=query,
                parameters=[{"name": "@name", "value": name_lower}],
                enable_cross_partition_query=True
            ))
            return {"exists": result[0] > 0 if result else False}
        except Exception:
            pass
    
    # Fallback
    exists = any(e.get("team_name", "").lower() == name_lower for e in in_memory_leaderboard)
    return {"exists": exists}

@app.post("/api/leaderboard")
async def add_score(entry: ScoreEntry):
    item = {
        "id": str(uuid.uuid4()),
        "team_name": entry.team_name,
        "score": entry.score,
        "level": entry.level,
        "rounds": entry.rounds,
        "created_at": datetime.utcnow().isoformat()
    }
    
    if cosmos_initialized and container:
        try:
            container.create_item(body=item)
            logger.info(f"✓ Score saved to Cosmos: {entry.team_name} - {entry.score}")
            return {"status": "ok", "id": item["id"]}
        except Exception as e:
            logger.error(f"Cosmos save error: {e}")
    
    # Fallback
    in_memory_leaderboard.append(item)
    logger.info(f"✓ Score saved to memory: {entry.team_name} - {entry.score}")
    return {"status": "ok", "id": item["id"]}

@app.delete("/api/leaderboard")
async def clear_leaderboard():
    global in_memory_leaderboard
    in_memory_leaderboard = []
    return {"status": "ok", "message": "Leaderboard cleared"}

# ==================== GAME LOGIC ====================
async def start_new_round():
    """Start a new round - generate and show pattern"""
    connected = state.get_connected_tiles()
    
    if len(connected) < 2:
        await broadcast_to_frontends({
            "event": "error",
            "data": {"message": "Need at least 2 connected tiles"}
        })
        return False
    
    state.game.round_number += 1
    state.game.phase = GamePhase.SHOWING_PATTERN
    state.game.player_sequence = []
    state.game.selected_tiles = set()
    state.game.phase_start_time = asyncio.get_event_loop().time()
    
    # Generate pattern
    pattern_length = calculate_pattern_length()
    state.game.pattern = random.sample(connected, min(pattern_length, len(connected)))
    
    logger.info(f"Round {state.game.round_number}: Pattern {state.game.pattern} (length={len(state.game.pattern)}, mode={state.game.mode.value})")
    
    # Determine display mode
    display_mode = "sequential" if state.game.mode == GameMode.SIMON else "simultaneous"
    show_time = LEVEL_CONFIG[state.game.level]["show_time"]
    
    # Tell frontends
    await broadcast_to_frontends({
        "event": "game_started",
        "data": {
            "phase": "showing_pattern",
            "pattern": state.game.pattern,
            "pattern_length": len(state.game.pattern),
            "round": state.game.round_number,
            "score": state.game.score,
            "display_mode": display_mode,
            "show_time": show_time,
            "message": f"Ronde {state.game.round_number} - Onthoud {len(state.game.pattern)} tegels!"
        }
    })
    
    # Tell master to show pattern
    await send_to_master({
        "event": "show_pattern",
        "data": {
            "pattern": state.game.pattern,
            "mode": display_mode,
            "duration": show_time * 1000
        }
    })
    
    # Wait for pattern display time
    await asyncio.sleep(show_time)
    
    # Enter selecting phase
    await enter_selecting_phase()
    return True

async def enter_selecting_phase():
    """Transition to selecting phase"""
    state.game.phase = GamePhase.SELECTING
    state.game.phase_start_time = asyncio.get_event_loop().time()
    state.game.selected_tiles = set()
    state.game.player_sequence = []
    
    # Tell master to hide pattern
    await send_to_master({
        "event": "hide_pattern",
        "data": {}
    })
    
    await broadcast_to_frontends({
        "event": "selecting_phase",
        "data": {
            "pattern_length": len(state.game.pattern),
            "mode": state.game.mode.value,
            "message": "Selecteer de juiste tegels!" if state.game.mode != GameMode.SIMON 
                       else "Herhaal de volgorde!"
        }
    })

async def handle_tile_step(tile_id: int, is_on: bool):
    """Handle player stepping on a tile"""
    if state.game.phase != GamePhase.SELECTING:
        logger.debug(f"Tile {tile_id} step ignored - wrong phase: {state.game.phase}")
        return
    
    # Simon Says: track sequence, no deselection
    if state.game.mode == GameMode.SIMON:
        if is_on:
            state.game.player_sequence.append(tile_id)
            state.game.selected_tiles.add(tile_id)
            
            # Check if sequence matches so far
            idx = len(state.game.player_sequence) - 1
            if idx < len(state.game.pattern):
                if state.game.player_sequence[idx] != state.game.pattern[idx]:
                    # Wrong sequence - game over
                    await end_game_wrong()
                    return
                
                # Check if pattern complete
                if len(state.game.player_sequence) == len(state.game.pattern):
                    await validate_selection()
                    return
        # Simon Says doesn't allow deselection
        return
    
    # Other modes: toggle selection
    if is_on:
        state.game.selected_tiles.add(tile_id)
    else:
        state.game.selected_tiles.discard(tile_id)
    
    await broadcast_to_frontends({
        "event": "tile_toggled",
        "data": {
            "tile_id": tile_id,
            "is_selected": is_on,
            "selected_tiles": list(state.game.selected_tiles),
            "total_selected": len(state.game.selected_tiles),
            "expected_count": len(state.game.pattern)
        }
    })

async def validate_selection():
    """Validate player's tile selection"""
    state.game.phase = GamePhase.VALIDATING
    
    pattern_set = set(state.game.pattern)
    
    # Check based on mode
    if state.game.mode == GameMode.SIMON:
        correct = state.game.player_sequence == state.game.pattern
    else:
        correct = state.game.selected_tiles == pattern_set
    
    if correct:
        await handle_correct_pattern()
    else:
        await end_game_wrong()

async def handle_correct_pattern():
    """Handle correct pattern selection"""
    state.game.phase = GamePhase.ROUND_COMPLETE
    
    points = calculate_points(True)
    state.game.score += points
    
    if state.game.score > state.high_score:
        state.high_score = state.game.score
    
    logger.info(f"✓ Correct! +{points} points. Total: {state.game.score}")
    
    # Tell master - pattern_correct will flash green then turn off
    await send_to_master({"event": "pattern_correct", "data": {}})
    
    await broadcast_to_frontends({
        "event": "pattern_correct",
        "data": {
            "message": "🎉 Perfect!",
            "score": state.game.score,
            "round": state.game.round_number,
            "points_earned": points
        }
    })
    
    # Brief pause then next round
    await asyncio.sleep(2)
    
    # Ensure tiles are off before next round (send twice for reliability)
    await send_to_master({"event": "clear_tiles", "data": {}})
    await asyncio.sleep(0.2)
    await send_to_master({"event": "clear_tiles", "data": {}})
    
    # Start next round automatically
    await asyncio.sleep(1)
    await start_new_round()

async def end_game_wrong():
    """End game due to wrong selection"""
    state.game.phase = GamePhase.GAME_OVER
    
    # Apply penalty
    state.game.score = max(0, state.game.score - WRONG_PENALTY)
    state.games_played += 1
    
    logger.info(f"✗ Wrong! Final score: {state.game.score}")
    
    # Tell master to turn off all tiles (send twice for reliability)
    await send_to_master({"event": "game_over", "data": {}})
    await asyncio.sleep(0.2)
    await send_to_master({"event": "clear_tiles", "data": {}})
    
    # Save score
    await save_score()
    
    await broadcast_to_frontends({
        "event": "game_over",
        "data": {
            "message": "❌ Fout! Game Over",
            "expected": state.game.pattern,
            "selected_tiles": list(state.game.selected_tiles),
            "player_sequence": state.game.player_sequence,
            "final_score": state.game.score,
            "rounds": state.game.round_number,
            "team_name": state.game.team_name,
            "level": state.game.level,
            "penalty_applied": WRONG_PENALTY
        }
    })
    
    # Reset game state after delay
    await asyncio.sleep(2)
    state.game.phase = GamePhase.IDLE

async def save_score():
    """Save score to leaderboard"""
    if state.game.score_submitted or not state.game.team_name.strip():
        return
    
    try:
        await add_score(ScoreEntry(
            team_name=state.game.team_name,
            score=state.game.score,
            level=state.game.level,
            rounds=state.game.round_number
        ))
        state.game.score_submitted = True
    except Exception as e:
        logger.error(f"Failed to save score: {e}")

# ==================== MASTER WEBSOCKET ====================
@app.websocket("/ws/master")
async def master_websocket(websocket: WebSocket):
    await websocket.accept()
    logger.info("→ Master WebSocket connected")
    
    try:
        # Wait for identification
        data = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        
        if data.get("event") == "master_connected":
            state.master_ws = websocket
            state.master_id = data.get("data", {}).get("master_id", "ESP32")
            logger.info(f"✓ Master registered: {state.master_id}")
            
            # Notify frontends
            await broadcast_to_frontends({
                "event": "master_status",
                "data": {"connected": True, "master_id": state.master_id}
            })
            await broadcast_to_frontends({
                "event": "master_connected",
                "data": {"master_id": state.master_id}
            })
            
            # Main message loop
            while True:
                try:
                    msg = await asyncio.wait_for(websocket.receive_json(), timeout=30)
                    await handle_master_message(msg)
                except asyncio.TimeoutError:
                    # Send ping to keep alive
                    try:
                        await websocket.send_json({"event": "ping"})
                    except:
                        break
                        
    except WebSocketDisconnect:
        logger.info("✗ Master disconnected")
    except Exception as e:
        logger.error(f"Master error: {e}")
    finally:
        state.master_ws = None
        state.master_id = None
        # Clear all tiles - if Master is disconnected, tiles can't be online
        for tid in state.tiles:
            state.tiles[tid].connected = False
        state._last_tile_status = {}  # Force status broadcast
        logger.info("✗ All tiles marked offline (Master disconnected)")
        await broadcast_to_frontends({
            "event": "master_status",
            "data": {"connected": False}
        })
        # Broadcast updated tile status showing all offline
        await broadcast_tile_status(force=True)

async def handle_master_message(msg: dict):
    """Handle messages from master ESP"""
    event = msg.get("event", "")
    data = msg.get("data", {})
    
    if event == "tile_status":
        # Update tile registry
        tiles_data = data.get("tiles", [])
        registered_count = data.get("registered_count", 0)
        
        # Update tiles
        for tile in tiles_data:
            tid = tile.get("id")
            if tid:
                if tid not in state.tiles:
                    state.tiles[tid] = TileInfo(id=tid)
                state.tiles[tid].connected = tile.get("connected", True)
                state.tiles[tid].last_seen = asyncio.get_event_loop().time()
                state.tiles[tid].battery = tile.get("battery", 100)
        
        # Broadcast to frontends (with deduplication)
        await broadcast_tile_status()
        
    elif event == "start_button_pressed":
        logger.info("→ START button pressed")
        
        if state.game.phase == GamePhase.REGISTERED:
            # Start first round
            await start_new_round()
        elif state.game.phase == GamePhase.SELECTING:
            # Clear tiles immediately before validating
            await send_to_master({"event": "clear_tiles", "data": {}})
            # Confirm selection
            await validate_selection()
        elif state.game.phase == GamePhase.IDLE:
            await broadcast_to_frontends({
                "event": "info",
                "data": {"message": "Register a team first!"}
            })
    
    elif event == "confirm_button_pressed":
        if state.game.phase == GamePhase.SELECTING:
            await validate_selection()
    
    elif event == "player_step":
        tile_id = data.get("tile_id")
        is_on = data.get("is_on", True)
        if tile_id is not None:
            await handle_tile_step(tile_id, is_on)
    
    elif event == "pong":
        pass  # Keep-alive response

# ==================== FRONTEND WEBSOCKET ====================
@app.websocket("/ws/frontend")
async def frontend_websocket(websocket: WebSocket):
    await websocket.accept()
    state.frontend_connections.append(websocket)
    logger.info(f"→ Frontend connected (total: {len(state.frontend_connections)})")
    
    # Send initial state
    await websocket.send_json({
        "event": "initial_state",
        "data": {
            "master_connected": state.master_id is not None,
            "games_played": state.games_played,
            "high_score": state.high_score,
            "tiles": {tid: {"connected": info.connected, "battery": info.battery} 
                      for tid, info in state.tiles.items()},
            "connected_tiles": state.get_connected_tiles(),
            "total_tiles": TOTAL_TILES,
            "game_phase": state.game.phase.value
        }
    })
    
    try:
        while True:
            msg = await websocket.receive_json()
            await handle_frontend_message(msg, websocket)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Frontend error: {e}")
    finally:
        if websocket in state.frontend_connections:
            state.frontend_connections.remove(websocket)
        logger.info(f"✗ Frontend disconnected (remaining: {len(state.frontend_connections)})")

async def handle_frontend_message(msg: dict, websocket: WebSocket):
    """Handle messages from frontend"""
    event = msg.get("event") or msg.get("type", "")
    data = msg.get("data", {}) or msg
    
    if event == "start_game":
        # Register new game
        state.game.reset()
        state.game.team_name = data.get("team_name", "Team")
        state.game.level = data.get("level", "easy")
        
        mode_str = data.get("mode", "classic")
        try:
            state.game.mode = GameMode(mode_str)
        except ValueError:
            state.game.mode = GameMode.CLASSIC
        
        state.game.phase = GamePhase.REGISTERED
        
        logger.info(f"→ Game registered: {state.game.team_name} ({state.game.level}, {state.game.mode.value})")
        
        await websocket.send_json({
            "event": "game_registered",
            "data": {
                "team_name": state.game.team_name,
                "level": state.game.level,
                "mode": state.game.mode.value,
                "message": "Press START on the master to begin!"
            }
        })
    
    elif event == "request_state":
        await websocket.send_json({
            "event": "state_update",
            "data": {
                "master_connected": state.master_id is not None,
                "tiles": {tid: {"connected": info.connected} for tid, info in state.tiles.items()},
                "game_phase": state.game.phase.value
            }
        })

# ==================== ADMIN API ====================

# Admin-configurable settings (separate from constants)
admin_config = {
    "levels": {
        "easy": {"steps": 4, "points": 10},
        "medium": {"steps": 6, "points": 15},
        "hard": {"steps": 8, "points": 25}
    },
    "speedRun": {
        "timePerStep": 3,
        "bonusPerSecond": 2
    }
}

@app.get("/api/admin/tiles")
async def get_tiles_admin():
    return {
        "tiles": [
            {"id": tid, "connected": info.connected, "battery": info.battery}
            for tid, info in sorted(state.tiles.items())
        ]
    }

@app.get("/api/admin/config")
async def get_config():
    return {
        "levels": admin_config["levels"],
        "speedRun": admin_config["speedRun"],
        "wrongPenalty": WRONG_PENALTY,
        "totalTiles": TOTAL_TILES
    }

@app.post("/api/admin/config/levels")
async def save_level_config(config: dict):
    """Save level configuration"""
    try:
        admin_config["levels"] = {
            "easy": {
                "steps": config.get("easy", {}).get("steps", 4),
                "points": config.get("easy", {}).get("points", 10)
            },
            "medium": {
                "steps": config.get("medium", {}).get("steps", 6),
                "points": config.get("medium", {}).get("points", 15)
            },
            "hard": {
                "steps": config.get("hard", {}).get("steps", 8),
                "points": config.get("hard", {}).get("points", 25)
            }
        }
        logger.info(f"Level config updated: {admin_config['levels']}")
        return {"status": "ok", "config": admin_config["levels"]}
    except Exception as e:
        logger.error(f"Failed to save level config: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/admin/config/speedrun")
async def save_speedrun_config(config: dict):
    """Save speed run configuration"""
    try:
        admin_config["speedRun"] = {
            "timePerStep": config.get("timePerStep", 3),
            "bonusPerSecond": config.get("bonusPerSecond", 2)
        }
        logger.info(f"Speed run config updated: {admin_config['speedRun']}")
        return {"status": "ok", "config": admin_config["speedRun"]}
    except Exception as e:
        logger.error(f"Failed to save speed run config: {e}")
        return {"status": "error", "message": str(e)}

@app.delete("/api/admin/leaderboard/{score_id}")
async def delete_single_score(score_id: str):
    """Delete a single score from leaderboard"""
    global in_memory_leaderboard
    
    if cosmos_initialized and container:
        try:
            # Try to find and delete from Cosmos DB
            query = "SELECT * FROM c WHERE c.id = @id"
            items = list(container.query_items(
                query=query,
                parameters=[{"name": "@id", "value": score_id}],
                enable_cross_partition_query=True
            ))
            
            if items:
                item = items[0]
                container.delete_item(item=item['id'], partition_key=item.get('team_name', item['id']))
                logger.info(f"✓ Deleted score {score_id} from Cosmos DB")
                return {"status": "ok", "message": "Score deleted"}
        except Exception as e:
            logger.error(f"Failed to delete from Cosmos DB: {e}")
            # Fall through to try in-memory deletion
    
    # Try in-memory deletion
    original_length = len(in_memory_leaderboard)
    
    # Try to find by id (string) or by index (number)
    try:
        # First try as string id
        in_memory_leaderboard = [e for e in in_memory_leaderboard if e.get("id") != score_id]
        
        # If that didn't work, try as index
        if len(in_memory_leaderboard) == original_length:
            try:
                index = int(score_id)
                if 0 <= index < len(in_memory_leaderboard):
                    del in_memory_leaderboard[index]
                    logger.info(f"✓ Deleted score at index {index} from memory")
                    return {"status": "ok", "message": "Score deleted"}
            except ValueError:
                pass
        else:
            logger.info(f"✓ Deleted score {score_id} from memory")
            return {"status": "ok", "message": "Score deleted"}
    except Exception as e:
        logger.error(f"Delete error: {e}")
    
    return {"status": "error", "message": "Score not found"}

@app.post("/api/admin/reset")
async def admin_reset():
    """Reset game state"""
    state.game.reset()
    await send_to_master({"event": "reset", "data": {}})
    await broadcast_to_frontends({"event": "game_reset", "data": {}})
    return {"status": "ok"}

# ==================== STARTUP ====================
@app.on_event("startup")
async def startup():
    logger.info("=" * 50)
    logger.info("Memory XXL Backend - Robust v2")
    logger.info("=" * 50)
    
    init_cosmos_db()
    
    logger.info("✓ Server ready")
    logger.info(f"  Master: ws://HOST:8000/ws/master")
    logger.info(f"  Frontend: ws://HOST:8000/ws/frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
