# Memory XXL - Hardware Testing Guide

## 🧪 Tile ESP Hardware Test

Use the test firmware to verify all switches and LEDs are working correctly before deploying the full system.

---

## 📥 Installation

1. Open `Firmware/tile_esp_TEST/tile_esp_TEST.ino` in Arduino IDE
2. Set the `TILE_ESP_ID` for the ESP you're testing:
   ```cpp
   #define TILE_ESP_ID 1  // Change to 1, 2, 3, or 4
   ```
3. Upload to ESP32
4. Open Serial Monitor at **115200 baud**

---

## 🎮 Test Menu

When the test code starts, you'll see:

```
========================================
  MEMORY XXL - TILE ESP HARDWARE TEST
========================================
Testing Tile ESP #1
========================================

This ESP manages tiles: 1, 2, 3, 4

TEST MENU
========================================
Press a key to select test:
  1 - LED Strip Test (cycle all LEDs)
  2 - Switch Test (monitor switches)
  3 - Combined Test (switch → LED)
  4 - Individual LED Test
  5 - Individual Switch Test
  r - Restart/Reset
  m - Show this menu
========================================
```

---

## 🔍 Test Modes

### Test 1: LED Strip Test (Automatic)

**Press `1` in Serial Monitor**

- Cycles through all 4 LED strips
- Each strip shows: RED → GREEN → BLUE → WHITE → OFF
- 1 second per color
- Repeats continuously

**What to check:**

- ✅ All LED strips light up
- ✅ Colors are correct
- ✅ All LEDs in strip work
- ✅ Strips are in correct order (1, 2, 3, 4)

**Expected output:**

```
Strip 1 (Tile 1): RED
Strip 1 (Tile 1): GREEN
Strip 1 (Tile 1): BLUE
Strip 1 (Tile 1): WHITE
Strip 1 (Tile 1): OFF
Strip 2 (Tile 2): RED
...
```

---

### Test 2: Switch Test (Interactive)

**Press `2` in Serial Monitor**

- Monitors all 4 switches
- Prints message when any switch changes state
- Shows PRESSED or Released

**What to check:**

- ✅ Each switch responds when pressed
- ✅ Switch releases properly
- ✅ No false triggers
- ✅ All switches work

**Expected output:**

```
Switch 1 (Tile 1): PRESSED ✓
Switch 1 (Tile 1): Released
Switch 3 (Tile 3): PRESSED ✓
Switch 3 (Tile 3): Released
```

**How to test:**

1. Press each switch one at a time
2. Verify you see "PRESSED ✓" message
3. Release and verify "Released" message
4. Repeat for all 4 switches

---

### Test 3: Combined Test (Interactive)

**Press `3` in Serial Monitor**

- Press switch → LED lights up
- Release switch → LED turns off
- Tests switch-to-LED connection

**What to check:**

- ✅ Pressing switch 1 lights LED 1
- ✅ Pressing switch 2 lights LED 2
- ✅ Pressing switch 3 lights LED 3
- ✅ Pressing switch 4 lights LED 4
- ✅ Releasing switch turns off LED
- ✅ No cross-wiring issues

**Expected output:**

```
Switch 1 (Tile 1) → LED 1 ON
Switch 1 (Tile 1) → LED 1 OFF
Switch 2 (Tile 2) → LED 2 ON
Switch 2 (Tile 2) → LED 2 OFF
```

**How to test:**

1. Press switch 1 → LED 1 should light GREEN
2. Release switch 1 → LED 1 should turn OFF
3. Repeat for switches 2, 3, 4
4. Try pressing multiple switches at once

---

### Test 4: Individual LED Test (Automatic)

**Press `4` in Serial Monitor**

- Tests each LED in each strip individually
- Lights one LED at a time
- 200ms per LED

**What to check:**

- ✅ All 12 LEDs work in Strip 1
- ✅ All 12 LEDs work in Strip 2
- ✅ All 12 LEDs work in Strip 3
- ✅ All 12 LEDs work in Strip 4
- ✅ LEDs light in sequence
- ✅ No dead LEDs

**Expected output:**

```
--- Strip 1 (Tile 1) ---
  LED 1: ON
  LED 2: ON
  LED 3: ON
  ...
  LED 12: ON
  All OFF
--- Strip 2 (Tile 2) ---
  ...
```

---

### Test 5: Individual Switch Test (Interactive)

**Press `5` in Serial Monitor**

- Tests each switch one at a time
- 5-second timeout per switch
- Guided testing

**What to check:**

- ✅ Switch 1 responds within 5 seconds
- ✅ Switch 2 responds within 5 seconds
- ✅ Switch 3 responds within 5 seconds
- ✅ Switch 4 responds within 5 seconds

**Expected output:**

```
Test Switch 1 (Tile 1)
Press the switch now...
  ✓ Switch PRESSED - Working!
  ✓ Switch RELEASED

Test Switch 2 (Tile 2)
Press the switch now...
  ✓ Switch PRESSED - Working!
  ✓ Switch RELEASED
```

**If timeout occurs:**

```
  ✗ Switch not pressed (timeout)
  Check wiring or try again.
```

---

## 🔧 Troubleshooting

### Problem: No LEDs light up

**Possible causes:**

- ❌ LED power supply not connected
- ❌ Wrong LED pin in code
- ❌ LED strip not connected to correct GPIO
- ❌ NeoPixel library not installed

**Solutions:**

1. Check 5V power supply to LED strips
2. Verify `LED_PIN_X` matches your wiring
3. Check LED strip data pin connections
4. Install Adafruit_NeoPixel library

---

### Problem: Wrong LED strip lights up

**Possible causes:**

- ❌ LED strips connected to wrong GPIOs
- ❌ Pin definitions in code don't match hardware

**Solutions:**

1. Check which GPIO each strip is connected to
2. Update pin definitions in code:
   ```cpp
   #define LED_PIN_1 13  // Update these
   #define LED_PIN_2 12
   #define LED_PIN_3 14
   #define LED_PIN_4 27
   ```

---

### Problem: Switch doesn't register

**Possible causes:**

- ❌ Switch not connected
- ❌ Wrong pin configuration
- ❌ Faulty switch
- ❌ Incorrect wiring (normally open/closed)

**Solutions:**

1. Check switch wiring (should be normally open)
2. Verify switch pin connections
3. Test switch with multimeter
4. Update pin definitions if needed:
   ```cpp
   #define SWITCH_PIN_1 33  // Update these
   #define SWITCH_PIN_2 32
   #define SWITCH_PIN_3 35
   #define SWITCH_PIN_4 34
   ```

---

### Problem: Switch triggers constantly

**Possible causes:**

- ❌ Switch wired as normally closed
- ❌ No pullup resistor
- ❌ Loose connection

**Solutions:**

1. Verify switch is normally open
2. Code uses INPUT_PULLUP (no external resistor needed)
3. Check for loose wires
4. Test with different switch

---

### Problem: Some LEDs in strip don't work

**Possible causes:**

- ❌ Dead LEDs in strip
- ❌ Insufficient power
- ❌ Data line issue

**Solutions:**

1. Check power supply capacity (60mA per LED)
2. Try reducing brightness in code
3. Check LED strip data line integrity
4. Replace faulty LED strip

---

### Problem: Colors are wrong

**Possible causes:**

- ❌ LED strip is RGB instead of GRB
- ❌ Wrong NeoPixel configuration

**Solutions:**

1. Change strip initialization:
   ```cpp
   // Try different color orders:
   NEO_GRB  // Green-Red-Blue (most common)
   NEO_RGB  // Red-Green-Blue
   NEO_GRBW // With white channel
   ```

---

## 📋 Test Checklist

Use this checklist when testing each Tile ESP:

### Tile ESP #1 (Tiles 1-4)

- [ ] LED Strip 1 (Tile 1) - All colors work
- [ ] LED Strip 2 (Tile 2) - All colors work
- [ ] LED Strip 3 (Tile 3) - All colors work
- [ ] LED Strip 4 (Tile 4) - All colors work
- [ ] Switch 1 (Tile 1) - Press/Release works
- [ ] Switch 2 (Tile 2) - Press/Release works
- [ ] Switch 3 (Tile 3) - Press/Release works
- [ ] Switch 4 (Tile 4) - Press/Release works
- [ ] Combined test - All switch→LED pairs work
- [ ] All 12 LEDs in each strip work
- [ ] No cross-wiring issues

### Tile ESP #2 (Tiles 5-8)

- [ ] LED Strip 1 (Tile 5) - All colors work
- [ ] LED Strip 2 (Tile 6) - All colors work
- [ ] LED Strip 3 (Tile 7) - All colors work
- [ ] LED Strip 4 (Tile 8) - All colors work
- [ ] Switch 1 (Tile 5) - Press/Release works
- [ ] Switch 2 (Tile 6) - Press/Release works
- [ ] Switch 3 (Tile 7) - Press/Release works
- [ ] Switch 4 (Tile 8) - Press/Release works
- [ ] Combined test - All switch→LED pairs work
- [ ] All 12 LEDs in each strip work
- [ ] No cross-wiring issues

### Tile ESP #3 (Tiles 9-12)

- [ ] LED Strip 1 (Tile 9) - All colors work
- [ ] LED Strip 2 (Tile 10) - All colors work
- [ ] LED Strip 3 (Tile 11) - All colors work
- [ ] LED Strip 4 (Tile 12) - All colors work
- [ ] Switch 1 (Tile 9) - Press/Release works
- [ ] Switch 2 (Tile 10) - Press/Release works
- [ ] Switch 3 (Tile 11) - Press/Release works
- [ ] Switch 4 (Tile 12) - Press/Release works
- [ ] Combined test - All switch→LED pairs work
- [ ] All 12 LEDs in each strip work
- [ ] No cross-wiring issues

### Tile ESP #4 (Tiles 13-16)

- [ ] LED Strip 1 (Tile 13) - All colors work
- [ ] LED Strip 2 (Tile 14) - All colors work
- [ ] LED Strip 3 (Tile 15) - All colors work
- [ ] LED Strip 4 (Tile 16) - All colors work
- [ ] Switch 1 (Tile 13) - Press/Release works
- [ ] Switch 2 (Tile 14) - Press/Release works
- [ ] Switch 3 (Tile 15) - Press/Release works
- [ ] Switch 4 (Tile 16) - Press/Release works
- [ ] Combined test - All switch→LED pairs work
- [ ] All 12 LEDs in each strip work
- [ ] No cross-wiring issues

---

## 🎯 Success Criteria

Before moving to the full firmware, ensure:

- ✅ All 16 LED strips work (4 strips per ESP × 4 ESPs)
- ✅ All 16 switches respond correctly
- ✅ Each switch controls correct LED
- ✅ All 12 LEDs in each strip work
- ✅ No false triggers or bouncing
- ✅ Colors display correctly
- ✅ Power supply is adequate

---

## 🔄 After Testing

Once all tests pass:

1. **Document results** in test checklist above
2. **Label each ESP** with its ID (1, 2, 3, or 4)
3. **Upload main firmware** (`tile_esp_4tiles.ino`)
4. **Set correct TILE_ESP_ID** in main firmware
5. **Update Master MAC address** in main firmware
6. **Proceed with system integration**

---

## 💡 Tips

- **Test one ESP at a time** for clear results
- **Use Serial Monitor** to see detailed output
- **Label wires** as you verify them
- **Take notes** of any issues found
- **Test power supply** under full load (all LEDs white)
- **Retest** after any wiring changes

---

## 📞 Common Serial Commands

| Key | Action                 |
| --- | ---------------------- |
| `1` | Start LED strip test   |
| `2` | Start switch test      |
| `3` | Start combined test    |
| `4` | Individual LED test    |
| `5` | Individual switch test |
| `r` | Restart ESP            |
| `m` | Show menu              |

---

**Pro Tip:** Keep this test firmware handy for troubleshooting hardware issues even after deployment!
