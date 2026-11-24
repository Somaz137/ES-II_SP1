// Host test for the Sharp dust sample rule. Build on Linux with
// g++ -std=c++11 -Wall -Wextra -pedantic firmware/tests/test_sharp_dust_limits.cpp
#include "../sharp_dust_limits.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>

int main() {
  // The largest accepted ADC value maps to the host's largest accepted value.
  assert(ROOM_DUST_MAX_ADC_MV * ROOM_DUST_DIVIDER_RATIO == ROOM_DUST_MAX_SENSOR_MV);
  assert(ROOM_DUST_MAX_SENSOR_MV == 5500);

  assert(dustSampleAccepted(280, 320, 1));
  assert(dustSampleAccepted(300, 340, ROOM_DUST_MAX_ADC_MV));
  assert(!dustSampleAccepted(280, 320, 0));
  assert(!dustSampleAccepted(280, 320, ROOM_DUST_MAX_ADC_MV + 1));
  assert(!dustSampleAccepted(280, 320, 2999));  // Accepted before this step.
  assert(!dustSampleAccepted(301, 320, 1000));
  assert(!dustSampleAccepted(280, 341, 1000));

  // A mean of accepted samples, printed with one decimal as the sketch does,
  // never exceeds the host limit.
  const uint32_t count = 300;
  const uint32_t sums[] = {count * ROOM_DUST_MAX_ADC_MV, count * ROOM_DUST_MAX_ADC_MV - 1,
                           count * 1, count * 450 + 7};
  for (uint32_t sum : sums) {
    char text[32];
    std::snprintf(text, sizeof(text), "%.1f", dustSensorMv(sum, count));
    const double printed = std::atof(text);
    assert(printed > 0 && printed <= ROOM_DUST_MAX_SENSOR_MV);
  }
  assert(dustSensorMv(count * ROOM_DUST_MAX_ADC_MV, count) == 5500.0);

  // Timing alone, so the task can tell a zero reading from a timing overrun.
  assert(dustTimingAccepted(300, 340));
  assert(!dustTimingAccepted(301, 320));
  assert(!dustTimingAccepted(280, 341));

  // Input at zero: the window fails and more than half of all samples read 0.
  assert(dustInputAtZero(0, 300, 300));      // Every sample read 0.
  assert(dustInputAtZero(99, 101, 101));     // 101 of 200: above half.
  assert(!dustInputAtZero(99, 101, 100));    // 100 of 200: exactly half.
  assert(!dustInputAtZero(0, 0, 0));         // No samples: the task is not running.
  assert(!dustInputAtZero(0, 300, 0));       // All rejected for timing.
  assert(!dustInputAtZero(99, 0, 0));        // Too few samples, none zero.
  assert(!dustInputAtZero(150, 150, 150));   // Passing window, although half read 0.
  assert(!dustInputAtZero(100, 100, 100));   // Passing window at both limits.
  // No uint32_t overflow in zeroRejected * 2 or count + rejected.
  assert(dustInputAtZero(0, 0xFFFFFFFFu, 0x80000000u));
  assert(!dustInputAtZero(0, 0xFFFFFFFFu, 0x7FFFFFFFu));
  assert(!dustInputAtZero(1, 0xFFFFFFFFu, 0x80000000u));  // 2^32 of 2^32: exactly half.

  // LED logic level (true = HIGH). Active low: on is LOW, off is HIGH.
  static_assert(!dustLedLevel(true, true), "on, active low: LOW");
  assert(!dustLedLevel(true, true));
  assert(dustLedLevel(false, true));
  // Active high (NPN low-side driver): on is HIGH, off is LOW.
  assert(dustLedLevel(true, false));
  assert(!dustLedLevel(false, false));
  return 0;
}
