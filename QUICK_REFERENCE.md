# Memory XXL - Quick Reference Card

## 🎯 System Overview

- **4 Tile ESPs** (each manages 4 tiles with switches)
- **1 Master ESP** (coordinates via ESP-NOW + WebSocket)
- **1 Backend** (Python FastAPI on port 8000)
- **Total: 16 tiles** that require registration before play

---

## 📌 CRITICAL CONFIGURATION STEPS

### 1️⃣ Tile ESP Configuration

```cpp
// In tile_esp_4tiles.ino
#define TILE_ESP_ID 1  // ⚠️ CHANGE THIS: 1, 2, 3, or 4

// Update Master MAC address
uint8_t masterMAC[] = {0xXX, 0xXX, 0xXX, 0xXX, 0xXX, 0xXX};
```

### 2️⃣ Master ESP Configuration

```cpp
// In master_4ESP_ARCHITECTURE.ino
const char* WIFI_SSID = "YourWiFi";
const char* WIFI_PASSWORD = "YourPassword";
const char* WS_HOST = "192.168.x.x";  // Backend IP
```

### 3️⃣ Start Backend

```bash
cd backend
python main_4esp.py
```

### 4️⃣ Access Frontend

```
http://BACKEND_IP:8000/index_4esp.html
```

---

## 🔌 Pin Connections (Each Tile ESP)

### Switches (INPUT_PULLUP)

```
GPIO 33 → Switch for Tile 1/5/9/13
GPIO 32 → Switch for Tile 2/6/10/14
GPIO 35 → Switch for Tile 3/7/11/15
GPIO 34 → Switch for Tile 4/8/12/16
```

### LEDs (NeoPixel - 12 per tile)

```
GPIO 13 → LED Strip 1
GPIO 12 → LED Strip 2
GPIO 14 → LED Strip 3
GPIO 27 → LED Strip 4
```

### Master ESP

```
GPIO 15 → Start Button
GPIO 2  → Status LED
```

---

## 🗺️ Tile Mapping

| ESP #1 | ESP #2 | ESP #3  | ESP #4  |
| ------ | ------ | ------- | ------- |
| Tile 1 | Tile 5 | Tile 9  | Tile 13 |
| Tile 2 | Tile 6 | Tile 10 | Tile 14 |
| Tile 3 | Tile 7 | Tile 11 | Tile 15 |
| Tile 4 | Tile 8 | Tile 12 | Tile 16 |

---

## 🚀 Startup Sequence

1. ✅ Power on all 4 Tile ESPs
2. ✅ Power on Master ESP
3. ✅ Start backend server
4. ✅ Open frontend in browser
5. ✅ Wait for ESP connections (check frontend)
6. ✅ **Step on each tile to register** (blue flash)
7. ✅ Start game when ready

---

## 🎨 LED Indicators

| Color     | Meaning              |
| --------- | -------------------- |
| 🤍 White  | Startup animation    |
| 💙 Cyan   | Sequential startup   |
| 💙 Blue   | **Tile registered!** |
| 💚 Green  | Tile ON (game)       |
| 💛 Yellow | Blink                |
| ⚫ Off    | Not registered       |

---

## 🔍 Status Checks

### Serial Monitor (Master ESP)

```
✓ Master ready!
✓ WiFi connected!
✓ Tile ESP #1 connected (Total: 1/4)
✓ Tile #1 registered (Total: 1/16)
```

### Serial Monitor (Tile ESP)

```
=== TILE ESP #1 (4 Tiles) ===
Managing tiles: 1, 2, 3, 4
✓ ESP Registered with Master!
→ Registering Tile 1
```

### Browser Console (F12)

```
✓ Connected to backend
← Master: system_status
```

---

## ⚠️ Troubleshooting

### Issue: Tile ESP not connecting

```
✅ Check TILE_ESP_ID is set correctly (1-4)
✅ Verify Master MAC address in code
✅ Both ESPs on WiFi channel 6
✅ Check Serial Monitor for errors
```

### Issue: Tile not registering

```
✅ Check switch wiring (should be normally open)
✅ Verify GPIO pins match code
✅ Test switch with multimeter
✅ Check Serial output when stepping
```

### Issue: LEDs not working

```
✅ Check LED power supply (5V, 3-5A)
✅ Verify NeoPixel library installed
✅ Check LED pin connections
✅ Test with single LED strip first
```

### Issue: WebSocket disconnects

```
✅ Check WiFi signal strength
✅ Verify backend IP in Master code
✅ Restart backend server
✅ Check firewall settings
```

---

## 📊 Message Flow

```
User Steps on Tile
       ↓
[Tile ESP] → ESP-NOW → [Master ESP]
                            ↓
                       WebSocket
                            ↓
                       [Backend]
                            ↓
                       WebSocket
                            ↓
                       [Frontend]
                            ↓
                    UI Updates!
```

---

## 🎮 Registration Requirements

| Status           | Can Play? | Message               |
| ---------------- | --------- | --------------------- |
| 0/16 registered  | ❌ No     | Need at least 2 tiles |
| 1/16 registered  | ❌ No     | Need at least 2 tiles |
| 2/16 registered  | ✅ Yes    | Minimum met!          |
| 16/16 registered | ✅ Yes    | All tiles ready!      |

---

## 🔄 Reset Registration

**Frontend:**

1. Click "Reset Registration" button
2. Confirm dialog
3. All tiles marked as not registered

**All users must step on tiles again!**

---

## 📝 Installation Commands

### Arduino Libraries Required

```
- WiFi (built-in)
- esp_now (built-in)
- esp_wifi (built-in)
- WebSocketsClient (by Links2004)
- ArduinoJson (by Benoit Blanchon)
- Adafruit_NeoPixel (by Adafruit)
```

### Python Backend

```bash
pip install fastapi uvicorn websockets
python main_4esp.py
```

---

## 📞 Key File Locations

```
Firmware/
├── tile_esp_4tiles/tile_esp_4tiles.ino     ← Tile ESP
└── master_4ESP_ARCHITECTURE/               ← Master ESP
    master_4ESP_ARCHITECTURE.ino

backend/
└── main_4esp.py                            ← Backend

static/
└── index_4esp.html                         ← Frontend

SETUP_4ESP.md                               ← Full guide
ARCHITECTURE_DIAGRAM.md                     ← Diagrams
MIGRATION_SUMMARY.md                        ← Changes
```

---

## ⚡ Quick Commands

### Get Master MAC Address

```cpp
Serial.println(WiFi.macAddress());  // Add to setup()
```

### Check Backend IP

```bash
ipconfig    # Windows
ifconfig    # Linux/Mac
```

### Test WebSocket

```javascript
// Browser console
ws = new WebSocket('ws://BACKEND_IP:8000/ws/frontend');
ws.onmessage = (e) => console.log(e.data);
```

### Monitor Serial

```bash
# Arduino IDE
Tools → Serial Monitor → 115200 baud

# PlatformIO
pio device monitor
```

---

## 🎯 Success Criteria

✅ All 4 ESPs show "connected" in frontend  
✅ All 16 tiles can be registered (blue flash)  
✅ Progress bar shows 16/16  
✅ Start button is enabled  
✅ Game starts with registered tiles  
✅ Tiles respond correctly during game

---

## 💾 Backup Configuration

**Before uploading firmware, note:**

- Master ESP MAC address: `__:__:__:__:__:__`
- WiFi SSID: `________________`
- Backend IP: `___.___.___.___`
- Tile ESP IDs: 1️⃣ 2️⃣ 3️⃣ 4️⃣

---

**Version**: 1.0  
**Last Updated**: January 22, 2026  
**Print this page for quick reference!** 📄
