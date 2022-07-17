#!/usr/bin/env python3

import base64
import io
import re
from typing import List

import click

from . import service, util


@click.command()
@click.argument('addr')
@click.option('--full', type=click.BOOL, is_flag=True)
@click.option('--height', type=click.INT)
def get_balance(addr: str, full: bool = False, height: int = None):
    svc = service.get_instance()
    print(svc.get_balance(util.ensure_address(addr), height=height, full_response=full))


@click.command()
@click.argument('ids', nargs=-1)
@click.option('--full', is_flag=True)
def get_block(ids: List[str], full: bool = False):
    svc = service.get_instance()
    if len(ids) == 0:
        ids = [ 'latest']
    for id in ids:
        blk = svc.get_block(util.ensure_block(id))
        util.dump_json(blk)

@click.command()
@click.argument('ids', nargs=-1)
@click.option('--full', is_flag=True)
def get_tx(ids: List[str], full: bool = False):
    svc = service.get_instance()
    for id in ids:
        tx = svc.get_transaction(id, full_response=full)
        util.dump_json(tx)

@click.command()
@click.argument('ids', nargs=-1)
@click.option('--full', is_flag=True)
def get_result(ids: List[str], full: bool = False):
    svc = service.get_instance()
    for id in ids:
        result = svc.get_transaction_result(id, full_response=full)
        util.dump_json(result)

@click.command(help="Get data of the hash")
@click.argument('hash', nargs=-1)
@click.option('--binary', '-b', is_flag=True)
@click.option('--out', '-o', type=click.File('wb'), default='-')
def get_data(hash: List[str], binary: bool, out: io.RawIOBase):
    svc = service.get_instance()
    for id in hash:
        data = svc.get_data_by_hash(util.ensure_hash(id))
        if binary:
            out.write(base64.decodestring(data.encode()))
        else:
            util.dump_json(data, fp=io.TextIOWrapper(out))
