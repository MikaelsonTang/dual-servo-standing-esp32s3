# 双舵机站立模型（ESP32S3）

使用 ESP32-S3、两只飞特 HD-1910-C001 总线舵机与 BMI270 IMU 的站立／翻身机器人实验项目。

**当前版本已完成 IMU 真机读取。尚未完成 ESP32 舵机控制、真机平衡或翻身站立；本仓库暂不包含 CAD、仿真或强化学习策略。**

## 硬件与当前状态

| 部件 | 配置／状态 |
| --- | --- |
| 主控 | ESP32-S3 N16R8，双 Type-C，板载 CH340 |
| IMU | BMI270；实测 I2C 地址 `0x68`、CHIP_ID `0x24` |
| 下舵机 | HD-1910-C001，用户已设置 ID 1 |
| 上舵机 | HD-1910-C001，用户已设置 ID 2 |
| 总线适配器 | 已有 Waveshare Bus Servo Adapter (A)，后续 UART 控制使用 |
| 当前供电 | 电脑 USB 仅供 ESP32 与 IMU；舵机供电未验收 |

用户称量：每只舵机 23 g（含舵盘和原配螺钉），上部柱子 11 g、中间轴承部分 7 g、底座 13 g。所列部件合计 77 g，不是包含面包板、IMU、导线等的整机实测质量。

## IMU 接线

断电后接线，按板上丝印核对，不按照片左右方向猜引脚。

| ESP32-S3 | IMU |
| --- | --- |
| 3V3 | 3.3V |
| GND | GND |
| GPIO4 | SDA |
| GPIO5 | SCL |
| 不接 | INT |

电脑接 ESP32 板背面标注 **COM** 的 Type-C 口，同时传输数据并供电；USB-OTG 口暂空着，无需再接充电头。此接法只验证 IMU。

## 固件编译与烧录

源码：[firmware/imu_reader/imu_reader.ino](firmware/imu_reader/imu_reader.ino)。Bosch 官方驱动及初始化配置随源码附带，无需另装传感器库。

本次验证环境：Arduino CLI 1.6.0、Espressif Arduino-ESP32 2.0.17。

Arduino IDE 设置：`ESP32S3 Dev Module`、Flash `16MB`、PSRAM `Disabled`、USB CDC On Boot `Disabled`。先安装对应 ESP32 核心，再打开上述 `.ino` 编译上传。

Arduino CLI 示例（端口号按本机修改）：

```powershell
arduino-cli core update-index --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core install esp32:esp32@2.0.17 --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli compile --fqbn "esp32:esp32:esp32s3:CDCOnBoot=default,FlashSize=16M,PSRAM=disabled" --output-dir build firmware/imu_reader
arduino-cli upload -p COM15 --fqbn "esp32:esp32:esp32s3:CDCOnBoot=default,FlashSize=16M,PSRAM=disabled,UploadSpeed=115200" --input-dir build firmware/imu_reader
```

烧录会覆盖原程序；有需要时先备份。设备原始闪存备份只留在本机，未上传。此固件不发送舵机指令。

## 电脑实时查看

安装带 Tkinter 的 Python 3（Windows 官方安装包默认包含），首次双击 `setup_monitor.cmd` 安装项目虚拟环境与 pyserial，然后双击 `view_imu.cmd`。窗口默认 COM15，可切换至设备管理器中的实际端口。

也可以手动运行：

```powershell
python -m pip install -r requirements.txt
python monitor/monitor.py --port COM15
```

串口使用 `115200`。不要同时打开另一个串口监视器占用该端口。固件配置传感器 100 Hz 采样、约 10 Hz 输出，显示：

- 三轴加速度（g）、三轴角速度（°/s）；
- 加速度合量（g）；
- 基于加速度的静态 Roll／Pitch（°）。

静态倾角不等于融合姿态，没有航向角；机器人运动时不能直接用于平衡控制。尚未标定零偏及芯片坐标到机器人坐标的转换。

程序自动保存原始日志；超过 1.5 秒没有新样本会清空读数并标注过期。

## 真机验证记录

2026-11-15：Bosch 驱动初始化成功，设置与读回配置一致；5 秒采集到 48 组有效数据，时间戳递增，加速度合量均值 **1.007593 g**。本次静止附近读数支持通信和基础测量正常，不代表精度标定或动态性能验收。

详见 [验证摘要](validation/imu_readout_2026-11-15.json) 与 [实测 CSV](validation/imu_sample_2026-11-15.csv)。

## 下一步

1. 确认舵机独立电源、实测输出电压及线路容量。
2. ESP32 经半双工 TTL 总线适配器，只读检查 ID 1／ID 2 的响应与状态。
3. 支撑结构、核对关节零位和机械限位，再逐只做低速小角度动作。
4. 完成 IMU 标定、坐标对齐后再做站立控制与仿真实机对照。

详见 [舵机供电与首次测试](docs/servo_power.md)。

## 来源

- 机构与任务参考：[homemadegarbage/SelfRisingRobot](https://github.com/homemadegarbage/SelfRisingRobot)。本次只归档新硬件的 IMU 验证，不声称复现了原项目策略。
- IMU 驱动：[Bosch BMI270 SensorAPI](https://github.com/boschsensortec/BMI270_SensorAPI)，固定提交 `41129fcfe39c583ee5462d79195741945d51c1fe`；保留原始 BSD-3-Clause 许可证，见 [第三方说明](THIRD_PARTY_NOTICES.md)。
