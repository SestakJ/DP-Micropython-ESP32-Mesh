# content of test_sample.py
from src.espmsg import Advertise, Root_elected, Claim_child, Claim_child_res, Node_fail, create_message, on_message
import pytest

from unittest.mock import MagicMock

class network:
    STA_IF =0
    AP_IF = 1
    WLAN = MagicMock()



from src.net import Net, ESP

def func(x):
    return x + 1

def test_answer():
    assert func(3) == 4

def test_advertise():
    node_id = b'\xff\xff\xff\xff\xff\xa0' # machine.unique_id()
    cntr = 1452
    rssi = -74.2
    ad = Advertise(node_id, cntr, rssi)
    msg = create_message(ad)
    assert msg[1] == 255 #\xff

def test_root():
    node_id = b'\xff\xff\xff\xff\xff\xa0' # machine.unique_id()
    cntr = 1452
    rssi = -74.2
    root = Root_elected(node_id, cntr, rssi)
    msg = create_message(root)
    assert msg[0] == 2

def test_claim_child():
    claimer = b'\xff\xff\xff\xff\xff\xa0' # machine.unique_id()
    vis = 0
    claimed = b'\xff\xff\xff\xff\xff\xb2'
    claim = Claim_child(claimer, vis, claimed)
    msg = create_message(claim)
    assert msg ==b'\x03\xff\xff\xff\xff\xff\xa0\x00\x00\x00\x00\xff\xff\xff\xff\xff\xb2' 

def test_claim_child_res():
    claimer = b'\xff\xff\xff\xff\xff\xa0' # machine.unique_id()
    vis = -55.4
    claimed = b'\xff\xff\xff\xff\xff\xb2'
    claim = Claim_child_res(claimer, vis, claimed)
    msg = create_message(claim)
    assert msg[0] == 4

def test_node_fail():
    node_id = b'\xff\xff\xff\xff\xff\xa0' # machine.unique_id()
    n_fail = Node_fail(node_id)
    msg = create_message(n_fail)
    assert msg == b'\x06\xff\xff\xff\xff\xff\xa0'

async def test_on_message():
    msg = b'\x02\xff\xff\xff\xff\xff\xa0\x00\x01\x00\x00\x00\x00'
    obj = await on_message(msg)
    assert type(obj) is Root_elected