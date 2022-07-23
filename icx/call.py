#!/usr/bin/env python3


import json
import re
import sys
from typing import List

import click

from iconsdk.builder.call_builder import CallBuilder
from iconsdk.builder.transaction_builder import CallTransactionBuilder
from iconsdk.icon_service import  SignedTransaction

from . import scoreapi, service, wallet
from .util import ensure_address, dump_json

METHOD_FMT = r'(?P<address>[a-z_0-9]+)(\.(?P<method>[a-zA-Z0-9_]+))?'
RE_METHOD = re.compile(METHOD_FMT)

def parse_param(input: dict, param: str) -> any:
    tname: str = input['type']
    if tname == 'str':
        return param
    if tname == 'int':
        value = int(param, 0)
        return hex(value)
    if tname == 'bool':
        if param.lower() in ['true', 'false']:
            return hex(param.lower() == 'true')
        else:
            return hex(int(param, 0))
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
            raise Exception(f'More Parameter is required next={name}')
        param_data[name] = parse_param(input, params[idx])
        idx += 1
    return param_data

def parse_output(outputs: list, output: any) -> any:
    tname = outputs[0]['type']
    if tname == 'int':
        return int(output, 0)
    elif tname == 'bool':
        return bool(int(output, 0))
    elif tname in ['str', 'Address', 'bytes']:
        return output
    else:
        return json.dumps(output, indent=2)

@click.command('call')
@click.argument('expr')
@click.argument('param', nargs=-1)
@click.option('--value')
@click.option("--keystore")
@click.option('--step_limit', '-s', help="Step limit")
@click.option('--height', '-h', help="Block height for query")
@click.option('--raw', '-r', is_flag=True)
def call(expr: str, param: List[str], value: str = 0, keystore: str = None, raw: bool = False, step_limit: str = None, height: str = None):
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
        if height is not None:
            height = int(height, 0)
        value = svc.call(CallBuilder(to=addr, method=method, params=params, height=height).build())
        if raw:
            dump_json(value)
        else:
            print(parse_output(info['outputs'], value))
    else:
        w = wallet.get_instance(keystore)
        params = make_params(info['inputs'], param)
        tx = CallTransactionBuilder(from_=w.address, to=addr, method=method, params=params, value=value, nid=svc.nid).build()
        if step_limit != None:
            signed_tx = SignedTransaction(tx, w, int(step_limit, 0))
            result = svc.send_transaction_and_pull(signed_tx)
        else:
            result = svc.estimate_and_send_tx(tx, w)
        dump_json(result)