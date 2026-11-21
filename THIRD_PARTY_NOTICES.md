# Third-party notices

`firmware/imu_reader/src/bosch/` contains the unchanged Bosch BMI270 SensorAPI files `bmi2.c`, `bmi2.h`, `bmi2_defs.h`, `bmi270.c`, `bmi270.h` and `LICENSE`.

Source: https://github.com/boschsensortec/BMI270_SensorAPI

Pinned commit: `41129fcfe39c583ee5462d79195741945d51c1fe`

Copyright and BSD-3-Clause license are preserved in the original source headers and the bundled `LICENSE`. The BMI270 initialization configuration is included in the upstream driver.

Arduino-ESP32, Arduino CLI and pyserial are external build/runtime dependencies. Current binary artifact notices are given below; third-party desktop executables are not redistributed.

## Current V20 workshop

The same Bosch SensorAPI source and BSD-3-Clause notice are retained in
`firmware/policy_shadow/src/bosch/`. See its bundled `LICENSE` and original source headers.

The original two-servo self-rising robot concept and training approach are based on
[HomeMadeGarbage / SelfRisingRobot](https://github.com/homemadegarbage/SelfRisingRobot),
reference revision `c344c2a4a1a51562247528d8aadcc0a527b6b103`, and
[the author's article](https://homemadegarbage.com/rl13).
This repository adapts the structure to HD1910 servos, uses locally trained/exported
front/back and side policies, and adds ESP32-S3/BMI270 bus control and the desktop UI.
Public availability is not a blanket license grant over upstream code, models or CAD;
their respective authors' terms still apply. No new blanket license is asserted here.

`firmware/prebuilt/v20/` contains compiled ESP32-S3 artifacts, including Arduino-ESP32
2.0.17 and ESP-IDF/bootloader components. Corresponding platform sources and license
notices are available at:

- https://github.com/espressif/arduino-esp32/tree/2.0.17
- https://github.com/espressif/esp-idf

The application source corresponding to the published V20 image is included in
`firmware/policy_shadow/`. The manifest records board settings and checksums.

FD, USB drivers, Arduino IDE, Arduino CLI, Python, pyserial and esptool are installed
from their respective official sources, rather than redistributed as third-party
executables. Python packages are declared in `requirements-workshop.txt`.
Windows fonts used by the UI are referenced by installed family name; font files
are not included. Assembly renders and the three HD1910 bracket STL files describe
this project's adapted geometry; the servo manufacturer's full STEP model is not included.

## Tutorial pictures

Official Waveshare adapter photos and the FEETECH HD1910 product photo are reproduced
as credited identification references. Copyright remains with their respective
owners; no new license is asserted over these images. FD 1.9.8.3 screenshots show
the unconnected software for teaching its controls and do not redistribute the
executable. The event-window screenshot shows this repository's unchanged UI.
The workshop hero is an AI-generated conceptual rendering based on the project's
CAD and is visibly captioned as such. Per-file sources, capture state and the final
generation prompt are recorded in [`docs/images/README.md`](docs/images/README.md).
