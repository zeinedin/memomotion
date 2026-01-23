/**
 * Memory XXL - TILE HUB ESP32
 * FIXES:
 * 1. Sets WiFi Channel to match Master/iPhone
 * 2. Fixes 'wifi_tx_info_t' compiler error
 * 3. Registers Broadcast Peer correctly
 */

#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h> // REQUIRED for channel setting
#include <Adafruit_NeoPixel.h>

// ================= CONFIGURATION =================
#define TILE_ESP_ID 0       // CHANGE FOR EACH ESP (0, 1, 2, 3)
#define NUM_TILES   4
#define LED_COUNT   12
#define WIFI_CHANNEL 6      // <--- SET THIS TO MATCH YOUR IPHONE CHANNEL

// GPIO PINS
const int SWITCH_PINS[NUM_TILES] = {13, 14, 26, 33}; 
const int LED_PINS[NUM_TILES]    = {12, 27, 25, 32}; 

// Broadcast Address
uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// NeoPixels
Adafruit_NeoPixel rings[NUM_TILES] = {
  Adafruit_NeoPixel(LED_COUNT, LED_PINS[0], NEO_GRB + NEO_KHZ800),
  Adafruit_NeoPixel(LED_COUNT, LED_PINS[1], NEO_GRB + NEO_KHZ800),
  Adafruit_NeoPixel(LED_COUNT, LED_PINS[2], NEO_GRB + NEO_KHZ800),
  Adafruit_NeoPixel(LED_COUNT, LED_PINS[3], NEO_GRB + NEO_KHZ800)
};

// ================= STRUCTURES =================
typedef struct {
  uint8_t messageType;  
  uint8_t tileEspId;    
  uint8_t tilePort;     
  uint8_t value;        
  uint8_t globalTileId; 
} TileMessage;

typedef struct {
  uint8_t commandType;  
  uint8_t targetEspId;  
  uint8_t targetPort;   
  uint8_t color[3];     
  uint8_t duration;     
} MasterCommand;

struct TileState {
  bool stableState;
  bool lastReading;
  unsigned long lastDebounceTime;
  bool isRegistered;
  bool isToggledOn;
  uint32_t currentColor;
  bool isBlinking;
  unsigned long lastBlinkTime;
  bool blinkState;
};

TileState tiles[NUM_TILES];
const unsigned long debounceDelay = 40;
const unsigned long registrationBlinkInterval = 500;
unsigned long lastHeartbeat = 0;

// ================= PROTOTYPES =================
void onDataReceive(const esp_now_recv_info_t *info, const uint8_t *data, int len);
void onDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status); // FIXED TYPE
void updateSwitch(int i);
void updateLEDs();
void sendHeartbeat();
void startRegistrationMode();
void handleTilePress(int port);
void registerTile(int port);
void toggleTile(int port);
void executeCommand(int port, MasterCommand *cmd);

// ================= SETUP =================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.printf("\n=== Memory XXL Tile Hub %d ===\n", TILE_ESP_ID);

  // 1. Initialize WiFi in Station Mode
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();

  // 2. FORCE WIFI CHANNEL (Crucial for iPhone Hotspot)
  // We use promiscuous mode temporarily to force the channel change
  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false);
  Serial.printf("WiFi Channel forced to: %d\n", WIFI_CHANNEL);

  // 3. Init ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    ESP.restart();
  }

  // 4. Register Broadcast Peer (So we can talk to Master without knowing its MAC)
  esp_now_peer_info_t peerInfo = {};
  memset(&peerInfo, 0, sizeof(peerInfo));
  for (int i = 0; i < 6; i++) {
    peerInfo.peer_addr[i] = 0xFF;
  }
  peerInfo.channel = WIFI_CHANNEL; 
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    Serial.println("Failed to add broadcast peer");
  }

  // 5. Register Callbacks
  esp_now_register_recv_cb(onDataReceive);
  esp_now_register_send_cb(onDataSent);

  // 6. Hardware Init
  for (int i = 0; i < NUM_TILES; i++) {
    pinMode(SWITCH_PINS[i], INPUT_PULLUP);
    rings[i].begin(); rings[i].clear(); rings[i].show();
    tiles[i].stableState = HIGH; 
    tiles[i].lastReading = HIGH;
    tiles[i].isRegistered = false;
  }
  
  startRegistrationMode();
}

void loop() {
  unsigned long currentMillis = millis();
  
  for (int i = 0; i < NUM_TILES; i++) updateSwitch(i);
  updateLEDs();
  
  if (currentMillis - lastHeartbeat >= 2000) {
    sendHeartbeat();
    lastHeartbeat = currentMillis;
  }
}

// ================= FUNCTIONS =================

// SEND FUNCTIONS (Now use broadcastAddress instead of NULL)
void sendRegistrationMessage(int tilePort, uint8_t value) {
  TileMessage msg = {0, TILE_ESP_ID, (uint8_t)tilePort, value, (uint8_t)(TILE_ESP_ID * 4 + tilePort + 1)};
  esp_now_send(broadcastAddress, (uint8_t *)&msg, sizeof(msg));
}

void sendToggleMessage(int tilePort, uint8_t value) {
  TileMessage msg = {1, TILE_ESP_ID, (uint8_t)tilePort, value, (uint8_t)(TILE_ESP_ID * 4 + tilePort + 1)};
  esp_now_send(broadcastAddress, (uint8_t *)&msg, sizeof(msg));
}

void sendHeartbeat() {
  for (int i = 0; i < NUM_TILES; i++) {
    TileMessage msg = {2, TILE_ESP_ID, (uint8_t)i, (uint8_t)(tiles[i].isRegistered ? 1 : 0), (uint8_t)(TILE_ESP_ID * 4 + i + 1)};
    esp_now_send(broadcastAddress, (uint8_t *)&msg, sizeof(msg));
  }
}

// FIXED SEND CALLBACK
void onDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  // Do nothing, or debug print
}

// RECEIVE CALLBACK
void onDataReceive(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (len != sizeof(MasterCommand)) return;
  MasterCommand cmd;
  memcpy(&cmd, data, sizeof(cmd));

  if (cmd.targetEspId != 255 && cmd.targetEspId != TILE_ESP_ID) return;

  if (cmd.targetPort == 255) {
    for (int i = 0; i < NUM_TILES; i++) executeCommand(i, &cmd);
  } else if (cmd.targetPort < NUM_TILES) {
    executeCommand(cmd.targetPort, &cmd);
  }
}

// LOGIC HELPERS
void updateSwitch(int tilePort) {
  bool reading = digitalRead(SWITCH_PINS[tilePort]);
  if (reading != tiles[tilePort].lastReading) tiles[tilePort].lastDebounceTime = millis();
  
  if ((millis() - tiles[tilePort].lastDebounceTime) > debounceDelay) {
    if (reading != tiles[tilePort].stableState) {
      tiles[tilePort].stableState = reading;
      if (tiles[tilePort].stableState == LOW) handleTilePress(tilePort);
    }
  }
  tiles[tilePort].lastReading = reading;
}

void handleTilePress(int tilePort) {
  if (!tiles[tilePort].isRegistered) registerTile(tilePort);
  else toggleTile(tilePort);
}

void startRegistrationMode() {
  for (int i = 0; i < NUM_TILES; i++) {
    if (!tiles[i].isRegistered) {
      tiles[i].isBlinking = true;
      tiles[i].currentColor = rings[i].Color(0, 0, 255);
    }
  }
}

void registerTile(int tilePort) {
  tiles[tilePort].isRegistered = true;
  tiles[tilePort].isBlinking = false;
  tiles[tilePort].currentColor = rings[tilePort].Color(0, 255, 0);
  rings[tilePort].fill(tiles[tilePort].currentColor);
  rings[tilePort].show();
  sendRegistrationMessage(tilePort, 1);
  delay(500);
  rings[tilePort].clear(); rings[tilePort].show(); tiles[tilePort].currentColor = 0;
}

void toggleTile(int tilePort) {
  tiles[tilePort].isToggledOn = !tiles[tilePort].isToggledOn;
  if (tiles[tilePort].isToggledOn) {
    tiles[tilePort].currentColor = rings[tilePort].Color(0, 255, 0);
    rings[tilePort].fill(tiles[tilePort].currentColor);
  } else {
    tiles[tilePort].currentColor = 0;
    rings[tilePort].clear();
  }
  rings[tilePort].show();
  sendToggleMessage(tilePort, tiles[tilePort].isToggledOn ? 1 : 0);
}

void executeCommand(int tilePort, MasterCommand *cmd) {
  uint32_t color = rings[tilePort].Color(cmd->color[0], cmd->color[1], cmd->color[2]);
  switch (cmd->commandType) {
    case 0: tiles[tilePort].currentColor = 0; tiles[tilePort].isBlinking = false; rings[tilePort].clear(); break;
    case 1: tiles[tilePort].currentColor = color; tiles[tilePort].isBlinking = false; rings[tilePort].fill(color); break;
    case 2: tiles[tilePort].currentColor = color; tiles[tilePort].isBlinking = true; break;
    case 3: tiles[tilePort].currentColor = color; tiles[tilePort].isBlinking = false; rings[tilePort].fill(color); break;
  }
  rings[tilePort].show();
}

void updateLEDs() {
  unsigned long currentMillis = millis();
  for (int i = 0; i < NUM_TILES; i++) {
    if (tiles[i].isBlinking) {
      if (currentMillis - tiles[i].lastBlinkTime >= registrationBlinkInterval) {
        tiles[i].blinkState = !tiles[i].blinkState;
        tiles[i].lastBlinkTime = currentMillis;
        if (tiles[i].blinkState) rings[i].fill(tiles[i].currentColor);
        else rings[i].clear();
        rings[i].show();
      }
    }
  }
}