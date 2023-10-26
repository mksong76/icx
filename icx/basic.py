#!/usr/bin/env python3

import base64
import io
from typing import List

import click

from iconsdk.builder.transaction_builder import DeployTransactionBuilder

from . import service, util, wallet
from .cui import Column, Header, MapPrinter, Row, RowPrinter


@click.command()
@click.argument('addr', type=util.ADDRESS)
@click.option('--full', type=click.BOOL, is_flag=True)
@click.option('--height', type=util.INT)
@click.option('--icx', is_flag=True)
def get_balance(addr: str, full: bool = False, height: int = None, icx: bool = False):
    '''Get balance of the account'''
    svc = service.get_instance()
    balance = svc.get_balance(util.ensure_address(addr), height=height, full_response=full)
    if icx:
        print(util.format_decimals(balance, 3))
    else:
        print(balance)


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
@click.option('--height', type=util.INT)
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
        Column(lambda height, status: status['current']['type'], 7, name="Type"),
        Column(lambda height, status: status['current']['codeHash'], 66, name="Code Hash"),
    ])
    p.print_header()
    for height, status in history:
        p.print_data(height, status)

def get_account(addr: str, svc: service.Service = None) -> List[Row]:
    if svc is None:
        svc = service.get_instance()

    info = { 'address': addr }
    rows = [
        Header(lambda v: 'Basic', 5, '{}'),
        Row(lambda v: v['address'], 42, '{}', 'Address'),
    ]

    info['balance'] = svc.get_balance(addr)
    rows += [
        Row(lambda v: util.format_decimals(v['balance'], 3), 32, '{:>28s} ICX', 'Balance'),
    ]

    if addr.startswith('cx'):
        status = svc.get_score_status(addr)
        info['status'] = status
        audit_txhash = status.get('current', {}).get('auditTxHash', None)
        if audit_txhash is not None:
            audit_tx = svc.get_transaction(audit_txhash)
            status['current']['height'] = str(audit_tx['blockHeight'])
        rows += [
            Header(lambda v: 'SCORE', 20, '{:^}'),
            Row(lambda v: v['status'].get('owner',''), 42, '{:42s}', 'Owner'),
            Row(lambda v: v['status'].get('current',{}).get('type', ''), 10, '{:10s}', 'Type'),
            Row(lambda v: v['status'].get('current',{}).get('height', ''), 16, '{:>16s}', 'Height'),
            Row(lambda v: v['status'].get('current',{}).get('codeHash', ''), 66, '{:66s}', 'Code Hash'),
        ]
        if 'depositInfo' in info['status']:
            rows += [
                Header(lambda v: 'DepositInfo', 20, '{:^}'),
                Row(lambda v: util.format_decimals(v['status']['depositInfo'].get('availableDeposit', '0x0'),3), 16, '{:>12s} ICX', 'Avaialble'),
                Row(lambda v: 'true' if v['status']['depositInfo'].get('useSystemDeposit', '0x0')=='0x1' else 'false', 5, '{:5}', 'Use System Deposit')
            ]
    return info, rows

@click.command('account', help='Show account information')
@click.argument('addr', metavar='<address>', type=util.ADDRESS)
def show_account(addr: str):
    info, rows = get_account(addr)
    rows.append(Header(lambda v: 'END', 3, '{:^}'))
    MapPrinter(rows).print_data(info)

@click.command('deploy', help='Deploy contract')
@click.option('--to', metavar='<to>', type=util.ADDRESS)
@click.option('--value', metavar='<value>', type=util.INT)
@click.option('--type', metavar='<contract type>', type=click.STRING)
@click.argument('score', metavar='<score file>', type=click.STRING)
@click.argument('params', metavar='<key=value>', type=click.STRING, nargs=-1)
def deploy_contract(score: str, params: list[str], *, type: str = None, to: str = None, value: int = None):
    '''
    Deploy or update the contract
    '''
    with open(score, 'rb') as fd:
        data = []
        while True:
            bs = fd.read()
            if not bs:
                break
            data.append(bs.hex())
        content = '0x'+(''.join(data))

    if type is None:
        if score.lower().endswith('.jar') :
            type = 'application/java'
        else:
            type = 'application/zip'

    mw = wallet.get_instance()
    svc = service.get_instance()

    if len(params) > 0:
        parameters = {}
        for param in params:
            idx = param.index('=')
            if idx<0:
                raise Exception('Invalid parameter (ex: <key>=<value>)')
            key = param[0:idx]
            value = param[idx+1:]
            parameters[key] = value if value != 'null' else None
    else:
        parameters = None

    builder = DeployTransactionBuilder(
        version=3,
        nid=svc.nid,
        from_=mw.address,
        content_type=type,
        content=content,
        params=parameters,
        to=to if to is not None else 'cx0000000000000000000000000000000000000000'
    )
    if value is not None:
        builder = builder.value(value)

    tx = builder.build()
    result = svc.estimate_and_send_tx(tx, mw)
    util.dump_json(result)