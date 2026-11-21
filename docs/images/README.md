# 教程图片与来源

本目录区分三类图片：**厂商实物参考、真实软件截图、效果/电气示意图**。软件截图不表示本次运行或起身已通过；效果图不作为孔位、螺钉和接线依据。图片随仓库下载，可以离线查看。

## 厂商实物图

以下图片保持原样，没有重画、改字或添加虚构接线。版权归各自厂商所有；这里只作本教程的型号与接口识别参考，不另行授予第三方图片许可。

| 文件 | 来源页面 | 原始图片 |
| --- | --- | --- |
| `adapter-ports.webp` | [微雪 Bus Servo Adapter (A) 接口说明](https://docs.waveshare.net/Bus_Servo_Adapter_A/) | [原图](https://docs.waveshare.net/assets/images/Bus_Servo_Adapter%28A%29-interface-introduction-00608f80697893b7223d8b8d94762509.webp) |
| `adapter-mode-a.webp` | [微雪 UART 接线示例](https://docs.waveshare.net/Bus_Servo_Adapter_A/Product-Wiring-Example/) | [原图](https://docs.waveshare.net/assets/images/Bus_Servo_Adapter%28A%29-A-3d21e59f9b2f3fddfb80c09d5afe7de8.webp) |
| `adapter-mode-b.webp` | [微雪 USB 接线示例](https://docs.waveshare.net/Bus_Servo_Adapter_A/Product-Wiring-Example/) | [原图](https://docs.waveshare.net/assets/images/Bus_Servo_Adapter%28A%29-B-e982dbdcd8f7e4ce00432f04c704769c.webp) |
| `hd1910-vendor.webp` | [FEETECH HD-1910-C001](https://ftservo.github.io/ftservo-wiki/en/products/models/hd-1910-c001/main/) | [原图](https://ftservo.github.io/ftservo-wiki/en/products/models/hd-1910-c001/images/main.webp) |

获取日期：2026-11-21。微雪图片上的 `9–12.6V` 是其他舵机示例的板上印字；本机器仍按本教程使用独立稳压 **5V**。只把图片用于认接口和跳线。

## 真实软件截图

| 文件 | 拍摄状态与用途 |
| --- | --- |
| `fd-search.png` | 飞特 FD 1.9.8.3，本地软件原生截图。波特率选 1000000、NONE，未打开串口，无舵机搜索结果。COM8 是界面示例。 |
| `fd-program.png` | 同版 FD 的“编程”页，未连接，内存表为空。用于认参数表和按钮位置，不暗示已写入 ID。 |
| `event-ui.png` | 仓库 `desktop/event_app.py` 当前活动 UI 原生截图，未连接硬件，未驱动舵机；未连接时“—”和禁用启动按钮属正常表现。 |

截图日期：2026-11-21。未合成 ID、反馈值或成功状态。FD 从既有官方包 `FD1.9.8.3.zip` 打开；[官方下载页](https://www.feetechrc.com/software.html)。本仓库不分发 FD 可执行文件。

## 项目示意与装配参考

- `assembly.png`：本项目 HD1910 适配 CAD 的三视图渲染，毫米尺寸；不含实际接线。
- `assembly_roles.svg`：上 ID1、下 ID2 的结构角色示意，非加工图。
- `wiring.svg`：整机电气关系，非物理针脚/孔位排列。
- `breadboard.svg`：常见面包板导通孔组，具体板子需核对。
- `workshop-roadmap.svg`：从器材到第一次起身的六步路线。
- `seven-wires.svg`：IMU 四根线、微雪三根低功率线，端点按功能排布，颜色仅供阅读。
- `pc-entrypoints.svg`：电脑端安装、烧录、打开窗口三个入口。

SVG 使用代码绘制，保留可编辑文本；接线关系对应当前 V20 代码和教程，不由图片生成模型猜测针脚。

## 写实效果图与最终提示词

`workshop-hero.png` 通过内置 **image_gen** 工具生成，参考本目录的 `assembly.png`。这是基于 CAD 的概念效果图，**不是实物照片或测试证据**。螺钉、舵盘、孔位和装配细节按 STL 与实物核对。

生成日期：2026-11-21。最终提示词如下：

```text
Use case: sketch-to-render / product-mockup. Asset type: wide hero image for a beginner HD1910 dual-servo self-righting robotics workshop guide. Reference image: the attached CAD three-view drawing is a strict GEOMETRY reference, not a layout reference. Render ONE assembled robot, preserving the exact reference shape and proportions: low blue rectangular 3D-printed base with two parallel long slots, orange compact middle yoke, two small black servo motors mounted on perpendicular joint axes, tall straight orange upper arm with narrow rounded top and elongated slot. Use realistic FDM layer lines on orange and blue plastic, small metal screws, matte black servo cases. Robot stands upright on a clean pale warm gray tabletop; softly blurred pale lavender background, natural window light, restrained soft shadows, polished photographic editorial style, clear entire robot without cropping, enough room around it. Landscape 3:2 composition. No electronics boards, no breadboards, no cables, no schematic connections, no extra robot, no people, no text, no labels, no logos, no dimension lines. This is a clearly captioned conceptual photorealistic rendering, so don't imply a documentary test photo.
```
