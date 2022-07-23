#!/usr/bin/env python3

from os import path
import click

from . import scoreapi, basic, preps, call, blockinterval, rlp, trace, txscan
from .config import CONTEXT_CONFIG, Config
from .wallet import asset

@click.group()
@click.option('--config', envvar='ICX_CONFIG')
@click.pass_context
def main(ctx: click.Context, config: str = None):
    config = path.join(click.get_app_dir('ICX'), 'config.json') if config is None else config
    ctx.obj = {
        CONTEXT_CONFIG: Config(config)
    }
    pass

main.add_command(scoreapi.get_apis, 'apis')
main.add_command(basic.get_balance, 'balance')
main.add_command(basic.get_block, 'block')
main.add_command(basic.get_tx, 'tx')
main.add_command(basic.get_result, 'result')
main.add_command(basic.get_data, 'data')
main.add_command(trace.get_trace, 'trace')
main.add_command(blockinterval.block_interval, 'interval')
main.add_command(txscan.scan, 'txscan')
main.add_command(rlp.convert, 'rlp')
main.add_command(call.call, 'call')
main.add_command(preps.main, 'prep')
main.add_command(asset.main, 'asset')

if __name__ == '__main__':
    main()
