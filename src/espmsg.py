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


class Advertise:
    type = COMMAND.ADVERTISE

    def __init__(self, node_id, cntr, rssi):
        self.node_id = node_id
        self.cntr = cntr
        self.rssi = rssi

    async def process(self):
        await asyncio.sleep(0.20)

    def __repr__(self):
        return f"Node_ID: {self.node_id} Centrality: {self.cntr} RSSI: {self.rssi}"

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

    def __init__(self, node_id):
        self.node_id = node_id

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
    dprint( *vars(obj).values())
    msg = struct.pack('B', obj.type) + struct.pack(pattern, *vars(obj).values())
    dprint(msg)
    return msg

# On received message unpack from bytes.
async def on_message(msg):
    msg_type = msg[0]
    klass, pattern = PACKETS[msg_type]
    obj = klass(*struct.unpack(pattern, msg[1:]))
    dprint(klass, pattern, obj)
    await obj.process()
    return obj

def print_mac(mac):
    dprint(hexlify(mac,':').decode())


async def main():

    node_id = b'\xff\xff\xff\xff\xff\xa0' # machine.unique_id()
    cntr = 1452
    rssi = -74.2
    dprint(type(node_id), node_id)
    dprint(type(cntr), cntr)
    dprint(type(rssi), rssi)
    ad = Advertise(node_id, cntr, rssi)
    msg = create_message(ad)

    dprint(type(msg), msg)
    dprint(msg[0])
    tmpmsg = await on_message(msg)


    root = Root_elected(node_id, cntr, rssi)
    dprint(root)
    msg = create_message(root)
    dprint(type(msg), msg)
    dprint(msg[0])
    
    tmpmsg = await on_message(msg)


    # pattern = '!hhl'
    # pattern = '6s'
    # # tmp = struct.pack(pattern, 1, 2.4, 3)

    # node_id = b'<q\xbf\xe4\x8d\xa0'
    # # dprint(bytes(node_id, 'UTF-8'))
    # tmp = struct.pack(pattern, node_id)
    # dprint(tmp, len(tmp))

    # utmp = struct.unpack(pattern, tmp)

    # dprint(utmp)

if __name__=="__main__":
    asyncio.run(main())
