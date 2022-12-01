#!/usr/bin/env python3
import click
import sys

from . import service
from .config import CONTEXT_CONFIG, Config
from .cui import Column, RowPrinter

CONFIG_NETWORKS='networks'
CONTEXT_NETWORK='network.name'

def handleFlag(obj: dict, net: str):
    config = obj[CONTEXT_CONFIG]
    networks = config.get(CONFIG_NETWORKS)
    if net not in networks:
        click.echo(f'Available networks:{",".join(networks.keys())}', file=sys.stderr)
        raise Exception(f'Unknown network name={net}')
    obj[CONTEXT_NETWORK] = net
    service.set_default(*networks[net])

@click.command('net', help='Show network information without name, delete network information without URL and NID. Otherwise set network information')
@click.pass_obj
@click.argument('name', type=click.STRING, required=False)
@click.argument('url', type=click.STRING, required=False)
@click.argument('nid', type=click.STRING, required=False)
@click.option('--delete', '-d', type=click.BOOL, is_flag=True, default=False)
def main(obj: dict, name: str = None, url: str = None, nid: str = None, delete: bool = None):
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
