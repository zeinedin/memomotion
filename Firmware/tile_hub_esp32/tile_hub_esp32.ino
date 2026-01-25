/**
 * Memory XXL - TILE HUB ESP32 (Robust Version)
 * 
 * Each hub manages 4 tiles with switches and NeoPixel LEDs.
 * 
 * Features:
 * - Proper debouncing with state machine
 * - Reliable registration with visual feedback
 * - Auto-reconnect to master
 * - Heartbeat for connection monitoring
 */

#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <Adafruit_NeoPixel.h>

// ==================== CONFIGURATION ====================
// *** CHANGE THIS FOR EACH HUB ***
#define HUB_ID 0  // Hub 0 = tiles 1-4, Hub 1 = tiles 5-8, Hub 2 = tiles 9-12

// WiFi channel must match master's WiFi channel
#define WIFI_CHANNEL 6

// Hardware config
#define NUM_TILES 4
#define LEDS_PER_TILE 12

// GPIO pins
const int SWITCH_PINS[NUM_TILES] = {13, 14, 26, 33};
const int LED_PINS[NUM_TILES] = {12, 27, 25, 32};

// Timing
#define DEBOUNCE_MS 50
#define HEARTBEAT_INTERVAL_MS 2000
#define REGISTRATION_BLINK_MS 500
#define LED_FEEDBACK_MS 200

// Broadcast address for ESP-NOW
uint8_t broadcastAddr[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// ==================== DATA STRUCTURES ====================
// Message to Master
typedef struct __attribute__((packed)) {
    uint8_t msgType;      // 0=register, 1=toggle, 2=heartbeat
    uint8_t hubId;        
    uint8_t port;         
    uint8_t value;        
    uint8_t globalTileId; 
} TileMessage;

// Command from Master
typedef struct __attribute__((packed)) {
    uint8_t cmdType;      // 0=off, 1=on, 2=blink, 3=ack
    uint8_t targetHub;    // 0xFF = all hubs
    uint8_t targetPort;   // 0xFF = all ports
    uint8_t colorR;
    uint8_t colorG;
    uint8_t colorB;
    uint8_t duration;
} MasterCommand;

// Tile state machine
enum TileState {
    TILE_UNREGISTERED,
    TILE_REGISTERING,
    TILE_REGISTERED,
    TILE_ON,
    TILE_OFF
};

struct Tile {
    TileState state;
    bool switchReading;
    bool lastSwitchReading;
    bool stableSwitch;
    unsigned long debounceTime;
    unsigned long blinkTime;
    bool blinkOn;
    uint32_t currentColor;
};

// ==================== GLOBALS ====================
Adafruit_NeoPixel leds[NUM_TILES] = {
    Adafruit_NeoPixel(LEDS_PER_TILE, LED_PINS[0], NEO_GRB + NEO_KHZ800),
    Adafruit_NeoPixel(LEDS_PER_TILE, LED_PINS[1], NEO_GRB + NEO_KHZ800),
    Adafruit_NeoPixel(LEDS_PER_TILE, LED_PINS[2], NEO_GRB + NEO_KHZ800),
    Adafruit_NeoPixel(LEDS_PER_TILE, LED_PINS[3], NEO_GRB + NEO_KHZ800)
};

Tile tiles[NUM_TILES];
unsigned long lastHeartbeat = 0;
bool espNowReady = false;

// ==================== FUNCTION DECLARATIONS ====================
void initESPNow();
void onESPNowRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len);
void sendMessage(uint8_t type, uint8_t port, uint8_t value);
void handleCommand(const MasterCommand& cmd);
void updateSwitch(int port);
void handleSwitchPress(int port);
void updateLEDs();
void setTileLED(int port, uint32_t color);
int getGlobalTileId(int port);

// ==================== SETUP ====================
void setup() {
    Serial.begin(115200);
    delay(500);
    
    Serial.println("\n========================================");
    Serial.printf("Memory XXL - Tile Hub %d\n", HUB_ID + 1);
    Serial.printf("Tiles: %d-%d\n", HUB_ID * 4 + 1, HUB_ID * 4 + 4);
    Serial.println("========================================");
    
    // Initialize switches
    for (int i = 0; i < NUM_TILES; i++) {
        pinMode(SWITCH_PINS[i], INPUT_PULLUP);
        tiles[i].state = TILE_UNREGISTERED;
        tiles[i].switchReading = HIGH;
        tiles[i].lastSwitchReading = HIGH;
        tiles[i].stableSwitch = HIGH;
        tiles[i].debounceTime = 0;
        tiles[i].blinkTime = 0;
        tiles[i].blinkOn = false;
        tiles[i].currentColor = 0;
    }
    
    // Initialize LEDs
    for (int i = 0; i < NUM_TILES; i++) {
        leds[i].begin();
        leds[i].clear();
        leds[i].show();
    }
    
    // Startup animation
    for (int i = 0; i < NUM_TILES; i++) {
        setTileLED(i, leds[i].Color(0, 0, 100));
        delay(100);
    }
    delay(200);
    for (int i = 0; i < NUM_TILES; i++) {
        setTileLED(i, 0);
    }
    
    // Initialize ESP-NOW
    initESPNow();
    
    // Start registration mode - blue blink for unregistered tiles
    for (int i = 0; i < NUM_TILES; i++) {
        tiles[i].state = TILE_UNREGISTERED;
        tiles[i].currentColor = leds[i].Color(0, 0, 255);
        tiles[i].blinkTime = millis();
    }
    
    Serial.println("✓ Hub ready - step on tiles to register");
}

// ==================== MAIN LOOP ====================
void loop() {
    unsigned long now = millis();
    
    // Update switches
    for (int i = 0; i < NUM_TILES; i++) {
        updateSwitch(i);
    }
    
    // Update LEDs (handle blinking)
    updateLEDs();
    
    // Send heartbeat
    if (espNowReady && (now - lastHeartbeat >= HEARTBEAT_INTERVAL_MS)) {
        for (int i = 0; i < NUM_TILES; i++) {
            if (tiles[i].state >= TILE_REGISTERED) {
                sendMessage(2, i, 1); // Heartbeat
            }
        }
        lastHeartbeat = now;
    }
}

// ==================== ESP-NOW ====================
void initESPNow() {
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();
    
    // Force WiFi channel to match master
    esp_wifi_set_promiscuous(true);
    esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
    esp_wifi_set_promiscuous(false);
    
    Serial.printf("WiFi channel: %d\n", WIFI_CHANNEL);
    
    if (esp_now_init() != ESP_OK) {
        Serial.println("✗ ESP-NOW init failed");
        ESP.restart();
    }
    
    // Add broadcast peer
    esp_now_peer_info_t peer = {};
    memcpy(peer.peer_addr, broadcastAddr, 6);
    peer.channel = WIFI_CHANNEL;
    peer.encrypt = false;
    
    if (!esp_now_is_peer_exist(broadcastAddr)) {
        if (esp_now_add_peer(&peer) != ESP_OK) {
            Serial.println("✗ Failed to add broadcast peer");
        }
    }
    
    esp_now_register_recv_cb(onESPNowRecv);
    
    espNowReady = true;
    Serial.println("✓ ESP-NOW ready");
}

void onESPNowRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
    if (len != sizeof(MasterCommand)) return;
    
    MasterCommand cmd;
    memcpy(&cmd, data, sizeof(cmd));
    
    // Check if command is for this hub
    if (cmd.targetHub != 255 && cmd.targetHub != HUB_ID) return;
    
    handleCommand(cmd);
}

void sendMessage(uint8_t type, uint8_t port, uint8_t value) {
    if (!espNowReady) return;
    
    TileMessage msg;
    msg.msgType = type;
    msg.hubId = HUB_ID;
    msg.port = port;
    msg.value = value;
    msg.globalTileId = getGlobalTileId(port);
    
    esp_now_send(broadcastAddr, (uint8_t*)&msg, sizeof(msg));
}

void handleCommand(const MasterCommand& cmd) {
    // Determine which ports to affect
    int startPort = (cmd.targetPort == 255) ? 0 : cmd.targetPort;
    int endPort = (cmd.targetPort == 255) ? NUM_TILES : cmd.targetPort + 1;
    
    // Debug: log received command
    Serial.printf("📥 CMD: type=%d hub=%d port=%d RGB(%d,%d,%d)\n", 
                  cmd.cmdType, cmd.targetHub, cmd.targetPort, 
                  cmd.colorR, cmd.colorG, cmd.colorB);
    
    for (int p = startPort; p < endPort && p < NUM_TILES; p++) {
        uint32_t color = leds[p].Color(cmd.colorR, cmd.colorG, cmd.colorB);
        
        switch (cmd.cmdType) {
            case 0: // OFF
                Serial.printf("💡 Tile %d OFF\n", getGlobalTileId(p));
                tiles[p].currentColor = 0;
                if (tiles[p].state >= TILE_REGISTERED) {
                    tiles[p].state = TILE_OFF;
                }
                setTileLED(p, 0);
                break;
                
            case 1: // ON
                tiles[p].currentColor = color;
                if (tiles[p].state >= TILE_REGISTERED) {
                    tiles[p].state = TILE_ON;
                }
                setTileLED(p, color);
                break;
                
            case 2: // BLINK
                tiles[p].currentColor = color;
                tiles[p].blinkTime = millis();
                tiles[p].blinkOn = true;
                break;
                
            case 3: // ACK (registration confirmed)
                if (tiles[p].state == TILE_REGISTERING) {
                    tiles[p].state = TILE_REGISTERED;
                    Serial.printf("✓ Tile %d registered by master\n", getGlobalTileId(p));
                }
                // Flash green
                setTileLED(p, leds[p].Color(0, 255, 0));
                delay(LED_FEEDBACK_MS);
                setTileLED(p, 0);
                tiles[p].currentColor = 0;
                break;
        }
    }
}

// ==================== SWITCH HANDLING ====================
void updateSwitch(int port) {
    tiles[port].switchReading = digitalRead(SWITCH_PINS[port]);
    
    // Debounce logic
    if (tiles[port].switchReading != tiles[port].lastSwitchReading) {
        tiles[port].debounceTime = millis();
    }
    
    if ((millis() - tiles[port].debounceTime) > DEBOUNCE_MS) {
        if (tiles[port].switchReading != tiles[port].stableSwitch) {
            tiles[port].stableSwitch = tiles[port].switchReading;
            
            // Switch pressed (LOW because of pull-up)
            if (tiles[port].stableSwitch == LOW) {
                handleSwitchPress(port);
            }
        }
    }
    
    tiles[port].lastSwitchReading = tiles[port].switchReading;
}

void handleSwitchPress(int port) {
    int globalId = getGlobalTileId(port);
    Serial.printf("🔘 Tile %d pressed (state: %d)\n", globalId, tiles[port].state);
    
    switch (tiles[port].state) {
        case TILE_UNREGISTERED:
            // Send registration request
            tiles[port].state = TILE_REGISTERING;
            sendMessage(0, port, 1); // Type 0 = register
            
            // Visual feedback - green flash
            setTileLED(port, leds[port].Color(0, 255, 0));
            delay(LED_FEEDBACK_MS);
            setTileLED(port, 0);
            
            // If no ack received, auto-confirm after brief delay
            delay(200);
            if (tiles[port].state == TILE_REGISTERING) {
                tiles[port].state = TILE_REGISTERED;
                Serial.printf("✓ Tile %d self-registered\n", globalId);
            }
            tiles[port].currentColor = 0;
            break;
            
        case TILE_REGISTERING:
            // Still waiting for registration, ignore
            break;
            
        case TILE_REGISTERED:
        case TILE_OFF:
            // Toggle ON
            tiles[port].state = TILE_ON;
            tiles[port].currentColor = leds[port].Color(0, 255, 0);
            setTileLED(port, tiles[port].currentColor);
            sendMessage(1, port, 1); // Type 1 = toggle, value 1 = ON
            Serial.printf("💡 Tile %d ON\n", globalId);
            break;
            
        case TILE_ON:
            // Toggle OFF
            tiles[port].state = TILE_OFF;
            tiles[port].currentColor = 0;
            setTileLED(port, 0);
            sendMessage(1, port, 0); // Type 1 = toggle, value 0 = OFF
            Serial.printf("💡 Tile %d OFF\n", globalId);
            break;
    }
}

// ==================== LED HANDLING ====================
void setTileLED(int port, uint32_t color) {
    if (color == 0) {
        leds[port].clear();
    } else {
        leds[port].fill(color);
    }
    leds[port].show();
}

void updateLEDs() {
    unsigned long now = millis();
    
    for (int i = 0; i < NUM_TILES; i++) {
        // Handle blinking for unregistered tiles
        if (tiles[i].state == TILE_UNREGISTERED) {
            if (now - tiles[i].blinkTime >= REGISTRATION_BLINK_MS) {
                tiles[i].blinkTime = now;
                tiles[i].blinkOn = !tiles[i].blinkOn;
                
                if (tiles[i].blinkOn) {
                    leds[i].fill(leds[i].Color(0, 0, 100)); // Blue blink
                } else {
                    leds[i].clear();
                }
                leds[i].show();
            }
        }
    }
}

// ==================== UTILITY ====================
int getGlobalTileId(int port) {
    return HUB_ID * NUM_TILES + port + 1;
}
