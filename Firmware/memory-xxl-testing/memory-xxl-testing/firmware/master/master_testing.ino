/**
 * Memory XXL - Master ESP32 (TESTING VERSION - Jan 9, 2025)
 * 
 * Simplified and stable for demo day
 * ESP32 Core 3.x Compatible
 */

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>

// ==================== CONFIGURATION ====================
// !!! UPDATE THESE BEFORE TESTING !!!
const char* WIFI_SSID = "iPhone";
const char* WIFI_PASSWORD = "eveneven";
const char* WS_HOST = "172.20.10.11";  // Your laptop's IP
const uint16_t WS_PORT = 8000;

#define START_BUTTON_PIN 15
#define STATUS_LED_PIN 2
#define MAX_TILES 16

// ==================== STRUCTURES ====================
typedef struct {
  uint8_t tileId;
  uint8_t messageType;  // 0=reg, 1=step, 2=heartbeat, 3=battery
  uint8_t value;
  uint8_t batteryLevel;
} TileMessage;

typedef struct {
  uint8_t tileId;
  uint8_t command;  // 0=off, 1=on, 2=blink, 3=ack
  uint8_t duration;
} MasterCommand;

struct TileInfo {
  uint8_t id;
  uint8_t macAddress[6];
  bool isConnected;
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

const unsigned long DEBOUNCE_DELAY = 50;
const unsigned long HEARTBEAT_INTERVAL = 3000;
const unsigned long TILE_TIMEOUT = 10000;

// ==================== SETUP ====================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== Memory XXL Master (Testing) ===");
  Serial.println("Version: Jan 9, 2025");
  
  pinMode(START_BUTTON_PIN, INPUT_PULLUP);
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);
  
  for (int i = 0; i < MAX_TILES; i++) {
    registeredTiles[i].isConnected = false;
  }
  
  initWiFi();
  initESPNow();
  initWebSocket();
  
  Serial.println("✓ Master ready!");
  digitalWrite(STATUS_LED_PIN, HIGH);
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
      doc["tile_count"] = tileCount;
      sendToBackend("start_button_pressed", doc);
    }
  }
  
  // Check tile connections
  if (currentMillis - lastTileCheck > 5000) {
    checkTileConnections();
    lastTileCheck = currentMillis;
  }
  
  // Heartbeat
  if (wsConnected && currentMillis - lastHeartbeat > HEARTBEAT_INTERVAL) {
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
    
    // Get WiFi channel
    uint8_t channel;
    wifi_second_chan_t secondChan;
    esp_wifi_get_channel(&channel, &secondChan);
    Serial.printf("  Channel: %d\n", channel);
  } else {
    Serial.println("\n✗ WiFi failed!");
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
      
    case 1: // Step
      if (msg.value == 1) {
        Serial.printf("→ Tile %d stepped!\n", msg.tileId);
        if (wsConnected) {
          StaticJsonDocument<200> doc;
          doc["tile_id"] = msg.tileId;
          doc["timestamp"] = millis();
          sendToBackend("player_step", doc);
        }
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
      sendCommandToTile(tileId, 3);  // Send ACK
      return;
    }
  }
  
  // New registration
  if (tileCount < MAX_TILES) {
    registeredTiles[tileCount].id = tileId;
    memcpy(registeredTiles[tileCount].macAddress, mac, 6);
    registeredTiles[tileCount].isConnected = true;
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
      
      // Send ACK
      sendCommandToTile(tileId, 3);
      
      // Notify backend
      if (wsConnected) {
        sendTileStatus();
      }
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
    }
  }
}

void checkTileConnections() {
  unsigned long now = millis();
  bool changed = false;
  
  for (int i = 0; i < tileCount; i++) {
    if (registeredTiles[i].isConnected) {
      if (now - registeredTiles[i].lastSeen > TILE_TIMEOUT) {
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
    JsonArray pattern = doc["data"]["pattern"];
    Serial.print("  Pattern: ");
    
    // Turn off all
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
  else if (event == "end_game") {
    sendCommandToAllTiles(0);
    Serial.println("  Game ended");
  }
}

// ==================== HELPERS ====================
bool handleStartButton() {
  bool current = digitalRead(START_BUTTON_PIN);
  
  if (current != lastButtonState) {
    lastDebounceTime = millis();
  }
  
  if ((millis() - lastDebounceTime) > DEBOUNCE_DELAY) {
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
