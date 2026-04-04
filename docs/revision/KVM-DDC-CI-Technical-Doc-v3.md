# ESP32-S3 DDC/CI KVM 切换器 — 技术文档 v3

> 最后更新：2026-04-05
> 阶段：LG 显示器 + USB 切换已实现，小米显示器等待硬件

---

## 1. 项目概述

### 1.1 目标

用 ESP32-S3 实现完全独立于电脑的一键 KVM 切换，在 MacBook Pro 和 Gaming PC 之间切换两台显示器输入源 + USB 外设。

### 1.2 设备清单

| 设备 | 型号 | 角色 | 状态 |
|------|------|------|------|
| 主显示器 | **LG 34GS95QE** | 超宽屏，DDC/CI Alt 模式 | ✅ 切换已验证 |
| 副显示器 | **Redmi G Pro 27** | 小米副屏，标准 DDC/CI | ⏳ 等待分线板+母转母 |
| 电脑 A | Gaming PC | Windows (LG HDMI1) | ✅ |
| 电脑 B | MacBook Pro | macOS (LG DP1) | ✅ |
| 控制器 | ESP32-S3 Dev Module | ESP-IDF v5.5.4 | ✅ |
| USB 切换 | TS3USB221 | USB 2.0 模拟开关 | ✅ 已验证 |

### 1.3 当前已实现功能

| 功能 | 状态 | 说明 |
|------|------|------|
| USB 键盘 A/B 键切换 | ✅ 完成 | A=Windows, B=MacBook |
| LG DDC/CI 写入切换 | ✅ 完成 | Alt 模式，HDMI1 ↔ DP1 |
| TS3USB221 USB 切换 | ✅ 完成 | GPIO4 控制 SEL 引脚 |
| DDC/CI 读取轮询 | 📋 Backlog | 非关键功能，暂不处理 |
| OSD 切换自动同步 USB | 📋 Backlog | 依赖 DDC 读取，暂不处理 |
| Redmi 显示器切换 | ⏳ 等待硬件 | 需要分线板 + 母转母 |
| 物理按钮 | ⏳ 待实现 | — |
| PCB 设计 | ⏳ 待验证完成后 | — |

### 1.4 当前接线方案

```
┌─────────────────────────────────────────────────────────┐
│                    LG 34GS95QE                          │
│              HDMI1 ← Gaming PC                          │
│              DP1   ← MacBook Pro                        │
│              HDMI DDC ← ESP32 I2C-0 (分线板直插)         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                     ESP32-S3                             │
│              I2C-0: GPIO18(SCL) + GPIO47(SDA) → LG DDC  │
│              GPIO4: TS3USB221 SEL                        │
│              USB-C: HID 键盘 (USB Host)                  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                    TS3USB221                             │
│              SEL=LOW  → Port1 (Windows)                  │
│              SEL=HIGH → Port2 (MacBook)                  │
└─────────────────────────────────────────────────────────┘
```

---

## 2. HDMI 分线板

### 2.1 排列方式

经 ESP32 GPIO 探测验证，分线板为**奇偶分排**结构：

```
              HDMI 公头方向（插入显示器端）
    ┌─────────────────────────────────────────┐
上排 │ 1   3   5   7   9  11  13  15  17  19  │  ← 奇数 Pin（10针）
    ├─────────────────────────────────────────┤
下排 │ 2   4   6   8  10  12  14  16  18      │  ← 偶数 Pin（9针）
    └─────────────────────────────────────────┘
      位置1 位置2 位置3 ...               位置10
```

### 2.2 DDC 引脚位置

| 信号 | HDMI Pin | 分线板位置 | 连接到 ESP32 |
|------|----------|-----------|-------------|
| **SCL** | Pin 15 | 上排第 8 针 | GPIO 18 + 4.7kΩ → 3.3V |
| **SDA** | Pin 16 | 下排第 9 针 | GPIO 47 + 4.7kΩ → 3.3V |
| **GND** | Pin 5 | 上排第 3 针 | ESP32 GND |

### 2.3 上拉电阻接法

每组 I2C 需要 2 个 4.7kΩ 电阻上拉到 3.3V。ESP32 上所有 3.3V 引脚是同一条电源轨，面包板上从任一 3.3V 引脚拉线到电源总线，所有上拉电阻从总线取电即可。未来如需接更多组 I2C（小米显示器），不需要额外的 3.3V 引脚。

```
面包板接法：

ESP32 3.3V ──→ 面包板电源总线（红线）

SCL 线: 分线板上排第8针 ── GPIO18 ── 同排插 4.7kΩ 一脚
                                      4.7kΩ 另一脚 ── 电源总线

SDA 线: 分线板下排第9针 ── GPIO47 ── 同排插 4.7kΩ 一脚
                                      4.7kΩ 另一脚 ── 电源总线
```

### 2.4 HDMI Type A 标准引脚参考

```
Pin 1:  TMDS Data2+        Pin 2:  TMDS Data2 Shield
Pin 3:  TMDS Data2-        Pin 4:  TMDS Data1+
Pin 5:  TMDS Data1 Shield  Pin 6:  TMDS Data1-
Pin 7:  TMDS Data0+        Pin 8:  TMDS Data0 Shield
Pin 9:  TMDS Data0-        Pin 10: TMDS Clock+
Pin 11: TMDS Clock Shield  Pin 12: TMDS Clock-
Pin 13: CEC                Pin 14: Reserved
Pin 15: SCL (DDC Clock)    Pin 16: SDA (DDC Data)
Pin 17: DDC/CEC Ground     Pin 18: +5V Power
Pin 19: Hot Plug Detect
```

---

## 3. LG 34GS95QE — DDC/CI

### 3.1 协议概要

LG 较新型号显示器使用非标准 "DDC Alt" 协议进行**写入**。标准协议可**读取**但**写入无效**。

| 操作 | 源地址 | VCP 代码 | 说明 |
|------|--------|---------|------|
| **写入（切换）** | **0x50** (Alt) | **0xF4** (Alt) | 必须用 Alt 模式 |
| **读取（查询）** | **0x51** (标准) | **0x60** (标准) | 标准模式可读 |

### 3.2 输入源值映射

| 输入端口 | 用途 | Alt 写入值 (VCP 0xF4) | 标准读取值 (VCP 0x60) |
|---------|------|---------------------|---------------------|
| HDMI-1 | **Windows** | **0x0090** (144) | **0x0F** (15) |
| HDMI-2 | — | 0x0091 (145) | 0x10 (16) |
| DP-1 | **MacBook** | **0x00D0** (208) | **0x11** (17) |
| DP-2 | — | 0x00D1 (209) | 0x12 (18) |

### 3.3 写入数据包格式 (已验证 ✅)

```
I2C 写到 0x37 (7-bit 地址, 总线上为 0x6E):
  [0] 0x50        ← 源地址（LG Alt）
  [1] 0x84        ← 长度 | 0x80（4字节负载）
  [2] 0x03        ← VCP Set 操作码
  [3] 0xF4        ← VCP 代码（LG Alt）
  [4] value_high  ← 值高字节
  [5] value_low   ← 值低字节
  [6] checksum    ← 0x6E ⊕ [0] ⊕ [1] ⊕ [2] ⊕ [3] ⊕ [4] ⊕ [5]
```

**示例（切到 DP-1 / MacBook）：**
```
数据: 50 84 03 F4 00 D0
校验: 0x6E ⊕ 0x50 ⊕ 0x84 ⊕ 0x03 ⊕ 0xF4 ⊕ 0x00 ⊕ 0xD0 = 0xA5
```

### 3.4 读取数据包格式 (调试中 🔧)

**请求：**
```
I2C 写到 0x37:
  [0] 0x51        ← 源地址（标准）
  [1] 0x82        ← 长度 | 0x80（2字节负载）
  [2] 0x01        ← Get VCP Feature 操作码
  [3] 0x60        ← VCP 代码（标准输入源）
  [4] checksum    ← 0x6E ⊕ [0] ⊕ [1] ⊕ [2] ⊕ [3]
```

**期望回复（11字节）：**
```
I2C 从 0x37 读取:
  [0] 0x6E        ← 显示器源地址
  [1] 0x88        ← 长度 | 0x80（8字节负载）
  [2] 0x00        ← 无错误
  [3] 0x02        ← VCP Feature Reply 操作码
  [4] 0x60        ← VCP 代码
  [5] type        ← 值类型
  [6] max_high    ← 最大值高字节
  [7] max_low     ← 最大值低字节
  [8] cur_high    ← 当前值高字节
  [9] cur_low     ← 当前值低字节
  [10] checksum   ← 0x50 ⊕ 所有回复字节
```

### 3.5 读取状态 (Backlog)

写入 100% 成功。读取 VCP 0x60 持续失败（可能原因：GPU 占用总线、时序问题、回复格式偏移），但不影响核心 KVM 切换功能，列为 Backlog 暂不处理。

### 3.6 I2C 总线设备

```
Scan: 0x37 0x3A 0x49 0x50 0x54 0x58 0x59  (7 devices, 稳定)
```

### 3.7 验证结果

- ✅ ESP32 通过 HDMI DDC 成功切换 LG 输入源（HDMI ↔ DP，双向）
- ✅ 切换延迟约 1-2 秒
- ✅ I2C 50kHz 稳定工作
- 📋 DDC 读取 VCP 0x60 失败，列为 Backlog

---

## 4. Redmi G Pro 27 — 标准 DDC/CI (等待硬件)

### 4.1 关键发现

**DDC 写入只接受来自活跃（当前显示的）输入端口的命令。**

- ESP32 接在空闲 HDMI1 口 → DDC 写入被忽略
- 一旦显示器切走当前端口，该端口就失去 DDC 控制能力
- **结论：ESP32 必须串联在活跃端口的 HDMI 线路中，与视频信号共享 DDC 总线**

### 4.2 方案

用 HDMI 母对母转接头，在 PC→显示器 和 Mac→显示器 的 HDMI 线中各串联一块分线板，ESP32 从分线板上取 DDC 信号。两条线路分别接 ESP32 的 I2C-0 和 I2C-1。

```
Gaming PC ──HDMI──→ [母对母] ← [分线板A] ──→ Redmi HDMI1
                                   │
                             ESP32 I2C-A

MacBook   ──HDMI──→ [母对母] ← [分线板B] ──→ Redmi HDMI2
                                   │
                             ESP32 I2C-B
```

### 4.3 协议参数

| 参数 | 值 |
|------|-----|
| I2C 地址 | 0x37 |
| 源地址 | **0x51**（标准） |
| VCP 代码 | **0x60**（标准） |
| I2C 速率 | 30kHz（推荐） |

### 4.4 已确认的输入源值

| 输入端口 | VCP 0x60 值 | 验证状态 |
|---------|------------|---------|
| DP-1 | 15 (0x0F) | ✅ 已验证 |
| HDMI-2 | 17 (0x11) | ✅ 已验证 |
| HDMI-1 | 待确认 | ⏳ 需要硬件 |

### 4.5 需要购买的硬件

| 物品 | 数量 | 用途 | 状态 |
|------|------|------|------|
| HDMI 分线板 | 2 块 | 串联在两条 HDMI 线中 | ⏳ 待购 |
| HDMI 母对母转接头 | 2 个 | 连接分线板和 HDMI 线 | ⏳ 待购 |
| 4.7kΩ 电阻 | 4 个 | 两组 I2C 上拉 | ⏳ 待购 |

---

## 5. TS3USB221 USB 切换

### 5.1 规格

| 参数 | 值 |
|------|-----|
| 芯片 | TS3USB221 |
| 协议 | USB 2.0 High Speed (480 Mbps) |
| 控制引脚 | SEL (GPIO 4) |
| SEL=LOW | Port 1 → Windows |
| SEL=HIGH | Port 2 → MacBook |

### 5.2 USB 2.0 vs 3.0

TS3USB221 只能切换 USB 2.0 的一对差分信号线（D+/D-）。USB 3.0 额外有两对 SuperSpeed 信号线（SS TX+/- 和 SS RX+/-），TS3USB221 没有这些引脚，无法切换 USB 3.0。

**当前外设全部为 USB 2.0（2kHz 无线鼠标接收器 × 2 + 普通键盘），无需升级。**

USB 2.0 High Speed 微帧间隔 125μs，支持最高 8000Hz 轮询，2kHz 鼠标完全没有问题。

### 5.3 未来 USB 3.0 升级路径

如需支持 USB 3.0 设备（外接硬盘、采集卡等），有两条路：

1. **换 USB 3.0 mux 芯片**（如 CBTL02043A、HD3SS460）— 需要画 PCB，芯片封装为 BGA/QFN
2. **买现成 USB 3.0 切换器**，拆开接 ESP32 GPIO 模拟按键 — 推荐，最省事

---

## 6. 切换逻辑

### 6.1 键盘切换 (已实现 ✅)

```
按 A 键 → kvm_switch_to(TARGET_WINDOWS):
  1. DDC Alt 写入: VCP=0xF4, val=0x0090 → LG 切到 HDMI1
  2. GPIO4 = LOW → TS3USB221 切到 Port1 (Windows)

按 B 键 → kvm_switch_to(TARGET_MACBOOK):
  1. DDC Alt 写入: VCP=0xF4, val=0x00D0 → LG 切到 DP1
  2. GPIO4 = HIGH → TS3USB221 切到 Port2 (MacBook)
```

### 6.2 OSD 自动同步 (Backlog 📋)

依赖 DDC 读取功能，暂不处理。设计思路备忘：

```
每 500ms 轮询:
  1. DDC 标准读取: VCP=0x60 → 获取当前输入源
  2. 如果值 ≠ current_target:
     → 同步 USB (仅切 GPIO，不发 DDC 写入)
  3. 键盘切换后 3 秒冷却期，避免读到过渡状态
```

### 6.3 未来完整切换逻辑 (双显示器)

```
切到 MacBook:
  1. 通过 PC 侧活跃总线发命令:
     - LG:    src=0x50, VCP=0xF4, val=0x00D0 (→DP1)
     - Redmi: src=0x51, VCP=0x60, val=0x0011 (→HDMI2)
  2. TS3USB221 SEL=HIGH → USB 切到 MacBook

切到 Windows:
  1. 通过 Mac 侧活跃总线发命令:
     - LG:    src=0x50, VCP=0xF4, val=0x0090 (→HDMI1)
     - Redmi: src=0x51, VCP=0x60, val=0x000F (→HDMI1)
  2. TS3USB221 SEL=LOW → USB 切到 Windows
```

---

## 7. 软件架构

### 7.1 框架

- **ESP-IDF v5.5.4**（非 Arduino）
- 编译目标：esp32s3
- 组件依赖：`usb_host_hid`（通过 `idf_component.yml` 自动拉取）

### 7.2 任务分配

| 任务 | 核心 | 优先级 | 栈大小 | 功能 |
|------|------|--------|--------|------|
| usb_host_lib | Core 0 | 2 | 4096 | USB Host 事件循环 |
| HID background | Core 0 | 5 | 4096 | HID 报告处理（驱动创建） |
| input_monitor | Core 1 | 3 | 4096 | DDC 读取轮询 + USB 同步 |

USB Host 相关任务在 Core 0，DDC 轮询在 Core 1，互不干扰。

### 7.3 项目文件结构

```
usb_switch_project/
├── CMakeLists.txt              ← 项目顶层 CMake
├── sdkconfig.defaults          ← 编译配置（esp32s3, USB Host, DEBUG 日志）
├── sdkconfig                   ← 完整编译配置（自动生成）
├── main/
│   ├── CMakeLists.txt          ← 源文件注册
│   ├── idf_component.yml       ← 组件依赖（usb_host_hid）
│   └── main.c                  ← 主程序（唯一需要修改的文件）
├── managed_components/         ← 自动下载的组件
│   └── espressif__usb_host_hid/
└── build/                      ← 编译输出
```

### 7.4 关键配置 (sdkconfig.defaults)

```
CONFIG_IDF_TARGET="esp32s3"
CONFIG_USB_OTG_SUPPORTED=y
CONFIG_USB_HOST_CONTROL_TRANSFER_MAX_SIZE=1024
CONFIG_USB_HOST_HW_BUFFER_BIAS_BALANCED=y
CONFIG_USB_HOST_HUBS_SUPPORTED=y
CONFIG_ESP_CONSOLE_SECONDARY_NONE=y          # 禁用 USB Serial JTAG 二级控制台
CONFIG_LOG_DEFAULT_LEVEL_DEBUG=y
CONFIG_LOG_DEFAULT_LEVEL=4
```

### 7.5 I2C 驱动

使用 ESP-IDF 新版 `i2c_master` 驱动（非旧版 `i2c.h`）。

```c
#include "driver/i2c_master.h"

i2c_master_bus_handle_t i2c_bus;
i2c_master_dev_handle_t ddc_dev;

// 初始化总线
i2c_master_bus_config_t bus_cfg = {
    .i2c_port = I2C_NUM_0,
    .scl_io_num = GPIO_NUM_18,
    .sda_io_num = GPIO_NUM_47,
    .glitch_ignore_cnt = 7,
    .flags.enable_internal_pullup = false,  // 外部 4.7kΩ
};
i2c_new_master_bus(&bus_cfg, &i2c_bus);

// 添加设备
i2c_device_config_t dev_cfg = {
    .device_address = 0x37,
    .scl_speed_hz = 50000,
};
i2c_master_bus_add_device(i2c_bus, &dev_cfg, &ddc_dev);

// 写入
i2c_master_transmit(ddc_dev, pkt, len, timeout_ms);

// 读取
i2c_master_receive(ddc_dev, resp, len, timeout_ms);

// 写+读 (repeated start)
i2c_master_transmit_receive(ddc_dev, req, req_len, resp, resp_len, timeout_ms);
```

---

## 8. ESP32-S3 注意事项

### 8.1 启动引脚限制

| GPIO | 限制 | 说明 |
|------|------|------|
| GPIO 0 | ⚠️ 启动模式 | 接 GND 进入下载模式 |
| GPIO 45 | ⚠️ 启动模式 | 接 GND 导致无限重启 |
| GPIO 46 | ⚠️ 启动模式 | 慎用 |
| GPIO 19/20 | USB D-/D+ | USB Host 功能占用，不可作他用 |

### 8.2 GPIO 分配

| GPIO | 当前用途 | 备注 |
|------|---------|------|
| 4 | TS3USB221 SEL | USB 切换控制 |
| 18 | I2C-0 SCL | LG DDC 时钟线 |
| 47 | I2C-0 SDA | LG DDC 数据线 |
| 5 | I2C-1 SCL (预留) | Redmi DDC 时钟线 |
| 6 | I2C-1 SDA (预留) | Redmi DDC 数据线 |
| 19 | USB D- | USB Host 键盘 |
| 20 | USB D+ | USB Host 键盘 |

### 8.3 双 I2C 总线

ESP32-S3 有两个硬件 I2C 控制器，可同时驱动两条独立总线：

```c
// ESP-IDF 新版驱动
i2c_master_bus_handle_t bus_0, bus_1;

// 总线 0: LG
bus_cfg.i2c_port = I2C_NUM_0;
bus_cfg.scl_io_num = 18; bus_cfg.sda_io_num = 47;

// 总线 1: Redmi (预留)
bus_cfg.i2c_port = I2C_NUM_1;
bus_cfg.scl_io_num = 5; bus_cfg.sda_io_num = 6;
```

---

## 9. 调试经验

### 9.1 已解决的问题

| 症状 | 原因 | 解决方案 |
|------|------|---------|
| 所有 I2C 地址都响应 | SDA/SCL/GND 接错，总线短路 | 重新确认分线板奇偶排列 |
| ESP32 "waiting for download" | GPIO 0 被拉低 | 避开 GPIO 0, 45, 46 |
| ESP32 无限重启 | GPIO 45 被拉低 | 同上 |
| 无 I2C 设备 | 缺少上拉电阻 | 加 4.7kΩ 上拉到 3.3V |
| 标准 DDC 读取正常但写入无效 (LG) | 需要 Alt 模式 | 源地址 0x50 + VCP 0xF4 |
| 写入 ACK 但不切换 (Redmi) | 从空闲端口发命令被忽略 | ESP32 必须串联在活跃端口 |

### 9.2 Backlog 问题

| 症状 | 可能原因 | 备注 |
|------|---------|------|
| DDC 读取 VCP 0x60 持续失败 | GPU 占用总线 / 时序问题 / 回复格式偏移 | 非关键功能，暂不处理 |

### 9.3 无万用表验证方法

利用 ESP32 GPIO 内部上拉电阻代替万用表：

1. 将分线板插在显示器上（显示器提供 GND 参考）
2. 各针脚接到 ESP32 GPIO，设置 `INPUT_PULLUP`
3. 读取电平：GND 引脚 = LOW，其他 = HIGH
4. 根据 GND 分布模式判断分线板排列

---

## 10. DDC 对显示器的影响

### 10.1 读取轮询安全性

- DDC/CI 使用 HDMI Pin 15/16（I2C），视频信号使用 Pin 1-12（TMDS），物理完全独立
- 一次 DDC 读取约几十字节，50kHz 下耗时不到几毫秒
- 显示器本身就预期被频繁查询（EDID、ddcutil、BetterDisplay 等）
- **500ms 轮询间隔对画面和性能完全无影响**

---

## 11. 参考资料

### 11.1 LG DDC Alt 模式

- [BetterDisplay Discussion #4246](https://github.com/waydabber/BetterDisplay/discussions/4246) — 34GS95QE 的 Alt 模式讨论
- [m1ddc PR #52](https://github.com/waydabber/m1ddc/pull/52) — 修复 LG Alt 模式校验和计算
- [ddcutil Wiki: LG 输入源切换](https://github.com/rockowitz/ddcutil/wiki/Switching-input-source-on-LG-monitors) — LG DDC Alt 模式文档
- [BetterDisplay Issue #1923](https://github.com/waydabber/BetterDisplay/issues/1923) — LG Alt 模式最初发现

### 11.2 已知支持 Alt 模式的 LG 型号

GP850, QP750, GP950, WP950C, QP88D, UL550/500, GP750, 28MQ780, UP850, UN880, GQ850, UQ85R, WQ75C, WQ60C, WQ95C, UP600, **34GS95QE** 等。

---

## 12. 下一步计划

### 12.1 近期（等待硬件到货）

1. 收到分线板 + 母对母后，验证 Redmi 串联方案
2. 确认 Redmi HDMI1 的 VCP 0x60 值
3. 实现双显示器同步切换
4. 添加物理按钮（GPIO 触发切换）

### 12.2 远期

5. 所有功能面包板验证通过后，设计 PCB
6. 嘉立创打样 + SMT 贴片
7. 整理进成品外壳

### 12.3 Backlog

- DDC 读取 VCP 0x60（读取失败，非关键功能）
- OSD 手动切换自动同步 USB（依赖 DDC 读取）

---

## 附录 A：工具代码

### A.1 分线板引脚探测器

```c
// Arduino IDE, ESP32-S3
#include <Arduino.h>

int pins[] = {12, 11, 10, 9, 46, 3, 8, 18, 17, 16};
int numPins = 10;

void setup() {
  Serial.begin(115200);
  delay(1000);
  for (int i = 0; i < numPins; i++) pinMode(pins[i], INPUT_PULLUP);
  Serial.println("=== HDMI Breakout Pin Mapper ===");
}

void loop() {
  for (int i = 0; i < numPins; i++) {
    int val = digitalRead(pins[i]);
    Serial.print("位置 "); Serial.print(i + 1); Serial.print(": ");
    Serial.println(val == LOW ? "LOW  ← GND!" : "HIGH");
  }
  Serial.println();
  delay(5000);
}
```

### A.2 DDC SDA 自动探测器

```c
// Arduino IDE, ESP32-S3
#include <Wire.h>

int sdaCandidates[] = {39, 36, 35, 2, 48, 47, 21, 20};
int numCandidates = 8;
int sclPin = 18;

void setup() {
  Serial.begin(115200);
  delay(1000);
  for (int i = 0; i < numCandidates; i++) {
    Wire.begin(sdaCandidates[i], sclPin);
    delay(100);
    Wire.beginTransmission(0x37);
    byte error = Wire.endTransmission();
    Serial.print("SDA=GPIO"); Serial.print(sdaCandidates[i]);
    Serial.println(error == 0 ? " >>> 0x37 FOUND! <<<" : " no response");
    Wire.end();
    delay(200);
  }
}

void loop() { delay(10000); }
```

### A.3 LG Alt 模式切换器 (Arduino 版，用于独立测试)

```c
// Arduino IDE, ESP32-S3
#include <Wire.h>

#define DDC_ADDR 0x37

void ddcWriteLG(byte vcp, uint16_t value) {
  byte msg[] = {0x50, 0x84, 0x03, vcp,
                (byte)(value >> 8), (byte)(value & 0xFF)};
  byte chk = 0x6E;
  for (int i = 0; i < 6; i++) chk ^= msg[i];

  Wire.beginTransmission(DDC_ADDR);
  Wire.write(msg, 6);
  Wire.write(chk);
  byte err = Wire.endTransmission();
  Serial.println(err == 0 ? "ACK" : "NACK");
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Wire.begin(47, 18);
  Wire.setClock(50000);
  Serial.println("1=HDMI1 2=HDMI2 3=DP1 4=DP2");
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();
    switch (c) {
      case '1': ddcWriteLG(0xF4, 0x0090); break;
      case '2': ddcWriteLG(0xF4, 0x0091); break;
      case '3': ddcWriteLG(0xF4, 0x00D0); break;
      case '4': ddcWriteLG(0xF4, 0x00D1); break;
    }
  }
}
```

---

## 附录 B：版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1 | — | 初始文档，HDMI 分线板验证 + LG DDC Alt 模式发现 |
| v2 | 2026-04-04 | 添加 Redmi 显示器测试结果、最终方案设计 |
| **v3** | **2026-04-05** | ESP-IDF 主程序实现（USB Host + DDC 写入 + USB 切换），DDC 读取诊断，USB 2.0/3.0 分析，完整软件架构文档 |
