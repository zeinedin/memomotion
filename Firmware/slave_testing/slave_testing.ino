/**
 * Memory XXL - SLAVE TILE (NeoPixel Version)
 * FEATURES: Auto-Calibrate Touch, Toggle on Step, NeoPixel Green, Non-blocking
 */

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <Adafruit_NeoPixel.h>

// ==================== CONFIGURATION ====================
#define TILE_ID        5       // !!! CHANGE THIS FOR EACH TILE !!!
#define LED_PIN        13      // NeoPixel Data Pin
#define LED_COUNT      12      // Number of LEDs in the ring/strip
#define TOUCH_PIN      4       // Copper tape / Wire

// Master MAC Address
uint8_t masterMAC[] = {0x00, 0x70, 0x07, 0x81, 0x4E, 0x10};

// NeoPixel Object
Adafruit_NeoPixel pixels(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

// ==================== DATA STRUCTURES ====================
typedef struct {
  uint8_t tileId;
  uint8_t messageType; 
  uint8_t value;
  uint8_t batteryLevel;
} TileMessage;

typedef struct {
  uint8_t tileId;
  uint8_t command; 
  uint8_t duration;
} MasterCommand;

// ==================== SETTINGS ====================
// Touch Sensitivity: Triggers if value drops by 30 (e.g., 40 -> 10)
const int TOUCH_DROP_REQUIRED = 30; 

// Globals for Logic
int touchBaseline = 0;
bool isRegistered = false;

// Touch State Tracking
bool currentTouchState = false; // Is foot currently down?
bool lastTouchState = false;    // Previous loop state
bool tileLitState = false;      // Logic State: Is the Light ON or OFF?

// Non-blocking Timers
unsigned long lastDebounceTime = 0;
unsigned long lastRegisterTime = 0;
unsigned long debounceDelay = 50; // 50ms debounce

// Flags for Main Loop Processing (Stability)
volatile bool cmdReceived = false;
volatile int  cmdCommand = -1;

// ==================== HELPER FUNCTIONS ====================

// Set all LEDs to a specific state (Green or Off)
void setLights(bool isOn) {
  if (isOn) {
    // GREEN (Red=0, Green=255, Blue=0)
    for(int i=0; i<pixels.numPixels(); i++) {
      pixels.setPixelColor(i, pixels.Color(0, 255, 0)); 
    }
  } else {
    // OFF
    pixels.clear();
  }
  pixels.show();
}

void sendMessage(uint8_t type, uint8_t value) {
  TileMessage msg;
  msg.tileId = TILE_ID;
  msg.messageType = type;
  msg.value = value;
  esp_now_send(masterMAC, (uint8_t *) &msg, sizeof(msg));
}

// Callback: Runs when data arrives (Keep this short!)
void onDataReceived(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (len != sizeof(MasterCommand)) return;
  MasterCommand cmd;
  memcpy(&cmd, data, sizeof(cmd));

  if (cmd.tileId != TILE_ID && cmd.tileId != 0) return;

  // Pass command to main loop to handle safely
  cmdCommand = cmd.command;
  cmdReceived = true;
}

// ==================== SETUP ====================
void setup() {
  Serial.begin(115200);
  
  // 1. Init NeoPixels
  pixels.begin();
  pixels.setBrightness(150); // Set brightness (0-255)
  setLights(false); // Start OFF

  Serial.printf("\n=== TILE %d STARTING (NEOPIXEL) ===\n", TILE_ID);

  // 2. Setup WiFi
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(6, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false);

  // 3. Init ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    ESP.restart();
  }
  esp_now_register_recv_cb(onDataReceived);

  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, masterMAC, 6);
  peerInfo.channel = 6;  
  peerInfo.encrypt = false;

  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add master peer");
  } else {
    Serial.println("Master peer added");
  }

  // 4. AUTO-CALIBRATE TOUCH
  // Take 10 readings and average them to find the "normal" state
  Serial.println("Calibrating Touch...");
  long total = 0;
  for(int i=0; i<20; i++) {
    total += touchRead(TOUCH_PIN);
    delay(10); // Small blocking delay allowed only in setup
  }
  touchBaseline = total / 20;
  
  Serial.print("✓ Baseline: "); Serial.println(touchBaseline);
  Serial.print("✓ Trigger: < "); Serial.println(touchBaseline - TOUCH_DROP_REQUIRED);
  
  // Flash Green once to say "Ready"
  setLights(true);
  delay(300);
  setLights(false);
}

// ==================== LOOP ====================
void loop() {
  unsigned long now = millis();

  // --- 1. HANDLE MASTER COMMANDS (Received via Callback) ---
  if (cmdReceived) {
    cmdReceived = false; // Reset flag
    
    if (cmdCommand == 0) {       // Master Force OFF
      tileLitState = false;
      setLights(false);
    } 
    else if (cmdCommand == 1) {  // Master Force ON
      tileLitState = true;
      setLights(true);
    } 
    else if (cmdCommand == 3) {  // Registration Confirm
      isRegistered = true;
      Serial.println("✓ REGISTERED!");
      // Quick double blink green to confirm
      setLights(true); delay(100); setLights(false); delay(100); setLights(true); delay(100); setLights(false);
    }
  }

  // --- 2. REGISTRATION RETRY ---
  // If not registered, try every 2 seconds
  if (!isRegistered && (now - lastRegisterTime > 2000)) {
    Serial.println("→ Sending Registration...");
    sendMessage(0, 0); 
    lastRegisterTime = now;
  }

  // --- 3. TOUCH & TOGGLE LOGIC ---
  int touchVal = touchRead(TOUCH_PIN);
  bool isTouched = (touchVal < (touchBaseline - TOUCH_DROP_REQUIRED));

  // Debouncing
  if (isTouched != lastTouchState) {
    lastDebounceTime = now; // Reset timer
  }

  if ((now - lastDebounceTime) > debounceDelay) {
    // If state has been stable for 50ms
    if (isTouched != currentTouchState) {
      currentTouchState = isTouched;

      // ACTION: Only Trigger when foot goes DOWN (Rising Edge)
      if (currentTouchState == true) {
        Serial.printf("→ STEP DETECTED! (Val: %d)\n", touchVal);
        
        // TOGGLE LOGIC: Flip state
        tileLitState = !tileLitState;
        
        // Update LEDs
        setLights(tileLitState);

        // Notify Master of new state (1=ON, 0=OFF)
        if (isRegistered) {
          sendMessage(1, tileLitState ? 1 : 0);
        }
      }
    }
  }

  lastTouchState = isTouched;
  
  // No delay() here - loop runs as fast as possible for responsiveness
}