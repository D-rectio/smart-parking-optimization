/*
 * Smart Parking System — Arduino Uno R4
 * 
 * Hardware:
 *   - Arduino Uno R4
 *   - 16x2 LCD with I2C module (address 0x27 or 0x3F)
 *     SDA → A4,  SCL → A5,  VCC → 5V,  GND → GND
 * 
 * Serial protocol (from Python):
 *   "F1B2S6\n"  → Floor 1, Block 2, Slot 6 is available
 *   "NONE\n"    → No slots available
 */

#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ── Change 0x27 to 0x3F if your module uses that address ──
LiquidCrystal_I2C lcd(0x27, 16, 2);

String inputBuffer   = "";
bool   dataReady     = false;

// Custom characters
byte carIcon[8]  = {0b00000, 0b01110, 0b11111, 0b10101, 0b11111, 0b01010, 0b00000, 0b00000};
byte checkMark[8]= {0b00000, 0b00001, 0b00011, 0b10110, 0b11100, 0b01000, 0b00000, 0b00000};
byte crossMark[8]= {0b00000, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b00000, 0b00000};

// ─────────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);
  inputBuffer.reserve(32);

  lcd.init();
  lcd.backlight();
  lcd.createChar(0, carIcon);
  lcd.createChar(1, checkMark);
  lcd.createChar(2, crossMark);

  // Startup splash
  lcd.setCursor(0, 0);
  lcd.print("Smart Parking");
  lcd.setCursor(0, 1);
  lcd.print("System Ready...");
  delay(2000);
  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("Waiting for");
  lcd.setCursor(0, 1);
  lcd.print("camera data...");
}

// ─────────────────────────────────────────────────────────
void loop() {
  if (dataReady) {
    processSlotData(inputBuffer);
    inputBuffer = "";
    dataReady   = false;
  }
}

// ─────────────────────────────────────────────────────────
// Called automatically when serial bytes arrive
void serialEvent() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      dataReady = true;          // signal main loop
    } else if (c != '\r') {
      inputBuffer += c;
    }
  }
}

// ─────────────────────────────────────────────────────────
void processSlotData(String data) {
  data.trim();

  // ── No slots available ──────────────────────────────────
  if (data.equalsIgnoreCase("NONE")) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.write(byte(2));          // cross mark icon
    lcd.print(" No Slots");
    lcd.setCursor(0, 1);
    lcd.print("  Available!");
    return;
  }

  // ── Parse "F<n>B<n>S<n>" ───────────────────────────────
  int fPos = data.indexOf('F');
  int bPos = data.indexOf('B');
  int sPos = data.indexOf('S');

  if (fPos == -1 || bPos == -1 || sPos == -1) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Bad data rcvd");
    return;
  }

  String floorNum = data.substring(fPos + 1, bPos);
  String blockNum = data.substring(bPos + 1, sPos);
  String slotNum  = data.substring(sPos + 1);

  // ── Display on LCD ──────────────────────────────────────
  // Row 0: "Available Slot:"  (15 chars)
  // Row 1: e.g. "F1  Block2  S6"
  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.write(byte(1));            // check-mark icon
  lcd.print(" Available Slot");

  lcd.setCursor(0, 1);
  lcd.print("F");
  lcd.print(floorNum);
  lcd.print(" B");
  lcd.print(blockNum);
  lcd.print(" S");
  lcd.print(slotNum);

  // Echo back to serial for debugging
  Serial.print("Displaying: F");
  Serial.print(floorNum);
  Serial.print(" B");
  Serial.print(blockNum);
  Serial.print(" S");
  Serial.println(slotNum);
}
