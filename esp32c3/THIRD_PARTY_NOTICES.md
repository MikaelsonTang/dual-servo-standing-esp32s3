# ESP32-C3 第三方来源与分发说明

`firmware/policy_shadow/src/bosch/` contains Bosch BMI270 SensorAPI source and its BSD-3-Clause LICENSE. Original source headers and license are preserved.

- Source: https://github.com/boschsensortec/BMI270_SensorAPI
- Pinned source revision used by this project: `41129fcfe39c583ee5462d79195741945d51c1fe`

`release/` contains ESP32-C3 binaries built with Arduino-ESP32 2.0.17 and its ESP-IDF/bootloader components. The matching application source and exported policy evaluator are included in `firmware/policy_shadow/`; checksums are in `manifest.json`.

- Arduino platform sources/licenses: https://github.com/espressif/arduino-esp32/tree/2.0.17
- ESP-IDF sources/licenses: https://github.com/espressif/esp-idf

The original self-rising robot concept and training approach are based on [HomeMadeGarbage / SelfRisingRobot](https://github.com/homemadegarbage/SelfRisingRobot), reference revision `c344c2a4a1a51562247528d8aadcc0a527b6b103`, and [the author's article](https://homemadegarbage.com/rl13). This project adapts geometry to HD1910 servos, uses locally trained front/back and side policies, and adds hardware control and a desktop UI. Public availability is not a blanket license over upstream code, models or CAD; their respective authors' terms still apply. No new blanket license is asserted here.

`tests/reference_networks.h` is the original float export used for numerical comparison with the C3 evaluator. Bosch's initialization configuration remains in its upstream driver.

Python, Arduino IDE/CLI, FD, USB drivers, pyserial and esptool are installed from their official sources. Their desktop executables are not bundled. Python dependencies are declared in `requirements.txt`. Windows fonts are referenced by installed family name; no font files are redistributed.

The three HD1910 bracket STL files describe this project's adapted geometry. The servo manufacturer's complete CAD model is not included. Pictures retain their original authors' rights; [per-file picture credits](docs/images/README.md) distinguish original project diagrams, the project's C3 photo, manufacturer images and FD software screenshots. Wiring SVGs are explanatory illustrations, not PCB manufacturing drawings.
