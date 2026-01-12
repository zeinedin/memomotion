# Memory XXL - Quick Reference Card
## PRINT THIS AND KEEP IT WITH YOU!

---

## ⚡ Emergency Quick Start

### If Everything Is Off:

1. **WiFi Hotspot** → Turn on phone hotspot
2. **Backend** → `cd backend` → `python main.py`
3. **Master** → Plug in USB → Wait for "WebSocket Connected"
4. **Slaves** → Plug in USB (one by one) → Wait for "REGISTERED!"
5. **Frontend** → Open `index.html` in browser

---

## 🔧 Configuration Quick Reference

### WiFi Settings:
```
SSID: ___________________________
Password: ________________________
```

### IP Addresses:
```
Laptop IP: _______________________
Master MAC: ______________________
WiFi Channel: ____________________
```

### Ports:
```
Backend: http://[LAPTOP_IP]:8000
Frontend: Open index.html locally
WebSocket: ws://[LAPTOP_IP]:8000/ws/frontend
```

---

## 🎮 Testing Flow

1. **Show game** (don't explain yet)
2. **Watch** user try to figure it out
3. **Help** if stuck after 30 seconds
4. **Observe** during play
5. **Ask** questions after
6. **Take notes** immediately
7. **Thank** them!

---

## 🐛 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| Master disconnected | 1. Check backend running<br>2. Check IP address<br>3. Restart master |
| Tiles not connecting | 1. Check master MAC<br>2. Check channel number<br>3. Power cycle tiles |
| Frontend not loading | 1. Check laptop IP<br>2. Check browser console<br>3. Try different browser |
| Pattern not showing | 1. Check master logs<br>2. Check tile LEDs<br>3. Restart game |

---

## 📱 Serial Monitor Messages

### Good Signs ✅:
```
Master:
  ✓ WiFi connected
  ✓ WebSocket connected
  ✓ Tile 1 registered

Slave:
  ✓ ESP-NOW initialized
  ✓ Master peer added
  ✓✓✓ REGISTERED! ✓✓✓
```

### Bad Signs ❌:
```
Master:
  ✗ WiFi failed
  ✗ WebSocket disconnected

Slave:
  ✗ Send failed
  → Retry registration...
```

---

## 🎯 Key Questions to Ask

1. Was it fun? (1-10)
2. Was it clear what to do?
3. Would you play again?
4. What would you change?

---

## 📊 Data to Track

**Per Tester:**
- Age: _____
- Fun rating: _____
- Understood without help? Y / N
- Played again? Y / N
- Main feedback: _______________

**Technical:**
- Failures: _____
- Tile disconnects: _____
- Backend crashes: _____

---

## ☎️ Emergency Contacts

```
Team Member 1: __________________
Team Member 2: __________________
Coach: __________________________
```

---

## 🎒 Checklist

**Hardware:**
- [ ] Master ESP32
- [ ] 4x Slave ESP32s (labeled!)
- [ ] USB cables
- [ ] Power bank
- [ ] Laptop + charger

**Software:**
- [ ] Backend files
- [ ] Frontend files
- [ ] Video backup

**Materials:**
- [ ] This reference card
- [ ] Test scenarios
- [ ] Feedback forms
- [ ] Pens
- [ ] Camera/phone

---

## 💡 Remember

- Test everything 1 day before!
- Arrive 30 min early
- Keep Serial Monitors open
- Take lots of notes
- Stay calm if things break
- Focus on user feedback
- **Have fun!**

---

## 🚀 You've Got This!

Good luck! 🎉
