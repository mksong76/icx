#!/usr/bin/env python3


import json
import re
import sys
from typing import List, Tuple

import click

from iconsdk.builder.call_builder import CallBuilder
from iconsdk.builder.transaction_builder import CallTransactionBuilder
from iconsdk.icon_service import  SignedTransaction
from iconsdk.monitor import EventMonitorSpec, EventFilter

from . import scoreapi, service, wallet
from .util import INT, DecimalType, ensure_address, dump_json, ensure_score

METHOD_FMT = r'(?P<address>[a-z_0-9]+)(\.(?P<method>[a-zA-Z0-9_]+))?'
RE_METHOD = re.compile(METHOD_FMT)
TC_CLEAR = '\033[K'

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

def parse_event(input: dict, param: str) -> any:
    if param == 'null':
        return None
    else:
        return parse_param(input, param)

def make_eventfilter(addr: str, info: dict, params: List[str]) -> EventFilter:
    inputs: List[dict] = info['inputs']
    if len(params) > len(inputs):
        raise Exception('Too many parameters')
    idx = 0
    indexed = 0
    args = []
    types = []
    for input in inputs:
        if idx<len(params):
            value = parse_event(input, params[idx])
            args.append(value)
            if int(input.get('indexed', '0x0'), 0):
                indexed += 1
        types.append(input['type'])
        idx += 1
    return EventFilter(f'{info["name"]}({",".join(types)})', addr, indexed, *args)

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
@click.option('--value', type=DecimalType('icx', 18), default=0, help='Value to transfer')
@click.option('--step_limit', '-s', type=INT, help="Step limit")
@click.option('--height', '-h', type=INT, default=None, help="Block height for query")
@click.option('--raw', '-r', is_flag=True)
def call(expr: str, param: List[str], value: int = 0, raw: bool = False, step_limit: int = None, height: int = None):
    '''
    Call method of the contract
    '''
    obj = RE_METHOD.match(expr)
    if obj is None:
        raise Exception(f'Invalid parameter param={expr}')

    addr = ensure_score(obj.group('address'))

    svc = service.get_instance()

    if height is not None and height < 0:
        blk = svc.get_block('latest')
        height += blk['height']
        if height < 0:
            raise Exception(f'Invalid block height height={height}')

    api = svc.get_score_api(addr, height=height)
    if api is None:
        raise Exception(f'No API for {addr}')

    method = obj.group('method')
    if method is None:
        click.echo(scoreapi.dumps(api))
        return

    methods = list(filter(lambda x: x['type'] in ['function','eventlog'] and method == x['name'], api))

    if len(methods) == 0 and method == 'events':
        if height is None:
            blk = svc.get_block('latest')
            height = blk['height']+1
        event_filter = make_eventfilter(addr, None, None)
        spec = EventMonitorSpec(height, event_filter, True, progress_interval=10)
        monitor = svc.monitor(spec)
        print("Waiting for events", file=sys.stderr)
        while True:
            obj = monitor.read()
            if 'progress' in obj:
                print(f'{TC_CLEAR}> Block height={obj["progress"]}', end='\r', flush=True, file=sys.stderr)
                continue
            else:
                print(f'{TC_CLEAR}', end='', flush=True, file=sys.stderr)
            dump_json(obj, flush=True)
    elif len(methods) == 0:
        methods = list(filter(lambda x: x['type'] in ['function','eventlog'] and method in x['name'], api))
        if len(methods) == 0:
            raise Exception(f'No methods found like={method}')
        click.echo(scoreapi.dumps(methods), file=sys.stderr)
        return

    info = methods[0]
    if 'readonly' in info and info['readonly'] == '0x1':
        params = make_params(info['inputs'], param)
        value = svc.call(CallBuilder(to=addr, method=method, params=params, height=height).build())
        if raw:
            dump_json(value)
        else:
            print(parse_output(info['outputs'], value))
    elif info['type'] == 'function':
        w = wallet.get_instance()
        params = make_params(info['inputs'], param)
        tx = CallTransactionBuilder(from_=w.address, to=addr, method=method, params=params, value=value, nid=svc.nid).build()
        if step_limit != None:
            signed_tx = SignedTransaction(tx, w, step_limit)
            result = svc.send_transaction_and_pull(signed_tx)
        else:
            result = svc.estimate_and_send_tx(tx, w)
        dump_json(result)
    else:
        if height is None:
            blk = svc.get_block('latest')
            height = blk['height']+1
        event_filter = make_eventfilter(addr, info, param)
        spec = EventMonitorSpec(height, event_filter, True)
        monitor = svc.monitor(spec)
        print("Waiting for events", file=sys.stderr)
        while True:
            obj = monitor.read()
            dump_json(obj, flush=True)