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
  // BSEC_OUTPUT_IAQ signal, 0 to 500. NaN when not reported; printed as null.
  double iaq;
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

// Writes the index with two decimals, or null when it is not finite or off the
// 0-500 scale that bsec_datatypes.h documents for BSEC_OUTPUT_IAQ.
inline void roomIndexText(char* output, std::size_t capacity, double value) {
  if (std::isfinite(value) && value >= 0.0 && value <= 500.0) {
    std::snprintf(output, capacity, "%.2f", value);
  } else {
    std::snprintf(output, capacity, "null");
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
  char index[16];
  roomIndexText(index, sizeof(index), sample.iaq);
  const int length = std::snprintf(
      output, capacity,
      "{\"type\":\"reading\",\"temp_c\":%.2f,\"humidity_pct\":%.2f,"
      "\"pressure_hpa\":%.2f,\"gas_ohms\":%.2f,\"bsec\":{"
      "\"stabilization_status\":%s,\"run_in_status\":%s,\"iaq_accuracy\":%s,\"iaq\":%s}}",
      sample.temp_c, sample.humidity_pct, sample.pressure_hpa, sample.gas_ohms,
      roomBinaryStatus(sample.stabilization), roomBinaryStatus(sample.run_in),
      roomAccuracyStatus(sample.accuracy), index);
  if (length < 0 || static_cast<std::size_t>(length) >= capacity) {
    output[0] = '\0';
    return false;
  }
  return true;
}
