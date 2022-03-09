# coding=utf-8
# (C) Copyright 2022 Jindrich Sestak (xsesta05)
# Licenced under MIT.
# Part of diploma thesis.
# Content: File with mesh logic

import uasyncio as asyncio
import machine
from net import Net, ESP
import espmsg

_DEFAULT_MS = const(5)
_ADVERTISE_MS = const(5)   #Advertise every 5 seconds

class Core:
    BROADCAST = b'\xff\xff\xff\xff\xff\xff'
    DEBUG = True

    def __init__(self):
        # Network and ESPNOW
        self.ap = Net(1)        # Ap interface
        self.sta = Net(0)       # Sta interface
        self.esp = ESP()

        self._loop = asyncio.get_event_loop()
        # Node definition
        self._id = machine.unique_id()
        self.cntr = 0
        self.rssi = 0.0

        self.adv = espmsg.Advertise
        self._neighbours = self.adv._neighbours

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
        await asyncio.sleep(_DEFAULT_MS)
        # Add broadcast peer
        self.esp.add_peer(self.BROADCAST)
        # Advertise neigbours nodes to the mesh
        self._loop.create_task(self._on_message())
        self._loop.create_task(self.advertise())

    async def advertise(self):
        while True:
            # Advertise itself and all the neighbours
            myself = espmsg.Advertise(self._id, self.cntr, self.rssi)
            msg = espmsg.create_message(myself)
            self.dprint("Advertise:", msg)
            self.esp.send(Core.BROADCAST, msg)
            for v in self._neighbours.values():
                adv = espmsg.Advertise(v.id, v.mesh_cntr, v.rssi)
                self.esp.send(Core.BROADCAST, espmsg.create_message(adv))
                self.dprint("Advertise:", msg)

            await asyncio.sleep(_ADVERTISE_MS)

    # Wait for messages. espmsg.on_message processes messages.
    async def _on_message(self):
        while True:
            msg = await self.esp.read(250)
            msg_magic = msg[0]
            msg_len = msg[1]
            msg_src = msg[2:8]
            msg = msg[8:]
            obj = await espmsg.on_message(msg)
            self.dprint("[on message] obj: ", obj, " \n\tNeighbours: ", self._neighbours )

def main():
    c = Core()

    c.start()

if __name__=='__main__':
    main()