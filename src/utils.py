from machine import Pin, mem32
import uasyncio as asyncio
import neopixel


def gpio_func_out(n):
    GPIO_FUNCn_OUT_SEL_CFG_REG = 0x3FF44530 + 0x4 * n
    return GPIO_FUNCn_OUT_SEL_CFG_REG


# Init led with neopixel library. Need to change the signal to Pin
def init_LED(pin_number=25):  
    pin = Pin(pin_number, Pin.OUT)
    n = neopixel.NeoPixel(pin, 1)
    # Getting GPIO_FUNC25_OUT_SEL_CFG_REG address
    r = gpio_func_out(25)
    # Setting 9'th bit to 1 for inverting the IO
    #  https://www.espressif.com/sites/default/files/documentation/esp32_technical_reference_manual_en.pdf
    # page 70
    mem32[r] |= 1 << 9
    return n


# Function for blinkin with led
async def blink(c=(10, 0, 0)):
    led = init_LED()
    while True:
        led[0] = c
        r, g, b = c
        g = g ^ 10
        b = b ^ 10
        c = ( r, g, b)
        led.write()
        await asyncio.sleep_ms(200)
