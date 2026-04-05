# ESP32-S3 KVM Hub — 概念设计文档 v1

> 最后更新：2026-04-05
> 阶段：概念设计，待面包板验证完成后进入 PCB 设计

---

## 1. 项目概述

### 1.1 目标

将面包板原型整合为一块完整的 PCB，做成一个独立的 KVM Hub 桌面设备。一键在 Gaming PC (Windows) 和 MacBook Pro 之间切换两台显示器输入源 + 全部 USB 外设。

### 1.2 设计原则

- **零性能折损**：视频信号不经过任何额外芯片，HDMI 直通走铜线
- **零延迟感知**：USB 2.0 hub 级联延迟 < 1μs，对 8kHz 鼠标也可忽略
- **独立于电脑**：ESP32 单独控制，不需要在 PC/Mac 上装任何软件
- **桌搭美观**：集成小屏幕显示状态，最终装进外壳

---

## 2. 接口清单

### 2.1 完整接口列表

| 编号 | 接口 | 类型 | 方向 | 用途 |
|------|------|------|------|------|
| 1 | HDMI (DDC only) | HDMI 母座 | IN | LG 显示器 DDC 控制（仅取 SCL/SDA/GND） |
| 2 | HDMI pass-through A-in | HDMI 母座 | IN | PC → Redmi 显示器 HDMI1（视频+DDC） |
| 3 | HDMI pass-through A-out | HDMI 母座 | OUT | → Redmi HDMI1 口 |
| 4 | HDMI pass-through B-in | HDMI 母座 | IN | MacBook → Redmi 显示器 HDMI2（视频+DDC） |
| 5 | HDMI pass-through B-out | HDMI 母座 | OUT | → Redmi HDMI2 口 |
| 6 | USB-B/C (upstream) | USB 母座 | OUT | 连接 Gaming PC |
| 7 | USB-B/C (upstream) | USB 母座 | OUT | 连接 MacBook |
| 8-15 | USB-A x8 (downstream) | USB-A 母座 | IN | 外设：鼠标x2、键盘x1、麦克风x1、DAC x1、冗余x3 |
| 16 | USB-C (power) | USB-C 母座 | IN | 5V 供电（充电器） |
| 17 | USB-C (control) | USB-C 母座 | IN | 控制键盘（ESP32 USB Host） |
| 18 | FPC/排针 (display) | FPC 或排针 | OUT | 状态显示小屏幕 |

### 2.2 接口分组

```
前面板（朝向用户）:
  USB-A x8 (外设口)
  USB-C (控制键盘)
  小屏幕

后面板（朝向桌子后方）:
  HDMI x5 (1个 DDC-only + 2对直通)
  USB x2 (上行到 PC 和 Mac)
  USB-C (供电)
```

---

## 3. 系统架构

### 3.1 信号通路

系统内有四条完全独立的信号通路，互不干扰：

**通路 1：视频信号（HDMI TMDS）**
```
Gaming PC ─── HDMI ──→ LG HDMI1           (不经过 hub)
MacBook   ─── DP ────→ LG DP1             (不经过 hub)
Gaming PC ─── HDMI ──→ [hub 直通] ──→ Redmi HDMI1
MacBook   ─── HDMI ──→ [hub 直通] ──→ Redmi HDMI2
```
视频信号在 PCB 上只是 19 根铜线直连，不经过任何芯片。4K 360Hz、8K 信号均无折损。

**通路 2：DDC/CI 控制信号（I2C）**
```
ESP32 I2C-0 ──→ LG HDMI DDC (Pin15/16)
ESP32 I2C-0 ──→ Redmi HDMI1 DDC (从直通线路 T 型分接)
ESP32 I2C-1 ──→ Redmi HDMI2 DDC (从直通线路 T 型分接)
```
50kHz I2C，仅几十字节的命令，对视频信号零影响。

**通路 3：USB 外设数据**
```
8x USB 外设 ──→ FE1.1s hub 级联 ──→ TS3USB221 ──→ PC 或 Mac
```
ESP32 不在此通路上，仅通过 GPIO 控制 TS3USB221 的 SEL 引脚。

**通路 4：控制通路**
```
控制键盘 ──→ ESP32 USB Host (独立 USB-C 口)
ESP32 GPIO ──→ TS3USB221 SEL
ESP32 I2C ──→ DDC/CI
ESP32 SPI ──→ 状态显示屏
```

### 3.2 架构框图

```
┌──────────────────────────────────────────────────────────────────┐
│                         KVM Hub PCB                              │
│                                                                  │
│  ┌─────────────┐                                                 │
│  │  ESP32-S3    │──GPIO4──→ TS3USB221 SEL                        │
│  │             │──I2C-0──→ LG DDC + Redmi HDMI1 DDC             │
│  │             │──I2C-1──→ Redmi HDMI2 DDC                      │
│  │             │──SPI────→ 状态显示屏                             │
│  │             │──USB────→ 控制键盘 (USB-C 口)                   │
│  └─────────────┘                                                 │
│                                                                  │
│  ┌─────────────┐     ┌───────────────┐                           │
│  │ TS3USB221   │◄───│ FE1.1s (root) │                           │
│  │ USB 2.0 mux │     └──┬─────────┬──┘                           │
│  └──┬──────┬──┘        │         │                               │
│     │      │       ┌────┴───┐ ┌───┴────┐                         │
│  To PC  To Mac    │FE1.1s A│ │FE1.1s B│                         │
│                   └─┬┬┬┬──┘ └──┬┬┬┬─┘                           │
│                     ││││       ││││                               │
│                   Port1-4    Port5-8                              │
│                                                                  │
│  ┌──────────────────────────────────────┐                        │
│  │ HDMI 直通 (19 pin copper, DDC tap)   │                        │
│  │  A: PC HDMI in ──────→ Redmi HDMI1   │                        │
│  │  B: Mac HDMI in ─────→ Redmi HDMI2   │                        │
│  └──────────────────────────────────────┘                        │
│                                                                  │
│  ┌──────────┐                                                    │
│  │ CH224K   │ USB-C PD sink → 5V rail                            │
│  └──────────┘                                                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. 芯片清单 (BOM)

### 4.1 主要 IC

| 芯片 | 数量 | 封装 | 功能 | 备注 |
|------|------|------|------|------|
| ESP32-S3-WROOM-1 | 1 | 模块 | 主控（I2C, GPIO, USB Host, SPI） | 直接用模块焊接，省去射频设计 |
| TS3USB221 | 1 | TSSOP-10 | USB 2.0 模拟开关 | SEL 引脚接 ESP32 GPIO4 |
| FE1.1s | 3 | SSOP-28 | USB 2.0 4-port hub | 1 root + 2 sub, 级联出 8 口 |
| CH224K | 1 | ESSOP-10 | USB-C PD sink | 锁定 5V 输出，支持 5V/3A |
| ST7789 屏幕 | 1 | FPC | 1.69" / 2.0" IPS 彩色屏 | SPI 接口，240x280 或 240x320 |

### 4.2 被动元件

| 元件 | 数量 | 规格 | 用途 |
|------|------|------|------|
| 4.7kΩ 电阻 | 6 | 0402/0603 | I2C 上拉 (3 组 x2) |
| 12MHz 晶振 | 3 | 3225 | FE1.1s 时钟 (每颗一个) |
| 100nF 去耦电容 | ~15 | 0402 | 每颗 IC 旁边 |
| 10μF 电容 | ~5 | 0805 | 电源滤波 |
| ESD 保护 | 若干 | SOT-23 | USB 端口 ESD 保护（可选） |

### 4.3 连接器

| 连接器 | 数量 | 用途 |
|--------|------|------|
| HDMI Type-A 母座 | 5 | 1 DDC-only + 2 对直通 |
| USB-A 母座 | 8 | 外设下行口 |
| USB-C 母座 | 3 | 供电 + 控制键盘 + 选其一做上行 |
| USB-B 或 USB-C 母座 | 2 | 上行到 PC 和 Mac（可用 USB-C） |
| FPC 连接器 | 1 | 屏幕接口 |

---

## 5. USB Hub 详细设计

### 5.1 FE1.1s 级联拓扑

```
                    ┌──────────────┐
                    │ TS3USB221    │
                    │ Port1=PC     │
                    │ Port2=Mac    │
                    └──────┬───────┘
                           │ USB upstream
                    ┌──────┴───────┐
                    │ FE1.1s root  │
                    │ 4 downstream │
                    └┬──┬──┬──┬───┘
                     │  │  │  │
              ┌──────┘  │  │  └──── (unused / 备用)
              │         │  └─────── (unused / 备用)
              │         │
       ┌──────┴──────┐  ┌──────┴──────┐
       │ FE1.1s (A)  │  │ FE1.1s (B)  │
       │ 4 ports     │  │ 4 ports     │
       └┬──┬──┬──┬──┘  └┬──┬──┬──┬──┘
        │  │  │  │       │  │  │  │
       P1 P2 P3 P4     P5 P6 P7 P8
```

Root hub 的 4 个下行口中用 2 个接 sub-hub，剩余 2 个可以作为备用口或直接引出。

### 5.2 性能分析

| 参数 | 值 | 说明 |
|------|-----|------|
| 上行带宽 | 480 Mbps | USB 2.0 High Speed |
| 级联层数 | 2 | Root + Sub, 远低于 USB 规范的 5 层限制 |
| 单层延迟 | ~0.4 μs | FE1.1s 典型转发延迟 |
| 总延迟 | ~0.8 μs | 2 层级联，对 8kHz 鼠标 (125μs) 占 0.64% |
| 最大轮询率 | 8000 Hz | USB 2.0 HS 微帧 = 125μs |

### 5.3 实际带宽用量

| 设备 | 带宽 | 说明 |
|------|------|------|
| 2kHz 鼠标 x2 | ~640 kbps | 每秒 2000 报告 x ~40 字节 |
| 键盘 | ~64 kbps | 每秒 1000 报告 x ~8 字节 |
| USB 麦克风 | ~1-3 Mbps | 16bit/48kHz 单声道 |
| HiFi DAC | ~4.6 Mbps | 24bit/96kHz 立体声 |
| **合计** | **< 10 Mbps** | 480 Mbps 管道利用率 < 3% |

### 5.4 FE1.1s 关键参数

| 参数 | 值 |
|------|-----|
| 芯片 | FE1.1s (Terminus Technology) |
| 封装 | SSOP-28 |
| 外部晶振 | 12MHz |
| 工作电压 | 3.3V (内部 LDO 也可从 5V 供) |
| 每口电流限制 | 可配置，默认 500mA |
| 嘉立创可贴片 | ✅ 常规封装 |

---

## 6. HDMI 直通设计

### 6.1 设计原则

HDMI 直通部分不含任何有源器件。PCB 上一对 HDMI 母座之间，19 根信号线直连走铜线。ESP32 仅从 Pin 15 (SCL) 和 Pin 16 (SDA) 做 T 型分接引出。

```
HDMI 母座 (IN) ──── 19 pin 直连 ────→ HDMI 母座 (OUT)
                         │
                    Pin 15 (SCL) ──→ ESP32 I2C SCL
                    Pin 16 (SDA) ──→ ESP32 I2C SDA
                    Pin 5  (GND) ──→ ESP32 GND
```

### 6.2 PCB 走线要求

| 信号 | 阻抗要求 | 走线规则 |
|------|---------|---------|
| TMDS 差分对 (Pin 1-12) | 100Ω 差分 | 等长、紧耦合、不打过孔、尽量短且直 |
| DDC (Pin 15-16) | 无要求 | 50kHz I2C，随便走 |
| CEC (Pin 13) | 无要求 | 直连 |
| +5V (Pin 18) | 无要求 | 直连，走线加粗 |
| HPD (Pin 19) | 无要求 | 直连 |

### 6.3 PCB 层叠建议

四层板结构：

```
Layer 1 (Top):    信号层 — HDMI TMDS 差分对 + USB 差分对
Layer 2 (Inner1): GND 完整铺铜 — 参考平面
Layer 3 (Inner2): 电源 (5V / 3.3V)
Layer 4 (Bottom): 信号层 — I2C, GPIO, SPI, 低速信号
```

嘉立创四层板阻抗控制选项可以直接指定 100Ω 差分阻抗，计算器会给出线宽和间距。

### 6.4 LG 显示器接口

LG 不需要直通，因为 ESP32 只读写 DDC，不拦截视频。所以 LG 那路只用一个 HDMI 母座，PCB 上只引出 Pin 5、15、16 三根线到 ESP32，其他引脚悬空即可。或者更简单：用一个 3pin 排针代替 HDMI 母座，从 LG 的 HDMI 分线板飞线过来。

---

## 7. 供电设计

### 7.1 功耗估算

| 模块 | 电压 | 电流 | 说明 |
|------|------|------|------|
| ESP32-S3 | 3.3V | ~200 mA | 含 WiFi/BLE 关闭 |
| FE1.1s x3 | 3.3V | ~50 mA | 每颗 ~15mA |
| TS3USB221 | 3.3V | < 1 mA | 模拟开关，极低功耗 |
| ST7789 屏幕 | 3.3V | ~20 mA | 背光 + 驱动 |
| USB 外设供电 | 5V | ~1500 mA | HID 设备 + DAC + 麦克风 |
| CH224K | — | < 1 mA | PD sink 控制 |
| **合计** | | **~1.8 A @ 5V** | |

### 7.2 供电方案

```
USB-C PD (5V/3A) ──→ CH224K ──→ 5V rail
                                   │
                                   ├──→ USB 外设口 (5V 直供)
                                   ├──→ FE1.1s (内部 LDO 降至 3.3V)
                                   │
                                   └──→ AMS1117-3.3 ──→ 3.3V rail
                                                          │
                                                          ├──→ ESP32-S3
                                                          ├──→ TS3USB221
                                                          └──→ ST7789 屏幕
```

5V/3A = 15W，实际功耗约 9W，裕量充足。

### 7.3 CH224K 配置

CH224K 通过电阻配置请求的 PD 电压。请求 5V 时 CFG 引脚全部悬空即可（默认 5V）。

---

## 8. 状态显示屏

### 8.1 硬件选型

| 参数 | 推荐值 |
|------|--------|
| 屏幕 | ST7789 IPS |
| 尺寸 | 1.69" (240x280) 或 2.0" (240x320) |
| 接口 | SPI (4-wire) |
| 背光 | 内置，3.3V 供电 |

### 8.2 GPIO 分配

| GPIO | 功能 | 说明 |
|------|------|------|
| GPIO 35 | SPI MOSI (DIN) | 数据 |
| GPIO 36 | SPI CLK (SCK) | 时钟 |
| GPIO 37 | CS | 片选 |
| GPIO 38 | DC | 数据/命令切换 |
| GPIO 39 | RST | 复位（可选，也可接 RC 延迟上电复位） |

### 8.3 可显示的信息

| 信息 | 数据来源 | 说明 |
|------|---------|------|
| 当前模式 (Windows / MacBook) | ESP32 内部状态 | 大字显示 + 颜色区分 |
| LG 输入源 | DDC/CI VCP 0x60 读取 | HDMI1 / DP1 |
| Redmi 输入源 | DDC/CI VCP 0x60 读取 | HDMI1 / HDMI2 |
| DDC 连接状态 | I2C 总线健康检查 | 3 路各自显示在线/离线 |
| 运行时间 | esp_timer_get_time() | HH:MM:SS |
| 今日切换次数 | 计数器 | — |
| 上次切换时间 | 时间戳 | 几分钟前 / 刚刚 |

### 8.4 无法显示的信息

| 信息 | 原因 |
|------|------|
| USB 设备轮询率 | ESP32 不在 USB 数据通路上，无法观测 |
| USB 设备带宽 | 同上，FE1.1s 不对外报告流量 |
| 显示器分辨率/刷新率 | EDID 可读但解析复杂，优先级低 |

### 8.5 变通方案

如需显示轮询率等信息，可在 PC/Mac 端跑一个轻量后台程序，通过 ESP32 的蓝牙 (BLE) 或串口发送数据。但这违背"独立于电脑"的设计原则，作为可选功能。

---

## 9. ESP32-S3 GPIO 完整分配

| GPIO | 功能 | 模块 |
|------|------|------|
| 4 | TS3USB221 SEL | USB 切换 |
| 18 | I2C-0 SCL | LG DDC + Redmi HDMI1 DDC |
| 47 | I2C-0 SDA | LG DDC + Redmi HDMI1 DDC |
| 5 | I2C-1 SCL | Redmi HDMI2 DDC |
| 6 | I2C-1 SDA | Redmi HDMI2 DDC |
| 19 | USB D- | USB Host (控制键盘) |
| 20 | USB D+ | USB Host (控制键盘) |
| 35 | SPI MOSI | 状态显示屏 |
| 36 | SPI CLK | 状态显示屏 |
| 37 | SPI CS | 状态显示屏 |
| 38 | SPI DC | 状态显示屏 |
| 39 | SPI RST | 状态显示屏 (可选) |
| — | 预留若干 | 物理按钮、LED 指示灯等 |

**禁用 GPIO：** 0 (启动模式)、45 (启动模式)、46 (慎用)

---

## 10. PCB 设计参数

### 10.1 板子规格

| 参数 | 建议值 |
|------|--------|
| 层数 | 4 层 |
| 板厚 | 1.6mm |
| 铜厚 | 1oz (外层), 0.5oz (内层) |
| 阻抗控制 | 是，100Ω 差分 (TMDS + USB) |
| 表面处理 | HASL 或沉金 |
| 最小线宽/间距 | 5mil / 5mil |
| 尺寸 | 预估 120mm x 80mm |

### 10.2 嘉立创制造

| 服务 | 说明 |
|------|------|
| PCB 打样 | 四层板 5 片，约 50-100 元 |
| SMT 贴片 | 主要 IC + 被动元件，约 100-200 元 |
| 钢网 | 含在 SMT 服务中 |
| BOM 匹配 | 嘉立创商城有 FE1.1s、CH224K、AMS1117 等 |
| **总计** | **约 200-400 元（含元件）** |

### 10.3 手焊 vs SMT

| 元件 | 封装 | 建议 |
|------|------|------|
| ESP32-S3-WROOM-1 | 模块 (castellated) | 可手焊，推荐 SMT |
| TS3USB221 | TSSOP-10 | 可手焊，推荐 SMT |
| FE1.1s | SSOP-28 | 可手焊（0.65mm pitch），推荐 SMT |
| CH224K | ESSOP-10 | SMT |
| 0402/0603 电阻电容 | 贴片 | SMT |
| HDMI/USB 连接器 | 插件 | 手焊（SMT 不好做插件） |

---

## 11. 不在范围内的功能

| 功能 | 原因 |
|------|------|
| 视频采集 / 录屏 | 需要 HDMI 接收芯片 + 视频编码器，完全不同的产品 |
| USB 3.0 切换 | TS3USB221 仅支持 USB 2.0；当前外设全是 USB 2.0 |
| 雷电 4 接口 | 需要 Intel 认证控制器芯片，不可自制 |
| 无线控制 | ESP32 有 BLE/WiFi 能力，但当前优先做有线方案 |

### 11.1 未来升级路径

| 功能 | 升级方案 |
|------|---------|
| USB 3.0 | 替换 TS3USB221 为 USB 3.0 mux (CBTL02043A)，或外接现成切换器拆解接 GPIO |
| 更多显示器 | 增加 I2C 总线或用 I2C multiplexer (TCA9548A) |
| 无线切换 | ESP32 BLE 已内置，加手机 App 控制 |
| 宏键盘集成 | 控制键盘口可接自制宏键盘，通过 HID 报告触发切换 |

---

## 12. 开发路线

### 12.1 阶段划分

| 阶段 | 内容 | 状态 |
|------|------|------|
| **Phase 1** | 面包板验证：LG DDC 写入 + USB 切换 | ✅ 完成 |
| **Phase 2** | DDC 读取调试 + OSD 自动同步 | 🔧 进行中 |
| **Phase 3** | Redmi 显示器串联验证（母转母 + 分线板） | ⏳ 等待硬件 |
| **Phase 4** | 双显示器 + USB 完整切换验证 | ⏳ |
| **Phase 5** | 原理图设计 (KiCad / 立创 EDA) | ⏳ |
| **Phase 6** | PCB layout + 阻抗仿真 | ⏳ |
| **Phase 7** | 嘉立创打样 + SMT | ⏳ |
| **Phase 8** | 焊接连接器 + 调试 | ⏳ |
| **Phase 9** | 外壳设计 + 装配 | ⏳ |

### 12.2 阶段依赖

```
Phase 1 ✅
  └→ Phase 2 🔧 (DDC 读取)
       └→ Phase 3 ⏳ (需要硬件: 分线板 + 母转母)
            └→ Phase 4 ⏳ (全功能验证)
                 └→ Phase 5-9 ⏳ (PCB 设计到成品)
```

**关键原则：所有功能必须在面包板上验证通过后才进入 PCB 设计。**

---

## 13. 待购硬件清单

| 物品 | 数量 | 用途 | 优先级 |
|------|------|------|--------|
| HDMI 分线板 | 2 | Redmi 串联测试 | Phase 3 |
| HDMI 母对母转接头 | 2 | Redmi 串联测试 | Phase 3 |
| 4.7kΩ 电阻 | 4 | I2C-1 上拉 + 备用 | Phase 3 |
| ST7789 1.69" 屏幕 | 1 | 状态显示测试 | Phase 4 |
| FE1.1s 芯片 | 3 | USB hub 面包板测试（可选，或直接上 PCB） | Phase 5 |

---

## 附录 A：参考资料

- FE1.1s datasheet: Terminus Technology USB 2.0 hub controller
- CH224K datasheet: WCH USB-C PD sink controller
- TS3USB221 datasheet: TI USB 2.0 high-speed mux
- ST7789 datasheet: Sitronix TFT LCD driver
- 嘉立创阻抗计算器: https://tools.jlcpcb.com/impedanceCalculation
- HDMI 2.1 specification: TMDS 差分对阻抗要求 100Ω

## 附录 B：版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| **v1** | **2026-04-05** | 初始概念设计：完整接口清单、芯片选型、USB hub 级联拓扑、HDMI 直通设计、供电方案、屏幕集成、GPIO 分配、PCB 参数 |
