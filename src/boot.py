# Complete project details at https://RandomNerdTutorials.com

try:
  import usocket as socket
except:
  import socket

from machine import Pin
import network

import esp
# esp.osdebug(None)

import gc
gc.collect()

from micropython import const
from machine import Pin, mem32
import uasyncio as asyncio
import neopixel


ssid = "FourMusketers_2.4GHz"
password = "jetufajN69"

station = network.WLAN(network.STA_IF)

station.active(True)
station.connect(ssid, password)
print('Connection pending')
while station.isconnected() == False:
  pass

print('Connection successful')
print(station.ifconfig())

# ap = network.WLAN(network.AP_IF) # create access-point interface
# ap.active(True)         # activate the interface
# ap.config(essid='ESP-AP') # set the ESSID of the access point
# while not ap.isconnected():
#   pass
# print("ESP-AP active and running")


pin = Pin(25, Pin.OUT)
n = neopixel.NeoPixel(pin, 1)
def gpio_func_out(n):
    GPIO_FUNCn_OUT_SEL_CFG_REG = 0x3FF44530 + 0x4 * n
    return GPIO_FUNCn_OUT_SEL_CFG_REG


r = gpio_func_out(25)
mem32[r] |= 1 << 9