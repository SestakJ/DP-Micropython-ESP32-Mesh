from micropython import const
from machine import Pin, mem32
import uasyncio as asyncio
import neopixel


pin = Pin(25, Pin.OUT)
n = neopixel.NeoPixel(pin, 1)


def gpio_func_out(n):
    GPIO_FUNCn_OUT_SEL_CFG_REG = 0x3FF44530 + 0x4 * n
    return GPIO_FUNCn_OUT_SEL_CFG_REG


async def main():
    # Getting GPIO_FUNC25_OUT_SEL_CFG_REG address
    r = gpio_func_out(25)
    # Setting 9'th bit to 1 for inverting the IO
    #  https://www.espressif.com/sites/default/files/documentation/esp32_technical_reference_manual_en.pdf
    # page 70
    mem32[r] |= 1 << 9

    state = True
    while True:
        n[0] = (0, 0, 10) if state else (0, 0, 0)
        n.write()
        await asyncio.sleep_ms(500)
        state = not state


try:
    asyncio.run(main())
except (KeyboardInterrupt, Exception) as e:
    print("Exception {} {}\n".format(type(e).__name__, e))
finally:
    asyncio.new_event_loop()