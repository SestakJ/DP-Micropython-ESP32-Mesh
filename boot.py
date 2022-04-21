try:
    from src.apps.blinkapp import BlinkApp
    c = BlinkApp()
except Exception as e:
    print('ERROR: ', e)