# coding=utf-8
# (C) Copyright 2022 Jindrich Sestak (xsesta05)
# Licenced under MIT.
# Part of diploma thesis.
# Content: File with mesh logic

import uasyncio as asyncio
import machine
import time
import struct
import json
from network import AUTH_WPA_WPA2_PSK
from src.net import Net, ESP
from src.espmsg import  Advertise, ObtainCreds, RootElected, ClaimChild, ClaimChildRes, NodeFail, \
                        pack_message, unpack_message, PACKETS, ESP_TYPE
from src.utils import init_button
from src.basecore import BaseCore


# User defined constants.
CONFIG_FILE = 'config.json'
LEFT_BUTTON = 32
RIGHT_BUTTON = 0

# Constants
DEFAULT_S = const(5)
MPS_THRESHOLD = const(4250) # Time how long button must be pressed to allow MPS in ms (cca 4-5s).
MPS_TIMER = const(45)       # Allow excahnge of credentials for this time, in seconds.
ADVERTISE_S = const(5)      # Advertise every once this timer expires, in seconds.
DIGEST_SIZE = const(32)     # Size of HMAC(SHA256) signing code. Equals to Size of Creds for HMAC(SHA256).
CREDS_LENGTH = const(32)

"""
Core class responsible for mesh operations.
"""
class Core(BaseCore):
    BROADCAST = b'\xff\xff\xff\xff\xff\xff'
    DEBUG = True

    def __init__(self):
        with open(CONFIG_FILE) as f:
            self._config = json.loads(f.read())
        # Network and ESPNOW interfaces.
        self.ap = Net(1)                # Access point interface.
        # Predefined only for initial setup via microdot, not important now.
        # self.ap_essid = AP_WIFI_NAME
        # self.ap_password = AP_WIFI_PASSWORD
        # self.ap_authmode = AUTH_WPA_WPA2_PSK   # WPA/WPA2-PSK mode.
        # self.ap.config(essid=self.ap_essid, password=self.ap_password, authmode=self.ap_authmode, hidden=0)
        self.sta = Net(0)               # Station interface
        self.esp = ESP()
        # Node definitions
        self._id = machine.unique_id()
        self.cntr = 0
        self.rssi = 0.0
        self.neighbours = {}
        # User defined from config.json.
        creds = self._config.get('credentials')
        if creds is None:
            creds = CREDS_LENGTH*b'\x00'
        elif len(creds) != CREDS_LENGTH:
            creds = creds.encode()
            new_creds = creds + (CREDS_LENGTH - len(creds))*b'\x00'
            creds = new_creds[:CREDS_LENGTH]
        self.creds = b''              # Should be 32 bytes for HMAC(SHA256) signing.
        _, pattern = PACKETS[ESP_TYPE.OBTAIN_CREDS]
        self._creds_msg_size = struct.calcsize(pattern) + 1
        self.esp_pmk = self._config.get('esp_pmk').encode()
        self.esp_lmk = self._config.get('esp_lmk').encode()
        print(type(creds), creds)
        self.esp.set_pmk(self.esp_pmk)
        self.inmps = False
        # Asyncio and PIN Interupt definition.
        self.button = init_button(RIGHT_BUTTON, self.mps_button_pressed)
        self.mps_start = self.mps_end = 0
        self._loop = asyncio.get_event_loop()
        self._lock = asyncio.Lock()

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
        self._loop.create_task(self.on_message())
        self._loop.create_task(self.advertise())

    def mps_button_pressed(self, irq):
        """
        Function to measure how long is button pressed. If between MPS_THRESHOLD and 2*MPS_THRESHOLD, we can exchange credentials.
        """    
        if irq.value() == 0:
            self.mps_start = time.ticks_ms()
        elif irq.value() == 1:
            self.mps_end = time.ticks_ms()
        self.dprint("[MPS] button presed for: ", time.ticks_diff(self.mps_end, self.mps_start))
        if MPS_THRESHOLD < time.ticks_diff(self.mps_end, self.mps_start) < 2*MPS_THRESHOLD:
            self._loop.create_task(self.allow_mps())
            if not self.has_creds():
                self._loop.create_task(self.send_mps())
        asyncio.sleep(0.1)
        return

    async def allow_mps(self):
        """
        Allow exchange of credentials only for some amount of time.
        """
        self.inmps = True
        self.dprint("\t[MPS ALLOWED] for: ", MPS_TIMER, "seconds.")
        await asyncio.sleep(MPS_TIMER)
        self.dprint("\t[MPS ALLOWED ENDED] now")
        self.inmps = False

    async def send_mps(self):
        """
        Schedule task to retrieve credentials that can only run for allowed amount of time.
        Allow only one task to be run at the time using Lock() even if button was pressed multiple times.
        """
        try:
            self._loop.run_until_complete(self._lock.acquire())
            await asyncio.wait_for(self.obtain_creds(), MPS_TIMER)
        except asyncio.TimeoutError:
            print('ERROR : MPS timeout!')
        except OSError as e:
            raise e

    async def obtain_creds(self):
        """
        Retrieve credentials until you have them.
        """
        while not self.has_creds():
            send_msg = self.send_creds(0, self.creds, peer=self.BROADCAST)
            await asyncio.sleep(DEFAULT_S)
        self._lock.release()

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
                self.dprint("[Advertise send]:", signed_msg[: len(signed_msg)-DIGEST_SIZE])

            await asyncio.sleep(ADVERTISE_S)

    def get_message_with_digest(self, buf):
        """
        Extract message and it's digest and length and return all of it.
        """
        msg_magic, msg_len, msg_src = struct.unpack("!BB6s", buf[0:8]) # Always in the incoming packet.
        # msg_magic = buf[0]
        # msg_len = buf[1]
        # msg_src = buf[2:8]
        msg = buf[8:(8 + msg_len - DIGEST_SIZE)]
        digest = buf[(8 + msg_len - DIGEST_SIZE) : (8 + msg_len)] # Get the digest from the message for comparison, digest is 32B.
        return msg, digest, msg_len

    async def on_message(self):
        """
        Wait for messages. Verify digest and unpack messages and process it.
        If node doesn't have credentials for digest, it will drop packet becaue degests will not match.
        """
        while True:
            buf =  await self.esp.read(250) # HAS to be 250 otherwise digest is blank, don't know why.
            next_msg = 0
            while True:
                buf = buf[next_msg:]
                msg, digest, msg_len = self.get_message_with_digest(buf)
                if self.verify_sign(msg, digest):           # Unpack and process the message only if the digest is correct.
                    obj = await unpack_message(msg, self)
                    self.dprint("[On Message Verified received] obj: ", obj)
                # If in exchange mode expect creds and wrong sign because we don't have the correct creds.
                elif self.inmps and msg_len == self._creds_msg_size + DIGEST_SIZE:
                    creds = digest
                    obj = await unpack_message(msg+creds, self)
                    self.dprint("[On Message not Verified received] obj: ", obj)
                else:
                    self.dprint("[On Message dropped]", msg, msg_len)

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

    # DONE in MPS exhcange symetric key. Every message will be signed with hmac(sha256) fucntion for security
    # DONE- i have button time detection and decides if i offer or request creds
    # DONE- downloaded hmac lib for signing with sha256
    # DONE- must do BaseCore class with sendig and receving msg with hmac for decryption.
    # MPS like procces, from foto
    # Client                  Mesh Node
    #                         Only if button pressed on this node process the packet
    #                         Listtens for packet with "gimme creds"
    # Button pressed
    # Send packet "gimme creds"
    #             <Handshake>(probably add_peer with LMK for encrypt comm)
    #                         Send creds (shared symetric key created for Mesh comm. Every packet will be signed with this key.)


    # TODO Root node after 2,5*ADV time no new node appeared start election process. Only the root node will send claim.
    # Centrality value of nodes will be computed like E(1/abs(rssi))^1/2
    
    # TODO Press one button and AP Wifi becomes visible and can connect to web server to set creds..


def main():
    c = Core()

    c.start()

if __name__=='__main__':
    main()