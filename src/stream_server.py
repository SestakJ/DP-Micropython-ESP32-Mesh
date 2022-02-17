import uasyncio as asyncio
import network
import utime
from machine import Pin, mem32
import neopixel
from utils import init_LED, create_wifi

html = """
        <html>
        <head> 
        <title>ESP Web Server</title> <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="icon" href="data:,"> 
        <style>html{font-family: Helvetica; display:inline-block; margin: 0px auto; text-align: center;}
        h1{color: #0F3376; padding: 2vh;}p{font-size: 1.5rem;}.button{display: inline-block; background-color: #e7bd3b; border: none; 
        border-radius: 4px; color: white; padding: 16px 40px; text-decoration: none; font-size: 30px; margin: 2px; cursor: pointer;}
        .button2{background-color: #4286f4;}</style>
        </head>
        
        <body> 
        <h1>ESP Web Server</h1> 
        <p>GPIO state: <strong>""" + """</strong></p>
        <p><a href="/?led=on"><button class="button">ON</button></a></p>
        <p><a href="/?led=off"><button class="button button2">OFF</button></a></p>
        
        <p>MESH ESP NOW setup </p>
        <form action="/" method="POST">
            <input type="text" name="mesh-ssid" placeholder="Mesh SSID"><br> 
            <input type="password" name="mesh-password" placeholder="Mesh Password"><br>
            <left><button type="submit">Submit</button></left>
        </form>     
        </body>
        </html>
        """


async def serve(reader, writer):
    t = utime.ticks_ms()
    resp = b"HTTP/1.0 200 OK\r\n\r\n" #+ "Ticks = {TICKS}\r\n".format(TICKS=t) 
    req = await reader.read(1024)
    print("Request from client")
    request = str(req)
    print(request)
    led_on = request.find('/?led=on')
    led_off = request.find('/?led=off')
    if led_on == 6:
        print('LED ON')
        c = (0, 10, 0)
        n[0] = c
        n.write()
    if led_off == 6:
        print('LED OFF')
        c = (0, 0, 10)
        n[0] = c
        n.write()
    await writer.awrite(html)
    asyncio.sleep_ms(50)
    await writer.wait_closed()
    print("response send")

def sta_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    #await asyncio.sleep_ms(10)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(ssid, password)
        while not wlan.isconnected():
            pass
     #       await asyncio.sleep_ms(10)
    print("Connected")
    print(wlan.ifconfig())
    return wlan

async def sta_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    await asyncio.sleep_ms(10)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(ssid, password)
        while not wlan.isconnected():
            await asyncio.sleep_ms(10)
    print("Connected")
    print(wlan.ifconfig())
    return wlan

n = init_LED()
async def main():
    ssid = "FourMusketers_2.4GHz"
    password = "jetufajN69"
    loop = asyncio.get_event_loop()
    print("loop init")

    wlan = await create_wifi(ssid, password, "STA")
    print("Wlan created")
    print(wlan.ifconfig()[0])

    
    loop.create_task(asyncio.start_server(serve, host="192.168.0.200", port=80))
    print("loop created task")
    try: 
        loop.run_forever()
    except KeyboardInterrupt:
        print("closing")
        loop.close()

try:
    asyncio.run(main())
except (KeyboardInterrupt, Exception) as e:
    print("Exception {}".format(type(e).__name__))
finally:
    asyncio.new_event_loop()
