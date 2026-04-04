/*
 * ESP32-S3 一键 KVM 切换器
 *
 * 功能：USB 键盘控制 LG 显示器输入源 + TS3USB221 USB 外设切换
 *
 * 按 A 键 → 切到 Windows (LG HDMI1 + USB Port1)
 * 按 B 键 → 切到 MacBook  (LG DP1   + USB Port2)
 *
 * 硬件接线：
 *   GPIO 4  → TS3USB221 SEL 引脚 (LOW=Windows, HIGH=MacBook)
 *   GPIO 18 → LG HDMI 分线板 SCL (上排第8针, Pin15) + 4.7kΩ 上拉到 3.3V
 *   GPIO 47 → LG HDMI 分线板 SDA (下排第9针, Pin16) + 4.7kΩ 上拉到 3.3V
 *   GND     → LG HDMI 分线板 GND (上排第3针, Pin5)
 *   USB-C   → 键盘 (通过 USB Host)
 *
 * LG 34GS95QE DDC/CI Alt 模式：
 *   I2C 地址: 0x37, 源地址: 0x50, VCP: 0xF4
 *   HDMI1 = 0x0090 (Windows)
 *   DP1   = 0x00D0 (MacBook)
 */

#include <stdio.h>
#include <string.h>
#include <inttypes.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "driver/gpio.h"
#include "driver/i2c_master.h"
#include "esp_log.h"
#include "usb/usb_host.h"
#include "usb/hid_host.h"
#include "usb/hid_usage_keyboard.h"

static const char *TAG = "KVM";

/* ========== 引脚定义 ========== */

#define PIN_USB_SEL     GPIO_NUM_4      /* TS3USB221 SEL 引脚 */
#define PIN_I2C_SCL     GPIO_NUM_18     /* DDC SCL */
#define PIN_I2C_SDA     GPIO_NUM_47     /* DDC SDA */

/* ========== DDC/CI 参数 (LG Alt 模式) ========== */

#define DDC_I2C_ADDR        0x37
#define DDC_I2C_FREQ_HZ     50000   /* 50kHz，LG 推荐较低速率 */

#define DDC_SRC_ADDR_LG     0x50    /* LG Alt 源地址 (标准为 0x51) */
#define DDC_VCP_LG_INPUT    0xF4    /* LG Alt VCP 代码 (标准为 0x60) */

#define LG_INPUT_HDMI1      0x0090  /* Windows - Gaming PC */
#define LG_INPUT_HDMI2      0x0091
#define LG_INPUT_DP1        0x00D0  /* MacBook Pro */
#define LG_INPUT_DP2        0x00D1

/* ========== HID 键码 ========== */

#define HID_KEYCODE_A       0x04
#define HID_KEYCODE_B       0x05

/* ========== 全局状态 ========== */

typedef enum {
    TARGET_WINDOWS = 0,
    TARGET_MACBOOK = 1,
} kvm_target_t;

static kvm_target_t current_target = TARGET_WINDOWS;
static uint8_t prev_keys[6] = {0};

/* I2C 句柄 */
static i2c_master_bus_handle_t i2c_bus = NULL;
static i2c_master_dev_handle_t ddc_dev = NULL;

/* ========== I2C / DDC 初始化 ========== */

static void ddc_i2c_init(void)
{
    /* 创建 I2C 主总线 */
    i2c_master_bus_config_t bus_cfg = {
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .i2c_port = I2C_NUM_0,
        .scl_io_num = PIN_I2C_SCL,
        .sda_io_num = PIN_I2C_SDA,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = false,  /* 外部已接 4.7kΩ 上拉 */
    };
    ESP_ERROR_CHECK(i2c_new_master_bus(&bus_cfg, &i2c_bus));

    /* 添加 DDC 设备 (0x37) */
    i2c_device_config_t dev_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = DDC_I2C_ADDR,
        .scl_speed_hz = DDC_I2C_FREQ_HZ,
    };
    ESP_ERROR_CHECK(i2c_master_bus_add_device(i2c_bus, &dev_cfg, &ddc_dev));

    ESP_LOGI(TAG, "I2C 初始化完成 — SCL=GPIO%d, SDA=GPIO%d, 设备=0x%02X, 频率=%dHz",
             PIN_I2C_SCL, PIN_I2C_SDA, DDC_I2C_ADDR, DDC_I2C_FREQ_HZ);
}

/* ========== DDC/CI LG Alt 模式发送 ========== */

/*
 * 数据包格式：
 *   I2C 写到 0x37 (总线地址 0x6E)
 *   [0] 0x50        源地址 (LG Alt)
 *   [1] 0x84        长度 | 0x80 (4字节负载)
 *   [2] 0x03        VCP Set 操作码
 *   [3] vcp         VCP 代码
 *   [4] value_high  值高字节
 *   [5] value_low   值低字节
 *   [6] checksum    = 0x6E ⊕ [0] ⊕ [1] ⊕ [2] ⊕ [3] ⊕ [4] ⊕ [5]
 */
static esp_err_t ddc_write_lg(uint8_t vcp, uint16_t value)
{
    uint8_t pkt[7];
    pkt[0] = DDC_SRC_ADDR_LG;              /* 0x50 */
    pkt[1] = 0x84;                          /* 长度 | 0x80 */
    pkt[2] = 0x03;                          /* VCP Set */
    pkt[3] = vcp;                           /* VCP 代码 */
    pkt[4] = (uint8_t)(value >> 8);         /* 值高字节 */
    pkt[5] = (uint8_t)(value & 0xFF);       /* 值低字节 */

    /* 校验和: 0x6E ⊕ 所有数据字节 */
    uint8_t chk = 0x6E;
    for (int i = 0; i < 6; i++) {
        chk ^= pkt[i];
    }
    pkt[6] = chk;

    esp_err_t err = i2c_master_transmit(ddc_dev, pkt, sizeof(pkt), 1000);
    return err;
}

/* ========== GPIO 初始化 ========== */

static void gpio_init(void)
{
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << PIN_USB_SEL),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&io_conf);
    gpio_set_level(PIN_USB_SEL, 0);     /* 默认 Windows */
    ESP_LOGI(TAG, "GPIO%d (USB SEL) 初始化完成", PIN_USB_SEL);
}

/* ========== KVM 切换核心逻辑 ========== */

static void kvm_switch_to(kvm_target_t target)
{
    if (target == current_target) {
        ESP_LOGI(TAG, "已经在 %s，无需切换",
                 target == TARGET_WINDOWS ? "Windows" : "MacBook");
        return;
    }

    const char *name;
    uint16_t lg_input;
    int usb_level;

    if (target == TARGET_WINDOWS) {
        name = "Windows";
        lg_input = LG_INPUT_HDMI1;      /* LG 切到 HDMI1 */
        usb_level = 0;                   /* TS3USB221 SEL=LOW → Port1 */
    } else {
        name = "MacBook";
        lg_input = LG_INPUT_DP1;         /* LG 切到 DP1 */
        usb_level = 1;                   /* TS3USB221 SEL=HIGH → Port2 */
    }

    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, ">> 切换到 %s", name);

    /* 1. 发送 DDC/CI 命令切换 LG 显示器 */
    esp_err_t err = ddc_write_lg(DDC_VCP_LG_INPUT, lg_input);
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "   LG 显示器: VCP=0xF4 → 0x%04X (%s) ✓",
                 lg_input,
                 lg_input == LG_INPUT_HDMI1 ? "HDMI1" : "DP1");
    } else {
        ESP_LOGW(TAG, "   LG 显示器: DDC 发送失败 (err=%s)", esp_err_to_name(err));
    }

    /* 2. 切换 USB (TS3USB221) */
    gpio_set_level(PIN_USB_SEL, usb_level);
    ESP_LOGI(TAG, "   USB 外设:  SEL=%d → %s ✓", usb_level, name);

    current_target = target;
    ESP_LOGI(TAG, "========================================");
}

/* ========== 键盘报告解析 ========== */

static void process_keyboard_report(const uint8_t *data, int length)
{
    if (length < 8) return;

    /* HID 键盘报告: [modifier, reserved, key1..key6] */
    for (int i = 2; i < 8; i++) {
        uint8_t key = data[i];
        if (key == 0) continue;

        /* 检查是否为新按下的键（去重） */
        bool is_new = true;
        for (int j = 0; j < 6; j++) {
            if (prev_keys[j] == key) {
                is_new = false;
                break;
            }
        }

        if (is_new) {
            if (key == HID_KEYCODE_A) {
                kvm_switch_to(TARGET_WINDOWS);
            } else if (key == HID_KEYCODE_B) {
                kvm_switch_to(TARGET_MACBOOK);
            } else {
                ESP_LOGD(TAG, "其他按键: 0x%02X (当前=%s)",
                         key,
                         current_target == TARGET_WINDOWS ? "Windows" : "MacBook");
            }
        }
    }

    memcpy(prev_keys, data + 2, 6);
}

/* ========== HID Host 回调 ========== */

static void hid_host_interface_callback(hid_host_device_handle_t hid_device,
                                         const hid_host_interface_event_t event,
                                         void *arg)
{
    switch (event) {
    case HID_HOST_INTERFACE_EVENT_INPUT_REPORT: {
        uint8_t data[64] = {0};
        size_t data_length = sizeof(data);
        hid_host_device_get_raw_input_report_data(hid_device, data, sizeof(data), &data_length);
        process_keyboard_report(data, data_length);
        break;
    }
    case HID_HOST_INTERFACE_EVENT_TRANSFER_ERROR:
        ESP_LOGW(TAG, "HID 传输错误");
        break;
    case HID_HOST_INTERFACE_EVENT_DISCONNECTED:
        ESP_LOGW(TAG, "键盘已断开");
        hid_host_device_close(hid_device);
        break;
    default:
        break;
    }
}

static void hid_host_device_callback(hid_host_device_handle_t hid_device,
                                      const hid_host_driver_event_t event,
                                      void *arg)
{
    switch (event) {
    case HID_HOST_DRIVER_EVENT_CONNECTED: {
        ESP_LOGI(TAG, "键盘已连接!");

        const hid_host_device_config_t dev_config = {
            .callback = hid_host_interface_callback,
            .callback_arg = NULL,
        };

        hid_host_device_open(hid_device, &dev_config);
        hid_host_device_start(hid_device);
        break;
    }
    default:
        break;
    }
}

/* ========== USB Host 事件处理任务 ========== */

static void usb_host_lib_task(void *arg)
{
    ESP_LOGI(TAG, "USB Host 事件处理任务已启动");
    while (true) {
        uint32_t event_flags;
        esp_err_t err = usb_host_lib_handle_events(pdMS_TO_TICKS(500), &event_flags);

        if (err == ESP_OK) {
            if (event_flags & USB_HOST_LIB_EVENT_FLAGS_NO_CLIENTS) {
                usb_host_device_free_all();
            }
        }
    }
}

/* ========== 主函数 ========== */

void app_main(void)
{
    ESP_LOGI(TAG, "");
    ESP_LOGI(TAG, "╔══════════════════════════════════╗");
    ESP_LOGI(TAG, "║    ESP32-S3 一键 KVM 切换器      ║");
    ESP_LOGI(TAG, "║    A = Windows    B = MacBook     ║");
    ESP_LOGI(TAG, "╚══════════════════════════════════╝");
    ESP_LOGI(TAG, "");

    /* 1. GPIO 初始化 (TS3USB221 SEL) */
    gpio_init();

    /* 2. I2C 初始化 (DDC/CI → LG 显示器) */
    ddc_i2c_init();

    /* 3. 安装 USB Host 库 */
    const usb_host_config_t host_config = {
        .skip_phy_setup = false,
        .intr_flags = ESP_INTR_FLAG_LEVEL1,
    };
    ESP_ERROR_CHECK(usb_host_install(&host_config));
    ESP_LOGI(TAG, "USB Host 库已安装");

    /* 4. 启动 USB Host 事件处理任务 */
    xTaskCreatePinnedToCore(usb_host_lib_task, "usb_host_lib", 4096,
                            NULL, 2, NULL, 0);

    /* 5. 安装 HID Host 驱动 */
    const hid_host_driver_config_t hid_config = {
        .create_background_task = true,
        .task_priority = 5,
        .stack_size = 4096,
        .core_id = 0,
        .callback = hid_host_device_callback,
        .callback_arg = NULL,
    };
    ESP_ERROR_CHECK(hid_host_install(&hid_config));
    ESP_LOGI(TAG, "HID Host 驱动已安装");

    /* 6. 就绪 */
    ESP_LOGI(TAG, "");
    ESP_LOGI(TAG, "当前状态: Windows (默认)");
    ESP_LOGI(TAG, "等待键盘连接...");
}