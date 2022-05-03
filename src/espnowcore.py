# coding=utf-8
# (C) Copyright 2022 Jindřich Šestak (xsesta05)
# Licenced under MIT.
# Part of diploma thesis.
# Content: File with mesh logic

import gc
gc.collect()
from src.utils.net import Net, ESP
gc.collect()
from src.utils.messages import Advertise, ObtainCreds, SendWifiCreds, pack_espmessage, unpack_espmessage, ESP_PACKETS, \
    Esp_Type
gc.collect()
from src.utils.pins import init_button, id_generator, RIGHT_BUTTON
gc.collect()
from src.utils.hmac import HMAC, compare_digest

gc.collect()
import uasyncio as asyncio
import time
import struct
import json
import ucryptolib as cryptolib
import math
from ubinascii import unhexlify
gc.collect()

# Constants
DEFAULT_S = const(5)
MPS_THRESHOLD_MS = const(4250)  # Time how long button must be pressed to allow MPS in ms (cca 4-5s).
MPS_TIMER_S = const(45)  # Allow excahnge of credentials for this time, in seconds.
ADVERTISE_S = const(5)  # Advertise every once this timer expires, in seconds.
ADVERTISE_OTHERS_MS = const(13000)
NEIGHBOURS_NOT_CHANGED_FOR = const(29)
DIGEST_SIZE = const(32)  # Size of HMAC(SHA256) signing code. Equals to Size of Creds for HMAC(SHA256).
CREDS_LENGTH = const(32)
PMK_LMK_LENGTH = const(16)

"""
ESP-NOW Core class responsible for mesh operations.
"""


class EspNowCore:
    BROADCAST = b'\xff\xff\xff\xff\xff\xff'

    def __init__(self, config, ap, sta):
        self.DEBUG = None
        self.config = config
        # Network and ESP-NOW interfaces.
        self.ap = ap
        self.sta = sta
        self.ap_essid = self.ap.wlan.config('essid')  # Should be multiple of 16, but will take care of.
        self.ap_password = id_generator(16)  # Must be multiple of 16
        self.sta_ssid = self.sta_password = None
        self.esp = ESP()
        self.creds = b'\x00'
        self._creds_msg_size = None
        # Node espnow mesh definitions.
        self.id = self.ap.wlan.config('mac')
        self.neighbours = {}
        # User defined from config.json.
        self.esp_pmk = self.esp_lmk = None
        self.get_config()
        self.esp.set_pmk(self.esp_pmk)
        # Asyncio and PIN Interupt definition.
        self.button = init_button(RIGHT_BUTTON, self.mps_button_pressed)  # Register IRQ for MPS procedure.
        self.mps_start = self.mps_end = 0
        self.loop = asyncio.get_event_loop()
        self.in_mps = False  # Flag signalize MPS procedure
        self._mps_lock = asyncio.Lock()  # Asyncio lock tol allow only one MPS proceduer at the time.
        # self._wlan_scan_lock = _thread.allocate_lock() # Threading lock similar to the one in C.
        self._wlan_scan_lock = asyncio.ThreadSafeFlag()  # Threading lock similar to the one in C.

        # Flags for root election and topology addition.
        self.neigh_last_changed = time.ticks_ms()  # Watch time from last change to start root election.
        self.in_topology = False  # When node was added into the tree.
        self.seen_topology = False  # If node sees another node in tree topology don't elect root.
        self.root = b''

    def get_config(self):
        self.DEBUG = self.config.get("EspNowConfig", 0)
        creds = self.config.get('credentials')
        if creds is None:
            creds = CREDS_LENGTH * b'\x00'
        elif len(creds) != CREDS_LENGTH:
            creds = creds.encode()
            new_creds = creds + (CREDS_LENGTH - len(creds)) * b'\x00'
            creds = new_creds[:CREDS_LENGTH]
        self.creds = creds  # Now is 32Bytes long for HMAC(SHA256) signing.
        _, pattern = ESP_PACKETS[Esp_Type.OBTAIN_CREDS]
        self._creds_msg_size = struct.calcsize(pattern) + 1  # Size of ObtainCreds class message.
        self.esp_pmk = self.config.get('esp_pmk').encode()
        self.esp_lmk = self.config.get('esp_lmk').encode()
        if len(self.esp_pmk) != PMK_LMK_LENGTH or len(self.esp_lmk) != PMK_LMK_LENGTH:
            raise ValueError('LMK and PMK key must be 16Bytes long.')

    def dprint(self, *args):
        if self.DEBUG:
            print(*args)

    def start(self):
        """
        Blocking start of firmware core.
        """
        print('\nStart EspNowCore: node ID: {}\n'.format(self.id))
        self.loop.create_task(self._run())

    async def _run(self):
        """
        Creation of all the neccessary tasks for mesh.
        """
        await asyncio.sleep_ms(10)
        # Add broadcast peer
        self.esp.add_peer(self.BROADCAST)
        self.loop.create_task(self.on_message())  # Receive messages

        await self.added_to_mesh()
        self.loop.create_task(self.advertise())  # Advertise itself
        self.loop.create_task(self.check_neighbours())  # Watch for neighbours
        self.loop.create_task(self.check_root_election())  # Watch for root election

    async def added_to_mesh(self):
        """
        Triger when node has obtained credentials, until then wait for MPS procedure.
        """
        while not self.has_creds():
            await asyncio.sleep(DEFAULT_S)

    def has_creds(self):
        return int.from_bytes(self.creds, "big")

    def mps_button_pressed(self, irq):
        """
        Registered as IRQ for button.
        Function to measure how long is button pressed.
        If between MPS_THRESHOLD_MS and 2*MPS_THRESHOLD_MS, we can exchange credentials.
        """
        if irq.value() == 0:
            self.mps_start = time.ticks_ms()
        elif irq.value() == 1:
            self.mps_end = time.ticks_ms()
        self.dprint("[MPS] button presed for: ", time.ticks_diff(self.mps_end, self.mps_start))
        if MPS_THRESHOLD_MS < time.ticks_diff(self.mps_end, self.mps_start) < 2 * MPS_THRESHOLD_MS:
            self.loop.create_task(self.allow_mps())
            if not self.has_creds():
                self.loop.create_task(self.get_signing_creds())
        # asyncio.sleep(0.1)
        return

    async def allow_mps(self):
        """ Allow exchange of credentials only for some amount of time."""
        self.in_mps = True
        print("\t[MPS ALLOWED] for: ", MPS_TIMER_S, "seconds.")
        await asyncio.sleep(MPS_TIMER_S)
        print("\t[MPS ALLOWED ENDED] now")
        self.in_mps = False

    async def get_signing_creds(self):
        """
        Schedule task to retrieve credentials that can only run for allowed amount of time.
        Allow only one task to be run at the time using Lock() even if button was pressed multiple times.
        """
        try:
            self.loop.run_until_complete(self._mps_lock.acquire())
            await asyncio.wait_for(self._obtain_signing_creds(), MPS_TIMER_S)
        except asyncio.TimeoutError:
            print('[MPS timeout!] Try again')
        except OSError as e:
            raise e

    async def _obtain_signing_creds(self):
        """Try to retrieve credentials until you have them. Processing of messages happens in message.py file."""
        while not self.has_creds():
            self.send_creds(0, self.creds, peer=self.BROADCAST)
            await asyncio.sleep(DEFAULT_S)
        print("\t[MPS credentials obtained] ")
        self._mps_lock.release()

    def send_creds(self, flag, creds, peer=BROADCAST):
        """
        Received ObtainCreds is processed directly in class in message.py.
        Sending credentials, should be used in exchange mode(MPS) only. Otherwise peer would not accept it.
        """
        obtain_creds = ObtainCreds(flag, self.id, creds)  # Default creds value is 32x"\x00".
        send_msg = self.send_msg(peer, obtain_creds)
        return send_msg

    async def advertise(self):
        """
        Actualize node's own values in database and send to everyone in the mesh.
        """
        cntr = rssi = 0.0
        wifies = []
        adv = Advertise(self.id, cntr, rssi, self.in_topology, 0)
        self.save_neighbour(adv, 0, 0)
        # self._wlan_scan_lock.set()
        while True:
            # self._wlan_scan_lock.acquire() # Lock is for waiting for results in second thread of scanning.
            # await self._wlan_scan_lock.wait()
            cntr, rssi = await self.get_cntr_rssi(wifies, b'FourMusketers_2.4GHz')
            adv.mesh_cntr = cntr
            adv.rssi = rssi
            adv.tree_root_elected = self.in_topology
            self.save_neighbour(adv, 0, 0)
            signed_msg = self.send_msg(self.BROADCAST, adv)
            self.dprint("[Advertise send]:", signed_msg[: len(signed_msg) - DIGEST_SIZE])
            # _thread.start_new_thread(self.wlan_scan, [wifies]) # Scan wlans in new thread and release lock.
            await asyncio.sleep(
                ADVERTISE_S)  # Use time of this sleep to switch to other thread. (Should be enough, lock is for sure.)

    async def get_cntr_rssi(self, wifies, router_ssid: bytes):
        """
        Compute centrality and RSSI to router. 
        """
        rssi = cntr = 0.0
        for record in wifies:
            if record[0] == router_ssid:
                rssi = record[3]
            elif record[1] in self.neighbours:
                if record[3] == 0:  # Division by zero error.
                    cntr += 1
                else:
                    eqaution = 1 / math.sqrt(abs(record[3]))
                    cntr = cntr + eqaution
        return cntr, rssi

    def save_neighbour(self, adv: Advertise, last_rx, last_tx):
        # Dictionary {mac : [node_id, node_cntr, node_rssi, is_root, ttl, last_rx, last_tx]}
        node_id = adv.id
        if adv.tree_root_elected:
            self.seen_topology = True
        # Update core.neighbours with new values.
        self.neighbours[node_id] = [x[1] for x in sorted(adv.__dict__.items())] + [last_rx, last_tx]

    def on_advertise(self, adv: Advertise):
        """
        Called from message.py.
        Update database of neighbours. On first encounter of new node immediately resend advertisement.
        Record in database is dict {node: (node, cnt, rssi, last_rx, last_tx)}
        """
        record = self.neighbours.get(adv.id, None)
        last_tx = 0
        tmp = adv.ttl
        last_rx = time.ticks_ms()
        if record:  # Node already registered.
            node_id, _cnt, _rss, _root, _ttl, _, last_tx = record
            if node_id == self.id:
                return
            adv.ttl = min(_ttl, adv.ttl)  # Save the lowest TTL
        else:  # New addition.
            self.neigh_last_changed = last_rx
            last_tx = time.ticks_ms()
            adv.ttl = adv.ttl + 1
            signed_msg = self.send_msg(self.BROADCAST, adv)
            adv.ttl = adv.ttl - 1
            self.dprint("[Advertise imedietly forward on new node]:", signed_msg[: len(signed_msg) - DIGEST_SIZE])
        self.save_neighbour(adv, last_rx, last_tx)
        adv.ttl = tmp

    async def check_neighbours(self):
        """
        Task will each second check old records and wipe them out.
        It will also advertise other nodes every 13s if they are active.
        """
        dprint = self.dprint
        while True:
            for record in self.neighbours.values():
                t = time.ticks_ms()
                node_id, node_cntr, node_rssi, root_elected, ttl, last_rx, last_tx = record
                if node_id == self.id:
                    continue
                elif time.ticks_diff(t, last_rx) > 2 * ADVERTISE_OTHERS_MS:  # Timeout -> delete record
                    del self.neighbours[node_id]
                    self.neigh_last_changed = t
                elif time.ticks_diff(last_rx, last_tx) > ADVERTISE_OTHERS_MS:  # Timeout -> advertise.
                    adv = Advertise(node_id, node_cntr, node_rssi, root_elected, ttl + 1)
                    last_tx = t
                    signed_msg = self.send_msg(self.BROADCAST, adv)
                    adv.ttl = ttl
                    self.save_neighbour(adv, last_rx, last_tx)
                    dprint(self.neighbours)
                    dprint("[Advertise every 13s database]:", signed_msg[: len(signed_msg) - DIGEST_SIZE])
            await asyncio.sleep(1)

    async def check_root_election(self):
        """
        After neighbours don't change for some time, trigger flag to simulate root election.
        """
        # while not self.neigh_last_changed:
        #     await asyncio.sleep(DEFAULT_S)
        while True:
            if self.seen_topology:  # If seen node in topology wait to be claimed.
                break
            elif time.ticks_diff(time.ticks_ms(),
                                 self.neigh_last_changed) > 5 * 1000:  # TODO NEIGHBOURS_NOT_CHANGED_FOR
                # TODO root election automatically
                print(
                    f"[ROOT ELECTION] can start, neigh database ot changed for {NEIGHBOURS_NOT_CHANGED_FOR} seconds")
                self.root = unhexlify(self.config.get("root", "")) # Now assign root to simulate election.
                if self.id == self.root:
                    self.in_topology = True
                    print(f"[ROOT ELECTION] finished, root is {self.root}")
                break
            else:
                await asyncio.sleep(DEFAULT_S)

    def aes_encrypt(self, value: 'str'):
        aes = cryptolib.aes(self.creds[:16], 2, b"1234" * 4)
        enc = aes.encrypt((value + 16 * '\x00')[:16])
        return enc

    def aes_decrypt(self, value):
        aes = cryptolib.aes(self.creds.decode()[:16], 2, b"1234" * 4)
        dec = aes.decrypt(value)
        return dec.decode()

    def claim_children(self, children: "list[mac]"):
        """
        Trigerred from upper level (WifiCore) class. Claim children from list. 
        """
        print(f"[Claim children] {children} in espMSG SSID: {self.ap_essid} PASSWORD: {self.ap_password}")
        for mac in children:  # TODO only for some nodes with good RSSI.
            self._send_wifi_creds(mac, self.aes_encrypt(self.ap_essid), self.aes_encrypt(self.ap_password))

    def _send_wifi_creds(self, dst_node, essid, pwd):
        wifi_creds = SendWifiCreds(dst_node, len(self.ap_essid), essid, pwd, key=self.creds.decode()[:16])
        self.send_msg(self.BROADCAST, wifi_creds)

    def on_send_wifi_creds(self, wifi_creds):
        """
        Called from message.py. Save credentials for station to connect, trigger conection process in WifiCore.
        """
        if wifi_creds.adst_node != self.id or self.in_topology:
            return
        self.sta_ssid = self.aes_decrypt(wifi_creds.cessid)[:wifi_creds.bessid_length]
        self.sta_password = self.aes_decrypt(wifi_creds.zpasswd)
        print(f"[RECEIVED WIFI CREDS FROM PARENT] {self.sta_ssid} and {self.sta_password}")
        self.in_topology = True

    def send_msg(self, peer=None, msg: "messages.class" = ""):
        """
        Create message from class object and send it through espnow.
        """
        packed_msg = pack_espmessage(msg)  # Creates byte-like string.
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
        my_digest = self.sign_message(msg)
        if len(my_digest) != len(msg_digest):
            return False
        return compare_digest(my_digest, bytes(msg_digest, 'utf-8'))

    async def on_message(self):
        """
        Wait for messages. Light weight function to not block recv process. Further processing in another coroutine.
        """
        # buf = bytearray(250)
        # readinto(buf)
        while True:
            buf = await self.esp.read(250)  # HAS to be 250 otherwise digest is blank, don't know why.
            next_msg = 0
            while True:
                buf = buf[next_msg:]
                msg, digest, msg_len = self.get_message_with_digest(buf)
                self.loop.create_task(self.process_message(msg, digest, msg_len))  # Process in another coro.
                # Read only first two bytes and then read length of the packet, 
                # cannot do because StreamReader.read(), read1() don't work, they read as much as can (whole packet).
                # Workaround here.
                if len(buf) > (8 + msg_len) and buf[8 + next_msg] == '\x99':
                    next_msg = 8 + msg_len
                else:
                    next_msg = 0
                    break

    def get_message_with_digest(self, buf):
        """
        Extract message and it's digest and length and return all of it.
        """
        msg_magic, msg_len, msg_src = struct.unpack("!BB6s", buf[0:8])  # Always in the incoming packet.
        msg = buf[8:(8 + msg_len - DIGEST_SIZE)]
        digest = buf[(8 + msg_len - DIGEST_SIZE): (
                    8 + msg_len)]  # Get the digest from the message for comparison, digest is 32B.
        return msg, digest, msg_len

    async def process_message(self, msg, digest, msg_len):
        """
        Verify sign and unpack messages and process it.
        If node doesn't have credentials for digest, it will drop packet becaue digests will not match.
        """
        if self.verify_sign(msg, digest):
            obj = await unpack_espmessage(msg, self)
            self.dprint("[On Message Verified received] obj: ", obj)
        # If in exchange mode expect creds and wrong sign because we don't have the correct creds.
        elif self.in_mps and msg_len == self._creds_msg_size + DIGEST_SIZE:
            creds = digest
            obj = await unpack_espmessage(msg + creds, self)
            self.dprint("[On Message not Verified received] obj: ", obj)
        else:
            self.dprint("[On Message dropped]", msg, msg_len)

    def wlan_scan(self, wlans):
        """
        Run in separate thread, wlan.scan() blocks rx_buffer of esp due to RTOS implementation.
        """
        wlans.clear()  # Clear the list of old records.
        try:
            wlans.extend(self.sta.wlan.scan())
        except RuntimeError as e:  # Sometimes can throw Wifi Unknown Error 0x0102 == no AP found.
            wlans.clear()
        # self._wlan_scan_lock.release()
        # self._wlan_scan_lock.set()

    # TODO Root node after 2,5*ADV time no new node appeared start election process. Only the root node will send claim.

    # TODO Root node confirmation - if multiple roots, select the one with lowes MAC for example.


def main():
    c = EspNowCore()

    c.start()


if __name__ == '__main__':
    main()
