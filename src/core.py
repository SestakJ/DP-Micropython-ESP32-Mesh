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
from src.espmsg import  Advertise, ObtainCreds, SendWifiCreds, RootElected, NodeFail, \
                        pack_espmessage, unpack_espmessage, ESP_PACKETS, ESP_TYPE
from src.utils import init_button, id_generator
from src.ucrypto.hmac import HMAC, compare_digest, new
import ucryptolib as cryptolib
import math

# User defined constants.
CONFIG_FILE = 'config.json'
LEFT_BUTTON = 32
RIGHT_BUTTON = 0

# Constants
DEFAULT_S = const(5)
MPS_THRESHOLD_MS = const(4250) # Time how long button must be pressed to allow MPS in ms (cca 4-5s).
MPS_TIMER_S = const(45)       # Allow excahnge of credentials for this time, in seconds.
ADVERTISE_S = const(5)      # Advertise every once this timer expires, in seconds.
ADVERTISE_OTHERS_MS = const(13000)
NEIGHBOURS_NOT_CHANGED_FOR = const(29)
DIGEST_SIZE = const(32)     # Size of HMAC(SHA256) signing code. Equals to Size of Creds for HMAC(SHA256).
CREDS_LENGTH = const(32)
PMK_LMK_LENGTH = const(16)

"""
Core class responsible for mesh operations.
"""
class Core():
    BROADCAST = b'\xff\xff\xff\xff\xff\xff'
    DEBUG = True

    def __init__(self):
        with open(CONFIG_FILE) as f:
            self._config = json.loads(f.read())
        # Network and ESPNOW interfaces.
        self.ap = Net(1)                # Access point interface.
        self.sta = Net(0)               # Station interface
        self.ap_essid = self.ap.wlan.config('essid')      # Must be multiple of 16, class will take care of.
        self.ap_password = id_generator(16)               # Must be multiple of 16
        self.sta_ssid = self.sta_password = None
        self.esp = ESP()
        self.creds  = b'\x00'
        # Node definitions.
        self._id = self.ap.wlan.config('mac')
        self.cntr = 0
        self.rssi = 0.0
        self.neighbours = {}
        # User defined from config.json.
        self.get_config()
        self.esp.set_pmk(self.esp_pmk)
        self.inmps = False
        # Asyncio and PIN Interupt definition.
        self.button = init_button(RIGHT_BUTTON, self.mps_button_pressed)
        self.mps_start = self.mps_end = 0
        self._loop = asyncio.get_event_loop()
        self._lock = asyncio.Lock()
        # Flags for root election and topology addition.
        self.neigh_last_changed = 0
        self.root = b''
        self.in_topology = False

    def get_config(self):
        creds = self._config.get('credentials')
        if creds is None:
            creds = CREDS_LENGTH*b'\x00'
        # TODO Not neccessary to have fixed length. It adds zeroes itself.
        elif len(creds) != CREDS_LENGTH:
            creds = creds.encode()
            new_creds = creds + (CREDS_LENGTH - len(creds))*b'\x00'
            creds = new_creds[:CREDS_LENGTH]
        self.creds = creds              # Is 32Bytes long for HMAC(SHA256) signing.
        _, pattern = ESP_PACKETS[ESP_TYPE.OBTAIN_CREDS]
        self._creds_msg_size = struct.calcsize(pattern) + 1
        self.esp_pmk = self._config.get('esp_pmk').encode()
        self.esp_lmk = self._config.get('esp_lmk').encode()
        if len(self.esp_pmk) !=  PMK_LMK_LENGTH or len(self.esp_lmk) != PMK_LMK_LENGTH:
            raise ValueError('LMK and PMK key must be 16Bytes long.')

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

        await self.added_to_mesh()
        # TODO uncommenct
        self._loop.create_task(self.advertise())
        self._loop.create_task(self.check_neighbours())
   
    async def added_to_mesh(self):
        """
        Triger when node has obtained credentials, until then be idle.
        """
        while not self.has_creds():
            await asyncio.sleep(DEFAULT_S)
        self._loop.create_task(self.check_root_election())

    def has_creds(self):
        return int.from_bytes(self.creds, "big")

    def send_msg(self, peer=None, msg: "espmsg.class" = ""):
        """
        Create message from class object and send it through espnow.
        """
        packed_msg = pack_espmessage(msg) # Creates byte-like string.
        digest_hash = self.sign_message(packed_msg)
        signed_msg = packed_msg + digest_hash
        self.esp.send(peer, signed_msg)
        return signed_msg

    def sign_message(self, msg):
        """
        Sign message with HMAC hash from sha256(by default) only if credentials are available.
        """
        mac = HMAC(self.creds, msg)
        digest_hash = mac.digest()
        return digest_hash

    def verify_sign(self, msg, msg_digest):
        """
        Check if the digest match with the same credentials. If not drop packet.
        """
        if not msg_digest or not msg:
            return False
        my_digest  = self.sign_message(msg)
        if len(my_digest) != len(msg_digest):
            return False
        return compare_digest(my_digest, bytes(msg_digest, 'utf-8'))

    def mps_button_pressed(self, irq):
        """
        Function to measure how long is button pressed. If between MPS_THRESHOLD_MS and 2*MPS_THRESHOLD_MS, we can exchange credentials.
        """    
        if irq.value() == 0:
            self.mps_start = time.ticks_ms()
        elif irq.value() == 1:
            self.mps_end = time.ticks_ms()
        self.dprint("[MPS] button presed for: ", time.ticks_diff(self.mps_end, self.mps_start))
        if MPS_THRESHOLD_MS < time.ticks_diff(self.mps_end, self.mps_start) < 2*MPS_THRESHOLD_MS:
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
        self.dprint("\t[MPS ALLOWED] for: ", MPS_TIMER_S, "seconds.")
        await asyncio.sleep(MPS_TIMER_S)
        self.dprint("\t[MPS ALLOWED ENDED] now")
        self.inmps = False

    async def send_mps(self):
        """
        Schedule task to retrieve credentials that can only run for allowed amount of time.
        Allow only one task to be run at the time using Lock() even if button was pressed multiple times.
        """
        try:
            self._loop.run_until_complete(self._lock.acquire())
            await asyncio.wait_for(self.obtain_creds(), MPS_TIMER_S)
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
        self.dprint("\t[MPS credentials obtained] ")
        self._lock.release()

    def send_creds(self, flag, creds, peer=BROADCAST):
        """
        Sending credentials, should be used in exchange mode(MPS) only.
        """
        gimme_creds = ObtainCreds(flag, self._id, creds)     # Default creds value is 32x"\x00".
        send_msg = self.send_msg(peer, gimme_creds)
        return send_msg

    def save_neighbour(self, lst: "list of [node_id, node_cntr, node_rssi, last_rx, last_tx]"):
        adv_node = tuple(lst)
        node_id = adv_node[0]
        self.neighbours[node_id] = adv_node         # update core.neigbours with new values.
    
    def update_neighbour(self, node):
        """
        Update database of neighbours. On first encounter of new node immediately resend advertisement.
        Record indatabase is dict {node: (node, cnt, rssi, last_rx, last_tx)}
        """
        record  = self.neighbours.get(node.id, None)
        last_tx = 0
        last_rx = time.ticks_ms()
        if record:
            node_id,_,_, _,last_tx = record
            if node_id == self._id:
                return
        else:
            self.neigh_last_changed = time.ticks_ms()
            last_tx = time.ticks_ms()
            signed_msg = self.send_msg(self.BROADCAST, node)
            self.dprint("[Advertise imedietly forward on new node]:", signed_msg[: len(signed_msg)-DIGEST_SIZE])
        self.save_neighbour(list(node.__dict__.values()) + [last_rx, last_tx])
   
    async def check_neighbours(self):
        """
        Task will each second check old records and wipe them out.
        It will also advertise other nodes every 13s if they are active.
        """
        while True:
            for record in self.neighbours.values():
                t = time.ticks_ms()
                node_id, node_cntr, node_rssi, last_rx, last_tx = record
                if node_id == self._id:
                    continue
                elif time.ticks_diff(t, last_rx) > 2*ADVERTISE_OTHERS_MS:
                    del self.neighbours[node_id]
                    self.neigh_last_changed = t
                elif time.ticks_diff(last_rx, last_tx) > ADVERTISE_OTHERS_MS:
                    adv = Advertise(node_id, node_cntr, node_rssi)
                    last_tx = t
                    signed_msg = self.send_msg(self.BROADCAST, adv)
                    self.save_neighbour([node_id, node_cntr, node_rssi, last_rx, last_tx])
                    self.dprint(self.neighbours)
                    self.dprint("[Advertise every 13s database]:", signed_msg[: len(signed_msg)-DIGEST_SIZE])
            await asyncio.sleep(1)

    async def check_root_election(self):
        """
        After neighbours don't change for some time, trigger flag to simulate root election.
        """
        while not self.neigh_last_changed:
            await asyncio.sleep(DEFAULT_S)
        while True:
            if time.ticks_diff(time.ticks_ms(), self.neigh_last_changed) > 5*1000: # TODO NEIGHBOURS_NOT_CHANGED_FOR
                # TODO root election automatically
                self.dprint(f"[ROOT ELECTION] can start, neigh database ot changed for {NEIGHBOURS_NOT_CHANGED_FOR} seconds")
                self.root = b'<q\xbf\xe4\x8b\x89'
                if self._id == self.root:
                    self.in_topology = True
                    self.dprint(f"[ROOT ELECTION] finish")
                    self._loop.create_task(self.claim_children())
                break
            else:
                await asyncio.sleep(DEFAULT_S)

    def aes_encrypt(self, value : 'str'):
        aes = cryptolib.aes(self.creds[:16], 2, b"1234"*4)
        enc = aes.encrypt((value + 16*'\x00')[:16])
        return enc

    def aes_decrypt(self, value):
        aes = cryptolib.aes(self.creds.decode()[:16], 2, b"1234"*4)
        dec = aes.decrypt(value)
        return dec.decode()
    
    async def claim_children(self):
        # Claim children if I am root node or if I was added to the topology by parent_claim_received.
        await asyncio.sleep_ms(1)
        self.dprint(f"[Claim children] in espMSG {self.ap_essid} {self.ap_password}")
        for record in self.neighbours.values(): # TODO only for some nodes with good RSSI.
            t = time.ticks_ms()
            node_id, node_cntr, node_rssi, last_rx, last_tx = record
            self.claim_child(node_id, self.aes_encrypt(self.ap_essid), self.aes_encrypt(self.ap_password))

    def claim_child(self, dst_node, essid, pwd):
        wifi_creds = SendWifiCreds(dst_node, len(self.ap_essid), essid, pwd, key=self.creds.decode()[:16])
        signed_msg = self.send_msg(self.BROADCAST, wifi_creds)

    def parent_claim_received(self, wifi_creds):
        if wifi_creds.adst_node != self._id or self.in_topology:
            return
        self.sta_ssid = self.aes_decrypt(wifi_creds.cessid)[:wifi_creds.bessid_length]
        self.sta_password = self.aes_decrypt(wifi_creds.zpasswd)
        self.dprint(f"[RECEIVED WIFI CREDS FROM PARENT] {self.sta_ssid} and {self.sta_password}")
        self.in_topology = True
        self._loop.create_task(self.claim_children())


    async def advertise(self):
        """
        Actualize node's own values in database and send to veryone in the mesh.
        """
        self.save_neighbour([self._id, self.cntr, self.rssi, 0, 0])
        while True:
            self.cntr, self.rssi = await self.get_cntr_rssi(b'')
            self.save_neighbour([self._id, self.cntr, self.rssi, 0, 0])
            adv = Advertise(self._id, self.cntr, self.rssi)
            signed_msg = self.send_msg(self.BROADCAST, adv)
            self.dprint("[Advertise send]:", signed_msg[: len(signed_msg)-DIGEST_SIZE])
            await asyncio.sleep(ADVERTISE_S)

    def get_message_with_digest(self, buf):
        """
        Extract message and it's digest and length and return all of it.
        """
        msg_magic, msg_len, msg_src = struct.unpack("!BB6s", buf[0:8]) # Always in the incoming packet.
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
                self._loop.create_task(self.process_message(msg, digest, msg_len))

                # TODO read only first two bytes and then read leng of the packet.
                # Cannot do because StreamReader.read(), read1() don't work, they read as much as can.
                # Workaround here. Repair later.
                if len(buf) > (8 + msg_len) and buf[8 + next_msg]=='\x99':
                    next_msg = 8 + msg_len
                else:
                    next_msg = 0
                    break

    async def process_message(self, msg, digest, msg_len):
        print("process message")
        if self.verify_sign(msg, digest):
            obj = await unpack_espmessage(msg, self)
            self.dprint("[On Message Verified received] obj: ", obj)
        # If in exchange mode expect creds and wrong sign because we don't have the correct creds.
        elif self.inmps and msg_len == self._creds_msg_size + DIGEST_SIZE:
            creds = digest
            obj = await unpack_espmessage(msg+creds, self)
            self.dprint("[On Message not Verified received] obj: ", obj)
        else:
            self.dprint("[On Message dropped]", msg, msg_len)

    async def get_cntr_rssi(self, router_ssid: bytes):
        wifies = [] # self.sta.wlan.scan() # Returns (ssid, bssid, channel, RSSI, authmode, hidden), but is blocking
        rssi = cntr = 0
        for record in wifies:
            if record[0] == router_ssid:
                rssi = record[3]
            if record[1] in self.neighbours:
                eqaution = 1/math.sqrt(abs(record[3]))
                cntr = cntr + eqaution
        return cntr, rssi

    # TODO in wlan.scan() try uasyncio.core._io_queue.queue_read + return super().recv() from https://github.com/glenn20/micropython/blob/espnow-g20/ports/esp32/modules/aioespnow.py    

    # TODO Root node after 2,5*ADV time no new node appeared start election process. Only the root node will send claim.
    # Centrality value of nodes will be computed like E(1/abs(rssi))^1/2

    # TODO Root node confirmation - if multiple roots, select the one with lowes MAC for example.
def main():
    c = Core()

    c.start()

if __name__=='__main__':
    main()