// Run on Linux only after choosing an available C++11 toolchain.
#include "../bsec_serial_format.h"
#include <cassert>
#include <cstring>
#include <limits>

int main() {
  RoomSample sample = {24.0, 45.0, 1005.0, 12000.0, 1, 0, 2};
  char output[320];
  assert(formatRoomReading(output, sizeof(output), sample));
  assert(std::strcmp(output,
      "{\"type\":\"reading\",\"temp_c\":24.00,\"humidity_pct\":45.00,"
      "\"pressure_hpa\":1005.00,\"gas_ohms\":12000.00,\"bsec\":{"
      "\"stabilization_status\":1,\"run_in_status\":0,\"iaq_accuracy\":2}}") == 0);

  sample.run_in = -1;
  assert(formatRoomReading(output, sizeof(output), sample));
  assert(std::strstr(output, "\"run_in_status\":null") != nullptr);
  sample.stabilization = 2;
  sample.accuracy = 4;
  assert(formatRoomReading(output, sizeof(output), sample));
  assert(std::strstr(output, "\"stabilization_status\":null") != nullptr);
  assert(std::strstr(output, "\"iaq_accuracy\":null") != nullptr);

  char shortBuffer[12];
  assert(!formatRoomReading(shortBuffer, sizeof(shortBuffer), sample));
  assert(shortBuffer[0] == '\0');
  assert(!formatRoomReading(nullptr, 0, sample));

  for (int field = 0; field < 4; ++field) {
    RoomSample invalid = sample;
    double* values[] = {&invalid.temp_c, &invalid.humidity_pct,
                        &invalid.pressure_hpa, &invalid.gas_ohms};
    *values[field] = std::numeric_limits<double>::quiet_NaN();
    assert(!formatRoomReading(output, sizeof(output), invalid));
    assert(output[0] == '\0');
    *values[field] = std::numeric_limits<double>::infinity();
    assert(!formatRoomReading(output, sizeof(output), invalid));
  }
  return 0;
}
