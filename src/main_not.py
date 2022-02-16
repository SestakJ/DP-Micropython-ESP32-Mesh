import esp
# esp.osdebug(None)

import gc
gc.collect()

import uasyncio as asyncio
from server import Server
from utils import init_LED, blink

async def main():
    print("Blink()")
    #loop = asyncio.get_event_loop()
    print("Hej")
    #loop.create_task(blink(10,0,0))

    asyncio.create_task(blink((0, 10, 0)))
    await asyncio.sleep_ms(20)
    print("Here")
    
    ssid = "FourMusketers_2.4GHz"
    password = "jetufajN69"
    
    server = Server(ssid, password)
    wlan = await server.sta_wifi(ssid, password)
    #await server.create_wifi()
    s = server.create_socket()
    print("Socket created")
    led = init_LED()

    #loop = asyncio.get_event_loop()
    #loop.create_task(server.http_server_ssl(s, led))
    await asyncio.sleep_ms(20)
    await server.http_server_ssl(s, led)
    

            
    # asyncio.create_task(webserver(s))
    # await asyncio.sleep_ms(1000)
    
    print("Webserver()")
    print("Running for eternity")
    


try:
    asyncio.run(main())
except (KeyboardInterrupt, Exception) as e:
    print("Exception {}".format(type(e).__name__))
finally:
    asyncio.new_event_loop()

