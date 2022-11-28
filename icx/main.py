#!/usr/bin/env python3

import sys
from datetime import datetime, timedelta, timezone
from os import path
from typing import List

import click

from icx.cui import Column, RowPrinter
from icx.util import datetime_from_ts, dump_json, format_dt

from . import (basic, blockinterval, call, preps, rlp, scoreapi, service,
               trace, txscan, network, wallet)
from .config import CONTEXT_CONFIG, Config
from .wallet import asset

CONFIG_NETWORKS='networks'

@click.group()
@click.option('--config', envvar='ICX_CONFIG')
@click.option('--net', '-n', type=click.STRING, envvar='ICX_NET')
@click.option('--url', type=click.STRING, envvar='ICX_RPC_URL')
@click.option('--nid', type=click.STRING, envvar='ICX_RPC_NID')
@click.option('--ks', type=click.STRING, envvar='ICX_KEYSTORE')
@click.pass_context
def main(ctx: click.Context, net: str = None, url: str = None, nid: str = None, config: str = None, ks: str = None):
    ctx.ensure_object(dict)
    config = path.join(click.get_app_dir('ICX'), 'config.json') if config is None else config
    ctx_config = Config(config)
    ctx.obj[CONTEXT_CONFIG] = ctx_config
    networks = ctx_config.get(CONFIG_NETWORKS)
    if url is not None and nid is not None:
        service.set_default(url, int(nid, 0))
    elif net is not None:
        network.handleFlag(ctx_config, net)
    if ks is not None:
        wallet.handleFlag(ctx_config, ks)

@click.command('time')
@click.argument('timestamp', type=click.STRING, nargs=-1)
@click.option('--utc', is_flag=True, default=False)
def time_convert(timestamp: List[str], utc: bool = False):
    dt_old = None
    for value in timestamp:
        dt = datetime_from_ts(value)
        if not utc:
            dt = dt.astimezone()
        if dt_old is None:
            print(format_dt(dt))
        else:
            dt_diff = dt-dt_old
            if dt_diff < timedelta(0):
                print(format_dt(dt), f'( -{-dt_diff} )')
            else:
                print(format_dt(dt), f'( +{dt_diff} )')
        dt_old = dt


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
main.add_command(network.main, 'net')
main.add_command(wallet.main, 'ks')
main.add_command(time_convert, 'time')

if __name__ == '__main__':
    main()
