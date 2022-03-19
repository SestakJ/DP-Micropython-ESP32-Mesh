# coding=utf-8
# (C) Copyright 2022 Jindrich Sestak (xsesta05)
# Licenced under MIT.
# Part of diploma thesis.
# Content: File with mesh logic

import uasyncio as asyncio
import machine
from src.net import Net, ESP
from src.espmsg import Advertise, RootElected, ClaimChild, ClaimChildRes, NodeFail, create_message, on_message

from network import AUTH_WPA_WPA2_PSK

# User defined constants.
AP_WIFI_NAME = "ESP"            # Doesn't matter because it will be hidden.
AP_WIFI_PASSWORD = "espespesp"  # Must be at least 8 characters long for WPA/WPA2-PSK authentization.


# Constants
DEFAULT_S = const(5)
ADVERTISE_S = const(5)   # Advertise every 5 seconds

"""
Core class responsible for mesh operations.
"""
class Core:
    BROADCAST = b'\xff\xff\xff\xff\xff\xff'
    DEBUG = True

    def __init__(self):
        # Network and ESPNOW interfaces.
        self.ap = Net(1)        # Access point interface.
        self.ap_essid = AP_WIFI_NAME
        self.ap_password = AP_WIFI_PASSWORD    
        self.ap_authmode = AUTH_WPA_WPA2_PSK   # WPA/WPA2-PSK mode.
        self.ap.config(essid=self.ap_essid, password=self.ap_password, authmode=self.ap_authmode, hidden=0)
        self.sta = Net(0)       # Station interface
        self.esp = ESP()
        self._loop = asyncio.get_event_loop()
        # Node definition
        self._id = machine.unique_id()
        self.cntr = 0
        self.rssi = 0.0
        self.neighbours = Advertise.neighbours


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
        self._loop.create_task(self._on_message())
        self._loop.create_task(self.advertise())

    async def advertise(self):
        """
        Propagation of the list of all the nodes in mesh.
        """
        while True:
            # Actualise node's own values in database.
            self.neighbours[self._id] = (self._id, self.cntr, self.rssi)
            # Send whole table record by record.
            for v in self.neighbours.values():
                adv = Advertise(*v)
                msg = create_message(adv)
                self.esp.send(Core.BROADCAST, msg)
                self.dprint("[Advertise]:", msg)

            await asyncio.sleep(ADVERTISE_S)

    # Wait for messages. espmsg.on_message processes messages.
    async def _on_message(self):
        while True:
            # TODO read only first two bytes and then read leng of the packet
            msg = await self.esp.read(250)
            msg_magic = msg[0]
            msg_len = msg[1]
            msg_src = msg[2:8]
            msg = msg[8:]
            obj = await on_message(msg)
            self.dprint("[On message] obj: ", obj, " \n\tNeighbours: ", self.neighbours )

    # DONE Instead of Node class use tuple()

    # DONE [-have a look on more practices] PEP8 rules for better understanding of code. ESPMSG names without underling, neighbours is private make it neighbours.

    # TODO create_message and on_message from espmsg.py move into this class. And swap _on_mesasge and on_message names (swap "_").
    
    # TODO in WPS exhcange symetric key. Every message will be signed with hmac(sha256) fucntion for security
    # WPS like procces, from foto
    # Client                  Mesh Node
    #                         Only if button pressed on this node process the packet
    #                         Listtens for packet with "gimme creds"
    # Button pressed
    # Send packet "gimme creds"
    #             <Handshake>(probably add_peer with LMK for encrypt comm)
    #                         Send creds (shared symetric key created for Mesh comm. Every packet will be signed with this key.)

    # TODO After WPS adds new node to the mesh, AP WiFi interface can be hidden.

    # TODO Root node after 2,5*ADV time no new node appeared start election process. Only the root node will send claim.
    # Centrality value of nodes will be computed like E(1/abs(rssi))^1/2


def main():
    c = Core()

    c.start()

if __name__=='__main__':
    main()