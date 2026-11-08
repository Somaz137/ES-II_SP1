#pragma once

// Confirm sensor die supply, which can differ from breakout VIN.
#ifndef ROOM_BME680_SUPPLY_MV
#define ROOM_BME680_SUPPLY_MV 0
#endif
#if ROOM_BME680_SUPPLY_MV != 1800 && ROOM_BME680_SUPPLY_MV != 3300
#error "Confirm BME680 supply, then set ROOM_BME680_SUPPLY_MV to 1800 or 3300."
#endif

constexpr unsigned long ROOM_LP_INTERVAL_MS = 3000;
constexpr unsigned long ROOM_NO_MEASUREMENT_MS = 2 * ROOM_LP_INTERVAL_MS;
