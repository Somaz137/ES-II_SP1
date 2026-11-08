#pragma once

// Target: DOIT ESP32 DEVKIT V1 with the classic ESP32 chip.
// The chip check cannot identify the physical development board.
#if !defined(ARDUINO_ARCH_ESP32) || !defined(CONFIG_IDF_TARGET_ESP32)
#error "Select DOIT ESP32 DEVKIT V1 with the classic ESP32 chip."
#endif

constexpr int ROOM_I2C_SDA_PIN = 21;
constexpr int ROOM_I2C_SCL_PIN = 22;
constexpr unsigned long ROOM_SERIAL_BAUD = 115200;

// User confirmed a 3.3 V sensor supply on 8 November 2026.
// This value selects the matching Bosch sensor configuration.
#ifndef ROOM_BME680_SUPPLY_MV
#define ROOM_BME680_SUPPLY_MV 3300
#endif
#if ROOM_BME680_SUPPLY_MV != 1800 && ROOM_BME680_SUPPLY_MV != 3300
#error "Confirm BME680 supply, then set ROOM_BME680_SUPPLY_MV to 1800 or 3300."
#endif

constexpr unsigned long ROOM_LP_INTERVAL_MS = 3000;
constexpr unsigned long ROOM_NO_MEASUREMENT_MS = 2 * ROOM_LP_INTERVAL_MS;
