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
from src.messages import  WIFI_PACKETS, TopologyPropagate, TopologyChanged, pack_wifimessage, unpack_wifimessage
from src.espnowcore import EspnowCore, CONFIG_FILE
from src.tree import Tree, TreeNode, json_to_tree

# Constants
DEFAULT_S = const(5)
BEACON_S = const(15)
SERVER_PORT = const(1234)
CHILDREN_COUNT = const(1)  # Number of maximum children for each node.

def mac_to_str(mac : bytes):
    return hexlify(mac, ':').replace(b':', b'').decode()

def str_to_mac(s : str):
    return unhexlify(s)

class WifiCore():
    DEBUG = True

    def __init__(self, app : "apps.baseapp"):
        self.app = app
        self.core = EspnowCore()
        self._loop = self.core._loop
        # Network interfaces.
        self.ap = self.core.ap
        self.sta = self.core.sta
        self.sta.wlan.disconnect()
        self._config = self.core._config
        self.ap_essid = self.core.ap_essid
        self.ap_password = self.core.ap_password
        self.sta_ssid = self.sta_password = None
        self.ap_authmode = AUTH_WPA_WPA2_PSK   # WPA/WPA2-PSK mode.

        # Node definitions.
        self._id = mac_to_str(self.core.id)
        # Sockets and tree topology. 
        self.children_writers = {} # {mac: (writer, (ip, port))}
        self.parent = self.parent_reader = self.parent_writer = None

        self.tree_topology = None

    def dprint(self, *args):
        if self.DEBUG:
            print(*args)

    def start(self):
        """
        Blocking start of firmware core.
        """
        print('\nStart: node ID: {}\n'.format(self._id))
        self._loop.create_task(self.core._run())    # Run ESPNOW core.
        self._loop.create_task(self._run())
        try:
            self._loop.run_forever()
        except Exception as e:    # TODO Every except raises exception meaning that the task is broken, reset whole device
            # asyncio.run(self.close_all())
            print(e)
        #     import machine
        #     # machine.reset() # TODO uncomment. It solves the problem with ERROR 104 ECONNRESET after Soft Reset on child.

    async def _run(self):
        """ Starting points in the mesh. Additional task created in called functions. """
        # Node must open socket to parent node on station interface, then start its own AP interface. 
        # Otherwise socket would bind to AP interface.
        await self.connect_to_parent()

        self._loop.create_task(self.start_parenting_server())
    
    async def connect_to_parent(self):
        """
        When received send_wifi_creds from parent -> connect to parent AP and open connection with socket to him.
        Or when node is root node -> create Tree topology.
        Create tasks for communication to parent.
        """
        while not (self.core.sta_ssid or mac_to_str(self.core.root) == self._id): # Either on_send_wifi_creds received or is root node.
            await asyncio.sleep(DEFAULT_S)
        # self.core.DEBUG = False     # Stop Debug messages in EspnowCore
        self.sta.wlan.disconnect()  # Disconnect from any previously connected WiFi.
        if self.core.sta_ssid:
            self.sta_ssid = self.core.sta_ssid
            self.sta_password = self.core.sta_password
            await self.sta.do_connect(self.sta_ssid, self.sta_password)
            self.dprint("[Connect to parent WiFi] Done")
        else:    # Node is root node. Create Topology with itself on top.
            tree = Tree()
            tree.root = TreeNode(self._id, None)
            self.tree_topology = tree
            return

        self.parent_reader, self.parent_writer = await asyncio.open_connection(self.sta.ifconfig()[2], SERVER_PORT)
        self.dprint("[Open connection to parent] Done")
        self._loop.create_task(self.send_beacon_to_parent())
        self._loop.create_task(self.listen_to_parent())

    async def send_beacon_to_parent(self):
        """ Send blank messages to parent for him to save my MAC addr and beacon to him."""
        msg = TopologyPropagate(self._id, "ffffffffffff", None) 
        while True:
            self.dprint("[SEND] to parent")
            msg.packet["msg"] = None
            await self.send_msg(self.parent , self.parent_writer, msg)
            await asyncio.sleep(BEACON_S)
            
    async def listen_to_parent(self):
        self.parent = await self.register_mac(self.parent_reader) # Register peer with mac address
        self._loop.create_task(self.on_message(self.parent_reader))
           

    async def start_parenting_server(self):
        """
        Create own WiFi AP and start server for listening for children to connect.
        """
        self.ap.config(essid=self.ap_essid, password=self.ap_password, authmode=self.ap_authmode, hidden=0)
        while not self.ap.wlan.active():
            await asyncio.sleep(DEFAULT_S)
        self.dprint("[START SERVER]")
        try:
            await self.in_tree_topology()   # Either root node has created topology or must wait for parent to send topology.
            await asyncio.start_server(self.listen_to_children, '0.0.0.0', SERVER_PORT)
            self._loop.create_task(self.send_topology_propagate(msg=["hello to child From ROOTOOOOT", 195]))
            self._loop.create_task(self.claim_children())
        except Exception as e:
            self.dprint("[Start Server] error: ", e)
            raise e

    async def in_tree_topology(self):
        while not self.tree_topology: # Received Tree topology from parent node.
            await asyncio.sleep(1)
        while not self.tree_topology.search(self._id): # Received updated Tree topology from parent node.
            await asyncio.sleep(1)
        return True
    
    async def listen_to_children(self, reader, writer):
        """
        Must update tree topology first. The topology has to be received earlier from its parent.
        Add new node and inform root about topology change.
        """
        mac = await self.register_mac(reader)       # Register peer with mac address.
        self.children_writers[mac] = (writer, writer.get_extra_info('peername'))
        my_node = self.tree_topology.search(self._id)
        new_child = TreeNode(mac, my_node)
        self.tree_topology.search(self._id).add_child(new_child)
        self.dprint("[Receive] child added: ", mac, writer.get_extra_info('peername'))
        await self.topology_changed(self.tree_topology.root.data, self.parent_writer)
        print("[Receive new child] treee changed ", self.tree_topology.pack())

        self._loop.create_task(self.on_message(reader))
        
    async def send_topology_propagate(self, msg):
        """ Periodically propagate tree topology to children nodes."""
        msg = TopologyPropagate(self._id, "ffffffffffff", None)
        while True:
            msg.packet["msg"] = self.tree_topology.pack() if self.tree_topology else None
            self._loop.create_task(self.send_to_children_once(msg))
            await asyncio.sleep(DEFAULT_S)

    async def send_to_children_once(self, msg):
        print("[SEND] to children")
        for destination, writers in self.children_writers.items(): # writers is a tuple(stream_writer, tuple(IP, port))
            self._loop.create_task(self.send_msg(destination, writers[0], msg))

    async def claim_children(self):
        """
        Claim child nodes while there are some nodes present in mesh but not in the tree topology.
        """
        tree = None
        tree_nodes = []
        neighbour_nodes = []
        while True:
            neighbour_nodes = list(dict(filter(lambda elem: elem[1][4] == 0, self.core.neighbours.items())).keys())
            tree_nodes = []
            tree = self.tree_topology
            cnt_children = 0
            if tree:
                tmp = list(tree.root.get_children().keys()) + [tree.root.data]
                tree_nodes = [str_to_mac(i) for i in tmp]
                cnt_children = len(tree.search(self._id).children)
            possible_children = [mac for mac in neighbour_nodes if mac not in tree_nodes]
            if cnt_children < CHILDREN_COUNT and possible_children:
                self.core.claim_children([urandom.choice(possible_children)])
            await asyncio.sleep(2*DEFAULT_S)

    async def register_mac(self, reader):
        """
        Receive first blank packet to be able to register MAC address of node
        """
        try:
            res = await reader.readline()
            self._loop.create_task(self.process_message(res))
            if res == b'': # Connection closed by host, clean up. Maybe hard reset.
                await self.close_connection(writer.get_extra_info('peername'))
                self.dprint("[Receive] conn is dead")
                return
        except Exception as e:
            self.dprint("[Receive] x conn is prob dead, stop listening. Error: ", e)
            await self.close_connection(writer.get_extra_info('peername'))
            return
        msg = json.loads(res)
        return msg["src"]

    async def on_message(self, reader):
        """
        Wait for messages. Light weight function to not block recv process. Further processing in another coroutine.
        """
        # TODO add parametre writer to be able to close him
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
            await self.close_connection(writer.get_extra_info('peername'))
            return

    async def process_message(self, msg):
        obj = await unpack_wifimessage(msg, self)
        self.dprint("[Processed msg] ", msg)

    async def send_msg(self, mac, writer, message):
        """
        Create message from class object message and send it through WiFi socket writer to mac.
        """
        if not writer:
            return
        try:
            self.dprint("[SEND] to:", mac ," message: ", message)
            writer.write('{}\n'.format(pack_wifimessage(message)))
            await writer.drain()
            self.dprint("[SEND] drained and done")
        except Exception as e:
            self.dprint("[Send] Whew! ", e, " occurred.")
            await self.close_connection(mac)

    async def send_to_all(self, msg): # TODO with routing
        await self.send_to_children_once(msg)
        await self.send_msg(self.parent, self.parent_writer, msg)
    
    def on_topology_propagate(self, topology : TopologyPropagate):
        """
        Called from message.py. Save tree topology only from parent node.
        """
        if not topology.packet["msg"]: # Topology Exchanges are blank from children as beacons
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
        # When new node connects or child node fails down inform just only root node.
        msg = TopologyChanged(self._id, node, self.tree_topology.pack())     # Send Topology update. 
        await self.send_msg(node, writer, msg)

    def on_topology_changed(self, topology: TopologyChanged):
        """
        Called from message.py. Topology update is saved only on root node. Root node then propagates new topology.
        """
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
            # raise Error # TODO To trigger machine.reset()
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
        """ Clean up function."""
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