#!/usr/bin/env python3

import base64
import io
import sys
from datetime import datetime
from typing import List, Union

import click
from iconsdk.builder.transaction_builder import (DeployTransactionBuilder,
                                                 TransactionBuilder)
from iconsdk.icon_service import SignedTransaction
from iconsdk.wallet.wallet import Wallet

from . import service, util, wallet, log
from .cui import Column, Header, MapPrinter, Row, RowPrinter


@click.command()
@click.argument('addr', type=wallet.ADDRESS)
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
        blk = svc.get_block(util.ensure_block(id), full_response=full)
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
        log.tx_result('Result', result, raw=full)

@click.command(help="Get data of the hash")
@click.argument('hash', nargs=-1)
@click.option('--binary', '-b', is_flag=True)
@click.option('--out', '-o', type=click.File('wb'), default='-')
def get_data(hash: List[str], binary: bool, out: io.RawIOBase):
    svc = service.get_instance()
    for id in hash:
        data = svc.get_data_by_hash(util.ensure_hash(id))
        if binary:
            out.write(base64.decodebytes(data.encode()))
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

    rows = [
        Header('Basic', 5),
        Row(addr, 42, '{}', 'Address'),
    ]

    balance = svc.get_balance(addr)
    rows += [
        Row(lambda v: util.format_decimals(balance, 3), 32, '{:>28s} ICX', 'Balance'),
    ]

    if addr.startswith('cx'):
        status = svc.get_score_status(addr)
        audit_txhash = status.get('current', {}).get('auditTxHash', None)
        if audit_txhash is not None:
            audit_tx = svc.get_transaction(audit_txhash)
            status['current']['height'] = str(audit_tx['blockHeight'])
        rows += [
            Header('SCORE', 20),
            Row(status.get('owner',''), 42, '{:42s}', 'Owner'),
            Row(status.get('current',{}).get('type', ''), 10, '{:10s}', 'Type'),
            Row(status.get('current',{}).get('height', ''), 16, '{:>16s}', 'Height'),
            Row(status.get('current',{}).get('codeHash', ''), 66, '{:66s}', 'Code Hash'),
        ]
        if 'depositInfo' in status:
            rows += [
                Header('DepositInfo', 20),
                Row(util.format_decimals(status['depositInfo'].get('availableDeposit', '0x0'),3), 16, '{:>12s} ICX', 'Avaialble'),
                Row('true' if status['depositInfo'].get('useSystemDeposit', '0x0')=='0x1' else 'false', 5, '{:5}', 'Use System Deposit')
            ]
    return rows

@click.command('account', help='Show account information')
@click.argument('addr', metavar='<address>', type=wallet.ADDRESS)
def show_account(addr: str):
    rows = get_account(addr)
    rows.append(Header('END', 3))
    MapPrinter(rows).print_data(None)

@click.command('deploy', help='Deploy contract')
@click.option('--to', metavar='<to>', type=wallet.ADDRESS)
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

def do_transfer(wallet: Wallet, to: str, amount: Union[str,int]) -> dict:
    svc = service.get_instance()
    owner = wallet.get_address()
    balance = svc.get_balance(owner)

    tx = (TransactionBuilder()
          .from_(wallet.get_address())
          .to(to)
          .value(0)
          .nid(svc.nid)
          .version(3)
    ).build()
    price = 12_500_000_000
    try :
        transfer_steps = svc.estimate_step(tx)
    except BaseException as exc:
        raise click.ClickException(f'Not transferable to={to}') from exc
    fee = transfer_steps*price
    max_value = balance - fee
    if max_value < 0:
        raise click.ClickException(f'Not enough balance to send transfer tx')

    if type(amount) is int:
        value = amount
    else:
        amount = str(amount).lower()
        if amount.endswith('icx'):
            value = int(float(amount[:-3])*util.ICX)
        elif amount == 'all':
            value = max_value
        else:
            value = int(amount, 0)
    if value > max_value:
        raise click.ClickException(f'Not enough balance to transfer limit = {util.format_decimals(max_value,3)} ICX')

    tx = (TransactionBuilder()
          .from_(wallet.get_address())
          .to(to)
          .value(value)
          .nid(svc.nid)
          .version(3)
          .step_limit(transfer_steps)
    ).build()
    log.info(f'Transfering {util.format_decimals(value,3)} of {balance/util.ICX:,.3f} to {to}')
    signed_tx = SignedTransaction(tx, wallet)
    return svc.send_transaction_and_pull(signed_tx)

@click.command('transfer', help="Transfer native token")
@click.argument('amount', metavar='<amount>', type=click.STRING)
@click.argument('to', metavar='<to>', type=wallet.ADDRESS)
def transfer(to: str, amount: str):
    '''
    Transfer specified amount of native coin to specified user.
    You may use one of following patterns for <amount>.

    \b
    - "all" for <balance> - <fee>.
    - "<X>icx" for <X> ICX.
    - "<X>" for <X> LOOP.
    '''
    ks = wallet.get_instance()
    result = do_transfer(ks, to, amount)
    log.tx_result('Transfer', result)

ScaleSearchHeight = 1000_000

@click.command('block-near', help='Get block near timestamp')
@click.argument('target_ts', metavar='<timestamp>', type=str)
def block_near(target_ts: str):
    try:
        dt = util.datetime_from_ts(target_ts)
    except:
        dt = datetime.fromisoformat(target_ts)

    dt = dt.astimezone()
    target_ts = int(dt.astimezone(util.UTC).timestamp()*1000000)

    print(f'DateTime={util.format_dt(dt)} TimeStamp={target_ts}', file=sys.stderr)

    svc = service.get_instance()

    lblk = svc.get_block(2)
    rblk = svc.get_block('latest')
    cnt = 0
    if target_ts < lblk['time_stamp'] or target_ts > rblk['time_stamp']:
        raise click.BadParameter(f'No block found at timestamp {target_ts}')
    while True:
        lblk_height = lblk['height']
        rblk_height = rblk['height']
        if rblk_height < lblk_height+ScaleSearchHeight:
            lblk_ts = lblk['time_stamp']
            rblk_ts = rblk['time_stamp']
            height = (target_ts - lblk_ts) * (rblk_height - lblk_height) // (rblk_ts - lblk_ts) + lblk_height
        else:
            height = (rblk_height + lblk_height)//2

        if height == lblk_height:
            util.dump_json(lblk)
            return
        elif height == rblk_height:
            util.dump_json(rblk)
            return

        blk = svc.get_block(height)
        cnt += 1
        print(f'[{cnt}] BH-{blk["height"]} TS={blk["time_stamp"]} {lblk_height} {rblk_height}', file=sys.stderr)
        blk_ts = blk['time_stamp']
        if target_ts < blk_ts:
            rblk = blk
        elif target_ts > blk_ts:
            lblk = blk
        else:
            util.dump_json(blk)
            return
        if rblk['height'] == lblk['height']:
            util.dump_json(blk)
            return
