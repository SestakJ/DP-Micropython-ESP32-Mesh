# coding=utf-8
# (C) Copyright 2022 Jindrich Sestak (xsesta05)
# Licenced under MIT.
# Part of diploma thesis.
# Content: File with WiFi logic

import uasyncio as asyncio
import machine
import json
from ubinascii import hexlify, unhexlify
from network import AUTH_WPA_WPA2_PSK
from src.net import Net, ESP
from src.espmsg import  WIFI_PACKETS, TopologyExchange, pack_wifimessage, unpack_wifimessage
from src.core import Core
from src.tree import Tree, TreeNode, treeify

# User defined constants.
CONFIG_FILE = 'config.json'

# Constants
DEFAULT_S = const(5)
DIGEST_SIZE = const(32)     # Size of HMAC(SHA256) signing code. Equals to Size of Creds for HMAC(SHA256).
CREDS_LENGTH = const(32)
SERVER_PORT = const(1234)

def mac_to_str(mac : bytes):
    return hexlify(mac, ':').replace(b':', b'').decode()

def str_to_mac(s : str):
    return unhexlify(dst)

class WifiCore():
    DEBUG = True

    def __init__(self):
        self.core = Core()
        self._loop = self.core._loop
        self._loop.create_task(self.core._run())
        self.ap = self.core.ap
        self.sta = self.core.sta
        self.sta.wlan.disconnect()
        self._config = self.core._config
        self.ap_essid = self.core.ap_essid
        self.ap_password = self.core.ap_password
        self.sta_ssid = self.sta_password = None
        self.ap_authmode = AUTH_WPA_WPA2_PSK   # WPA/WPA2-PSK mode.
        # Node definitions
        self._id = mac_to_str(self.ap.wlan.config('mac'))
        # User defined from config.json.
        self._loop = self.core._loop
        self.children_writers = {} # {mac: (writer, (ip, port))}
        self.parent = self.parent_reader = self.parent_writer = None
        self.json_topology = self._config.get('topology', None)

    def dprint(self, *args):
        if self.DEBUG:
            print(*args)

    def start(self):
        """
        Blocking start of firmware core.
        """
        print('\nStart: node ID: {}\n'.format(self._id))
        self._loop.create_task(self._run())
        try:
            self._loop.run_forever()
        except Exception as e:    # TODO Every except raises exception meaning that the task is broken, reset whole device
            # asyncio.run(self.close_all())
            print(e)
        #     import machine
        #     # machine.reset() # TODO uncomment. It solves the problem with ERROR 104 ECONNRESET after Soft Reset on child.

    async def _run(self):
        """
        Creation of all the neccessary tasks for mesh.
        """
        # Node first must open socket to parent node, then start its own AP interface. Otherwise socket would bind to localhost.
        await self.connect_to_parent()

        self._loop.create_task(self.start_parenting())
    
    async def connect_to_parent(self):
        """
        Wait for the right signal. Assign WiFi credentials and connect to it, open connection with socket. 
        Or node is to be the root so return.
        """
        while not (self.core.sta_ssid or mac_to_str(self.core.root) == self._id): # TODO maybe not Either parent claimed him or is root.
            await asyncio.sleep(DEFAULT_S)
        # self.core.DEBUG = False     # Stop Debug messages in EspCore
        self.sta.wlan.disconnect()  # Disconnect from any previously connected WiFi.
        if self.core.sta_ssid:
            self.sta_ssid = self.core.sta_ssid
            self.sta_password = self.core.sta_password
            await self.sta.do_connect(self.sta_ssid, self.sta_password)
            self.dprint("[Connect to parent WiFi] Done")
        else:
            # TODO here update topology of me becouase i am root node
            return
        self.parent_reader, self.parent_writer = await asyncio.open_connection(self.sta.ifconfig()[2], SERVER_PORT)
        self.dprint("[Open connection to parent] Done")
        self._loop.create_task(self.send_to_parent())
        self._loop.create_task(self.receive_from_parent())
        
    async def send_to_parent(self):
        msg = TopologyExchange(self._id, "ffffffffffff", 1, self.json_topology)
        while True:
            self.dprint("[SEND] to parent")
            await self.send_msg(self.parent , self.parent_writer, msg)
            await asyncio.sleep(15)
            
    async def receive_from_parent(self):
        self.parent = await self.register_mac(self.parent_reader) # Register peer with mac address
        self._loop.create_task(self.receive(self.parent_reader))
        #     #TODO create task for processing the message.
        #     self._loop.create_task(self.send_to_children_once(res)) # Relay messages to children.
        #     await asyncio.sleep(2)
            
    async def start_parenting(self):
        """
        Create own WiFi AP and start server for listening for children to connect.
        """
        self.ap.config(essid=self.ap_essid, password=self.ap_password, authmode=self.ap_authmode, hidden=0)
        while not self.ap.wlan.active():
            await asyncio.sleep(DEFAULT_S)
        self.dprint("[START SERVER]")
        try:
            self._loop.create_task(asyncio.start_server(self.receive_from_child, '0.0.0.0', SERVER_PORT))
            self._loop.create_task(self.sending_to_children(msg=["hello to child From ROOTOOOOT", 195]))
        except Exception as e:
            self.dprint("[Start Server] error: ", e)
            raise e

    async def sending_to_children(self, msg):  
        msg = TopologyExchange(self._id, "ffffffffffff", 1, self.json_topology)
        while True:
            self._loop.create_task(self.send_to_children_once(msg))
            await asyncio.sleep(DEFAULT_S)

    async def send_to_children_once(self, msg):
        # l = self.ap.wlan.status('stations') # Get list of tuples of MAC of connected devices.
        # children = [mac[0] for mac in l]
        # TODO Must be SRC MAC and DST MAC in JSON messages, then I can match the mac addresses to the right IP addresses.
        print("[SEND] to children")
        for destination, writers in self.children_writers.items(): # But this is tuple(IP, port)
            # if destination[0] not in children: # Delete old connections from dead child nodes.
            #     # self._loop.create_task(self.close_connection(destination))
            #     continue
            self._loop.create_task(self.send_msg(destination, writers[0], msg))

    async def receive_from_child(self, reader, writer):
        mac = await self.register_mac(reader) # Register peer with mac address.
        self.children_writers[mac] = (writer, writer.get_extra_info('peername'))
        self.dprint("[Receive] child added: ",msg["src"], writer.get_extra_info('peername'))
        self._loop.create_task(self.receive(reader))

    async def register_mac(self, reader):
        """
        Receive first blank packet to be able to register MAC address of node
        """
        try:
            res = await reader.readline()
            self.dprint("[Receive] from x message: ", res)
            if res == b'': # Connection closed by host, clean up. Maybe hard reset.
                await self.close_connection(writer.get_extra_info('peername'))
                self.dprint("[Receive] conn is dead")
                return
        except Exception as e:
            self.dprint("[Receive] x conn is prob dead, stop listening. Error: ", e)
            return
            raise e
        msg = json.loads(res)
        return msg["src"]

    async def receive(self, reader):
        # TODO must be a routing table and when dst address is not myself retransmit in direction of dst address up or down stream.
        try:
            while True:
                res = await reader.readline()
                self.dprint("[Receive] from x message: ", res)
                if res == b'': # Connection closed by host, clean up. Maybe hard reset.
                    await self.close_connection(writer.get_extra_info('peername'))
                    self.dprint("[Receive] conn is dead")
                    return
        except Exception as e:
            self.dprint("[Receive] x conn is prob dead, stop listening. Error: ", e)
            return
            raise e
        # self.dprint("Close the connection")
        # del self.children_writers[writer.get_extra_info('peername')]
        # writer.close()
        # await writer.wait_closed()

    async def send_msg(self, mac, writer, message):
        if not writer:
            return
        try:
            self.dprint("[SEND] to:", mac ," message: ", message)
            writer.write('{}\n'.format(pack_wifimessage(message)))
            await writer.drain()
            print("[SEND] drained and done")
        except Exception as e:
            print("[Send] Whew! ", e, " occurred.")
            await self.close_connection(mac)
    
    async def close_connection(self, mac):
        writer = None
        if mac == self.parent:
            writer = self.parent_writer
            self.parent = None
            self.parent_writer = None
            self.parent_reader = None
        elif mac in self.children_writers:
            writer, ip = self.children_writers[mac]
            del self.children_writers[mac]
        if writer:
            writer.close()
            await writer.wait_closed()
        
    async def close_all(self):
        if self.parent_writer:
            self.close_connection(self.parent)
        for address, writer in self.children_writers.items():
            await self.close_connection(address)
        self.children_writers.clear()
        self.dprint("[Clean UP of sockets] Done")

# TODO Open connection sometimes returns StreamIO with ERROR104 ECONNRESET
        # [Send] Whew!  [Errno 104] ECONNRESET  occurred.
        # [Receive] from parent Whew! [Errno 9] EBADF occurred.
        # Probably DONE -- need testing
# TODO Form a topology from JSON
# TODO Form a topology automatically. 

def main():
    from src.wificore import WifiCore
    c= WifiCore()
    c.start()