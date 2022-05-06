# Connects to AP during ESP-NOW broadcast sending
import aioespnow as espnow
import uasyncio as asyncio
import network

async def main(w0, w1, e):
        
   
    peer = b'\xff\xff\xff\xff\xff\xff'   # MAC address of peer's wifi interface
    e.add_peer(peer, ifidx=network.AP_IF)
    asyncio.run(e.asend(peer, "5"*20))
    e.send(peer, b'end')

    ssid = "ESP-WifiTest"
    password = "hellotherekenobi"

    print(f"Connect to WiFI AP essid:{ssid} password:{password}")
    # ssid= "FourMusketers_2.4GHz"
    # password= "jetufajN69"

    if not w0.isconnected():
        w0.connect(ssid, password)
        while not w0.isconnected():
            print("Connecting")
            await asyncio.sleep_ms(10)
    print("Connected STA_IF")
    print(wlan.ifconfig())
    return wlan

if __name__=="__main__":
     # A WLAN interface must be active to send()/recv()
    w0 = network.WLAN(network.STA_IF)  # Or network.AP_IF
    w0.active(True)
    w0.disconnect()   # For ESP8266

    w1 = network.WLAN(network.AP_IF)  # Or network.AP_IF
    w1.active(True)

    e = espnow.ESPNow()
    e.init()

    asyncio.run(main(w0, w1, e))
