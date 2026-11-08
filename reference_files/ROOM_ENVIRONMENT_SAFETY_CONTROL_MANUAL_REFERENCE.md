# Room Environment Safety Control / Project 8 — Course-Manual Reference for a Terminal Coding AI

**Current project name:** Room Environment Safety Control (user-selected on 8 November 2026). The original course title and codename below are preserved as source facts, not current branding.

**Purpose:** A source-grounded engineering reference extracted from the user-provided course materials, for an AI assistant working on Project 8. This is **not** a complete reprint of every lecture and **not** permission to install additional software. It concentrates on all material useful to this project, including version constraints, platform decisions, hardware interfaces, commands, reusable code patterns, testing, and omissions.

**Target platform selected by user:** Ubuntu **22.04 LTS laptop (x86-64)** + **ESP32** over USB serial. **Not** an NVIDIA Jetson deployment.  
**Current interpreter confirmed by user:** Python **3.10.12**, inside an activated virtual environment named `env`.  
**Source set:** 10 uploaded lecture PDFs + `vigil_v0.8.zip`. References below use **PDF page numbers (1-indexed)**; the ZIP references are archive-relative paths.  
**Authority:** Only the uploaded materials and user-confirmed facts, **not** current online recommendations.

**Maintenance:** This document preserves extracted course facts and historical user confirmations. Use the companion implementation plan for current progress and decisions. The original PDFs and VIGIL ZIP are not included in this repository.

---

## 0. REQUIRED OPERATING RULES FOR AN AI READING THIS FILE

1. **Use the exact versions in the uploaded course manuals.** Do not upgrade, downgrade, substitute, install or recommend any unlisted version without obtaining the user's approval **before recommending the command**.
2. **Do not introduce installation commands, libraries, runtime services, sensors, algorithms, additional features, or implementation functions that are absent from the manuals without asking first.** A missing specification is a question for the user, not a license to make a default choice.
3. **Never conflate Jetson-specific and Ubuntu laptop instructions.** Ubuntu 22.04 is shared, but `amd64` (laptop) and `arm64` (Jetson) packages, GPIO, OpenCV source, JetPack and GPU frameworks differ.
4. **Separate source facts from project adaptations.** Use labels such as `[MANUAL]`, `[ZIP]`, `[USER CONFIRMED]`, `[PROPOSED — APPROVAL REQUIRED]`, `[UNSPECIFIED]`, or `[EXAMPLE OUTPUT]` when a distinction matters.
5. **Do not run the old Room Environment Safety Control starter setup script automatically.** A previous assistant-created starter archive contains externally selected Arduino ESP32-core/BME680-library versions and additional setup packages that are **not** pinned by the lectures. Those selections are not approved.
6. **If course modules disagree, show both versions and explain the context; do not silently reconcile them.** If a version must be chosen for the user's scope and there is an actual conflict, ask before installing.
7. **Do not treat example values as requirements.** Sample kernel versions, IP addresses, credentials, sensor values, program paths, patient thresholds and figures in lecture outputs are not guaranteed to describe this particular laptop or patient.
8. **No medical claims.** This is an educational demonstration, not a certified safety/clinical monitoring device. Patient-specific safe ranges are not given in the materials and must not be fabricated.
9. **Do not perform irreversible or privileged changes without approval.** Even a command appearing in a manual (e.g., deleting packages, exposing a dashboard, installing services) may be inappropriate unless its stated condition is met and the user approves its application.
10. **Before modifying implementation code**, identify which requirement and source page justify it and what is still not defined by the course.

## 1. Exact assignment and scope

**Primary source:** `Healthcare_Case_Study_Idea_Book_Complete_1-18.pdf`, pp. **21–22**, Case-study idea **8**.

- **Official title:** *Room Environment Safety Monitor*; codename **SAFE-ROOM**; subtitle *Sensing Ambient Factors for Edge-based Room-safety*.
- **Problem:** Vulnerable patients may need individual environmental limits. Monitor an **occupied** room continuously and alert a caregiver when conditions remain outside a particular patient's permitted range.
- **Inputs:** BME680 environment sensor (temperature, humidity, pressure and air-quality information); webcam to confirm occupancy.
- **User configuration:** A clinician-facing form changes **per-patient safe limits** rather than editing program code.
- **Decision requirement:** A breach must **persist for a sustained period**; short spikes must not trigger an alarm. The brief gives a ten-minute alert as an illustrative example, **not a mandated default**.
- **Outputs:** Live room conditions; unambiguous alert messages describing the condition and duration; **24-hour trend chart**; alert/event history.
- **Reliability requirement:** Email/notification/network delivery must be **non-blocking**; a slow notification must not stop sampling, condition checks, or local records.
- **Assessment tasks explicitly listed:** read/display sensor data; change per-patient limits through a form; sustained-breach alert (not noise spike); trend chart and independent notification path.
- **Listed hardware:** NVIDIA Jetson Orin Nano developer kit, **BME680**, USB webcam, optional buzzer or LED. **Project adaptation:** user has selected Ubuntu laptop + ESP32, a pattern taught in Module 3.3. The PDF's project itself depicts a Jetson.
- **Listed software:** Python 3 + **NumPy**, **OpenCV**, **Flask + SQLite**, **PyYAML**, **pytest**.
- **Difficulty/time in book:** easy–medium; 5–6 hours is an educational estimate, not a deadline.
- **Explicit dependency on unavailable course content:** Project 8 says it reuses **Module 4.3** for BME680 and an editable rule engine. Uploaded Module 3.3 also points to **Module 4.2** for reading sensors. **Neither module is provided.** This is a material missing source, not an invitation to invent an implementation.

### Reference architecture derived from the brief and Module 3.3

```text
[BME680: environmental values] --I2C--> [ESP32 DevKit V1]
                                           |
                                           | USB serial, 115200 baud (Module 3.3)
                                           v
  [Webcam via OpenCV] -------------> [Ubuntu 22.04 laptop / Python 3.10]
                                            |
                                            +-- occupancy indicator [algorithm not specified]
                                            +-- per-patient YAML limits + editing form
                                            +-- sustained-breach safety rules
                                            +-- local SQLite history/events
                                            +-- independent alert delivery
                                            +-- Flask dashboard (current, 24h trends, alerts)
                                            +-- optional LED/buzzer via ESP32 [requires approved design]
```

**Important:** This is the project's **adaptation** to the user-selected platform, not a diagram claiming the brief explicitly shows an ESP32.

---

## 2. Evidence and relevance map — every uploaded item

| Source | Pages | Relevance for this project | Apply to this Ubuntu laptop? |
|---|---:|---|---|
| `Healthcare_Case_Study_Idea_Book_Complete_1-18.pdf` | 43 | Idea 8 on pp. 21–22; shared toolkit and teaching prototype principle on pp. 2–4 | **Yes**: functional requirements |
| `Module_1_1_Introduction_to_Edge_Computing_in_Healthcare_v1.1.pdf` | 6 | Device–edge–cloud model; latency, bandwidth, privacy, independence from internet | **Yes**, conceptual design |
| `Module_1_2_NVIDIA_Jetson_Platform_Overview_v1.1.pdf` | 6 | Jetson hardware and JetPack version matrix | **Reference only**; no Jetson install |
| `Module_1_3a_Setting_Up_the_Development_Environment_v1.0.pdf` | 26 | §1.3.10 Ubuntu 22.04 laptop path (pp. ~19–25); separate Jetson flash/SSH setup | **Ubuntu part only**; Linux already installed |
| `Module_2_1a_Introduction_to_Linux_OS_Concepts_v1.0.pdf` | 10 | OS architecture, terminal/bash, filesystem and version checks | **Yes** |
| `Module_2_2a_Package_Management_on_Jetson_v1.0.pdf` | 14 | APT, pip, virtual environments, laptop vs Jetson OpenCV, troubleshooting | **Yes** with architecture distinctions |
| `Module_2_3a_Essential_Linux_Commands_v1.0.pdf` | 23 | Directory/file operations, grep/find, permissions, shell scripts | **Yes** |
| `Module_3_2a_Python_Libraries_for_Jetson_Development_v1.0.pdf` | 36 | **Exact laptop Python package pins** in Table 3.2-4 and Appendix A/B | **Yes** |
| `Module_3_3a_Interfacing_with_Peripherals_ESP32_v1.0.pdf` | 21 | **ESP32 I/O bridge**, 3.3 V wiring, IDE 2.3.10, serial, camera examples, troubleshooting | **Yes** |
| `Module_3.4_Healthcare_Case_Study_1_v0.8.pdf` | 20 | Separate monitor/dashboard, YAML config, alarm controls, Flask/SQLite/pytest, systemd | **Reuse architecture only**; VIGIL is a different project |
| `vigil_v0.8.zip` | 58 entries | VIGIL code and requirements, examples of alarm, DB, config, web dashboard and tests | **Reference code**, not Room Environment Safety Control |

## 3. Version inventory — strictly distinguish source from recommendation

### 3.1 Python / laptop dependencies — selected `requirements.txt` baseline

These six pins were **assembled** for Room Environment Safety Control from different manuals. No supplied lecture publishes this exact six-line Room Environment Safety Control lockfile, but **every individual version is traceable**.

```text
numpy==1.26.4
opencv-python==4.11.0.86
pyserial==3.5
Flask==3.0.3
PyYAML==6.0.1
pytest==8.2.0
```

| Name | Exact version | Source | Project role |
|---|---|---|---|
| Python interpreter | **3.10**; example machine **3.10.12** | Module 3.2 pp. 1, 3 | Main runtime; user has **3.10.12** |
| NumPy | **1.26.4** | Module 3.2 pp. 3–5, Appendix A p. 35 | Numerical processing |
| OpenCV Python *distribution* | **opencv-python==4.11.0.86** | Module 3.2 p. 4, Appendix A p. 35 | Webcam processing; `cv2.__version__` reports **4.11.0** |
| pyserial | **3.5** | Module 3.3 p. 8 | USB serial protocol with ESP32 |
| Flask | **3.0.3** | Module 3.4 pp. 6–7; `vigil/requirements.txt` | Web app/dashboard |
| PyYAML | **6.0.1** | `vigil/requirements.txt` | Read/write YAML configuration; *not built into Python* |
| pytest | **8.2.0** | Module 3.4 pp. 6–7; `vigil/requirements.txt` | Hardware-free tests of safety logic |
| SQLite3 | Python stdlib, **no separate pip version/pin** | Module 3.4 p. 7 | Local database |

**Already completed [USER CONFIRMED]:** The six-item `requirements.txt` has been installed in the active `env` virtual environment. Actual imports/version outputs were **not individually reported**, so do not falsely mark them tested.

### 3.2 Other versioned Python/library material (do not automatically install)

| Name | Exact version in course | Source | Room Environment Safety Control status |
|---|---|---|---|
| Pandas | **1.3.5** | Module 3.2 pp. 3–4 and p. 35 | Optional; **not** in current requirements |
| Matplotlib | **3.5.1** | Module 3.2 pp. 3–4 and p. 35 | Optional; chart approach not selected |
| Tkinter / Tcl-Tk | **8.6** | Module 3.2 p. 4; package `python3-tk` via APT | Not needed for Flask web UI unless chosen |
| MediaPipe | **0.10.21** (laptop Module 3.2/3.3) | Module 3.2 pp. 4, 35–36; Module 3.3 p. 15 | Not required explicitly by Project 8; occupancy method unresolved |
| MediaPipe | **0.10.14** (VIGIL) | Module 3.4 pp. 6–7 and ZIP | **Different project/version**; do not mix |
| scikit-learn | **1.5.0** | Module 3.2 p. 4, Appendix A | Not required for the brief |
| Jetson.GPIO | **2.1.6** | Module 3.4 p. 7 and ZIP | **Jetson only**, not laptop + ESP32 |
| gunicorn | **22.0.0** | Module 3.4 pp. 6–7 and ZIP | VIGIL deployment; not Project 8 core requirement |
| VIGIL NumPy range | **>=1.24,<2** | `vigil/requirements.txt` | Different Jetson environment; laptop Module 3.2 pins **1.26.4** |
| Jetson OpenCV | JetPack build; **4.11.0** shown in Module 3.4 example, **4.8.x** commented in ZIP | Module 3.4 p. 6; ZIP | **Jetson-specific source inconsistency**; not laptop wheel pin |

Packages/tools *mentioned without project pin*: SciPy, Pillow, `python-dateutil`, `pytz`, `pyparsing`, `protobuf`, `joblib`, `threadpoolctl`, `opencv-contrib-python`, PyTorch, TensorFlow, HeartPy, scikit-image, pydicom, SimpleITK, Intel RealSense SDK, Nuitrack. **Do not add merely because a lecture mentions them**. Note Module 3.3 p. 15 warns that MediaPipe may install a matching OpenCV-contrib distribution and that mismatched `cv2` builds can break imports.

### 3.3 Arduino, ESP32, Linux and NVIDIA versions

| Item | Version / specification stated | Source | Applicability |
|---|---|---|---|
| Ubuntu | **22.04 LTS**, x86-64 / `amd64` | Modules 1.3, 2.1–2.2, 3.2–3.3 | **User platform** |
| Arduino IDE | **2.3.10** Linux 64-bit AppImage | Module 3.3 pp. 4–6 | Needed when programming ESP32; installation status **unknown** |
| Espressif Arduino `esp32` Boards Manager core | **NO VERSION GIVEN** | Module 3.3 p. 6 | **Approval gate before choosing version** |
| BME680 firmware/driver/Arduino sensor library | **NO PACKAGE NAME OR VERSION PINNED** in supplied modules | Idea 8 pp. 21–22; missing Modules 4.2/4.3 | **Approval gate before selecting/installing** |
| `libfuse2` | Example APT output **2.9.9-5ubuntu3**, not an `apt install pkg=version` pin | Module 3.3 pp. 4–5 | AppImage prerequisite; do not manually force version |
| Serial baud | **115200** | Module 3.3 pp. 3, 7–8 | **Required to match firmware/host** |
| Serial port | Example **`/dev/ttyUSB0`** | Module 3.3 pp. 3, 6–8 | Actual device may differ: must inspect |
| Jetson device | Orin Nano **8 GB**, `arm64/aarch64` | Module 1.2 | Not user's target |
| JetPack target | **6.2.2**; Jetson Linux **36.5** / kernel **5.15** | Module 1.2 pp. 1, 4–5 | Not installed on laptop |
| NVIDIA SDK Manager | **2.4.1** | Module 1.3 p. 1 | Jetson flashing; not needed |
| NoMachine | **9.8.2** | Module 1.3 p. 1 | Jetson remote access; not needed |
| CUDA / TensorRT / cuDNN / VPI | **12.6 / 10.3 / 9.3 / 3.2** | Module 1.2 pp. 4–5 | Jetson AI stack; **not** Project 8 laptop prerequisite |
| DeepStream | **7.1** support | Module 1.2 p. 5 | Not needed |

**Do not confuse** Module 2.2's example `nvidia-jetpack` package version `6.2.3+b81` with the bootcamp's JetPack **6.2.2** target; irrelevant to laptop.

---

## 4. Linux platform, command-line and package-management instructions

### 4.1 Architecture and design principles

- **Module 1.1 pp. 2–5:** device tier gathers sensor/camera data; edge tier does local decisions; cloud tier (if used) gets compact results. Four reasons for edge processing are **latency**, **bandwidth**, **privacy** and **reliability during outages**. Keep local alarm behavior independent from internet access.
- **Module 2.1 pp. 1–3:** Ubuntu is the operating system, Bash is the command shell, the kernel manages files, processes, I/O, memory and drivers. Standard Ubuntu PC kernel suffix may be `-generic`; Jetson uses `-tegra`.
- **Module 1.3 §1.3.10, especially pp. 24–25:** Ubuntu laptop is operated **directly**; Jetson's SDK Manager flashing, USB-IP `192.168.55.1`, Wi-Fi provisioning, SSH and NoMachine steps do not apply. Ubuntu system already installed in user's case.
- **Module 2.2 pp. 1–3 and 9–10:** APT installs system packages and resolves dependencies; pip manages project Python libraries; prefer a **venv** to avoid system-Python conflicts; **do not `sudo pip`** project libraries. On a laptop pip OpenCV is appropriate; on a Jetson, JetPack's OpenCV must be preserved.
- **Module 2.2 p. 9:** `python3.10-venv` is explicitly used; `python3 -m venv env` is documented p. 10. The user installed `python3.10-venv` successfully and created/activated `env`.

### 4.2 Manual-documented terminal commands (only use when relevant)

**These are examples/instructions from the PDFs, not instructions to rerun everything.** Most Python setup is *already complete*.

```bash
# Read-only host checks: Module 2.1 and Module 3.2
lsb_release -a
uname -r
uname -m
python3 --version

# APT and package information: Module 2.2
sudo apt update
apt show nano
dpkg -l nano
apt list --installed

# Module 2.2 p. 9: virtual environment package (USER CONFIRMED INSTALLED)
sudo apt install python3.10-venv

# Module 2.2 p. 10: create a project environment (USER CONFIRMED DONE)
python3 -m venv env

# Module 3.4 p. 6: venv activation syntax shown with its own directory
# For user's environment: source env/bin/activate (already working)

# Module 3.2 p. 5: exact NumPy install / check (already in requirements)
python3 -m pip install numpy==1.26.4
python3 -c "import numpy as np; print('NumPy', np.__version__)"

# Module 3.4 p. 6: install versioned requirements from inside the venv
pip install -r requirements.txt

# Module 3.2 Appendix A (p. 35): laptop OpenCV wheel
python3 -m pip install opencv-python==4.11.0.86

# Module 3.3 pp. 6–8: ESP32 port and serial access
ls /dev/ttyUSB*
sudo usermod -a -G dialout $USER

# Module 3.3 p. 6: inspect conflict only when port disappears
sudo dmesg | grep -i brltty

# Module 3.3 p. 20: camera device inspection
v4l2-ctl --list-devices
```

`sudo usermod -a -G dialout $USER` requires logout/login before the new group membership applies (Module 3.3 p. 5). `ls /dev/ttyUSB*` can fail legitimately when nothing is connected; the path is a **sample**, not universal.

**Conditional, potentially disruptive manual troubleshooting:** Module 3.3 pp. 6, 20 discusses `sudo apt remove --purge -y brltty` **only** where logs confirm that `brltty` is interfering with the USB serial device. Do not run without checking and user approval. Module 2.2 gives `sudo apt --fix-broken install` as a package-repair step; package changes must be inspected rather than applied blindly.

**Module 2.3 general shell reference (pp. 1–23):** `pwd`, `cd`, `ls`, `mkdir`, `cat`, `cp`, `mv`, `rm`, `rmdir`, `find`, `grep`, `diff`, `chmod`, `sudo`; redirects `>`/`>>`, pipe `|`, wildcards `*` and `?`. Use `pwd`/`ls` to confirm location before editing/deleting files. `rm` is destructive. For an executable shell script, `chmod +x` is described. No special kernel tuning or root access is required just to develop Room Environment Safety Control.

### 4.3 Virtual environment and verification

- The user confirmed **working `env`** and **Python 3.10.12**.
- The user confirmed executing the requirements installation; library imports **still need verification**.
- **Manual verification commands** already taught include:

```bash
python3 -c "import numpy as np; print('NumPy', np.__version__)"    # expected 1.26.4
python3 -c "import cv2; print(cv2.__version__)"                   # expected 4.11.0
```

- Module 3.2 Appendix B (p. 36) demonstrates an import/version-check script using `__import__` and `getattr(module, "__version__", "built-in")`. It checks seven Module 3.2 libraries, many **not** installed for this specific project. Missing optional packages in that *seven-library course checker* do not mean Room Environment Safety Control's six-package requirements failed.
- Module 3.4 uses `--system-site-packages` to reuse **JetPack-provided OpenCV**. That is **not the laptop path**, and the user's venv should not be recreated merely to imitate VIGIL.

---

## 5. ESP32 integration — Module 3.3 exact details

### 5.1 Hardware and electrical safety (pp. 3–4)

- Course board: **ESP32 DevKit V1**, common **30-pin WROOM-32** variant; confirm the user's actual board before selecting it in Arduino IDE.
- ESP32 digital GPIO logic is **3.3 V**, not 5 V. **Do not connect 5 V to GPIO**. Wire only with power/USB disconnected.
- For the course's I²C sensor bus: **GPIO21 = SDA**, **GPIO22 = SCL**. These pins are also used for LEDs in other course examples, so **never use them simultaneously for I²C and a display/LED**.
- Additional example pins: GPIO23, GPIO19, GPIO18 are digital LED outputs (with **220 Ω** series resistor per LED); GPIO34 and GPIO35 are **ADC1 inputs only**; GPIO32/GPIO33 are used for digital inputs. GPIO34–39 are input-only.
- The **Jetson** has 40-pin GPIO and I²C but **no ADC**, whereas a laptop needs the ESP32 bridge. This distinction is in Table 3.3-1 (p. 3).
- BME680 is named in the I²C note on p. 4, but **the supplied Module 3.3 does not provide BME680 wiring diagrams, driver installation, initialization, calibration, or data conversion**.

### 5.2 Arduino IDE procedure from the lecture (pp. 4–6)

1. `sudo apt update`, then `sudo apt install libfuse2 -y` for the 64-bit AppImage (if not present).
2. Manual folder: `mkdir -p ~/apps/arduino-ide` then `cd ~/apps/arduino-ide`.
3. Manual's exact IDE download URL and commands:

   ```bash
   wget https://downloads.arduino.cc/arduino-ide/arduino-ide_2.3.10_Linux_64bit.AppImage
   chmod +x arduino-ide_2.3.10_Linux_64bit.AppImage
   ./arduino-ide_2.3.10_Linux_64bit.AppImage
   ```

4. Arduino IDE: File → Preferences → Additional Boards Manager URLs. The lecture prints:

   ```text
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```

5. Tools → Board → Boards Manager → search **`esp32` by Espressif Systems**; choose **DOIT ESP32 DEVKIT V1** if matching user's actual board. **Manual does not pin the ESP32 board-core version. Ask the user before installing one.**
6. Tools → Port: choose the port the board actually enumerates at; example `/dev/ttyUSB0`.
7. Linux serial access: `sudo usermod -a -G dialout $USER`; **log out and back in**.
8. If firmware upload stalls on `Connecting...`, the manual says to hold **BOOT** during upload (p. 6, p. 20).
9. If IDE fails to launch, manual checks `libfuse2`. Manual also mentions a `--no-sandbox` workaround for a specific Chromium sandbox error; **do not preemptively use it**.

**The user's Arduino IDE installation, actual board and serial-port status are not yet confirmed.**

### 5.3 `gpio_bridge.ino` firmware is NOT a BME680 reader (pp. 6–8)

- `gpio_bridge.ino` responds to **newline-terminated** serial text at **115200 baud**:
  - `LED,<pin>,<0|1>`: set a pin low/high.
  - `SEG,<0-9>`: display a digit (seven-segment).
  - `BAR,<0-5>`: light that number of LEDs.
  - Sends `OK` acknowledgement.
- The sketch's `SEG` pin array is `{23,22,21,19,18,5,17}` and `BAR` uses `{23,22,21,19,18}`. **This code occupies GPIO21 and GPIO22 as digital outputs. It must NOT be flashed unchanged while a BME680 I²C sensor is connected to those pins.** This is a serious hardware/resource conflict.
- Module 3.3 explicitly says **Module 4.2 extends the firmware to stream sensor data**, but that module is missing. The available sketch has **no BME680 read command or transmitted sensor format**.
- Module 3.3's `bridge.py` uses `serial.Serial(PORT, 115200, timeout=1)`, delays `time.sleep(2)` after the port opens because ESP32 resets, sends `cmd + "\n"`, and reads one line of response. This behavior is documented, but the **sensor messaging schema remains unspecified**.
- Module 3.3 p. 8 LED serial test toggles an LED on GPIO23 via `send("LED,23,1")`, waits one second, then `send("LED,23,0")`; use **220 Ω series resistor** and correct polarity. This is a *bridge test*, not required final Room Environment Safety Control circuitry.

### 5.4 Documented serial troubleshooting (pp. 6, 8–9, 20)

| Symptom | Lecture's investigation |
|---|---|
| `/dev/ttyUSB0` absent | Confirm USB **data** cable, physical connection and port; inspect logs |
| Port appears then vanishes | Check `sudo dmesg | grep -i brltty`; removal is conditional and approval-gated |
| Permission denied | Check `dialout` membership and relogin |
| Serial returns no data | Arduino Serial Monitor may already own the port; close it; allow 2 s after reset |
| Upload hangs on `Connecting...` | Press/hold BOOT as upload starts |
| Camera not listed/in use | Use `v4l2-ctl --list-devices`; another `/dev/video` index may be correct |

### 5.5 Missing course specifications for BME680 implementation

The missing sensor module would need to establish: **exact sensor breakout power/pin mapping, required Arduino BME680 driver and version, ESP32 core version, sensor initialization, read frequency, units, status/error handling and serial message format**. None is fully pinned in the supplied materials. **Ask for Modules 4.2/4.3 or the user's approval of a separately sourced implementation before selecting these details.** Do not claim a BME680 supplies a medically validated or calibrated pollution index from the provided brief alone.

---

## 6. Webcam and occupancy — what lectures actually establish

- **Project 8 p. 21:** webcam should confirm a room is **occupied before triggering an alert**.
- **Module 3.3 p. 14:** both laptop's built-in camera and USB UVC webcams can be accessed via Ubuntu **V4L2**; sample device `/dev/video0` (others may be `/dev/video1`).
- **Module 3.3 pp. 15–16:** capture with `cv2.VideoCapture(0)`; `ok, frame = cap.read()`; BGR to HSV with `cv2.cvtColor`, threshold mask with `cv2.inRange`, contour detection, draw boxes. Clean up with `cap.release()` and `cv2.destroyAllWindows()`.
- **Module 3.3 p. 20 exercise:** `cv2.absdiff` between frames is proposed for **motion** detection, but motion **does not by itself establish occupancy of a stationary person**. Project 8 does not prescribe this as the occupancy algorithm. Do not silently treat it as an adequate patient-presence classifier.
- **Module 3.2 pp. 25 onward:** OpenCV lessons cover capture and image processing; MediaPipe hand detection appears as an additional library example, but no Project 8 occupancy decision method is specified.
- **VIGIL Module 3.4 pp. 3–5:** MediaPipe Pose returns body landmarks and supports VIGIL's bed states. **VIGIL's bed posture logic is not the Project 8 occupancy algorithm.**
- **Privacy:** The common case-study principle and VIGIL keep image processing local and avoid exporting/storing identifiable raw patient frames. Apply the same privacy objective as a design constraint, but **do not add a new external vision library without approval**.

**Unresolved decision:** How to detect a person reliably, including people who remain still, using approved installed libraries and classroom expectations.

---

## 7. Reusable monitor/dashboard patterns from Module 3.4 and `vigil_v0.8.zip`

### 7.1 What VIGIL actually is

`Module_3.4_Healthcare_Case_Study_1_v0.8.pdf` and `vigil_v0.8.zip` implement **a dementia-patient bed-position monitor** (not Room Environment Safety Control), using MediaPipe Pose/OpenCV and Jetson. Do not rename and deploy VIGIL as Project 8.

### 7.2 Reusable separation of responsibilities

Sources: Module 3.4 pp. 3–6, 8–13, 15–18; ZIP `README.md` and named source files.

| ZIP path | Existing VIGIL role | Room Environment Safety Control relevance |
|---|---|---|
| `vigil/config.yaml` | Central configuration, documented units, thresholds | Pattern for editable, validated Room Environment Safety Control config; **do not copy VIGIL's posture limits** |
| `vigil/monitor.py` | Continuous capture → classify → alert → persist | Pattern for independent **sensor** safety loop; not directly reusable |
| `vigil/alarm.py` | Debounce, cooldown, severity and alert lifecycle | Example of testable alarm state, but Project 8 needs **sustained time-based breaches** |
| `vigil/db.py` | SQLite event log/history and retention | Structural example of local storage |
| `vigil/server.py` | Flask app/API that reads local data | Pattern for dashboard separate from monitor |
| `vigil/templates/dashboard.html` | Web front-end for status, alarms/history | UI design reference only |
| `vigil/test_safety.py` | Synthetic safety tests independent of camera | Pattern for testing rule engine without hardware |
| `vigil/systemd/*.service` | Monitor/web/tunnel service definitions | Optional future deployment; **not to install unchanged** |
| `vigil/pose_engine.py`, `posture.py`, `calibrate_bed.py` | Body-pose/bed calculations and homography | **Out of scope** for environmental monitoring |

### 7.3 Specific techniques in the sources

- **Independent monitoring and display:** VIGIL's monitor and Flask dashboard run as different programs; the dashboard does not own the camera. If dashboard/network fails, monitoring is intended to continue (Module 3.4 pp. 3, 12, 15–17).
- **Central config:** VIGIL settings live in `config.yaml` rather than hard-coded constants. Room Environment Safety Control brief separately requires editable **patient-specific** safe limits via a clinician form.
- **Alarm stability:** VIGIL implements a debounce of **eight frames** and a **60-second** cooldown for its vision states (Module 3.4 p. 5). These are **VIGIL-only defaults** and do **not** specify Room Environment Safety Control's sustained-temperature breach time or cooldown. The book uses a ten-minute breach **example**, not a universal threshold.
- **Local data:** SQLite keeps event state, timestamps, and history. `sqlite3` comes with Python; do not install a third-party `sqlite3` package.
- **Notification separation:** Project 8 explicitly says a slow email/notification must not block monitoring; VIGIL's separation of services is a reference pattern. It does **not** define Room Environment Safety Control's notification channel or delivery format.
- **Tests:** VIGIL's `pytest -v test_safety.py` runs synthetic cases without a real camera/Jetson (Module 3.4 p. 17 and ZIP README). Room Environment Safety Control should have tests for sustained breaches, but actual test cases are not supplied and must be agreed.
- **Remote/dashboard deployment:** Cloudflare Tunnel, Gunicorn, `systemd` services and API keys are documented for **VIGIL** (Module 3.4 pp. 12–17). They are not mandatory for the Room Environment Safety Control brief; public exposure and auto-start should be discussed before enabling.
- **Privacy/ethics:** Educational demo with volunteers and no clinical reliance, avoid raw-video storage or transmission (Module 3.4 p. 19; Case Study book pp. 2–3).

**Caution:** `Module 3.4` p. 7 erroneously labels PyYAML “Python built-in”; `vigil/requirements.txt` explicitly pins **PyYAML==6.0.1**. Treat SQLite as built-in, PyYAML as a pip dependency.

---

## 8. Current implementation status

Current progress and open decisions are maintained in [ROOM_ENVIRONMENT_SAFETY_CONTROL_PROJECT8_IMPLEMENTATION_PLAN.md](ROOM_ENVIRONMENT_SAFETY_CONTROL_PROJECT8_IMPLEMENTATION_PLAN.md). Status statements elsewhere in this extraction describe the source conversation at extraction time, not ongoing verification.

The repository now includes experimental BME680 firmware and a serial reader. Their presence does not resolve missing course specifications or establish dependency approval, successful compilation, or working hardware. Sections 5.5 and 9 describe gaps in the supplied manuals, not the absence of starter code.

---

## 9. Unspecified facts — do NOT fill in automatically

1. Exact ESP32 board (manual demonstrates DevKit V1 WROOM-32; user's physical board not confirmed).
2. Whether Arduino IDE **2.3.10** is installed; whether an appropriate USB data cable and sensor/webcam are present.
3. **ESP32 Arduino core version is not pinned.**
4. **BME680 Arduino sensor library, name, version, dependencies and initialization method are not pinned.**
5. BME680 breakout's electrical specification/pin labels and any board-specific pull-ups are not supplied.
6. Serial **sensor output** protocol/schema/units and error records (the `gpio_bridge.ino` example supports only LED/SEG/BAR).
7. Exact occupancy model/algorithm and handling of stationary people, absent/occluded camera, multiple people or darkness.
8. Safe temperature/humidity/air thresholds, whether pressure should trigger alerts, per-patient profiles, and units.
9. Duration of sustained breach, any reset behavior or cooldown; the example ten minutes is **not** a pin.
10. Clinician identity/authorization on configuration form; deployment security of any remotely accessible app.
11. Notification transport (email, local alarm, dashboard only), backoff, behavior on offline failures.
12. Exact SQLite schema, data-sampling interval, retention policy and chart implementation technique.
13. Whether the instructor expects an actual Jetson (the official brief assumes one) or accepts Ubuntu+ESP32; the user chose the latter for development.
14. Missing **Modules 4.2 and 4.3**. Request them before claiming to reproduce the full specified sensor lab.

**When implementation reaches any of these blockers, stop and ask the user before recommending a non-manual installation command, choosing an unpinned version, or writing an unapproved feature/algorithm.**

---

## 10. Quick source pointers for the terminal AI

| Need to check | Open source |
|---|---|
| Project deliverables, sensor/camera/buzzer hardware, 24h chart | Idea Book **pp. 21–22** |
| Edge design, privacy, offline processing | Module 1.1 **pp. 2–5** |
| Why JetPack packages do not belong on laptop | Module 1.2 **pp. 4–5**; Module 2.2 **p. 10** |
| Ubuntu laptop setup context | Module 1.3 **§1.3.10**, especially **pp. 24–25** |
| Linux architecture / checks | Module 2.1 **pp. 1–3** |
| `python3.10-venv`, pip/apt strategy | Module 2.2 **pp. 8–10** |
| Bash/file and permissions commands | Module 2.3 **pp. 1–23** |
| Exact NumPy/OpenCV/Pandas/etc. versions | Module 3.2 **pp. 3–4, 35–36** |
| ESP32 I²C pins and electrical cautions | Module 3.3 **pp. 3–4** |
| Arduino IDE 2.3.10 AppImage, boards, serial port | Module 3.3 **pp. 4–6** |
| `gpio_bridge.ino` and `pyserial==3.5` | Module 3.3 **pp. 7–8** |
| Webcam frame processing | Module 3.3 **pp. 14–20** |
| VIGIL monitor/db/Flask/test reference | Module 3.4 **pp. 3–7, 12–19** and ZIP `vigil/{monitor.py,alarm.py,db.py,server.py,test_safety.py}` |
| VIGIL exact PyYAML/Flask/pytest pins | ZIP `vigil/requirements.txt` |
| Project 8 BME680 sensor/rule instructions | **Missing Module 4.2 / Module 4.3** |

**Document boundary:** This reference extracts **project-relevant** directions from all uploaded lectures and distinguishes unavailable material. It is not proof of installed packages on the user's laptop, not full source code for Room Environment Safety Control, and not an external version-compatibility certification.
