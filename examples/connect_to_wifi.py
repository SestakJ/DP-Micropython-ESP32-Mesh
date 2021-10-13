import network
import time
ssid = "FourMusketers_2.4GHz"
passd = "blank"
async def connectWifi():
    print(time.localtime())
   
    station = network.WLAN(network.STA_IF)
    station.active(True)
    await station.scan()
    if station.isconnected() == True:
        print("Already connected")
    if station.isconnected() == False:
        station.connect(ssid, passd)
        print(time.localtime())
    while station.isconnected() == False:
        pass

    print("Connection successful")
    print(station.ifconfig())




import time
import neopixel
import network
import uasyncio as asyncio
from machine import Pin

led_pin = Pin(25, Pin.OUT)
led = neopixel.NeoPixel(led_pin, 1)

start = time.ticks_us()

async def blink():
    b = 10
    while True:
        led[0] = (0, b, 0)
        b = b ^ 10
        led.write()
        print("[LED] BLINK", time.ticks_us() - start)
        await asyncio.sleep_ms(20)


async def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    print(f"Create WLAN", time.ticks_us() - start)
    await asyncio.sleep_ms(0)
    wlan.active(True)
    print(f"WLAN active", time.ticks_us() - start)
    if not wlan.isconnected():
        wlan.connect(ssid, password)
        print(f"WLAN connect", time.ticks_us() - start)
        while not wlan.isconnected():
            print("Sleep here?")
            await asyncio.sleep_ms(10)

    print("Connected")
    print(wlan.ifconfig())
    return wlan


async def main():
    asyncio.create_task(blink())
    await asyncio.sleep_ms(500)
    wlan = connect_wifi(ssid, passd)
    await wlan


try:
    asyncio.run(main())
except (KeyboardInterrupt, Exception) as e:
    print("Exception {}".format(type(e).__name__))
finally:
    asyncio.new_event_loop()

