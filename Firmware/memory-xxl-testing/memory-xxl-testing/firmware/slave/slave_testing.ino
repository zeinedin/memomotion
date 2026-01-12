/**
 * Memory XXL - Slave Tile (TESTING VERSION - Jan 9, 2025)
 * 
 * !!! CHANGE TILE_ID FOR EACH TILE !!!
 * Tile 1: #define TILE_ID 1
 * Tile 2: #define TILE_ID 2
 * etc.
 */

#include <esp_now.h>
#include <WiFi.h>

// ==================== CONFIGURATION ====================
#define TILE_ID 1  // !!! CHANGE THIS: 1, 2, 3, 4, etc. !!!

#define LED_PIN 2
#define TOUCH_PIN 4
#define BATTERY_PIN 34

// Master MAC - GET THIS FROM MASTER'S SERIAL MONITOR
uint8_t masterMAC[] = {0x20, 0xE7, 0xC8, 0x9E, 0xE3, 0x68};

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

// ==================== GLOBALS ====================
enum State {
  STARTUP_BLINK,
  STARTUP_WAIT,
  RUNNING
};

State currentState = STARTUP_BLINK;

unsigned long currentMillis = 0;
unsigned long blinkTimer = 0;
unsigned long waitTimer = 0;
unsigned long lastHeartbeat = 0;
unsigned long lastRegister = 0;
unsigned long lastDebounce = 0;

int blinkCount = 0;
unsigned long waitDuration = 0;

bool isRegistered = false;
bool ledState = false;
bool lastTouch = false;
bool currentTouch = false;

const unsigned long HEARTBEAT_INTERVAL = 5000;
const unsigned long REGISTER_INTERVAL = 2000;
const unsigned long DEBOUNCE_DELAY = 50;

// ==================== SETUP ====================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== Memory XXL Tile (Testing) ===");
  Serial.printf("Tile ID: %d\n", TILE_ID);
  Serial.println("Version: Jan 9, 2025");
  
  pinMode(LED_PIN, OUTPUT);
  pinMode(TOUCH_PIN, INPUT_PULLUP);
  pinMode(BATTERY_PIN, INPUT);
  
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  
  Serial.print("MAC: ");
  Serial.println(WiFi.macAddress());
  
  initESPNow();
  
  randomSeed(analogRead(0));
  waitDuration = random(200, 1500);
  
  Serial.println("✓ Ready");
}

// ==================== LOOP ====================
void loop() {
  currentMillis = millis();
  
  switch (currentState) {
    case STARTUP_BLINK:
      // Blink 3 times
      if (currentMillis - blinkTimer >= 150) {
        blinkTimer = currentMillis;
        ledState = !ledState;
        digitalWrite(LED_PIN, ledState);
        if (!ledState) blinkCount++;
        
        if (blinkCount >= 3) {
          digitalWrite(LED_PIN, LOW);
          currentState = STARTUP_WAIT;
          waitTimer = currentMillis;
          Serial.printf("Wait %d ms...\n", waitDuration);
        }
      }
      break;
      
    case STARTUP_WAIT:
      if (currentMillis - waitTimer >= waitDuration) {
        Serial.println("→ Registering...");
        sendMessage(0, 0);
        lastRegister = currentMillis;
        currentState = RUNNING;
      }
      break;
      
    case RUNNING:
      // Re-register if needed
      if (!isRegistered && currentMillis - lastRegister > REGISTER_INTERVAL) {
        Serial.println("→ Retry registration...");
        sendMessage(0, 0);
        lastRegister = currentMillis;
      }
      
      // Touch sensor with debouncing
      bool rawTouch = readTouch();
      if (rawTouch != currentTouch) {
        lastDebounce = currentMillis;
        currentTouch = rawTouch;
      }
      
      if (currentMillis - lastDebounce > DEBOUNCE_DELAY) {
        if (currentTouch != lastTouch) {
          lastTouch = currentTouch;
          
          if (currentTouch && isRegistered) {
            Serial.println("→ STEP!");
            sendMessage(1, 1);
          }
        }
      }
      
      // Heartbeat
      if (isRegistered && currentMillis - lastHeartbeat > HEARTBEAT_INTERVAL) {
        sendMessage(2, 0);
        lastHeartbeat = currentMillis;
      }
      break;
  }
  
  delay(10);
}

// ==================== ESP-NOW ====================
void initESPNow() {
  if (esp_now_init() != ESP_OK) {
    Serial.println("✗ ESP-NOW failed");
    delay(1000);
    ESP.restart();
  }
  
  Serial.println("✓ ESP-NOW initialized");
  
  esp_now_register_send_cb((esp_now_send_cb_t)onDataSent);
  esp_now_register_recv_cb(onDataReceived);
  
  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, masterMAC, 6);
  peerInfo.channel = 6;  // Match your WiFi channel!
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("✗ Add peer failed");
  } else {
    Serial.println("✓ Master peer added");
  }
}

void sendMessage(uint8_t type, uint8_t value) {
  TileMessage msg;
  msg.tileId = TILE_ID;
  msg.messageType = type;
  msg.value = value;
  msg.batteryLevel = 100;
  
  esp_err_t result = esp_now_send(masterMAC, (uint8_t *)&msg, sizeof(msg));
  
  if (result != ESP_OK) {
    Serial.printf("✗ Send failed: %d\n", result);
  }
}

void onDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  // Optional: track send status
}

void onDataReceived(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (len != sizeof(MasterCommand)) return;
  
  MasterCommand cmd;
  memcpy(&cmd, data, sizeof(cmd));
  
  if (cmd.tileId != TILE_ID && cmd.tileId != 255) return;
  
  Serial.printf("← Command: %d\n", cmd.command);
  
  switch (cmd.command) {
    case 0:  // OFF
      digitalWrite(LED_PIN, LOW);
      break;
    case 1:  // ON
      digitalWrite(LED_PIN, HIGH);
      break;
    case 2:  // BLINK
      // Quick blink
      for (int i = 0; i < 3; i++) {
        digitalWrite(LED_PIN, HIGH);
        delay(100);
        digitalWrite(LED_PIN, LOW);
        delay(100);
      }
      break;
    case 3:  // ACK - REGISTERED!
      isRegistered = true;
      digitalWrite(LED_PIN, LOW);
      Serial.println("✓✓✓ REGISTERED! ✓✓✓");
      break;
  }
}

// ==================== HELPERS ====================
bool readTouch() {
  // Option 1: Capacitive touch
  int value = touchRead(TOUCH_PIN);
  return value < 40;
  
  // Option 2: Digital button (uncomment if using button)
  // return digitalRead(TOUCH_PIN) == LOW;
}
