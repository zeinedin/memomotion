/**
 * Memory XXL - SLAVE TILE (TILE AUTHORITY)
 * Logic: Tile toggles its own light immediately, then tells the Website.
 * Result: Zero delay, stable light.
 */

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <Adafruit_NeoPixel.h>

// ==================== CONFIGURATION ====================
#define TILE_ID        5       
#define LED_PIN        13      
#define LED_COUNT      12      
#define TOUCH_PIN      4       

// !!! WIFI CHANNEL MUST MATCH MASTER !!!
#define WIFI_CHANNEL   6       

// Master MAC Address
uint8_t masterMAC[] = {0x00, 0x70, 0x07, 0x81, 0x4E, 0x10};

// NeoPixel
Adafruit_NeoPixel pixels(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

// ==================== SETTINGS ====================
const int TOUCH_THRESHOLD = 100; 
const int RESET_TOLERANCE = 50; 

// Globals
int touchBaseline = 0;
bool isRegistered = false;

// THE STATE MEMORY
// This variable remembers if the tile is currently ON or OFF.
bool tileLitState = false; 

// Stability State Machine
enum StepState { STATE_IDLE, STATE_PRESSED, STATE_WAITING_RELEASE };
StepState currentState = STATE_IDLE;
unsigned long lastRegisterTime = 0;

// Data Structures
typedef struct { uint8_t tileId; uint8_t msgType; uint8_t val; uint8_t batt; } TileMessage;
typedef struct { uint8_t tileId; uint8_t cmd; uint8_t dur; } MasterCommand;

// ==================== LED HELPER ====================
void setLights(bool isOn) {
  if (isOn) {
    // GREEN
    for(int i=0; i<LED_COUNT; i++) pixels.setPixelColor(i, pixels.Color(0, 255, 0)); 
  } else {
    // OFF
    pixels.clear();
  }
  pixels.show();
}

// ==================== COMMS HELPER ====================
void sendMessage(uint8_t type, uint8_t value) {
  TileMessage msg;
  msg.tileId = TILE_ID;
  msg.msgType = type;
  msg.val = value; 
  esp_now_send(masterMAC, (uint8_t *) &msg, sizeof(msg));
}

// RECEIVE CALLBACK (Only used for Game Over / Reset)
void onDataReceived(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (len != sizeof(MasterCommand)) return;
  MasterCommand cmd;
  memcpy(&cmd, data, sizeof(cmd));
  
  if (cmd.tileId != TILE_ID && cmd.tileId != 0) return;

  // Master commands override local state (e.g. Game Over)
  if (cmd.cmd == 0) { 
    tileLitState = false; 
    setLights(false); 
  }
  else if (cmd.cmd == 1) { 
    tileLitState = true; 
    setLights(true); 
  }
  else if (cmd.cmd == 3) { 
    // Registration Confirm
    if (!isRegistered) {
      isRegistered = true; 
      Serial.println("✓ REGISTERED!");
      // Blue flash
      for(int i=0; i<LED_COUNT; i++) pixels.setPixelColor(i, pixels.Color(0, 0, 255));
      pixels.show();
      delay(200);
      setLights(tileLitState); // Return to previous state
    }
  }
}

// ==================== SETUP ====================
void setup() {
  Serial.begin(115200);
  pixels.begin(); pixels.setBrightness(150); setLights(false);

  Serial.printf("\n=== TILE %d AUTHORITY ===\n", TILE_ID);

  // WiFi Setup
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  
  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false);

  if (esp_now_init() != ESP_OK) ESP.restart();
  
  esp_now_register_recv_cb(onDataReceived);

  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, masterMAC, 6);
  peerInfo.channel = WIFI_CHANNEL; 
  peerInfo.encrypt = false;
  if (esp_now_add_peer(&peerInfo) != ESP_OK) Serial.println("Peer add failed");

  // Calibration
  Serial.println("Calibrating...");
  long total = 0;
  for(int i=0; i<50; i++) { total += touchRead(TOUCH_PIN); delay(5); }
  touchBaseline = total / 50;
  Serial.printf("Baseline: %d | Threshold: < %d\n", touchBaseline, touchBaseline - TOUCH_THRESHOLD);
  
  // Ready Flash
  setLights(true); delay(200); setLights(false);
}

// ==================== LOOP ====================
void loop() {
  int raw = touchRead(TOUCH_PIN);

  switch (currentState) {
    // 1. Waiting for Step
    case STATE_IDLE:
      if (raw < (touchBaseline - TOUCH_THRESHOLD)) {
        Serial.printf("STEP! (Raw: %d)\n", raw);
        
        // --- INSTANT ACTION ---
        
        // 1. Toggle Local State
        tileLitState = !tileLitState;
        
        // 2. Update LED Immediately
        setLights(tileLitState);
        
        // 3. Tell Master the NEW state (1=ON, 0=OFF)
        sendMessage(1, tileLitState ? 1 : 0);
        
        currentState = STATE_PRESSED;
      }
      break;

    // 2. Step Held Down
    case STATE_PRESSED:
      if (raw > (touchBaseline - TOUCH_THRESHOLD + 20)) currentState = STATE_WAITING_RELEASE;
      break;

    // 3. Step Released
    case STATE_WAITING_RELEASE:
      if (raw > (touchBaseline - RESET_TOLERANCE)) currentState = STATE_IDLE;
      break;
  }

  // Register Retry
  if (!isRegistered && (millis() - lastRegisterTime > 3000)) {
    Serial.println("Connecting...");
    sendMessage(0, 0);
    lastRegisterTime = millis();
  }
  
  delay(5);
}