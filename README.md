# DP
Diploma Thesis in micropython ESP32


## Manual to ESP32 boards
Micropython firmwares for ESP32 https://github.com/glenn20/micropython-espnow-images
And to upload them to ESP32 board:
    esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 115200 write_flash -z 0x1000 ../../Downloads/firmware-esp32-GENERICv17.bin

-using ampy to run, put, list, etc. files on ESP32
ampy -p /dev/ttyUSB0 run webpage.py

--using mpremote to connect to REPL
mpremote [--port Port]

## Project

- Microdot web server in micropython (https://github.com/miguelgrinberg/microdot)
