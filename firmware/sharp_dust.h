#pragma once
// Experimental acquisition: verify pulse and ADC timing with an oscilloscope.
// Pins are in bsec_board_config.h. ROOM_DUST_LED_PIN HIGH turns on an external
// NPN sink; never wire sensor pin 3 directly. ROOM_DUST_ADC_PIN reads Vo
// through the 2:1 divider. This task never writes Serial; only loop() does.
#include "sharp_dust_limits.h"

static portMUX_TYPE dustMux = portMUX_INITIALIZER_UNLOCKED;
static uint32_t dustSum = 0, dustCount = 0, dustRejected = 0;
static bool dustTaskReady = false;

void dustAcquire(void*) {
  TickType_t wake = xTaskGetTickCount();
  for (;;) {
    digitalWrite(ROOM_DUST_LED_PIN, HIGH);
    const uint32_t start = micros();
    delayMicroseconds(280);
    const uint32_t sampleStart = micros() - start;
    const uint32_t mv = analogReadMilliVolts(ROOM_DUST_ADC_PIN);
    while (micros() - start < 320) {}
    digitalWrite(ROOM_DUST_LED_PIN, LOW);
    const uint32_t pulse = micros() - start;
    portENTER_CRITICAL(&dustMux);
    // Reject timing overruns and out-of-range readings instead of presenting
    // them as good measurements.
    if (dustSampleAccepted(sampleStart, pulse, mv)) {
      dustSum += mv;
      ++dustCount;
    } else ++dustRejected;
    portEXIT_CRITICAL(&dustMux);
    // Reset before delaying so missed cycles cannot produce a catch-up pulse.
    if (xTaskGetTickCount() - wake >= pdMS_TO_TICKS(10)) wake = xTaskGetTickCount();
    vTaskDelayUntil(&wake, pdMS_TO_TICKS(10));
  }
}

void beginDust() {
  pinMode(ROOM_DUST_LED_PIN, OUTPUT);
  digitalWrite(ROOM_DUST_LED_PIN, LOW);
  analogReadResolution(12);
  // The core only applies a per-pin attenuation to a pin that is already an
  // ADC channel, so read once before setting it. 11 dB is ESP-IDF 12 dB.
  analogReadMilliVolts(ROOM_DUST_ADC_PIN);
  analogSetPinAttenuation(ROOM_DUST_ADC_PIN, ADC_11db);
  // Prime ADC calibration outside the timed pulse.
  analogReadMilliVolts(ROOM_DUST_ADC_PIN);
  dustTaskReady = xTaskCreate(dustAcquire, "sharp-dust", 2048, nullptr, 2, nullptr) == pdPASS;
}

void reportDust() {
  static unsigned long last = 0;
  if (millis() - last < 3000) return;
  last = millis();
  uint32_t sum, count, rejected;
  portENTER_CRITICAL(&dustMux);
  sum = dustSum; count = dustCount; rejected = dustRejected;
  dustSum = dustCount = dustRejected = 0;
  portEXIT_CRITICAL(&dustMux);
  if (!dustTaskReady || count < 100 || rejected > count) {
    Serial.println("{\"type\":\"dust_error\",\"message\":\"dust_acquisition_unavailable\"}");
    return;
  }
  // dustSensorMv undoes the 2:1 divider.
  Serial.print("{\"type\":\"dust\",\"sensor_mv\":");
  Serial.print(dustSensorMv(sum, count), 1);
  Serial.print(",\"samples\":"); Serial.print(count);
  Serial.print(",\"rejected_samples\":"); Serial.print(rejected);
  Serial.println("}");
}
