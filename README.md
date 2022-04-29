# DP
Diploma Thesis in micropython ESP32


## Manual to ESP32 boards
To get MicroPython on your board you need IDF from Espressif. Then download MicroPython and execute: \
cd micropython \
make -C mpy-cross/ \
cd ports/esp32/ \
get-idf  \
idf.py -D MICROPY_BOARD=GENERIC_SPIRAM build \ 
idf.py erase_flash \
idf.py flash  \

OR: \
make BOARD=GENERIC_SPIRAM deploy \ 

-using ampy to run, put, list, etc. files on ESP32: `ampy -p /dev/ttyUSB0 run webpage.py`

-using mpremote to connect to REPL : `mpremote [--port Port]`

## Project

- HMAC class in src/utils/hmac.py from https://github.com/dmazzella/ucrypto \
Sign every message iven if doesn't have credentials. Nodes in mesh with credentials will drop the message.
- config.json is configuration file, pmk and lmk must be 16B and creds should be 32B.

- Mesh Protected Setup procedure for exchange of credentials for HMAC signing. Button must be pressed on both devices:
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
[[SAVE_CREDENTIALS]]
DEL_PEER()
UNREQ_SYN -->>                      
                                    DEL_PEER()
```