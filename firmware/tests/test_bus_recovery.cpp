// Host test for the I2C bus restart rule. Build on Linux with
// g++ -std=c++11 -Wall -Wextra -pedantic firmware/tests/test_bus_recovery.cpp
#include "../bus_recovery.h"
#include <cassert>
#include <cstdint>
#include <cstdio>

int main() {
  assert(ROOM_BUS_RESTART_AFTER_MS == 10000);
  assert(ROOM_BUS_RESTART_INTERVAL_MS == 30000);

  // Never restarted: due 10000 ms after the last good reading, not before.
  assert(!roomBusRestartDue(9999, 0, 0, false));
  assert(roomBusRestartDue(10000, 0, 0, false));
  assert(!roomBusRestartDue(5000 + 9999, 5000, 0, false));
  assert(roomBusRestartDue(5000 + 10000, 5000, 0, false));

  // Restarted and still failing: the next restart waits 30000 ms.
  const uint32_t good = 1000;
  const uint32_t restart = good + 10000;
  assert(!roomBusRestartDue(restart + 20000, good, restart, true));
  assert(!roomBusRestartDue(restart + 29999, good, restart, true));
  assert(roomBusRestartDue(restart + 30000, good, restart, true));

  // A good reading after the restart: not due until 10000 ms after it,
  // even when the restart interval has passed.
  const uint32_t goodAfter = restart + 25000;
  assert(!roomBusRestartDue(restart + 30000, goodAfter, restart, true));
  assert(roomBusRestartDue(goodAfter + 10000, goodAfter, restart, true));

  // millis() wrap-around: decided by the elapsed time.
  const uint32_t nearEnd = UINT32_MAX - 4999;  // 5000 ms before the wrap.
  assert(!roomBusRestartDue(4999, nearEnd, 0, false));  // 9999 ms elapsed.
  assert(roomBusRestartDue(5000, nearEnd, 0, false));   // 10000 ms elapsed.
  const uint32_t restartNearEnd = UINT32_MAX - 9999;   // 10000 ms before the wrap.
  assert(!roomBusRestartDue(19999, nearEnd - 30000, restartNearEnd, true));  // 29999 ms.
  assert(roomBusRestartDue(20000, nearEnd - 30000, restartNearEnd, true));   // 30000 ms.

  std::puts("test_bus_recovery: all passed");
  return 0;
}
