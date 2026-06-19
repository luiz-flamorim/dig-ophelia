#include "display_renderer.h"

#include "LedControl1.h"
#include "config.h"

namespace {

constexpr uint8_t DEVICES_PER_ROW = MODULE_COLS / DIGITS_PER_DEVICE;
constexpr uint8_t NUM_DEVICES = MODULE_ROWS * DEVICES_PER_ROW;

LedControl lc(PIN_MOSI, PIN_CLK, PIN_CS, NUM_DEVICES);

void correctDigitForReversedRows(uint8_t device, uint8_t* digit) {
  if (!FIX_REVERSED_LAST_TWO_ROWS) {
    return;
  }

  const uint8_t row = device / DEVICES_PER_ROW;
  const uint8_t devInRow = device % DEVICES_PER_ROW;

  if (row == 6 && devInRow == 1) {
    *digit = (*digit + 4) % 8;
  } else if (row == 7) {
    *digit = (*digit + 4) % 8;
  }
}

void setAllDigitsOff() {
  for (uint8_t dev = 0; dev < NUM_DEVICES; dev++) {
    lc.clearDisplay(dev);
    if ((dev + 1) % 5 == 0) {
      delayMicroseconds(50);
    }
  }
  delayMicroseconds(100);
}

void rowTest() {
  setAllDigitsOff();
  delay(500);

  for (uint8_t row = 0; row < MODULE_ROWS; row++) {
    const uint8_t firstDevice = row * DEVICES_PER_ROW;

    for (uint8_t devOffset = 0; devOffset < DEVICES_PER_ROW; devOffset++) {
      const uint8_t device = firstDevice + devOffset;
      for (uint8_t digit = 0; digit < DIGITS_PER_DEVICE; digit++) {
        lc.setDigit(device, digit, row, false);
        delayMicroseconds(50);
      }
    }

    delay(50);
  }

  delay(500);
  setAllDigitsOff();
  delay(300);

  for (uint16_t squareIndex = 0; squareIndex < MODULE_CELLS; squareIndex++) {
    const uint8_t row = squareIndex / MODULE_COLS;
    const uint8_t physicalDigit = squareIndex % MODULE_COLS;
    const uint8_t device = row * DEVICES_PER_ROW + (physicalDigit / DIGITS_PER_DEVICE);
    uint8_t digit = physicalDigit % DIGITS_PER_DEVICE;

    correctDigitForReversedRows(device, &digit);
    lc.setDigit(device, digit, physicalDigit, false);
    delayMicroseconds(50);
  }

  delay(2000);
}

void processMessage(const uint8_t* bytes) {
  uint16_t squareIndex = 0;

  for (uint16_t byteIndex = 0; byteIndex < BYTES_PER_MODULE; byteIndex++) {
    const uint8_t value = bytes[byteIndex];

    for (int8_t bit = 7; bit >= 0; bit--) {
      if (squareIndex >= MODULE_CELLS) {
        return;
      }

      const bool isActive = (value >> bit) & 1;
      const uint8_t row = squareIndex / MODULE_COLS;
      const uint8_t physicalDigit = squareIndex % MODULE_COLS;
      const uint8_t device = row * DEVICES_PER_ROW + (physicalDigit / DIGITS_PER_DEVICE);
      uint8_t digit = physicalDigit % DIGITS_PER_DEVICE;

      correctDigitForReversedRows(device, &digit);

      if (isActive) {
        lc.setDigit(device, digit, 8, false);
      } else {
        lc.setChar(device, digit, ' ', false);
      }

      squareIndex++;
    }
  }
}

}  // namespace

void displayBegin() {
  for (uint8_t d = 0; d < NUM_DEVICES; d++) {
    lc.shutdown(d, false);
    delayMicroseconds(100);
    lc.disableDisplayTest(d);
    delayMicroseconds(100);
  }

  for (uint8_t d = 0; d < NUM_DEVICES; d++) {
    lc.setScanLimit(d, 7);
    lc.setIntensity(d, BASE_BRIGHTNESS);
    lc.clearDisplay(d);
  }

  if (RUN_ROW_TEST_ON_BOOT) {
    rowTest();
    delay(1000);
  }
}

void displayRenderFrame(const uint8_t* bytes) {
  processMessage(bytes);
}
