/**
 * Memory XXL - SLAVE TILE (FINAL STABLE v3.0)
 * Fixed for ESP32 Arduino Core 3.0+ compilation errors
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

// !!! CRITICAL: Set this to your Router's Channel (1, 6, or 11)
// If you don't know it, try 1, then 6, then 11 until the Website works.
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
bool tileLitState = false; 

// Stability State Machine
enum StepState { STATE_IDLE, STATE_PRESSED, STATE_WAITING_RELEASE };
StepState currentState = STATE_IDLE;
unsigned long lastRegisterTime = 0;

// Data Structures
typedef struct { uint8_t tileId; uint8_t msgType; uint8_t val; uint8_t batt; } TileMessage;
typedef struct { uint8_t tileId; uint8_t cmd; uint8_t dur; } MasterCommand;

// ==================== COMMS HELPER ====================

void sendMessage(uint8_t type, uint8_t value) {
  TileMessage msg;
  msg.tileId = TILE_ID;
  msg.msgType = type;
  msg.val = value;
  esp_now_send(masterMAC, (uint8_t *) &msg, sizeof(msg));
}

// CORRECTED Callback for ESP32 v3.0+
void onDataReceived(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (len != sizeof(MasterCommand)) return;
  MasterCommand cmd;
  memcpy(&cmd, data, sizeof(cmd));
  if (cmd.tileId != TILE_ID && cmd.tileId != 0) return;

  if (cmd.cmd == 0) { tileLitState = false; setLights(false); }
  else if (cmd.cmd == 1) { tileLitState = true; setLights(true); }
  else if (cmd.cmd == 3) { 
    if (!isRegistered) {
      isRegistered = true; 
      Serial.println("✓ REGISTERED with Master!");
      // Flash blue to confirm registration
      for(int i=0; i<LED_COUNT; i++) pixels.setPixelColor(i, pixels.Color(0, 0, 255));
      pixels.show();
      delay(200);
      setLights(false);
    }
  }
}

// ==================== LED & SETUP ====================
void setLights(bool isOn) {
  if (isOn) {
    for(int i=0; i<LED_COUNT; i++) pixels.setPixelColor(i, pixels.Color(0, 255, 0)); 
  } else {
    pixels.clear();
  }
  pixels.show();
}

void setup() {
  Serial.begin(115200);
  pixels.begin(); pixels.setBrightness(150); setLights(false);

  Serial.printf("\n=== TILE %d v3.0 FIXED ===\n", TILE_ID);

  // WiFi Setup
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  
  // FORCE CHANNEL
  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false);
  Serial.printf("WiFi Channel set to: %d\n", WIFI_CHANNEL);

  if (esp_now_init() != ESP_OK) ESP.restart();
  
  // Register ONLY Receive Callback (Send callback removed to fix error)
  esp_now_register_recv_cb(onDataReceived);

  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, masterMAC, 6);
  peerInfo.channel = WIFI_CHANNEL; 
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Peer add failed (Check MAC)");
  }

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
    case STATE_IDLE:
      if (raw < (touchBaseline - TOUCH_THRESHOLD)) {
        Serial.printf("STEP! (Raw: %d) -> Sending to Master\n", raw);
        tileLitState = !tileLitState;
        setLights(tileLitState);
        
        // Send Message
        sendMessage(1, tileLitState ? 1 : 0);
        
        currentState = STATE_PRESSED;
      }
      break;

    case STATE_PRESSED:
      if (raw > (touchBaseline - TOUCH_THRESHOLD + 20)) currentState = STATE_WAITING_RELEASE;
      break;

    case STATE_WAITING_RELEASE:
      if (raw > (touchBaseline - RESET_TOLERANCE)) currentState = STATE_IDLE;
      break;
  }

  // Register Retry (Every 3 sec until registered, then stop)
  if (!isRegistered && (millis() - lastRegisterTime > 3000)) {
    Serial.println("Attempting Register...");
    sendMessage(0, 0);
    lastRegisterTime = millis();
  }
  delay(5);  // Reduced delay for faster response
}