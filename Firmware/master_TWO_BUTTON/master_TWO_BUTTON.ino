/**
 * Memory XXL - Master ESP32 (TWO-BUTTON SYSTEM)
 * 
 * Game Flow:
 * 1. Press START → Show pattern
 * 2. Player steps on tiles (tiles light up)
 * 3. Press START again → Check if correct
 */

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>

// ==================== CONFIGURATION ====================
const char* WIFI_SSID = "iPhone";
const char* WIFI_PASSWORD = "eveneven";
const char* WS_HOST = "172.20.10.9";
const uint16_t WS_PORT = 8000;

#define START_BUTTON_PIN 15
#define STATUS_LED_PIN 2
#define MAX_TILES 16

// ==================== STRUCTURES ====================
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

struct TileInfo {
  uint8_t id;
  uint8_t macAddress[6];
  bool isConnected;
  bool isLit;  // Track if tile is currently lit
  unsigned long lastSeen;
  uint8_t batteryLevel;
};

// ==================== GLOBALS ====================
WebSocketsClient webSocket;
TileInfo registeredTiles[MAX_TILES];
uint8_t tileCount = 0;

bool lastButtonState = HIGH;
unsigned long lastDebounceTime = 0;
unsigned long lastHeartbeat = 0;
unsigned long lastTileCheck = 0;
bool wsConnected = false;

// ==================== SETUP ====================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== Memory XXL Master (Two-Button) ===");
  
  pinMode(START_BUTTON_PIN, INPUT_PULLUP);
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);
  
  for (int i = 0; i < MAX_TILES; i++) {
    registeredTiles[i].isConnected = false;
    registeredTiles[i].isLit = false;
  }
  
  initWiFi();
  initESPNow();
  initWebSocket();
  
  Serial.println("✓ Master ready!");
}

// ==================== LOOP ====================
void loop() {
  unsigned long currentMillis = millis();
  
  webSocket.loop();
  
  // Start button
  if (handleStartButton()) {
    Serial.println("→ START pressed!");
    if (wsConnected) {
      StaticJsonDocument<200> doc;
      doc["master_id"] = WiFi.macAddress();
      sendToBackend("start_button_pressed", doc);
    }
  }
  
  // Check tile connections
  if (currentMillis - lastTileCheck > 5000) {
    checkTileConnections();
    lastTileCheck = currentMillis;
  }
  
  // Heartbeat
  if (wsConnected && currentMillis - lastHeartbeat > 3000) {
    sendTileStatus();
    lastHeartbeat = currentMillis;
  }
  
  delay(10);
}

// ==================== WIFI ====================
void initWiFi() {
  Serial.println("→ Connecting to WiFi...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✓ WiFi connected!");
    Serial.print("  IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("  MAC: ");
    Serial.println(WiFi.macAddress());
    
    uint8_t channel;
    wifi_second_chan_t secondChan;
    esp_wifi_get_channel(&channel, &secondChan);
    Serial.printf("  Channel: %d\n", channel);
  }
}

// ==================== ESP-NOW ====================
void initESPNow() {
  if (esp_now_init() != ESP_OK) {
    Serial.println("✗ ESP-NOW failed");
    return;
  }
  
  Serial.println("✓ ESP-NOW initialized");
  esp_now_register_recv_cb(onTileMessage);
}

void onTileMessage(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (len != sizeof(TileMessage)) return;
  
  TileMessage msg;
  memcpy(&msg, data, sizeof(msg));
  
  switch (msg.messageType) {
    case 0: // Registration
      registerTile(msg.tileId, info->src_addr);
      break;
      
    case 1: // Step detected
      if (msg.value == 1) {
        handleTileStep(msg.tileId);
      }
      break;
      
    case 2: // Heartbeat
      for (int i = 0; i < tileCount; i++) {
        if (registeredTiles[i].id == msg.tileId) {
          registeredTiles[i].lastSeen = millis();
          break;
        }
      }
      break;
  }
}

void registerTile(uint8_t tileId, const uint8_t *mac) {
  // Check if already registered
  for (int i = 0; i < tileCount; i++) {
    if (registeredTiles[i].id == tileId) {
      Serial.printf("→ Tile %d re-registered\n", tileId);
      registeredTiles[i].lastSeen = millis();
      registeredTiles[i].isConnected = true;
      sendCommandToTile(tileId, 3);  // ACK
      return;
    }
  }
  
  // New registration
  if (tileCount < MAX_TILES) {
    registeredTiles[tileCount].id = tileId;
    memcpy(registeredTiles[tileCount].macAddress, mac, 6);
    registeredTiles[tileCount].isConnected = true;
    registeredTiles[tileCount].isLit = false;
    registeredTiles[tileCount].lastSeen = millis();
    registeredTiles[tileCount].batteryLevel = 100;
    
    // Add peer
    esp_now_peer_info_t peerInfo = {};
    memcpy(peerInfo.peer_addr, mac, 6);
    peerInfo.channel = 0;  // Auto
    peerInfo.encrypt = false;
    
    if (esp_now_add_peer(&peerInfo) == ESP_OK) {
      tileCount++;
      Serial.printf("✓ Tile %d registered (Total: %d)\n", tileId, tileCount);
      
      sendCommandToTile(tileId, 3);  // ACK
      
      if (wsConnected) {
        sendTileStatus();
      }
    }
  }
}

void handleTileStep(uint8_t tileId) {
  Serial.printf("→ Tile %d STEP!\n", tileId);
  
  // Find tile and toggle LED
  for (int i = 0; i < tileCount; i++) {
    if (registeredTiles[i].id == tileId) {
      registeredTiles[i].isLit = !registeredTiles[i].isLit;
      
      // Send command to toggle LED
      sendCommandToTile(tileId, registeredTiles[i].isLit ? 1 : 0);
      
      Serial.printf("  Tile %d is now %s\n", tileId, registeredTiles[i].isLit ? "LIT" : "OFF");
      break;
    }
  }
  
  // Notify backend
  if (wsConnected) {
    StaticJsonDocument<200> doc;
    doc["tile_id"] = tileId;
    doc["timestamp"] = millis();
    sendToBackend("player_step", doc);
  }
}

void sendCommandToTile(uint8_t tileId, uint8_t command) {
  for (int i = 0; i < tileCount; i++) {
    if (registeredTiles[i].id == tileId && registeredTiles[i].isConnected) {
      MasterCommand cmd;
      cmd.tileId = tileId;
      cmd.command = command;
      cmd.duration = 0;
      
      esp_now_send(registeredTiles[i].macAddress, (uint8_t *)&cmd, sizeof(cmd));
      return;
    }
  }
}

void sendCommandToAllTiles(uint8_t command) {
  for (int i = 0; i < tileCount; i++) {
    if (registeredTiles[i].isConnected) {
      sendCommandToTile(registeredTiles[i].id, command);
      
      // Update lit status
      if (command == 0) {
        registeredTiles[i].isLit = false;
      } else if (command == 1) {
        registeredTiles[i].isLit = true;
      }
    }
  }
}

void checkTileConnections() {
  unsigned long now = millis();
  bool changed = false;
  
  for (int i = 0; i < tileCount; i++) {
    if (registeredTiles[i].isConnected) {
      if (now - registeredTiles[i].lastSeen > 10000) {
        registeredTiles[i].isConnected = false;
        changed = true;
        Serial.printf("✗ Tile %d timeout\n", registeredTiles[i].id);
      }
    }
  }
  
  if (changed && wsConnected) {
    sendTileStatus();
  }
}

// ==================== WEBSOCKET ====================
void initWebSocket() {
  webSocket.begin(WS_HOST, WS_PORT, "/ws/master");
  webSocket.onEvent(wsEvent);
  webSocket.setReconnectInterval(5000);
  Serial.println("✓ WebSocket initialized");
}

void wsEvent(WStype_t type, uint8_t *payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      wsConnected = false;
      digitalWrite(STATUS_LED_PIN, LOW);
      Serial.println("✗ WebSocket disconnected");
      break;
      
    case WStype_CONNECTED:
      wsConnected = true;
      digitalWrite(STATUS_LED_PIN, HIGH);
      Serial.println("✓ WebSocket connected");
      
      // Register
      {
        StaticJsonDocument<200> doc;
        doc["master_id"] = WiFi.macAddress();
        doc["tile_count"] = tileCount;
        sendToBackend("master_connected", doc);
      }
      break;
      
    case WStype_TEXT:
      handleBackendMessage(String((char*)payload));
      break;
  }
}

void handleBackendMessage(String msg) {
  StaticJsonDocument<512> doc;
  if (deserializeJson(doc, msg)) return;
  
  String event = doc["event"];
  Serial.printf("← Backend: %s\n", event.c_str());
  
  if (event == "show_pattern") {
    // Show pattern on tiles
    JsonArray pattern = doc["data"]["pattern"];
    Serial.print("  Pattern: ");
    
    // Turn off all first
    sendCommandToAllTiles(0);
    delay(500);
    
    // Show pattern
    for (int i = 0; i < pattern.size(); i++) {
      uint8_t tileId = pattern[i];
      Serial.printf("%d ", tileId);
      
      sendCommandToTile(tileId, 1);  // ON
      delay(800);
      sendCommandToTile(tileId, 0);  // OFF
      delay(400);
    }
    Serial.println();
    
    // Notify done
    StaticJsonDocument<100> resp;
    resp["status"] = "complete";
    sendToBackend("pattern_shown", resp);
  }
  else if (event == "light_tile") {
    // Light up or turn off a specific tile
    uint8_t tileId = doc["data"]["tile_id"];
    bool on = doc["data"]["on"];
    
    Serial.printf("  %s Tile %d\n", on ? "Light" : "Off", tileId);
    sendCommandToTile(tileId, on ? 1 : 0);
  }
  else if (event == "end_game") {
    // Turn off all tiles
    Serial.println("  Turning off all tiles");
    sendCommandToAllTiles(0);
  }
}

// ==================== HELPERS ====================
bool handleStartButton() {
  bool current = digitalRead(START_BUTTON_PIN);
  
  if (current != lastButtonState) {
    lastDebounceTime = millis();
  }
  
  if ((millis() - lastDebounceTime) > 50) {
    if (current == LOW && lastButtonState == HIGH) {
      lastButtonState = current;
      return true;
    }
  }
  
  lastButtonState = current;
  return false;
}

void sendTileStatus() {
  StaticJsonDocument<1024> doc;
  doc["master_id"] = WiFi.macAddress();
  
  JsonArray tiles = doc.createNestedArray("tiles");
  for (int i = 0; i < tileCount; i++) {
    JsonObject tile = tiles.createNestedObject();
    tile["id"] = registeredTiles[i].id;
    tile["connected"] = registeredTiles[i].isConnected;
    tile["battery"] = registeredTiles[i].batteryLevel;
  }
  
  sendToBackend("tile_status", doc);
}

void sendToBackend(String event, JsonDocument &data) {
  if (!wsConnected) return;
  
  StaticJsonDocument<2048> msg;
  msg["event"] = event;
  msg["data"] = data;
  
  String output;
  serializeJson(msg, output);
  webSocket.sendTXT(output);
}
