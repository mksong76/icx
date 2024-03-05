#!/usr/bin/env python3
from typing import List
import click
import sys

from . import service
from .config import CONTEXT_CONFIG, Config
from .cui import Column, RowPrinter

CONFIG_NETWORKS='networks'
CONTEXT_NETWORK='network.name'
CONFIG_NODE_SEEDS='node.seeds'
CONTEXT_NODE_SEED='node.seed'

def handleFlag(obj: dict, net: str):
    config = obj[CONTEXT_CONFIG]
    networks = config.get(CONFIG_NETWORKS)
    if net not in networks:
        click.echo(f'Available networks:{",".join(networks.keys())}', file=sys.stderr)
        raise Exception(f'Unknown network name={net}')
    obj[CONTEXT_NETWORK] = net
    service.set_default(*networks[net])

    seeds = config.get(CONFIG_NODE_SEEDS)
    if net in seeds:
        obj[CONTEXT_NODE_SEED] = seeds[net]

@click.command('net')
@click.pass_obj
@click.argument('name', type=click.STRING, required=False)
@click.argument('url', type=click.STRING, required=False)
@click.argument('nid', type=click.STRING, required=False)
@click.option('--delete', '-d', type=click.BOOL, is_flag=True, default=False, help='Delete network')
@click.option('--rename', '-r', metavar='<OLD>', type=click.STRING, help='Rename network')
def main(obj: dict, name: str = None, url: str = None, nid: str = None, delete: bool = None, rename: str = None):
    '''
    Manage network information

    \b
    Show network information without name,
    with <NAME>, it shows the network information (may delete or rename).
    with <NAME> <URL> <NID>, it saves network information.
    '''
    config: Config = obj[CONTEXT_CONFIG]
    networks: dict = config[CONFIG_NETWORKS]

    if name is None:
        columns = [
            Column(lambda name, info: name, 10, name='Name'),
            Column(lambda name, info: info[0], 60, name='URL'),
            Column(lambda name, info: f'{info[1]:#x}', 20, name='NID'),
        ]
        printer = RowPrinter(columns)
        printer.print_separater()
        printer.print_header()
        printer.print_separater()
        for name, value in networks.items():
            printer.print_data(name, value)
            printer.print_separater()
        return
    if url is None:
        if rename is not None:
            if rename not in networks:
                click.secho(f'No network named{rename}', color='red', file=sys.stderr)
                return
            if name in networks:
                click.secho(f'Network {name} is already exists', color='red', file=sys.stderr)
                return
            networks[name] = networks[rename]
            del networks[rename]
            config[CONFIG_NETWORKS] = networks
            click.echo(f'Network {rename} renamed to {name}')
            return
        if name in networks:
            if delete:
                del networks[name]
                config[CONFIG_NETWORKS] = networks
                click.echo(f'Network {name} is deleted')
            else:
                url, nid = tuple(networks[name])
                click.echo(f'Network {name} URL={url} NID={nid:#x}')
        else:
            click.secho(f'No network named {name}', color='red', file=sys.stderr)
        return

    if nid is None:
        click.secho(f'NID is required to set network information', color='red', file=sys.stderr)
        return

    nid = int(nid, 0)
    networks[name] = (url, nid)
    config[CONFIG_NETWORKS] = networks

    click.echo(f'Network {name} is set as URL={url} NID=0x{nid:x}')

@click.command('seed')
@click.pass_obj
@click.argument('network', type=click.STRING, required=False)
@click.argument('server', nargs=-1)
@click.option('--delete', '-d', type=click.BOOL, is_flag=True, default=False)
def set_seed(obj: dict, network: str = None, delete: bool = None, server: List[str] = None):
    '''
    Manage seed server configurations for networks
    '''
    config: Config = obj[CONTEXT_CONFIG]
    prep_seeds: dict = config[CONFIG_NODE_SEEDS]

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
                config[CONFIG_NODE_SEEDS] = prep_seeds
                click.echo(f'Seed servers for [{network}] is deleted')
            else:
                seeds: List[str] = prep_seeds[network]
                click.echo(f'Seed servers for [{network}] : {" ".join(seeds)}')
        else:
            click.secho(f'No seed servers for [{network}]', color='red', file=sys.stderr)
        return

    prep_seeds[network] = server
    config[CONFIG_NODE_SEEDS] = prep_seeds
    click.echo(f'Seed servers for [{network}] are set')