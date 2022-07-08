#!/usr/bin/env python3

import click

from icx.wallet import asset

from . import util
from . import scoreapi
from . import basic 
from . import preps

@click.group()
def main():
    pass

main.add_command(scoreapi.get_apis, 'apis')
main.add_command(basic.get_balance, 'balance')
main.add_command(preps.main, 'prep')
main.add_command(asset.main, 'asset')

if __name__ == '__main__':
    main()
