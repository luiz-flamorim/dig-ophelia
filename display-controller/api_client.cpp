#include "api_client.h"

#include <HTTPClient.h>
#include <WiFi.h>

#include "config.h"

namespace {

bool wifiConnected = false;
HTTPClient http;

bool ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    return true;
  }

  wifiConnected = false;
  Serial.println("WiFi disconnected — reconnecting...");
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  const uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_CONNECT_TIMEOUT_MS) {
    delay(250);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi connect failed");
    return false;
  }

  wifiConnected = true;
  Serial.print("WiFi connected: ");
  Serial.println(WiFi.localIP());
  return true;
}

void logHexFrame(const uint8_t* buffer, size_t length) {
  for (size_t i = 0; i < length; i++) {
    if (buffer[i] < 0x10) {
      Serial.print('0');
    }
    Serial.print(buffer[i], HEX);
    if (i + 1 < length) {
      Serial.print(' ');
    }
  }
  Serial.println();
}

}  // namespace

void apiBegin() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  // Max TX power — partial mitigation for local RF noise from the SPI/LED chain
  // running right next to this board (suspected cause of ESP32-only packet loss;
  // see ping comparison against the Pi on the same network).
  WiFi.setTxPower(WIFI_POWER_19_5dBm);
  ensureWifi();
}

bool apiFetchModuleFrame(uint8_t* buffer, size_t bufferSize) {
  if (bufferSize < BYTES_PER_MODULE) {
    Serial.println("Fetch buffer too small");
    return false;
  }

  if (!ensureWifi()) {
    return false;
  }

  char url[128];
  snprintf(url, sizeof(url), "http://%s:%u/api/module/%u", PI_HOST, PI_PORT, MODULE_ID);

  // Pi's server speaks HTTP/1.0 (Python http.server default) and closes the
  // socket after every response — setReuse(true) tried to keep it alive
  // across polls, eventually reusing a socket the Pi had already closed
  // (read timeout, then a hard RST). Open a fresh connection every poll instead.
  http.setReuse(false);
  http.setTimeout(500);
  http.begin(url);

  const int httpCode = http.GET();
  if (httpCode != HTTP_CODE_OK) {
    Serial.print("HTTP error ");
    Serial.print(httpCode);
    Serial.print(" for ");
    Serial.println(url);
    http.end();
    return false;
  }

  const int length = http.getSize();
  if (length != static_cast<int>(BYTES_PER_MODULE)) {
    Serial.print("Unexpected payload size: ");
    Serial.print(length);
    Serial.print(" (expected ");
    Serial.print(BYTES_PER_MODULE);
    Serial.println(")");
    http.end();
    return false;
  }

  WiFiClient* stream = http.getStreamPtr();
  size_t received = 0;
  while (received < BYTES_PER_MODULE && http.connected()) {
    const int chunk = stream->readBytes(buffer + received, BYTES_PER_MODULE - received);
    if (chunk <= 0) {
      break;
    }
    received += static_cast<size_t>(chunk);
  }
  http.end();

  if (received != BYTES_PER_MODULE) {
    Serial.print("Incomplete payload: ");
    Serial.println(received);
    return false;
  }

  if (SERIAL_DEBUG) {
    Serial.print("Frame OK (");
    Serial.print(received);
    Serial.print(" bytes): ");
    logHexFrame(buffer, received);
  }
  return true;
}
