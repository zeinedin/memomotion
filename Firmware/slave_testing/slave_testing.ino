/**
 * Memory XXL - SLAVE TILE
 * FINAL FIXED VERSION: Standard LEDs + Auto-Calibrate Touch
 */

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>

// ==================== CONFIGURATION ====================
#define TILE_ID 4  // !!! CHANGE THIS FOR EACH TILE !!!


// Pins
#define LED_PIN 2
#define TOUCH_PIN 4 

// Master MAC
uint8_t masterMAC[] = {0x00, 0x70, 0x07, 0x81, 0x4E, 0x10};

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

// ==================== SETTINGS ====================
// !!! FIXED LED LOGIC (STANDARD) !!!
#define LED_ON  HIGH   
#define LED_OFF LOW  

// Touch Sensitivity
// Triggers if value drops by 30 (e.g., 250 -> 220)
const int TOUCH_DROP_REQUIRED = 30; 

// Globals
int touchBaseline = 0;
bool isRegistered = false;
bool currentTouch = false;
bool lastTouch = false;
unsigned long lastDebounce = 0;
unsigned long lastRegister = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.printf("\n=== TILE %d STARTING ===\n", TILE_ID);

  // 1. Setup LED (Start OFF)
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LED_OFF); 

  // 2. Setup WiFi & Channel 6
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(6, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false);
  
  // 3. Setup ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    ESP.restart();
  }
  esp_now_register_recv_cb(onDataReceived);
  
  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, masterMAC, 6);
  peerInfo.channel = 6; 
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add master peer");
  } else {
    Serial.println("Master peer added");
  }

  // 4. AUTO-CALIBRATE TOUCH
  // Do NOT touch the wire while this runs (first 2 seconds)
  long total = 0;
  for(int i=0; i<10; i++) {
    total += touchRead(TOUCH_PIN);
    delay(10);
  }
  touchBaseline = total / 10;
  Serial.print("✓ Touch Baseline: "); Serial.println(touchBaseline);
  Serial.print("✓ Trigger Level: < "); Serial.println(touchBaseline - TOUCH_DROP_REQUIRED);
}

void loop() {
  unsigned long now = millis();

  // 1. Register with Master
  if (!isRegistered && (now - lastRegister > 2000)) {
    Serial.println("→ Sending Registration...");
    sendMessage(0, 0); 
    lastRegister = now;
    
    // Quick blink
    digitalWrite(LED_PIN, LED_ON); delay(50); digitalWrite(LED_PIN, LED_OFF);
  }

  // 2. TOUCH LOGIC
  int val = touchRead(TOUCH_PIN);
  bool isTouched = (val < (touchBaseline - TOUCH_DROP_REQUIRED));

  if (isTouched != currentTouch) {
    lastDebounce = now;
    currentTouch = isTouched;
  }

  if ((now - lastDebounce) > 50) {
    if (currentTouch != lastTouch) {
      lastTouch = currentTouch;
      
      if (currentTouch == true && isRegistered) {
        Serial.printf("→ TOUCH! (Val: %d)\n", val);
        
        // Feedback
        digitalWrite(LED_PIN, LED_ON);
        sendMessage(1, 1); 
        delay(100);
        digitalWrite(LED_PIN, LED_OFF);
      }
    }
  }
  delay(20);
}

void sendMessage(uint8_t type, uint8_t value) {
  TileMessage msg;
  msg.tileId = TILE_ID;
  msg.messageType = type;
  msg.value = value;
  esp_now_send(masterMAC, (uint8_t *) &msg, sizeof(msg));
}

void onDataReceived(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (len != sizeof(MasterCommand)) return;
  MasterCommand cmd;
  memcpy(&cmd, data, sizeof(cmd));

  if (cmd.tileId != TILE_ID && cmd.tileId != 0) return;

  if (cmd.command == 0) digitalWrite(LED_PIN, LED_OFF); 
  else if (cmd.command == 1) digitalWrite(LED_PIN, LED_ON); 
  else if (cmd.command == 3) {
    isRegistered = true;
    Serial.println("✓ REGISTERED!");
    digitalWrite(LED_PIN, LED_ON); delay(200); digitalWrite(LED_PIN, LED_OFF);
  }
}