"""
Memory XXL Backend - TESTING VERSION
January 15, 2026

Features:
- Team registration with levels
- Leaderboard with Azure Cosmos DB
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
import os
import uuid

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Azure Cosmos DB imports
from azure.cosmos import CosmosClient, PartitionKey, exceptions

app = FastAPI(title="Memory XXL Backend")

# ==================== COSMOS DB ====================
# Configuration - Set these environment variables in .env file
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT", "https://your-account.documents.azure.com:443/")
COSMOS_KEY = os.getenv("COSMOS_KEY", "your-primary-key-here")
COSMOS_DATABASE = os.getenv("COSMOS_DATABASE", "memomotion")
COSMOS_CONTAINER = os.getenv("COSMOS_CONTAINER", "leaderboard")

# Global Cosmos DB clients
cosmos_client = None
database = None
container = None
cosmos_initialized = False

def init_cosmos_db():
    """Initialize Cosmos DB connection"""
    global cosmos_client, database, container, cosmos_initialized
    
    try:
        # Check if credentials are set
        if "your-account" in COSMOS_ENDPOINT or "your-primary-key" in COSMOS_KEY:
            print("⚠️ Cosmos DB credentials not configured - set COSMOS_ENDPOINT and COSMOS_KEY environment variables")
            return False
        
        # Create the Cosmos client
        cosmos_client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
        
        # Get database reference (assumes database exists)
        database = cosmos_client.get_database_client(COSMOS_DATABASE)
        
        # Get container reference (assumes container exists)
        container = database.get_container_client(COSMOS_CONTAINER)
        
        # Test connection by reading container properties
        container.read()
        
        cosmos_initialized = True
        print("✓ Cosmos DB connected successfully")
        print(f"  Database: {COSMOS_DATABASE}")
        print(f"  Container: {COSMOS_CONTAINER}")
        return True
        
    except exceptions.CosmosHttpResponseError as e:
        print(f"✗ Cosmos DB connection failed: {e.message}")
        return False
    except Exception as e:
        print(f"✗ Cosmos DB error: {e}")
        return False

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
        self.game_phase: str = "idle"  # idle, showing_pattern, selecting, checking
        self.pattern: List[int] = []
        self.player_steps: List[int] = []
        self.selected_tiles: set = set()  # Tiles currently selected by player (toggle mode)
        
        # Team info
        self.current_team: str = ""
        self.current_level: str = "easy"
        self.score_submitted: bool = False  # Prevent duplicate score submissions
        
        self.games_played = 0
        self.high_score = 0
        self.current_score = 0
        self.round_number = 0
        self.start_time = None

# Level configurations
# Scoring: correct = round_number * level_multiplier * 10
# Wrong = -15 penalty (but score cannot go below 0)
LEVEL_CONFIG = {
    "easy": {"pattern_length": 1, "level_multiplier": 1, "base_points": 20},
    "medium": {"pattern_length": 3, "level_multiplier": 2, "base_points": 30},
    "hard": {"pattern_length": 5, "level_multiplier": 3, "base_points": 50}
}

WRONG_PENALTY = 15  # Points deducted for wrong answer

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

@app.get("/api/cosmos-status")
async def get_cosmos_status():
    """Debug endpoint to check Cosmos DB connection status"""
    return {
        "cosmos_initialized": cosmos_initialized,
        "endpoint_configured": "your-account" not in COSMOS_ENDPOINT,
        "key_configured": "your-primary-key" not in COSMOS_KEY,
        "database": COSMOS_DATABASE,
        "container": COSMOS_CONTAINER,
        "endpoint_prefix": COSMOS_ENDPOINT[:50] + "..." if len(COSMOS_ENDPOINT) > 50 else COSMOS_ENDPOINT
    }

# ==================== LEADERBOARD API (Cosmos DB) ====================
@app.get("/api/leaderboard")
async def get_leaderboard(limit: int = 10, level: Optional[str] = None):
    """Get leaderboard entries from Cosmos DB"""
    if not cosmos_initialized:
        print("⚠️ Leaderboard request but Cosmos DB not initialized!")
        return {"leaderboard": [], "error": "Database not connected", "cosmos_initialized": False}
    
    try:
        # Build query - order by score descending
        if level:
            query = f"SELECT * FROM c WHERE c.level = @level ORDER BY c.score DESC OFFSET 0 LIMIT {limit}"
            parameters = [{"name": "@level", "value": level}]
        else:
            query = f"SELECT * FROM c ORDER BY c.score DESC OFFSET 0 LIMIT {limit}"
            parameters = []
        
        print(f"📊 Querying leaderboard: {query}")
        
        # Execute query (cross-partition since we use /id as partition key)
        items = list(container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
        
        print(f"📊 Found {len(items)} items")
        
        # Format response (remove Cosmos DB internal fields)
        leaderboard = [
            {
                "id": item.get("id"),
                "team_name": item.get("team_name"),
                "score": item.get("score"),
                "level": item.get("level"),
                "rounds": item.get("rounds", 0),
                "created_at": item.get("created_at")
            }
            for item in items
        ]
        
        return {"leaderboard": leaderboard}
        
    except Exception as e:
        print(f"✗ Error fetching leaderboard: {e}")
        return {"leaderboard": [], "error": str(e)}

@app.get("/api/leaderboard/check-name")
async def check_team_name(name: str):
    """Check if a team name already exists in the leaderboard"""
    if not cosmos_initialized:
        return {"exists": False, "error": "Database not connected"}
    
    try:
        query = "SELECT VALUE COUNT(1) FROM c WHERE LOWER(c.team_name) = LOWER(@name)"
        parameters = [{"name": "@name", "value": name.strip()}]
        
        result = list(container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
        
        count = result[0] if result else 0
        return {"exists": count > 0}
        
    except Exception as e:
        print(f"✗ Error checking team name: {e}")
        return {"exists": False, "error": str(e)}

@app.post("/api/leaderboard")
async def add_score(entry: ScoreEntry):
    """Add a new score to Cosmos DB leaderboard"""
    if not cosmos_initialized:
        return {"status": "error", "message": "Database not connected"}
    
    try:
        # Create document with unique ID
        item = {
            "id": str(uuid.uuid4()),  # Unique ID (also partition key)
            "team_name": entry.team_name,
            "score": entry.score,
            "level": entry.level,
            "rounds": entry.rounds,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Insert into Cosmos DB
        container.create_item(body=item)
        
        print(f"✓ Score saved to Cosmos DB: {entry.team_name} - {entry.score} ({entry.level})")
        
        return {"status": "ok", "message": "Score saved", "id": item["id"]}
        
    except exceptions.CosmosHttpResponseError as e:
        print(f"✗ Cosmos DB error: {e.message}")
        return {"status": "error", "message": e.message}
    except Exception as e:
        print(f"✗ Error saving score: {e}")
        return {"status": "error", "message": str(e)}

@app.delete("/api/leaderboard")
async def clear_leaderboard():
    """Clear all leaderboard entries (admin) - Use with caution!"""
    if not cosmos_initialized:
        return {"status": "error", "message": "Database not connected"}
    
    try:
        # Query all items
        items = list(container.query_items(
            query="SELECT c.id FROM c",
            enable_cross_partition_query=True
        ))
        
        deleted_count = 0
        for item in items:
            # Delete each item (partition key is the id)
            container.delete_item(item=item["id"], partition_key=item["id"])
            deleted_count += 1
        
        print(f"✓ Cleared {deleted_count} entries from leaderboard")
        return {"status": "ok", "message": f"Cleared {deleted_count} entries"}
        
    except Exception as e:
        print(f"✗ Error clearing leaderboard: {e}")
        return {"status": "error", "message": str(e)}

# ==================== ADMIN ROUTES ====================
@app.get("/admin")
async def admin_page():
    """Serve admin dashboard"""
    return FileResponse('static/admin.html')

@app.get("/api/admin/tiles")
async def get_tiles_status():
    """Get all tiles status for admin"""
    tiles = [
        {"id": tile_id, "connected": info.get("connected", False), "battery": info.get("battery", 0)}
        for tile_id, info in state.tiles.items()
    ]
    return {"tiles": sorted(tiles, key=lambda x: x["id"])}

@app.get("/api/admin/config")
async def get_config():
    """Get current game configuration"""
    return {
        "levels": {
            "easy": {"steps": LEVEL_CONFIG["easy"]["pattern_length"], "multiplier": LEVEL_CONFIG["easy"]["level_multiplier"], "base": LEVEL_CONFIG["easy"]["base_points"]},
            "medium": {"steps": LEVEL_CONFIG["medium"]["pattern_length"], "multiplier": LEVEL_CONFIG["medium"]["level_multiplier"], "base": LEVEL_CONFIG["medium"]["base_points"]},
            "hard": {"steps": LEVEL_CONFIG["hard"]["pattern_length"], "multiplier": LEVEL_CONFIG["hard"]["level_multiplier"], "base": LEVEL_CONFIG["hard"]["base_points"]}
        },
        "wrongPenalty": WRONG_PENALTY,
        "scoringFormula": "points = (round * level_multiplier * 10) + base_points"
    }

@app.post("/api/admin/config/levels")
async def update_level_config(config: dict):
    """Update level configuration"""
    global LEVEL_CONFIG
    
    if "easy" in config:
        LEVEL_CONFIG["easy"]["pattern_length"] = config["easy"].get("steps", 1)
        LEVEL_CONFIG["easy"]["level_multiplier"] = config["easy"].get("multiplier", 1)
        LEVEL_CONFIG["easy"]["base_points"] = config["easy"].get("base", 20)
    if "medium" in config:
        LEVEL_CONFIG["medium"]["pattern_length"] = config["medium"].get("steps", 3)
        LEVEL_CONFIG["medium"]["level_multiplier"] = config["medium"].get("multiplier", 2)
        LEVEL_CONFIG["medium"]["base_points"] = config["medium"].get("base", 30)
    if "hard" in config:
        LEVEL_CONFIG["hard"]["pattern_length"] = config["hard"].get("steps", 5)
        LEVEL_CONFIG["hard"]["level_multiplier"] = config["hard"].get("multiplier", 3)
        LEVEL_CONFIG["hard"]["base_points"] = config["hard"].get("base", 50)
    
    print(f"✓ Level config updated: {LEVEL_CONFIG}")
    return {"status": "ok", "config": LEVEL_CONFIG}

@app.post("/api/admin/config/speedrun")
async def update_speedrun_config(config: dict):
    """Update speed run configuration"""
    # Store in state for now (could be persisted to DB)
    state.speedrun_time_per_step = config.get("timePerStep", 3)
    state.speedrun_bonus = config.get("bonusPerSecond", 2)
    
    print(f"✓ Speed run config updated: {config}")
    return {"status": "ok"}

@app.delete("/api/admin/leaderboard/{score_id}")
async def delete_single_score(score_id: str):
    """Delete a single score from leaderboard by ID"""
    if not cosmos_initialized:
        return {"status": "error", "message": "Database not connected"}
    
    try:
        # In Cosmos DB with /id as partition key, the id is also the partition key
        container.delete_item(item=score_id, partition_key=score_id)
        print(f"✓ Score {score_id} deleted")
        return {"status": "ok", "message": f"Score {score_id} deleted"}
    except exceptions.CosmosResourceNotFoundError:
        return {"status": "error", "message": "Score not found"}
    except Exception as e:
        print(f"✗ Error deleting score: {e}")
        return {"status": "error", "message": str(e)}

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
    
    elif event == "confirm_button_pressed":
        print("→ CONFIRM button pressed!")
        await handle_confirm_button()
    
    elif event == "player_step":
        await handle_tile_toggle(data)
    
    elif event == "tile_touched" or event == "tile_pressed":
        # Tile was touched/pressed - handle as toggle in selecting phase
        tile_id = data.get("tile_id")
        print(f"  Tile {tile_id} touched!")
        
        # If game is in selecting phase, handle as toggle
        if state.game_phase == "selecting":
            await handle_tile_toggle(data)
        else:
            # Just visual feedback outside of selecting phase
            await broadcast_to_frontends({
                "event": "tile_pressed",
                "data": {
                    "tile_id": tile_id,
                    "timestamp": data.get("timestamp", 0)
                }
            })
    
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
    # Handle both 'event' and 'type' formats from frontend
    event = msg.get("event") or msg.get("type")
    data = msg.get("data", {})
    
    # If data is empty, use the message itself (flat format from frontend)
    if not data:
        data = msg
    
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
        # Register team and level (handle both nested and flat formats)
        state.current_team = data.get("team_name", msg.get("team_name", "Team"))
        state.current_level = data.get("level", msg.get("level", "easy"))
        state.current_score = 0
        state.round_number = 0
        state.game_phase = "idle"
        state.player_steps = []
        state.pattern = []
        state.score_submitted = False  # Reset for new game
        print(f"→ New game registered: {state.current_team} ({state.current_level})")
        
        # Send confirmation to frontend
        await websocket.send_json({
            "event": "game_registered",
            "data": {
                "team_name": state.current_team,
                "level": state.current_level,
                "message": "Press START on the master to begin!"
            }
        })

# ==================== GAME LOGIC ====================
async def handle_start_button():
    """Handle START button press - starts a new round"""
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
        # Start a new round - show pattern
        await start_show_pattern(connected_tiles)
    elif state.game_phase == "selecting":
        # START button during selecting phase = CONFIRM selection
        print("  START pressed during selecting - treating as CONFIRM")
        await handle_confirm_button()
    else:
        # In any other phase, ignore
        print(f"  START pressed during {state.game_phase} - ignoring")

async def start_show_pattern(connected_tiles: List[int]):
    """Generate and show pattern - all tiles at once for 8 seconds"""
    print("→ Showing pattern for 8 seconds...")
    
    state.game_phase = "showing_pattern"
    state.player_steps = []
    state.selected_tiles = set()  # Clear selected tiles
    state.round_number += 1
    
    # Get pattern length from level config + round progression
    # Pattern grows by 1 each round: base + (round - 1)
    level_config = LEVEL_CONFIG.get(state.current_level, LEVEL_CONFIG["easy"])
    base_pattern = level_config["pattern_length"]
    pattern_length = base_pattern + (state.round_number - 1)
    # Cap at number of connected tiles
    pattern_length = min(pattern_length, len(connected_tiles))
    
    # Generate pattern (unique tiles)
    state.pattern = random.sample(connected_tiles, pattern_length)
    
    print(f"  Pattern: {state.pattern} (Level: {state.current_level}, Round: {state.round_number}, Size: {pattern_length})")
    
    # Tell frontend - show all pattern tiles at once
    await broadcast_to_frontends({
        "event": "game_started",
        "data": {
            "phase": "showing_pattern",
            "pattern": state.pattern,
            "message": f"Ronde {state.round_number}",
            "round": state.round_number,
            "display_mode": "simultaneous"  # New flag for simultaneous display
        }
    })
    
    # Tell master to show ALL pattern tiles at once for 8 seconds
    if state.master_ws:
        await state.master_ws.send_json({
            "event": "show_pattern_simultaneous",
            "data": {
                "pattern": state.pattern,
                "duration": 8000  # 8 seconds in milliseconds
            }
        })
    
    # Wait 8 seconds for pattern display
    await asyncio.sleep(8)
    
    # Enter selecting phase - player can now toggle tiles
    state.game_phase = "selecting"
    
    # Turn off pattern tiles on master
    if state.master_ws:
        await state.master_ws.send_json({
            "event": "pattern_hide",
            "data": {}
        })
    
    await broadcast_to_frontends({
        "event": "selecting_phase",
        "data": {
            "pattern_length": len(state.pattern),
            "message": "Selecteer de juiste tegels!"
        }
    })

async def handle_tile_toggle(data: dict):
    """Player stepped on a tile - toggle selection on/off"""
    tile_id = data.get("tile_id")
    
    if tile_id is None:
        print("  Toggle ignored (no tile_id)")
        return
    
    if state.game_phase != "selecting":
        print(f"  Toggle ignored (wrong phase: {state.game_phase})")
        return
    
    # Use LED state from tile if provided (more accurate), otherwise toggle
    if "is_on" in data:
        # Trust the tile's LED state (tile is authoritative)
        is_selected = data.get("is_on", False)
        if is_selected:
            state.selected_tiles.add(tile_id)
        else:
            state.selected_tiles.discard(tile_id)
        print(f"  Tile {tile_id} {'SELECTED' if is_selected else 'DESELECTED'} (from tile, total: {len(state.selected_tiles)})")
    else:
        # Fallback: Toggle tile selection
        if tile_id in state.selected_tiles:
            state.selected_tiles.remove(tile_id)
            is_selected = False
            print(f"  Tile {tile_id} DESELECTED (total: {len(state.selected_tiles)})")
        else:
            state.selected_tiles.add(tile_id)
            is_selected = True
            print(f"  Tile {tile_id} SELECTED (total: {len(state.selected_tiles)})")
        
        # Tell master to toggle LED on tile (only if we calculated the toggle)
        if state.master_ws:
            await state.master_ws.send_json({
                "event": "toggle_tile",
                "data": {
                    "tile_id": tile_id,
                    "on": is_selected
                }
            })
    
    # Broadcast to frontend
    await broadcast_to_frontends({
        "event": "tile_toggled",
        "data": {
            "tile_id": tile_id,
            "is_selected": is_selected,
            "selected_tiles": list(state.selected_tiles),
            "total_selected": len(state.selected_tiles),
            "expected_count": len(state.pattern)
        }
    })

async def handle_confirm_button():
    """Handle CONFIRM button press - validate selected tiles"""
    if state.game_phase != "selecting":
        print(f"  CONFIRM ignored (wrong phase: {state.game_phase})")
        return
    
    print(f"→ Validating selection...")
    print(f"  Selected: {sorted(state.selected_tiles)}")
    print(f"  Pattern:  {sorted(state.pattern)}")
    
    state.game_phase = "checking"
    
    # Check if selected tiles match pattern (order doesn't matter)
    pattern_set = set(state.pattern)
    correct = state.selected_tiles == pattern_set
    
    # Get level config for scoring
    level_config = LEVEL_CONFIG.get(state.current_level, LEVEL_CONFIG["easy"])
    
    if correct:
        # Scoring: round_number * level_multiplier * 10 + base_points
        # e.g., Round 1 Easy: 1 * 1 * 10 + 20 = 30 points
        # e.g., Round 3 Hard: 3 * 3 * 10 + 50 = 140 points
        points = (state.round_number * level_config["level_multiplier"] * 10) + level_config["base_points"]
        state.current_score += points
        if state.current_score > state.high_score:
            state.high_score = state.current_score
        
        print(f"✓ CORRECT! Score: {state.current_score}")
        
        # Tell master to show success
        if state.master_ws:
            await state.master_ws.send_json({
                "event": "pattern_correct",
                "data": {}
            })
        
        await broadcast_to_frontends({
            "event": "pattern_correct",
            "data": {
                "message": "🎉 Perfect!",
                "score": state.current_score,
                "round": state.round_number,
                "points_earned": points,
                "pattern": state.pattern,
                "selected_tiles": list(state.selected_tiles)
            }
        })
        
        # Wait then reset for next round
        await asyncio.sleep(2)
        
        # Turn off all tiles
        if state.master_ws:
            await state.master_ws.send_json({
                "event": "end_game",
                "data": {}
            })
        
        # Reset for next round (keep score and round number)
        state.player_steps = []
        state.pattern = []
        state.selected_tiles = set()
        
        # Automatically start next round
        connected_tiles = [tid for tid, info in state.tiles.items() if info["connected"]]
        if len(connected_tiles) >= 2:
            await asyncio.sleep(1)  # Brief pause before next round
            await start_show_pattern(connected_tiles)
        else:
            state.game_phase = "idle"
    else:
        print(f"✗ WRONG SELECTION!")
        print(f"  Missing: {pattern_set - state.selected_tiles}")
        print(f"  Extra:   {state.selected_tiles - pattern_set}")
        await end_game_wrong_selection()

async def end_game_wrong_selection():
    """End the game when player selects wrong tiles"""
    print("→ Wrong selection - ending game...")
    state.game_phase = "game_over"
    
    # Apply penalty (score can't go below 0)
    state.current_score = max(0, state.current_score - WRONG_PENALTY)
    
    # Turn off all tiles
    if state.master_ws:
        await state.master_ws.send_json({
            "event": "end_game",
            "data": {}
        })
    
    # Update stats
    state.games_played += 1
    
    # Submit score to database from backend (only once)
    await submit_score_to_db()
    
    # Send single game_over event with all data
    await broadcast_to_frontends({
        "event": "game_over",
        "data": {
            "message": "❌ Fout! Game Over",
            "expected": state.pattern,
            "selected_tiles": list(state.selected_tiles),
            "final_score": state.current_score,
            "rounds": state.round_number,
            "team_name": state.current_team,
            "level": state.current_level,
            "penalty_applied": WRONG_PENALTY
        }
    })
    
    # Reset state
    await asyncio.sleep(2)
    state.game_phase = "idle"
    state.player_steps = []
    state.pattern = []
    state.selected_tiles = set()

# ==================== HELPERS ====================
async def submit_score_to_db():
    """Submit score to Cosmos DB - only once per game"""
    if state.score_submitted:
        print("  Score already submitted, skipping...")
        return False
    
    if not state.current_team or not state.current_team.strip():
        print("  No team name, skipping score submission...")
        return False
    
    if not cosmos_initialized:
        print("  Cosmos DB not initialized, skipping score submission...")
        return False
    
    try:
        item = {
            "id": str(uuid.uuid4()),
            "team_name": state.current_team.strip(),
            "score": state.current_score,
            "level": state.current_level,
            "rounds": state.round_number,
            "created_at": datetime.utcnow().isoformat()
        }
        
        container.create_item(body=item)
        state.score_submitted = True
        print(f"✓ Score saved: {state.current_team} - {state.current_score} ({state.current_level})")
        return True
        
    except Exception as e:
        print(f"✗ Error saving score: {e}")
        return False

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
    print("Memory XXL Backend - v2.1")
    print("January 15, 2026 - Azure Cosmos DB Edition")
    print("="*50)
    
    # Initialize Cosmos DB
    print("\n🔗 Connecting to Azure Cosmos DB...")
    init_cosmos_db()
    
    print("\n✓ Server ready")
    print(f"  Master endpoint: ws://YOUR_IP:8000/ws/master")
    print(f"  Frontend endpoint: ws://YOUR_IP:8000/ws/frontend")
    print(f"  Leaderboard API: http://YOUR_IP:8000/api/leaderboard")
    print(f"  Health check: http://YOUR_IP:8000/status")
    print("\nWaiting for connections...\n")
    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)