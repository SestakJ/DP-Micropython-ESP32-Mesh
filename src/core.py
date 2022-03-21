# coding=utf-8
# (C) Copyright 2022 Jindrich Sestak (xsesta05)
# Licenced under MIT.
# Part of diploma thesis.
# Content: File with mesh logic

import uasyncio as asyncio
import machine
import time
import struct
from network import AUTH_WPA_WPA2_PSK
from src.net import Net, ESP
from src.espmsg import Advertise, ObtainCreds, RootElected, ClaimChild, ClaimChildRes, NodeFail, pack_message, unpack_message
from src.utils import init_button
from src.basecore import BaseCore


# User defined constants.
AP_WIFI_NAME = "ESP"            # Doesn't matter because it will be hidden.
AP_WIFI_PASSWORD = "espespesp"  # Must be at least 8 characters long for WPA/WPA2-PSK authentization.

LEFT_BUTTON = 32
RIGHT_BUTTON = 0

# Constants
DEFAULT_S = const(5)
WPS_THRESHOLD = const(4250) # Time how long button must be pressed to allow WPS in ms (cca 4-5s).
WPS_TIMER = const(45)       # Allow excahnge of credentials for this time, in seconds.
ADVERTISE_S = const(5)      # Advertise every once this timer expires, in seconds.
DIGEST_SIZE = const(32)

"""
Core class responsible for mesh operations.
"""
class Core(BaseCore):
    BROADCAST = b'\xff\xff\xff\xff\xff\xff'
    DEBUG = True

    def __init__(self, creds=b'hellotheregeneralkenobinobodyex'):
        # Network and ESPNOW interfaces.
        self.ap = Net(1)                # Access point interface.
        self.ap_essid = AP_WIFI_NAME
        self.ap_password = AP_WIFI_PASSWORD
        self.ap_authmode = AUTH_WPA_WPA2_PSK   # WPA/WPA2-PSK mode.
        self.ap.config(essid=self.ap_essid, password=self.ap_password, authmode=self.ap_authmode, hidden=0)
        self.sta = Net(0)               # Station interface
        self.esp = ESP()
        self._loop = asyncio.get_event_loop()
        # Node definition
        self._id = machine.unique_id()
        self.cntr = 0
        self.rssi = 0.0
        self.neighbours = {}
        # MESH definition
        self.creds = creds              # Should be 64 bytes for HMAC(SHA256) signing.
        self.button = init_button(RIGHT_BUTTON, self.button_pressed)
        self.inwps = False


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
        await asyncio.sleep(DEFAULT_S)
        # Add broadcast peer
        self.esp.add_peer(self.BROADCAST)
        # Advertise neigbours nodes to the mesh
        self._loop.create_task(self.on_message())
        self._loop.create_task(self.advertise())


    # TODO move to BaseCore after I know it is working.
    def button_pressed(self, irq):
        """
        Function to measure how long is button pressed. If between 4.5s and 9s we can exchange credentials.
        """    
        if irq.value() == 0:
            self.wps_start = time.ticks_ms()
            self.wps_end = 0
        elif irq.value() == 1:
            self.wps_end = time.ticks_ms()
        self.dprint("[WPS] button presed for: ", time.ticks_diff(self.wps_end, self.wps_start))
        if WPS_THRESHOLD < time.ticks_diff(self.wps_end, self.wps_start) < 2*WPS_THRESHOLD:
            if self.creds:
                self._loop.create_task(self.allow_wps())
            else:
                self._loop.create_task(self.obtain_creds())

    async def allow_wps(self):
        self.inwps = True
        self.dprint("[WPS ALLOWED] for: ", WPS_TIMER, "seconds.")
        asyncio.sleep(WPS_TIMER)
        self.inwps = False

    async def obtain_creds(self):
        pass

    async def advertise(self):
        """
        Propagation of the list of all the nodes in mesh.
        """
        while True:
            # Actualize node's own values in database.
            self.neighbours[self._id] = (self._id, self.cntr, self.rssi)
            # Send whole table record by record.
            for v in self.neighbours.values():
                adv = Advertise(*v)
                signed_msg = self.send_msg(self.BROADCAST, adv)
                self.dprint("[Advertise]:", signed_msg)

            await asyncio.sleep(ADVERTISE_S)

    async def on_message(self):
        """
        Wait for messages. Verify digest and unpack messages and process it.
        If node doesn't have credentials for digest, it will drop packet becaue degests will not match.
        """
        while True:
            buf =  await self.esp.read(250) # HAS to be 250 otherwise digest is blank dont how why.
            next_msg = 0
            while True:
                buf = buf[next_msg:]
                msg_magic = buf[0]
                msg_len = buf[1]
                msg_src = buf[2:8]
                msg = buf[8:(8 + msg_len - DIGEST_SIZE)]
                digest = buf[(8 + msg_len - DIGEST_SIZE) : (8 + msg_len)] # Get the digest from the message for comparison, digest is 32B.
                # Process the message only if the digest is correct.
                if self.verify_sign(msg, digest):
                    obj = await unpack_message(msg, self)
                    self.dprint("[On Message Verified] obj: ", obj, " \n\tNeighbours: ", self.neighbours )

                # TODO read only first two bytes and then read leng of the packet.
                # Cannot do because StreamReader.read(), read1() don't work, they read as much as can.
                # Workaround here. Repair later.
                if len(buf) > (8 + msg_len) and buf[8 + next_msg]=='\x99':
                    next_msg = 8 + msg_len
                else:
                    next_msg = 0
                    break

    # DONE Instead of Node class use tuple()

    # DONE [-have a look on more practices] PEP8 rules for better understanding of code. ESPMSG names without underling, neighbours is private make it neighbours.

    # TODO in WPS exhcange symetric key. Every message will be signed with hmac(sha256) fucntion for security
    # DONE- i have button time detection and decides if i offer or request creds
    # DONE- downloaded hmac lib for signing with sha256
    # DONE- must do BaseCore class with sendig and receving msg with hmac for decryption.
    # WPS like procces, from foto
    # Client                  Mesh Node
    #                         Only if button pressed on this node process the packet
    #                         Listtens for packet with "gimme creds"
    # Button pressed
    # Send packet "gimme creds"
    #             <Handshake>(probably add_peer with LMK for encrypt comm)
    #                         Send creds (shared symetric key created for Mesh comm. Every packet will be signed with this key.)

    # TODO Press one button and AP Wifi becomes visible and can connect to web server to set creds..

    # TODO Root node after 2,5*ADV time no new node appeared start election process. Only the root node will send claim.
    # Centrality value of nodes will be computed like E(1/abs(rssi))^1/2

def main():
    c = Core()

    c.start()

if __name__=='__main__':
    main()