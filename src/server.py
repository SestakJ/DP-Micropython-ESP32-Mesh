# coding=utf-8
# (C) Copyright 2022 Jindřich Šesták (xsesta05)
# Licenced under MIT.
# Part of diploma thesis.
 
import ubinascii as binascii
from micropython import const
from machine import Pin, mem32
import uasyncio as asyncio
import neopixel
import network
import ussl as ssl
import uasyncio as asyncio
import time
try:
    import usocket as socket
except:
    import socket


# Class starts WiFi and bind socket, then waits for user request to access web page
# URl address is : https://192.168.0.200/:8443  (IP address and port may vary)
class Server():
    # Source codes: https://github.com/micropython/micropython/blob/master/examples/network/http_server_ssl.py
    # This self-signed key/cert pair is randomly generated and to be used for
    # testing/demonstration only.  You should always generate your own key/cert.
    key = binascii.unhexlify(
        b"3082013b020100024100cc20643fd3d9c21a0acba4f48f61aadd675f52175a9dcf07fbef"
        b"610a6a6ba14abb891745cd18a1d4c056580d8ff1a639460f867013c8391cdc9f2e573b0f"
        b"872d0203010001024100bb17a54aeb3dd7ae4edec05e775ca9632cf02d29c2a089b563b0"
        b"d05cdf95aeca507de674553f28b4eadaca82d5549a86058f9996b07768686a5b02cb240d"
        b"d9f1022100f4a63f5549e817547dca97b5c658038e8593cb78c5aba3c4642cc4cd031d86"
        b"8f022100d598d870ffe4a34df8de57047a50b97b71f4d23e323f527837c9edae88c79483"
        b"02210098560c89a70385c36eb07fd7083235c4c1184e525d838aedf7128958bedfdbb102"
        b"2051c0dab7057a8176ca966f3feb81123d4974a733df0f958525f547dfd1c271f9022044"
        b"6c2cafad455a671a8cf398e642e1be3b18a3d3aec2e67a9478f83c964c4f1f"
    )
    cert = binascii.unhexlify(
        b"308201d53082017f020203e8300d06092a864886f70d01010505003075310b3009060355"
        b"0406130258583114301206035504080c0b54686550726f76696e63653110300e06035504"
        b"070c075468654369747931133011060355040a0c0a436f6d70616e7958595a3113301106"
        b"0355040b0c0a436f6d70616e7958595a3114301206035504030c0b546865486f73744e61"
        b"6d65301e170d3139313231383033333935355a170d3239313231353033333935355a3075"
        b"310b30090603550406130258583114301206035504080c0b54686550726f76696e636531"
        b"10300e06035504070c075468654369747931133011060355040a0c0a436f6d70616e7958"
        b"595a31133011060355040b0c0a436f6d70616e7958595a3114301206035504030c0b5468"
        b"65486f73744e616d65305c300d06092a864886f70d0101010500034b003048024100cc20"
        b"643fd3d9c21a0acba4f48f61aadd675f52175a9dcf07fbef610a6a6ba14abb891745cd18"
        b"a1d4c056580d8ff1a639460f867013c8391cdc9f2e573b0f872d0203010001300d06092a"
        b"864886f70d0101050500034100b0513fe2829e9ecbe55b6dd14c0ede7502bde5d46153c8"
        b"e960ae3ebc247371b525caeb41bbcf34686015a44c50d226e66aef0a97a63874ca5944ef"
        b"979b57f0b3"
    )
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

    def __init__(self, ssid, password, AP = False):
        self._ssid = ssid
        self._password = password
        self.wifi_mode = "AP" if AP else "STA"
        self._page = self.html
        self.wlan = None

    async def create_wifi(self):
        if self.wifi_mode == "AP":
            print("AP_mode")
            self.wlan = self.ap_wifi(self._ssid, self._password)
        else:
            print("STA_mode")
            self.wlan = self.sta_wifi(self._ssid, self._password)

    async def sta_wifi(self, ssid, password):
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

    async def ap_wifi(self, ssid, password=None):
        wlan = network.WLAN(network.AP_IF) # create access-point interface
        await asyncio.sleep_ms(10)
        wlan.active(True)         # activate the interface
        wlan.config(ssid, password) # set the ESSID of the access point
        while not wlan.isconnected():
            await asyncio.sleep_ms(10)
        print("Connected")
        print(wlan.ifconfig())
        return wlan

    def create_socket(self, port=8443, ipaddr='', maxconnection=2):
        s = socket.socket()
        # s.setblocking(0)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        #s.setsockopt(socket.AF_INET, socket.SOCK_STREAM, 0)
        s.bind(('', port))
        s.listen(maxconnection)
        print(f"Listening, connect your browser to https://", ipaddr, ":", port)
        return s

    def print_http(self, ssl_socket):
        req = ssl_socket.readline()
        request = str(req)
        print(req)
        while True:
            h = ssl_socket.readline()
            if h == b"" or h == b"\r\n":
                break
            print(h)
            request = request + str(h)
        return request
        
    def parse_request_url(self, request, led):
        n = led
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

    def http_server_ssl(self, sockets, led, use_stream=True):
        print("http_server_ssl")
        s = sockets
        n = led
        print("Inside webserver before WHILE")
        while True:
            print("Inside webserver inside WHILE")
            #await asyncio.sleep_ms(20)self
            res = s.accept()
            
            print("Inside webserver inside WHILE after sleep")
            client_s = res[0]
            client_addr = res[1]
            print("Client address:", client_addr)
            print("Client socket:", client_s)
            client_s = ssl.wrap_socket(client_s, server_side=True, key=self.key, cert=self.cert)
            print(client_s)
            print("Request:")
            if use_stream:
                # Both CPython and MicroPython SSLSocket objects support read() and
                # write() methods.
                # Browsers are prone to terminate SSL connection abruptly if they
                # see unknown certificate, etc. We must continue in such case -
                # next request theynned as an expansion for 2020’s Assassin’s Creed Valhalla but morphed into a full game late last y issue will likely be more well-behaving and
                # will succeed.
                print("why")
                try:
                    print("Kde kurva")
                    request = self.print_http(client_s)
                    self.parse_request_url(request, led)
                    response = self.html
                    print("Kde kurva")
                    self.response(client_s, response)
                    
                    print("Done")
                except Exception as e:
                    print("Exception serving request:", e.args)
            else:
                print(client_s.recv(4096))
                client_s.send(CONTENT % counter)

            client_s.close()


    def response(self, ssl_socket, res):
        print("response")
        ssl_socket.write('HTTP/1.0 200 OK\n')
        ssl_socket.write('Content-Type: text/html\n')
        ssl_socket.write('Connection: close\n\n')
        ssl_socket.write(res)
        print("Data written")