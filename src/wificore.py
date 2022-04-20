# coding=utf-8
# (C) Copyright 2022 Jindrich Sestak (xsesta05)
# Licenced under MIT.
# Part of diploma thesis.
# Content: File with WiFi logic

import uasyncio as asyncio
import machine
import json
from ubinascii import hexlify, unhexlify
from network import AUTH_WPA_WPA2_PSK
import urandom
from src.net import Net, ESP
from src.espmsg import  WIFI_PACKETS, TopologyPropagate, TopologyChanged, pack_wifimessage, unpack_wifimessage
from src.core import Core
from src.tree import Tree, TreeNode, json_to_tree, get_all_nodes
# User defined constants.
CONFIG_FILE = 'config.json'

# Constants
DEFAULT_S = const(5)
BEACON_S = const(15)
DIGEST_SIZE = const(32)     # Size of HMAC(SHA256) signing code. Equals to Size of Creds for HMAC(SHA256).
CREDS_LENGTH = const(32)
SERVER_PORT = const(1234)
CHILDREN_COUNT = const(1)  # Number of max child for each node.

def mac_to_str(mac : bytes):
    return hexlify(mac, ':').replace(b':', b'').decode()

def str_to_mac(s : str):
    return unhexlify(s)

class WifiCore():
    DEBUG = True

    def __init__(self):
        self.core = Core()
        self._loop = self.core._loop
        self._loop.create_task(self.core._run())
        self.ap = self.core.ap
        self.sta = self.core.sta
        self.sta.wlan.disconnect()
        self._config = self.core._config
        self.ap_essid = self.core.ap_essid
        self.ap_password = self.core.ap_password
        self.sta_ssid = self.sta_password = None
        self.ap_authmode = AUTH_WPA_WPA2_PSK   # WPA/WPA2-PSK mode.
        # Node definitions
        self._id = mac_to_str(self.ap.wlan.config('mac'))
        # User defined from config.json.
        self._loop = self.core._loop
        self.children_writers = {} # {mac: (writer, (ip, port))}
        self.parent = self.parent_reader = self.parent_writer = None
        self.json_topology = self._config.get('topology', None)
        self.tree_topology = None

    def dprint(self, *args):
        if self.DEBUG:
            print(*args)

    def start(self):
        """
        Blocking start of firmware core.
        """
        print('\nStart: node ID: {}\n'.format(self._id))
        self._loop.create_task(self._run())
        try:
            self._loop.run_forever()
        except Exception as e:    # TODO Every except raises exception meaning that the task is broken, reset whole device
            # asyncio.run(self.close_all())
            print(e)
        #     import machine
        #     # machine.reset() # TODO uncomment. It solves the problem with ERROR 104 ECONNRESET after Soft Reset on child.

    async def _run(self):
        """
        Creation of all the neccessary tasks for mesh.
        """
        # Node first must open socket to parent node, then start its own AP interface. Otherwise socket would bind to localhost.
        await self.connect_to_parent()

        self._loop.create_task(self.start_parenting())
    
    async def connect_to_parent(self):
        """
        Wait for the right signal. Assign WiFi credentials and connect to it, open connection with socket. 
        Or node is to be the root so return.
        """
        while not (self.core.sta_ssid or mac_to_str(self.core.root) == self._id): # Either parent claimed him or is root node.
            await asyncio.sleep(DEFAULT_S)
        # self.core.DEBUG = False     # Stop Debug messages in EspCore
        self.sta.wlan.disconnect()  # Disconnect from any previously connected WiFi.
        if self.core.sta_ssid:
            self.sta_ssid = self.core.sta_ssid
            self.sta_password = self.core.sta_password
            await self.sta.do_connect(self.sta_ssid, self.sta_password)
            self.dprint("[Connect to parent WiFi] Done")
        else: # Node is root node. Create Topology with myself on top.
            tree = Tree()
            tree.root = TreeNode(self._id, None)
            self.tree_topology = tree
            return
        self.parent_reader, self.parent_writer = await asyncio.open_connection(self.sta.ifconfig()[2], SERVER_PORT)
        self.dprint("[Open connection to parent] Done")
        self._loop.create_task(self.send_beacon_to_parent())
        self._loop.create_task(self.receive_from_parent())
        
    async def send_beacon_to_parent(self):
        msg = TopologyPropagate(self._id, "ffffffffffff", None) # Send first message for parent to save my MAC addr.
        while True:
            self.dprint("[SEND] to parent")
            msg.packet["msg"] = None
            await self.send_msg(self.parent , self.parent_writer, msg)
            await asyncio.sleep(BEACON_S)
            
    async def receive_from_parent(self):
        self.parent = await self.register_mac(self.parent_reader) # Register peer with mac address
        self._loop.create_task(self.receive(self.parent_reader))
            
    async def start_parenting(self):
        """
        Create own WiFi AP and start server for listening for children to connect.
        """
        self.ap.config(essid=self.ap_essid, password=self.ap_password, authmode=self.ap_authmode, hidden=0)
        while not self.ap.wlan.active():
            await asyncio.sleep(DEFAULT_S)
        self.dprint("[START SERVER]")
        try:
            self._loop.create_task(asyncio.start_server(self.receive_from_child, '0.0.0.0', SERVER_PORT))
            self._loop.create_task(self.sending_to_children(msg=["hello to child From ROOTOOOOT", 195]))
            await self.in_tree_topology()
            self._loop.create_task(self.claim_children())
        except Exception as e:
            self.dprint("[Start Server] error: ", e)
            raise e

    async def in_tree_topology(self):
        while not self.tree_topology:
            await asyncio.sleep(1)
        while not self.tree_topology.search(self._id):
            await asyncio.sleep(1)
        return True

    async def claim_children(self):
        tree = None
        tree_nodes = []
        neighbour_nodes = []
        while True:
            neighbour_nodes = list(self.core.neighbours.keys())
            tree_nodes = []
            tree = self.tree_topology
            children_count = 0
            if tree:
                tmp = list(tree.root.get_children().keys())
                tree_nodes = [str_to_mac(i) for i in tmp]
                children_count = len(tree.search(self._id).children)
            try:
                
                for mac in tree_nodes:
                    neighbour_nodes.remove(mac)
                neighbour_nodes.remove(str_to_mac(self._id))
            except ValueError as e:
                pass
            if children_count < CHILDREN_COUNT:
                self.core.claim_children([urandom.choice(neighbour_nodes)])
            await asyncio.sleep(2*DEFAULT_S)

    async def sending_to_children(self, msg):
        msg = TopologyPropagate(self._id, "ffffffffffff", None)
        while True:
            msg.packet["msg"] = self.tree_topology.pack() if self.tree_topology else None
            self._loop.create_task(self.send_to_children_once(msg))
            await asyncio.sleep(DEFAULT_S)

    async def send_to_children_once(self, msg):
        # l = self.ap.wlan.status('stations') # Get list of tuples of MAC of connected devices.
        # children = [mac[0] for mac in l]
        print("[SEND] to children")
        for destination, writers in self.children_writers.items(): # But this is tuple(IP, port)
            # if destination[0] not in children: # Delete old connections from dead child nodes.
            #     # self._loop.create_task(self.close_connection(destination))
            #     continue
            self._loop.create_task(self.send_msg(destination, writers[0], msg))

    async def receive_from_child(self, reader, writer):
        mac = await self.register_mac(reader)       # Register peer with mac address.
        self.children_writers[mac] = (writer, writer.get_extra_info('peername'))
        my_node = self.tree_topology.search(self._id)
        new_child = TreeNode(mac, my_node)
        self.tree_topology.search(self._id).add_child(new_child)
        self.dprint("[Receive] child added: ", mac, writer.get_extra_info('peername'))
        await self.topology_changed(self.tree_topology.root.data, self.parent_writer)
        print("[Receive new child] treee changed ", self.tree_topology.pack())

        self._loop.create_task(self.receive(reader))

    async def register_mac(self, reader):
        """
        Receive first blank packet to be able to register MAC address of node
        """
        try:
            res = await reader.readline()
            self.dprint("[Receive] from x message: ", res)
            self._loop.create_task(self.process_message(res))
            if res == b'': # Connection closed by host, clean up. Maybe hard reset.
                await self.close_connection(writer.get_extra_info('peername'))
                self.dprint("[Receive] conn is dead")
                return
        except Exception as e:
            self.dprint("[Receive] x conn is prob dead, stop listening. Error: ", e)
            return
            raise e
        msg = json.loads(res)
        return msg["src"]

    async def receive(self, reader):
        # TODO must be a routing table and when dst address is not myself retransmit in direction of dst address up or down stream.
        try:
            while True:
                res = await reader.readline()
                self._loop.create_task(self.process_message(res)) # Create task so this function is as fast as possible. 
                if res == b'': # Connection closed by host, clean up. Maybe hard reset.
                    await self.close_connection(writer.get_extra_info('peername'))
                    self.dprint("[Receive] conn is dead")
                    return
        except Exception as e:
            self.dprint("[Receive] x conn is prob dead, stop listening. Error: ", e)
            return
            # raise e
        # self.dprint("Close the connection")
        # del self.children_writers[writer.get_extra_info('peername')]
        # writer.close()
        # await writer.wait_closed()

    async def process_message(self, msg):
        self.dprint("[RECEIVED] ", msg)
        obj = await unpack_wifimessage(msg, self)
        self.dprint("[Receive] from x message: ", obj)

    async def send_msg(self, mac, writer, message):
        if not writer:
            return
        try:
            self.dprint("[SEND] to:", mac ," message: ", message)
            writer.write('{}\n'.format(pack_wifimessage(message)))
            await writer.drain()
            print("[SEND] drained and done")
        except Exception as e:
            print("[Send] Whew! ", e, " occurred.")
            await self.close_connection(mac)
    
    def on_topology_propagate(self, topology : TopologyPropagate):
        if not topology.packet["msg"]: # Topology Exchange is blank when children infroms it has connected
            return
        tmp = self.tree_topology
        self.tree_topology = None
        del tmp
        tree = Tree()
        json_to_tree(topology.packet["msg"], tree, None)
        if topology.packet["src"] == self.parent:
            self.tree_topology = tree
            print("[OnTopologyPropagate] ", topology.packet)

    async def topology_changed(self, node, writer):
        msg = TopologyChanged(self._id, node, self.tree_topology.pack())     # Send Topology update. 
        await self.send_msg(node, writer, msg)

    def on_topology_changed(self, topology: TopologyChanged):
        print("[OnTopologyChanged] ", topology.packet)
        if not topology.packet["msg"] and not self._id != self.tree_topology.root.data: 
            return
        tree = Tree()
        json_to_tree(topology.packet["msg"], tree, None)
        old_node = self.tree_topology.search(topology.packet["src"])
        old_node_parent = old_node.parent
        new_node = tree.search(topology.packet["src"])
        new_node.parent = old_node_parent
        old_node_parent.del_child(old_node)
        old_node_parent.add_child(new_node)

    async def close_connection(self, mac):
        writer = None
        if mac == self.parent:
            writer = self.parent_writer
            self.parent = None
            self.parent_writer = None
            self.parent_reader = None
            del self.tree_topology      # Lost connection to parent so drop whole topology.
            self.tree_topology = None
            # raise Error # To trigger machine.reset()
        elif mac in self.children_writers:
            writer, ip = self.children_writers[mac]
            del self.children_writers[mac]
            to_delete = self.tree_topology.search(mac)
            print(to_delete)
            print(to_delete.parent)
            to_delete.parent.del_child(to_delete)   # Delete lost child from topology.
            await self.topology_changed(self.tree_topology.root.data, self.parent_writer)
            print("[Close connection] treee changed ", self.tree_topology.pack())
        if writer:
            writer.close()
            await writer.wait_closed()
        
    async def close_all(self):
        if self.parent_writer:
            self.close_connection(self.parent)
        for address, writer in self.children_writers.items():
            await self.close_connection(address)
        self.children_writers.clear()
        self.dprint("[Clean UP of sockets] Done")

# TODO Now nodes every x seconds try to claim new nodes. But RSSI to nodes doesn't work
# TODO routing 

def main():
    from src.wificore import WifiCore
    c= WifiCore()
    c.start()