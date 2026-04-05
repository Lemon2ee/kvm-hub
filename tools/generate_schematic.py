#!/usr/bin/env python3
"""Generate KiCad 7 schematic (.kicad_sch) for ESP32-S3 KVM Switch.

Usage: python generate_schematic.py > ../hardware/kvm_switch.kicad_sch
"""

_uid = 0
def uid():
    global _uid
    _uid += 1
    return f"{_uid:08x}-0000-0000-0000-000000000000"

ROOT_UUID = uid()

# ============================================================
# Symbol definitions (lib_symbols)
# ============================================================

def sym_2pin(name, pin1_name="~", pin2_name="~", pin_type="passive",
             body="rectangle", ref_prefix="R"):
    """Generate a 2-pin vertical symbol (resistor, cap, diode, LED, switch)."""
    body_shape = ""
    if body == "rectangle":
        body_shape = f"""      (rectangle (start -1.016 -2.286) (end 1.016 2.286)
        (stroke (width 0.254) (type default)) (fill (type none)))"""
    elif body == "triangle":  # diode/LED
        body_shape = f"""      (polyline (pts (xy -1.27 1.27) (xy 0 -1.27) (xy 1.27 1.27) (xy -1.27 1.27))
        (stroke (width 0.254) (type default)) (fill (type none)))
      (polyline (pts (xy -1.27 -1.27) (xy 1.27 -1.27))
        (stroke (width 0.254) (type default)) (fill (type none)))"""

    return f"""    (symbol "KVM:{name}" (pin_numbers hide) (pin_names (offset 0) hide)
      (in_bom yes) (on_board yes)
      (property "Reference" "{ref_prefix}" (at 2.286 0 90)
        (effects (font (size 1.27 1.27))))
      (property "Value" "{name}" (at -2.286 0 90)
        (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0)
        (effects (font (size 1.27 1.27)) hide))
      (symbol "{name}_0_1"
{body_shape}
      )
      (symbol "{name}_1_1"
        (pin {pin_type} line (at 0 3.81 270) (length 1.524)
          (name "{pin1_name}" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27)))))
        (pin {pin_type} line (at 0 -3.81 90) (length 1.524)
          (name "{pin2_name}" (effects (font (size 1.27 1.27))))
          (number "2" (effects (font (size 1.27 1.27)))))
      )
    )"""


def sym_ic(name, left_pins, right_pins, ref_prefix="U"):
    """Generate rectangular IC symbol with pins on left and right."""
    n = max(len(left_pins), len(right_pins))
    half_h = round((n * 2.54) / 2 + 1.27, 2)
    body_w = 5.08

    lines = []
    lines.append(f'    (symbol "KVM:{name}" (pin_names (offset 1.016))')
    lines.append(f'      (in_bom yes) (on_board yes)')
    lines.append(f'      (property "Reference" "{ref_prefix}" (at 0 {round(half_h + 1.27, 2)} 0)')
    lines.append(f'        (effects (font (size 1.27 1.27))))')
    lines.append(f'      (property "Value" "{name}" (at 0 {round(-half_h - 1.27, 2)} 0)')
    lines.append(f'        (effects (font (size 1.27 1.27))))')
    lines.append(f'      (property "Footprint" "" (at 0 0 0)')
    lines.append(f'        (effects (font (size 1.27 1.27)) hide))')
    lines.append(f'      (symbol "{name}_0_1"')
    lines.append(f'        (rectangle (start {-body_w} {round(-half_h, 2)}) (end {body_w} {round(half_h, 2)})')
    lines.append(f'          (stroke (width 0.254) (type default)) (fill (type background)))')
    lines.append(f'      )')
    lines.append(f'      (symbol "{name}_1_1"')

    # Left pins (direction 0 = pointing right, connection on left)
    for i, (num, pname, ptype) in enumerate(left_pins):
        py = round(half_h - 1.27 - i * 2.54, 2)
        lines.append(f'        (pin {ptype} line (at {-body_w - 2.54} {py} 0) (length 2.54)')
        lines.append(f'          (name "{pname}" (effects (font (size 1.016 1.016))))')
        lines.append(f'          (number "{num}" (effects (font (size 1.016 1.016)))))')

    # Right pins (direction 180 = pointing left, connection on right)
    for i, (num, pname, ptype) in enumerate(right_pins):
        py = round(half_h - 1.27 - i * 2.54, 2)
        lines.append(f'        (pin {ptype} line (at {body_w + 2.54} {py} 180) (length 2.54)')
        lines.append(f'          (name "{pname}" (effects (font (size 1.016 1.016))))')
        lines.append(f'          (number "{num}" (effects (font (size 1.016 1.016)))))')

    lines.append(f'      )')
    lines.append(f'    )')
    return "\n".join(lines)


def sym_connector(name, pins, ref_prefix="J"):
    """Single-sided connector (pins on left)."""
    n = len(pins)
    half_h = round((n * 2.54) / 2 + 1.27, 2)
    body_w = 5.08

    lines = []
    lines.append(f'    (symbol "KVM:{name}" (pin_names (offset 1.016))')
    lines.append(f'      (in_bom yes) (on_board yes)')
    lines.append(f'      (property "Reference" "{ref_prefix}" (at 0 {round(half_h + 1.27, 2)} 0)')
    lines.append(f'        (effects (font (size 1.27 1.27))))')
    lines.append(f'      (property "Value" "{name}" (at 0 {round(-half_h - 1.27, 2)} 0)')
    lines.append(f'        (effects (font (size 1.27 1.27))))')
    lines.append(f'      (property "Footprint" "" (at 0 0 0)')
    lines.append(f'        (effects (font (size 1.27 1.27)) hide))')
    lines.append(f'      (symbol "{name}_0_1"')
    lines.append(f'        (rectangle (start {-body_w} {round(-half_h, 2)}) (end {body_w} {round(half_h, 2)})')
    lines.append(f'          (stroke (width 0.254) (type default)) (fill (type background)))')
    lines.append(f'      )')
    lines.append(f'      (symbol "{name}_1_1"')

    for i, (num, pname, ptype) in enumerate(pins):
        py = round(half_h - 1.27 - i * 2.54, 2)
        lines.append(f'        (pin {ptype} line (at {-body_w - 2.54} {py} 0) (length 2.54)')
        lines.append(f'          (name "{pname}" (effects (font (size 1.016 1.016))))')
        lines.append(f'          (number "{num}" (effects (font (size 1.016 1.016)))))')

    lines.append(f'      )')
    lines.append(f'    )')
    return "\n".join(lines)


# ============================================================
# Pin position calculator
# ============================================================

# Pin definitions per symbol type: { symbol_name: [(pin_num, lib_x, lib_y, direction), ...] }
# direction: 0=right(left-side pin), 180=left(right-side pin), 270=down(top pin), 90=up(bottom pin)
# lib coords: Y positive UP

def get_2pin_positions():
    """Return pin positions for 2-pin vertical symbols."""
    return [
        ("1", 0, 3.81, 270),   # top pin
        ("2", 0, -3.81, 90),   # bottom pin
    ]

def get_ic_pin_positions(left_pins, right_pins):
    """Calculate pin positions for IC symbols."""
    n = max(len(left_pins), len(right_pins))
    half_h = round((n * 2.54) / 2 + 1.27, 2)
    body_w = 5.08
    positions = []

    for i, (num, _, _) in enumerate(left_pins):
        py = round(half_h - 1.27 - i * 2.54, 2)
        positions.append((num, -(body_w + 2.54), py, 0))

    for i, (num, _, _) in enumerate(right_pins):
        py = round(half_h - 1.27 - i * 2.54, 2)
        positions.append((num, body_w + 2.54, py, 180))

    return positions

def get_connector_pin_positions(pins):
    """Calculate pin positions for connector symbols."""
    n = len(pins)
    half_h = round((n * 2.54) / 2 + 1.27, 2)
    body_w = 5.08
    positions = []

    for i, (num, _, _) in enumerate(pins):
        py = round(half_h - 1.27 - i * 2.54, 2)
        positions.append((num, -(body_w + 2.54), py, 0))

    return positions


def pin_sheet_pos(sx, sy, lib_x, lib_y):
    """Convert lib coords to sheet coords. Sheet: Y positive down, Lib: Y positive up."""
    return (sx + lib_x, sy - lib_y)


def wire_and_label(pin_sx, pin_sy, direction, net_name):
    """Generate wire stub + global label for a pin."""
    STUB = 2.54
    if direction == 0:  # left-side pin, wire goes further left
        wx, wy = round(pin_sx - STUB, 2), round(pin_sy, 2)
        label_angle = 180
    elif direction == 180:  # right-side pin, wire goes further right
        wx, wy = round(pin_sx + STUB, 2), round(pin_sy, 2)
        label_angle = 0
    elif direction == 270:  # top pin, wire goes up (smaller y on sheet)
        wx, wy = round(pin_sx, 2), round(pin_sy - STUB, 2)
        label_angle = 90
    elif direction == 90:  # bottom pin, wire goes down (larger y on sheet)
        wx, wy = round(pin_sx, 2), round(pin_sy + STUB, 2)
        label_angle = 270
    else:
        raise ValueError(f"Unknown direction: {direction}")

    pin_sx, pin_sy = round(pin_sx, 2), round(pin_sy, 2)
    wire = (f'  (wire (pts (xy {pin_sx} {pin_sy}) (xy {wx} {wy}))\n'
            f'    (stroke (width 0) (type default))\n'
            f'    (uuid "{uid()}"))')
    label = (f'  (global_label "{net_name}" (shape passive) (at {wx} {wy} {label_angle})\n'
             f'    (effects (font (size 1.27 1.27)))\n'
             f'    (uuid "{uid()}")\n'
             f'    (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at 0 0 0)\n'
             f'      (effects (font (size 0.635 0.635)) hide)))')
    return wire + "\n" + label


# ============================================================
# Data: symbol type definitions
# ============================================================

TS3USB221_LEFT = [
    ("1", "VCC", "power_in"),
    ("2", "S", "input"),
    ("3", "D+", "bidirectional"),
    ("4", "D-", "bidirectional"),
    ("5", "~{OE}", "input"),
]
TS3USB221_RIGHT = [
    ("10", "1D+", "bidirectional"),
    ("9", "1D-", "bidirectional"),
    ("8", "2D+", "bidirectional"),
    ("7", "2D-", "bidirectional"),
    ("6", "GND", "power_in"),
]

USB_C_PINS = [
    ("1", "VBUS", "power_in"),
    ("2", "D+", "bidirectional"),
    ("3", "D-", "bidirectional"),
    ("4", "CC1", "passive"),
    ("5", "CC2", "passive"),
    ("6", "GND", "power_in"),
]

USB_A_PINS = [
    ("1", "VBUS", "power_in"),
    ("2", "D-", "bidirectional"),
    ("3", "D+", "bidirectional"),
    ("4", "GND", "power_in"),
]

CONN3_PINS = [
    ("1", "GND", "passive"),
    ("2", "SDA", "bidirectional"),
    ("3", "SCL", "bidirectional"),
]

ESP32_LEFT = []
ESP32_RIGHT = [
    ("1", "3V3", "power_out"),
    ("2", "GND", "power_in"),
    ("3", "GPIO4", "bidirectional"),
    ("4", "GPIO5", "bidirectional"),
    ("5", "GPIO6", "bidirectional"),
    ("6", "GPIO9", "bidirectional"),
    ("7", "GPIO10", "bidirectional"),
    ("8", "GPIO11", "bidirectional"),
    ("9", "GPIO18", "bidirectional"),
    ("10", "GPIO47", "bidirectional"),
]

# ============================================================
# Data: component placements (sheet coords, Y positive down)
# ============================================================

COMPONENTS = [
    # (ref, symbol_type, value, sx, sy, lcsc)
    ("J1", "USB_C", "USB-C Win", 50, 40, "C165948"),
    ("J2", "USB_C", "USB-C Mac", 50, 80, "C165948"),
    ("U1", "TS3USB221", "TS3USB221", 130, 50, "C130085"),
    ("J3", "USB_A", "USB-A Periph", 185, 50, "C168713"),
    ("D1", "D", "SS34", 85, 35, "C8678"),
    ("D2", "D", "SS34", 85, 60, "C8678"),
    ("C1", "C", "100nF", 115, 68, "C49678"),
    ("C2", "C", "10uF", 95, 42, "C15850"),
    ("R7", "R", "5.1k", 36, 52, "C27834"),
    ("R8", "R", "5.1k", 31, 52, "C27834"),
    ("R9", "R", "5.1k", 36, 92, "C27834"),
    ("R10", "R", "5.1k", 31, 92, "C27834"),
    ("U2", "ESP32", "ESP32-S3", 55, 150, ""),
    ("J4", "CONN3", "DDC LG", 130, 125, "C144394"),
    ("J5", "CONN3", "DDC RedmiA", 130, 145, "C144394"),
    ("J6", "CONN3", "DDC RedmiB", 130, 165, "C144394"),
    ("R1", "R", "4.7k", 158, 120, "C17673"),
    ("R2", "R", "4.7k", 163, 120, "C17673"),
    ("R3", "R", "4.7k", 158, 145, "C17673"),
    ("R4", "R", "4.7k", 163, 145, "C17673"),
    ("SW1", "SW", "BTN", 210, 128, "C318884"),
    ("R11", "R", "330R", 225, 140, "C23138"),
    ("LED1", "LED", "Green", 225, 152, "C2297"),
    ("R12", "R", "330R", 225, 168, "C23138"),
    ("LED2", "LED", "Blue", 225, 180, "C2293"),
]

# ============================================================
# Data: net connections
# net_name -> [(component_ref, pin_number), ...]
# ============================================================

NETS = {
    "GND": [
        ("J1", "6"), ("J2", "6"), ("U1", "5"), ("U1", "6"),
        ("J3", "4"), ("C1", "2"), ("C2", "2"),
        ("R7", "2"), ("R8", "2"), ("R9", "2"), ("R10", "2"),
        ("LED1", "2"), ("LED2", "2"), ("SW1", "2"),
        ("J4", "1"), ("J5", "1"), ("J6", "1"), ("U2", "2"),
    ],
    "VCC3V3": [
        ("U1", "1"), ("C1", "1"),
        ("R1", "1"), ("R2", "1"), ("R3", "1"), ("R4", "1"),
        ("U2", "1"),
    ],
    "VBUS_WIN": [("J1", "1"), ("D1", "1")],
    "VBUS_MAC": [("J2", "1"), ("D2", "1")],
    "VBUS_OUT": [("D1", "2"), ("D2", "2"), ("C2", "1"), ("J3", "1")],
    "WIN_DP":  [("J1", "2"), ("U1", "10")],
    "WIN_DN":  [("J1", "3"), ("U1", "9")],
    "MAC_DP":  [("J2", "2"), ("U1", "8")],
    "MAC_DN":  [("J2", "3"), ("U1", "7")],
    "COM_DP":  [("U1", "3"), ("J3", "3")],
    "COM_DN":  [("U1", "4"), ("J3", "2")],
    "CC1_WIN": [("J1", "4"), ("R7", "1")],
    "CC2_WIN": [("J1", "5"), ("R8", "1")],
    "CC1_MAC": [("J2", "4"), ("R9", "1")],
    "CC2_MAC": [("J2", "5"), ("R10", "1")],
    "USB_SEL": [("U1", "2"), ("U2", "3")],
    "I2C0_SCL": [("U2", "9"), ("J4", "3"), ("R1", "2")],
    "I2C0_SDA": [("U2", "10"), ("J4", "2"), ("R2", "2")],
    "I2C1_SCL": [("U2", "4"), ("J5", "3"), ("J6", "3"), ("R3", "2")],
    "I2C1_SDA": [("U2", "5"), ("J5", "2"), ("J6", "2"), ("R4", "2")],
    "BTN":     [("U2", "6"), ("SW1", "1")],
    "LED_WIN": [("U2", "7"), ("R11", "1")],
    "LED_MAC": [("U2", "8"), ("R12", "1")],
    "LED1_A":  [("R11", "2"), ("LED1", "1")],
    "LED2_A":  [("R12", "2"), ("LED2", "1")],
}

# ============================================================
# Pin position lookup
# ============================================================

# Build pin position tables for each symbol type
SYMBOL_PIN_POSITIONS = {}

# 2-pin types
for sym_name in ["R", "C", "D", "LED", "SW"]:
    SYMBOL_PIN_POSITIONS[sym_name] = get_2pin_positions()

# IC types
SYMBOL_PIN_POSITIONS["TS3USB221"] = get_ic_pin_positions(TS3USB221_LEFT, TS3USB221_RIGHT)

# Connectors
SYMBOL_PIN_POSITIONS["USB_C"] = get_connector_pin_positions(USB_C_PINS)
SYMBOL_PIN_POSITIONS["USB_A"] = get_connector_pin_positions(USB_A_PINS)
SYMBOL_PIN_POSITIONS["CONN3"] = get_connector_pin_positions(CONN3_PINS)

# ESP32 (right-side pins only)
SYMBOL_PIN_POSITIONS["ESP32"] = get_ic_pin_positions(ESP32_LEFT, ESP32_RIGHT)


def find_pin(symbol_type, pin_num):
    """Find (lib_x, lib_y, direction) for a pin number in a symbol type."""
    for pnum, px, py, d in SYMBOL_PIN_POSITIONS[symbol_type]:
        if pnum == pin_num:
            return (px, py, d)
    raise ValueError(f"Pin {pin_num} not found in {symbol_type}")


# ============================================================
# Output generation
# ============================================================

def generate():
    lines = []

    # Header
    lines.append(f'(kicad_sch (version 20231120) (generator "claude_kvm")')
    lines.append(f'  (uuid "{ROOT_UUID}")')
    lines.append(f'  (paper "A3")')
    lines.append(f'')

    # Lib symbols
    lines.append(f'  (lib_symbols')
    lines.append(sym_2pin("R", ref_prefix="R"))
    lines.append(sym_2pin("C", ref_prefix="C"))
    lines.append(sym_2pin("D", pin1_name="A", pin2_name="K", body="triangle", ref_prefix="D"))
    lines.append(sym_2pin("LED", pin1_name="A", pin2_name="K", body="triangle", ref_prefix="LED"))
    lines.append(sym_2pin("SW", ref_prefix="SW"))
    lines.append(sym_ic("TS3USB221", TS3USB221_LEFT, TS3USB221_RIGHT))
    lines.append(sym_connector("USB_C", USB_C_PINS))
    lines.append(sym_connector("USB_A", USB_A_PINS))
    lines.append(sym_connector("CONN3", CONN3_PINS))
    lines.append(sym_ic("ESP32", ESP32_LEFT, ESP32_RIGHT))
    lines.append(f'  )')
    lines.append(f'')

    # Component instances
    comp_map = {}  # ref -> (symbol_type, sx, sy)
    for ref, sym_type, value, sx, sy, lcsc in COMPONENTS:
        comp_map[ref] = (sym_type, sx, sy)
        u = uid()

        ref_prefix = ref.rstrip("0123456789")
        lines.append(f'  (symbol (lib_id "KVM:{sym_type}") (at {sx} {sy} 0) (unit 1)')
        lines.append(f'    (in_bom yes) (on_board yes)')
        lines.append(f'    (uuid "{u}")')
        lines.append(f'    (property "Reference" "{ref}" (at {sx} {sy - 2.54} 0)')
        lines.append(f'      (effects (font (size 1.27 1.27))))')
        lines.append(f'    (property "Value" "{value}" (at {sx} {sy + 2.54} 0)')
        lines.append(f'      (effects (font (size 1.27 1.27))))')
        lines.append(f'    (property "Footprint" "" (at {sx} {sy} 0)')
        lines.append(f'      (effects (font (size 1.27 1.27)) hide))')
        if lcsc:
            lines.append(f'    (property "LCSC" "{lcsc}" (at {sx} {sy} 0)')
            lines.append(f'      (effects (font (size 1.27 1.27)) hide))')
        lines.append(f'    (instances')
        lines.append(f'      (project "KVM_Switch"')
        lines.append(f'        (path "/{ROOT_UUID}" (reference "{ref}") (unit 1))))')
        lines.append(f'  )')
        lines.append(f'')

    # Wires and global labels for each net
    lines.append(f'  ; ====== Net connections (wires + global labels) ======')
    for net_name, connections in NETS.items():
        lines.append(f'  ; --- {net_name} ---')
        for comp_ref, pin_num in connections:
            sym_type, sx, sy = comp_map[comp_ref]
            lib_x, lib_y, direction = find_pin(sym_type, pin_num)
            pin_sx, pin_sy = pin_sheet_pos(sx, sy, lib_x, lib_y)
            wl = wire_and_label(pin_sx, pin_sy, direction, net_name)
            lines.append(wl)
        lines.append(f'')

    lines.append(f')')
    return "\n".join(lines)


if __name__ == "__main__":
    print(generate())
