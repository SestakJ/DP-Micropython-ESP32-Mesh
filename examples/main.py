# Complete project details at https://RandomNerdTutorials.com
# Complete project details at https://RandomNerdTutorials.com

try:
  import usocket as socket
except:
  import socket

from machine import Pin
import network

import esp
esp.osdebug(None)

import gc
gc.collect()

from micropython import const
from machine import Pin, mem32
import uasyncio as asyncio
import neopixel


ssid = "FourMusketers_2.4GHz"
password = "pass"

# station = network.WLAN(network.STA_IF)

# station.active(True)
# station.connect(ssid, password)
# print('Connection pending')
# while station.isconnected() == False:
#   pass

# print('Connection successful')
# print(station.ifconfig())

print("Create AP of ESP")
ap = network.WLAN(network.AP_IF) # create access-point interface
ap.active(True)         # activate the interface
ap.config(essid='ESP-AP') # set the ESSID of the access point
print("configed wait for isconnect")
while not ap.isconnected():
  pass
print("ESP-AP active and running")


pin = Pin(25, Pin.OUT)
n = neopixel.NeoPixel(pin, 1)
def gpio_func_out(n):
    GPIO_FUNCn_OUT_SEL_CFG_REG = 0x3FF44530 + 0x4 * n
    return GPIO_FUNCn_OUT_SEL_CFG_REG


r = gpio_func_out(25)
mem32[r] |= 1 << 9

def web_page():
  if n[0] != (0,0,0):
    gpio_state="ON"
  else:
    gpio_state="OFF"
  
  html = """<html><head> <title>ESP Web Server</title> <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,"> <style>html{font-family: Helvetica; display:inline-block; margin: 0px auto; text-align: center;}
  h1{color: #0F3376; padding: 2vh;}p{font-size: 1.5rem;}.button{display: inline-block; background-color: #e7bd3b; border: none; 
  border-radius: 4px; color: white; padding: 16px 40px; text-decoration: none; font-size: 30px; margin: 2px; cursor: pointer;}
  .button2{background-color: #4286f4;}</style></head><body> <h1>ESP Web Server</h1> 
  <p>GPIO state: <strong>""" + gpio_state + """</strong></p><p><a href="/?led=on"><button class="button">ON</button></a></p>
  <p><a href="/?led=off"><button class="button button2">OFF</button></a></p>
  
   <p>MESH ESP NOW setup </p>
   <form action="/" method="POST">
    <input type="text" name="mesh-ssid" placeholder="Mesh SSID"><br> 
    <input type="password" name="mesh-password" placeholder="Mesh Password"><br>
    <left><button type="submit">Submit</button></left>
  </form>     
  </body></html>
  """
  return html

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', 80))
s.listen(5)

print('Connection successful')
#print(station.ifconfig())

while True:
  # ssl.wrap_socket (httpd.socket, key="../src/key.pem", 
  #       cert='../src/cert.pem', server_side=True)
  
  # sslsock = ssl.wrap_socket(s)
  conn, addr = s.accept()
  print('Got a connection from %s' % str(addr))
  request = conn.recv(1024)
  request = str(request)
  print('Content = %s' % request)
  led_on = request.find('/?led=on')
  led_off = request.find('/?led=off')
  mesh_ssid = request.find('mesh-ssid')
  mesh_password = request.find('mesh-password')
  # print(mesh_ssid + " :" + mesh_password)
  if led_on == 6:
    print('LED ON')
    n[0] = (0, 0, 10)
    n.write()
  if led_off == 6:
    print('LED OFF')
    n[0] = (0, 0, 0)
    n.write()
  response = web_page()
  conn.send('HTTP/1.1 200 OK\n')
  conn.send('Content-Type: text/html\n')
  conn.send('Connection: close\n\n')
  conn.sendall(response)
  conn.close()
