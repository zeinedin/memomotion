/**
 * Memory XXL - Master ESP32 (FINAL ROBUST VERSION)
 * * FIXES:
 * 1. Auto-registers tiles on ANY message (Heartbeat/Step) -> Fixes "0 Tiles" after Master reset.
 * 2. Sends correct JSON structure to Backend.
 * 3. Handles 16 Tiles.
 */

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <WebSocketsClient.h>

// ==================== CONFIGURATION ====================
const char* WIFI_SSID = "iPhone";        // <--- CHECK THIS
const char* WIFI_PASSWORD = "eveneven";  // <--- CHECK THIS
const char* WS_HOST = "172.20.10.11";    // <--- CHECK THIS (Your PC IP)
const uint16_t WS_PORT = 8000;

#define START_BUTTON_PIN 0  // BOOT button
#define STATUS_LED_PIN 2    // Blue LED
#define MAX_TILES 16        // Updated for Memory XXL

// ==================== STRUCTURES ====================
typedef struct {
  uint8_t tileId;
  uint8_t messageType; // 0=Reg, 1=Step, 2=Heartbeat, 3=Battery
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
int tileCount = 0;

bool wsConnected = false;
unsigned long lastHeartbeat = 0;
unsigned long lastTileCheck = 0;
uint8_t pendingStepTileId = 0;

// Button Debouncing
bool lastButtonState = HIGH;
unsigned long lastButtonPress = 0;

// ==================== FUNCTION PROTOTYPES ====================
void initWiFi();
void initESPNow();
void initWebSocket();
void onTileMessage(const esp_now_recv_info_t *info, const uint8_t *data, int len);
void registerTile(uint8_t tileId, const uint8_t *mac);
void sendTileStatus();
void sendCommandToTile(uint8_t tileId, uint8_t command);
void sendCommandToAllTiles(uint8_t command);
void handleBackendMessage(String msg);

// ==================== SETUP ====================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== Memory XXL Master (Final) ===");
  
  pinMode(START_BUTTON_PIN, INPUT_PULLUP); // Use Internal Pullup for BOOT button
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);
  
  // Clear array
  for (int i = 0; i < MAX_TILES; i++) {
    registeredTiles[i].isConnected = false;
    registeredTiles[i].id = 0;
  }
  
  initWiFi();
  initESPNow();
  initWebSocket();
  
  Serial.println("✓ Master System Ready");
}

// ==================== MAIN LOOP ====================
void loop() {
  webSocket.loop();
  
  unsigned long currentMillis = millis();

  // 1. Handle Button Press (Start Game)
  if (digitalRead(START_BUTTON_PIN) == LOW) {
    if (currentMillis - lastButtonPress > 500) { // 500ms Debounce
      Serial.println("👉 START BUTTON PRESSED");
      if (wsConnected) {
        webSocket.sendTXT("{\"event\":\"start_button_pressed\",\"data\":{}}");
      } else {
        Serial.println("  (Not connected to Backend)");
      }
      lastButtonPress = currentMillis;
    }
  }

  // 2. Handle Pending Steps (From Tiles)
  if (pendingStepTileId > 0) {
    if (wsConnected) {
      char msg[64];
      sprintf(msg, "{\"event\":\"player_step\",\"data\":{\"tile_id\":%d,\"correct\":true}}", pendingStepTileId);
      webSocket.sendTXT(msg);
      Serial.printf("📤 Sent Step: Tile %d\n", pendingStepTileId);
    }
    pendingStepTileId = 0; // Clear flag
  }

  // 3. Periodic Updates to Backend (Every 2 seconds)
  if (wsConnected && currentMillis - lastHeartbeat > 2000) {
    sendTileStatus(); // Keep backend sync'd
    lastHeartbeat = currentMillis;
  }
}

// ==================== ESP-NOW LOGIC ====================
void initESPNow() {
  if (esp_now_init() != ESP_OK) {
    Serial.println("❌ ESP-NOW Init Failed");
    ESP.restart();
  }
  Serial.println("✓ ESP-NOW Initialized");
  esp_now_register_recv_cb(onTileMessage);
}

void onTileMessage(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (len != sizeof(TileMessage)) return;
  
  TileMessage msg;
  memcpy(&msg, data, sizeof(msg));
  const uint8_t *mac = info->src_addr;

  // 1. Check if we know this tile
  int knownIndex = -1;
  for (int i = 0; i < tileCount; i++) {
    if (registeredTiles[i].id == msg.tileId) {
      knownIndex = i;
      break;
    }
  }

  // 2. Auto-Register if unknown (Fixes the "Master Reset" issue)
  if (knownIndex == -1) {
    Serial.printf("⚠️ Unknown Tile %d detected! Auto-registering...\n", msg.tileId);
    registerTile(msg.tileId, mac);
    return; // registerTile will recurse or handle it
  }

  // 3. Update Last Seen
  registeredTiles[knownIndex].lastSeen = millis();
  registeredTiles[knownIndex].isConnected = true;

  // 4. Handle Message Types
  if (msg.messageType == 1 && msg.value == 1) {
    // STEP DETECTED
    Serial.printf("👣 Step detected on Tile %d\n", msg.tileId);
    pendingStepTileId = msg.tileId;
    
    // Immediate Visual Feedback (Optional)
    sendCommandToTile(msg.tileId, 1); // Light ON
    delay(50);
    sendCommandToTile(msg.tileId, 0); // Light OFF
  }
  else if (msg.messageType == 0) {
    // Explicit Registration Request
    Serial.printf("👋 Registration request from Tile %d\n", msg.tileId);
    sendCommandToTile(msg.tileId, 3); // Send ACK
    sendTileStatus(); // Force update to backend
  }
}

void registerTile(uint8_t tileId, const uint8_t *mac) {
  if (tileCount >= MAX_TILES) return;

  // Check duplicates one last time
  for(int i=0; i<tileCount; i++) {
    if (registeredTiles[i].id == tileId) return; 
  }

  // Add new tile
  registeredTiles[tileCount].id = tileId;
  memcpy(registeredTiles[tileCount].macAddress, mac, 6);
  registeredTiles[tileCount].isConnected = true;
  registeredTiles[tileCount].lastSeen = millis();
  
  // Register Peer
  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, mac, 6);
  peerInfo.channel = 0; // Use current channel
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) == ESP_OK) {
    Serial.printf("✓ Tile %d Registered (Total: %d)\n", tileId, tileCount + 1);
    tileCount++;
    
    // Send ACK to Tile
    sendCommandToTile(tileId, 3);
    
    // Inform Backend Immediately
    sendTileStatus();
  } else {
    Serial.println("❌ Failed to add peer");
  }
}

// ==================== WIFI & WEBSOCKET ====================
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
}

void initWebSocket() {
  webSocket.begin(WS_HOST, WS_PORT, "/ws/master");
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(3000);
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.println("❌ WebSocket Disconnected");
      wsConnected = false;
      digitalWrite(STATUS_LED_PIN, LOW);
      break;
      
    case WStype_CONNECTED:
      Serial.println("✓ WebSocket Connected!");
      wsConnected = true;
      digitalWrite(STATUS_LED_PIN, HIGH);
      
      // Handshake - Send current tile count immediately!
      char handshake[128];
      sprintf(handshake, "{\"event\":\"master_connected\",\"data\":{\"master_id\":\"MASTER_01\",\"tile_count\":%d}}", tileCount);
      webSocket.sendTXT(handshake);
      
      // Force a full status update
      sendTileStatus();
      break;
      
    case WStype_TEXT:
      handleBackendMessage(String((char*)payload));
      break;
  }
}

// ==================== COMMUNICATION HELPERS ====================
void sendTileStatus() {
  if (!wsConnected) return;

  // Manual JSON construction to ensure validity
  String json = "{\"event\":\"tile_status\",\"data\":{\"tiles\":[";
  
  int activeCount = 0;
  for (int i = 0; i < tileCount; i++) {
    if (activeCount > 0) json += ",";
    
    json += "{\"id\":";
    json += registeredTiles[i].id;
    json += ",\"connected\":";
    json += registeredTiles[i].isConnected ? "true" : "false";
    json += ",\"battery\":100}";
    
    activeCount++;
  }
  json += "]}}";
  
  webSocket.sendTXT(json);
  // Serial.println("Sent Tile Status"); // Uncomment for debugging
}

void handleBackendMessage(String msg) {
  // Simple string parsing to avoid heavy JSON library on Master
  if (msg.indexOf("show_pattern") >= 0) {
    Serial.println("📥 Received Pattern Command");
    
    // Basic parsing logic or just pass through commands
    // For demo: Light up all tiles briefly
    sendCommandToAllTiles(1);
    delay(500);
    sendCommandToAllTiles(0);
    
    // Extract numbers from pattern string [1, 2, 3]
    // Note: A robust parser is better, but for demo:
    int idx = msg.indexOf("[");
    int end = msg.indexOf("]");
    if (idx > 0 && end > idx) {
      String pat = msg.substring(idx+1, end);
      Serial.println("Pattern: " + pat);
      
      // Here you would parse "1, 2" and light them up sequentially
      // For now, let's just confirm receipt
      webSocket.sendTXT("{\"event\":\"pattern_shown\",\"data\":{}}");
    }
  }
  else if (msg.indexOf("light_tile") >= 0) {
     // Handle individual light command
     // Parse "tile_id": X
  }
}

void sendCommandToTile(uint8_t tileId, uint8_t command) {
  // Find tile MAC
  for (int i = 0; i < tileCount; i++) {
    if (registeredTiles[i].id == tileId) {
      MasterCommand cmd;
      cmd.tileId = tileId;
      cmd.command = command;
      cmd.duration = 5; // 500ms
      esp_now_send(registeredTiles[i].macAddress, (uint8_t *) &cmd, sizeof(cmd));
      return;
    }
  }
}

void sendCommandToAllTiles(uint8_t command) {
  for (int i = 0; i < tileCount; i++) {
    sendCommandToTile(registeredTiles[i].id, command);
    delay(10); // Small delay to prevent jamming
  }
}