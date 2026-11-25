# 4 · 把程序烧进 ESP32-C3

[接线](03-wiring.md) · [C3 首页](../README.md) · [打开窗口](05-first-run.md)

“烧录”就是把已编译的机器人程序写进 C3。新手走 **A**；关节零位在窗口保存，无需自己编译。只有修改 IMU 安装标定或其他源码时才走 **B**。

## A · 用附带的 V25 二进制直接烧录

1. 完整解压 C3 包，装好 Python，运行一次 `00_setup.cmd`。
2. 关闭 FD、展示窗口、Arduino 串口监视器，避免占用串口。
3. 先断开舵机独立电源，电脑 USB 数据线接 C3。底座平放，两轴直立并保持静止。
4. Windows 设备管理器 → **端口（COM 和 LPT）**，找插上 C3 后新增的 COM。也可拔插一次对照。不能照抄作者的 COM18。
5. 双击 `01_flash.cmd`。脚本会检查四个固件文件的 SHA256 和源码是否被改过，然后列出串口。
6. 输入 C3 对应的 `COM数字`，按回车。看到 `Chip is ESP32-C3`、写入进度和 `Hash of data verified`，表示写入已校验。芯片不符时不要改 `--chip` 强刷。
7. 烧录成功后等待重启；若停在下载模式，轻按右侧 **RST** 一次。
8. 底座继续平放静止约 **35～40 秒**。C3 先跑完整模型自检（实测约 27 秒），再采集 IMU 水平零点。
9. 如需接回舵机独立电源，先断电完成连接，再整机平放直立上电。按[第 5 章](05-first-run.md)连接窗口。

**V25 首次使用：完成连接后，在真实直立、卸力状态点击“保存当前直立关节零位”。** 不再要求新设备符合旧的 337/2872，也不需要为关节零位重新编译。该设置保存在当前 C3；正常更新此包不会主动擦除 NVS，但换板、擦除整片 Flash 或存储校验失败时需要重新保存。

使用的数据线要能传数据。C3 只有这一个 USB-C 口，同时负责供电、烧录和窗口数据。本板走原生 USB，不是 S3 双口板的 COM/OTG 选择方式。

## C3 连接有问题：用 BOOT 插 USB

以下左右方向对应[正面针脚图](03-wiring.md)：**元件朝上、USB-C 朝上**。

1. **拔掉 C3 的 USB。**
2. **按住左边 BOOT，同时插回 USB。**
3. **插好后等约 2 秒，再松开 BOOT。**
4. 再看设备管理器；下载模式的 COM 号可能改变，选新出现的 C3 串口，重新运行 `01_flash.cmd`。
5. 烧录成功后，**轻按右边 RST 一次**，进入已烧录程序。保持底座平放静止，等完整自检和水平零点。

BOOT 用于进入下载模式，RST 用于重启。按过 BOOT 不代表已经烧好了程序；下载模式也不会提供完整的机器人姿态数据。仍无端口时换数据线、USB 口，核对这块实物的按键标字，不改接线试探。

<a id="build-source"></a>

## B · 修改源码后自己编译

**只为设置关节零位，可以跳过整个 B 部分。** V25 在窗口里保存即可。只有修改 IMU 安装矩阵、模型或其他源码时才需要以下编译步骤。

需要软件：[Arduino IDE 官方下载](https://www.arduino.cc/en/software)；Espressif [开发板安装说明](https://docs.espressif.com/projects/arduino-esp32/en/latest/installing.html)。

1. Arduino IDE 首选项的“附加开发板管理器网址”添加 `https://espressif.github.io/arduino-esp32/package_esp32_index.json`。
2. 开发板管理器安装 **esp32 by Espressif Systems，版本 2.0.17**。这是本包验证过的版本，避免第一次自行升级核心。
3. 打开 `firmware/policy_shadow/policy_shadow.ino`；整个 `policy_shadow` 文件夹必须保留，不能只拿走 `.ino`。
4. 开发板选 **ESP32C3 Dev Module**；USB CDC On Boot **Enabled**；Flash Mode **DIO**；Flash Size **4MB**；Flash Frequency **80MHz**；CPU **160MHz**；Partition Scheme **Default**。端口选 C3 当前 COM。
5. 点击“验证”编译。BMI270 驱动和网络头文件已包含，不需要再装重复的 BMI270 库。
6. 上传前关闭窗口，底座平放直立静止，必要时按上述 BOOT 步骤进下载模式，再上传。
7. 上传后按 RST，等待自检与水平校准，再启动窗口。用自己的源码版本、窗口配置成套保存。

Arduino CLI 对应配置：

```text
arduino-cli core install esp32:esp32@2.0.17
arduino-cli compile --fqbn esp32:esp32:esp32c3:CDCOnBoot=cdc,FlashMode=dio,FlashSize=4M firmware/policy_shadow
```

CLI 首次使用仍需配置上述开发板索引，详见官方安装文档。程序串口为 230400，舵机 UART1 为 1000000、TX=4、RX=5，I²C SDA=6、SCL=7，均已写在源码中。

**修改了零位/标定/模型源码后，不再使用原机 `01_flash.cmd` 覆盖回附带二进制。** 脚本会拒绝被修改的配套源码；自己的编译结果走 Arduino 上传并归档。

固件组件和地址：

| 文件 | 写入地址 |
| --- | --- |
| `release/bootloader.bin` | `0x0` |
| `release/partitions.bin` | `0x8000` |
| `release/boot_app0.bin` | `0xe000` |
| `release/application.bin` | `0x10000` |

这些地址只用于本 C3 构建；无需手动输入，`01_flash.cmd` 会调用 `flash_c3.py` 完成。

原生 USB CDC 的原理参考：[Espressif USB CDC 与烧录说明](https://docs.espressif.com/projects/arduino-esp32/en/latest/tutorials/cdc_dfu_flash.html)。
