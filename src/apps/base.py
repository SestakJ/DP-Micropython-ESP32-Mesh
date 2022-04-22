# coding=utf-8
# (C) Copyright 2022 Jindrich Sestak (xsesta05)
# Licenced under MIT.
# Part of diploma thesis.
# Content: Base application pattern

import gc
from src.messages import AppMessage, pack_wifimessage, unpack_wifimessage
gc.collect()
from src.wificore import WifiCore
gc.collect()


class BaseApp():
    """
    Base parent for all apps.
    """

    def __init__(self):
        self.core = WifiCore(self)
        self._loop = self.core._loop

    def start(self):
        """
        Blocking start of firmware core.
        """
        print('\nStart: Application Blink')
        self._loop.create_task(self.core.start())    # Run Wifi core.

    async def process(self, appmsg : ""):
        """Process message. Children class receiving data should overwrite it."""
        pass

    async def send_msg(self, msg):
        """Send message. Children class sending data should overwrite it."""
        pass
