#include "display_renderer.h"

#include <string.h>

#include "LedControl1.h"
#include "config.h"

namespace {

constexpr uint8_t  DEVICES_PER_ROW      = MODULE_COLS / DIGITS_PER_DEVICE;
constexpr uint8_t  DEVICES_PER_TILE_ROW = TILE_COLS / DIGITS_PER_DEVICE;
constexpr uint8_t  DEVICES_PER_TILE     = TILE_ROWS * DEVICES_PER_TILE_ROW;
constexpr uint8_t  NUM_DEVICES          = MODULE_ROWS * DEVICES_PER_ROW;
// Re-assert all chip registers every N frames to recover from brownout / SPI
// noise that corrupts shutdown, decode-mode, scan-limit, or intensity.
// At ~8 FPS this fires every ~7 s; at 25 FPS every ~2.4 s.
constexpr uint16_t REINIT_PERIOD_FRAMES = 60;
static_assert(NUM_DEVICES <= 64, "LedControl buffers support up to 64 MAX7219 devices (2x2 module)");
static_assert(
    NUM_DEVICES == (MODULE_TILES_X * MODULE_TILES_Y) * DEVICES_PER_TILE,
    "Device count must match tile count × devices per tile");

LedControl lc(PIN_MOSI, PIN_CLK, PIN_CS, NUM_DEVICES);

// Map SPI stream index (wire byte order) to MAX7219 device + digit.
// Stream order matches Pi packer: each tile is a contiguous block on the chain.
void streamIndexToDevice(uint16_t streamIndex, uint8_t* device, uint8_t* digit) {
  if (TILE_CHAIN_BLOCK_ORDER) {
    constexpr uint16_t CELLS_PER_TILE = TILE_ROWS * TILE_COLS;
    const uint8_t tileIndex = streamIndex / CELLS_PER_TILE;
    const uint16_t inTile = streamIndex % CELLS_PER_TILE;
    const uint8_t rowInTile = inTile / TILE_COLS;
    const uint8_t colInTile = inTile % TILE_COLS;

    *device = static_cast<uint8_t>(
        tileIndex * DEVICES_PER_TILE + rowInTile * DEVICES_PER_TILE_ROW + colInTile / DIGITS_PER_DEVICE);
    *digit = colInTile % DIGITS_PER_DEVICE;
  } else {
    const uint8_t row = streamIndex / MODULE_COLS;
    const uint8_t col = streamIndex % MODULE_COLS;
    *device = static_cast<uint8_t>(row * DEVICES_PER_ROW + col / DIGITS_PER_DEVICE);
    *digit = col % DIGITS_PER_DEVICE;
  }
}

void correctDigitForReversedRows(uint8_t device, uint8_t* digit) {
  if (!FIX_REVERSED_LAST_TWO_ROWS) {
    return;
  }

  uint8_t row;
  uint8_t devInRow;
  if (TILE_CHAIN_BLOCK_ORDER) {
    const uint8_t offsetInTile = device % DEVICES_PER_TILE;
    row = offsetInTile / DEVICES_PER_TILE_ROW;
    devInRow = offsetInTile % DEVICES_PER_TILE_ROW;
  } else {
    row = device / DEVICES_PER_ROW;
    devInRow = device % DEVICES_PER_ROW;
  }

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

// Boot wiring test: each tile shows {MODULE_ID}{tileIndex} (e.g. 00, 01, 02, 03).
// Tiles are side-by-side within a module; modules stack in the install.
// Matching digits (00, 11) fill every cell; mixed digits alternate per column (0101…).
void tileIdTest() {
  setAllDigitsOff();
  delay(500);

  constexpr uint16_t CELLS_PER_TILE = TILE_ROWS * TILE_COLS;

  for (uint16_t streamIndex = 0; streamIndex < MODULE_CELLS; streamIndex++) {
    const uint8_t tileIndex = streamIndex / CELLS_PER_TILE;
    const uint8_t colInTile = (streamIndex % CELLS_PER_TILE) % TILE_COLS;

    const uint8_t moduleDigit = MODULE_ID % 10;
    const uint8_t tileDigit = tileIndex % 10;

    uint8_t value;
    if (moduleDigit == tileDigit) {
      value = moduleDigit;
    } else if (colInTile % 2 == 0) {
      value = moduleDigit;
    } else {
      value = tileDigit;
    }

    uint8_t device;
    uint8_t digit;
    streamIndexToDevice(streamIndex, &device, &digit);
    correctDigitForReversedRows(device, &digit);

    lc.setDigit(device, digit, value, false);
    delayMicroseconds(50);
  }

  delay(3000);
  setAllDigitsOff();
  delay(300);
}

// Re-assert every critical MAX7219 register so a chip whose config was
// corrupted by brownout or SPI noise recovers without a reboot.
// Does NOT clear the display — the frame write that follows overwrites it.
void reinitAllDevices() {
  for (uint8_t d = 0; d < NUM_DEVICES; d++) {
    lc.shutdown(d, false);
    lc.disableDisplayTest(d);
    lc.setScanLimit(d, 7);
    lc.setIntensity(d, BASE_BRIGHTNESS);
  }
}

void processMessage(const uint8_t* bytes) {
  // Full register reinit every REINIT_PERIOD_FRAMES; fast display-test clear on other frames.
  static uint16_t frameCount = 0;
  if (++frameCount >= REINIT_PERIOD_FRAMES) {
    frameCount = 0;
    reinitAllDevices();
  } else {
    lc.resetDisplayTestAll();
  }

  // Step 1: decode every stream bit into a per-device, per-digit-register byte.
  // On = 0x7F (all segments lit, same as charTable[8]).  Off = 0x00.
  uint8_t frame[NUM_DEVICES][8];
  memset(frame, 0, sizeof(frame));

  for (uint16_t streamIndex = 0; streamIndex < MODULE_CELLS; streamIndex++) {
    const uint16_t byteIndex = streamIndex / 8;
    const uint8_t  bit       = 7 - (streamIndex % 8);
    const bool     isActive  = (bytes[byteIndex] >> bit) & 1;

    uint8_t device;
    uint8_t digit;
    streamIndexToDevice(streamIndex, &device, &digit);
    correctDigitForReversedRows(device, &digit);

    frame[device][digit] = isActive ? 0x7F : 0x00;
  }

  // Step 2: flush the frame — one SPI transaction per digit register, updating
  // all devices simultaneously (8 transactions total, regardless of chain length).
  uint8_t rowValues[NUM_DEVICES];
  for (uint8_t digitPos = 0; digitPos < 8; digitPos++) {
    for (uint8_t dev = 0; dev < NUM_DEVICES; dev++) {
      rowValues[dev] = frame[dev][digitPos];
    }
    lc.setRowAllDevices(digitPos, rowValues, NUM_DEVICES);
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
    tileIdTest();
    delay(1000);
  }
}

void displayRenderFrame(const uint8_t* bytes) {
  processMessage(bytes);
}
