# coding=utf-8
# (C) Copyright 2022 Jindřich Šesták (xsesta05)
# Licenced under Apache License.
# Part of diploma thesis.
import machine

try:
    # 'c' is available from boot.py
    c.start()
except Exception as e:
    print('ERROR in main: ', e)
    #machine.reset()
