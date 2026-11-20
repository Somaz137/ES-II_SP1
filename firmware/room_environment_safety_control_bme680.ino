// Room Environment Safety Control: experimental BSEC LP acquisition.
// Target: ESP32-S3 with 16 MB flash and 8 MB PSRAM (N16R8-type module). Local LED and buzzer alarm.
// Compiled with ESP32 core 3.3.12, BSEC2 1.10.2610 and BME68x 1.3.40408.
// Hardware operation remains unverified.
// Board pins, serial speed and confirmed supply: bsec_board_config.h.
//
// Only the loop task writes Serial (loop(), reportDust(), reportRoomError()
// and the BSEC callback, which runs inside roomSensor.run()). The dust task
// never writes it. Output lines therefore never interleave. Keep it so.
#include <Wire.h>
#include "bsec_board_config.h"
#include <bsec2.h>
#include "bsec_serial_format.h"
#include "sharp_dust.h"
#include "alarm_command.h"

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
// Last IAQ accuracy from the BSEC callback, 0 to 3. Read by loop() for the
// state save.
uint8_t roomIaqAccuracy = 0;
bool roomStateSavedOnce = false;
uint32_t roomLastStateSaveMs = 0;

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
  sample.iaq = NAN;
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
          roomIaqAccuracy = value.accuracy <= 3 ? value.accuracy : 0;
          // Bosch's index, 0 to 500. The formatter prints null when unusable.
          sample.iaq = value.signal;
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

AlarmLineReader roomAlarmReader;
int roomAlarmLevel = 0;
uint32_t roomLastCommandMs = 0;
AlarmOutputs roomWrittenOutputs = {false, false};
bool roomOutputsWritten = false;  // False until the first pin write.

// The only place the alarm pins are written. Writes only when the outputs
// change, and always on the first call.
void refreshAlarmOutputs() {
  const uint32_t now = millis();
  const bool lost = alarmLinkLost(now, roomLastCommandMs, ROOM_ALARM_LINK_TIMEOUT_MS);
  const AlarmOutputs outputs =
      alarmOutputsAt(roomAlarmLevel, lost, now, ROOM_ALARM_BLINK_HALF_PERIOD_MS);
  if (roomOutputsWritten && outputs.led == roomWrittenOutputs.led &&
      outputs.buzzer == roomWrittenOutputs.buzzer) return;
  digitalWrite(ROOM_ALARM_LED_PIN, outputs.led ? HIGH : LOW);
  digitalWrite(ROOM_BUZZER_PIN,
               alarmDriveLevel(outputs.buzzer, ROOM_BUZZER_ACTIVE_HIGH) ? HIGH : LOW);
  roomWrittenOutputs = outputs;
  roomOutputsWritten = true;
}

void sendAlarmReply(int level) {
  char reply[32];
  if (formatAlarmReply(reply, sizeof(reply), level)) Serial.println(reply);
}

// Called only for a valid command, so only a valid command resets the link timer.
void applyAlarmLevel(int level) {
  roomAlarmLevel = level;
  roomLastCommandMs = millis();
  refreshAlarmOutputs();
  sendAlarmReply(level);
}

// Prints the BSEC library version as major.minor.major_bugfix.minor_bugfix.
// roomSensor.version is set by roomSensor.begin().
void printBsecVersion() {
  Serial.print(static_cast<unsigned>(roomSensor.version.major));
  Serial.print('.');
  Serial.print(static_cast<unsigned>(roomSensor.version.minor));
  Serial.print('.');
  Serial.print(static_cast<unsigned>(roomSensor.version.major_bugfix));
  Serial.print('.');
  Serial.print(static_cast<unsigned>(roomSensor.version.minor_bugfix));
}

// Asks the host for the saved BSEC state and waits up to
// ROOM_BSEC_STATE_WAIT_MS for one BSEC_STATE line. ALARM lines are applied
// during the wait. Call after setConfig and before updateSubscription, the
// order of Bosch's example basic_config_state.ino. The wait reads through the
// alarm reader's HostLineReader, so a line cut by the end of the wait goes on
// in loop().
void restoreBsecState() {
  Serial.print("{\"type\":\"bsec_state_request\",\"bsec_version\":\"");
  printBsecVersion();
  Serial.println("\"}");
  const uint32_t start = millis();
  while (static_cast<uint32_t>(millis() - start) < ROOM_BSEC_STATE_WAIT_MS) {
    unsigned used = 0;
    while (used < ROOM_ALARM_MAX_BYTES_PER_PASS && Serial.available() > 0) {
      const int c = Serial.read();
      if (c < 0) break;
      ++used;
      const HostCommand command = roomAlarmReader.host.feed(static_cast<char>(c));
      if (command.kind == ROOM_HOST_ALARM) {
        applyAlarmLevel(command.level);
      } else if (command.kind == ROOM_HOST_BSEC_NONE) {
        return;
      } else if (command.kind == ROOM_HOST_BSEC_STATE) {
        // Bsec2::setState passes BSEC_MAX_STATE_BLOB_SIZE bytes to BSEC, so
        // the bytes after the received state are zero.
        static uint8_t state[BSEC_MAX_STATE_BLOB_SIZE];
        memset(state, 0, sizeof(state));
        memcpy(state, command.state, command.stateLength);
        const bool ok = roomSensor.setState(state);
        Serial.print("{\"type\":\"bsec_state_restored\",\"ok\":");
        Serial.print(ok ? "true" : "false");
        Serial.println("}");
        return;
      }
    }
    refreshAlarmOutputs();
    delay(1);
  }
}

// Sends the BSEC state to the host when bsecShouldSave allows it. Called from
// loop(), outside the BSEC callback. Bsec2::getState does not report the
// state length, so all BSEC_MAX_STATE_BLOB_SIZE bytes are sent.
void saveBsecState() {
  const uint32_t now = millis();
  if (!bsecShouldSave(roomIaqAccuracy, roomStateSavedOnce, now, roomLastStateSaveMs,
                      ROOM_BSEC_STATE_SAVE_MS)) return;
  static uint8_t state[BSEC_MAX_STATE_BLOB_SIZE];
  static char hex[2 * BSEC_MAX_STATE_BLOB_SIZE + 1];
  if (!roomSensor.getState(state) ||
      !formatStateHex(state, sizeof(state), hex, sizeof(hex))) {
    // Tried again on the next pass; reportRoomError limits the error lines.
    reportRoomError("bsec_state_save_failed");
    return;
  }
  Serial.print("{\"type\":\"bsec_state\",\"accuracy\":");
  Serial.print(static_cast<unsigned>(roomIaqAccuracy));
  Serial.print(",\"bsec_version\":\"");
  printBsecVersion();
  Serial.print("\",\"state\":\"");
  Serial.print(hex);
  Serial.println("\"}");
  roomStateSavedOnce = true;
  roomLastStateSaveMs = now;
}

void setup() {
  roomLastCommandMs = millis();
  // Alarm outputs off before anything slow runs.
  pinMode(ROOM_ALARM_LED_PIN, OUTPUT);
  pinMode(ROOM_BUZZER_PIN, OUTPUT);
  refreshAlarmOutputs();
  Serial.begin(ROOM_SERIAL_BAUD);
  // Tell the host the board restarted at level 0.
  sendAlarmReply(0);
  beginDust();
  Wire.begin(ROOM_I2C_SDA_PIN, ROOM_I2C_SCL_PIN);
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
  restoreBsecState();
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
  // Bounded and non-blocking. Runs even when the BME680 failed to start.
  pumpAlarmInput(Serial, roomAlarmReader, ROOM_ALARM_MAX_BYTES_PER_PASS, applyAlarmLevel);
  refreshAlarmOutputs();
  reportDust();
  delay(1);
  if (!roomConfigured) {
    reportRoomError(roomStartupError);
    return;
  }
  // BSEC decides when to acquire. Do not add a three-second delay here.
  if (!roomSensor.run()) {
    reportRoomError("bsec_measurement_failed");
  }
  saveBsecState();
  if (millis() - roomLastMeasurementAt >= ROOM_NO_MEASUREMENT_MS) {
    reportRoomError("bsec_measurement_unavailable");
  }
}
