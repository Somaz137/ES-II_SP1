# Serial runtime implementation and Linux verification

## Implemented source

- [x] Separate transport, runtime settings, loop, output and thin CLI.
- [x] Bounded newline framing and retry without resetting monitor state.
- [x] Monotonic fault timing and five-second periodic checks during silence.
- [x] Preserve last measurement and mask unavailable gas statuses.
- [x] Write hardware-free tests and update Linux/human documentation.
- [ ] Run full pinned pytest on the user's Linux environment.
- [ ] Verify imports, serial operation, units, real timing, disconnect/reconnect and cleanup.

## Linux procedure

1. Preserve local work. Fetch and select codex/serial-runtime, or its merged successor, after inspecting branch state. It builds on PR #8; do not assume main has these files.
2. Use the existing Ubuntu env and verify its recorded Python/package pins. Do not reinstall automatically.
3. From the root run python3 -m pytest. There are eleven Python test files, plus the separate firmware C++ tests. Record actual results and versions. All remain unrun at source preparation.
4. Establish firmware status before interpreting gas metadata. Old firmware can test environmental routing but reports unknown gas readiness. New BSEC source requires approved exact dependencies and sensor supply, real compilation and flashing as a separate authorized procedure.
5. Identify the actual ESP32 port. Close Arduino Serial Monitor and tools/read_sensor.py before opening it here. Run python3 monitor.py --port /dev/ttyUSB0 only if that is the verified device; otherwise substitute the actual path.
6. Verify initial empty values, complete records, estimated UTC timestamp, raw units, gas metadata and error records. Output is terminal JSON, not a dashboard or a room-safety decision.
7. Disconnect USB and confirm monitor stays running, retains values/time, and reports communication loss after the configured duration on the next check. Reconnect at the same device path and verify real new packets restore communication without clearing its acknowledgment latch or changing old receipt time before a new complete record.
8. Verify errors keep communication alive but trigger sensor fault after 120 seconds; a complete reading clears that sensor fault. Exercise sensor pause/resume using fake-clock tests before hardware fault experiments. Do not unplug/reconnect live sensor wires without an agreed electrical procedure.
9. Ctrl+C must close the port. No runtime acknowledgment interface exists yet. Record this limit and actual findings; do not label the full project complete.

Next work: patient-profile format and limits, occupancy method, environmental rules, SQLite history/control, dashboard with acknowledgment, notifications and end-to-end validation. Firmware dependency/supply confirmation and all hardware verification remain pending. Do not automatically merge this draft.
