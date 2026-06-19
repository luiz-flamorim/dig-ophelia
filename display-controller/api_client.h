#pragma once

#include <Arduino.h>

void apiBegin();
bool apiFetchModuleFrame(uint8_t* buffer, size_t bufferSize);
