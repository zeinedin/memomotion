#include <Adafruit_NeoPixel.h>

#define LED_PIN    13      // GPIO 13
#define LED_COUNT  12      // 12 NeoPixels

Adafruit_NeoPixel pixels(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

void setup() {
  pixels.begin();          // Initialiseer NeoPixel
  pixels.clear();          // Zet alle LEDs uit
  pixels.show();
}

void loop() {
  // Alle LEDs rood
  setAll(255, 0, 0);
  delay(1000);

  // Alle LEDs groen
  setAll(0, 255, 0);
  delay(1000);

  // Alle LEDs blauw
  setAll(0, 0, 255);
  delay(1000);

  // Uit
  setAll(0, 0, 0);
  delay(1000);
}

void setAll(uint8_t r, uint8_t g, uint8_t b) {
  for (int i = 0; i < LED_COUNT; i++) {
    pixels.setPixelColor(i, pixels.Color(r, g, b));
  }
  pixels.show();
}
