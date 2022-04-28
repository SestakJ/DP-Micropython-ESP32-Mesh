try:
    import src.wificore
    from blinkapp import BlinkApp
    c = BlinkApp()
except Exception as e:
    print('ERROR: ', e)
