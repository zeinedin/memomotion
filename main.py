"""
Memory XXL Backend - ROBUST VERSION
Production-ready with proper state machine and error handling
Version: 2.1 - Fixed speedrun timer timeout
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
import time
import os
import uuid
import logging

# Configure logging - set to WARNING for production (less noise)
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Suppress verbose HTTP request logging
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

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
    "easy": {"base_pattern": 1, "multiplier": 1, "base_points": 20, "show_time": 6},
    "medium": {"base_pattern": 3, "multiplier": 2, "base_points": 30, "show_time": 5},
    "hard": {"base_pattern": 5, "multiplier": 3, "base_points": 50, "show_time": 4}
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

# Speedrun configuration (time_limit in seconds: easy=4min, medium=2.5min, hard=1.5min)
SPEEDRUN_CONFIG = {
    "easy": {"time_limit": 240, "time_bonus_per_second": 2, "base_pattern": 2},
    "medium": {"time_limit": 150, "time_bonus_per_second": 3, "base_pattern": 3},
    "hard": {"time_limit": 90, "time_bonus_per_second": 5, "base_pattern": 5}
}

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
    # Speedrun specific fields
    speedrun_start_time: float = 0
    speedrun_time_limit: float = 0
    speedrun_timer_task: Optional[asyncio.Task] = None
    
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
        self.speedrun_start_time = 0
        self.speedrun_time_limit = 0
        if self.speedrun_timer_task:
            self.speedrun_timer_task.cancel()
        self.speedrun_timer_task = None

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
    elif state.game.mode == GameMode.CLASSIC:
        # Classic: progressive difficulty with increasing plateau lengths
        # Round 1: base (1 round at this level)
        # Rounds 2-3: base+1 (2 rounds at this level)
        # Rounds 4-6: base+2 (3 rounds at this level)
        # Rounds 7-10: base+3 (4 rounds at this level)
        # etc. - each level lasts one round longer than the previous
        # Win condition: when pattern reaches 10 tiles, player wins!
        import math
        round_num = state.game.round_number
        
        # Calculate level using triangular number formula
        # Level n starts at round: 1 + n(n+1)/2
        # Given round R, level = floor((-1 + sqrt(1 + 8*(R-1))) / 2)
        level = int((-1 + math.sqrt(1 + 8 * (round_num - 1))) / 2)
        pattern_length = base + level
        
        return min(pattern_length, max_tiles)
    else:
        # Speedrun: fixed pattern size based on level, focus on speed not memory growth
        speedrun_base = SPEEDRUN_CONFIG[state.game.level]["base_pattern"]
        pattern_length = speedrun_base + min(state.game.round_number - 1, 2)  # Max +2 tiles
        return min(pattern_length, max_tiles)

def calculate_points(correct: bool) -> int:
    """Calculate points for round"""
    if not correct:
        return -WRONG_PENALTY
    
    # Speedrun mode: points based on time remaining
    if state.game.mode == GameMode.SPEEDRUN:
        return calculate_speedrun_points()
    
    config = LEVEL_CONFIG[state.game.level]
    # Points = (round * multiplier * 10) + base
    return (state.game.round_number * config["multiplier"] * 10) + config["base_points"]

def calculate_speedrun_points() -> int:
    """Calculate points for Speedrun mode based on time remaining"""
    config = SPEEDRUN_CONFIG[state.game.level]
    time_remaining = get_speedrun_time_remaining()
    
    # Base points for correct pattern + bonus for remaining time
    base_points = 50 + (state.game.round_number * 10)
    time_bonus = int(time_remaining * config["time_bonus_per_second"])
    
    return base_points + time_bonus

def get_speedrun_time_remaining() -> float:
    """Get remaining time in Speedrun mode"""
    if state.game.speedrun_start_time == 0:
        return 0
    
    elapsed = time.time() - state.game.speedrun_start_time
    remaining = state.game.speedrun_time_limit - elapsed
    return max(0, remaining)

async def speedrun_timer_loop():
    """Background task to update speedrun timer and check for timeout"""
    try:
        while True:
            if state.game.mode != GameMode.SPEEDRUN:
                break
            if state.game.phase == GamePhase.GAME_OVER:
                break
            if state.game.phase == GamePhase.IDLE:
                break
            
            if state.game.speedrun_start_time == 0:
                break
                
            time_remaining = get_speedrun_time_remaining()
            
            # Broadcast timer update to frontends
            try:
                await broadcast_to_frontends({
                    "event": "speedrun_timer",
                    "data": {
                        "time_remaining": round(time_remaining, 1),
                        "time_limit": state.game.speedrun_time_limit
                    }
                })
            except Exception:
                pass
            
            # Check for timeout - END THE GAME
            if time_remaining <= 0:
                try:
                    await end_game_timeout()
                except Exception as e:
                    logger.error(f"Timer timeout error: {e}")
                break
            
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Timer error: {e}")


async def end_game_timeout():
    """Handle speedrun timeout - end the game"""
    state.game.phase = GamePhase.GAME_OVER
    state.games_played += 1
    
    # Cancel timer task
    if state.game.speedrun_timer_task:
        state.game.speedrun_timer_task.cancel()
        state.game.speedrun_timer_task = None
    
    # Reset speedrun timing to prevent further checks
    state.game.speedrun_start_time = 0
    state.game.speedrun_time_limit = 0
    
    # Tell master to turn off all tiles (multiple times for reliability)
    try:
        await send_to_master({"event": "game_over", "data": {}})
        await asyncio.sleep(0.1)
        await send_to_master({"event": "clear_tiles", "data": {}})
    except Exception:
        pass
    
    # Save score BEFORE broadcasting to prevent blocking
    try:
        await save_score()
    except Exception:
        pass
    
    # Broadcast game over to frontends
    try:
        await broadcast_to_frontends({
            "event": "game_over",
            "data": {
                "message": "⏱️ Time's Up! Game Over",
                "final_score": state.game.score,
                "rounds": state.game.round_number,
                "team_name": state.game.team_name,
                "level": state.game.level,
                "timeout": True,
                "mode": "speedrun"
            }
        })
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
    
    # Keep GAME_OVER phase visible longer before resetting
    await asyncio.sleep(5)
    
    # Only reset to IDLE if still in GAME_OVER (not started new game)
    if state.game.phase == GamePhase.GAME_OVER:
        state.game.phase = GamePhase.IDLE

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
    if os.path.exists("static/favicon.ico"):
        return FileResponse("static/favicon.ico", media_type="image/x-icon")
    return Response(status_code=204)

@app.get("/logos/{filename}")
async def get_logo(filename: str):
    filepath = f"static/logos/{filename}"
    if os.path.exists(filepath):
        return FileResponse(filepath)
    return Response(status_code=404)

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
    """Clear entire leaderboard (both Cosmos DB and in-memory)"""
    global in_memory_leaderboard
    
    deleted_count = 0
    failed_count = 0
    
    # Clear Cosmos DB if initialized
    if cosmos_initialized and container:
        try:
            # Query all items with all fields needed for deletion
            query = "SELECT * FROM c"
            items = list(container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            
            logger.info(f"Found {len(items)} items in Cosmos DB to delete")
            
            for item in items:
                item_id = item.get('id')
                if not item_id:
                    continue
                    
                # Try different partition key strategies
                partition_keys_to_try = [
                    item_id,  # Most common: /id as partition key
                    item.get('team_name'),  # Alternative: /team_name
                    item.get('level'),  # Alternative: /level
                ]
                
                deleted = False
                for pk in partition_keys_to_try:
                    if pk is None:
                        continue
                    try:
                        container.delete_item(item=item_id, partition_key=pk)
                        deleted_count += 1
                        deleted = True
                        break
                    except Exception:
                        continue
                
                if not deleted:
                    failed_count += 1
                    logger.warning(f"Could not delete item {item_id}")
            
            logger.info(f"✓ Deleted {deleted_count} items from Cosmos DB ({failed_count} failed)")
        except Exception as e:
            logger.error(f"Failed to clear Cosmos DB: {e}")
    
    # Also clear in-memory
    in_memory_count = len(in_memory_leaderboard)
    in_memory_leaderboard = []
    
    total_deleted = deleted_count + in_memory_count
    logger.info(f"✓ Leaderboard cleared (Cosmos: {deleted_count}, Memory: {in_memory_count})")
    return {"status": "ok", "message": f"Leaderboard cleared ({total_deleted} scores deleted)"}

# ==================== GAME LOGIC ====================
async def start_new_round():
    """Start a new round - generate and show pattern"""
    # Check if game was ended (e.g., by speedrun timeout)
    if state.game.phase == GamePhase.GAME_OVER or state.game.phase == GamePhase.IDLE:
        logger.info("start_new_round aborted - game already ended")
        return False
    
    # For speedrun, check if time already expired
    if state.game.mode == GameMode.SPEEDRUN and state.game.speedrun_start_time > 0:
        if get_speedrun_time_remaining() <= 0:
            logger.info("start_new_round aborted - speedrun time expired")
            return False
    
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
    
    # Initialize Speedrun timer on first round
    if state.game.mode == GameMode.SPEEDRUN and state.game.round_number == 1:
        config = SPEEDRUN_CONFIG[state.game.level]
        state.game.speedrun_time_limit = config["time_limit"]
        state.game.speedrun_start_time = time.time()  # Use time.time() for reliable timing
        # Cancel any existing timer task
        if state.game.speedrun_timer_task:
            state.game.speedrun_timer_task.cancel()
        # Start timer background task
        state.game.speedrun_timer_task = asyncio.create_task(speedrun_timer_loop())
        logger.info(f"⏱️ Speedrun started: {state.game.speedrun_time_limit}s timer at {state.game.speedrun_start_time}")
    
    # Generate pattern
    pattern_length = calculate_pattern_length()
    
    # WIN CONDITION: If pattern would reach 10 tiles in Classic mode, player wins!
    if state.game.mode == GameMode.CLASSIC and pattern_length >= 10:
        await end_game_win()
        return True
    
    # Simon Says: build on previous pattern by adding one new tile each round
    if state.game.mode == GameMode.SIMON:
        base = LEVEL_CONFIG[state.game.level]["base_pattern"]  # easy=1, medium=3, hard=5
        if state.game.round_number == 1:
            # First round: start with base_pattern tiles based on difficulty
            state.game.pattern = random.sample(connected, min(base, len(connected)))
        else:
            # Subsequent rounds: add one new random tile to existing pattern
            # Choose from tiles not recently used to add variety
            available = [t for t in connected if t != state.game.pattern[-1]] if len(connected) > 1 else connected
            new_tile = random.choice(available)
            state.game.pattern.append(new_tile)
    else:
        # Other modes: generate fresh random pattern
        state.game.pattern = random.sample(connected, min(pattern_length, len(connected)))
    
    logger.info(f"Round {state.game.round_number}: Pattern {state.game.pattern} (length={len(state.game.pattern)}, mode={state.game.mode.value})")
    
    # Determine display mode
    display_mode = "sequential" if state.game.mode == GameMode.SIMON else "simultaneous"
    show_time = LEVEL_CONFIG[state.game.level]["show_time"]
    
    # Tell frontends
    game_data = {
        "phase": "showing_pattern",
        "pattern": state.game.pattern,
        "pattern_length": len(state.game.pattern),
        "round": state.game.round_number,
        "score": state.game.score,
        "display_mode": display_mode,
        "show_time": show_time,
        "message": f"Ronde {state.game.round_number} - Onthoud {len(state.game.pattern)} tegels!"
    }
    
    # Add speedrun info if applicable
    if state.game.mode == GameMode.SPEEDRUN:
        game_data["speedrun"] = True
        game_data["time_remaining"] = round(get_speedrun_time_remaining(), 1)
        game_data["time_limit"] = state.game.speedrun_time_limit
    
    await broadcast_to_frontends({
        "event": "game_started",
        "data": game_data
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
    # For Simon Says (sequential), need more time: 0.8s per tile + buffer
    if state.game.mode == GameMode.SIMON:
        sequential_time = len(state.game.pattern) * 0.8 + 0.5  # 800ms per tile + 500ms buffer
        await asyncio.sleep(max(sequential_time, show_time))
    else:
        await asyncio.sleep(show_time)
    
    # Enter selecting phase
    await enter_selecting_phase()
    return True

async def enter_selecting_phase():
    """Transition to selecting phase"""
    # Check if game ended (speedrun timeout during pattern display)
    if state.game.phase == GamePhase.GAME_OVER or state.game.phase == GamePhase.IDLE:
        logger.info("enter_selecting_phase aborted - game already ended")
        return
    
    # For speedrun, check if time expired
    if state.game.mode == GameMode.SPEEDRUN and state.game.speedrun_start_time > 0:
        if get_speedrun_time_remaining() <= 0:
            logger.info("enter_selecting_phase aborted - speedrun time expired")
            return
    
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
    
    # For speedrun, check if time expired (game should be ending)
    if state.game.mode == GameMode.SPEEDRUN and state.game.speedrun_start_time > 0:
        if get_speedrun_time_remaining() <= 0:
            logger.debug(f"Tile {tile_id} step ignored - speedrun time expired")
            return
    
    # Simon Says: track sequence, no deselection
    if state.game.mode == GameMode.SIMON:
        if is_on:
            state.game.player_sequence.append(tile_id)
            state.game.selected_tiles.add(tile_id)
            
            # Send tile toggle event for Simon mode too
            await broadcast_to_frontends({
                "event": "tile_toggled",
                "data": {
                    "tile_id": tile_id,
                    "is_selected": True,
                    "selected_tiles": list(state.game.selected_tiles),
                    "total_selected": len(state.game.player_sequence),
                    "expected_count": len(state.game.pattern)
                }
            })
            
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
    # Check if game already ended (e.g., speedrun timeout)
    if state.game.phase == GamePhase.GAME_OVER or state.game.phase == GamePhase.IDLE:
        logger.info("validate_selection aborted - game already ended")
        return
    
    # For speedrun, check if time expired
    if state.game.mode == GameMode.SPEEDRUN and state.game.speedrun_start_time > 0:
        if get_speedrun_time_remaining() <= 0:
            logger.info("validate_selection aborted - speedrun time expired")
            return
    
    state.game.phase = GamePhase.VALIDATING
    
    # IMMEDIATELY clear all tile LEDs when validation starts
    await send_to_master({"event": "clear_tiles", "data": {}})
    
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
    
    # Check if game ended during the pause (speedrun timeout)
    if state.game.phase == GamePhase.GAME_OVER or state.game.phase == GamePhase.IDLE:
        logger.info("handle_correct_pattern: game ended during pause, not starting new round")
        return
    
    # For speedrun, check if time expired during pause
    if state.game.mode == GameMode.SPEEDRUN and get_speedrun_time_remaining() <= 0:
        logger.info("handle_correct_pattern: speedrun time expired during pause")
        return
    
    # Ensure tiles are off before next round (send twice for reliability)
    await send_to_master({"event": "clear_tiles", "data": {}})
    await asyncio.sleep(0.2)
    await send_to_master({"event": "clear_tiles", "data": {}})
    
    # Start next round automatically
    await asyncio.sleep(1)
    await start_new_round()

async def end_game_win():
    """End game - PLAYER WINS! Reached 10 tile pattern"""
    state.game.phase = GamePhase.GAME_OVER
    state.games_played += 1
    
    # Cancel speedrun timer if running
    if state.game.speedrun_timer_task:
        state.game.speedrun_timer_task.cancel()
        state.game.speedrun_timer_task = None
    
    # Reset speedrun timing to prevent further checks
    state.game.speedrun_start_time = 0
    state.game.speedrun_time_limit = 0
    
    # Bonus points for winning!
    bonus_points = 100
    state.game.score += bonus_points
    
    if state.game.score > state.high_score:
        state.high_score = state.game.score
    
    logger.info(f"🏆 WINNER! Final score: {state.game.score} (includes {bonus_points} bonus)")
    
    # Tell master to celebrate (flash all tiles green)
    await send_to_master({"event": "game_won", "data": {}})
    await asyncio.sleep(0.2)
    await send_to_master({"event": "pattern_correct", "data": {}})  # Flash green
    
    # Save score
    await save_score()
    
    await broadcast_to_frontends({
        "event": "game_won",
        "data": {
            "message": "🏆 GEFELICITEERD! Je hebt gewonnen!",
            "final_score": state.game.score,
            "rounds": state.game.round_number,
            "team_name": state.game.team_name,
            "level": state.game.level,
            "mode": state.game.mode.value,
            "bonus_points": bonus_points
        }
    })
    
    # Reset game state after delay
    await asyncio.sleep(3)
    await send_to_master({"event": "clear_tiles", "data": {}})
    state.game.phase = GamePhase.IDLE

async def end_game_wrong():
    """End game due to wrong selection"""
    # Prevent multiple calls
    if state.game.phase == GamePhase.GAME_OVER:
        logger.info("end_game_wrong: already game over, skipping")
        return
    
    state.game.phase = GamePhase.GAME_OVER
    
    # Cancel speedrun timer if running
    if state.game.speedrun_timer_task:
        state.game.speedrun_timer_task.cancel()
        state.game.speedrun_timer_task = None
    
    # Reset speedrun timing to prevent further checks
    state.game.speedrun_start_time = 0
    state.game.speedrun_time_limit = 0
    
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
            "mode": state.game.mode.value,
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
        
        # Check if game was in progress - preserve game state but notify frontend
        game_was_active = state.game.phase not in [GamePhase.IDLE, GamePhase.GAME_OVER]
        
        # Send master_disconnected event with game state info
        await broadcast_to_frontends({
            "event": "master_disconnected",
            "data": {
                "connected": False,
                "game_paused": game_was_active,
                "game_phase": state.game.phase.value,
                "team_name": state.game.team_name,
                "round": state.game.round_number,
                "score": state.game.score
            }
        })
        
        # Also send master_status for compatibility
        await broadcast_to_frontends({
            "event": "master_status",
            "data": {"connected": False}
        })
        
        # Broadcast updated tile status showing all offline
        await broadcast_to_frontends({
            "event": "tile_status",
            "data": {
                "tiles": {tid: {"connected": False, "battery": info.battery} 
                          for tid, info in state.tiles.items()},
                "total": TOTAL_TILES,
                "connected": 0,
                "connected_tiles": [],
                "master_connected": False
            }
        })

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
        logger.info(f"→ START button pressed (phase: {state.game.phase})")
        
        if state.game.phase == GamePhase.REGISTERED:
            # Start first round
            await start_new_round()
        elif state.game.phase == GamePhase.GAME_OVER:
            # Player pressed start after game over - allow restart if team is registered
            if state.game.team_name:
                state.game.phase = GamePhase.REGISTERED
                state.game.round_number = 0
                state.game.score = 0
                state.game.pattern = []
                state.game.selected_tiles = set()
                state.game.player_sequence = []
                state.game.score_submitted = False
                # Cancel any existing speedrun timer
                if state.game.speedrun_timer_task:
                    state.game.speedrun_timer_task.cancel()
                    state.game.speedrun_timer_task = None
                state.game.speedrun_start_time = 0
                state.game.speedrun_time_limit = 0
                await start_new_round()
            else:
                await broadcast_to_frontends({
                    "event": "info",
                    "data": {"message": "Register a team first!"}
                })
        elif state.game.phase == GamePhase.SELECTING:
            # Clear tiles immediately before validating
            await send_to_master({"event": "clear_tiles", "data": {}})
            # Confirm selection
            await validate_selection()
        elif state.game.phase == GamePhase.IDLE:
            # Check if we have a team name from previous game
            if state.game.team_name:
                # Re-register the team and start
                state.game.phase = GamePhase.REGISTERED
                state.game.round_number = 0
                state.game.score = 0
                state.game.pattern = []
                state.game.selected_tiles = set()
                state.game.player_sequence = []
                state.game.score_submitted = False
                await start_new_round()
            else:
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
        # Register new game - reset game progress but set team info first
        team_name = data.get("team_name", "Team")
        level = data.get("level", "easy")
        mode_str = data.get("mode", "classic")
        
        # Cancel any existing speedrun timer before reset
        if state.game.speedrun_timer_task:
            state.game.speedrun_timer_task.cancel()
            state.game.speedrun_timer_task = None
        
        # Reset game progress (but keep team info we're about to set)
        state.game.score = 0
        state.game.round_number = 0
        state.game.pattern = []
        state.game.player_sequence = []
        state.game.selected_tiles = set()
        state.game.score_submitted = False
        state.game.phase_start_time = 0
        state.game.speedrun_start_time = 0
        state.game.speedrun_time_limit = 0
        
        # Set team info
        state.game.team_name = team_name
        state.game.level = level
        try:
            state.game.mode = GameMode(mode_str)
        except ValueError:
            state.game.mode = GameMode.CLASSIC
        
        # Set phase LAST to ensure all data is ready
        state.game.phase = GamePhase.REGISTERED
        
        logger.info(f"→ Game registered: {state.game.team_name} ({state.game.level}, {state.game.mode.value})")
        
        # Broadcast to ALL frontends, not just the one that sent the message
        await broadcast_to_frontends({
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
    # Return current game config values (sync admin_config with actual LEVEL_CONFIG)
    return {
        "levels": {
            "easy": {"steps": LEVEL_CONFIG["easy"]["base_pattern"], "points": LEVEL_CONFIG["easy"]["base_points"]},
            "medium": {"steps": LEVEL_CONFIG["medium"]["base_pattern"], "points": LEVEL_CONFIG["medium"]["base_points"]},
            "hard": {"steps": LEVEL_CONFIG["hard"]["base_pattern"], "points": LEVEL_CONFIG["hard"]["base_points"]}
        },
        "speedRun": {
            "timePerStep": admin_config["speedRun"]["timePerStep"],
            "bonusPerSecond": SPEEDRUN_CONFIG["easy"]["time_bonus_per_second"]
        },
        "wrongPenalty": WRONG_PENALTY,
        "totalTiles": TOTAL_TILES
    }

@app.post("/api/admin/config/levels")
async def save_level_config(config: dict):
    """Save level configuration - updates both admin_config and LEVEL_CONFIG"""
    try:
        logger.info(f"Received level config to save: {config}")
        
        # Extract values with defaults
        easy_steps = int(config.get("easy", {}).get("steps", 1))
        easy_points = int(config.get("easy", {}).get("points", 20))
        medium_steps = int(config.get("medium", {}).get("steps", 3))
        medium_points = int(config.get("medium", {}).get("points", 30))
        hard_steps = int(config.get("hard", {}).get("steps", 5))
        hard_points = int(config.get("hard", {}).get("points", 50))
        
        # Update admin_config
        admin_config["levels"] = {
            "easy": {"steps": easy_steps, "points": easy_points},
            "medium": {"steps": medium_steps, "points": medium_points},
            "hard": {"steps": hard_steps, "points": hard_points}
        }
        
        # Update LEVEL_CONFIG to apply changes to the game
        LEVEL_CONFIG["easy"]["base_pattern"] = easy_steps
        LEVEL_CONFIG["easy"]["base_points"] = easy_points
        LEVEL_CONFIG["medium"]["base_pattern"] = medium_steps
        LEVEL_CONFIG["medium"]["base_points"] = medium_points
        LEVEL_CONFIG["hard"]["base_pattern"] = hard_steps
        LEVEL_CONFIG["hard"]["base_points"] = hard_points
        
        logger.info(f"✓ Level config SAVED - Easy: {easy_steps} steps/{easy_points} pts, Medium: {medium_steps} steps/{medium_points} pts, Hard: {hard_steps} steps/{hard_points} pts")
        logger.info(f"✓ LEVEL_CONFIG now: {LEVEL_CONFIG}")
        
        return {
            "status": "ok", 
            "config": admin_config["levels"],
            "applied": {
                "easy": {"base_pattern": LEVEL_CONFIG["easy"]["base_pattern"], "base_points": LEVEL_CONFIG["easy"]["base_points"]},
                "medium": {"base_pattern": LEVEL_CONFIG["medium"]["base_pattern"], "base_points": LEVEL_CONFIG["medium"]["base_points"]},
                "hard": {"base_pattern": LEVEL_CONFIG["hard"]["base_pattern"], "base_points": LEVEL_CONFIG["hard"]["base_points"]}
            }
        }
    except Exception as e:
        logger.error(f"Failed to save level config: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/admin/config/speedrun")
async def save_speedrun_config(config: dict):
    """Save speed run configuration - updates both admin_config and SPEEDRUN_CONFIG"""
    try:
        logger.info(f"Received speedrun config to save: {config}")
        
        time_per_step = int(config.get("timePerStep", 3))
        bonus_per_second = int(config.get("bonusPerSecond", 2))
        
        admin_config["speedRun"] = {
            "timePerStep": time_per_step,
            "bonusPerSecond": bonus_per_second
        }
        
        # Update SPEEDRUN_CONFIG to apply changes to the game
        for level in ["easy", "medium", "hard"]:
            SPEEDRUN_CONFIG[level]["time_bonus_per_second"] = bonus_per_second
        
        logger.info(f"✓ Speedrun config SAVED - timePerStep: {time_per_step}, bonusPerSecond: {bonus_per_second}")
        logger.info(f"✓ SPEEDRUN_CONFIG now: {SPEEDRUN_CONFIG}")
        
        return {"status": "ok", "config": admin_config["speedRun"]}
    except Exception as e:
        logger.error(f"Failed to save speed run config: {e}")
        return {"status": "error", "message": str(e)}

@app.delete("/api/admin/leaderboard/{score_id}")
async def delete_single_score(score_id: str):
    """Delete a single score from leaderboard"""
    global in_memory_leaderboard
    
    logger.info(f"Attempting to delete score with ID: {score_id}")
    
    if cosmos_initialized and container:
        try:
            # Try to find the item first
            query = "SELECT * FROM c WHERE c.id = @id"
            items = list(container.query_items(
                query=query,
                parameters=[{"name": "@id", "value": score_id}],
                enable_cross_partition_query=True
            ))
            
            if items:
                item = items[0]
                item_id = item['id']
                
                # Try different partition key strategies
                partition_keys_to_try = [
                    item_id,  # Most common: /id as partition key
                    item.get('team_name'),  # Alternative: /team_name
                    item.get('level'),  # Alternative: /level
                ]
                
                for pk in partition_keys_to_try:
                    if pk is None:
                        continue
                    try:
                        container.delete_item(item=item_id, partition_key=pk)
                        logger.info(f"✓ Deleted score {score_id} from Cosmos DB (partition key: {pk})")
                        return {"status": "ok", "message": "Score deleted"}
                    except Exception as del_err:
                        logger.debug(f"Delete with partition key '{pk}' failed: {del_err}")
                        continue
                
                # If all partition key attempts failed, log error
                logger.error(f"Could not delete item {score_id} - all partition key attempts failed")
            else:
                logger.info(f"Item {score_id} not found in Cosmos DB, trying in-memory")
        except Exception as e:
            logger.error(f"Failed to query/delete from Cosmos DB: {e}")
    
    # Try in-memory deletion
    original_length = len(in_memory_leaderboard)
    
    # First try to find by id (UUID string)
    new_leaderboard = [e for e in in_memory_leaderboard if e.get("id") != score_id]
    
    if len(new_leaderboard) < original_length:
        in_memory_leaderboard = new_leaderboard
        logger.info(f"✓ Deleted score {score_id} from memory")
        return {"status": "ok", "message": "Score deleted"}
    
    # If not found by ID, try as index
    try:
        index = int(score_id)
        if 0 <= index < len(in_memory_leaderboard):
            deleted_entry = in_memory_leaderboard[index]
            del in_memory_leaderboard[index]
            logger.info(f"✓ Deleted score at index {index} ({deleted_entry.get('team_name', 'unknown')}) from memory")
            return {"status": "ok", "message": "Score deleted"}
    except ValueError:
        pass
    
    logger.warning(f"Score {score_id} not found in either Cosmos DB or memory")
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

