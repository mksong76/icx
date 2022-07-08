#!/usr/bin/env python3

import click
from . import util, service

@click.command()
@click.argument('addr')
@click.option('--full', type=click.BOOL, is_flag=True)
@click.option('--height', type=click.INT)
def get_balance(addr: str, full: bool = False, height: int = None):
    svc = service.get_instance()
    print(svc.get_balance(util.ensure_address(addr), height=height, full_response=full))

