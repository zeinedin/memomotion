/**
 * Memory XXL - MASTER ESP32 (Game State Aware Version)
 * * Updates:
 * 1. Tracks game state (gameActive)
 * 2. Button press broadcasts "OFF" only if game is active
 * 3. Optimized "Turn All Off" to use 0xFF broadcast address
 */

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>

// ==================== CONFIGURATION ====================
const char* WIFI_SSID = "iPhone";
const char* WIFI_PASSWORD = "eveneven";
const char* WS_HOST = "memo-motion.azurewebsites.net";
const uint16_t WS_PORT = 443;
const bool USE_SSL = true;      // Set false for local HTTP

// Hardware pins
#define START_BUTTON_PIN 13
#define STATUS_LED_PIN 2

// System config
#define MAX_TILES 12
#define NUM_TILE_HUBS 3
#define TILES_PER_HUB 4
#define HEARTBEAT_TIMEOUT_MS 10000
#define STATUS_INTERVAL_MS 3000
#define BUTTON_DEBOUNCE_MS 300
#define WS_RECONNECT_INTERVAL_MS 5000
#define ESPNOW_RETRY_COUNT 3
#define ESPNOW_RETRY_DELAY_MS 10

// Broadcast address
uint8_t broadcastAddr[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// ==================== DATA STRUCTURES ====================
// Message from Tile Hub -> Master
typedef struct __attribute__((packed)) {
    uint8_t msgType;      // 0=register, 1=toggle, 2=heartbeat
    uint8_t hubId;        // Hub ID (0-2)
    uint8_t port;         // Port on hub (0-3)
    uint8_t value;        // Toggle state or status
    uint8_t globalTileId; // Computed: hubId * 4 + port + 1
} TileMessage;

// Command from Master -> Tile Hub
typedef struct __attribute__((packed)) {
    uint8_t cmdType;      // 0=off, 1=on, 2=blink, 3=ack
    uint8_t targetHub;    // 0xFF = all hubs
    uint8_t targetPort;   // 0xFF = all ports on hub
    uint8_t colorR;
    uint8_t colorG;
    uint8_t colorB;
    uint8_t duration;     // For blink/timed operations
} MasterCommand;

// Tile state tracking
struct TileState {
    uint8_t hubId;
    uint8_t port;
    bool registered;
    bool isOn;
    unsigned long lastSeen;
};

// Hub state tracking
struct HubState {
    bool connected;
    unsigned long lastSeen;
    uint8_t mac[6];
};

// ==================== GLOBAL STATE ====================
WebSocketsClient webSocket;

TileState tiles[MAX_TILES];
HubState hubs[NUM_TILE_HUBS];

int registeredCount = 0;
bool wsConnected = false;
bool buttonLastState = HIGH;
unsigned long lastButtonPress = 0;
unsigned long lastStatusSend = 0;
unsigned long lastWsReconnect = 0;

// NEW: Game State Tracking
bool gameActive = false; 

// ==================== FUNCTION DECLARATIONS ====================
void initWiFi();
void initESPNow();
void initWebSocket();
void onESPNowRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len);
void onESPNowSend(const uint8_t *mac, esp_now_send_status_t status);
void handleTileMessage(const TileMessage& msg, const uint8_t* mac);
void sendCommand(uint8_t hub, uint8_t port, uint8_t cmd, uint8_t r, uint8_t g, uint8_t b);
void sendCommandWithRetry(uint8_t hub, uint8_t port, uint8_t cmd, uint8_t r, uint8_t g, uint8_t b);
void turnAllTilesOff();
void sendTileStatus();
void checkTimeouts();
void handleButton();
void handleWebSocket(WStype_t type, uint8_t* payload, size_t length);
void handleBackendMessage(const char* json);
void wsSendJson(const char* event, const char* dataJson);

// ==================== SETUP ====================
void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("\n========================================");
    Serial.println("Memory XXL - Master ESP32 (State Aware)");
    Serial.println("========================================");
    
    // Initialize pins
    pinMode(START_BUTTON_PIN, INPUT_PULLUP);
    pinMode(STATUS_LED_PIN, OUTPUT);
    digitalWrite(STATUS_LED_PIN, LOW);
    
    // Initialize tile array
    for (int i = 0; i < MAX_TILES; i++) {
        tiles[i].hubId = i / TILES_PER_HUB;
        tiles[i].port = i % TILES_PER_HUB;
        tiles[i].registered = false;
        tiles[i].isOn = false;
        tiles[i].lastSeen = 0;
    }
    
    // Initialize hub array
    for (int i = 0; i < NUM_TILE_HUBS; i++) {
        hubs[i].connected = false;
        hubs[i].lastSeen = 0;
        memset(hubs[i].mac, 0, 6);
    }
    
    initWiFi();
    initESPNow();
    initWebSocket();
    
    Serial.println("✓ Master ready");
}

// ==================== MAIN LOOP ====================
void loop() {
    webSocket.loop();
    
    unsigned long now = millis();
    
    // Handle button press
    handleButton();
    
    // Periodic status broadcast (every 3 seconds)
    if (wsConnected && (now - lastStatusSend >= STATUS_INTERVAL_MS)) {
        sendTileStatus();
        lastStatusSend = now;
    }
    
    // Check for hub/tile timeouts
    checkTimeouts();
    
    // WebSocket reconnect
    if (!wsConnected && (now - lastWsReconnect >= WS_RECONNECT_INTERVAL_MS)) {
        Serial.println("🔄 WebSocket reconnecting...");
        initWebSocket();
        lastWsReconnect = now;
    }
    
    // Status LED
    digitalWrite(STATUS_LED_PIN, wsConnected ? HIGH : (millis() / 500) % 2);
}

// ==================== WIFI ====================
void initWiFi() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    
    Serial.print("Connecting to WiFi");
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n✓ WiFi connected");
        Serial.printf("  IP: %s\n", WiFi.localIP().toString().c_str());
        Serial.printf("  Channel: %d\n", WiFi.channel());
    } else {
        Serial.println("\n✗ WiFi failed - restarting...");
        ESP.restart();
    }
}

// ==================== ESP-NOW ====================
void initESPNow() {
    if (esp_now_init() != ESP_OK) {
        Serial.println("✗ ESP-NOW init failed");
        ESP.restart();
    }
    
    // Add broadcast peer
    esp_now_peer_info_t peer = {};
    memcpy(peer.peer_addr, broadcastAddr, 6);
    peer.channel = 0;
    peer.encrypt = false;
    
    if (!esp_now_is_peer_exist(broadcastAddr)) {
        esp_now_add_peer(&peer);
    }
    
    esp_now_register_recv_cb(onESPNowRecv);
    
    Serial.println("✓ ESP-NOW initialized");
}

void onESPNowRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
    if (len != sizeof(TileMessage)) return;
    
    TileMessage msg;
    memcpy(&msg, data, sizeof(msg));
    
    // Add sender as peer if not exists
    if (!esp_now_is_peer_exist(info->src_addr)) {
        esp_now_peer_info_t peer = {};
        memcpy(peer.peer_addr, info->src_addr, 6);
        peer.channel = 0;
        peer.encrypt = false;
        esp_now_add_peer(&peer);
    }
    
    handleTileMessage(msg, info->src_addr);
}

void handleTileMessage(const TileMessage& msg, const uint8_t* mac) {
    // Validate hub ID
    if (msg.hubId >= NUM_TILE_HUBS) return;
    
    // Update hub state
    hubs[msg.hubId].connected = true;
    hubs[msg.hubId].lastSeen = millis();
    memcpy(hubs[msg.hubId].mac, mac, 6);
    
    // Calculate tile index
    int tileIdx = msg.hubId * TILES_PER_HUB + msg.port;
    if (tileIdx >= MAX_TILES) return;
    
    switch (msg.msgType) {
        case 0: // Registration
            if (!tiles[tileIdx].registered) {
                tiles[tileIdx].registered = true;
                tiles[tileIdx].lastSeen = millis();
                registeredCount++;
                
                Serial.printf("✓ Tile %d registered (Hub %d, Port %d)\n", 
                             msg.globalTileId, msg.hubId + 1, msg.port);
                
                // Send green flash acknowledgment
                sendCommandWithRetry(msg.hubId, msg.port, 1, 0, 255, 0);
                delay(100);
                sendCommandWithRetry(msg.hubId, msg.port, 0, 0, 0, 0);
                
                // Send status update immediately
                sendTileStatus();
            }
            break;
            
        case 1: // Toggle (player step)
            tiles[tileIdx].lastSeen = millis();
            tiles[tileIdx].isOn = (msg.value == 1);
            
            // Auto-register if needed
            if (!tiles[tileIdx].registered) {
                tiles[tileIdx].registered = true;
                registeredCount++;
                Serial.printf("✓ Tile %d auto-registered\n", msg.globalTileId);
            }
            
            Serial.printf("🎯 Tile %d %s\n", msg.globalTileId, 
                          tiles[tileIdx].isOn ? "ON" : "OFF");
            
            // Forward to backend
            if (wsConnected) {
                char json[128];
                snprintf(json, sizeof(json), 
                        "{\"tile_id\":%d,\"is_on\":%s}",
                        msg.globalTileId, 
                        tiles[tileIdx].isOn ? "true" : "false");
                wsSendJson("player_step", json);
            }
            break;
            
        case 2: // Heartbeat
            tiles[tileIdx].lastSeen = millis();
            break;
    }
}

// ==================== COMMANDS ====================
void sendCommand(uint8_t hub, uint8_t port, uint8_t cmd, uint8_t r, uint8_t g, uint8_t b) {
    MasterCommand command = {cmd, hub, port, r, g, b, 0};
    esp_now_send(broadcastAddr, (uint8_t*)&command, sizeof(command));
}

void sendCommandWithRetry(uint8_t hub, uint8_t port, uint8_t cmd, uint8_t r, uint8_t g, uint8_t b) {
    MasterCommand command = {cmd, hub, port, r, g, b, 0};
    
    for (int i = 0; i < ESPNOW_RETRY_COUNT; i++) {
        esp_now_send(broadcastAddr, (uint8_t*)&command, sizeof(command));
        delay(ESPNOW_RETRY_DELAY_MS);
    }
}

void turnAllTilesOff() {
    Serial.println("💡 Broadcasting GLOBAL OFF");
    // Send multiple times with delays for reliability
    for (int retry = 0; retry < 3; retry++) {
        // Hub=0xFF (All), Port=0xFF (All), Cmd=0 (Off)
        sendCommandWithRetry(0xFF, 0xFF, 0, 0, 0, 0);
        delay(20);
    }
}

// ==================== STATUS ====================
void sendTileStatus() {
    if (!wsConnected) return;
    
    // Build tiles array
    StaticJsonDocument<1024> doc;
    JsonArray tilesArr = doc.createNestedArray("tiles");
    
    for (int i = 0; i < MAX_TILES; i++) {
        if (tiles[i].registered) {
            JsonObject t = tilesArr.createNestedObject();
            t["id"] = i + 1;
            t["connected"] = true;
            t["battery"] = 100;
        }
    }
    
    doc["registered_count"] = registeredCount;
    doc["game_active"] = gameActive;
    
    // Serialize and send
    char buffer[1024];
    serializeJson(doc, buffer, sizeof(buffer));
    wsSendJson("tile_status", buffer);
}

void checkTimeouts() {
    unsigned long now = millis();
    
    // Check hub timeouts
    for (int h = 0; h < NUM_TILE_HUBS; h++) {
        if (hubs[h].connected && (now - hubs[h].lastSeen > HEARTBEAT_TIMEOUT_MS)) {
            Serial.printf("⚠️ Hub %d timeout\n", h + 1);
            hubs[h].connected = false;
            
            // Mark all tiles on this hub as unregistered
            for (int p = 0; p < TILES_PER_HUB; p++) {
                int idx = h * TILES_PER_HUB + p;
                if (tiles[idx].registered) {
                    tiles[idx].registered = false;
                    registeredCount--;
                }
            }
        }
    }
}

// ==================== BUTTON (UPDATED) ====================
void handleButton() {
    bool buttonState = digitalRead(START_BUTTON_PIN);
    
    if (buttonState == LOW && buttonLastState == HIGH) {
        unsigned long now = millis();
        if (now - lastButtonPress > BUTTON_DEBOUNCE_MS) {
            Serial.println("🔘 START button pressed");
            
            // 1. ALWAYS NOTIFY BACKEND FIRST
            // Let backend handle game logic and send clear command back
            if (wsConnected) {
                wsSendJson("start_button_pressed", "{}");
            } else {
                Serial.println("⚠️ WebSocket not connected");
            }
            
            // 2. IMMEDIATE LOCAL CLEAR if game is active
            // This provides instant feedback while backend processes
            if (gameActive) {
                Serial.println("📡 Game Active: Clearing Tiles...");
                turnAllTilesOff();
            } else {
                Serial.println("ℹ️ Game Idle: Skipping LED clear");
            }
            
            lastButtonPress = now;
        }
    }
    
    buttonLastState = buttonState;
}

// ==================== WEBSOCKET ====================
void initWebSocket() {
    if (USE_SSL) {
        webSocket.beginSSL(WS_HOST, WS_PORT, "/ws/master");
    } else {
        webSocket.begin(WS_HOST, WS_PORT, "/ws/master");
    }
    
    webSocket.onEvent(handleWebSocket);
    webSocket.setReconnectInterval(WS_RECONNECT_INTERVAL_MS);
}

void handleWebSocket(WStype_t type, uint8_t* payload, size_t length) {
    switch (type) {
        case WStype_CONNECTED:
            Serial.println("✓ WebSocket connected");
            wsConnected = true;
            digitalWrite(STATUS_LED_PIN, HIGH);
            
            // Send identification
            {
                char json[128];
                snprintf(json, sizeof(json), "{\"master_id\":\"ESP32-%s\"}", 
                         WiFi.macAddress().c_str());
                wsSendJson("master_connected", json);
            }
            
            // Send initial status
            sendTileStatus();
            break;
            
        case WStype_DISCONNECTED:
            Serial.println("✗ WebSocket disconnected");
            wsConnected = false;
            digitalWrite(STATUS_LED_PIN, LOW);
            break;
            
        case WStype_TEXT:
            handleBackendMessage((char*)payload);
            break;
            
        case WStype_PING:
        case WStype_PONG:
            break;
            
        default:
            break;
    }
}

// ==================== BACKEND HANDLER (UPDATED) ====================
void handleBackendMessage(const char* json) {
    StaticJsonDocument<512> doc;
    DeserializationError err = deserializeJson(doc, json);
    
    if (err) {
        Serial.printf("⚠️ JSON parse error: %s\n", err.c_str());
        return;
    }
    
    const char* event = doc["event"];
    if (!event) return;
    
    Serial.printf("📥 Backend: %s\n", event);
    
    // --- GAME STATE LOGIC ---
    if (strcmp(event, "show_pattern") == 0) {
        gameActive = true; 
        turnAllTilesOff();
    }
    else if (strcmp(event, "game_over") == 0 || strcmp(event, "reset") == 0) {
        gameActive = false;
        turnAllTilesOff();
    }
    else if (strcmp(event, "pattern_correct") == 0) {
        // Flash all registered tiles green
        for (int i = 0; i < MAX_TILES; i++) {
            if (tiles[i].registered) {
                sendCommand(tiles[i].hubId, tiles[i].port, 1, 0, 255, 0);
            }
        }
        delay(500);
        turnAllTilesOff();
        
        // Note: We keep gameActive = true because the next round follows automatically
    }
    else if (strcmp(event, "hide_pattern") == 0 || 
             strcmp(event, "clear_tiles") == 0) {
        turnAllTilesOff();
    }
    else if (strcmp(event, "ping") == 0) {
        wsSendJson("pong", "{}");
    }
}

void wsSendJson(const char* event, const char* dataJson) {
    if (!wsConnected) return;
    
    char buffer[1024];
    snprintf(buffer, sizeof(buffer), "{\"event\":\"%s\",\"data\":%s}", event, dataJson);
    webSocket.sendTXT(buffer);
}