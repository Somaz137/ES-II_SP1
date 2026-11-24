#pragma once

// I2C bus restart rule for the BME680. Pure C++11: no Arduino dependency.
// firmware/tests/test_bus_recovery.cpp checks it.
//
// Measured 25 November 2026: the bus stopped answering after the first
// bme68x_init (rc -2 for about 27 s), and Wire.end() + Wire.begin() restored
// it at once. The sketch restarts the bus by elapsed time with this rule.
// The constants are here, not in bsec_board_config.h, so the host test can
// include them (that header requires an ESP32-S3 build).

#include <cstdint>

// No valid reading for this long starts a restart: more than three LP
// intervals of 3 s.
constexpr uint32_t ROOM_BUS_RESTART_AFTER_MS = 10000;
// While the readings stay missing, at most one restart in this time.
constexpr uint32_t ROOM_BUS_RESTART_INTERVAL_MS = 30000;

// True when a bus restart is due. lastGoodMs is the time of the last valid
// reading (or of the last sensor start), lastRestartMs the time of the last
// restart, restartedOnce false until the first restart. Unsigned subtraction
// keeps the rule right across the millis() wrap.
inline bool roomBusRestartDue(uint32_t now, uint32_t lastGoodMs, uint32_t lastRestartMs,
                              bool restartedOnce) {
  if (static_cast<uint32_t>(now - lastGoodMs) < ROOM_BUS_RESTART_AFTER_MS) return false;
  return !restartedOnce ||
         static_cast<uint32_t>(now - lastRestartMs) >= ROOM_BUS_RESTART_INTERVAL_MS;
}
