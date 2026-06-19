#include "api_client.h"
#include "config.h"
#include "display_renderer.h"

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println("Dig Ophelia display-controller");
  Serial.print("Module ID: ");
  Serial.println(MODULE_ID);
  Serial.print("Grid: ");
  Serial.print(MODULE_ROWS);
  Serial.print(" x ");
  Serial.println(MODULE_COLS);
  Serial.print("Payload bytes: ");
  Serial.println(BYTES_PER_MODULE);

  displayBegin();
  apiBegin();
}

void loop() {
  uint8_t buffer[BYTES_PER_MODULE];

  if (apiFetchModuleFrame(buffer, sizeof(buffer))) {
    displayRenderFrame(buffer);
  }

  delay(POLL_INTERVAL_MS);
}
