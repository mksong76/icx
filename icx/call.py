#!/usr/bin/env python3


import json
import re
import sys
from typing import List

import click

from iconsdk.builder.call_builder import CallBuilder
from iconsdk.builder.transaction_builder import CallTransactionBuilder

from . import scoreapi, service, wallet
from .util import ensure_address

METHOD_FMT = r'(?P<address>[a-z_0-9]+)(\.(?P<method>[a-zA-Z0-9_]+))?'
RE_METHOD = re.compile(METHOD_FMT)

def parse_param(input: dict, param: str) -> any:
    tname: str = input['type']
    if tname == 'str':
        return param
    if tname == 'int':
        value = int(param, 0)
        return hex(value)
    if tname == 'bytes':
        if not param.startswith("0x"):
            raise Exception(f'Invalid bytes value={param}')
        bs = bytes.fromhex(param[2:])
        return "0x"+bs.hex()
    if tname == 'Address':
        return ensure_address(param)
    if tname.startswith('[]') or tname == 'struct':
        return json.loads(param)
    raise Exception(f'UnknownType(type={tname})')

def make_params(inputs: list, params: List[str]) -> dict:
    if len(params) > len(inputs):
        raise Exception('Too many parameters')
    idx = 0
    param_data = {}
    for input in inputs:
        name = input['name']
        if len(params) <= idx:
            if 'default' in input:
                idx += 1
                continue
            print(f'More parameter is required next={name}', file=sys.stderr)
            return
        param_data[name] = parse_param(input, params[idx])
    return param_data

@click.command('call')
@click.argument('expr')
@click.argument('param', nargs=-1)
@click.option('--value')
@click.option("--keystore")
@click.option('--raw', '-r', is_flag=True)
def call(expr: str, param: List[str], value: str = 0, keystore: str = None, raw: bool = False):
    obj = RE_METHOD.match(expr)
    if obj is None:
        raise Exception(f'Invalid parameter param={expr}')

    addr = ensure_address(obj.group('address'))

    svc = service.get_instance()
    api = svc.get_score_api(addr)
    if api is None:
        raise Exception(f'No API for {addr}')

    method = obj.group('method')
    if method is None:
        if raw:
            print(json.dumps(api))
        else:
            print(scoreapi.dumps(api))
        return

    methods = list(filter(lambda x: x['type'] == 'function' and method == x['name'], api))

    if len(methods) == 0:
        methods = list(filter(lambda x: x['type'] == 'function' and method in x['name'], api))
        if len(methods) == 0:
            raise Exception(f'No methods found like={method}')
        print(scoreapi.dumps(methods), file=sys.stderr)
        return

    info = methods[0]
    if 'readonly' in info and info['readonly'] == '0x1':
        params = make_params(info['inputs'], param)
        value = svc.call(CallBuilder(to=addr, method=method, params=params).build())
        print(json.dumps(value))
    else:
        w = wallet.get_instance(keystore)
        params = make_params(info['inputs'], param)
        tx = CallTransactionBuilder(from_=w.address, to=addr, method=method, params=params, value=value). build()
        result = svc.estimate_and_send_tx(tx, w)
        print(json.dumps(result))