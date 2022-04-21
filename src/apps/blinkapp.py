# coding=utf-8
# (C) Copyright 2022 Jindrich Sestak (xsesta05)
# Licenced under MIT.
# Part of diploma thesis.
# Content: Base application pattern

from .base import BaseApp
from src.utils import init_button, id_generator, LEFT_BUTTON, LED_PIN, init_LED
from src.messages import AppMessage

import uasyncio as asyncio
import machine
import time
import urandom

PRESSED_FOR_MS = const(100)

class BlinkApp(BaseApp):

    def __init__(self):
        super().__init__()
        self.button = init_button(LEFT_BUTTON, self.btn_pressed) # Register IRQ for MPS procedure.
        self.led = init_LED()
        self.colour = tuple(urandom.randint(0,250) for i in range(3))

    async def blink(self):
        """Send app message to blink. """
        colour = self.colour
        try:
            msg = AppMessage(self.core._id, "ffffffffffff", {"blink": colour})
            await self.core.send_to_all(msg)
        except Exception as e:
            print(e)
        self.led[0] = colour
        self.led.write()

    async def process(self, appmsg : ""):
        """Process message for blinking."""
        if not appmsg.packet["msg"]:
            return
        colour =  appmsg.packet["msg"].get("blink", None) # Is list due to JSON
        if colour and len(colour) == 3:
            colour = tuple(colour)
            self.led[0] = colour
            self.led.write()
        print(f"LED switch to colour {colour}")

    def btn_pressed(self, irq):
        """
        Registered as IRQ for button.
        Function to measure how long is button pressed. If between PRESSED_FOR_MS and 2*PRESSED_FOR_MS, we can exchange credentials.
        """    
        if irq.value() == 0:
            self.pressed_start = time.ticks_ms()
        elif irq.value() == 1:
            self.pressed_end = time.ticks_ms()
        self.dprint("[MPS] button presed for: ", time.ticks_diff(self.pressed_end, self.pressed_start))
        if PRESSED_FOR_MS < time.ticks_diff(self.pressed_end, self.pressed_start) < 10*PRESSED_FOR_MS:
            self._loop.create_task(self.blink())
        return
