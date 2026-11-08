# VIGIL and Room Environment Safety Control

Updated: 8 November 2026.

## Evidence and scope

This comparison uses the original uploaded `Module_3.4_Healthcare_Case_Study_1_v0.8.pdf`, read directly on 8 November 2026 (pp. 3-7 and 9-17), the repository's extracted course reference, and the user's confirmed design decisions. The original `vigil_v0.8.zip` was located, but download failed because of a network/DNS restriction. Its Python source has not been inspected in this session. Do not infer undocumented implementation details from this comparison.

The project's current name is **Room Environment Safety Control**. The course's original title and SAFE-ROOM codename remain historical source facts. No environmental actuator or closed-loop control has been selected merely by renaming the project.

## Comparison

| Area | VIGIL, as documented in Module 3.4 | Our requirements or confirmed decisions |
|---|---|---|
| Purpose | Dementia-patient bed-position and bed-exit monitoring (pp. 3-5) | Occupied-room environmental monitoring for patient-specific limits |
| Hardware | Jetson Orin Nano, camera, optional GPIO alarms (p. 5) | Ubuntu 22.04 laptop plus ESP32/BME680 and webcam; development currently from Windows |
| Camera role | MediaPipe body landmarks, bed calibration and seven posture-related states (pp. 4-5, 9-10) | Occupancy input; exact method remains undecided, no new vision dependency selected |
| Alarm filtering | Eight consecutive frames; 60-second per-type cooldown; FALL bypasses cooldown (p. 5) | Separate 120-second communication and sensor-error waits. Environmental breach duration remains undecided |
| Communication fault | Manual documents dashboard offline indication (pp. 11-12); exact timeout and lifecycle need ZIP inspection | Recognized ESP32 messages reset communication timing; alert requires acknowledgment; acknowledgment during silence starts another 120-second wait |
| Sensor errors | BME680 serial errors are not part of the manual's described posture pipeline | Error messages maintain communication but begin/continue a separate sensor fault; a valid measurement resets its timer and clears its alert |
| Configuration | Adjustable values in config.yaml (p. 9) | Dedicated YAML timeout settings, initially 120 seconds each; restart versus live application remains undecided |
| Dashboard | Patient state, health/offline warning, recent log, alarms and acknowledgment (pp. 11-12) | Live environmental readings, last successful measurement time, distinct fault states, editable patient limits, 24-hour trends and event history; most still unimplemented |
| Program separation | Monitor owns camera; Flask dashboard reads monitoring data from SQLite (pp. 3, 11-12, 15) | Use that separation as the course-reference pattern; keep our Python responsibilities in small focused modules |
| Testing | Synthetic camera-free posture and alarm tests, 18 checks described (p. 17) | Hardware-free tests for communication, sensor errors and alert lifecycle, followed by environmental rules and separate real-hardware verification |
| Deployment | Gunicorn, systemd and Cloudflare tunnel (pp. 12-17) | No tunnel, public exposure, or auto-start selected; do not run VIGIL installer unchanged |

## Code reuse authorized by the user

The user explicitly permits using VIGIL code snippets as a reference and adapting suitable snippets. Candidate areas are YAML handling, SQLite access, Flask/data boundaries, alert bookkeeping and hardware-free test structure. These are candidates, not inspected or copied source in this session.

Before adapting a snippet, inspect its original file and dependencies, explain its role and any difference from our confirmed behavior, then preserve the course-pinned versions. Record origin at file/function level when adapting code. Existing user decisions override VIGIL defaults.

Do not copy posture thresholds, bed calibration, Jetson setup or GPIO assumptions into the environmental monitor. Exact VIGIL acknowledgment/repeat behavior and whether its application supports live config reload remain unverified until its source is readable; a generic systemctl reload table does not prove application reload support.

## Next open decision

When should edits to the timeout YAML take effect: only at program restart, or during monitoring? This remains open; permission to reuse snippets does not settle it.
