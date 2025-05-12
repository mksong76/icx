#!/usr/bin/env python3

from datetime import timedelta
from os import path
from typing import List

import click

from . import (basic, blockinterval, blockvotes, btp, call, icon, inspect,
               network, rlp, scoreapi, service, trace, txscan, verifytx,
               wallet)
from .config import CONTEXT_CONFIG, Config
from .market import exchange
from .util import datetime_from_ts, format_dt

CONFIG_NETWORKS='networks'

@click.group()
@click.option('--config', envvar='ICX_CONFIG',
             metavar='<config.json>',
             help='Configuration JSON file')
@click.option('--net', '-n', envvar='ICX_NET',
             metavar='<name>',
             help='Name of pre-defined network')
@click.option('--url', envvar='ICX_RPC_URL',
             metavar='<rpc url>',
             help='RPC URL for the network')
@click.option('--nid', envvar='ICX_RPC_NID',
             metavar='<nid>',
             help='Network ID for the network')
@click.option('--ks', envvar='ICX_KEYSTORE',
             metavar='<name|keystore.json>',
             help='Name of the keystore or keystore file')
@click.option("--auth", "-a", envvar="ICX_EXCHANGE_CONFIG",
            metavar="<exchanges.json>",
            help="Authentication credentials for the exchanges",
)
@click.pass_context
def main(ctx: click.Context, net: str = None, url: str = None, nid: str = None, config: str = None, ks: str = None, auth: str = None):
    ctx.ensure_object(dict)
    config = path.join(click.get_app_dir('ICX'), 'config.json') if config is None else config
    ctx_config = Config(config)
    ctx.obj[CONTEXT_CONFIG] = ctx_config
    if url is not None and nid is not None:
        service.set_default(url, int(nid, 0))
    elif net is not None:
        network.handleFlag(ctx.obj, net)
    if ks is not None:
        wallet.handleFlag(ctx.obj, ks)
    if auth is not None:
        exchange.handleFlag(ctx.obj, auth)

@click.command('time')
@click.argument('timestamp', type=click.STRING, nargs=-1)
@click.option('--utc', is_flag=True, default=False)
def time_convert(timestamp: List[str], utc: bool = False):
    '''
    Convert microsecond to datetime
    '''
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
main.add_command(basic.show_account, 'account')
main.add_command(basic.deploy_contract, 'deploy')
main.add_command(basic.transfer, 'transfer')
main.add_command(basic.block_near, 'block-near')
main.add_command(trace.get_trace, 'trace')
main.add_command(btp.main, 'btp')
main.add_command(blockinterval.block_interval, 'interval')
main.add_command(txscan.scan, 'txscan')
main.add_command(rlp.rlp_endecode, 'rlp')
main.add_command(rlp.hex_endecode, 'hex')
main.add_command(call.call, 'call')
main.add_command(network.main, 'net')
main.add_command(network.set_seed, 'seed')
main.add_command(wallet.main, 'ks')
main.add_command(wallet.bookmark_main, 'bk')
main.add_command(time_convert, 'time')
main.add_command(blockvotes.check_votes, 'votes')
main.add_command(verifytx.verify_tx, 'verifytx')
main.add_command(blockvotes.show_validators, 'validators')
main.add_command(inspect.show_inspection, 'inspect')
main.add_command(inspect.show_netinspection, 'netinspect')

main.add_command(icon.main)
main.add_command(icon.asset_group)
main.add_command(icon.preps)
main.add_command(icon.proposal_group)
main.add_command(exchange.main)

if __name__ == '__main__':
    main()
