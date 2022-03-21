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


class ESP_TYPE:
    ADVERTISE=1
    OBTAIN_CREDS=7

    ROOT_ELECTED=2
    CLAIM_CHILD_REQUEST=3
    CLAIM_CHILD_RESPONSE=4
    CLAIM=5
    NODE_FAIL=6

class Advertise:
    type = ESP_TYPE.ADVERTISE

    def __init__(self, id, cntr, rssi):
        self.id = id
        self.mesh_cntr = cntr
        self.rssi = rssi
    
    async def process(self, core: "core.Core"):
        adv_node = tuple(self.__dict__.values()) #(self.id, self.mesh_cntr, self.rssi)
        core.neighbours[self.id] = adv_node         # update core.mneigbours with new values.
        dprint(type(self), "Node advertised process: ", *adv_node)

    def __repr__(self):
        return f"Node_ID: {self.id} Centrality: {self.mesh_cntr} RSSI: {self.rssi}"

class ObtainCreds:
    type = ESP_TYPE.OBTAIN_CREDS

    def __init__(self, creds):
        self.creds = creds

    def process(self, core: "core.Core"):
        pass

class RootElected(Advertise):
    type = ESP_TYPE.ROOT_ELECTED

    async def process(self):
        await asyncio.sleep(0.30)


class ClaimChild:
    type = ESP_TYPE.CLAIM_CHILD_REQUEST

    def __init__(self, claimer, vis, claimed):
        self.claimer = claimer
        self.vis = vis
        self.claimed = claimed
    
    async def process(self):
        await asyncio.sleep(0.40)


class ClaimChildRes(ClaimChild):
    type = ESP_TYPE.CLAIM_CHILD_RESPONSE

    async def process(self):
        await asyncio.sleep(0.50)


class NodeFail:
    type = ESP_TYPE.NODE_FAIL

    def __init__(self, id):
        self.id = id

    async def process(self):
        await asyncio.sleep(0.55)


PACKETS = {
    ESP_TYPE.ADVERTISE              : (Advertise, "!6shf"),
    ESP_TYPE.OBTAIN_CREDS           : (ObtainCreds, "s"),

    ESP_TYPE.ROOT_ELECTED           : (RootElected, "!6shf"),
    ESP_TYPE.CLAIM_CHILD_REQUEST    : (ClaimChild, "!6sf6s"),
    ESP_TYPE.CLAIM_CHILD_RESPONSE   : (ClaimChildRes, "!6sf6s"),
    # 5: Claim
    ESP_TYPE.NODE_FAIL              : (NodeFail, "!6s")
}


# Pack msg into bytes.
def pack_message(obj):
    klass, pattern = PACKETS[obj.type]
    # print(*obj.__dict__.values())
    # dprint( *vars(obj).values())
    # msg = struct.pack('B', obj.type) + struct.pack(pattern, *vars(obj).values())
    msg = struct.pack('B', obj.type) + struct.pack(pattern, *obj.__dict__.values())
    dprint("pack_message: ", msg)
    return msg


# On received message unpack from bytes.
async def unpack_message(msg, core : "core.Core"):
    msg_type = msg[0]
    klass, pattern = PACKETS[msg_type]
    obj = klass(*struct.unpack(pattern, msg[1:]))
    dprint("unpack_message: ", pattern, obj)
    await obj.process(core)
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
    msg = pack_message(ad)

    # dprint(type(msg), msg)
    # dprint(msg[0])
    tmpmsg = await unpack_message(msg)

    print(ad.neighbours)


    # root = Root_elected(id, cntr, rssi)
    # dprint(root)
    # msg = pack_message(root)
    # dprint(type(msg), msg)
    # dprint(msg[0])
    
    # tmpmsg = await unpack_message(msg)


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
