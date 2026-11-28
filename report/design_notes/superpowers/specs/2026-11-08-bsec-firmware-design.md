# BSEC firmware design

User approved BSEC integration, LP sampling every three seconds and inline continuation with fewer checkpoints. Prepare source only. Installation, compilation, tests, flashing and hardware operation remain deferred to Linux.

## Interfaces

Keep USB serial 115200, I2C SDA21/SCL22 and address fallback 0x76 then 0x77. Bsec2.run() is called frequently and owns the three-second LP sampling schedule. Do not use a three-second sleep or print repeated cached measurements as new records.

Subscribe to raw temperature, pressure, humidity and gas, IAQ (for its accuracy only), stabilization and run-in. Each callback constructs a new sample and resets status fields to unknown. Extract status outputs only for the callback's current timestamp. Serialize all four valid scalar measurements plus bsec integer statuses, or null for missing/invalid statuses. IAQ values and equivalent gas concentrations are not added.

Source inspection of BSEC2 wrapper 1.10.2610 shows run() multiplies raw pressure by 0.01 before callback. Use callback data.pressure directly as hPa. Convert fixed-point temperature/humidity only when BME68X_USE_FPU is absent. This is version-sensitive and must be checked against the approved installed release and real readings before use. A matching version is not yet an approved installed toolchain.

Reject nonfinite measurements and gas-invalid/heater-unstable conversions as recognized error messages. Expected long BSEC warm-up flags zero still permit valid raw measurements, without a sensor error. Preserve provisional gas status.

Failures must not halt indefinitely or emit arbitrary log text into the serial protocol. Failed initialization/config/subscription produces periodic type=error records. Runtime run() failure also produces rate-limited errors and continues calls. If the wrapper returns success but produces no valid measurement for two LP periods, emit measurement-unavailable errors every three seconds. This is a firmware reporting watchdog, not a new host alert timeout. Existing Python fault timeouts remain 120 seconds.

No automatic sensor reinitialization, state persistence, custom temperature offset, indicator pins or extra library installation. A failed initialization requires intervention/restart, as in the earlier starter. Python restart does not restart ESP32 by design, but opening a serial port can reset some boards and must be checked on Linux.

## Configuration and dependency boundary

Exact ESP32/core/library versions and physical sensor supply are not established by the available course manuals. Source references BSEC2 1.10.2610 and BME68x wrapper v1.3.40408 as candidates only. Do not install/upgrade them without the user's agreement. Preserve Arduino IDE 2.3.10 and the Python requirements pins.

A local firmware configuration header deliberately requires confirmation of the sensor die supply: 1800 or 3300 mV. Its initial value zero stops compilation with a clear message. The value is the BME680 supply, not automatically the breakout VIN. Include the matching Bosch bme680_iaq_[18v/33v]_3s_4d configuration from the installed library, rather than vendoring a Bosch binary/configuration blob. Four-day baseline history matches the inspected standard profile, not a four-day warm-up requirement.

## Files

- Existing .ino: BSEC setup, callback collection and loop/error reporting.
- firmware/bsec_board_config.h: explicit unconfirmed supply and LP reporting constants.
- firmware/bsec_serial_format.h: portable scalar/status JSON formatter, independent of Arduino and BSEC.
- firmware/tests/test_bsec_serial_format.cpp: host C++ behavior tests, written before implementation, unexecuted.
- tests/fixtures/bsec_reading.json: agreed example wire record, used by a real parser/router test. This fixture is not claimed as observed firmware output.
- firmware/README.md: candidate dependencies, configuration boundary, deferred Linux verification and upstream references.

## Reference and limitations

Upstream APIs inspected at https://github.com/boschsensortec/Bosch-BSEC2-Library/tree/1.10.2610 and https://github.com/boschsensortec/Bosch-BME68x-Library/tree/v1.3.40408 . This implementation uses public APIs without copying the upstream example body or redistribution of the proprietary algorithm/config blobs. VIGIL has no equivalent ESP32 gas pipeline. Shared principle: keep input handling separate from dashboard decisions.
