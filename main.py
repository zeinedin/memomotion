import sqlite3
import random
import asyncio
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List, Optional

app = FastAPI()

# Database Setup (SQLite - Automatisch aangemaakt op Azure)
DB_FILE = "scores.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS scores
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  team_name TEXT, 
                  level TEXT, 
                  score INTEGER, 
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

# Models
class TeamRegister(BaseModel):
    team_name: str
    level: str

# State
class GameState:
    def __init__(self):
        self.master_ws = None
        self.frontend_connections = []
        self.tiles = {} 
        self.pattern = []
        self.player_steps = []
        self.game_phase = "idle"
        # Huidige team info
        self.current_team = "Unknown"
        self.current_level = "Normal"
        self.current_score = 0

state = GameState()

# === API ROUTES (Voor Frontend) ===

@app.post("/api/register")
async def register_team(team: TeamRegister):
    state.current_team = team.team_name
    state.current_level = team.level
    print(f"Team registered: {team.team_name} ({team.level})")
    return {"status": "ok", "team": team.team_name}

@app.get("/api/leaderboard")
async def get_leaderboard():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Haal top 10 scores op
    c.execute("SELECT team_name, level, score FROM scores ORDER BY score DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    
    leaderboard = []
    for i, row in enumerate(rows):
        leaderboard.append({
            "rank": i + 1,
            "name": row[0],
            "level": row[1],
            "score": row[2]
        })
    return leaderboard

# === WEBSOCKETS ===

@app.websocket("/ws/master")
async def master_websocket(websocket: WebSocket):
    await websocket.accept()
    state.master_ws = websocket
    print("Master connected")
    try:
        while True:
            msg = await websocket.receive_json()
            await handle_master_message(msg)
    except:
        state.master_ws = None
        print("Master disconnected")

@app.websocket("/ws/frontend")
async def frontend_websocket(websocket: WebSocket):
    await websocket.accept()
    state.frontend_connections.append(websocket)
    try:
        while True:
            msg = await websocket.receive_json()
            if msg.get('event') == 'start_game':
                await start_game_logic()
    except:
        state.frontend_connections.remove(websocket)

async def handle_master_message(msg):
    event = msg.get('event')
    data = msg.get('data', {})
    
    if event == 'tile_status':
        # Update tegels
        for t in data.get('tiles', []):
            state.tiles[t['id']] = t
        # Stuur naar frontend
        await broadcast_frontend({
            "event": "tile_status", 
            "data": {"connected": len(state.tiles), "total": len(state.tiles)}
        })
    
    elif event == 'start_button_pressed':
        # Alleen starten als we in de Start fase zitten
        await start_game_logic()
        
    elif event == 'player_step':
        tile_id = data.get('tile_id')
        await handle_player_step(tile_id)

async def start_game_logic():
    if state.game_phase == "idle":
        print("Starting Game...")
        # 1. Genereer Patroon
        length = 4 if state.current_level == "Easy" else 6 if state.current_level == "Normal" else 8
        state.pattern = [random.choice(list(state.tiles.keys())) for _ in range(length)]
        state.player_steps = []
        state.game_phase = "showing"
        
        # 2. Toon op scherm (Frontend)
        await broadcast_frontend({
            "event": "game_started",
            "data": {
                "pattern": state.pattern,
                "message": "Watch carefully!"
            }
        })
        
        # 3. Toon op tegels (Master)
        if state.master_ws:
            await state.master_ws.send_json({
                "event": "show_pattern",
                "data": {"pattern": state.pattern}
            })
            
        # 4. Wacht even en start dan speler beurt
        await asyncio.sleep(length * 1.5)
        state.game_phase = "playing"
        await broadcast_frontend({
            "event": "memorizing_phase", 
            "data": {"message": "Your turn! Step on the tiles."}
        })

async def handle_player_step(tile_id):
    if state.game_phase != "playing": return
    
    state.player_steps.append(tile_id)
    
    # Check stap
    step_index = len(state.player_steps) - 1
    expected = state.pattern[step_index]
    
    correct = (tile_id == expected)
    
    # Feedback naar Frontend
    await broadcast_frontend({
        "event": "player_stepped",
        "data": {"tile_id": tile_id, "correct": correct}
    })
    
    if not correct:
        await end_game(won=False)
    elif len(state.player_steps) == len(state.pattern):
        await end_game(won=True)

async def end_game(won):
    state.game_phase = "idle"
    
    score = len(state.pattern) * 10 if won else 0
    if state.current_level == "Hard": score *= 2
    
    # OPSLAAN IN AZURE DATABASE (SQLite)
    if won:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO scores (team_name, level, score) VALUES (?, ?, ?)", 
                  (state.current_team, state.current_level, score))
        conn.commit()
        conn.close()
        print(f"Score saved for {state.current_team}")

    await broadcast_frontend({
        "event": "game_ended",
        "data": {
            "won": won, 
            "score": score,
            "message": "YOU WIN! 🎉" if won else "GAME OVER ❌"
        }
    })

async def broadcast_frontend(msg):
    for ws in state.frontend_connections:
        try: await ws.send_json(msg)
        except: pass

# Serveer statische bestanden (Frontend)
if not os.path.exists("static"): os.makedirs("static")
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)