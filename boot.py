
try:
    from src.core import Core
    c = Core()
except Exception as e:
    print('ERROR: ', e)