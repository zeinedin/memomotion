# Memory XXL - 4-ESP Switch-Based Architecture

## 🎯 Overview

This system uses 4 Tile ESPs instead of 16, with each ESP managing 4 tiles using switches (not touch sensors). The tiles must be registered by the user before playing.

### Architecture

- **4 Tile ESPs**: Each controls 4 tiles (16 total)
- **1 Master ESP**: Coordinates all Tile ESPs via ESP-NOW
- **Switch-based**: Physical switches instead of touch sensors
- **Registration System**: User steps on each tile to register it

## 📋 Tile Mapping

| ESP    | Tiles   | IDs            |
| ------ | ------- | -------------- |
| ESP #1 | 4 tiles | 1, 2, 3, 4     |
| ESP #2 | 4 tiles | 5, 6, 7, 8     |
| ESP #3 | 4 tiles | 9, 10, 11, 12  |
| ESP #4 | 4 tiles | 13, 14, 15, 16 |

## 🔧 Hardware Setup

### Tile ESP (4 tiles each)

**Required Components per ESP:**

- 1x ESP32 DevKit
- 4x Switches (normally open, with pullup resistor support)
- 4x LED strips (12 LEDs each)
- Power supply

**Pin Configuration:**

```cpp
// Switches (INPUT_PULLUP)
SWITCH_PIN_1 = 33  // Tile 1/5/9/13
SWITCH_PIN_2 = 32  // Tile 2/6/10/14
SWITCH_PIN_3 = 35  // Tile 3/7/11/15
SWITCH_PIN_4 = 34  // Tile 4/8/12/16

// LED Strips (NeoPixel)
LED_PIN_1 = 13     // Tile 1/5/9/13
LED_PIN_2 = 12     // Tile 2/6/10/14
LED_PIN_3 = 14     // Tile 3/7/11/15
LED_PIN_4 = 27     // Tile 4/8/12/16
```

**IMPORTANT Configuration:**

- In `tile_esp_4tiles.ino`, set `TILE_ESP_ID`:
  - ESP #1: `#define TILE_ESP_ID 1`
  - ESP #2: `#define TILE_ESP_ID 2`
  - ESP #3: `#define TILE_ESP_ID 3`
  - ESP #4: `#define TILE_ESP_ID 4`

### Master ESP

**Required Components:**

- 1x ESP32 DevKit
- 1x Start button (INPUT_PULLUP)
- 1x Status LED
- WiFi connection

**Pin Configuration:**

```cpp
START_BUTTON_PIN = 15
STATUS_LED_PIN = 2
```

## 📡 Software Setup

### 1. Firmware Installation

#### Tile ESPs

1. Open `Firmware/tile_esp_4tiles/tile_esp_4tiles.ino`
2. Set `TILE_ESP_ID` (1, 2, 3, or 4)
3. Update `masterMAC[]` with your Master ESP's MAC address
4. Upload to ESP32
5. Repeat for all 4 Tile ESPs

#### Master ESP

1. Open `Firmware/master_4ESP_ARCHITECTURE/master_4ESP_ARCHITECTURE.ino`
2. Update WiFi credentials:
   ```cpp
   const char* WIFI_SSID = "YourSSID";
   const char* WIFI_PASSWORD = "YourPassword";
   const char* WS_HOST = "YourBackendIP";
   ```
3. Upload to ESP32
4. Note the MAC address from Serial Monitor

### 2. Backend Setup

1. Navigate to backend folder:

   ```bash
   cd backend
   ```

2. Install dependencies:

   ```bash
   pip install fastapi uvicorn websockets python-multipart
   ```

3. Run backend:

   ```bash
   python main_4esp.py
   ```

4. Backend will start on `http://0.0.0.0:8000`

### 3. Frontend Access

Open browser and navigate to:

```
http://YOUR_BACKEND_IP:8000/index_4esp.html
```

Or for local development:

```
http://localhost:8000/index_4esp.html
```

## 🎮 Usage Workflow

### Step 1: System Startup

1. Power on all 4 Tile ESPs
2. Power on Master ESP
3. Start backend server
4. Open frontend in browser

### Step 2: ESP Registration

- Each Tile ESP will automatically register with Master
- Watch Serial Monitor for confirmation:
  ```
  ✓ Tile ESP #1 connected (Total: 1/4)
  ✓ Tile ESP #2 connected (Total: 2/4)
  ✓ Tile ESP #3 connected (Total: 3/4)
  ✓ Tile ESP #4 connected (Total: 4/4)
  ```
- Frontend shows ESP status in real-time

### Step 3: Tile Registration

⚠️ **IMPORTANT**: Tiles must be registered before playing!

1. Each Tile ESP enters "Registration Mode" after connecting
2. Frontend displays registration status
3. **Step on each tile** to register it:
   - Tile flashes **BLUE** when registered
   - Frontend updates in real-time
   - Must register at least 2 tiles to play

4. Registration Progress:
   - Green tile indicator = Registered ✓
   - Gray tile indicator = Not registered
   - Progress bar shows overall status

### Step 4: Start Game

1. Once at least 2 tiles are registered, "Start Game" button enables
2. Click "Start Game"
3. Game begins with registered tiles only

### Step 5: Reset Registration (if needed)

- Click "Reset Registration" button
- All tiles must be stepped on again

## 🔍 Troubleshooting

### Tile ESP not connecting

1. Check MAC address in code
2. Verify WiFi channel (should be 6)
3. Check ESP-NOW initialization in Serial Monitor
4. Ensure both ESPs on same WiFi channel

### Tile not registering

1. Check switch connection
2. Verify pin configuration matches hardware
3. Check debounce settings
4. Look for Serial output when stepping

### Master not receiving data

1. Check WebSocket connection in browser console
2. Verify backend IP in Master firmware
3. Check WiFi credentials
4. Monitor Master Serial output for ESP-NOW messages

### Frontend not updating

1. Check WebSocket connection (F12 → Console)
2. Verify backend is running
3. Check CORS settings if accessing remotely
4. Clear browser cache

## 📊 System Messages

### ESP-NOW Messages

**From Tile ESP to Master:**

- Type 0: ESP registration
- Type 1: Tile registration
- Type 2: Tile step (during game)
- Type 3: Heartbeat

**From Master to Tile ESP:**

- Command 0: Turn off tile
- Command 1: Turn on tile
- Command 2: Blink tile
- Command 3: Confirm registration

### WebSocket Messages

**Master to Backend:**

- `master_connected`: Initial connection
- `system_status`: Full system update
- `player_step`: Tile was stepped on

**Backend to Master:**

- `show_pattern`: Display pattern
- `light_tile`: Control specific tile
- `end_game`: Turn off all tiles
- `reset_registration`: Clear registrations

## 📁 File Structure

```
memomotion/
├── Firmware/
│   ├── tile_esp_4tiles/
│   │   └── tile_esp_4tiles.ino          # NEW: Tile ESP firmware
│   └── master_4ESP_ARCHITECTURE/
│       └── master_4ESP_ARCHITECTURE.ino # NEW: Master firmware
├── backend/
│   └── main_4esp.py                     # NEW: Backend with registration
├── static/
│   └── index_4esp.html                  # NEW: Frontend with registration UI
└── SETUP_4ESP.md                        # This file
```

## 🎯 Key Features

### Switch Detection

- Uses INPUT_PULLUP resistors
- Debounced (50ms)
- Reliable press detection
- LOW = pressed, HIGH = released

### Tile Registration

- First press registers tile
- Visual feedback (blue flash)
- Persistent until reset
- Required before gameplay

### ESP-NOW Communication

- Low latency (<10ms)
- Reliable delivery
- Heartbeat every 5 seconds
- Auto-reconnect on disconnect

### WebSocket Updates

- Real-time frontend updates
- Connection status monitoring
- Automatic reconnection
- Bi-directional communication

## 💡 Tips

1. **Label Your ESPs**: Physically label each ESP with its ID
2. **Test Individually**: Test each Tile ESP before final assembly
3. **Check Wiring**: Verify all switch and LED connections
4. **Monitor Serial**: Keep Serial Monitor open during setup
5. **Registration First**: Always register tiles before starting game
6. **Network Stability**: Use stable WiFi network for best performance

## 🔋 Power Considerations

- Each LED strip draws ~720mA at full brightness (12 LEDs × 60mA)
- 4 strips per ESP = ~2.88A max
- Use appropriate power supply (5V, 3-5A recommended per ESP)
- Consider power injection for longer LED strips

## 🚀 Future Enhancements

- Battery level monitoring
- Wireless power detection
- Tile health diagnostics
- Auto-calibration for switches
- Mobile app for configuration
- OTA firmware updates

## 📝 Notes

- ESP-NOW range: ~200m line-of-sight
- WiFi channel must match between Master and Tile ESPs
- Backend can run on Raspberry Pi, laptop, or server
- Frontend is responsive and mobile-friendly
- System supports up to 16 simultaneous players (1 per tile)

---

**Version**: 1.0  
**Last Updated**: January 22, 2026  
**Architecture**: 4-ESP with Switch-based Registration
