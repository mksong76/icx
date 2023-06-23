#!/usr/bin/env python3

from typing import Iterable, List, Union

import click

from . import service
from .cui import Column, RowPrinter
from .util import *

FULL_ADDR_LEN=42
SHORT_ADDR_LEN=20
def shorten_address(s: str) -> str:
    return shorten(s, SHORT_ADDR_LEN, Shorten.MIDDLE)

SHORT_VALUE_LEN = 20
def format_value(s: str) -> str:
    return shorten(format_decimals(s, 2), SHORT_VALUE_LEN, Shorten.LEFT)

def dict_get(value: dict, keys: Union[any,list], default = None) -> any:
    if type(keys) is not list:
        keys = [ keys ]
    for k in keys:
        if k in value:
            value = value[k]
        else:
            return default
    return value

TX_COLUMNS = {
    'id': Column(lambda title, tx: tx['txHash'], 66, name='ID'),
    'from': Column(lambda title, tx: dict_get(tx, 'from', '-'), FULL_ADDR_LEN, name='From'),
    'from...': Column(lambda title, tx: shorten_address(dict_get(tx, 'from', '-')), SHORT_ADDR_LEN, name='From'),
    'type': Column(lambda title, tx: dict_get(tx, 'dataType', 'transfer'), 8, name='Type'),
    'method': Column(lambda title, tx: shorten(dict_get(tx, ['data', 'method'], '-'), 20), 20, name='Method'),
    'to': Column(lambda title, tx: dict_get(tx, 'to', '-'), FULL_ADDR_LEN, name='To'),
    'to...': Column(lambda title, tx: shorten_address(dict_get(tx, 'to', '-')), SHORT_ADDR_LEN, name='To'),
    'value': Column(lambda title, tx: format_value(dict_get(tx, 'value', '0')), 20, format='{:>20}', name='Value'),
}
TX_HEIGHT_COLUMN = Column(lambda title, tx: title, 8, format='{:>8}', name='Height')
DEFAULT_COLUMN_NAMES = [ 'id', 'from...', 'type', 'method', 'to', 'value' ]

def show_txs(printer: RowPrinter, height: int, txs: list, reversed: bool, **kwargs):
    txs = txs.__reversed__() if reversed else txs
    title = str(height)
    for tx in txs:
        printer.print_data(title, tx, **kwargs)
        title = ''

def merge_filters(filter: list):
    def func(tx:dict ) -> bool:
        for f in filter:
            if not f(tx):
                return False
        return True
    return func

def expand_comma(args: Iterable[str]) -> List[str]:
    items = []
    for arg in args:
        for item in arg.split(','):
            items.append(item)
    return items

TC_CLEAR = '\033[K'

@click.command()
@click.argument('block', default="latest")
@click.option('--column', '-c', 'columns', multiple=True)
#@click.argument('columns', nargs=-1)
#@click.option('--block', '--height', 'block', default='latest')
@click.option('--forward', type=bool, is_flag=True, default=False)
@click.option('--nobase', type=bool, is_flag=True, default=False)
@click.option('--to', 'receivers', default=None, multiple=True)
@click.option('--from', 'senders', default=None, multiple=True)
@click.option('--address', '-a', 'addresses', default=None, multiple=True)
@click.option('--method', '-m', 'methods', default=None, multiple=True)
@click.option('--data_type', '-t', 'data_types', default=None, multiple=True)
@click.option('--version', type=click.INT, default=None)
def scan(columns: List[str], block, forward, nobase, receivers, senders, addresses, methods, data_types, version: int = None):
    """Scanning transactions

    COLUMNS is list of columns to display. Some of following values
    can be used.
    (id, from, from..., type, method, to, to..., value)
    """

    svc = service.get_instance()

    tx_filters = []
    if nobase:
        tx_filters.append(lambda tx: dict_get(tx, 'dataType') != 'base')
    if len(receivers) > 0:
        receivers = expand_comma(receivers)
        receivers = tuple(map(lambda x: ensure_address(x), receivers))
        tx_filters.append(lambda tx: dict_get(tx, 'to') in receivers )
    if len(senders) > 0:
        senders = expand_comma(senders)
        senders = tuple(map(lambda x: ensure_address(x), senders))
        tx_filters.append(lambda tx: dict_get(tx, 'from') in senders )
    if len(addresses) > 0:
        addresses = expand_comma(addresses)
        addresses = tuple(map(lambda x: ensure_address(x), addresses))
        tx_filters.append(lambda tx: dict_get(tx, 'from') in addresses or dict_get(tx,'to') in addresses )
    if len(methods) > 0:
        tx_filters.append(lambda tx: dict_get(tx, ['data', 'method']) in methods)
    if len(data_types) > 0:
        data_types = expand_comma(data_types)
        tx_filters.append(lambda tx: dict_get(tx, 'dataType', 'transfer') in data_types)
    if version is not None:
        tx_filters.append(lambda tx: dict_get(tx, 'version', 2) == version)
    tx_filter = merge_filters(tx_filters)

    if len(columns) == 0:
        columns = DEFAULT_COLUMN_NAMES
    else:
        columns = expand_comma(columns)
    column_data = list(map(lambda x: TX_COLUMNS[x], columns))
    column_data.insert(0, TX_HEIGHT_COLUMN)
    printer = RowPrinter(column_data)

    id = ensure_block(block)
    print_header = True
    style_index = 0
    styles = [
        {},
        { 'bg': 'bright_black'},
    ]
    while True:
        print(f'{TC_CLEAR}>Get Block {id}\r', end='')
        blk = svc.get_block(id)
        height = blk['height']
        txs = blk['confirmed_transaction_list']
        txs = list(filter(tx_filter, txs))
        if len(txs) > 0:
            if print_header:
                printer.print_header(bold=True)
                print_header = False
            show_txs(printer, height, txs, not forward, **styles[style_index])
            style_index = (style_index+1)%len(styles)
            #printer.print_separater()
        if forward:
            id = height+1
        else:
            id = height-1
