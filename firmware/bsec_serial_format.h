#pragma once

#include <cmath>
#include <cstddef>
#include <cstdio>

struct RoomSample {
  double temp_c;
  double humidity_pct;
  double pressure_hpa;
  double gas_ohms;
  int stabilization;
  int run_in;
  int accuracy;
};

inline const char* roomBinaryStatus(int value) {
  return value == 0 ? "0" : value == 1 ? "1" : "null";
}

inline const char* roomAccuracyStatus(int value) {
  switch (value) {
    case 0: return "0";
    case 1: return "1";
    case 2: return "2";
    case 3: return "3";
    default: return "null";
  }
}

inline bool formatRoomReading(char* output, std::size_t capacity,
                              const RoomSample& sample) {
  if (output == nullptr || capacity == 0) return false;
  output[0] = '\0';
  if (!std::isfinite(sample.temp_c) || !std::isfinite(sample.humidity_pct) ||
      !std::isfinite(sample.pressure_hpa) || !std::isfinite(sample.gas_ohms)) {
    return false;
  }
  const int length = std::snprintf(
      output, capacity,
      "{\"type\":\"reading\",\"temp_c\":%.2f,\"humidity_pct\":%.2f,"
      "\"pressure_hpa\":%.2f,\"gas_ohms\":%.2f,\"bsec\":{"
      "\"stabilization_status\":%s,\"run_in_status\":%s,\"iaq_accuracy\":%s}}",
      sample.temp_c, sample.humidity_pct, sample.pressure_hpa, sample.gas_ohms,
      roomBinaryStatus(sample.stabilization), roomBinaryStatus(sample.run_in),
      roomAccuracyStatus(sample.accuracy));
  if (length < 0 || static_cast<std::size_t>(length) >= capacity) {
    output[0] = '\0';
    return false;
  }
  return true;
}
