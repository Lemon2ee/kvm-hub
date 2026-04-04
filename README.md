# TS3USB221 USB 切换器 - ESP32-S3 USB Host 键盘控制

## 项目结构

```
usb_switch_project/
├── CMakeLists.txt
├── sdkconfig.defaults
└── main/
    ├── CMakeLists.txt
    ├── idf_component.yml    ← 自动拉取 usb_host_hid 组件
    └── main.c               ← 主程序
```

## 编译 & 烧录

1. VS Code 打开此文件夹
2. 底部状态栏选择 ESP32-S3 为目标芯片
3. 底部状态栏选择你的串口 (COM 口)
4. 点击底部 🔥 Build/Flash/Monitor

或者命令行:
```bash
idf.py set-target esp32s3
idf.py build
idf.py -p /dev/ttyACM0 flash monitor
```

## 用法

键盘插到 ESP32-S3 空着的那个 USB-C 口 (可能需要 USB-C 转 USB-A 转接头)
按 A → Port 1
按 B → Port 2
