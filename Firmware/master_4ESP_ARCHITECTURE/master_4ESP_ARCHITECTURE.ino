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
#define MAX_TILES 16
#define NUM_TILE_ESPS 4

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
    tiles[i].espId = i / 4;
    tiles[i].port = i % 4;
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
  if (wsConnected && currentMillis - lastHeartbeat > 2000) {
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
  
  if (!tiles[tileIndex].isRegistered) {
    tiles[tileIndex].isRegistered = true;
    registeredTileCount++;
    Serial.printf("✓ Tile %d Registered\n", msg->globalTileId);
    
    // Flash Green ACK
    sendCommandToTile(msg->tileEspId, msg->tilePort, 1, 0, 255, 0); 
    delay(100);
    sendCommandToTile(msg->tileEspId, msg->tilePort, 0, 0, 0, 0);
  }
}

void handleToggleMessage(TileMessage *msg) {
  int tileIndex = msg->globalTileId - 1;
  if (tileIndex >= 0 && tileIndex < MAX_TILES) {
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
  String json = "{\"event\":\"tile_status\",\"data\":{\"tiles\":[";
  bool first = true;
  for (int i = 0; i < MAX_TILES; i++) {
    if (tiles[i].isRegistered) {
      if (!first) json += ",";
      json += "{\"id\":"; json += tiles[i].globalId;
      json += ",\"connected\":true,\"battery\":100}";
      first = false;
    }
  }
  json += "],\"registered_count\":";
  json += registeredTileCount;
  json += "}}";
  webSocket.sendTXT(json);
}

void handleBackendMessage(String msg) {
  if (msg.indexOf("show_pattern") >= 0) {
    // Logic for showing pattern extracted from msg...
  }
}