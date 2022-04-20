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
    import ucryptolib
except:
    import asyncio
    from binascii import hexlify, unhexlify

gc.collect()

DEBUG = False
def dprint(*args):
    if DEBUG:
        print(*args)


##### Messages on ESP-NOW protocol layer.
class ESP_TYPE:
    ADVERTISE=1
    OBTAIN_CREDS=2
    SEND_WIFI_CREDS=3
    ROOT_ELECTED=4

# Periodic advertisment to the broadcast
class Advertise:
    type = ESP_TYPE.ADVERTISE

    def __init__(self, id, cntr, rssi):
        self.id = id
        self.mesh_cntr = cntr
        self.rssi = rssi
    
    async def process(self, core: "core.Core"):
        core.on_advertise(self)
        
    def __repr__(self):
        return f"Node_ID: {self.id} Centrality: {self.mesh_cntr} RSSI: {self.rssi}"


"""
Handshake protocol for exchange of credentials:
Client                              Server
--------------------------------------------
SYN -->>                            
                                    ADD_PEER(LMK)
                              <<--  SYN_ACK
ADD_PEER(LMK)
OBTAIN -->>                         
                              <<--  RESPOND
[[SAVE_CREDENTIALS]]
DEL_PEER()
UNREQ_SYN -->>                      
                                    DEL_PEER()
"""
class ObtainCreds:
    type = ESP_TYPE.OBTAIN_CREDS
    SYN = 0
    SYN_ACK = 1     # For add_peer on the other side.
    OBTAIN = 2
    RESPOND = 3
    UNREG = 4 

    def __init__(self, aflag, asrc_addr, creds = 32*b'\x00'):
        self.aflag = aflag
        self.asrc_addr = asrc_addr
        self.creds = creds
        
    async def process(self, core: "core.Core"):
        instruction = ObtainCreds_methods.get(self.aflag, None)
        if instruction:
            return instruction(self, core)

    def __repr__(self):
        return f"Cred: {self.creds} Flag {self.aflag} Srcaddr {self.asrc_addr}"

    def register_server(self, core):
        core.esp.add_peer(self.asrc_addr, core.esp_lmk, encrypt=True)
        core.send_creds(self.SYN_ACK, 32*b'\x00')       # BUT send via Broadcast.

    def register_client(self, core):
        core.esp.add_peer(self.asrc_addr, core.esp_lmk, encrypt=True)
        core.send_creds(self.OBTAIN, 32*b'\x00', peer=self.asrc_addr)

    def exchange_creds(self, core):
        core.send_creds(self.RESPOND, core.creds, peer=self.asrc_addr) # Send Credentials.

    def unregister_syn(self, core):
        core.creds = self.creds     # Save credentials
        core.send_creds(self.UNREG, 32*b'\x00', peer=self.asrc_addr)
        core.esp.del_peer(self.asrc_addr)

    def unregister(self, core):
        core.esp.del_peer(self.asrc_addr)

ObtainCreds_methods = {
    ObtainCreds.SYN         : ObtainCreds.register_server,
    ObtainCreds.SYN_ACK     : ObtainCreds.register_client,
    ObtainCreds.OBTAIN      : ObtainCreds.exchange_creds,
    ObtainCreds.RESPOND     : ObtainCreds.unregister_syn,
    ObtainCreds.UNREG       : ObtainCreds.unregister
}

# For sending ciphered credentials to child nodes to connect to WiFi
class SendWifiCreds:
    type = ESP_TYPE.SEND_WIFI_CREDS
    def __init__(self, dst_node, length_essid, essid, passwd, key=None):
        self.adst_node = dst_node
        self.bessid_length = length_essid
        self.cessid = essid           # It has 16 chars because it is already encrypted by AES.
        self.zpasswd = passwd         # It has 16 chars because it is already encrypted by AES.
        
    async def process(self, core : "core.Core"):
        core.on_send_wifi_creds(self)


class RootElected(Advertise):
    type = ESP_TYPE.ROOT_ELECTED

    async def process(self):
        await asyncio.sleep(0.30)

ESP_PACKETS = {
    ESP_TYPE.ADVERTISE              : (Advertise, "!6sff"),
    ESP_TYPE.OBTAIN_CREDS           : (ObtainCreds, "!B6s32s"),
    ESP_TYPE.SEND_WIFI_CREDS        : (SendWifiCreds, "!6sh16s16s"),
    ESP_TYPE.ROOT_ELECTED           : (RootElected, "!6shf"),
}

# Pack msg into bytes.
def pack_espmessage(obj):
    klass, pattern = ESP_PACKETS[obj.type]
    msg = struct.pack('B', obj.type) + struct.pack(pattern, *obj.__dict__.values())
    dprint("pack_espmessage: ", msg)
    return msg


# Unpack received message from bytes into Object and process message.
async def unpack_espmessage(msg, core : "core.Core"):
    msg_type = msg[0]
    klass, pattern = ESP_PACKETS[msg_type]
    obj = klass(*struct.unpack(pattern, msg[1:]))
    dprint("unpack_espmessage: ", pattern, obj)
    await obj.process(core)
    return obj


##### WIFI messages for mesh
# In JSON with structure:
    #{'src':'\xxx',
    # 'dst' : '\xxx',
    # 'flag': Num,
    # 'msg' : Payload
    # }

class WIFIMSG:
    TOPOLOGY_PROPAGATE=1
    TOPOLOGY_CHANGED=2
    CLAIM_CHILD_REQUEST=3
    CLAIM_CHILD_RESPONSE=4

class WifiMSGBase():
    def __init__(self, src, dst):
        self.packet = {}
        self.packet["src"] = src
        self.packet["dst"] = dst

class TopologyPropagate(WifiMSGBase):
    """
    Sends root periodically to all other nodes.
    """
    type = WIFIMSG.TOPOLOGY_PROPAGATE

    def __init__(self, src, dst, topology, flag = WIFIMSG.TOPOLOGY_PROPAGATE):
        super().__init__(src, dst)
        self.packet["flag"] = flag
        self.packet["msg"] = topology

    async def process(self, wificore : "wificore.WifiCore"):
        wificore.on_topology_propagate(self)

class TopologyChanged(WifiMSGBase):
    """
    Nodes send update when new node have been added or some node failed down. Sends to root and root then propagates.
    """
    type = WIFIMSG.TOPOLOGY_CHANGED

    def __init__(self, src,dst, my_topology, flag = WIFIMSG.TOPOLOGY_CHANGED):
        super().__init__(src, dst)
        self.packet["flag"] = flag
        self.packet["msg"] = my_topology

    async def process(self, wificore : "wificore.WifiCore"):
        wificore.on_topology_changed(self)

# class ClaimChild:
#     type = ESP_TYPE.CLAIM_CHILD_REQUEST

#     def __init__(self, claimer, vis, claimed):
#         self.claimer = claimer
#         self.vis = vis
#         self.claimed = claimed
    
#     async def process(self):
#         await asyncio.sleep(0.40)


# class ClaimChildRes(ClaimChild):
#     type = ESP_TYPE.CLAIM_CHILD_RESPONSE

#     async def process(self):
#         await asyncio.sleep(0.50)


WIFI_PACKETS = {
    WIFIMSG.TOPOLOGY_PROPAGATE  : TopologyPropagate,
    WIFIMSG.TOPOLOGY_CHANGED    : TopologyChanged
}

# Prepare WiFi message to be sent
def pack_wifimessage(obj):
    j = json.dumps(obj.packet)
    return j

# Unpack received WiFi message and process it.
async def unpack_wifimessage(msg, core : "wificore.WifiCore"):
    d = json.loads(msg)
    klass = WIFI_PACKETS[d["flag"]]
    obj = klass(d["src"], d["dst"], d["msg"])
    await obj.process(core)
    return obj

async def main():

    idn = b'\xff\xff\xff\xff\xff\xa0' # machine.unique_id()
    cntr = 1452
    rssi = -74.2
    ad = Advertise(idn, cntr, rssi)
    msg = pack_espmessage(ad)
    print(f"Advertise message {ad}")
    # tmpmsg = await unpack_espmessage(msg, None)

    gimme_creds = ObtainCreds(0,b'\xff\xff\xff\xff\xff\xa0' )
    try:
        msg = pack_espmessage(gimme_creds)
    except:
        print(msg)
    print(f"Obtain creds 0 {msg}")
    # tmpmsg = await unpack_espmessage(msg, "hej")
    gimme_creds = ObtainCreds(1,b'\xff\xff\xff\xff\xff\xa0' )
    try:
        msg = pack_espmessage(gimme_creds)
    except:
        print(msg)
    print(f"Obtain creds 1 {msg}")
    # tmpmsg = await unpack_espmessage(msg, "hej")
    gimme_creds = ObtainCreds(2,b'\xff\xff\xff\xff\xff\xa0' )
    msg = pack_espmessage(gimme_creds)
    print(f"Obtain creds 2 {msg}")
    # tmpmsg = await unpack_espmessage(msg, "hej")
    gimme_creds = ObtainCreds(3,b'\xff\xff\xff\xff\xff\xa0' )
    msg = pack_espmessage(gimme_creds)
    print(f"Obtain creds 3 {msg}")
    # tmpmsg = await unpack_espmessage(msg, "hej")
    gimme_creds = ObtainCreds(4,b'\xff\xff\xff\xff\xff\xa0' )
    msg = pack_espmessage(gimme_creds)
    print(f"Obtain creds 4 {msg}")
    # tmpmsg = await unpack_espmessage(msg, "hej")

    essid = b'ESP' + hexlify(b'<q\xbf\xe4\x8d\xa1')
    passwd = b'GpWVdRn3uMNPf1Ep' #id_generator()
    claim = SendWifiCreds(b'<q\xbf\xe4\x8d\xa1', len(essid), essid, passwd)
    msg = pack_espmessage(claim)
    print(f"Send WiFi creds in ESPNOW {msg}")
    # ret_msg = await unpack_espmessage(msg, "hello")
    
    tmp ={"topology": {"node" : "3c:71:bb:e4:8b:89",
                      "child" : 
                      [
                         {"node" : "3c:71:bb:e4:8b:a1",
                          "child": 
                          [
                              {
                                  "node": "3c:71:bb:e4:8b:b9",
                                  "child": {}  
                              }
                          ]
                          }
                      ]
                      }
    }
    dst = hexlify(b'<q\xbf\xe4\x8b\x88', ':').replace(b':', b'').decode()
    new_dst = unhexlify(dst)
    topo = TopologyPropagate(dst, dst, "Topology json")
    msg = pack_wifimessage(topo)
    print(f"Topology Propagate  {msg}")
    # obj = await unpack_wifimessage(msg, "core")

if __name__=="__main__":
    asyncio.run(main())
