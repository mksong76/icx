#!/usr/bin/env python3

import getpass
import json
import os
from time import sleep
from typing import Any

import requests

CHAIN_SCORE = 'cx0000000000000000000000000000000000000000'
GOV_SCORE = 'cx0000000000000000000000000000000000000001'
ICX = 10**18

defined_addresses = [
    ('gov_score', GOV_SCORE),
    ('chain_score', CHAIN_SCORE),
]

def ensure_address(addr: str) -> str:
    if addr in defined_addresses:
        return defined_addresses[addr]
    elif addr.startswith('hx') or addr.startswith('cx'):
        prefix = addr[0:2]
        idpart = addr[2:]
        if len(idpart) < 40:
            idpart = (('0'*40)+idpart)[-40:]
        elif len(idpart) > 40:
            idpart = idpart[-40:]
        return prefix+idpart
    else:
        raise Exception(f'InvalidAddress(addr={addr})')

def jsonrpc_call(url, method: str, params: Any) -> Any:
    resp = requests.post(url, json={
        "jsonrpc": "2.0",
        "id": 1001,
        "method": "icx_call",
        "params": params
    }, timeout=1.0)
    if resp.status_code != 200:
        raise f"HTTPError(status={resp.status_code}) "
    res = resp.json()
    if "code" in res:
        raise f"JSONRPCERror(code={res['code']},msg={res['message']}"
    return res['result']

def rest_get(url) -> Any:
    resp = requests.get(url, timeout=1.0)
    if resp.status_code != 200:
        raise f"HTTPError(status={resp.status_code}) "
    return resp.json()

