#!/usr/bin/env python3

from os import path
import sys
from typing import List
import click

from ..cui import Column, RowPrinter

from .. import service, util
from ..network import CONTEXT_NETWORK
from ..config import Config, CONTEXT_CONFIG
from iconsdk.builder.call_builder import CallBuilder

GRADE_TO_TYPE = {
    "0x0": "Main",
    "0x1": "Sub",
    "0x2": "Cand",
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

def icon_getPReps(server: str = None) -> any:
    if server is not None:
        svc = service.get_instance(f'http://{server}/api/v3')
    else:
        svc = service.get_instance()
    call = CallBuilder(to=util.CHAIN_SCORE, method='getPReps').build()
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
        else:
            raise Exception(f'No valid SEEDs for network {network}')
