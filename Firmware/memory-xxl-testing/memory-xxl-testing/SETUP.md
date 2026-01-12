# Memory XXL - Testing Setup Guide
## January 9, 2025 Demo Day

---

## 📦 What's Included

```
memory-xxl-testing/
├── firmware/
│   ├── master/
│   │   └── master_testing.ino       # Master ESP32 code
│   └── slave/
│       └── slave_testing.ino        # Slave tile code (duplicate for each tile)
├── backend/
│   ├── main.py                      # FastAPI backend
│   └── requirements.txt             # Python dependencies
├── frontend/
│   ├── index.html                   # UI
│   ├── style.css                    # Styling
│   └── app.js                       # Logic
└── SETUP.md                         # This file
```

---

## 🚀 Quick Start (Day Before Testing)

### Step 1: Hardware Preparation

#### Master ESP32:
1. Open `firmware/master/master_testing.ino` in Arduino IDE
2. **CRITICAL**: Update these lines (around line 14-16):
   ```cpp
   const char* WIFI_SSID = "YourHotspotName";      // Your iPhone/hotspot name
   const char* WIFI_PASSWORD = "YourPassword";      // Your WiFi password
   const char* WS_HOST = "192.168.X.X";            // Your laptop IP (see below)
   ```
3. Upload to Master ESP32
4. Open Serial Monitor (115200 baud)
5. **WRITE DOWN THE MAC ADDRESS** shown in Serial Monitor
6. Note the WiFi channel (e.g., "Channel: 6")

#### Slave Tiles (Repeat for each tile):
1. Open `firmware/slave/slave_testing.ino` in Arduino IDE
2. **CHANGE TILE_ID** for each tile:
   ```cpp
   #define TILE_ID 1  // Use 1, 2, 3, 4, etc. for each tile
   ```
3. **UPDATE MASTER MAC** (from Step 1.5):
   ```cpp
   uint8_t masterMAC[] = {0x20, 0xE7, 0xC8, 0x9E, 0xE3, 0x68};  // Your master's MAC
   ```
4. **UPDATE CHANNEL** to match master's WiFi channel (from Step 1.6):
   ```cpp
   peerInfo.channel = 6;  // Match your WiFi channel!
   ```
5. Upload to each slave ESP32
6. Label each tile with its ID number!

### Step 2: Backend Setup

1. Install Python dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. Find your laptop's IP address:
   - **Windows**: Open CMD → `ipconfig` → Look for "IPv4 Address"
   - **Mac**: System Preferences → Network → Look for IP
   - **Linux**: `ip addr show` or `ifconfig`
   - Example: `192.168.1.100` or `172.20.10.11`

3. Start the backend:
   ```bash
   python main.py
   ```

4. You should see:
   ```
   ✓ Server ready
     Master endpoint: ws://YOUR_IP:8000/ws/master
     Frontend endpoint: ws://YOUR_IP:8000/ws/frontend
   ```

5. **Test it**: Open browser → `http://YOUR_IP:8000/` → Should show JSON status

### Step 3: Frontend Setup

1. Edit `frontend/app.js` line 8:
   ```javascript
   const WS_HOST = '192.168.X.X';  // Your laptop IP from Step 2.2
   ```

2. Open `frontend/index.html` in a web browser
   - OR host it: `python -m http.server 8080` then open `http://localhost:8080`

---

## ✅ Testing Checklist (Morning of January 9th)

### Hardware Test:
- [ ] Master ESP32 powers on
- [ ] Master Serial Monitor shows "✓ WiFi connected"
- [ ] Master Serial Monitor shows "✓ WebSocket connected"
- [ ] Each slave tile powers on
- [ ] Each slave LED blinks 3 times at startup
- [ ] Each slave Serial Monitor shows "✓✓✓ REGISTERED! ✓✓✓"

### Software Test:
- [ ] Backend running: `python main.py` shows no errors
- [ ] Frontend loads in browser
- [ ] Frontend shows "Master: Connected"
- [ ] Frontend shows "Tiles: X/X" with correct numbers
- [ ] "START NEW GAME" button is enabled (not grayed out)

### Game Test:
- [ ] Click "START NEW GAME"
- [ ] Pattern displays on tiles (LEDs light up in sequence)
- [ ] Step on tiles in correct order
- [ ] Score increases on correct steps
- [ ] Game continues to next round
- [ ] Game ends on wrong step

---

## 🔧 Troubleshooting

### "Master: Disconnected" in Frontend

**Problem**: Master can't connect to backend

**Solutions**:
1. Check backend is running (`python main.py`)
2. Check WS_HOST IP in master firmware matches laptop IP
3. Check firewall isn't blocking port 8000
4. Try: `curl http://YOUR_IP:8000/` → Should return JSON

### "Tiles: 0/X" - Tiles Not Registering

**Problem**: Slaves can't reach master

**Solutions**:
1. Check master MAC in slave firmware is correct
2. Check WiFi channel matches (e.g., both on channel 6)
3. Power cycle slaves (unplug, plug back in)
4. Check Serial Monitor on slave for "✗ Send failed" errors

### Tiles Connecting Then Disconnecting

**Problem**: Channel mismatch or WiFi interference

**Solutions**:
1. Verify peerInfo.channel in slave matches master's WiFi channel
2. Move closer to WiFi hotspot
3. Reduce WiFi interference (turn off other devices)

### Backend Crashes

**Problem**: Python error or dependency issue

**Solutions**:
1. Check `pip install -r requirements.txt` ran successfully
2. Look at error message in terminal
3. Restart: `python main.py`

---

## 📱 Demo Day Setup Procedure

### 1. Arrive Early (30 min before)
- [ ] Set up table/workspace
- [ ] Lay out tiles in clear pattern (e.g., 2x2 grid)
- [ ] Connect all hardware to power

### 2. Start Systems (15 min before)
1. Start WiFi hotspot on phone
2. Start backend on laptop: `python main.py`
3. Power on Master ESP32
4. Wait for master to connect (watch Serial Monitor)
5. Power on all slave tiles (one by one)
6. Watch each tile register (master Serial Monitor shows "✓ Tile X registered")
7. Open frontend on phone/tablet browser

### 3. Verify Everything (5 min before)
- [ ] Frontend shows all systems connected
- [ ] Run one test game
- [ ] Have backup phone with frontend ready

### 4. During Testing
- Keep laptop visible (for backend monitoring)
- Keep Serial Monitors open (for debugging)
- Have backup: if hardware fails, show video demo

---

## 🎮 User Testing Flow

### Test Scenario Example:

1. **Introduction** (1 min)
   - "This is Memory XXL - a physical memory game"
   - "Watch the pattern, then repeat it by stepping on tiles"
   - "Let's try it!"

2. **First Game** (2-3 min)
   - Click START
   - Let user watch pattern
   - Guide them: "Now step on the tiles in the same order"
   - Let them play until game ends

3. **Feedback** (2 min)
   - "What did you think?"
   - "Was it clear what to do?"
   - "Would you play again?"
   - **TAKE NOTES!**

---

## 📊 What to Observe

✅ **Watch For**:
- Do they understand the rules without explanation?
- Do they look at the screen or the tiles?
- Do they get frustrated or engaged?
- Do they want to play again?
- Do they compete with friends?

✅ **Ask**:
- "What was confusing?"
- "What was fun?"
- "Too easy or too hard?"
- "Would you play this at a party?"

---

## 🔋 Battery Life Tips

- Master: Can run on USB power bank (2+ hours)
- Slaves: Test battery life beforehand
- Bring spare USB cables and power banks
- Label all cables by device!

---

## 📞 Emergency Contacts

- **Coach**: [Name] - [Phone]
- **Team Member 1**: [Name] - [Phone]
- **Team Member 2**: [Name] - [Phone]

---

## 💾 Backup Plan

If hardware completely fails:
1. Have video demo ready on phone
2. Use Figma prototype to show concept
3. Show backend running (proves technical capability)
4. Explain: "Hardware works, but demo gremlins struck!"

---

## 🎯 Success Criteria

✅ At minimum, have working:
- 2 tiles registering
- 1 complete game demo
- Frontend displaying correctly

🌟 Ideal scenario:
- 4+ tiles working
- Multiple test users
- Smooth demonstrations
- Good feedback notes

---

## 📝 Final Checklist for Demo Day

### Pack:
- [ ] Laptop (charged + charger)
- [ ] Master ESP32 + cable
- [ ] 4x Slave ESP32s + cables (labeled!)
- [ ] Power bank(s) (charged!)
- [ ] Phone with hotspot
- [ ] Backup phone/tablet
- [ ] Pen & paper for notes
- [ ] This setup guide printed
- [ ] USB hub (if needed)

### Printed Materials:
- [ ] Test scenarios
- [ ] Feedback form
- [ ] Observation checklist

### Digital Backup:
- [ ] Video demo
- [ ] Figma prototype
- [ ] All code on USB drive

---

## 🎊 You've Got This!

Remember:
- Test everything the day before
- Arrive early
- Stay calm if something breaks
- Focus on getting user feedback
- Have fun!

Good luck! 🚀

---

## Quick Reference

**WiFi**: [Your hotspot name]
**Laptop IP**: [Write here]
**Master MAC**: [Write here]
**WiFi Channel**: [Write here]

**Backend URL**: http://[LAPTOP_IP]:8000
**Frontend URL**: Open index.html in browser
**Master Serial**: 115200 baud
**Slave Serial**: 115200 baud
