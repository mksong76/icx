#!/usr/bin/env python3

import json
from os import path
import sys
from typing import List, Union
import click

from ..cui import Column, RowPrinter, Row, MapPrinter, Header

from .. import service, util
from ..network import CONTEXT_NETWORK
from ..config import Config, CONTEXT_CONFIG
from iconsdk.builder.call_builder import CallBuilder

GRADE_TO_TYPE = {
    "0x0": "Main",
    "0x1": "Sub",
    "0x2": "Cand",
}

STATE_TO_STR = {
    "0x0": "None",
    "0x1": "Ready",
    "0x2": "Success",
    "0x3": "Failure",
}

PREPS_JSON="~/.preps.{network}.json"
P2P="p2p"
RPC="rpc"

CONTEXT_PREP_SEEDS='prep.seeds'
CONTEXT_PREP_STORE='prep.store'
CONFIG_PREP_SEEDS='prep.seeds'

def p2p_to_rpc(server: str) -> str:
    ip, port = tuple(server.split(':'))
    port = int(port, 0)+(9000-7100)
    return f'{ip}:{port}'

def server_to_ip(server: str) -> str:
    ip, _ = tuple(server.split(':'))
    return ip

def icon_getMainPReps() -> any:
    svc = service.get_instance()
    call = CallBuilder(to=util.CHAIN_SCORE, method='getMainPReps').build()
    return svc.call(call)

def get_service_with_rpc(server: str=None) -> service.Service:
    if server is not None:
        return service.get_instance(f'http://{server}/api/v3')
    else:
        return service.get_instance()

def icon_getPRep(addr: str, server: str=None, start: int=None, end: int=None, height: int=None) -> any:
    svc = get_service_with_rpc(server)
    params = { 'address':addr }
    if start is not None:
        params['startRanking'] = f'0x{start:x}'
    if end is not None:
        params['endRanking'] = f'0x{end:x}'
    call = CallBuilder(to=util.CHAIN_SCORE, method='getPRep', params=params, height=height).build()
    return svc.call(call)

def icon_getPReps(server: str = None, height: int = None) -> any:
    svc = get_service_with_rpc(server)
    call = CallBuilder(to=util.CHAIN_SCORE, method='getPReps', height=height).build()
    return svc.call(call)

def icon_getPRepStats(server: str = None, height: int = None) -> any:
    svc = get_service_with_rpc(server)
    call = CallBuilder(to=util.CHAIN_SCORE, method='getPRepStats', height=height).build()
    return svc.call(call)

def node_inspect(server: str) -> any:
    return util.rest_get(f'http://{server}/admin/chain/icon_dex?informal=true')

def node_get_chain(server: str, timeout: float = 1.0) -> any:
    return util.rest_get(f'http://{server}/admin/chain', timeout=timeout)[0]

def node_get_version(server: str, timeout: float = 1.0) -> any:
    si = util.rest_get(f'http://{server}/admin/system', timeout=timeout)
    return si['buildVersion']

@click.command('seeds')
@click.pass_obj
@click.argument('network', type=click.STRING, required=False)
@click.argument('server', nargs=-1)
@click.option('--delete', '-d', type=click.BOOL, is_flag=True, default=False)
def set_seed(obj: dict, network: str = None, delete: bool = None, server: List[str] = None):
    '''
    Manage seed server configurations for networks
    '''
    config: Config = obj[CONTEXT_CONFIG]
    prep_seeds: dict = config[CONFIG_PREP_SEEDS]

    if network is None:
        if len(prep_seeds) == 0:
            click.echo(f'No seed servers are registered')
            return
        columns = [
            Column(lambda name, info: name, 10, name='Name'),
            Column(lambda name, info: ",".join(info), 60, name='Seed servers'),
        ]
        printer = RowPrinter(columns)
        printer.print_separater()
        printer.print_header()
        printer.print_separater()
        for name, value in prep_seeds.items():
            printer.print_data(name, value)
            printer.print_separater()
        return

    if len(server) == 0:
        if network in prep_seeds:
            if delete:
                del prep_seeds[network]
                config[CONFIG_PREP_SEEDS] = prep_seeds
                click.echo(f'Seed servers for [{network}] is deleted')
            else:
                seeds: List[str] = prep_seeds[network]
                click.echo(f'Seed servers for [{network}] : {" ".join(seeds)}')
        else:
            click.secho(f'No seed servers for [{network}]', color='red', file=sys.stderr)
        return

    prep_seeds[network] = server
    config[CONFIG_PREP_SEEDS] = prep_seeds
    click.echo(f'Seed servers for [{network}] are set')

def load_prep_store(file: str):
    with open(file, "r") as fd:
        return json.load(fd)

def search_prep(prep_info:dict, key: str) -> any:
    preps = []
    for addr, prep in prep_info.items():
        if addr == key:
            return prep
        elif prep.get('address', '') == key:
            return prep
        elif key in prep.get('p2p', ''):
            preps.append(prep)
        elif key.lower() in prep.get('name', '').lower():
            preps.append(prep)
    if len(preps) > 0:
        return preps[0]
    return None

def find_rpc(prep_info:dict) -> Union[str,None]:
    for _, prep in prep_info.items():
        if RPC in prep:
            return prep[RPC]
    return None

@click.command('get')
@click.pass_obj
@click.argument('key')
@click.option('--raw', is_flag=True)
@click.option('--height', type=str, default=None)
def get_prep(obj: dict, key: str, raw: bool, height: str):
    '''
    Get PRep information
    '''
    prep_info = load_prep_store(obj[CONTEXT_PREP_STORE])
    rpc = find_rpc(prep_info)
    preps = icon_getPReps(rpc, height=height)['preps']

    if height is not None:
        height = int(height, 0)

    prep_index = None

    try :
        prep_index = int(key, 0)-1
    except:
        pass

    if prep_index is None:
        prep = search_prep(prep_info, key)
        prep_addr = None
        if 'address' in prep:
            prep_addr = prep['address']

        for idx in range(len(preps)):
            if preps[idx]['address'] == prep_addr:
                prep_index = idx
    else:
        while prep_index >= len(preps):
            preps += icon_getPReps(rpc, len(preps), height=height)['preps']
        prep_addr = preps[prep_index]['address']

    if prep_index is None:
        raise Exception(f'fail to find PRep key={key:q}')

    prep_info:dict = icon_getPRep(prep_addr, rpc, height=height)
    prep_stats = icon_getPRepStats(rpc, height=height)['preps']
    prep_info['stat'] = prep_stats[prep_index]

    if raw :
        util.dump_json(prep_info)
    else:
        MapPrinter([
            Row(lambda obj: obj.get('address'), 42, '{}', 'Address'),
            Row(lambda obj: obj.get('name'), 20, '{}', 'Name'),
            Row(lambda obj: obj.get('city'), 10, '{}', 'City'),
            Row(lambda obj: obj.get('country'), 3, '{}', 'Country'),
            Row(lambda obj: obj.get('email'), 40, '{}', 'Email'),
            Row(lambda obj: obj.get('details'), 60, '{}', 'Details'),
            Row(lambda obj: obj.get('website'), 60, '{}', 'WebSite'),
            Row(lambda obj: GRADE_TO_TYPE[obj.get('grade')], 4, '{}', 'Grade'),
            Row(lambda obj: obj.get('nodeAddress'), 42, '{}', 'Node'),
            Row(lambda obj: obj.get('p2pEndpoint'), 40, '{}', 'P2P'),
            Row(lambda obj: obj.get('penalty'), 3, '{}', 'Penalty'),
            Row(lambda obj: obj.get('status'), 3, '{}', 'Status'),
            Row(lambda obj: util.format_decimals(obj.get('irep')), 40, '{:>40}', 'iRep'),
            Row(lambda obj: int(obj.get('irepUpdateBlockHeight'),0), 40, '{:>40,}', 'iRep-Height'),
            Row(lambda obj: util.format_decimals(obj.get('bonded')), 40, '{:>40}', 'Bonded'),
            Row(lambda obj: util.format_decimals(obj.get('delegated')), 40, '{:>40}', 'Delegated'),
            Row(lambda obj: util.format_decimals(obj.get('power')), 40, '{:>40}', 'Power'),
            Row(lambda obj: int(obj.get('totalBlocks'),0), 40, '{:>40,}', 'Total Blocks'),
            Row(lambda obj: int(obj.get('validatedBlocks'),0), 40, '{:>40,}', 'Validated Blocks'),
            Header(lambda obj: "Statics", 40, '{}'),
            Row(lambda obj: STATE_TO_STR[obj['stat']['lastState']], 20, '{:>20}', 'Last State'),
            Row(lambda obj: int(obj['stat']['lastHeight'], 0), 32, '({0:#x}) {0:>,}', 'Last Height'),
            Row(lambda obj: int(obj['stat']['realFailCont'], 0), 20, '{:>20,}', 'Continuous Failure'),
            Row(lambda obj: int(obj['stat']['realFail'], 0), 20, '{:>20,}', 'Validation Failure'),
            Row(lambda obj: int(obj['stat']['realTotal'], 0), 20, '{:>20,}', 'Validation Oppitunity'),
        ]).print_header().print_data(prep_info).print_separater()

def handlePReps(obj: dict, store: str):
    # ensure CONTEXT_PREP_STORE is set
    if store is None:
        if CONTEXT_NETWORK in obj:
            network = obj[CONTEXT_NETWORK]
        else:
            network = 'default'
        store = PREPS_JSON.format(network=network)
    obj[CONTEXT_PREP_STORE] = path.expanduser(store)

    # if network is specified, then SEEDs also need to be set
    if CONTEXT_NETWORK in obj:
        network: str = obj[CONTEXT_NETWORK]
        config: Config = obj[CONTEXT_CONFIG]
        prep_seeds: dict = config[CONFIG_PREP_SEEDS]

        if network in prep_seeds:
            obj[CONTEXT_PREP_SEEDS] = prep_seeds[network]