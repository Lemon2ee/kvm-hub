# ESP32-S3 DDC/CI KVM 切换项目笔记

## 项目目标

ESP32-S3 通过 DDC/CI 控制显示器自动切换输入源，配合 TS3USB221 切换 USB 外设，实现 MacBook Pro 和 Gaming PC 之间的一键 KVM 切换。

---

## 1. HDMI 分线板接线

### 1.1 分线板排列方式

经测试确认，分线板为**奇偶分排**结构：

```
                HDMI 公头方向
    ┌──────────────────────────────┐
上排 │ 1  3  5  7  9  11 13 15 17 19 │  ← 奇数 Pin
    ├──────────────────────────────┤
下排 │ 2  4  6  8  10 12 14 16 18    │  ← 偶数 Pin（9针）
    └──────────────────────────────┘
         位置编号（从左到右）
上排:  1   2   3   4   5   6   7   8   9  10
下排:  1   2   3   4   5   6   7   8   9  10  11
```

### 1.2 验证方法（无万用表）

使用 ESP32 GPIO 内部上拉电阻代替万用表，将分线板各针脚接到 GPIO，读取电平。GND 引脚会被拉 LOW。

**上排 GND 验证结果：**

- 位置 3 = LOW → Pin 5 (GND) ✓
- 位置 6 = LOW → Pin 11 (GND) ✓

**下排 GND 验证结果：**

- 位置 2 = LOW (GPIO38)
- 位置 3 = LOW (GPIO37)
- 位置 6 = LOW (GPIO0 → 触发下载模式，额外确认)

> **注意：** ESP32-S3 的 GPIO 0、45、46 为启动引脚，接到 GND 会导致芯片进入下载模式或无限重启。测试时必须避开这些 GPIO。

### 1.3 DDC/CI 所需引脚

| 信号 | HDMI Pin | 分线板位置 | 说明 |
|------|----------|-----------|------|
| SCL  | Pin 15   | **上排第 8 针** | DDC 时钟线 |
| SDA  | Pin 16   | **下排第 9 针** | DDC 数据线 |
| GND  | Pin 5    | **上排第 3 针** | 接地（Pin 11 也可用） |

### 1.4 ESP32-S3 接线

| ESP32 GPIO | 功能 | 连接目标 |
|-----------|------|---------|
| GPIO 18   | SCL  | 上排第 8 针 (HDMI Pin 15) |
| GPIO 47   | SDA  | 下排第 9 针 (HDMI Pin 16) |
| GND       | GND  | 上排第 3 针 (HDMI Pin 5) |

**上拉电阻：**

- GPIO 18 (SCL) → 4.7kΩ → 3.3V
- GPIO 47 (SDA) → 4.7kΩ → 3.3V

```
面包板接法示例（以 SCL 为例）：

排 X: HDMI SCL杜邦线 ── 电阻一脚 ── 去GPIO18的杜邦线
排 Y: 电阻另一脚 ── 3.3V杜邦线

SDA 同理，用另外两排。
```

### 1.5 HDMI Type A 标准引脚参考

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

## 2. LG 显示器 DDC/CI Alt 模式

### 2.1 背景

LG 较新型号的显示器（包括 34GS95QE）不使用标准 DDC/CI 协议切换输入源。标准工具（如 ControlMyMonitor、ddcutil 默认模式）可以**读取**输入源但**无法写入**切换。

LG 使用一种非标准的 "DDC Alt" 协议，关键区别：

| 参数 | 标准 DDC/CI | LG Alt 模式 |
|------|-----------|------------|
| I2C 地址 | 0x37 | 0x37（相同） |
| 源地址字节 | **0x51** | **0x50** |
| VCP 代码 | **0x60** (Input Source) | **0xF4** |
| 输入值编码 | 0x0F=DP1, 0x11=HDMI1 等 | 0x0090=HDMI1, 0x00D0=DP1 等 |

### 2.2 LG 34GS95QE 参数

| 参数 | 值 |
|------|-----|
| I2C 设备地址 | 0x37 |
| I2C 总线上其他设备 | 0x3A, 0x49, 0x50 (EDID), 0x54, 0x58, 0x59 |
| DDC 源地址 | **0x50** |
| VCP 代码 | **0xF4** |
| I2C 速率 | 50kHz（推荐，更稳定） |

### 2.3 输入源值映射

| 输入端口 | Alt 模式值 (VCP 0xF4) | 标准模式值 (VCP 0x60) |
|---------|---------------------|---------------------|
| HDMI-1  | **0x0090** (144)     | 0x0F (15)           |
| HDMI-2  | **0x0091** (145)     | 0x10 (16)           |
| DP-1    | **0x00D0** (208)     | 0x11 (17)           |
| DP-2    | **0x00D1** (209)     | 0x12 (18)           |

> **注意：** 标准模式的 VCP 0x60 可以正常**读取**当前输入源，但**写入无效**。切换必须使用 Alt 模式。

### 2.4 DDC/CI Alt 模式数据包格式

**写入（切换输入源）：**

```
I2C 地址: 0x37 (7-bit) → 总线上为 0x6E (写)
数据字节:
  [0] 0x50        ← 源地址（LG Alt，标准为 0x51）
  [1] 0x84        ← 长度 | 0x80 (4 字节负载)
  [2] 0x03        ← VCP Set 操作码
  [3] 0xF4        ← VCP 代码（LG Alt，标准为 0x60）
  [4] 0x00        ← 值高字节
  [5] 0xD0        ← 值低字节（示例：DP-1）
  [6] checksum    ← 校验和
```

**校验和计算：**

```
checksum = 0x6E ⊕ 0x50 ⊕ 0x84 ⊕ 0x03 ⊕ 0xF4 ⊕ value_high ⊕ value_low

其中 0x6E = I2C 写地址（目标地址），参与校验但不作为数据发送
```

### 2.5 已知支持 Alt 模式的 LG 型号

根据 ddcutil wiki 和 BetterDisplay 社区信息，以下型号可能需要 Alt 模式：

GP850, QP750, GP950, WP950C, QP88D, UL550/500, GP750, 28MQ780, UP850, UN880, GQ850, UQ85R, WQ75C, WQ60C, WQ95C, UP600, **34GS95QE** 等。

### 2.6 参考资料

- [BetterDisplay Discussion #4246](https://github.com/waydabber/BetterDisplay/discussions/4246) — 34GS95QE 的 DDC Alt 模式讨论
- [m1ddc PR #52](https://github.com/waydabber/m1ddc/pull/52) — 修复 LG Alt 模式校验和计算
- [ddcutil Wiki: LG 输入源切换](https://github.com/rockowitz/ddcutil/wiki/Switching-input-source-on-LG-monitors) — LG DDC Alt 模式文档
- [BetterDisplay Issue #1923](https://github.com/waydabber/BetterDisplay/issues/1923) — LG Alt 模式最初发现

---

## 3. ESP32 代码

### 3.1 I2C 扫描器

用于验证接线是否正确，应稳定检测到 0x37。

```cpp
#include <Wire.h>

void setup() {
  Serial.begin(115200);
  delay(1000);
  Wire.begin(47, 18); // SDA=GPIO47, SCL=GPIO18
  Serial.println("I2C Scanner");
}

void loop() {
  int nDevices = 0;
  Serial.print("Scan: ");

  for (byte addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.print("0x");
      if (addr < 16) Serial.print("0");
      Serial.print(addr, HEX);
      Serial.print(" ");
      nDevices++;
    }
  }

  Serial.print(" (");
  Serial.print(nDevices);
  Serial.println(" devices)");
  delay(3000);
}
```

### 3.2 LG Alt 模式输入切换器（最终版）

```cpp
#include <Wire.h>

#define DDC_ADDR 0x37

void ddcWriteLG(byte vcp, uint16_t value) {
  byte msg[] = {0x50, 0x84, 0x03, vcp,
                (byte)(value >> 8), (byte)(value & 0xFF)};
  byte chk = 0x6E;
  for (int i = 0; i < 6; i++) chk ^= msg[i];

  Serial.print("VCP=0x");
  Serial.print(vcp, HEX);
  Serial.print(" val=0x");
  Serial.print(value, HEX);
  Serial.print(" ... ");

  Wire.beginTransmission(DDC_ADDR);
  Wire.write(msg, 6);
  Wire.write(chk);
  byte err = Wire.endTransmission();
  Serial.println(err == 0 ? "ACK" : "NACK");
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Wire.begin(47, 18);       // SDA=GPIO47, SCL=GPIO18
  Wire.setClock(50000);      // 50kHz，LG 推荐较低速率
  Serial.println("=== LG Alt Mode (VCP 0xF4) ===");
  Serial.println("  1 = HDMI-1 (0x90)");
  Serial.println("  2 = HDMI-2 (0x91)");
  Serial.println("  3 = DP-1   (0xD0)");
  Serial.println("  4 = DP-2   (0xD1)");
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();
    switch (c) {
      case '1': ddcWriteLG(0xF4, 0x0090); break; // HDMI-1
      case '2': ddcWriteLG(0xF4, 0x0091); break; // HDMI-2
      case '3': ddcWriteLG(0xF4, 0x00D0); break; // DP-1
      case '4': ddcWriteLG(0xF4, 0x00D1); break; // DP-2
    }
  }
}
```

### 3.3 分线板引脚探测工具

用于在没有万用表的情况下确认分线板 pin 排列。将各针脚接到 ESP32 GPIO，利用内部上拉读取电平，GND 引脚读到 LOW。

```cpp
#include <Arduino.h>

// 将分线板的针脚依次接到以下 GPIO
// 注意避开 GPIO 0, 45, 46（启动引脚）
int pins[] = {12, 11, 10, 9, 46, 3, 8, 18, 17, 16};
int numPins = 10;

void setup() {
  Serial.begin(115200);
  delay(1000);

  for (int i = 0; i < numPins; i++) {
    pinMode(pins[i], INPUT_PULLUP);
  }

  Serial.println("=== HDMI Breakout Pin Mapper ===");
  Serial.println("确保 HDMI 插在显示器上（提供 GND 参考）");
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
  delay(5000);
}
```

### 3.4 DDC SDA 自动探测工具

固定 SCL，依次尝试下排各非 GND 引脚作为 SDA，自动找到能扫到 0x37 的引脚。

```cpp
#include <Wire.h>

// 下排非 GND 引脚的 GPIO 列表
int sdaCandidates[] = {39, 36, 35, 2, 48, 47, 21, 20};
int numCandidates = 8;
int sclPin = 18; // 已确认的 SCL 引脚

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("=== DDC Pin Finder ===");
  Serial.print("SCL fixed at GPIO ");
  Serial.println(sclPin);

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
      int found = 0;
      for (byte addr = 1; addr < 127; addr++) {
        Wire.beginTransmission(addr);
        if (Wire.endTransmission() == 0) found++;
      }
      Serial.print("no 0x37, found ");
      Serial.print(found);
      Serial.println(" other devices");
    }

    Wire.end();
    delay(200);
  }

  Serial.println("=== Done ===");
}

void loop() {
  delay(10000);
}
```

---

## 4. 调试经验与注意事项

### 4.1 常见问题

| 症状 | 原因 | 解决方案 |
|------|------|---------|
| 几乎所有 I2C 地址都响应 | SDA/SCL/GND 接错，总线短路 | 重新确认分线板排列 |
| ESP32 卡在 "waiting for download" | GPIO 0 被拉低 | 避免使用 GPIO 0、45、46 |
| ESP32 无限重启 | GPIO 45 被拉低 | 同上 |
| I2C 扫描无设备 | 缺少上拉电阻或接线错误 | 加 4.7kΩ 上拉到 3.3V |
| 扫描到 0x37 但读写不稳定 | I2C 速率过高 | Wire.setClock(50000) 降至 50kHz |
| 标准 DDC 读取正常但写入无效 | LG 需要 Alt 模式 | 使用 0x50 源地址 + VCP 0xF4 |
| ControlMyMonitor 也无法切换 | 显示器不接受标准协议写入 | 确认需要 LG Alt 模式 |

### 4.2 ESP32-S3 GPIO 注意事项

- **GPIO 0:** 启动模式选择，不可接 GND
- **GPIO 45:** 启动模式选择，不可接 GND
- **GPIO 46:** 启动模式选择，慎用
- **GPIO 19/20:** USB D-/D+，如使用 USB 功能需保留
- I2C 的 SDA/SCL 可以使用任意普通 GPIO

### 4.3 硬件清单

- ESP32-S3 Dev Module
- HDMI 分线板（20pin，两排各10/9针）
- 面包板
- 杜邦线（公对母）
- 4.7kΩ 电阻 × 2（I2C 上拉）
- 1N5819 肖特基二极管（备用，5V 容忍保护）

---

## 5. 下一步计划

1. **第二台显示器（小米）** — 确认是否使用标准 DDC/CI（VCP 0x60 + 0x51），需要第二组 I2C 引脚
2. **TS3USB221 USB 切换** — 用 GPIO 控制 SEL 引脚，同步切换 USB 外设
3. **物理按钮** — 接一个按钮到 GPIO，一键同时切换两台显示器 + USB
4. **PCB 设计** — 将面包板原型转为成品 PCB
