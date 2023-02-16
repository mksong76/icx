#!/usr/bin/env python3

from datetime import datetime, timedelta, timezone
import json
import sys
from enum import Enum
from time import sleep
from typing import Any, Union
import click

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
        idpart = bytes.fromhex(addr[2:])
        if len(idpart) < 20:
            idpart = ((b'\x00'*20)+idpart)[-20:]
        elif len(idpart) > 20:
            idpart = idpart[-20:]
        return prefix+idpart.hex()
    else:
        raise Exception(f'InvalidAddress(addr={addr})')

def ensure_score(addr: str) -> str:
    addr = ensure_address(addr)
    if not addr.startswith('cx'):
        raise Exception(f'InvalidSCORE(addr={addr})')
    return addr

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

def rest_get(url, timeout=1.0) -> Any:
    resp = requests.get(url, timeout=timeout)
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
    if f == 0:
        return f'{{:,}}'.format(i_value)
    else:
        return f'{{:,}}.{{:0{f}d}}'.format(i_value, f_value)

UTC = timezone(timedelta(hours=0), name='UTC')
def datetime_from_ts(tv: Union[str, int]) -> datetime:
    if type(tv) is str:
        tv = int(tv, 0)
    return datetime.utcfromtimestamp(tv/10**6).replace(tzinfo=UTC)

def format_dt(dt: datetime) -> str:
    return dt.strftime('%Y-%m-%d %H:%M:%S:%f %Z')

class HexIntegerType(click.ParamType):
    name = "hexint"
    def convert(self, value, param, ctx) -> int:
        if isinstance(value, int):
            return value
        try:
            return int(value, 0)
        except ValueError:
            self.fail(f'{value} is not a valid integer', param, ctx)

HEXINT = HexIntegerType()

class AddressType(click.ParamType):
    name = "address"
    def convert(self, value, param, ctx) -> str:
        if value is None:
            return None
        return ensure_address(value)

ADDRESS = AddressType()

class SCOREType(click.ParamType):
    name = "score"
    def convert(self, value, param, ctx) -> str:
        if value is None:
            return None
        return ensure_score(value)

SCORE = SCOREType()

class BlockIDType(click.ParamType):
    name = "blockID"
    def convert(self, value, param, ctx) -> str:
        if value is None:
            return None
        return ensure_block(value)

BLOCKID = BlockIDType()

class HashType(click.ParamType):
    name = "hash"
    def convert(self, value, param, ctx) -> str:
        if value is None:
            return None
        return ensure_hash(value)

HASH = HashType()