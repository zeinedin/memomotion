/**
 * Memory XXL - SLAVE TILE (ONE-SHOT TRIGGER)
 * Logic: Triggers ONCE when you step. 
 * Will NOT trigger again until you lift your foot completely.
 */

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <Adafruit_NeoPixel.h>

// ==================== CONFIGURATION ====================
#define TILE_ID 3
#define LED_PIN 13
#define LED_COUNT 12
#define TOUCH_PIN 4
#define WIFI_CHANNEL 6

// Master MAC Address
uint8_t masterMAC[] = { 0x00, 0x70, 0x07, 0x81, 0x4E, 0x10 };

Adafruit_NeoPixel pixels(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

// ==================== SETTINGS ====================
const int TOUCH_THRESHOLD = 80;  // How hard to press
const int RELEASE_BUFFER = 50;   // How much to lift foot to reset

// Globals
int touchBaseline = 0;
bool isRegistered = false;
bool tileLitState = false;
bool isFootDown = false;  // Tracks if you are currently standing on it
unsigned long lastRegisterTime = 0;
unsigned long lastHeartbeat = 0;  // Periodic heartbeat to stay connected

// Data Structures (MUST MATCH MASTER)
typedef struct {
  uint8_t tileId;
  uint8_t messageType; // 0=Reg, 1=Step, 2=Heartbeat, 3=Battery
  uint8_t value;
  uint8_t batteryLevel;
} TileMessage;
typedef struct {
  uint8_t tileId;
  uint8_t cmd;
  uint8_t dur;
} MasterCommand;

// ==================== LED HELPER ====================
void setLights(bool isOn) {
  if (isOn) {
    for (int i = 0; i < LED_COUNT; i++) pixels.setPixelColor(i, pixels.Color(0, 255, 0));
  } else {
    pixels.clear();
  }
  pixels.show();
}

// ==================== COMMS HELPER ====================
void sendMessage(uint8_t type, uint8_t val) {
  TileMessage msg;
  msg.tileId = TILE_ID;
  msg.messageType = type;  // 0=Reg, 1=Step, 2=Heartbeat
  msg.value = val;
  msg.batteryLevel = 100;  // TODO: Read actual battery
  esp_now_send(masterMAC, (uint8_t *)&msg, sizeof(msg));
}

// RECEIVE CALLBACK
void onDataReceived(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (len != sizeof(MasterCommand)) return;
  MasterCommand cmd;
  memcpy(&cmd, data, sizeof(cmd));

  if (cmd.tileId != TILE_ID && cmd.tileId != 0) return;

  if (cmd.cmd == 0) {
    tileLitState = false;
    setLights(false);
  } else if (cmd.cmd == 1) {
    tileLitState = true;
    setLights(true);
  } else if (cmd.cmd == 3) {
    if (!isRegistered) {
      isRegistered = true;
      Serial.println("✓ REGISTERED!");
      for (int i = 0; i < LED_COUNT; i++) pixels.setPixelColor(i, pixels.Color(0, 0, 255));
      pixels.show();
      delay(200);
      setLights(tileLitState);
    }
  }
}

// ==================== SETUP ====================
void setup() {
  Serial.begin(115200);
  pixels.begin();
  pixels.setBrightness(150);
  setLights(false);

  Serial.printf("\n=== TILE %d ONE-SHOT ===\n", TILE_ID);

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
  Serial.println("Calibrating... DO NOT TOUCH WIRE");
  long total = 0;
  for (int i = 0; i < 50; i++) {
    total += touchRead(TOUCH_PIN);
    delay(10);
  }
  touchBaseline = total / 50;
  Serial.printf("Baseline: %d | Trigger Level: < %d\n", touchBaseline, touchBaseline - TOUCH_THRESHOLD);

  // Ready Flash
  setLights(true);
  delay(200);
  setLights(false);
}

// ==================== LOOP (THE FIX) ====================
void loop() {
  int raw = touchRead(TOUCH_PIN);

  // 1. DETECT PRESS (Value goes LOW)
  if (raw < (touchBaseline - TOUCH_THRESHOLD)) {

    // Only trigger if foot was NOT down before
    if (!isFootDown) {
      Serial.printf("STEP DOWN! (Raw: %d)\n", raw);

      // Mark foot as down - this prevents re-triggering
      isFootDown = true;

      // ACTION: Toggle LED state
      tileLitState = !tileLitState;
      Serial.printf("LED State: %s\n", tileLitState ? "ON" : "OFF");
      setLights(tileLitState);
      
      // Small delay to ensure LED change is visible before sending message
      delay(50);
      
      // Send to master
      sendMessage(1, tileLitState ? 1 : 0);
      Serial.printf("Sent to master: is_on=%d\n", tileLitState ? 1 : 0);
    }
  }

  // 2. DETECT RELEASE (Value goes HIGH)
  // We require the value to go almost back to baseline to reset
  else if (raw > (touchBaseline - RELEASE_BUFFER)) {
    if (isFootDown) {
      Serial.println("Foot Lifted (Resetting trigger)");
      isFootDown = false;  // Now allowed to step again
    }
  }

  // Register Retry (if not registered yet)
  if (!isRegistered && (millis() - lastRegisterTime > 3000)) {
    Serial.println("Connecting...");
    sendMessage(0, 0);  // msgType 0 = register
    lastRegisterTime = millis();
  }
  
  // Heartbeat to stay connected (every 2 seconds)
  if (isRegistered && (millis() - lastHeartbeat > 2000)) {
    sendMessage(2, 0);  // msgType 2 = heartbeat
    lastHeartbeat = millis();
  }

  delay(10);
}