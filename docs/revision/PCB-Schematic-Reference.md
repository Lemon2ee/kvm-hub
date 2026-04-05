# ESP32-S3 KVM 切换器 — PCB 原理图参考

> 目标 EDA：立创 EDA (LCEDA)
> 生产：嘉立创 PCB + SMT 贴片
> 最后更新：2026-04-05

---

## 1. BOM (物料清单)

### 1.1 主要 IC / 连接器

| Ref | 元件 | 型号 | 封装 | LCSC | 数量 | 备注 |
|-----|------|------|------|------|------|------|
| U1 | USB 2.0 Mux | TS3USB221RSER | UQFN-10 | **C130085** | 1 | SEL 控制切换 |
| J1 | USB-C 母座 (Win) | TYPE-C-31-M-12 | SMD 16pin | **C165948** | 1 | PC 端 |
| J2 | USB-C 母座 (Mac) | TYPE-C-31-M-12 | SMD 16pin | **C165948** | 1 | Mac 端 |
| J3 | USB-A 母座 (外设) | AF 90 15.5 PBT | Through-hole | **C168713** | 1 | 鼠标/键盘 |
| J4 | DDC-0 (LG) | B3B-XH-A | 2.5mm 3pin | **C144394** | 1 | I2C-0 |
| J5 | DDC-1 (Redmi A) | B3B-XH-A | 2.5mm 3pin | **C144394** | 1 | I2C-1 预留 |
| J6 | DDC-2 (Redmi B) | B3B-XH-A | 2.5mm 3pin | **C144394** | 1 | I2C-1 预留 |
| U2 | ESP32-S3 排母座 | 2.54mm 排母 | Through-hole | — | 2排 | 按你 dev board 针数买 |
| SW1 | 轻触开关 | TS-1187A-B-A-B | SMD 5.1mm | **C318884** | 1 | 物理切换按钮 |

### 1.2 二极管

| Ref | 元件 | 型号 | 封装 | LCSC | 数量 | 备注 |
|-----|------|------|------|------|------|------|
| D1 | 肖特基二极管 | SS34 | SMA | **C8678** | 1 | Win VBUS |
| D2 | 肖特基二极管 | SS34 | SMA | **C8678** | 1 | Mac VBUS |

### 1.3 电阻 (全部 0805)

| Ref | 值 | LCSC | 数量 | 用途 |
|-----|-----|------|------|------|
| R1-R6 | 4.7kΩ | **C17673** | 6 | I2C 上拉 (3 bus × SDA+SCL) |
| R7-R10 | 5.1kΩ | **C27834** | 4 | USB-C CC pull-down (2 port × CC1+CC2) |
| R11-R12 | 330Ω | **C23138** | 2 | LED 限流 |

### 1.4 电容 (全部 0805)

| Ref | 值 | LCSC | 数量 | 用途 |
|-----|-----|------|------|------|
| C1 | 100nF | **C49678** | 1 | U1 (TS3USB221) VCC 去耦 |
| C2 | 10μF | **C15850** | 1 | VBUS 电源滤波 |
| C3 | 100nF | **C49678** | 1 | 3.3V 去耦 (可选) |

### 1.5 LED (0805)

| Ref | 颜色 | LCSC | 数量 | 用途 |
|-----|------|------|------|------|
| LED1 | 绿色 | **C2297** | 1 | Windows 活跃 |
| LED2 | 蓝色 | **C2293** | 1 | MacBook 活跃 |

---

## 2. 原理图 — 逐模块连接

### 2.1 TS3USB221 (U1) — USB 数据切换

```
TS3USB221RSER (UQFN-10) 引脚:

  Pin 1  VCC ──── 3.3V + C1(100nF) 到 GND
  Pin 2  S   ──── ESP32 GPIO 4  (SEL: LOW=Win, HIGH=Mac)
  Pin 3  D+  ──── J3 USB-A D+ (外设公共端)
  Pin 4  D-  ──── J3 USB-A D- (外设公共端)
  Pin 5  OE# ──── GND (始终使能)
  Pin 6  GND ──── GND
  Pin 7  2D- ──── J2 USB-C D- (Mac)
  Pin 8  2D+ ──── J2 USB-C D+ (Mac)
  Pin 9  1D- ──── J1 USB-C D- (Win)
  Pin 10 1D+ ──── J1 USB-C D+ (Win)
```

**注意：** D+/D- 差分对走线尽量等长、平行、短，间距保持一致。2 层板 90Ω 差分阻抗参考嘉立创阻抗计算器。

### 2.2 USB-C 母座 (J1, J2) — PC 连接

```
TYPE-C-31-M-12 关键引脚:

  A1  (GND)  ──── GND
  A4  (VBUS) ──── D1 或 D2 阳极 (Schottky)
  A5  (CC1)  ──── 5.1kΩ (R7/R9) ──── GND
  A6  (D+)   ──┐
  A7  (D-)   ──┤── 接到 TS3USB221 对应端口
  B6  (D+)   ──┘   (USB 2.0: A6/B6 D+ 同网络, A7/B7 D- 同网络)
  B7  (D-)   ──┘
  A8  (SBU1) ──── NC
  A9  (VBUS) ──── 与 A4 同网络
  A12 (GND)  ──── GND
  B1  (GND)  ──── GND
  B4  (VBUS) ──── 与 A4 同网络
  B5  (CC2)  ──── 5.1kΩ (R8/R10) ──── GND
  B8  (SBU2) ──── NC
  B9  (VBUS) ──── 与 A4 同网络
  B12 (GND)  ──── GND
  Shell      ──── GND

USB 2.0 简化: D+ 引脚(A6+B6)合并, D- 引脚(A7+B7)合并
```

**每个 USB-C 需要 2 颗 5.1kΩ 电阻 (CC1, CC2 各一颗到 GND)。**
这告诉电脑对面是一个 USB device / 吸电端，电脑才会供电和枚举。

### 2.3 VBUS 供电 — Schottky OR

```
J1 VBUS (Win) ──── D1 阳极 ──|>── D1 阴极 ──┐
                                             ├── VBUS_OUT ──── J3 USB-A VBUS
J2 VBUS (Mac) ──── D2 阳极 ──|>── D2 阴极 ──┘
                                             │
                                          C2 (10μF) ──── GND

D1, D2 = SS34 (Vf ≈ 0.3V @ 100mA)
外设实际得到约 4.7V，鼠标键盘无问题。
```

### 2.4 USB-A 母座 (J3) — 外设端

```
J3 USB-A:
  Pin 1 (VBUS) ──── VBUS_OUT (从 Schottky OR 来)
  Pin 2 (D-)   ──── U1 Pin 4 (COM D-)
  Pin 3 (D+)   ──── U1 Pin 3 (COM D+)
  Pin 4 (GND)  ──── GND
  Shell         ──── GND
```

### 2.5 ESP32-S3 排母座 (U2) — 关键连接

```
只列出 PCB 上需要连接的引脚，其余直通排母座即可:

  3.3V  ──── I2C 上拉电阻公共端 + U1 VCC
  GND   ──── 系统 GND
  GPIO4 ──── U1 Pin 2 (SEL)
  GPIO9 ──── SW1 一端 (另一端接 GND)
  GPIO10 ─── R11(330Ω) ──── LED1 阳极 (绿, 阴极接 GND)
  GPIO11 ─── R12(330Ω) ──── LED2 阳极 (蓝, 阴极接 GND)
  GPIO18 ─── J4-SCL (LG)  + R1(4.7kΩ) 到 3.3V
  GPIO47 ─── J4-SDA (LG)  + R2(4.7kΩ) 到 3.3V
  GPIO5  ─── J5-SCL + J6-SCL (Redmi, 预留) + R3(4.7kΩ) 到 3.3V
  GPIO6  ─── J5-SDA + J6-SDA (Redmi, 预留) + R4(4.7kΩ) 到 3.3V
```

**按钮 SW1:** GPIO9 设为 INPUT_PULLUP，按下接 GND，软件去抖。

**LED:** GPIO HIGH = 亮, LOW = 灭。

### 2.6 DDC 连接器 (J4, J5, J6) — JST-XH 3pin

```
每个 JST-XH 3pin 引脚定义 (从左到右):

  Pin 1: GND
  Pin 2: SDA ──── 对应 GPIO + 4.7kΩ 上拉到 3.3V
  Pin 3: SCL ──── 对应 GPIO + 4.7kΩ 上拉到 3.3V

J4 (DDC-0, LG):     SDA=GPIO47, SCL=GPIO18
J5 (DDC-1, Redmi):  SDA=GPIO6,  SCL=GPIO5
J6 (DDC-2, Redmi):  SDA=GPIO6,  SCL=GPIO5  (与 J5 共用 I2C-1)
```

**J5 和 J6 共用同一组 I2C 总线。** 小米显示器 DDC 只从活跃端口响应，所以同一时刻只有一条线路有设备应答，共用总线不会冲突。上拉电阻只需一组 (R3+R4)，不需要重复。

### 2.7 I2C 上拉电阻网络

```
         3.3V
          │
     ┌────┼────┐
     R1   R2   │        ← I2C-0 (LG)
   4.7kΩ 4.7kΩ │
     │    │    │
  GPIO18 GPIO47│
   (SCL)  (SDA)│
               │
     ┌────┬────┘
     R3   R4            ← I2C-1 (Redmi, 预留)
   4.7kΩ 4.7kΩ
     │    │
   GPIO5  GPIO6
   (SCL)  (SDA)
```

R5, R6 为额外预留焊盘 (DNP)，如果未来需要第三组独立 I2C。

---

## 3. PCB Layout 指南

### 3.1 板子尺寸

目标 **70mm × 50mm**，2 层板。

### 3.2 连接器布局

```
              70mm
    ┌──────────────────────────┐
    │ [J1 USB-C]  [J2 USB-C]  │  ← 顶边: 两根线到两台电脑
    │    Win          Mac      │
    │                          │
    │  U1   D1 D2   C1 C2     │  ← 中上: TS3USB221 + 电源
    │                          │
50mm│ ┌──────────────────┐     │
    │ │   ESP32-S3 Dev   │ [J3]│  ← 右边: USB-A 外设口
    │ │   (排母插座)      │     │
    │ └──────────────────┘     │
    │                          │
    │ [J4] [J5] [J6] [SW1]    │  ← 底边: DDC 连接 + 按钮
    │  LG  Redmi      BTN     │
    │              LED1 LED2   │
    └──────────────────────────┘
```

### 3.3 走线要点

| 信号 | 要求 |
|------|------|
| USB D+/D- | 差分对，等长，90Ω 阻抗，尽量短 (< 30mm) |
| I2C SDA/SCL | 普通走线即可，50kHz 低速无特殊要求 |
| GPIO (SEL/BTN/LED) | 普通走线 |
| VBUS 电源 | 适当加宽 (0.5mm+) |
| GND | 大面积铺铜，底层整面 GND |

### 3.4 铺铜

- **底层 (B.Cu):** 整面 GND 铺铜
- **顶层 (F.Cu):** 在空白区域铺 GND，USB 走线区域保持清晰

---

## 4. 立创 EDA 操作提示

### 4.1 创建项目

1. 立创 EDA → 新建项目 → "ESP32-S3 KVM Switch"
2. 新建原理图 + PCB

### 4.2 放置元件

在原理图编辑器中，使用 LCSC 编号直接搜索放置：
- 搜索框输入 `C130085` → 自动关联 TS3USB221RSER 符号 + 封装
- 搜索框输入 `C165948` → TYPE-C-31-M-12
- 以此类推

### 4.3 嘉立创 SMT 注意事项

- BOM 中标注 LCSC 编号，下单时自动匹配
- UQFN-10 (TS3USB221) 必须机贴，无法手焊
- Through-hole 元件 (USB-A, JST-XH, 排母) 需要手焊或选择嘉立创插件服务
- 建议 SMD 元件全部放同一面 (顶层)，降低贴片费

### 4.4 阻抗计算

嘉立创提供在线阻抗计算器，2 层板 1.6mm 板厚：
- 差分 90Ω 参考：线宽约 0.2mm，间距约 0.15mm（具体值用计算器确认）
- 在 PCB 设计规则中设置差分对约束

---

## 5. 原理图网络表 (快速参考)

| 网络名 | 连接点 |
|--------|--------|
| 3V3 | ESP32 3.3V, U1 VCC, R1-R6 上拉端, C1, C3 |
| GND | ESP32 GND, U1 GND, U1 OE#, J1-J6 GND, D1/D2 参考, C1-C3, R7-R10, LED 阴极, SW1 |
| VBUS_WIN | J1 VBUS pins, D1 阳极 |
| VBUS_MAC | J2 VBUS pins, D2 阳极 |
| VBUS_OUT | D1 阴极, D2 阴极, J3 VBUS, C2 |
| USB_SEL | ESP32 GPIO4, U1 S |
| COM_DP | U1 D+, J3 D+ |
| COM_DN | U1 D-, J3 D- |
| WIN_DP | U1 1D+, J1 D+ |
| WIN_DN | U1 1D-, J1 D- |
| MAC_DP | U1 2D+, J2 D+ |
| MAC_DN | U1 2D-, J2 D- |
| CC1_WIN | J1 CC1, R7 |
| CC2_WIN | J1 CC2, R8 |
| CC1_MAC | J2 CC1, R9 |
| CC2_MAC | J2 CC2, R10 |
| I2C0_SCL | ESP32 GPIO18, J4 SCL, R1 |
| I2C0_SDA | ESP32 GPIO47, J4 SDA, R2 |
| I2C1_SCL | ESP32 GPIO5, J5 SCL, J6 SCL, R3 |
| I2C1_SDA | ESP32 GPIO6, J5 SDA, J6 SDA, R4 |
| BTN | ESP32 GPIO9, SW1 |
| LED_WIN | ESP32 GPIO10, R11 |
| LED_MAC | ESP32 GPIO11, R12 |
