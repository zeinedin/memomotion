"""
Memory XXL Backend - VISUAL PATTERN VERSION
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import random

app = FastAPI(title="Memory XXL Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GameState:
    def __init__(self):
        self.master_ws: Optional[WebSocket] = None
        self.frontend_connections: List[WebSocket] = []
        self.tiles: Dict[int, dict] = {} 
        self.pattern: List[int] = []
        self.player_progress = 0
        self.round_score = 0
        self.game_active = False

state = GameState()

@app.websocket("/ws/master")
async def master_websocket(websocket: WebSocket):
    await websocket.accept()
    print("→ Master connected")
    try:
        state.master_ws = websocket
        while True:
            data = await websocket.receive_json()
            event = data.get("event")
            
            if event == "master_connected":
                print("✓ Master Registered")
                await broadcast({"event": "master_status", "data": {"connected": True}})
                
            elif event == "start_button_pressed":
                print("→ START BUTTON!")
                if not state.game_active:
                    await start_new_game()
                else:
                    # If button clicked while playing, maybe reset or check?
                    # For now, let's restart a new game
                    print("→ Restarting Game")
                    await start_new_game()

            elif event == "tile_status":
                # Save tile info
                tiles = data.get("data", {}).get("tiles", [])
                for t in tiles:
                    state.tiles[t["id"]] = {"connected": t["connected"]}
                await broadcast({"event": "tile_update", "data": state.tiles})
                
            elif event == "player_step":
                await handle_step(data.get("data", {}))

    except Exception as e:
        print(f"Master Error: {e}")
        state.master_ws = None
        state.game_active = False

@app.websocket("/ws/frontend")
async def frontend_websocket(websocket: WebSocket):
    await websocket.accept()
    state.frontend_connections.append(websocket)
    # Send current state immediately
    await websocket.send_json({
        "event": "init", 
        "data": {"tiles": state.tiles, "game_active": state.game_active}
    })
    try:
        while True: await websocket.receive_text() # Keep alive
    except:
        state.frontend_connections.remove(websocket)

async def start_new_game():
    # 1. Check for tiles
    connected = [tid for tid, t in state.tiles.items() if t["connected"]]
    if len(connected) < 1:
        print("✗ No tiles connected!")
        return

    # 2. Reset State
    state.game_active = True
    state.player_progress = 0
    state.round_score = 0
    
    # 3. Generate Pattern
    # Creates a random pattern of 3 steps
    state.pattern = [random.choice(connected) for _ in range(3)]
    print(f"✓ New Pattern: {state.pattern}")

    # 4. Show on Website (Frontend)
    await broadcast({
        "event": "show_pattern_web",
        "data": {
            "pattern": state.pattern,
            "message": "Memorize this pattern!"
        }
    })

    # 5. Show on Physical Tiles (Master)
    if state.master_ws:
        await state.master_ws.send_json({
            "event": "show_pattern",
            "data": {"pattern": state.pattern}
        })

async def handle_step(data):
    if not state.game_active: return
    
    tile_id = data.get("tile_id")
    expected = state.pattern[state.player_progress]
    
    print(f"Step: {tile_id} (Expected: {expected})")

    if tile_id == expected:
        # Correct Step
        state.player_progress += 1
        await broadcast({"event": "step_correct", "data": {"tile_id": tile_id}})
        
        # Win Condition
        if state.player_progress >= len(state.pattern):
            print("✓ Round Won!")
            await broadcast({"event": "game_won", "data": {"score": 100}})
            state.game_active = False
    else:
        # Wrong Step
        print("✗ Wrong Tile!")
        await broadcast({"event": "step_wrong", "data": {"tile_id": tile_id}})
        state.game_active = False # Game Over on first mistake

async def broadcast(msg):
    for ws in state.frontend_connections:
        try: await ws.send_json(msg)
        except: pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)