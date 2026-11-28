#pragma once

// Sharp dust sample rule. Pure C++11: no Arduino dependency.
// src/firmware/tests/test_sharp_dust_limits.cpp and tests/test_dust.py check it.

#include <cstdint>

// Two equal 10 kohm resistors halve the sensor voltage at the ADC pin.
// This is a wiring assumption; check the divider with a meter.
constexpr uint32_t ROOM_DUST_DIVIDER_RATIO = 2;
// dust.py accepts 0 <= sensor_mv <= 5500 and rejects anything above.
constexpr uint32_t ROOM_DUST_MAX_SENSOR_MV = 5500;
// Largest accepted ADC reading. It keeps every reported mean inside the host
// range and stays below the end of the ESP32-S3 12 dB ADC range (about 3.1 V).
constexpr uint32_t ROOM_DUST_MAX_ADC_MV = 2750;
static_assert(ROOM_DUST_MAX_ADC_MV * ROOM_DUST_DIVIDER_RATIO == ROOM_DUST_MAX_SENSOR_MV,
              "ADC limit must match the host limit through the divider");

// Sharp timing: sample 0.28 ms after LED on, 0.32 ms pulse. Overruns are rejected.
constexpr uint32_t ROOM_DUST_SAMPLE_START_MAX_US = 300;
constexpr uint32_t ROOM_DUST_PULSE_MAX_US = 340;

// LED logic level for the wanted LED state, true = HIGH. With an active-low
// LED (sensor pin 3 driven directly) on is LOW; with an NPN low-side driver
// on is HIGH.
constexpr bool dustLedLevel(bool on, bool activeLow) {
  return on != activeLow;
}

inline bool dustTimingAccepted(uint32_t sampleStartUs, uint32_t pulseUs) {
  return sampleStartUs <= ROOM_DUST_SAMPLE_START_MAX_US && pulseUs <= ROOM_DUST_PULSE_MAX_US;
}

// A zero reading is a failed read in the core; it is rejected too.
inline bool dustSampleAccepted(uint32_t sampleStartUs, uint32_t pulseUs, uint32_t adcMv) {
  return dustTimingAccepted(sampleStartUs, pulseUs) && adcMv > 0 && adcMv <= ROOM_DUST_MAX_ADC_MV;
}

// True when a 3 s window fails and more than half of all its samples were
// rejected only for reading 0 mV: a missing sensor at about 0 V, not a broken
// task. 64-bit arithmetic cannot overflow.
inline bool dustInputAtZero(uint32_t count, uint32_t rejected, uint32_t zeroRejected) {
  const bool windowFails = count < 100 || rejected > count;
  return windowFails &&
         static_cast<uint64_t>(zeroRejected) * 2 > static_cast<uint64_t>(count) + rejected;
}

// Sensor-side mean in mV. Undoes the divider. count must be above zero.
inline double dustSensorMv(uint32_t sum, uint32_t count) {
  return static_cast<double>(ROOM_DUST_DIVIDER_RATIO) * sum / count;
}
