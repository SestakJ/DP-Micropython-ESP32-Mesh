# coding=utf-8
# (C) Copyright 2022 Jindrich Sestak (xsesta05)
# Licenced under MIT.
# Part of diploma thesis.
# Content: Messages class definition, packing and unpacking.

import json
import gc
import struct
try:
    import uasyncio as asyncio
    from ubinascii import hexlify, unhexlify
except:
    import asyncio
    from binascii import hexlify, unhexlify

gc.collect()

DEBUG = False
def dprint(*args):
    if DEBUG:
        print(*args)

class COMMAND:
    ADVERTISE=1
    ROOT_ELECTED=2
    CLAIM_CHILD_REQUEST=3
    CLAIM_CHILD_RESPONSE=4
    CLAIM=5
    NODE_FAIL=6

class Node:
    def __init__(self, id, mesh_cntr, rssi):
        self.id = id
        self.mesh_cntr = mesh_cntr
        self.rssi = rssi

class Advertise:
    type = COMMAND.ADVERTISE
    _neighbours = {}

    def __init__(self, id, cntr, rssi):
        self.id = id
        self.mesh_cntr = cntr
        self.rssi = rssi
    
    async def process(self):
        adv_node = Node(self.id, self.mesh_cntr, self.rssi)
        self._neighbours[self.id] = adv_node
        dprint(type(self), "Node advertised process: ", adv_node)

    def __repr__(self):
        return f"Node_ID: {self.id} Centrality: {self.mesh_cntr} RSSI: {self.rssi}"

class Root_elected(Advertise):
    type = COMMAND.ROOT_ELECTED

    async def process(self):
        await asyncio.sleep(0.30)

class Claim_child:
    type = COMMAND.CLAIM_CHILD_REQUEST

    def __init__(self, claimer, vis, claimed):
        self.claimer = claimer
        self.vis = vis
        self.claimed = claimed
    
    async def process(self):
        await asyncio.sleep(0.40)

class Claim_child_res(Claim_child):
    type = COMMAND.CLAIM_CHILD_RESPONSE

    async def process(self):
        await asyncio.sleep(0.50)

class Node_fail:
    type = COMMAND.NODE_FAIL

    def __init__(self, id):
        self.id = id

    async def process(self):
        await asyncio.sleep(0.55)

PACKETS = {
    1: (Advertise, "!6shf"),
    2: (Root_elected, "!6shf"),
    3: (Claim_child, "!6sf6s"),
    4: (Claim_child_res, "!6sf6s"),
    
    6: (Node_fail, "!6s")
}

# Pack msg into bytes.
def create_message(obj):
    klass, pattern = PACKETS[obj.type]
    # print(*obj.__dict__.values())
    # dprint( *vars(obj).values())
    # msg = struct.pack('B', obj.type) + struct.pack(pattern, *vars(obj).values())
    msg = struct.pack('B', obj.type) + struct.pack(pattern, *obj.__dict__.values())
    dprint("create_message: ", msg)
    return msg

# On received message unpack from bytes.
async def on_message(msg):
    msg_type = msg[0]
    klass, pattern = PACKETS[msg_type]
    obj = klass(*struct.unpack(pattern, msg[1:]))
    dprint("on_message: ", pattern, obj)
    await obj.process()
    return obj

def print_mac(mac):
    dprint(hexlify(mac,':').decode())


async def main():

    id = b'\xff\xff\xff\xff\xff\xa0' # machine.unique_id()
    cntr = 1452
    rssi = -74.2
    # dprint(type(id), id)
    # dprint(type(cntr), cntr)
    # dprint(type(rssi), rssi)
    ad = Advertise(id, cntr, rssi)
    msg = create_message(ad)

    # dprint(type(msg), msg)
    # dprint(msg[0])
    tmpmsg = await on_message(msg)


    # root = Root_elected(id, cntr, rssi)
    # dprint(root)
    # msg = create_message(root)
    # dprint(type(msg), msg)
    # dprint(msg[0])
    
    # tmpmsg = await on_message(msg)


    # pattern = '!hhl'
    # pattern = '6s'
    # # tmp = struct.pack(pattern, 1, 2.4, 3)

    # id = b'<q\xbf\xe4\x8d\xa0'
    # # dprint(bytes(id, 'UTF-8'))
    # tmp = struct.pack(pattern, id)
    # dprint(tmp, len(tmp))

    # utmp = struct.unpack(pattern, tmp)

    # dprint(utmp)

if __name__=="__main__":
    asyncio.run(main())
