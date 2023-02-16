#!/usr/bin/env python3

import base64
import io
from typing import List

import click

from . import service, util
from .cui import Column, RowPrinter


@click.command()
@click.argument('addr', type=util.ADDRESS)
@click.option('--full', type=click.BOOL, is_flag=True)
@click.option('--height', type=util.HEXINT)
def get_balance(addr: str, full: bool = False, height: int = None):
    '''Get balance of the account'''
    svc = service.get_instance()
    print(svc.get_balance(util.ensure_address(addr), height=height, full_response=full))


@click.command()
@click.argument('ids', nargs=-1)
@click.option('--full', is_flag=True)
def get_block(ids: List[str], full: bool = False):
    '''Get the block information'''
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
    '''Get the transaction information'''
    svc = service.get_instance()
    for id in ids:
        tx = svc.get_transaction(id, full_response=full)
        util.dump_json(tx)

@click.command()
@click.argument('ids', nargs=-1)
@click.option('--full', is_flag=True)
def get_result(ids: List[str], full: bool = False):
    '''Get the transaction result'''
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

@click.command(help="Get SCORE status")
@click.argument("scores", type=util.SCORE, nargs=-1)
@click.option('--full', is_flag=True)
@click.option('--height', type=util.HEXINT)
def get_score(scores: List[str], height: int = None, full: bool = False):
    svc = service.get_instance()
    for score in scores:
        result = svc.get_score_status(score, height=height, full_response=full)
        util.dump_json(result)

@click.command(help="Get SCORE History")
@click.argument("score", type=util.SCORE, nargs=1)
def get_codes(score: str):
    svc = service.get_instance()
    height = None
    history = []
    while True:
        try:
            status = svc.get_score_status(score, height=height)
        except:
            break
        if 'current' not in status:
            break
        tx_hash = status['current']['auditTxHash']
        tx = svc.get_transaction(tx_hash)
        height = tx['blockHeight']
        history.insert(0, (height, status))

    if len(history) == 0:
        return

    p = RowPrinter([
        Column(lambda height, status: height, 10, format='{:>10}', name="Height"),
        Column(lambda height, status: status['current']['deployTxHash'], 66, name="Deploy TX Hash"),
        Column(lambda height, status: status['current']['type'], 7, name="Type"),
        Column(lambda height, status: status['current']['codeHash'], 66, name="Code Hash"),
    ])
    p.print_header()
    for height, status in history:
        p.print_data(height, status)
