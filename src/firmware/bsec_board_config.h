#pragma once

// Target: ESP32-S3 with 16 MB quad flash and 8 MB embedded PSRAM (N16R8-type module),
// read from the connected board by esptool on 17 November 2026.
// The chip check cannot identify the physical development board or its memory.
#if !defined(ARDUINO_ARCH_ESP32) || !defined(CONFIG_IDF_TARGET_ESP32S3)
#error "Select an ESP32-S3 board (esp32:esp32:esp32s3). This firmware targets the ESP32-S3 (developed on an N16R8-type module)."
#endif

// Board pins decided by the user on 15 November 2026.
// Not yet checked against the physical board: see firmware/README.md.
constexpr int ROOM_I2C_SDA_PIN = 8;
constexpr int ROOM_I2C_SCL_PIN = 9;
// The dust pins were swapped to match the user's wiring on 20 November 2026.
constexpr int ROOM_DUST_ADC_PIN = 5;    // ADC1 channel 4.
constexpr int ROOM_DUST_LED_PIN = 4;    // Drives sensor pin 3 (LED); see below.
// Measured 25 November 2026: GPIO4 drives sensor pin 3 directly, so the LED is
// on when GPIO4 is LOW. Set false for the NPN low-side driver of
// report/design_notes/SHARP_DUST_INTEGRATION.md (LED on when GPIO4 is HIGH).
constexpr bool ROOM_DUST_LED_ACTIVE_LOW = true;
// Alarm LED: the onboard RGB LED (user decision, 20 November 2026; no external LED).
// LED_BUILTIN is GPIO48 on the default ESP32-S3 variant. digitalWrite HIGH lights it
// white and LOW turns it off, through the core's RGB LED support.
// Not checked on the board: some ESP32-S3 DevKitC-1 v1.1 boards have the RGB LED on
// GPIO38, and some clone boards need the "RGB" solder pad closed.
constexpr int ROOM_ALARM_LED_PIN = LED_BUILTIN;
// No buzzer is connected at present (20 November 2026), so GPIO7 drives nothing.
constexpr int ROOM_BUZZER_PIN = 7;      // Signal input of the 3-pin buzzer module.

// Buzzer module trigger level. UNVERIFIED: the module may be active high or
// active low. Check it on the real part before relying on the alarm.
// true: HIGH sounds. A wrong value inverts the buzzer, so it sounds at level 0.
constexpr bool ROOM_BUZZER_ACTIVE_HIGH = true;

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
// The I2C bus restart times (ROOM_BUS_RESTART_AFTER_MS, 10 s, and
// ROOM_BUS_RESTART_INTERVAL_MS, 30 s) are in bus_recovery.h, so its host test
// can include them without this ESP32-S3-only header.

// Serial bytes read for alarm commands in one loop pass. A command is 8 or 9
// bytes. The rest stays in the driver's receive buffer for the next pass.
constexpr unsigned ROOM_ALARM_MAX_BYTES_PER_PASS = 64;

// With no valid alarm command for this long, the alarm LED blinks (on and off
// for ROOM_ALARM_BLINK_HALF_PERIOD_MS each). The buzzer keeps its last state.
constexpr unsigned long ROOM_ALARM_LINK_TIMEOUT_MS = 30000;
constexpr unsigned long ROOM_ALARM_BLINK_HALF_PERIOD_MS = 1000;
static_assert(ROOM_ALARM_BLINK_HALF_PERIOD_MS > 0,
              "The blink half period divides the elapsed time; it must not be 0");

// The board sends its BSEC state to the host at IAQ accuracy 3: once when it
// first reaches 3 after start, then at this interval while it stays 3.
// Bosch's standard interval, from Bosch's example basic_config_state.ino (STATE_SAVE_PERIOD, 360 minutes). User decision, 20 November 2026.
constexpr unsigned long ROOM_BSEC_STATE_SAVE_MS = 360UL * 60UL * 1000UL;

// After a failed getState the board waits this long before it tries again,
// so a lasting fault sends one bsec_state_save_failed line a minute.
constexpr unsigned long ROOM_BSEC_STATE_RETRY_MS = 60000;

// At start the board asks the host for the saved BSEC state, then waits this
// long for a BSEC_STATE line. With no reply it runs without a state.
constexpr unsigned long ROOM_BSEC_STATE_WAIT_MS = 10000;
