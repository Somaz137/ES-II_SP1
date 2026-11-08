# Technical alert configuration design

Approved scope: the learner selected "implement this step" on 8 November 2026 after the implementation checkpoint.

## Goal and constraints

- Current prototype: one room, one BME680, one camera, ESP32-to-laptop USB serial.
- Keep configuration loading and validation in separate Python files with focused functions.
- A dedicated config/alerts.yaml stores communication_timeout_s and sensor_error_timeout_s, initially 120 seconds each.
- Technical settings are loaded once during startup. The caller retains the returned settings; a later file edit does not mutate that snapshot.
- Patient-profile live updates are a separate future feature.
- Use PyYAML==6.0.1 and pytest==8.2.0 from existing requirements; target Python 3.10, with the recorded Ubuntu environment at 3.10.12.
- Existing fault lifecycle decisions remain unchanged; this step does not implement timers, serial handling, patient profiles or dashboard features.

## Approach and interfaces

Reuse VIGIL's startup yaml.safe_load pattern, with validation separated for readability and testing. The approved startup approach avoids changing active technical timers during file edits; live technical reloading is out of scope.

- config_loader.load_alert_settings(path): read UTF-8 YAML, validate it, return its settings mapping.
- config_validation.validate_alert_settings(data): raise ValueError for a non-mapping, missing required timeout, or invalid timeout. Both durations must be finite positive int/float values; booleans and numeric strings are invalid.
- Missing/unreadable files retain native filesystem errors. Malformed YAML raises ValueError with the path.
- Extra settings are preserved without assigning meaning; only the two selected timeout fields are consumed by this feature.

## Verification

Real-file pytest cases cover independent values, retained snapshots, absent/invalid settings, malformed YAML and missing files. Run the project suite in the pinned environment. Do not substitute a different interpreter or dependency version without the learner's agreement.

