# coding=utf-8
# (C) Copyright 2022 Jindřich Šesták (xsesta05)
# Licenced under Apache License.
# Part of diploma thesis.
# Content: Blink application demo.

import gc
from src.wificore import WifiCore

gc.collect()

from src.utils.messages import AppMessage

gc.collect()

from src.utils.pins import init_button, LEFT_BUTTON, init_led

gc.collect()

import uasyncio as asyncio
import time
import urandom
import machine

gc.collect()

PRESSED_FOR_MS = const(100)


class BlinkApp:

    def __init__(self):
        self.core = WifiCore(self)
        self._loop = self.core.loop
        self.button = init_button(LEFT_BUTTON, self.btn_pressed)  # Register IRQ for MPS procedure.
        self.led = init_led()
        self.colour = tuple(urandom.randint(0, 150) for _ in range(3))
        self.pressed_start = self.pressed_end = 0
        self.led[0] = (0,0,0)
        self.led.write()

    def start(self):
        """
        Blocking start of firmware application.
        """
        print(f"\nStart: Application Blink with colour {self.colour}")
        try:
            self.core.start()  # Run Wifi core.
            self._loop.run_forever()
        except Exception as e:  # Every except raises exception meaning that the task is broken, reset whole device
            print(f"Error in BlinkApp {e}")
            machine.reset()  # TODO. It solves the problem with ERROR 104 ECONNRESET after Soft Reset on child.

    async def blink(self):
        """Send app message to blink. """
        colour = self.colour
        try:
            msg = AppMessage(self.core.id, "ffffffffffff", {"blink": colour})
            await self.core.send_to_nodes(msg)
        except Exception as e:
            print(e)
        self.led[0] = colour
        self.led.write()
        print(f"BLINK-APP - blink with colour {colour}")

    async def process(self, appmsg: ""):
        """Process message for blinking."""
        if not appmsg.packet["msg"]:
            return
        colour = appmsg.packet["msg"].get("blink", None)  # Is list due to JSON
        if colour and len(colour) == 3:
            colour = tuple(colour)
            self.led[0] = colour
            self.led.write()
            print(f"BLINK-APP RECEIVED - blink with colour {colour}")
            # Measure hop time. Ping pong the blink message.
            # print(f"Processed in time : {time.time_ns()}")
            # try:
            #     msg = AppMessage(self.core.id, "ffffffffffff", {"blink": colour})
            #     await self.core.send_to_nodes(msg)
            #     print(f"Resend in time : {time.time_ms()}")
            # except Exception as e:
            #     print(e)

    def btn_pressed(self, irq):
        """
        Registered as IRQ for button.
        If triggered light LED and send app data to turn LED on to others.
        """
        if irq.value() == 0:
            self.pressed_start = time.ticks_ms()
        elif irq.value() == 1:
            self.pressed_end = time.ticks_ms()
        if PRESSED_FOR_MS < time.ticks_diff(self.pressed_end, self.pressed_start) < 10 * PRESSED_FOR_MS:
            self._loop.create_task(self.blink())
        return
