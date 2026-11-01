"""Central design description for the VaultKey USB hardware project.

This file is intentionally data-only so that the PCB builder, the schematic
builder and the fabrication exporter all describe exactly the same circuit.

Board geometry is locked by the supplied VaultKey_USB_Cutout specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Mechanical definition (mm)
# ---------------------------------------------------------------------------

BOARD_W = 112.5
BOARD_H = 50.0
BODY_X0 = 12.0
TONGUE_X1 = 12.0
TONGUE_Y0 = 19.0
TONGUE_Y1 = 31.0
TIP_CHAMFER = 0.5

# Closed outline, counter-clockwise on screen.  The 0.5 mm chamfers are at the
# free (tip) end of the USB-A tongue.
OUTLINE = [
    (0.0, 19.5),
    (0.5, 19.0),
    (12.0, 19.0),
    (12.0, 0.0),
    (112.5, 0.0),
    (112.5, 50.0),
    (12.0, 50.0),
    (12.0, 31.0),
    (0.5, 31.0),
    (0.0, 30.5),
]

MOUNTING_HOLES = {
    "H1": (16.0, 3.5),
    "H2": (15.0, 47.0),
    "H3": (108.5, 3.5),
    "H4": (108.0, 46.0),
}

# ---------------------------------------------------------------------------
# Nets
# ---------------------------------------------------------------------------

NETS = [
    "GND",
    "+5V",
    "+3V3",
    "USB_VBUS",
    "USB_DM",
    "USB_DP",
    "OLED_SDA",
    "OLED_SCL",
    "OLED_RST",
    "SW_UP",
    "SW_DOWN",
    "SW_SELECT",
    "SW_BACK",
    "EN",
    "BOOT",
    "VBAT",
    "RTC_X1",
    "RTC_X2",
    "RTC_SDA",
    "RTC_SCL",
    "I2C_BIAS",
    "LED_A",
]

# Nets that get a wider track when the router is allowed to choose.
POWER_NETS = {"GND", "+5V", "+3V3", "USB_VBUS"}


# ---------------------------------------------------------------------------
# Symbols / footprints
# ---------------------------------------------------------------------------

USB_FP_LIB = "VaultKey"
USB_FP_NAME = "VaultKey_USB_A_Male_PCB_Edge"
MOUNT_FP_LIB = "VaultKey"
MOUNT_FP_NAME = "MountingHole_2.7mm_NPTH_Custom"


@dataclass
class Part:
    ref: str
    value: str
    lib: str                 # KiCad footprint library nickname
    fp: str                  # footprint name inside that library
    x: float
    y: float
    rot: float = 0.0
    side: str = "F"          # "F" or "B"
    flip_lr: bool = False    # only relevant for B-side SMD parts
    pads: dict[str, str] = field(default_factory=dict)
    dnp: bool = False
    description: str = ""


PARTS: list[Part] = [
    # ---- USB input and protection -------------------------------------
    Part("J1", "USB_A_MALE_EDGE", USB_FP_LIB, USB_FP_NAME, 9.5, 25.0, -90,
         pads={"1": "USB_VBUS", "2": "USB_DM", "3": "USB_DP", "4": "GND"},
         description="USB 2.0 Type-A male edge connector"),
    Part("F1", "0.5A_Polyfuse", "Fuse", "Fuse_1206_3216Metric", 14.6, 10.0, 0,
         pads={"1": "USB_VBUS", "2": "+5V"},
         description="Resettable 0.5 A USB input fuse"),
    Part("C9", "1uF", "Capacitor_SMD", "C_0805_2012Metric", 18.5, 10.0, 90,
         pads={"1": "+5V", "2": "GND"},
         description="USB VBUS input bypass"),
    Part("U5", "USBLC6-2SC6", "Package_TO_SOT_SMD", "SOT-23-6", 17.0, 25.05, 0,
         side="B", flip_lr=False,
         pads={"1": "USB_DP", "2": "GND", "3": "USB_DM",
               "4": "USB_DM", "5": "+5V", "6": "USB_DP"},
         description="USB ESD protection array"),

    # ---- 5 V to 3.3 V linear regulator --------------------------------
    Part("U3", "AMS1117-3.3", "Package_TO_SOT_SMD", "SOT-223-3_TabPin2",
         27.0, 7.0, 0,
         pads={"1": "GND", "2": "+3V3", "3": "+5V"},
         description="1 A low-dropout 3.3 V regulator"),
    Part("C1", "10uF", "Capacitor_SMD", "C_1206_3216Metric", 20.8, 9.3, 90,
         pads={"1": "+5V", "2": "GND"}, description="Regulator input capacitor"),
    Part("C2", "22uF", "Capacitor_SMD", "C_1206_3216Metric", 33.0, 7.0, 90,
         pads={"1": "+3V3", "2": "GND"}, description="Regulator output capacitor"),
    Part("C3", "10uF", "Capacitor_SMD", "C_1206_3216Metric", 76.0, 44.6, 90,
         pads={"1": "+3V3", "2": "GND"}, description="ESP32 bulk decoupling"),
    Part("C6", "100nF", "Capacitor_SMD", "C_0805_2012Metric", 51.0, 44.6, 90,
         pads={"1": "+3V3", "2": "GND"}, description="ESP32 local decoupling"),
    Part("C8", "100nF", "Capacitor_SMD", "C_0805_2012Metric", 36.0, 11.0, 90,
         pads={"1": "+5V", "2": "GND"}, description="OLED VIN bypass"),

    # ---- Power indicator ----------------------------------------------
    Part("R5", "1k", "Resistor_SMD", "R_0805_2012Metric", 47.5, 3.5, 0,
         pads={"1": "+3V3", "2": "LED_A"}, description="Power LED series resistor"),
    Part("D1", "GREEN", "LED_SMD", "LED_0805_2012Metric", 51.5, 3.5, 0,
         pads={"1": "GND", "2": "LED_A"},
         description="3.3 V power indicator LED (pad 1 cathode)"),

    # ---- ESP32-S3 module ----------------------------------------------
    Part("U1", "ESP32-S3-WROOM-1U", "RF_Module", "ESP32-S3-WROOM-1U",
         62.0, 37.5, 180,
         pads={
             "1": "GND", "2": "+3V3", "3": "EN",
             "4": "SW_SELECT", "5": "SW_DOWN", "6": "SW_BACK", "7": "SW_UP",
             "12": "OLED_SDA", "13": "USB_DM", "14": "USB_DP",
             "17": "OLED_SCL", "21": "OLED_RST", "27": "BOOT",
             "40": "GND", "41": "GND",
         },
         description="ESP32-S3 Wi-Fi/BLE module with external antenna"),

    # ---- OLED display -------------------------------------------------
    Part("DS1", "Adafruit_SSD1306_128x64", "VaultKey",
         "Adafruit_SSD1306_NoMountingHoles",
         23.088, 16.0, 0,
         pads={"1": "OLED_SDA", "2": "OLED_SCL", "3": "GND", "4": "OLED_RST",
               "5": "GND", "7": "+5V", "8": "GND"},
         description="Adafruit 1.3 inch 128x64 I2C OLED breakout"),

    # ---- DS1307 RTC ---------------------------------------------------
    Part("U2", "DS1307+", "Package_DIP", "DIP-8_W7.62mm", 64.585, 3.545, 0,
         pads={"1": "RTC_X1", "2": "RTC_X2", "3": "VBAT", "4": "GND",
               "5": "RTC_SDA", "6": "RTC_SCL", "8": "+5V"},
         description="I2C real-time clock"),
    Part("X1", "32.768kHz", "Crystal", "Crystal_SMD_3215-2Pin_3.2x1.5mm",
         58.7, 4.815, 0,
         pads={"1": "RTC_X1", "2": "RTC_X2"}, description="RTC crystal"),
    Part("BT1", "CR2032", "Battery",
         "BatteryHolder_Keystone_1058_1x2032", 96.0, 18.0, 90,
         side="B", flip_lr=True,
         pads={"1": "VBAT", "2": "GND"},
         description="Keystone 1058 low-profile slot-style CR2032 holder"),

    # ---- I2C level translation ---------------------------------------
    Part("U4", "PCA9306", "Package_SO", "TSSOP-8_3x3mm_P0.65mm", 78.0, 7.0, 0,
         # TI PCA9306: 1 GND, 2 VREF1 (3.3 V side), 3 SCL1, 4 SDA1,
         # 5 SDA2 (5 V side), 6 SCL2, 7 VREF2, 8 EN.
         pads={"1": "GND", "2": "+3V3", "3": "OLED_SCL", "4": "OLED_SDA",
               "5": "RTC_SDA", "6": "RTC_SCL", "7": "I2C_BIAS", "8": "I2C_BIAS"},
         description="Bidirectional I2C level translator, 3.3 V to 5 V"),
    Part("C5", "100pF", "Capacitor_SMD", "C_0805_2012Metric", 82.0, 7.0, 90,
         pads={"1": "I2C_BIAS", "2": "GND"},
         description="PCA9306 VREF2/EN filter capacitor"),
    Part("R8", "200k", "Resistor_SMD", "R_0805_2012Metric", 84.5, 6.0, 90,
         # The resistor is non-polar; this assignment puts +5 V on the pad
         # nearest the existing rail and I2C_BIAS nearest C5.
         pads={"1": "I2C_BIAS", "2": "+5V"},
         description="PCA9306 VREF2/EN bias resistor (TI recommended)"),
    Part("C4", "100nF", "Capacitor_SMD", "C_0805_2012Metric", 79.5, 3.0, 90,
         pads={"1": "+5V", "2": "GND"}, description="DS1307 VCC bypass"),

    # ---- I2C pull-ups --------------------------------------------------
    Part("R1", "4.7k", "Resistor_SMD", "R_0805_2012Metric", 65.0, 18.0, 90,
         pads={"1": "+3V3", "2": "OLED_SDA"}, description="3.3 V SDA pull-up"),
    Part("R2", "4.7k", "Resistor_SMD", "R_0805_2012Metric", 67.5, 18.0, 90,
         pads={"1": "+3V3", "2": "OLED_SCL"}, description="3.3 V SCL pull-up"),
    Part("R3", "4.7k", "Resistor_SMD", "R_0805_2012Metric", 70.0, 18.0, 90,
         pads={"1": "+5V", "2": "RTC_SDA"}, description="5 V SDA pull-up"),
    Part("R4", "4.7k", "Resistor_SMD", "R_0805_2012Metric", 72.5, 18.0, 90,
         pads={"1": "+5V", "2": "RTC_SCL"}, description="5 V SCL pull-up"),

    # ---- User controls -------------------------------------------------
    Part("SW1", "UP", "Button_Switch_SMD",
         "SW_Push_1TS009xxxx-xxxx-xxxx_6x6x5mm", 86.5, 12.0, 0,
         pads={"1": "SW_UP", "2": "GND"}, description="Navigation up"),
    Part("SW2", "DOWN", "Button_Switch_SMD",
         "SW_Push_1TS009xxxx-xxxx-xxxx_6x6x5mm", 87.0, 33.5, 0,
         pads={"1": "SW_DOWN", "2": "GND"}, description="Navigation down"),
    Part("SW3", "SELECT", "Button_Switch_SMD",
         "SW_Push_1TS009xxxx-xxxx-xxxx_6x6x5mm", 95.0, 22.0, 0,
         pads={"1": "SW_SELECT", "2": "GND"}, description="Navigation select"),
    Part("SW4", "BACK", "Button_Switch_SMD",
         "SW_Push_1TS009xxxx-xxxx-xxxx_6x6x5mm", 77.5, 22.0, 0,
         pads={"1": "SW_BACK", "2": "GND"}, description="Navigation back"),

    # ---- Recessed reset / boot strap -----------------------------------
    # The BOOT button was removed.  GPIO0 is held HIGH by R7 so the module
    # always boots normally from flash; native USB-Serial/JTAG handles
    # automatic download mode, so no BOOT button is required.
    # SW5 is a tiny SMD tactile switch reached through a pinhole in the
    # enclosure, not a finger-operated control.
    Part("SW5", "RESET", "Button_Switch_SMD",
         "SW_Push_1P1T_NO_Vertical_Wuerth_434133025816", 104.0, 13.5, 0,
         pads={"1": "EN", "2": "GND"},
         description="Recessed EN/reset switch, needle access only"),
    Part("R6", "10k", "Resistor_SMD", "R_0805_2012Metric", 99.0, 8.0, 90,
         pads={"1": "+3V3", "2": "EN"}, description="EN pull-up"),
    Part("C7", "100nF", "Capacitor_SMD", "C_0805_2012Metric", 101.5, 8.0, 90,
         pads={"1": "EN", "2": "GND"}, description="EN RC delay capacitor"),
    Part("R7", "10k", "Resistor_SMD", "R_0805_2012Metric", 99.0, 39.5, 90,
         pads={"1": "+3V3", "2": "BOOT"}, description="BOOT/GPIO0 pull-up"),
]

for _ref, (_x, _y) in MOUNTING_HOLES.items():
    PARTS.append(
        Part(_ref, "MountingHole_2.7mm", MOUNT_FP_LIB, MOUNT_FP_NAME,
             _x, _y, 0, pads={}, description="M2.5 non-plated mounting hole")
    )


def part_by_ref(ref: str) -> Part:
    for p in PARTS:
        if p.ref == ref:
            return p
    raise KeyError(ref)


# Footprint library nicknames used by the board builder.
FOOTPRINT_LIBS = {
    "VaultKey": "lib/VaultKey.pretty",
    "Button_Switch_SMD": "/usr/share/kicad/footprints/Button_Switch_SMD.pretty",
    "Capacitor_SMD": "/usr/share/kicad/footprints/Capacitor_SMD.pretty",
    "Crystal": "/usr/share/kicad/footprints/Crystal.pretty",
    "Battery": "/usr/share/kicad/footprints/Battery.pretty",
    "Display": "/usr/share/kicad/footprints/Display.pretty",
    "Fuse": "/usr/share/kicad/footprints/Fuse.pretty",
    "LED_SMD": "/usr/share/kicad/footprints/LED_SMD.pretty",
    "Package_DIP": "/usr/share/kicad/footprints/Package_DIP.pretty",
    "Package_SO": "/usr/share/kicad/footprints/Package_SO.pretty",
    "Package_TO_SOT_SMD": "/usr/share/kicad/footprints/Package_TO_SOT_SMD.pretty",
    "RF_Module": "/usr/share/kicad/footprints/RF_Module.pretty",
    "Resistor_SMD": "/usr/share/kicad/footprints/Resistor_SMD.pretty",
}
