/**
 * Memory XXL - MASTER ESP32
 * FIXES: 
 * 1. Fixed 'onDataSent' compilation error (wifi_tx_info_t)
 * 2. Broadcast Peer Registration added
 * 3. Prints WiFi Channel for Hub configuration
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
// MUST MATCH HUB STRUCTURES EXACTLY
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
  uint8_t macAddress[6];
  bool isRegistered;
  bool isConnected;
  bool isToggledOn;
  unsigned long lastSeen;
};

// ==================== GLOBALS ====================
WebSocketsClient webSocket;
TileInfo tiles[MAX_TILES];
int registeredTileCount = 0;
int connectedEspCount = 0;
bool wsConnected = false;
unsigned long lastHeartbeat = 0;
bool espConnected[NUM_TILE_ESPS] = {false};
unsigned long espLastSeen[NUM_TILE_ESPS] = {0};

// ==================== PROTOTYPES ====================
void initWiFi();
void initESPNow();
void initWebSocket();
void onTileMessage(const esp_now_recv_info_t *info, const uint8_t *data, int len);

// *** FIXED PROTOTYPE ***
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

  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);
  
  // Initialize tile array
  for (int i = 0; i < MAX_TILES; i++) {
    tiles[i].globalId = i + 1;
    tiles[i].espId = i / 4;
    tiles[i].port = i % 4;
    tiles[i].isRegistered = false;
    tiles[i].isConnected = false;
  }
  
  initWiFi();     // Connects to iPhone and determines Channel
  initESPNow();   // Starts ESP-NOW on that Channel
  initWebSocket();
}

void loop() {
  webSocket.loop();
  unsigned long currentMillis = millis();

  // Periodic Heartbeat to Backend
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
  Serial.print("IP: "); Serial.println(WiFi.localIP());
  
  // *** CRITICAL: PRINT THE CHANNEL ***
  Serial.print("📡 CURRENT WIFI CHANNEL: ");
  Serial.println(WiFi.channel());
  Serial.println("⚠️ SET YOUR TILE HUBS TO THIS CHANNEL IN THEIR CODE! ⚠️");
}

void initESPNow() {
  if (esp_now_init() != ESP_OK) {
    Serial.println("❌ ESP-NOW Init Failed");
    ESP.restart();
  }
  
  // 1. Register Broadcast Peer (Required to talk to unregistered tiles)
  esp_now_peer_info_t peerInfo = {};
  memset(&peerInfo, 0, sizeof(peerInfo));
  for (int i = 0; i < 6; i++) {
    peerInfo.peer_addr[i] = 0xFF; // Address: FF:FF:FF:FF:FF:FF
  }
  peerInfo.channel = 0; // Use current WiFi channel
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    Serial.println("❌ Failed to add broadcast peer");
  } else {
    Serial.println("✓ Broadcast Peer Added");
  }

  // 2. Register Callbacks
  esp_now_register_recv_cb(onTileMessage);
  esp_now_register_send_cb(onDataSent);
}

// *** FIXED SEND CALLBACK ***
void onDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  // Optional: Debug print
  // if (status != ESP_NOW_SEND_SUCCESS) Serial.println("Send failed");
}

void onTileMessage(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (len != sizeof(TileMessage)) return;
  TileMessage msg;
  memcpy(&msg, data, sizeof(msg));

  // Auto-register sender as a peer if unknown
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
    
    // ACK: Flash Green then Off
    sendCommandToTile(msg->tileEspId, msg->tilePort, 1, 0, 255, 0); 
    delay(50);
    sendCommandToTile(msg->tileEspId, msg->tilePort, 0, 0, 0, 0);
  }
}

void handleToggleMessage(TileMessage *msg) {
  int tileIndex = msg->globalTileId - 1;
  if (tileIndex >= 0 && tileIndex < MAX_TILES) {
    tiles[tileIndex].isToggledOn = (msg->value == 1);
    Serial.printf("Tile %d Toggled: %d\n", msg->globalTileId, msg->value);
    
    if (wsConnected) {
       char buffer[128];
       sprintf(buffer, "{\"event\":\"player_step\",\"data\":{\"tile_id\":%d,\"is_on\":%s}}", 
               msg->globalTileId, tiles[tileIndex].isToggledOn ? "true" : "false");
       webSocket.sendTXT(buffer);
    }
  }
}

void handleHeartbeatMessage(TileMessage *msg) {
  // Update tile connection status based on heartbeat
  int tileIndex = msg->globalTileId - 1;
  if (tileIndex >= 0 && tileIndex < MAX_TILES) {
    tiles[tileIndex].isConnected = (msg->value == 1);  // value=1 means registered
    tiles[tileIndex].lastSeen = millis();
    
    // Update ESP connection tracking
    espConnected[msg->tileEspId] = true;
    espLastSeen[msg->tileEspId] = millis();
  }
}

void sendCommandToTile(uint8_t espId, uint8_t port, uint8_t commandType, uint8_t r, uint8_t g, uint8_t b) {
  MasterCommand cmd;
  cmd.commandType = commandType;
  cmd.targetEspId = espId;
  cmd.targetPort = port;
  cmd.color[0] = r; cmd.color[1] = g; cmd.color[2] = b;
  
  // SEND TO BROADCAST ADDRESS
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
      Serial.println("✓ WS Connected");
      wsConnected = true;
      
      // Send master identification message
      {
        String macStr = WiFi.macAddress();
        macStr.replace(":", "");
        String json = "{\"event\":\"master_connected\",\"data\":{\"master_id\":\"";
        json += macStr;
        json += "\"}}";
        webSocket.sendTXT(json);
      }
      
      // Send initial tile status
      sendTileStatusToBackend();
      break;
    case WStype_DISCONNECTED:
      wsConnected = false;
      break;
    case WStype_TEXT:
      handleBackendMessage(String((char*)payload));
      break;
  }
}

void sendTileStatusToBackend() {
  if (!wsConnected) return;
  
  // Build JSON with all tile information
  String json = "{\"event\":\"tile_status\",\"data\":{\"tiles\":[";
  
  bool first = true;
  for (int i = 0; i < MAX_TILES; i++) {
    if (tiles[i].isRegistered) {
      if (!first) json += ",";
      json += "{\"id\":";
      json += tiles[i].globalId;
      json += ",\"connected\":";
      json += tiles[i].isConnected ? "true" : "false";
      json += ",\"battery\":100}";  // Default battery level
      first = false;
    }
  }
  
  json += "],\"registered_count\":";
  json += registeredTileCount;
  json += "}}";
  
  webSocket.sendTXT(json);
}

void handleBackendMessage(String msg) {
  // Parse JSON command from backend
  int eventStart = msg.indexOf("\"event\":\"") + 9;
  int eventEnd = msg.indexOf("\"", eventStart);
  String event = msg.substring(eventStart, eventEnd);
  
  Serial.print("Backend command: ");
  Serial.println(event);
  
  if (event == "show_pattern") {
    // Extract pattern array
    int patternStart = msg.indexOf("[", msg.indexOf("\"pattern\""));
    int patternEnd = msg.indexOf("]", patternStart);
    String patternStr = msg.substring(patternStart + 1, patternEnd);
    
    // Parse tile IDs
    int tileIds[16];
    int count = 0;
    int pos = 0;
    while (pos < patternStr.length() && count < 16) {
      int commaPos = patternStr.indexOf(",", pos);
      if (commaPos == -1) commaPos = patternStr.length();
      String numStr = patternStr.substring(pos, commaPos);
      numStr.trim();
      if (numStr.length() > 0) {
        tileIds[count++] = numStr.toInt();
      }
      pos = commaPos + 1;
    }
    
    Serial.printf("Showing pattern with %d tiles\n", count);
    
    // Show pattern
    for (int i = 0; i < count; i++) {
      int tileId = tileIds[i];
      int tileIndex = tileId - 1;
      if (tileIndex >= 0 && tileIndex < MAX_TILES) {
        sendCommandToTile(tiles[tileIndex].espId, tiles[tileIndex].port, 1, 0, 255, 0);
        delay(800);
        sendCommandToTile(tiles[tileIndex].espId, tiles[tileIndex].port, 0, 0, 0, 0);
        delay(200);
      }
    }
    
    String response = "{\"event\":\"pattern_shown\",\"data\":{}}";
    webSocket.sendTXT(response);
    
  } else if (event == "end_game") {
    Serial.println("Ending game");
    for (int i = 0; i < MAX_TILES; i++) {
      if (tiles[i].isRegistered) {
        sendCommandToTile(tiles[i].espId, tiles[i].port, 0, 0, 0, 0);
      }
    }
  }
}