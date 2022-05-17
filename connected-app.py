# coding=utf-8
# (C) Copyright 2022 Jindřich Šesták (xsesta05)
# Licenced under Apache License.
# Part of diploma thesis.
# Content: User's app to control the light of the mesh. Run on your PC with correct IP of the root node.

import gc

gc.collect()
from src.utils.messages import AppMessage, pack_wifimessage

gc.collect()

import asyncio
import time
import random

gc.collect()

ROUTER_PORT_FOR_USER = 4321
USER_MAC = "ff0000000000"


class UserApp:
    """App to run on user's PC.
    To be connected to the WIFI with the mesh you must specify the WiFi credentials in config.json.
    User must specify the IP of the root node (it is printed on the OLED display)."""
    def __init__(self, ip):
        self._loop = asyncio.get_event_loop()
        self.colour = tuple(random.randint(0, 100) for _ in range(3))
        self.esp_ip = ip
        self.writer = self.reader = None

    def start(self):
        """
        Blocking start of firmware application.
        """
        print(f"\nStart: Application on User PC with colour {self.colour}")
        try:
            self._loop.create_task(self.run())
            self._loop.run_forever()
        except Exception as e:  # Every except raises exception meaning that the task is broken, reset whole device
            print(f"Error in User App {e}")

    async def run(self):
        reader, writer = await asyncio.open_connection(
            self.esp_ip, ROUTER_PORT_FOR_USER)
        self.writer = writer
        self.reader = reader
        self._loop.create_task(self.process())
        self._loop.create_task(self.blink())
        print(f"\nRun: Application on User PC with colour {self.colour}")

    async def blink(self):
        """Send app message to blink. """
        while True:
            colour = tuple(random.randint(0, 100) for _ in range(3))
            try:
                msg = AppMessage(USER_MAC, "ffffffffffff", {"blink": colour})
                self.writer.write(('{}\n'.format(pack_wifimessage(msg))).encode())
            except Exception as e:
                print(e)
            print(f"BLINK-APP - blink with colour {colour}")
            await asyncio.sleep(20)

    async def process(self):
        """READ messages from the root node."""
        while True:
            appmsg = await self.reader.readline()
            if appmsg:
                print(f"Received msg from root node {appmsg}")


def main():
    app = UserApp('192.168.0.171')
    app.start()


if __name__ == "__main__":
    main()
