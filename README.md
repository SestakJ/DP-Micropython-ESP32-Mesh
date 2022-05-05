# Diploma Thesis - Dynamic mesh network in MicroPython on ESP32 with ESP-NOW protocol. 
### Jindřich Šesták 2021/22

Mesh network connects multiple nodes into one structure. Nodes create tree topology with one parent node. Parent node can be connected to the WiFi AP. Mesh operates on top of two protocol, ESP-NOW and WiFi. Basic self-healing is implemented and routing in the mesh works as well. This project was developed as Diploma Thesis on Brno University of Technology on Faculty of Information Technology in 2021/22 with collaboration with company Espressif s.r.o.
Mesh has static root node set. On at least one the credentials have to be set, other nodes can be added with MPS procedure with button pressing. Can automatically create connections in WiFi between nodes, self-heal and support application data transition.
Mesh is developed and tested on ESP32-Buddy boards, with firmware "build-GENERIC" with 111KB of memory.

## Overview

Mesh protocol operates firstly on ESP-NOW and collects info about other nodes. Then root nodes starts claiming nodes into the tree using WiFi and tree topology is formed.
The mesh has the following features and steps:
* **Add broadcast** MAC address into ESP-NOW communication.
* Wait until it has key for message **HMAC-SHA256 signing**. Serves as integrity and
authentication check for messages.
* Distribute the key through **Mesh Protected Setup** process. Activate by button
pressed for 4,25-8,5 seconds and run for 45 seconds.
* Send **periodic beacon advertisement** every 5 seconds. Manage database of nodes.
Retransmit information about other nodes every 13 seconds.
* Root node election is only simulated but not implemented. The **root node is set
statically** in the configuration file.
• Send AES-128 encrypted **node’s WiFi AP SSID and password** to child nodes. This
function is triggered by WiFi core but uses ESP-NOW protocol.
* **Connect** to parent's WiFi AP interface and creates socket connections between them.(Tree edge)
* Start its **own WiFi AP** interface and claim child nodes.
* **Self-healing** when child is dead wipe it out of the tree. When parent is dead reset itself, otherwise socket raises error in new connection to parent.
* **Demo app** for blinking LED diode. Each node has its own specific colour.

## Structure of this project:
- Readme.md - this readme file.
- Makefile - makefile for project deployment.
- boot.py - init file which runs everytime on the board.
- main.py - starting point runs everytime on the board.
- config.json - configuration file to set: the root node, the WiFi identifications, ESP-NOW LMK and PMK, debug prints and on one node it is necessary to set "credentials" with 32 char length.
- blinkapp.py - demo application for use of mesh network package.
- src/
  - espnowcore.py - base layer core class with ESP-NOW functionality.
  - wificore.py - creation of tree topology with WiFi connection between nodes.
  - utils/ 
    - hmac.py - HMAC class for message signing. Taken from: https://github.com/dmazzella/ucrypto
    - mesasges.py - classes for messages in ESP-NOW are packed using struct library into Bytes to save space. WiFi messages are packed using JSON library.
    - net.py - Net and ESP classes overshadow original network.WLAN and esp.espnow.ESPNow classes.
    - oled_display.py - module for controlling the OLED built in display taken from: https://how2electronics.com/micropython-interfacing-oled-display-esp32/
    - pins.py - module for controlling LED diode and buttons on ESP32-Buddy.
    - tree.py - module for Tree and TreeNode definitions. Tree class represent tree topology in the mesh.
- micropython_616/ - copy of github form glenn-g20/ branch of micropython with working ESP-NOW support on ESP32-Buddy boards. This version is probably re-based and unavailable.

## Manual to ESP32 boards
To get MicroPython on your board you need ESP-IDF from Espressif. Then download MicroPython and execute following. This will provide board with 111KB of RAM: \
```
cd micropython_616\
make -C mpy-cross/ \
cd ports/esp32/ \
get-idf  \
idf.py build \ 
idf.py erase_flash \
idf.py flash  \
```

Full potential of ESP32-Buddy is 4MB of SPIRAM but this build doesn't work with MicroPython well. \
`idf.py -D BOARD=GENERIC_SPIRAM` 

You can use ampy to run, put, list,   etc. files on ESP32: `ampy -p /dev/ttyUSB0 put config.json`

-using mpremote to connect to REPL : `mpremote [connect --port:/dev/ttyUSB5]`

## Use of project
### Configuration
In config.json there are several fields that need to be defined.
* Credentials define one mesh network. For several mesh networks change this value. This value has to be set at least on one node. Other nodes can obtain this key through MPS process when you need to press button for 4,25-8,5 seconds to trigger MPS process.
* EspNowConfig and WifiConfig are bool values that allow debug printing in the REPL console.
* root filed is for statically setting the root node
* WIFI is for defining WIFI SSID, password and channel WIFI operates on.
* esp_lmk and esp_pmk are values for MPS proccess and can be changed. But must match on both devices in order to MPS to work.

### Mesh Protected Setup
Mesh Protected Setup procedure is for exchange of credentials for HMAC signing. Button must be pressed on both devices. Then they register one another for unicast ciphered communication using LMK and PMK. In secure unicast they exchange the key credentials to be able to sign messages fir the mesh.
```
Handshake protocol for exchange of credentials:
Client                              Server
--------------------------------------------
SYN -->>                            
                                    ADD_PEER(LMK)
                              <<--  SYN_ACK
ADD_PEER(LMK)
OBTAIN -->>                         
                              <<--  RESPOND
                                    DEL_PEER()
[[SAVE_CREDENTIALS]]
DEL_PEER()                               
```

### Application
User can define his own application. Demo application is in blinkapp.py. 
Here are basic functions that needs to be implemented in the user app:
```python
from src.wificore import WifiCore
class App:
  def __init__(self):
    self.wificore = WifiCore(self)
    self._loop = self.core.loop
    
  def start(self):
    self.wificore.start()
    ...

  async def process(self, appmsg : "messages.AppMessage"):
    ...
    
  async def whatever(self):
    ...
    appmsg = AppMessage(self.core.id, "ffffffffffff", {"blink": colour})
    await self.core.send_to_nodes(appmsg)
    ...
```