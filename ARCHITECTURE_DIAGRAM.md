# Memory XXL - System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     BACKEND SERVER                              │
│                   (FastAPI + WebSocket)                         │
│                    Port: 8000                                   │
│                                                                 │
│  - Manages game logic                                          │
│  - Tracks tile registration                                    │
│  - Coordinates pattern display                                 │
└────────────────────┬────────────────────────────────────────────┘
                     │ WebSocket
                     │
┌────────────────────▼────────────────────────────────────────────┐
│                   MASTER ESP32                                  │
│                (ESP-NOW + WiFi)                                 │
│                                                                 │
│  - Coordinates 4 Tile ESPs                                     │
│  - Forwards messages via ESP-NOW                               │
│  - Manages start button                                        │
│  MAC: XX:XX:XX:XX:XX:XX                                        │
└────────────────────┬────────────────────────────────────────────┘
                     │ ESP-NOW
         ┌───────────┼───────────┬───────────┐
         │           │           │           │
┌────────▼───┐ ┌────▼─────┐ ┌───▼──────┐ ┌─▼────────┐
│ TILE ESP #1│ │TILE ESP#2│ │TILE ESP#3│ │TILE ESP#4│
│            │ │          │ │          │ │          │
│ Tiles 1-4  │ │Tiles 5-8 │ │Tiles 9-12│ │Tiles13-16│
└────────────┘ └──────────┘ └──────────┘ └──────────┘
     │              │            │            │
     │              │            │            │
┌────▼────┐    ┌───▼────┐  ┌───▼────┐  ┌───▼────┐
│ TILE 1  │    │ TILE 5 │  │ TILE 9 │  │ TILE 13│
│ Switch 1│    │Switch 1│  │Switch 1│  │Switch 1│
│ LED 1   │    │LED 1   │  │LED 1   │  │LED 1   │
└─────────┘    └────────┘  └────────┘  └────────┘
┌─────────┐    ┌────────┐  ┌────────┐  ┌────────┐
│ TILE 2  │    │ TILE 6 │  │ TILE 10│  │ TILE 14│
│ Switch 2│    │Switch 2│  │Switch 2│  │Switch 2│
│ LED 2   │    │LED 2   │  │LED 2   │  │LED 2   │
└─────────┘    └────────┘  └────────┘  └────────┘
┌─────────┐    ┌────────┐  ┌────────┐  ┌────────┐
│ TILE 3  │    │ TILE 7 │  │ TILE 11│  │ TILE 15│
│ Switch 3│    │Switch 3│  │Switch 3│  │Switch 3│
│ LED 3   │    │LED 3   │  │LED 3   │  │LED 3   │
└─────────┘    └────────┘  └────────┘  └────────┘
┌─────────┐    ┌────────┐  ┌────────┐  ┌────────┐
│ TILE 4  │    │ TILE 8 │  │ TILE 12│  │ TILE 16│
│ Switch 4│    │Switch 4│  │Switch 4│  │Switch 4│
│ LED 4   │    │LED 4   │  │LED 4   │  │LED 4   │
└─────────┘    └────────┘  └────────┘  └────────┘
```

## Communication Flow

### 1. Startup & Registration

```
[Tile ESP] ──── ESP Register (Type 0) ───→ [Master ESP]
[Master ESP] ─── ESP Confirm (Cmd 3) ────→ [Tile ESP]
[Tile ESP] ──── Heartbeat (Type 3) ──────→ [Master ESP]
[Master ESP] ─── System Status ──────────→ [Backend]
[Backend] ────── Status Update ──────────→ [Frontend]
```

### 2. Tile Registration (User Steps on Tile)

```
[User Steps on Tile]
      │
      ▼
[Tile ESP] ──── Tile Register (Type 1) ──→ [Master ESP]
[Master ESP] ─── System Status ──────────→ [Backend]
[Backend] ────── Status Update ──────────→ [Frontend]
[Frontend] ───── Shows tile as registered
```

### 3. Game Start

```
[Frontend] ────── Start Game ─────────────→ [Backend]
[Backend] ─────── Show Pattern ───────────→ [Master ESP]
[Master ESP] ──── Light On (Cmd 1) ───────→ [Tile ESPs]
[Tile ESPs] ───── Turn on LEDs
```

### 4. Player Input

```
[User Steps on Tile]
      │
      ▼
[Tile ESP] ──── Tile Step (Type 2) ──────→ [Master ESP]
[Master ESP] ─── Player Step ─────────────→ [Backend]
[Backend] ────── Validates step
      │
      ├─ Correct ──→ Continue/Next Round
      └─ Wrong ────→ End Game
```

## Message Types

### ESP-NOW Messages (Tile ESP ↔ Master ESP)

**Tile ESP → Master:**

- **Type 0**: ESP Registration
- **Type 1**: Tile Registration (user stepped on tile)
- **Type 2**: Tile Step (during game)
- **Type 3**: Heartbeat (keep-alive)

**Master → Tile ESP:**

- **Cmd 0**: Turn OFF tile LEDs
- **Cmd 1**: Turn ON tile LEDs
- **Cmd 2**: Blink tile LEDs
- **Cmd 3**: Confirm ESP/Tile registration

### WebSocket Messages (Master ESP ↔ Backend)

**Master → Backend:**

```json
{
  "event": "master_connected",
  "data": {"master_id": "master", "architecture": "4-ESP"}
}

{
  "event": "system_status",
  "data": {
    "tile_esps": [...],
    "tiles": [...],
    "summary": {...}
  }
}

{
  "event": "player_step",
  "data": {"tile_id": 5, "timestamp": 12345}
}
```

**Backend → Master:**

```json
{
  "event": "show_pattern",
  "data": {"pattern": [1, 5, 9], "duration": 800}
}

{
  "event": "light_tile",
  "data": {"tile_id": 5, "on": true}
}

{
  "event": "end_game",
  "data": {}
}
```

## Pin Mapping Reference

### Tile ESP #1 (Tiles 1-4)

```
GPIO 33 → Switch 1 → Tile 1
GPIO 32 → Switch 2 → Tile 2
GPIO 35 → Switch 3 → Tile 3
GPIO 34 → Switch 4 → Tile 4

GPIO 13 → LED Strip 1 → Tile 1 (12 LEDs)
GPIO 12 → LED Strip 2 → Tile 2 (12 LEDs)
GPIO 14 → LED Strip 3 → Tile 3 (12 LEDs)
GPIO 27 → LED Strip 4 → Tile 4 (12 LEDs)
```

### Tile ESP #2 (Tiles 5-8)

Same pin layout, different TILE_ESP_ID in code

### Tile ESP #3 (Tiles 9-12)

Same pin layout, different TILE_ESP_ID in code

### Tile ESP #4 (Tiles 13-16)

Same pin layout, different TILE_ESP_ID in code

### Master ESP

```
GPIO 15 → Start Button (INPUT_PULLUP)
GPIO 2  → Status LED
```

## State Machine

### Tile ESP States

```
[POWER ON]
    │
    ▼
[INITIALIZING] ─→ WiFi Setup
    │              ESP-NOW Setup
    │              LED Setup
    ▼
[REGISTERING] ─→ Send ESP registration
    │              Wait for confirmation
    │
    ▼
[REGISTERED] ─→ ESP confirmed
    │             Waiting for tile registrations
    │
    ▼
[TILE_REGISTRATION_MODE]
    │
    ├─→ User steps on tile
    │     ├─→ Blue flash
    │     └─→ Send tile registration
    │
    ▼
[READY] ─→ All tiles registered
    │        Ready for game
    │
    ▼
[PLAYING] ─→ Handle tile steps
              Send to master
```

### Master ESP States

```
[POWER ON]
    │
    ▼
[CONNECTING] ─→ WiFi connection
    │            ESP-NOW setup
    │            WebSocket connection
    ▼
[WAITING_FOR_TILE_ESPS]
    │
    ▼
[ACTIVE] ─→ Receive ESP registrations
    │        Forward tile registrations
    │        Handle game commands
    │        Monitor heartbeats
    │
    ▼
[GAME_ACTIVE] ─→ Show patterns
                  Forward player steps
                  Control tile LEDs
```

## Network Configuration

**ESP-NOW Channel**: 6  
**WiFi Mode**: STA (Station)  
**WebSocket Port**: 8000

**Timeout Values:**

- ESP-NOW: 20 seconds
- WebSocket: 5 seconds reconnect
- Heartbeat: 5 seconds interval
- Debounce: 50 milliseconds

## LED Colors

- **White**: Startup animation
- **Cyan**: Sequential startup
- **Green**: Normal game state (tile ON)
- **Blue**: Tile registered successfully
- **Yellow**: Blink command
- **Off**: Tile OFF or not registered
