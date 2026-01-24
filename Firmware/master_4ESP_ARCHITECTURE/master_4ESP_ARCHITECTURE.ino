/**
 * Memory XXL - MASTER ESP32
 * INTEGRATED FIXES: 
 * 1. Button Reading Logic (GPIO 13)
 * 2. ESP-NOW v3.0+ Callback Compatibility
 * 3. WiFi Channel Printing for Hub Sync
 */

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <WebSocketsClient.h>

// ==================== CONFIGURATION ====================
const char* WIFI_SSID = "iPhone";
const char* WIFI_PASSWORD = "eveneven";
const char* WS_HOST = "memo-motion.azurewebsites.net";
const uint16_t WS_PORT = 443;

#define START_BUTTON_PIN 13
#define STATUS_LED_PIN 2
#define MAX_TILES 12
#define NUM_TILE_ESPS 3

// Broadcast address (Send to everyone)
uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// ==================== STRUCTURES ====================
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

struct TileInfo {
  uint8_t globalId;     
  uint8_t espId;        
  uint8_t port;         
  bool isRegistered;
  bool isConnected;
  bool isToggledOn;
  unsigned long lastSeen;
};

// ==================== GLOBALS ====================
WebSocketsClient webSocket;
TileInfo tiles[MAX_TILES];
int registeredTileCount = 0;
bool wsConnected = false;
unsigned long lastHeartbeat = 0;

// ESP Hub tracking
bool espConnected[NUM_TILE_ESPS] = {false, false, false};
unsigned long espLastSeen[NUM_TILE_ESPS] = {0, 0, 0};
const unsigned long ESP_TIMEOUT = 5000; // 5 seconds

// Button state tracking
bool lastButtonState = HIGH;
unsigned long lastButtonPress = 0;

// ==================== PROTOTYPES ====================
void initWiFi();
void initESPNow();
void initWebSocket();
void onTileMessage(const esp_now_recv_info_t *info, const uint8_t *data, int len);
void onDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status);
void handleRegistrationMessage(TileMessage *msg, const uint8_t *mac);
void handleToggleMessage(TileMessage *msg);
void handleHeartbeatMessage(TileMessage *msg);
void sendTileStatusToBackend();
void sendCommandToTile(uint8_t espId, uint8_t port, uint8_t commandType, uint8_t r, uint8_t g, uint8_t b);
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length);
void handleBackendMessage(String msg);

// ==================== SETUP ====================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== Memory XXL Master ESP ===");

  pinMode(START_BUTTON_PIN, INPUT_PULLUP);
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);
  
  // Initialize tile array
  for (int i = 0; i < MAX_TILES; i++) {
    tiles[i].globalId = i + 1;
    tiles[i].espId = i / 4;  // FIXED: Each hub has 4 tiles, not 3
    tiles[i].port = i % 4;   // FIXED: Port 0-3, not 0-2
    tiles[i].isRegistered = false;
    tiles[i].isConnected = false;
    tiles[i].lastSeen = 0;
  }
  
  initWiFi();     
  initESPNow();   
  initWebSocket();
}

// ==================== MAIN LOOP ====================
void loop() {
  webSocket.loop();
  unsigned long currentMillis = millis();

  // --- START BUTTON HANDLING ---
  bool currentButtonState = digitalRead(START_BUTTON_PIN);
  if (currentButtonState == LOW && lastButtonState == HIGH) {
    if (currentMillis - lastButtonPress > 300) { // Debounce
      Serial.println("👉 START BUTTON PRESSED");
      if (wsConnected) {
        webSocket.sendTXT("{\"event\":\"start_button_pressed\",\"data\":{}}");
      } else {
        Serial.println("⚠️ Button pressed, but WebSocket is not connected!");
      }
      lastButtonPress = currentMillis;
    }
  }
  lastButtonState = currentButtonState;

  // --- PERIODIC STATUS UPDATE ---
  if (wsConnected && currentMillis - lastHeartbeat > 5000) { // Reduced from 2s to 5s
    sendTileStatusToBackend();
    lastHeartbeat = currentMillis;
  }
}

// ==================== WIFI & ESP-NOW ====================
void initWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✓ WiFi Connected");
  Serial.print("📡 CURRENT WIFI CHANNEL: ");
  Serial.println(WiFi.channel()); // Hubs MUST match this channel
}

void initESPNow() {
  if (esp_now_init() != ESP_OK) {
    Serial.println("❌ ESP-NOW Init Failed");
    ESP.restart();
  }
  
  // Register Broadcast Peer
  esp_now_peer_info_t peerInfo = {};
  memset(&peerInfo, 0, sizeof(peerInfo));
  for (int i = 0; i < 6; i++) peerInfo.peer_addr[i] = 0xFF;
  peerInfo.channel = 0; 
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("❌ Failed to add broadcast peer");
  }

  esp_now_register_recv_cb(onTileMessage);
  esp_now_register_send_cb(onDataSent);
}

void onDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  // Callback required by library
}

void onTileMessage(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (len != sizeof(TileMessage)) return;
  TileMessage msg;
  memcpy(&msg, data, sizeof(msg));

  // Add the hub as a peer if we haven't seen it yet
  if (!esp_now_is_peer_exist(info->src_addr)) {
    esp_now_peer_info_t peerInfo = {};
    memcpy(peerInfo.peer_addr, info->src_addr, 6);
    peerInfo.channel = 0;
    peerInfo.encrypt = false;
    esp_now_add_peer(&peerInfo);
  }

  switch (msg.messageType) {
    case 0: handleRegistrationMessage(&msg, info->src_addr); break;
    case 1: handleToggleMessage(&msg); break;
    case 2: handleHeartbeatMessage(&msg); break;
  }
}

// ==================== HANDLERS ====================
void handleRegistrationMessage(TileMessage *msg, const uint8_t *mac) {
  int tileIndex = msg->globalTileId - 1;
  if (tileIndex < 0 || tileIndex >= MAX_TILES) return;
  
  // Mark ESP as connected when we receive registration
  if (msg->tileEspId < NUM_TILE_ESPS) {
    espConnected[msg->tileEspId] = true;
    espLastSeen[msg->tileEspId] = millis();
  }
  
  if (!tiles[tileIndex].isRegistered) {
    tiles[tileIndex].isRegistered = true;
    registeredTileCount++;
    Serial.printf("✓ Tile %d Registered (ESP %d)\n", msg->globalTileId, msg->tileEspId + 1);
    
    // Flash Green ACK
    sendCommandToTile(msg->tileEspId, msg->tilePort, 1, 0, 255, 0); 
    delay(50);
    sendCommandToTile(msg->tileEspId, msg->tilePort, 0, 0, 0, 0);
    
    // Send updated status to backend
    sendTileStatusToBackend();
  }
}

void handleToggleMessage(TileMessage *msg) {
  int tileIndex = msg->globalTileId - 1;
  if (tileIndex >= 0 && tileIndex < MAX_TILES) {
    // Auto-register if not already registered (handles master resets)
    if (!tiles[tileIndex].isRegistered) {
      tiles[tileIndex].isRegistered = true;
      registeredTileCount++;
      Serial.printf("✓ Tile %d Auto-Registered (ESP %d)\n", msg->globalTileId, msg->tileEspId + 1);
      
      // Mark ESP as connected
      if (msg->tileEspId < NUM_TILE_ESPS) {
        espConnected[msg->tileEspId] = true;
        espLastSeen[msg->tileEspId] = millis();
      }
      
      // Flash green to acknowledge registration
      sendCommandToTile(msg->tileEspId, msg->tilePort, 1, 0, 255, 0);
      delay(50);
      sendCommandToTile(msg->tileEspId, msg->tilePort, 0, 0, 0, 0);
      
      sendTileStatusToBackend();
    }
    
    tiles[tileIndex].isToggledOn = (msg->value == 1);
    Serial.printf("🔄 Tile %d Step: %d\n", msg->globalTileId, msg->value);
    
    if (wsConnected) {
       char buffer[128];
       sprintf(buffer, "{\"event\":\"player_step\",\"data\":{\"tile_id\":%d,\"is_on\":%s}}", 
               msg->globalTileId, tiles[tileIndex].isToggledOn ? "true" : "false");
       webSocket.sendTXT(buffer);
    }
  }
}

void handleHeartbeatMessage(TileMessage *msg) {
  int tileIndex = msg->globalTileId - 1;
  if (tileIndex >= 0 && tileIndex < MAX_TILES) {
    tiles[tileIndex].isConnected = true;
    tiles[tileIndex].lastSeen = millis();
    
    // Mark ESP as connected when we receive heartbeat
    if (msg->tileEspId < NUM_TILE_ESPS) {
      espConnected[msg->tileEspId] = true;
      espLastSeen[msg->tileEspId] = millis();
    }
  }
}

void sendCommandToTile(uint8_t espId, uint8_t port, uint8_t commandType, uint8_t r, uint8_t g, uint8_t b) {
  MasterCommand cmd;
  cmd.commandType = commandType;
  cmd.targetEspId = espId;
  cmd.targetPort = port;
  cmd.color[0] = r; cmd.color[1] = g; cmd.color[2] = b;
  esp_now_send(broadcastAddress, (uint8_t *)&cmd, sizeof(cmd));
}

// ==================== WEBSOCKET ====================
void initWebSocket() {
  webSocket.beginSSL(WS_HOST, WS_PORT, "/ws/master");
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(3000);
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_CONNECTED:
      Serial.println("✓ WebSocket Connected");
      wsConnected = true;
      digitalWrite(STATUS_LED_PIN, HIGH);
      
      // Send master identification message
      {
        String macStr = WiFi.macAddress();
        macStr.replace(":", "");
        String json = "{\"event\":\"master_connected\",\"data\":{\"master_id\":\"";
        json += macStr;
        json += "\"}}";
        webSocket.sendTXT(json);
        Serial.println("📤 Sent master_connected");
      }
      
      // Send initial tile status
      sendTileStatusToBackend();
      break;
    case WStype_DISCONNECTED:
      Serial.println("❌ WebSocket Disconnected");
      wsConnected = false;
      digitalWrite(STATUS_LED_PIN, LOW);
      break;
    case WStype_TEXT:
      handleBackendMessage(String((char*)payload));
      break;
  }
}

void sendTileStatusToBackend() {
  if (!wsConnected) return;
  
  // Check for ESP timeouts
  unsigned long currentMillis = millis();
  int connectedEspCount = 0;
  for (int i = 0; i < NUM_TILE_ESPS; i++) {
    if (espConnected[i]) {
      if (currentMillis - espLastSeen[i] > ESP_TIMEOUT) {
        espConnected[i] = false;
        Serial.printf("⚠️ ESP %d timeout\n", i + 1);
      } else {
        connectedEspCount++;
      }
    }
  }
  
  // Build JSON with tile status AND ESP status
  String json = "{\"event\":\"tile_status\",\"data\":{";
  
  // Tiles array
  json += "\"tiles\":[";
  bool first = true;
  for (int i = 0; i < MAX_TILES; i++) {
    if (tiles[i].isRegistered) {
      if (!first) json += ",";
      json += "{\"id\":"; json += tiles[i].globalId;
      json += ",\"connected\":true,\"battery\":100}";
      first = false;
    }
  }
  json += "],";
  
  // ESP array
  json += "\"tile_esps\":[";
  for (int i = 0; i < NUM_TILE_ESPS; i++) {
    if (i > 0) json += ",";
    json += "{\"id\":"; json += (i + 1);
    json += ",\"connected\":"; json += espConnected[i] ? "true" : "false";
    json += "}";
  }
  json += "],";
  
  json += "\"registered_count\":";
  json += registeredTileCount;
  json += "}}";
  
  // Debug print
  Serial.printf("📤 Tiles:%d ESPs:%d/%d\n", registeredTileCount, connectedEspCount, NUM_TILE_ESPS);
  
  webSocket.sendTXT(json);
}

void handleBackendMessage(String msg) {
  Serial.printf("📥 Backend: %s\n", msg.c_str());
  
  // Parse JSON to extract event
  if (msg.indexOf("\"event\":\"game_started\"") >= 0) {
    // Turn off all tiles - send multiple times to ensure reliability
    Serial.println("🔴 Game started - turning off all tiles...");
    for (int repeat = 0; repeat < 2; repeat++) {
      for (int i = 0; i < NUM_TILE_ESPS; i++) {
        for (int port = 0; port < 4; port++) {
          sendCommandToTile(i, port, 0, 0, 0, 0);
          delay(5);
        }
      }
      delay(50);
    }
    Serial.println("✓ All tiles off - pattern will show on website only");
  }
  else if (msg.indexOf("\"event\":\"selecting_phase\"") >= 0) {
    Serial.println("👉 Player's turn - waiting for tile selection");
    // Turn off all tiles to prepare for player selection - send twice for reliability
    for (int repeat = 0; repeat < 2; repeat++) {
      for (int i = 0; i < NUM_TILE_ESPS; i++) {
        for (int port = 0; port < 4; port++) {
          sendCommandToTile(i, port, 0, 0, 0, 0);
          delay(5);
        }
      }
      delay(50);
    }
  }
  else if (msg.indexOf("\"event\":\"pattern_correct\"") >= 0) {
    Serial.println("🎉 Correct pattern!");
    // Flash all registered tiles green
    for (int i = 0; i < MAX_TILES; i++) {
      if (tiles[i].isRegistered) {
        sendCommandToTile(tiles[i].espId, tiles[i].port, 1, 0, 255, 0);
      }
    }
    delay(500);
    for (int i = 0; i < MAX_TILES; i++) {
      if (tiles[i].isRegistered) {
        sendCommandToTile(tiles[i].espId, tiles[i].port, 0, 0, 0, 0);
      }
    }
  }
  else if (msg.indexOf("\"event\":\"game_over\"") >= 0 || msg.indexOf("\"event\":\"end_game\"") >= 0) {
    Serial.println("❌ Game Over - turning off all tiles");
    // Turn off all tiles - send multiple times for reliability
    for (int repeat = 0; repeat < 3; repeat++) { // Send 3 times to ensure all tiles turn off
      for (int i = 0; i < NUM_TILE_ESPS; i++) {
        for (int port = 0; port < 4; port++) {
          sendCommandToTile(i, port, 0, 0, 0, 0);
          delay(5);
        }
      }
      delay(100);
    }
    Serial.println("✓ All tiles turned off");
  }
}