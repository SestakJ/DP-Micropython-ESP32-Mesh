# coding=utf-8
# (C) Copyright 2022 Jindrich Sestak (xsesta05)
# Licenced under MIT.
# Part of diploma thesis.
# Content: Classes for network and esp-now interaction.
 
try:
    import uasyncio as asyncio
    from uasyncio import StreamReader
    import network
    from esp import espnow
except ImportError:
    import asyncio
    from asyncio import StreamReader

DEBUG = True
def dprint(*args):
    if DEBUG:
        print(*args)

class Net:
    def __init__(self, mode):
        self.mode = mode
        self.WLAN = network.WLAN
        self.wlan = network.WLAN(self.mode) # Create an interface
        self.wlan.active(True)
        
    def isconnected(self):
        return self.wlan.isconnected()

    def connect(self, ssid, password):
        return self.wlan.connect(ssid, password)

    def ifconfig(self):
        return self.wlan.ifconfig()

    def config(self, essid="ssid", password="password", *args):
        dprint("This is runned")
        return self.wlan.config(essid=essid, password=password)

    async def do_connect(self, ssid, password=""):
        if self.mode == network.AP_IF:
            dprint("AP_mode " + ssid + " " + password )
            await self.ap_wifi(ssid, password)
        else:
            dprint("STA_mode" + ssid + " " + password)
            await self.sta_wifi(ssid, password)

    async def sta_wifi(self, ssid, password):
        wlan = self.wlan
        if not wlan.isconnected():
            wlan.connect(ssid, password)
            while not wlan.isconnected():
                await asyncio.sleep_ms(10)
        dprint("Connected STA_IF")
        dprint(wlan.ifconfig())
        return wlan

    async def ap_wifi(self, ssid, password=""):
        wlan = self.wlan
        wlan.config(essid=ssid, password=password) # set the ESSID of the access point
        while wlan.active() == False:
            await asyncio.sleep_ms(10)
        dprint("Connected AP_IF")
        dprint(wlan.ifconfig())
        return wlan

class ESP:
    def __init__(self, net):
        self.esp = espnow.ESPNow()
        self.esp.init()
        self.net = net
        self.stream_reader = StreamReader(self.esp)

    def add_peer(self, peer, lmk=None, channel=0, ifidx=network.AP_IF):
        return self.esp.add_peer(peer, lmk, channel, ifidx)

    def config(self,*args):
        return self.esp.config(*args)

    def send(self, peer=None, msg=""):
        if peer is None:
            return self.esp.send(msg)
        else:
            return self.esp.send(peer, msg)

    async def read(self, size):
        return await self.stream_reader.read(size)

    def irecv(self):
        return self.esp.irecv()

    def recv(self):
        return self.esp.recv()