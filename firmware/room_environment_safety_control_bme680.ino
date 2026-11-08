// Room Environment Safety Control ESP32 sensor test (NOT a complete safety-monitoring application)
// Target: ESP32 DevKit V1, Arduino-ESP32 core, Adafruit BME680 Library.
// I2C: GPIO21 SDA, GPIO22 SCL. USB serial: 115200 baud.
// Emits JSON lines (one per second). Gas resistance is raw Ohms, NOT an AQI/CO2 value.
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME680.h>

Adafruit_BME680 bme;
bool sensorReady = false;
unsigned long lastReading = 0;

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);
  sensorReady = bme.begin(0x76);
  if (!sensorReady) sensorReady = bme.begin(0x77);
  if (sensorReady) {
    bme.setTemperatureOversampling(BME680_OS_8X);
    bme.setHumidityOversampling(BME680_OS_2X);
    bme.setPressureOversampling(BME680_OS_4X);
    bme.setIIRFilterSize(BME680_FILTER_SIZE_3);
    bme.setGasHeater(320, 150);
  }
}

void loop() {
  if (millis() - lastReading < 1000) return;
  lastReading = millis();

  if (!sensorReady) {
    Serial.println("{\"type\":\"error\",\"message\":\"bme680_not_found\"}");
    return;
  }
  if (!bme.performReading()) {
    Serial.println("{\"type\":\"error\",\"message\":\"sensor_read_failed\"}");
    return;
  }
  Serial.print("{\"type\":\"reading\",\"temp_c\":");
  Serial.print(bme.temperature, 2);
  Serial.print(",\"humidity_pct\":");
  Serial.print(bme.humidity, 2);
  Serial.print(",\"pressure_hpa\":");
  Serial.print(bme.pressure / 100.0, 2);
  Serial.print(",\"gas_ohms\":");
  Serial.print(bme.gas_resistance);
  Serial.println("}");
}
