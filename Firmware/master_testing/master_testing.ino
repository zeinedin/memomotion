/**
 * Memory XXL - MASTER Device
 * FIXED VERSION: Heartbeat added + Non-blocking logic
 */

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>

// ==================== CONFIGURATION ====================
const char* WIFI_SSID = "iPhone";
const char* WIFI_PASSWORD = "eveneven";

// !!! CHECK YOUR IPCONFIG !!!
const char* WS_HOST = "172.20.10.9"; 
const uint16_t WS_PORT = 8000;

// Hardware Config
#define START_BUTTON_PIN 0 // Pin 15 to Button to GND
#define STATUS_LED_PIN 2     // Onboard Blue LED
#define MAX_TILES 16

// ==================== GLOBALS ====================
WebSocketsClient webSocket;
bool wsConnected = false;
int lastButtonState = HIGH;
unsigned long lastDebounceTime = 0;
unsigned long lastTileStatusTime = 0;  // Throttle tile_status updates
uint8_t tileCount = 0;

// Data Structures
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
  unsigned long lastSeen;
};
TileInfo registeredTiles[MAX_TILES];

// ==================== SETUP ====================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== MASTER STARTING ===");

  // 1. Setup Pins
  pinMode(START_BUTTON_PIN, INPUT_PULLUP);
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);

  // 2. Setup WiFi (Force Channel 6 for stability)
  WiFi.mode(WIFI_STA);
  // This turns off auto-channel to prevent disconnects
  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(6, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false);
  
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✓ WiFi Connected!");
  Serial.print("  IP: "); Serial.println(WiFi.localIP());
  Serial.print("  Channel: "); Serial.println(WiFi.channel());
  Serial.print("  MAC: "); Serial.println(WiFi.macAddress());

  // 3. Setup WebSocket
  initWebSocket();

  // 4. Setup ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("✗ ESP-NOW Init Failed");
    ESP.restart();
  }
  esp_now_register_recv_cb(onTileMessage);
  Serial.println("✓ ESP-NOW Initialized");
  
  digitalWrite(STATUS_LED_PIN, HIGH);
  Serial.println("✓ MASTER READY");
}

// ==================== LOOP ====================
void loop() {
webSocket.loop(); // Keep the connection alive

  // --- FIXED BUTTON LOGIC ---
  int reading = digitalRead(START_BUTTON_PIN);

  // 1. Check for the click (Transition from HIGH to LOW)
  if (lastButtonState == HIGH && reading == LOW) {
    
    // 2. Check if enough time has passed since the last click (200ms debounce)
    if (millis() - lastDebounceTime > 200) {
       Serial.println("→ START BUTTON PRESSED");
       
       if (wsConnected) {
         StaticJsonDocument<200> doc;
         doc["master_id"] = WiFi.macAddress();
         doc["tile_count"] = tileCount;
         sendToBackend("start_button_pressed", doc);
       } else {
         Serial.println("✗ Ignored: WebSocket disconnected");
       }
       
       lastDebounceTime = millis(); // Reset the timer
    }
  }

  // 3. Save the state for the next loop
  lastButtonState = reading;
  // -------------------------
}

// ==================== WEBSOCKET ====================
void initWebSocket() {
  webSocket.begin(WS_HOST, WS_PORT, "/ws/master");
  webSocket.onEvent(wsEvent);
  
  // !!! CRITICAL FIXES !!!
  webSocket.setReconnectInterval(5000);
  webSocket.enableHeartbeat(15000, 3000, 2); // Ping every 15s to stay alive
}

void wsEvent(WStype_t type, uint8_t *payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.println("✗ WebSocket disconnected");
      wsConnected = false;
      digitalWrite(STATUS_LED_PIN, LOW);
      break;
    case WStype_CONNECTED:
      Serial.println("✓ WebSocket CONNECTED!");
      wsConnected = true;
      digitalWrite(STATUS_LED_PIN, HIGH);
      // Register with backend immediately
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
  StaticJsonDocument<1024> doc;
  deserializeJson(doc, msg);
  String event = doc["event"];

  if (event == "show_pattern") {
    JsonArray pattern = doc["data"]["pattern"];
    Serial.println("→ Showing Pattern...");
    
    sendCommandToAllTiles(0); // All Off
    delay(500); 

    for (int i = 0; i < pattern.size(); i++) {
      uint8_t tileId = pattern[i];
      
      // NON-BLOCKING WAITS
      sendCommandToTile(tileId, 1); // ON
      unsigned long start = millis();
      while(millis() - start < 800) { webSocket.loop(); } // Keep WS alive
      
      sendCommandToTile(tileId, 0); // OFF
      start = millis();
      while(millis() - start < 400) { webSocket.loop(); } // Keep WS alive
    }
    
    StaticJsonDocument<100> resp;
    resp["status"] = "complete";
    sendToBackend("pattern_shown", resp);
  }
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

// ==================== ESP-NOW LOGIC ====================
void onTileMessage(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (len != sizeof(TileMessage)) return;
  TileMessage msg;
  memcpy(&msg, data, sizeof(msg));

  if (msg.messageType == 0) { // Register
    registerTile(msg.tileId, info->src_addr);
  } else if (msg.messageType == 1) { // Step/Toggle - send both ON and OFF states
     bool isOn = (msg.value == 1);
     Serial.printf("Tile %d Toggled: %s\n", msg.tileId, isOn ? "ON" : "OFF");
     if (wsConnected) {
       StaticJsonDocument<200> doc;
       doc["tile_id"] = msg.tileId;
       doc["is_on"] = isOn;  // Include LED state from tile
       sendToBackend("player_step", doc);
     }
  }
}

void registerTile(uint8_t tileId, const uint8_t *mac) {
  // Check duplicates
  for(int i=0; i<tileCount; i++) {
    if(registeredTiles[i].id == tileId) {
      // Already registered, just ACK (no tile_status spam)
      sendCommandToTile(tileId, 3);
      return;
    }
  }
  
  // New Tile
  registeredTiles[tileCount].id = tileId;
  memcpy(registeredTiles[tileCount].macAddress, mac, 6);
  registeredTiles[tileCount].isConnected = true;
  
  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, mac, 6);
  peerInfo.channel = 6; // Force Channel 6
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) == ESP_OK) {
    tileCount++;
    Serial.printf("✓ Tile %d Registered\n", tileId);
    sendCommandToTile(tileId, 3); // Send ACK
    
    // Throttle tile_status updates (max once per 5 seconds)
    if(wsConnected && (millis() - lastTileStatusTime > 5000)) {
       lastTileStatusTime = millis();
       StaticJsonDocument<1024> doc;
       doc["master_id"] = WiFi.macAddress();
       JsonArray tiles = doc.createNestedArray("tiles");
       for(int i=0; i<tileCount; i++) {
         JsonObject t = tiles.createNestedObject();
         t["id"] = registeredTiles[i].id;
         t["connected"] = true;
       }
       sendToBackend("tile_status", doc);
    }
  }
}

void sendCommandToTile(uint8_t tileId, uint8_t command) {
  for (int i = 0; i < tileCount; i++) {
    if (registeredTiles[i].id == tileId) {
      MasterCommand cmd;
      cmd.tileId = tileId;
      cmd.command = command;
      esp_now_send(registeredTiles[i].macAddress, (uint8_t *)&cmd, sizeof(cmd));
    }
  }
}

void sendCommandToAllTiles(uint8_t command) {
  for (int i = 0; i < tileCount; i++) {
    sendCommandToTile(registeredTiles[i].id, command);
  }
}