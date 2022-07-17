#!/usr/bin/env python3

import json
import sys
from enum import Enum
from time import sleep
from typing import Any, Union

import requests

CHAIN_SCORE = 'cx0000000000000000000000000000000000000000'
GOV_SCORE = 'cx0000000000000000000000000000000000000001'
ICX = 10**18

defined_addresses = {
    'gov_score': GOV_SCORE,
    'chain_score': CHAIN_SCORE,
}

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

def dump_json(value: any, fp=sys.stdout):
    def json_handler(x) -> any:
        if isinstance(x, bytes):
            return '0x'+x.hex()
        raise TypeError(f'UnknownType(type={type(x)})')
    json.dump(value, fp=fp, indent=2, default=json_handler)
    print('', file=fp)

def ensure_block(id: str) -> Union[int, str]:
    if len(id) >= 64:
        return ensure_hash(id)
    elif id == 'latest':
        return id
    else:
        id = int(id, 0)
    return id

def ensure_hash(value: str) -> str:
    if not value.startswith('0x'):
        value = '0x'+value
    bs = bytes.fromhex(value[2:])
    if len(bs) != 32:
        raise Exception('InvalidHashValue(len(hash)!=32)')
    return value

class Shorten(Enum):
    RIGHT=0
    MIDDLE=1
    LEFT=2

def shorten(s: str, length: int, method: Shorten=Shorten.RIGHT, replace: str = '~') -> str:
    s_len = len(s)
    if s_len <= length:
        return s
    e_len = len(replace)
    to_skip = (s_len-length)+e_len
    if method == Shorten.MIDDLE:
        right = (s_len-to_skip)//2
        left = s_len-to_skip-right
        return s[:left]+replace+s[-right:]
    elif method == Shorten.LEFT:
        return replace+s[to_skip:]
    else:
        return s[:s_len-to_skip]+replace

def format_decimals(value: Union[str,int], f: int=2) -> str:
    if type(value) is not int:
        value = int(str(value), 0)
    i_value = value//ICX
    f_value = (value%ICX)*(10**f)//ICX
    return f'{{:,}}.{{:0{f}d}}'.format(i_value, f_value)