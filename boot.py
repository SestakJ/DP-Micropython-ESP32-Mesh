
try:
    from src.wificore import WifiCore
    c = WifiCore()
except Exception as e:
    print('ERROR: ', e)