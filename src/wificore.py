# coding=utf-8
# (C) Copyright 2022 Jindrich Sestak (xsesta05)
# Licenced under MIT.
# Part of diploma thesis.
# Content: File with WiFi logic

import uasyncio as asyncio
import machine
import time
import struct
import json
from network import AUTH_WPA_WPA2_PSK
from src.net import Net, ESP
from src.espmsg import  Advertise, ObtainCreds, RootElected, ClaimChild, ClaimChildRes, NodeFail, \
                        pack_message, unpack_message, PACKETS, ESP_TYPE
import sys
from src.core import Core

# User defined constants.
CONFIG_FILE = 'config.json'

# Constants
DEFAULT_S = const(5)
DIGEST_SIZE = const(32)     # Size of HMAC(SHA256) signing code. Equals to Size of Creds for HMAC(SHA256).
CREDS_LENGTH = const(32)
SERVER_PORT = const(1234)


class WifiCore():
    DEBUG = True

    def __init__(self):
        self.core = Core()
        self._loop = self.core._loop
        self._loop.create_task(self.core._run())
        self.ap = self.core.ap
        self.sta = self.core.sta
        self._config = self.core._config
        self.ap_essid = self.core.ap_essid
        self.ap_password = self.core.ap_password
        self.sta_ssid = self.sta_password = None

        # self.ap_essid = self.core.ap_essid
        # self.ap_password = self.core.ap_password
        # self.sta_ssid = self._config.get('STAWIFI')[0]
        self.ap_authmode = AUTH_WPA_WPA2_PSK   # WPA/WPA2-PSK mode.
        # self.sta_password = self._config.get('STAWIFI')[1]

        # Node definitions
        self._id = self.ap.wlan.config('mac')
        # User defined from config.json.
        creds = self._config.get('credentials')
        if creds is None:
            creds = CREDS_LENGTH*b'\x00'
        elif len(creds) != CREDS_LENGTH:
            creds = creds.encode()
            new_creds = creds + (CREDS_LENGTH - len(creds))*b'\x00'
            creds = new_creds[:CREDS_LENGTH]
        self.creds = creds              # Is 32Bytes long for HMAC(SHA256) signing.
        
        self._loop = self.core._loop
        self.children_writers = {}
        self.parent = self.parent_reader = self.parent_writer = None

    def dprint(self, *args):
        if self.DEBUG:
            print(*args)

    def start(self):
        """
        Blocking start of firmware core.
        """
        print('\nStart: node ID: {}\n'.format(self._id))
        self._loop.create_task(self._run())
        self._loop.run_forever()

    async def _run(self):
        """
        Creation of all the neccessary tasks for mesh.
        """
        # Node first must open socket to parent node, then start its own AP interface. Otherwise socket would bind to localhost.
        await self.connect_to_parent()

        self._loop.create_task(self.start_parenting())
    
    async def connect_to_parent(self):
        print("Connect to parent beginnig")
        while not (self.core.sta_ssid or self.core.root == self._id): # TODO maybe not Either parent claimed him or is root.
            await asyncio.sleep(DEFAULT_S)
        self.sta.wlan.disconnect()
        if self.core.sta_ssid:
            print("Connect to parent assign sta creds and connect")
            self.sta_ssid = self.core.sta_ssid
            self.sta_password = self.core.sta_password
            await self.sta.do_connect(self.sta_ssid, self.sta_password)
        else:
            return
        self.dprint("[OPEN CONNECTION]")
        self.parent = self.sta.ifconfig()[2]
        self.parent_reader, self.parent_writer = await asyncio.open_connection(self.parent, SERVER_PORT)
        self.dprint("[OPEN CONNECTION] connected, ", self.parent_reader, self.parent_writer)
        # self._loop.create_task(self.client_hello(self.parent_reader, self.parent_writer))
        self._loop.create_task(self.send_beacon_to_parent())
        self._loop.create_task(self.receive_from_parent())
        self.dprint("[OPEN CONNECTION created")

    async def resend_to_children(self, msg):
        print("[RESEND] to children")
        for destination in self.children_writers:
            await self.send_msg(destination, msg)
        
    async def send_beacon_to_parent(self):
        while True:
            print("[SEND] to parent")
            await self.send_msg(self.parent, ["Hello to parent", 196])
            await asyncio.sleep(DEFAULT_S)
            
    # async def send_parent(self, msg):
    #     try:
    #         print("write")
    #         self.parent_writer.write('{}\n'.format(json.dumps(data)))
    #         print("drain")
    #         await self.parent_writer.drain()
    #     except OSError:
    #         print(OSError.__dict__)
    #         raise OSError
    #         self.parent_writer.close()
    #         await writer.wait_closed()
    #         # close()
    #         return
    #     except:
    #         print("Whew!", sys.exc_info()[0], "occurred.")
    
    async def receive_from_parent(self):
        while True:
            try:
                print("[Receive] from parent readline")
                res = await self.parent_reader.readline()
            # except OSError:
            #     print(OSError.__dict__)
            #     raise OSError
            #     # close()
            except Exception as e:
                print("[Receive] from parent Whew!", e, "occurred.")
                self.parent = None
                self.parent_writer = None
                self.parent_reader = None
                break
            await self.resend_to_children(res)
            try:
                print('[Receive] from parent', json.loads(res))
            except ValueError:
                raise ValueError
            except Exception as e:
                print("[Receive] from parent Whew!", e, "occurred.")
            await asyncio.sleep(2)
        print("[RECEIVE] parent conn is prob dead, stop listening")
            
    async def client_hello(self, sreader, swriter):
        data = ['value', 1]
        self._loop.create_task(self.receive_from_parent())
        while True:
            try:
                print("write ", data)
                swriter.write('{}\n'.format(json.dumps(data)))
                print("drain")
                await swriter.drain()
                # print("readline")
                # res = await sreader.readline()
            # except OSError:
            #     print(OSError.__dict__)
            #     raise OSError
            #     swriter.close()
            #     await writer.wait_closed()
            #     # close()
            #     return
            except Exception as e:
                print("Whew!", e, "occurred.")
                swriter.close()
                await swriter.wait_closed()
            # try:
            #     print('Received', json.loads(res))
            # # except ValueError:
            # #     raise ValueError
            # #     # close()
            # #     swriter.close()
            # #     await writer.wait_closed()
            # #     return
            # except Exception as e:
            #     print("Whew!", e, "occurred.")
            #     swriter.close()
            #     await swriter.wait_closed()
            await asyncio.sleep(2)
            data[1] += 1

    async def start_parenting(self):
        self.ap.config(essid=self.ap_essid, password=self.ap_password, authmode=self.ap_authmode, hidden=0)
        while not self.ap.wlan.active():
            await asyncio.sleep(DEFAULT_S)
        self.dprint("[START SERVER]")
        try:
            self._loop.create_task(asyncio.start_server(self.receive_from_child, '0.0.0.0', SERVER_PORT))
            self._loop.create_task(self.send_update_children(msg=["hello to child From ROOTOOOOT", 195]))
        except Exception as e:
            print("[Start Server end] ", e)

    async def send_update_children(self, msg = ["hello to child", 195]):  
        while True:
            print("[SEND] to children")
            for destination in self.children_writers:
                await self.send_msg(destination, msg)
            await asyncio.sleep(DEFAULT_S)

    async def receive_from_child(self, reader, writer):
        print("[Received from child]: add child")
        self.children_writers[writer.get_extra_info('peername')] = writer
        try:
            while True:
                print("[Received from child]: readline()")
                data = await reader.readline()
                message = data.decode()
                addr = writer.get_extra_info('peername')

                print(f"[Received from child] {message} from {addr}")
                # self._loop.create_task(self.send_msg(writer.get_extra_info('peername'), data))
        except OSError:
            pass
        print("Close the connection")
        del self.children_writers[writer.get_extra_info('peername')]
        writer.close()
        await writer.wait_closed()

    
    async def send_msg(self, destination, data):
        if not destination:
            return
        writer = None
        if destination in self.children_writers:
            writer = self.children_writers[destination]
        elif destination == self.parent:
            writer = self.parent_writer
        else:
            return
        message = data
        try:
            print("[SEND] to :", destination, writer)
            print(f"Send: {message}")
            writer.write('{}\n'.format(json.dumps(data)))
            await writer.drain()
            print("[SEND] drained and done")
        except Exception as e:
            print("[Send] Whew! ", e, " occurred.")
            writer.close()
            await writer.wait_closed()
            if destination in self.children_writers:
                del self.children_writers[destination]
            elif destination == self.parent:
                self.parent = None
                self.parent_writer = None
                self.parent_reader = None

# TODO Clean UP
# TODO Open connection sometimes returns StreamIO with ERROR104 ECONNRESET
# TODO Form a topology from JSON
# TODO Form a topology automatically. 

def main():
    from src.wificore import WifiCore
    c= WifiCore()
    c.start()