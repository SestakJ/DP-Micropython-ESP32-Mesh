# coding=utf-8
# (C) Copyright 2022 Jindřich Šesták (xsesta05)
# Licenced under Apache License.
# Part of diploma thesis.


try:
    import src.wificore
    from blinkapp import BlinkApp
    c = BlinkApp()
except Exception as e:
    print('ERROR: ', e)
