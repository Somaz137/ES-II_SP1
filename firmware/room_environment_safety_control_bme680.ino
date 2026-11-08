// Room Environment Safety Control: experimental BSEC LP acquisition.
// Reference APIs: BSEC2 1.10.2610 and BME68x wrapper v1.3.40408.
// Installed toolchain compatibility and hardware remain unverified.
// USB 115200; I2C SDA21/SCL22. Confirm supply in bsec_board_config.h.
#include <Wire.h>
#include <bsec2.h>
#include "bsec_board_config.h"
#include "bsec_serial_format.h"

const uint8_t roomBsecConfig[] = {
#if ROOM_BME680_SUPPLY_MV == 3300
#include "config/bme680/bme680_iaq_33v_3s_4d/bsec_iaq.txt"
#elif ROOM_BME680_SUPPLY_MV == 1800
#include "config/bme680/bme680_iaq_18v_3s_4d/bsec_iaq.txt"
#else
  0 // The board-config header reports the required configuration error.
#endif
};

Bsec2 roomSensor;
bool roomConfigured = false;
bool roomErrorSent = false;
unsigned long roomLastErrorAt = 0;
unsigned long roomLastMeasurementAt = 0;
const char* roomStartupError = "bsec_initialization_failed";

// All call sites use constant protocol-safe diagnostics, not arbitrary text.
void reportRoomError(const char* message) {
  const unsigned long now = millis();
  if (roomErrorSent && now - roomLastErrorAt < ROOM_LP_INTERVAL_MS) return;
  Serial.print("{\"type\":\"error\",\"message\":\"");
  Serial.print(message);
  Serial.print("\",\"bsec_code\":");
  Serial.print(static_cast<int>(roomSensor.status));
  Serial.print(",\"sensor_code\":");
  Serial.print(static_cast<int>(roomSensor.sensor.status));
  Serial.println("}");
  roomLastErrorAt = now;
  roomErrorSent = true;
}

int roomStatusValue(float signal, int maximum) {
  if (!std::isfinite(signal) || signal < 0 || signal > maximum ||
      std::floor(signal) != signal) return -1;
  return static_cast<int>(signal);
}

void receiveRoomSample(const bme68xData data, const bsecOutputs outputs,
                       const Bsec2 bsec) {
  if (bsec.status != BSEC_OK || bsec.sensor.status < BME68X_OK) {
    reportRoomError("bsec_output_error");
    return;
  }
  const uint8_t required = BME68X_GASM_VALID_MSK | BME68X_HEAT_STAB_MSK;
  if ((data.status & required) != required) {
    reportRoomError("gas_conversion_invalid");
    return;
  }

  RoomSample sample;
#ifdef BME68X_USE_FPU
  sample.temp_c = data.temperature;
  sample.humidity_pct = data.humidity;
#else
  sample.temp_c = data.temperature / 100.0;
  sample.humidity_pct = data.humidity / 1000.0;
#endif
  // Wrapper run() already converts callback pressure to hPa.
  // Recheck this contract if the approved wrapper version differs.
  sample.pressure_hpa = data.pressure;
  sample.gas_ohms = data.gas_resistance;
  sample.stabilization = -1;
  sample.run_in = -1;
  sample.accuracy = -1;
  if (outputs.nOutputs > 0) {
    const int64_t cycleTime = outputs.output[0].time_stamp;
    for (uint8_t i = 0; i < outputs.nOutputs; ++i) {
      const bsecData& value = outputs.output[i];
      if (value.time_stamp != cycleTime) continue;
      switch (value.sensor_id) {
        case BSEC_OUTPUT_STABILIZATION_STATUS:
          sample.stabilization = roomStatusValue(value.signal, 1);
          break;
        case BSEC_OUTPUT_RUN_IN_STATUS:
          sample.run_in = roomStatusValue(value.signal, 1);
          break;
        case BSEC_OUTPUT_IAQ:
          sample.accuracy = value.accuracy <= 3 ? value.accuracy : -1;
          break;
        default: break;
      }
    }
  }

  char record[320];
  if (!formatRoomReading(record, sizeof(record), sample)) {
    reportRoomError("measurement_serialization_failed");
    return;
  }
  Serial.println(record);
  roomLastMeasurementAt = millis();
  roomErrorSent = false;
}

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);
  if (!roomSensor.begin(BME68X_I2C_ADDR_LOW, Wire) &&
      !roomSensor.begin(BME68X_I2C_ADDR_HIGH, Wire)) {
    reportRoomError(roomStartupError);
    return;
  }
  if (!roomSensor.setConfig(roomBsecConfig)) {
    roomStartupError = "bsec_configuration_failed";
    reportRoomError(roomStartupError);
    return;
  }
  bsecSensor requested[] = {
    BSEC_OUTPUT_RAW_TEMPERATURE, BSEC_OUTPUT_RAW_PRESSURE,
    BSEC_OUTPUT_RAW_HUMIDITY, BSEC_OUTPUT_RAW_GAS,
    BSEC_OUTPUT_IAQ, BSEC_OUTPUT_STABILIZATION_STATUS,
    BSEC_OUTPUT_RUN_IN_STATUS
  };
  if (!roomSensor.updateSubscription(requested, ARRAY_LEN(requested),
                                     BSEC_SAMPLE_RATE_LP)) {
    roomStartupError = "bsec_subscription_failed";
    reportRoomError(roomStartupError);
    return;
  }
  roomSensor.attachCallback(receiveRoomSample);
  roomLastMeasurementAt = millis();
  roomConfigured = true;
}

void loop() {
  if (!roomConfigured) {
    reportRoomError(roomStartupError);
    return;
  }
  // BSEC decides when to acquire. Do not add a three-second delay here.
  if (!roomSensor.run()) {
    reportRoomError("bsec_measurement_failed");
  }
  if (millis() - roomLastMeasurementAt >= ROOM_NO_MEASUREMENT_MS) {
    reportRoomError("bsec_measurement_unavailable");
  }
}
