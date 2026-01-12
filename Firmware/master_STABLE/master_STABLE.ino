/**
 * Memory XXL - Master ESP32 (STABLE VERSION)
 * 
 * Optimized for stability:
 * - Reduced JSON buffer sizes
 * - Fewer simultaneous operations
 * - Better task separation
 * - Watchdog management
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
#define MAX_TILES 8  // Reduced from 16 for stability

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
  bool isLit;
  unsigned long lastSeen;
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

// Queues for deferred operations
bool pendingTileStatus = false;
bool pendingStartButton = false;
uint8_t pendingStepTileId = 0;

// ==================== SETUP ====================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== Memory XXL Master (Stable) ===");
  
  pinMode(START_BUTTON_PIN, INPUT_PULLUP);
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);
  
  for (int i = 0; i < MAX_TILES; i++) {
    registeredTiles[i].isConnected = false;
    registeredTiles[i].isLit = false;
  }
  
  initWiFi();
  delay(500);  // Let WiFi settle
  
  initESPNow();
  delay(500);  // Let ESP-NOW settle
  
  initWebSocket();
  
  Serial.println("✓ Master ready!");
  Serial.printf("Free heap: %d bytes\n", ESP.getFreeHeap());
}

// ==================== LOOP ====================
void loop() {
  unsigned long currentMillis = millis();
  
  // WebSocket loop (priority 1)
  webSocket.loop();
  yield();
  
  // Check button
  if (handleStartButton()) {
    pendingStartButton = true;
  }
  
  // Process deferred operations (one per loop)
  if (wsConnected) {
    if (pendingStartButton) {
      sendStartButton();
      pendingStartButton = false;
    }
    else if (pendingStepTileId > 0) {
      sendStepEvent(pendingStepTileId);
      pendingStepTileId = 0;
    }
    else if (pendingTileStatus && currentMillis - lastHeartbeat > 3000) {
      sendTileStatus();
      pendingTileStatus = false;
      lastHeartbeat = currentMillis;
    }
  }
  
  // Check tile connections (low priority)
  if (currentMillis - lastTileCheck > 10000) {
    checkTileConnections();
    lastTileCheck = currentMillis;
  }
  
  delay(10);
  yield();
}

// ==================== WIFI ====================
void initWiFi() {
  Serial.println("→ Connecting WiFi...");
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
  
  // Handle registration immediately
  if (msg.messageType == 0) {
    registerTile(msg.tileId, info->src_addr);
  }
  // Defer step handling
  else if (msg.messageType == 1 && msg.value == 1) {
    handleTileStepLocal(msg.tileId);
    pendingStepTileId = msg.tileId;  // Send to backend later
  }
  // Update heartbeat
  else if (msg.messageType == 2) {
    for (int i = 0; i < tileCount; i++) {
      if (registeredTiles[i].id == msg.tileId) {
        registeredTiles[i].lastSeen = millis();
        break;
      }
    }
  }
}

void registerTile(uint8_t tileId, const uint8_t *mac) {
  // Check if already registered
  for (int i = 0; i < tileCount; i++) {
    if (registeredTiles[i].id == tileId) {
      Serial.printf("→ Tile %d re-reg\n", tileId);
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
    
    // Add peer
    esp_now_peer_info_t peerInfo = {};
    memcpy(peerInfo.peer_addr, mac, 6);
    peerInfo.channel = 0;
    peerInfo.encrypt = false;
    
    if (esp_now_add_peer(&peerInfo) == ESP_OK) {
      tileCount++;
      Serial.printf("✓ Tile %d (Total: %d)\n", tileId, tileCount);
      
      // Send ACK immediately
      sendCommandToTile(tileId, 3);
      
      // Defer backend notification
      pendingTileStatus = true;
    }
  }
}

void handleTileStepLocal(uint8_t tileId) {
  // Toggle LED locally (fast)
  for (int i = 0; i < tileCount; i++) {
    if (registeredTiles[i].id == tileId) {
      registeredTiles[i].isLit = !registeredTiles[i].isLit;
      sendCommandToTile(tileId, registeredTiles[i].isLit ? 1 : 0);
      Serial.printf("→ Tile %d %s\n", tileId, registeredTiles[i].isLit ? "ON" : "OFF");
      break;
    }
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
      if (command == 0) registeredTiles[i].isLit = false;
      else if (command == 1) registeredTiles[i].isLit = true;
      delay(10);  // Small delay between commands
    }
  }
}

void checkTileConnections() {
  unsigned long now = millis();
  for (int i = 0; i < tileCount; i++) {
    if (registeredTiles[i].isConnected) {
      if (now - registeredTiles[i].lastSeen > 15000) {
        registeredTiles[i].isConnected = false;
        Serial.printf("✗ Tile %d timeout\n", registeredTiles[i].id);
        pendingTileStatus = true;
      }
    }
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
      
      // Send simple registration
      webSocket.sendTXT("{\"event\":\"master_connected\",\"data\":{\"master_id\":\"master\"}}");
      
      // Queue tile status for next loop
      pendingTileStatus = true;
      break;
      
    case WStype_TEXT:
      handleBackendMessage(String((char*)payload));
      break;
  }
}

void handleBackendMessage(String msg) {
  // Simple parsing - avoid large JSON operations
  if (msg.indexOf("\"show_pattern\"") > 0) {
    // Extract pattern manually (more stable than JSON parsing)
    int patternStart = msg.indexOf("[", msg.indexOf("pattern")) + 1;
    int patternEnd = msg.indexOf("]", patternStart);
    String patternStr = msg.substring(patternStart, patternEnd);
    
    Serial.println("← Pattern command");
    
    // Turn off all
    sendCommandToAllTiles(0);
    delay(500);
    
    // Parse and show pattern
    int pos = 0;
    while (pos < patternStr.length()) {
      int tileId = patternStr.substring(pos, pos + 2).toInt();
      if (tileId > 0) {
        Serial.printf("  Show: %d\n", tileId);
        sendCommandToTile(tileId, 1);
        delay(800);
        sendCommandToTile(tileId, 0);
        delay(400);
      }
      pos = patternStr.indexOf(",", pos) + 1;
      if (pos == 0) break;
    }
    
    webSocket.sendTXT("{\"event\":\"pattern_shown\",\"data\":{\"status\":\"complete\"}}");
  }
  else if (msg.indexOf("\"light_tile\"") > 0) {
    // Extract tile_id and on state
    int tidStart = msg.indexOf("tile_id") + 10;
    int tidEnd = msg.indexOf(",", tidStart);
    int tileId = msg.substring(tidStart, tidEnd).toInt();
    
    bool on = msg.indexOf("\"on\":true") > 0;
    
    Serial.printf("← Light tile %d: %s\n", tileId, on ? "ON" : "OFF");
    sendCommandToTile(tileId, on ? 1 : 0);
  }
  else if (msg.indexOf("\"end_game\"") > 0) {
    Serial.println("← End game");
    sendCommandToAllTiles(0);
  }
}

// ==================== DEFERRED OPERATIONS ====================
void sendStartButton() {
  if (!wsConnected) return;
  
  Serial.println("→ Sending START");
  webSocket.sendTXT("{\"event\":\"start_button_pressed\",\"data\":{}}");
}

void sendStepEvent(uint8_t tileId) {
  if (!wsConnected) return;
  
  Serial.printf("→ Sending step: %d\n", tileId);
  
  char msg[100];
  snprintf(msg, sizeof(msg), 
    "{\"event\":\"player_step\",\"data\":{\"tile_id\":%d,\"timestamp\":%lu}}", 
    tileId, millis());
  webSocket.sendTXT(msg);
}

void sendTileStatus() {
  if (!wsConnected) return;
  
  Serial.println("→ Sending tile status");
  
  // Build simple JSON manually (more stable)
  String msg = "{\"event\":\"tile_status\",\"data\":{\"tiles\":[";
  
  for (int i = 0; i < tileCount; i++) {
    if (i > 0) msg += ",";
    msg += "{\"id\":";
    msg += registeredTiles[i].id;
    msg += ",\"connected\":";
    msg += registeredTiles[i].isConnected ? "true" : "false";
    msg += ",\"battery\":100}";
  }
  
  msg += "]}}";
  webSocket.sendTXT(msg);
}

// ==================== BUTTON ====================
bool handleStartButton() {
  bool current = digitalRead(START_BUTTON_PIN);
  
  if (current != lastButtonState) {
    lastDebounceTime = millis();
  }
  
  if ((millis() - lastDebounceTime) > 50) {
    if (current == LOW && lastButtonState == HIGH) {
      lastButtonState = current;
      Serial.println("START!");
      return true;
    }
  }
  
  lastButtonState = current;
  return false;
}
