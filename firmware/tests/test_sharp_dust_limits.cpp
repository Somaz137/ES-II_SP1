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
  return 0;
}
