# Creates AP during ESP-NOW broadcast sending
import aioespnow as espnow
import uasyncio as asyncio
import network

def main(w0, w1, e):
    essid = "ESP-WifiTest"
    password = "hellotherekenobi"
    w1.config(essid=essid, password=password, authmode=network.AUTH_WPA_WPA2_PSK)
    print(f"WIFI AP essid: {essid} password: {password}")


    peer = b'\xff\xff\xff\xff\xff\xff'   # MAC address of peer's wifi interface
    e.add_peer(peer, ifidx=network.AP_IF)
    asyncio.run(e.asend(peer, "5"*20))
    e.send(peer, b'end')

if __name__=="__main__":
    # A WLAN interface must be active to send()/recv()
    w0 = network.WLAN(network.STA_IF)  # Or network.AP_IF
    w0.active(True)
    w0.disconnect()   # For ESP8266

    w1 = network.WLAN(network.AP_IF)  # Or network.AP_IF
    w1.active(True)

    e = espnow.ESPNow()
    e.init()
    
    main(w0, w1 ,e)
