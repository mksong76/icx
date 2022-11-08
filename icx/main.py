#!/usr/bin/env python3

from os import path
import sys

import click
from icx.cui import Column, RowPrinter

from icx.util import dump_json

from . import (basic, blockinterval, call, preps, rlp, scoreapi, service,
               trace, txscan)
from .config import CONTEXT_CONFIG, Config
from .wallet import asset

CONFIG_NETWORKS='networks'

@click.group()
@click.option('--config', envvar='ICX_CONFIG')
@click.option('--net', '-n', type=click.STRING, envvar='ICX_NET')
@click.option('--url', type=click.STRING, envvar='ICX_RPC_URL')
@click.option('--nid', type=click.STRING, envvar='ICX_RPC_NID')
@click.pass_context
def main(ctx: click.Context, net: str = None, url: str = None, nid: str = None, config: str = None):
    ctx.ensure_object(dict)
    config = path.join(click.get_app_dir('ICX'), 'config.json') if config is None else config
    ctx_config = Config(config)
    ctx.obj[CONTEXT_CONFIG] = ctx_config
    networks = ctx_config.get(CONFIG_NETWORKS)
    if url is not None and nid is not None:
        service.set_default(url, int(nid, 0))
    elif net is not None:
        if net not in networks:
            click.echo(f'Available networks:{",".join(networks.keys())}', file=sys.stderr)
            raise Exception(f'Unknown network name={net}')
        url, nid = tuple(networks[net])
        service.set_default(*networks[net])

@click.command('net', help='Show network information without name, delete network information without URL and NID. Otherwise set network information')
@click.pass_obj
@click.argument('name', type=click.STRING, required=False)
@click.argument('url', type=click.STRING, required=False)
@click.argument('nid', type=click.STRING, required=False)
@click.option('--delete', '-d', type=click.BOOL, is_flag=True, default=False)
def network(obj: dict, name: str = None, url: str = None, nid: str = None, delete: bool = None):
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

main.add_command(scoreapi.get_apis, 'apis')
main.add_command(basic.get_balance, 'balance')
main.add_command(basic.get_block, 'block')
main.add_command(basic.get_tx, 'tx')
main.add_command(basic.get_result, 'result')
main.add_command(basic.get_data, 'data')
main.add_command(basic.get_score, 'score')
main.add_command(basic.get_codes, 'codes')
main.add_command(trace.get_trace, 'trace')
main.add_command(blockinterval.block_interval, 'interval')
main.add_command(txscan.scan, 'txscan')
main.add_command(rlp.convert, 'rlp')
main.add_command(call.call, 'call')
main.add_command(preps.main, 'prep')
main.add_command(asset.main, 'asset')
main.add_command(network, 'net')

if __name__ == '__main__':
    main()
