#!/usr/bin/env python3

import click

from icx.wallet import asset

from . import scoreapi, basic, preps, call

@click.group()
def main():
    pass

main.add_command(scoreapi.get_apis, 'apis')
main.add_command(basic.get_balance, 'balance')
main.add_command(basic.get_trace, 'trace')
main.add_command(basic.get_block, 'block')
main.add_command(basic.get_tx, 'tx')
main.add_command(basic.get_result, 'result')
main.add_command(call.call, 'call')
main.add_command(preps.main, 'prep')
main.add_command(asset.main, 'asset')

if __name__ == '__main__':
    main()
