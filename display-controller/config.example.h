#pragma once

// Copy this file to config.h and fill in your WiFi credentials.
// Keep MODULE_TILES_X/Y in sync with camera-processor/config.py.

// --- Tile (fixed — matches Pi config.TILE_ROWS / TILE_COLS) ---
constexpr uint8_t TILE_ROWS = 8;
constexpr uint8_t TILE_COLS = 16;

// --- Tiles per module (Phase 1: 1×1, two-tile test: 2×1 or 1×2, full module: 2×2) ---
constexpr uint8_t MODULE_TILES_X = 1;
constexpr uint8_t MODULE_TILES_Y = 1;

// --- Derived module grid (this ESP32 drives one module) ---
constexpr uint8_t MODULE_ROWS = TILE_ROWS * MODULE_TILES_Y;
constexpr uint8_t MODULE_COLS = TILE_COLS * MODULE_TILES_X;
constexpr uint16_t MODULE_CELLS = MODULE_ROWS * MODULE_COLS;
constexpr uint16_t BYTES_PER_MODULE = (MODULE_CELLS + 7) / 8;

// --- Which Pi endpoint this board polls (install layout is Pi config.INSTALL_MODULES_*) ---
constexpr uint8_t MODULE_ID = 0;

// --- Network ---
constexpr const char* WIFI_SSID = "YOUR_WIFI_SSID";
constexpr const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";
constexpr const char* PI_HOST = "192.168.1.157";
constexpr uint16_t PI_PORT = 8080;
constexpr uint32_t POLL_INTERVAL_MS = 120;
constexpr uint32_t WIFI_CONNECT_TIMEOUT_MS = 15000;

// --- Hardware SPI (ESP32 VSPI — data/clk pins ignored by LedControl, uses HW SPI) ---
constexpr uint8_t PIN_MOSI = 23;
constexpr uint8_t PIN_CLK = 18;
constexpr uint8_t PIN_CS = 4;
constexpr uint8_t DIGITS_PER_DEVICE = 8;
constexpr uint8_t BASE_BRIGHTNESS = 3;

// --- Debug ---
constexpr bool SERIAL_DEBUG = false;  // true = log every fetched frame to Serial (slow)

// --- Daisy chain: true = each tile is a contiguous SPI block (tile 0 rows 0–7, then tile 1, …) ---
constexpr bool TILE_CHAIN_BLOCK_ORDER = true;

// --- Tile order: true = chain tile 0 is the rightmost tile (match Pi TILE_MIRROR_X) ---
constexpr bool TILE_MIRROR_X = false;

// --- Startup ---
constexpr bool RUN_ROW_TEST_ON_BOOT = true;

// --- Hardware workaround: reverse last two rows (remove when PCB is fixed) ---
constexpr bool FIX_REVERSED_LAST_TWO_ROWS = true;
