# ESP32-S3 DDC/CI KVM 切换器 — 技术文档 v2

> 最后更新：2026-04-04
> 阶段：原型验证完成，等待硬件到货

---

## 1. 项目概述

### 1.1 目标

用 ESP32-S3 实现完全独立于电脑的一键 KVM 切换，在 MacBook Pro 和 Gaming PC 之间切换两台显示器输入源 + USB 外设。

### 1.2 设备清单

| 设备 | 型号 | 角色 |
|------|------|------|
| 主显示器 | **LG 34GS95QE** | 超宽屏，DDC/CI Alt 模式 |
| 副显示器 | **Redmi G Pro 27** | 小米副屏，标准 DDC/CI |
| 电脑 A | Gaming PC | Windows |
| 电脑 B | MacBook Pro | macOS |
| 控制器 | ESP32-S3 Dev Module | Arduino IDE 2.3.8 |

### 1.3 最终接线方案（待实施）

```
┌─────────────────────────────────────────────────────────┐
│                    LG 34GS95QE                          │
│              HDMI1 ← Gaming PC                          │
│              DP1   ← MacBook Pro                        │
│              HDMI DDC ← ESP32 I2C-0 (通过分线板串联)      │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                  Redmi G Pro 27                          │
│              HDMI1 ← Gaming PC (通过分线板A串联)          │
│              HDMI2 ← MacBook Pro (通过分线板B串联)        │
│              HDMI1 DDC ← ESP32 I2C-0 或 I2C-1            │
│              HDMI2 DDC ← ESP32 I2C-1 或 I2C-0            │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                     ESP32-S3                             │
│              I2C-0: GPIO18(SCL) + GPIO47(SDA)            │
│              I2C-1: GPIO5(SCL) + GPIO6(SDA)（待定）       │
│              按钮: GPIO4（待定）                          │
│              TS3USB221 SEL: GPIO（待定）                   │
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

### 2.2 GND 引脚验证结果

**上排 GND（利用 ESP32 INPUT_PULLUP 探测）：**

| 位置 | Pin | 读数 | 说明 |
|------|-----|------|------|
| 3 | Pin 5 | LOW | TMDS Data1 Shield / GND ✓ |
| 6 | Pin 11 | LOW | TMDS Clock Shield / GND ✓ |
| 9 | Pin 17 | HIGH | DDC GND（可能接触不同，但仍是GND） |

**下排 GND：**

| 位置 | Pin | 读数 |
|------|-----|------|
| 2 | Pin 4 | LOW (GPIO38) |
| 3 | Pin 6 | LOW (GPIO37) |
| 6 | Pin 12 | LOW (GPIO0 → 触发下载模式确认) |

### 2.3 DDC 引脚位置

| 信号 | HDMI Pin | 分线板位置 |
|------|----------|-----------|
| **SCL** | Pin 15 | 上排第 8 针 |
| **SDA** | Pin 16 | 下排第 9 针 |
| **GND** | Pin 5 | 上排第 3 针 |

### 2.4 验证方法（无万用表）

利用 ESP32 GPIO 内部上拉电阻代替万用表：

1. 将分线板插在显示器上（显示器提供 GND 参考）
2. 各针脚接到 ESP32 GPIO，设置 `INPUT_PULLUP`
3. 读取电平：GND 引脚 = LOW，其他 = HIGH
4. 根据 GND 分布模式判断奇偶分排 vs 顺序排列

**关键代码见附录 A.1**

### 2.5 SDA 自动探测

固定 SCL (GPIO 18)，遍历下排所有非 GND 引脚，尝试扫描 0x37：

- GPIO 47（下排位置 9）= **三次测试均命中 0x37** ← 确认为 SDA
- GPIO 21、20 偶尔也响应（相邻引脚串扰，不影响）

**关键代码见附录 A.2**

### 2.6 HDMI Type A 标准引脚参考

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

## 3. LG 34GS95QE — DDC/CI Alt 模式

### 3.1 发现过程

1. 标准协议（0x51 + VCP 0x60）可以**读取**输入源，但**写入无效**
2. ControlMyMonitor 也无法写入 VCP 0x60
3. GitHub BetterDisplay 讨论 (#4246) 发现 LG 新型号使用非标准 "DDC Alt" 协议
4. ddcutil wiki 确认：VCP 代码为 **0xF4**，源地址为 **0x50**

### 3.2 协议对比

| 参数 | 标准 DDC/CI | LG Alt 模式 |
|------|-----------|------------|
| I2C 地址 | 0x37 | 0x37（相同） |
| 源地址字节 | **0x51** | **0x50** |
| VCP 代码 | **0x60** | **0xF4** |
| 校验和种子 | 0x6E ⊕ 0x51 ⊕ ... | 0x6E ⊕ **0x50** ⊕ ... |

### 3.3 输入源值映射

| 输入端口 | Alt 模式值 (VCP 0xF4) | 标准读取值 (VCP 0x60) |
|---------|---------------------|---------------------|
| HDMI-1 | **0x0090** (144) | 0x0F (15) |
| HDMI-2 | **0x0091** (145) | 0x10 (16) |
| DP-1 | **0x00D0** (208) | 0x11 (17) |
| DP-2 | **0x00D1** (209) | 0x12 (18) |

### 3.4 数据包格式

**写入命令（切换输入源）：**

```
I2C START → 0x6E(W) → ACK
  [0] 0x50        ← 源地址（LG Alt）
  [1] 0x84        ← 长度 | 0x80（4字节负载）
  [2] 0x03        ← VCP Set 操作码
  [3] 0xF4        ← VCP 代码（LG Alt）
  [4] value_high  ← 值高字节
  [5] value_low   ← 值低字节
  [6] checksum    ← 校验和
I2C STOP
```

**校验和：** `checksum = 0x6E ⊕ 全部数据字节`

**示例（切到 DP-1）：**

```
0x50 0x84 0x03 0xF4 0x00 0xD0 → checksum = 0x6E⊕0x50⊕0x84⊕0x03⊕0xF4⊕0x00⊕0xD0 = 0xA5
```

### 3.5 I2C 总线设备

```
Scan: 0x37 0x3A 0x49 0x50 0x54 0x58 0x59  (7 devices, 稳定)
```

- 0x37 = DDC/CI
- 0x50 = EDID
- 其他 = 显示器内部设备

### 3.6 验证结果

- ✅ ESP32 通过 HDMI DDC 成功切换 LG 输入源（HDMI ↔ DP，双向）
- ✅ 切换延迟约 1-2 秒
- ✅ I2C 30-50kHz 均稳定工作

### 3.7 已知支持 Alt 模式的 LG 型号

GP850, QP750, GP950, WP950C, QP88D, UL550/500, GP750, 28MQ780, UP850, UN880, GQ850, UQ85R, WQ75C, WQ60C, WQ95C, UP600, **34GS95QE** 等。

### 3.8 参考资料

- [BetterDisplay Discussion #4246](https://github.com/waydabber/BetterDisplay/discussions/4246)
- [m1ddc PR #52](https://github.com/waydabber/m1ddc/pull/52)
- [ddcutil Wiki: LG 输入源切换](https://github.com/rockowitz/ddcutil/wiki/Switching-input-source-on-LG-monitors)
- [BetterDisplay Issue #1923](https://github.com/waydabber/BetterDisplay/issues/1923)

---

## 4. Redmi G Pro 27 — 标准 DDC/CI（不稳定读取）

### 4.1 特性

| 特性 | 状态 |
|------|------|
| DDC/CI 读取 VCP 0x60 | ❌ 不稳定（返回随机值） |
| DDC/CI 写入 VCP 0x60 | ✅ 可用（从活跃端口） |
| ControlMyMonitor 读取 | ⚠️ 偶尔有效 |
| ControlMyMonitor 写入 | ✅ 有效（从 PC 端 DP1） |
| m1ddc 写入 | ✅ 有效（从 Mac 端 DP/HDMI） |
| OSD DDC/CI 开关 | 无此选项 |

### 4.2 关键发现

**DDC 写入只接受来自活跃（当前显示的）输入端口的命令。**

- ESP32 接在空闲 HDMI1 口 → DDC 写入被忽略
- PC 通过 DP1（活跃）发 DDC 命令 → ✅ 切换成功
- Mac 通过 HDMI2（活跃）发 DDC 命令 → ✅ 切换成功
- 一旦显示器切走当前端口，该端口就失去 DDC 控制能力

**结论：ESP32 必须串联在活跃端口的 HDMI 线路中，与视频信号共享 DDC 总线。**

### 4.3 已确认的输入源值

| 输入端口 | VCP 0x60 值 | 验证方式 | 验证结果 |
|---------|------------|---------|---------|
| DP-1 | **15** (0x0F) | m1ddc `set input 15` | ✅ 从 HDMI2 切到 DP1 成功 |
| HDMI-2 | **17** (0x11) | CMM `/SetValue ... 60 17` | ✅ 从 DP1 切到 HDMI2 成功 |
| HDMI-1 | **待确认** | 需要硬件到位后测试 | |
| DP-2 | **16** (0x10)? | CMM 显示 Max=14，不确定 | |

### 4.4 协议参数

| 参数 | 值 |
|------|-----|
| I2C 地址 | 0x37 |
| 源地址 | **0x51**（标准） |
| VCP 代码 | **0x60**（标准） |
| I2C 速率 | 30kHz（推荐，此显示器较慢） |

### 4.5 暴力测试记录

| 测试 | 范围 | 结果 |
|------|------|------|
| ESP32 空闲 HDMI1, src=0x51, VCP=0x60, 0x00-0xFF | 256 值 | ❌ 全部无反应（空闲端口） |
| ESP32 空闲 HDMI1, src=0x50, VCP=0x60, 0x00-0xFF | 256 值 | ❌ 全部无反应 |
| ESP32 空闲 HDMI1, src=0x51, VCP=0xF4, 0x00-0xFF | 256 值 | ❌ 全部无反应 |
| ESP32 空闲 HDMI1, src=0x50, VCP=0xF4, 0x00-0xFF | 256 值 | ❌ 全部无反应 |
| m1ddc input 0-255（Mac via DP2） | 256 值 | 仅 15 有效 |
| m1ddc input-alt 0-255（Mac via DP2） | 256 值 | ❌ 全部无反应 |
| m1ddc input 256-512（Mac via DP2） | 256 值 | ❌ 全部无反应 |

### 4.6 I2C 总线设备

```
Scan: 0x37 0x3A 0x49 0x50 0x54 0x58 0x59  (7 devices)
```

与 LG 相同的设备分布。

---

## 5. 最终方案设计

### 5.1 接线方案

小米显示器需要 ESP32 接在**两条活跃端口的 DDC 总线上**，才能双向切换：

```
=== LG 34GS95QE ===
Gaming PC ──HDMI──→ LG HDMI1
MacBook   ──DP────→ LG DP1
ESP32 I2C-0 ──────→ LG HDMI DDC（分线板串联在 PC 的 HDMI 线中）

=== Redmi G Pro 27 ===
Gaming PC ──HDMI──→ [母对母] ← [分线板A] ──→ Redmi HDMI1
                                   │
                             ESP32 I2C-A（切到 Mac 方向时使用）

MacBook   ──HDMI──→ [母对母] ← [分线板B] ──→ Redmi HDMI2
                                   │
                             ESP32 I2C-B（切到 PC 方向时使用）
```

### 5.2 切换逻辑

```
按钮按下 → 切到 Mac:
  1. ESP32 通过 I2C-PC（活跃）发命令给两台显示器
     - LG:    src=0x50, VCP=0xF4, val=0x00D0  (→ DP1)
     - Redmi: src=0x51, VCP=0x60, val=0x0011  (→ HDMI2) ← 值待确认
  2. ESP32 控制 TS3USB221 SEL 引脚切 USB

按钮按下 → 切到 PC:
  1. ESP32 通过 I2C-Mac（活跃）发命令给两台显示器
     - LG:    src=0x50, VCP=0xF4, val=0x0090  (→ HDMI1)
     - Redmi: src=0x51, VCP=0x60, val=0x000F  (→ HDMI1) ← 值待确认
  2. ESP32 控制 TS3USB221 SEL 引脚切 USB
```

### 5.3 需要购买的硬件

| 物品 | 数量 | 用途 |
|------|------|------|
| HDMI 分线板（单公头） | **1 块**（已有1块，共需2块给Redmi，LG另算） | 串联到 HDMI 线中 |
| HDMI 母对母转接头 | **2-3 个** | 连接分线板和 HDMI 线 |
| 4.7kΩ 电阻 | **4 个**（已有2个） | 每组 I2C 需要 2 个上拉 |

### 5.4 待确认事项

- [ ] Redmi HDMI1 对应的 VCP 0x60 值（预计 17 或 18）
- [ ] Redmi HDMI2 对应的 VCP 0x60 值（已知 PC 端用 17 能切到 HDMI2）
- [ ] ESP32 通过串联分线板的 DDC 能否成功切换 Redmi
- [ ] LG 的分线板串联方案（目前是直插，需改为串联）
- [ ] 两台显示器同时切换的时序
- [ ] TS3USB221 USB 切换集成

---

## 6. ESP32-S3 注意事项

### 6.1 启动引脚限制

| GPIO | 限制 | 说明 |
|------|------|------|
| GPIO 0 | ⚠️ 启动模式 | 接 GND 进入下载模式 |
| GPIO 45 | ⚠️ 启动模式 | 接 GND 导致无限重启 |
| GPIO 46 | ⚠️ 启动模式 | 慎用 |
| GPIO 19/20 | USB D-/D+ | 如使用 USB 功能需保留 |

### 6.2 I2C 配置

ESP32-S3 有两个硬件 I2C 控制器，可同时驱动两条总线：

```cpp
TwoWire I2C_0 = TwoWire(0);  // 第一组
TwoWire I2C_1 = TwoWire(1);  // 第二组

I2C_0.begin(SDA_PIN_A, SCL_PIN_A);
I2C_1.begin(SDA_PIN_B, SCL_PIN_B);
```

### 6.3 上拉电阻

每组 I2C 需要两个 4.7kΩ 上拉电阻（拉到 3.3V）：
- SDA → 4.7kΩ → 3.3V
- SCL → 4.7kΩ → 3.3V

---

## 附录 A：工具代码

### A.1 分线板引脚探测器

```cpp
#include <Arduino.h>

// 将分线板各针脚接到以下 GPIO（避开 0, 45, 46）
int pins[] = {12, 11, 10, 9, 46, 3, 8, 18, 17, 16};
int numPins = 10;

void setup() {
  Serial.begin(115200);
  delay(1000);
  for (int i = 0; i < numPins; i++) {
    pinMode(pins[i], INPUT_PULLUP);
  }
  Serial.println("=== HDMI Breakout Pin Mapper ===");
  Serial.println("确保 HDMI 插在显示器上");
}

void loop() {
  Serial.println("--- 读取结果 ---");
  for (int i = 0; i < numPins; i++) {
    int val = digitalRead(pins[i]);
    Serial.print("位置 ");
    Serial.print(i + 1);
    Serial.print(": ");
    Serial.println(val == LOW ? "LOW  ← GND!" : "HIGH");
  }
  Serial.println();
  Serial.println("奇偶分排: GND 在位置 3,6,9");
  Serial.println("顺序排列: GND 在位置 2,5,8");
  delay(5000);
}
```

### A.2 DDC SDA 自动探测器

```cpp
#include <Wire.h>

int sdaCandidates[] = {39, 36, 35, 2, 48, 47, 21, 20};
int numCandidates = 8;
int sclPin = 18;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("=== DDC Pin Finder ===");

  for (int i = 0; i < numCandidates; i++) {
    int sdaPin = sdaCandidates[i];
    Serial.print("Trying SDA = GPIO ");
    Serial.print(sdaPin);
    Serial.print(" ... ");

    Wire.begin(sdaPin, sclPin);
    delay(100);

    Wire.beginTransmission(0x37);
    byte error = Wire.endTransmission();

    if (error == 0) {
      Serial.println(">>> 0x37 FOUND! <<<");
    } else {
      Serial.println("no response");
    }

    Wire.end();
    delay(200);
  }
  Serial.println("=== Done ===");
}

void loop() { delay(10000); }
```

### A.3 LG Alt 模式切换器

```cpp
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

  Serial.print("VCP=0x");
  Serial.print(vcp, HEX);
  Serial.print(" val=0x");
  Serial.print(value, HEX);
  Serial.println(err == 0 ? " ACK" : " NACK");
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Wire.begin(47, 18);
  Wire.setClock(50000);
  Serial.println("=== LG Alt Mode (VCP 0xF4) ===");
  Serial.println("  1=HDMI1(0x90) 2=HDMI2(0x91) 3=DP1(0xD0) 4=DP2(0xD1)");
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

### A.4 Redmi 标准模式切换器

```cpp
#include <Wire.h>

#define DDC_ADDR 0x37

void ddcWrite(byte vcp, uint16_t value) {
  byte msg[] = {0x51, 0x84, 0x03, vcp,
                (byte)(value >> 8), (byte)(value & 0xFF)};
  byte chk = 0x6E;
  for (int i = 0; i < 6; i++) chk ^= msg[i];

  Wire.beginTransmission(DDC_ADDR);
  Wire.write(msg, 6);
  Wire.write(chk);
  byte err = Wire.endTransmission();

  Serial.print("val=0x");
  Serial.print(value, HEX);
  Serial.println(err == 0 ? " ACK" : " NACK");
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Wire.begin(47, 18);
  Wire.setClock(30000);
  Serial.println("=== Redmi Standard DDC ===");
  Serial.println("  1=DP1(15) 2=DP2(16) 3=HDMI1(17) 4=HDMI2(18)");
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();
    switch (c) {
      case '1': ddcWrite(0x60, 0x000F); break; // DP1 = 15
      case '2': ddcWrite(0x60, 0x0010); break; // DP2 = 16
      case '3': ddcWrite(0x60, 0x0011); break; // HDMI1 = 17 (待确认)
      case '4': ddcWrite(0x60, 0x0012); break; // HDMI2 = 18 (待确认)
    }
  }
}
```

### A.5 双显示器 KVM 切换器（预览版）

```cpp
#include <Wire.h>

TwoWire I2C_HDMI1 = TwoWire(0); // Redmi HDMI1 (PC侧)
TwoWire I2C_HDMI2 = TwoWire(1); // Redmi HDMI2 (Mac侧)

#define DDC_ADDR 0x37
#define BUTTON_PIN 4

bool currentIsPC = true;

void ddcSendStandard(TwoWire &bus, uint16_t value) {
  byte msg[] = {0x51, 0x84, 0x03, 0x60,
                (byte)(value >> 8), (byte)(value & 0xFF)};
  byte chk = 0x6E;
  for (int i = 0; i < 6; i++) chk ^= msg[i];

  bus.beginTransmission(DDC_ADDR);
  bus.write(msg, 6);
  bus.write(chk);
  bus.endTransmission();
}

void ddcSendLG(TwoWire &bus, uint16_t value) {
  byte msg[] = {0x50, 0x84, 0x03, 0xF4,
                (byte)(value >> 8), (byte)(value & 0xFF)};
  byte chk = 0x6E;
  for (int i = 0; i < 6; i++) chk ^= msg[i];

  bus.beginTransmission(DDC_ADDR);
  bus.write(msg, 6);
  bus.write(chk);
  bus.endTransmission();
}

void switchToMac() {
  // 当前 PC 活跃，用 PC 侧总线发命令
  // LG: HDMI1→DP1
  // ddcSendLG(I2C_LG, 0x00D0);    // TODO: LG 接线
  // Redmi: HDMI1→HDMI2
  ddcSendStandard(I2C_HDMI1, 0x0011); // 值待确认
  currentIsPC = false;
  Serial.println("→ Mac");
}

void switchToPC() {
  // 当前 Mac 活跃，用 Mac 侧总线发命令
  // LG: DP1→HDMI1
  // ddcSendLG(I2C_LG, 0x0090);    // TODO: LG 接线
  // Redmi: HDMI2→HDMI1
  ddcSendStandard(I2C_HDMI2, 0x000F); // 值待确认（可能不是15）
  currentIsPC = true;
  Serial.println("→ PC");
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  I2C_HDMI1.begin(47, 18);
  I2C_HDMI1.setClock(30000);

  I2C_HDMI2.begin(6, 5);
  I2C_HDMI2.setClock(30000);

  pinMode(BUTTON_PIN, INPUT_PULLUP);

  Serial.println("=== Dual Monitor KVM ===");
  Serial.println("  Button or 't' to toggle");
}

void loop() {
  if (digitalRead(BUTTON_PIN) == LOW) {
    if (currentIsPC) switchToMac();
    else switchToPC();
    delay(500);
  }

  if (Serial.available()) {
    char c = Serial.read();
    if (c == 't') {
      if (currentIsPC) switchToMac();
      else switchToPC();
    }
  }
}
```

---

## 附录 B：调试经验

| 症状 | 原因 | 解决方案 |
|------|------|---------|
| 所有 I2C 地址都响应 | SDA/SCL/GND 接错，总线短路 | 重新确认分线板排列 |
| ESP32 "waiting for download" | GPIO 0 被拉低 | 避开 GPIO 0, 45, 46 |
| ESP32 无限重启 | GPIO 45 被拉低 | 同上 |
| 无 I2C 设备 | 缺少上拉电阻 | 加 4.7kΩ 上拉到 3.3V |
| 读取返回随机值 | 显示器 DDC 实现不稳定 | 多次重试或降低时钟 |
| 读取正常写入无效 (LG) | 需要 Alt 模式 | 源地址 0x50 + VCP 0xF4 |
| 写入 ACK 但不切换 (Redmi) | 从空闲端口发命令被忽略 | ESP32 必须串联在活跃端口 |
| ControlMyMonitor/BetterDisplay 切不回来 | 切走后失去 DDC 控制 | ESP32 独立控制的价值所在 |
