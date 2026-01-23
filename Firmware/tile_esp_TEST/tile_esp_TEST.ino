// ================= DEBOUNCE & TOGGLE STATE =================
struct TileState {
  bool stableState;

  bool lastReading;
  unsigned long lastDebounceTime;
  bool ledActive; // <--- NEW: Tracks if this specific tile is "Toggled On"
};

// Initialize with ledActive = false
TileState tile1 = {HIGH, HIGH, 0, false};
TileState tile2 = {HIGH, HIGH, 0, false};
TileState tile3 = {HIGH, HIGH, 0, false};
TileState tile4 = {HIGH, HIGH, 0, false};

// ... (setup remains the same) ...

// ================= CHECK TILE (TOGGLE VERSION) =================
void checkTile(int switchPin, TileState* state, Adafruit_NeoPixel* ring, uint8_t tilePort) {
  bool reading = digitalRead(switchPin);

  if (reading != state->lastReading) {
    state->lastDebounceTime = millis();
  }

  if ((millis() - state->lastDebounceTime) > debounceDelay) {
    if (reading != state->stableState) {
      state->stableState = reading;

      // Only act when the switch is PRESSED (transition to LOW)
      if (state->stableState == LOW) {
        // Toggle the internal state
        state->ledActive = !state->ledActive; 

        int baseTile = (TILE_ESP_ID - 1) * 4;
        
        if (state->ledActive) {
          showGreen(ring);
          sendEvent(tilePort, 1); // Send "Toggled ON" event
          Serial.printf("Tile %d TOGGLED ON\n", baseTile + tilePort + 1);
        } else {
          showOff(ring);
          sendEvent(tilePort, 0); // Send "Toggled OFF" event
          Serial.printf("Tile %d TOGGLED OFF\n", baseTile + tilePort + 1);
        }
      }
    }
  }

  state->lastReading = reading;
}