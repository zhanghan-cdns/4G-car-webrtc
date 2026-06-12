from periphery import SPI
import lgpio
import time

# 引脚（固定不变）
DC  = 16
RST = 18
BLK = 22

# 初始化GPIO
h = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(h, DC)
lgpio.gpio_claim_output(h, RST)
lgpio.gpio_claim_output(h, BLK)

# 打开背光
lgpio.gpio_write(h, BLK, 1)

# SPI1.1 硬件片选 CS1(Pin26)
spi = SPI("/dev/spidev1.1", 0, 40000000)

def wr_cmd(c):
    lgpio.gpio_write(h, DC, 0)
    spi.transfer([c])

def wr_data(d):
    lgpio.gpio_write(h, DC, 1)
    spi.transfer(d if isinstance(d, list) else [d])

# 复位
lgpio.gpio_write(h, RST, 0)
time.sleep(0.1)
lgpio.gpio_write(h, RST, 1)
time.sleep(0.1)

# ST7789 基础初始化
wr_cmd(0x11)
time.sleep(0.1)
wr_cmd(0x36)
wr_data(0x00)
wr_cmd(0x3A)
wr_data(0x55)   # 16位RGB565颜色
wr_cmd(0x29)

# ========== 纯色配置 ==========
# RGB565 格式：2字节表示一个像素，下面给常用色值
# 示例：0xFFFF 纯白 | 0x0000 纯黑 | 0xF800 红 | 0x07E0 绿 | 0x001F 蓝
COLOR = [0x00, 0x00]  # 纯黑，按需修改

# 构建大缓冲区，高速刷屏
BUF_LEN = 2048
color_buf = COLOR * (BUF_LEN // 2)

print("屏幕填充纯色...")
while True:
    wr_data(color_buf)