#!/usr/bin/env python3

from typing import List, Union
import click

from . import service
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


class Column:
    def __init__(self, get_value, size: int, format: str = None) -> None:
        self.__get_value = get_value
        self.__size = size
        self.__format = format if format is not None else f'{{:{size}}}'

    def get_value(self, *args) -> any:
        return self.__get_value(*args)

    @property
    def size(self):
        return self.__size

    @property
    def format(self):
        return self.__format

TX_COLUMNS = {
    'id': Column(lambda title, tx: tx['txHash'], 66),
    'from': Column(lambda title, tx: dict_get(tx, 'from', '-'), FULL_ADDR_LEN),
    'from...': Column(lambda title, tx: shorten_address(dict_get(tx, 'from', '-')), SHORT_ADDR_LEN),
    'type': Column(lambda title, tx: dict_get(tx, 'dataType', 'transfer'), 8),
    'method': Column(lambda title, tx: shorten(dict_get(tx, ['data', 'method'], '-'), 20), 20),
    'to': Column(lambda title, tx: dict_get(tx, 'to', '-'), FULL_ADDR_LEN),
    'to...': Column(lambda title, tx: shorten_address(dict_get(tx, 'to', '-')), SHORT_ADDR_LEN),
    'value': Column(lambda title, tx: format_value(dict_get(tx, 'value', '0')), 20, format='{:>20}'),
}
TX_HEIGHT_COLUMN = Column(lambda title, tx: title, 8, format='{:>8}')
DEFAULT_COLUMN_NAMES = [ 'id', 'from...', 'type', 'method', 'to...', 'value' ]

class RowPrinter:
    def __init__(self, columns: List[Column], file=sys.stdout) -> None:
        formats = []
        seps = []
        for column in columns:
            formats.append(column.format)
            seps.append('-'*column.size)
        self.__columns = columns
        self.__file = file
        self.__format_str = '| ' + ' | '.join(formats) + ' |'
        self.__sep_str = '+-' + '-+-'.join(seps) + '-+'

    def print_separater(self):
        print(self.__sep_str, file=self.__file)

    def print_data(self, *args):
        values = []
        for column in self.__columns:
            values.append(column.get_value(*args))
        print(self.__format_str.format(*values), file=self.__file)

def show_txs(printer: RowPrinter, height: int, txs: list, reverse: bool):
    txs = txs.__reversed__() if reverse else txs
    title = str(height)
    for tx in txs:
        printer.print_data(title, tx)
        title = ''
    printer.print_separater()

def merge_filters(filter: list):
    def func(tx:dict ) -> bool:
        for f in filter:
            if not f(tx):
                return False
        return True
    return func

TC_CLEAR = '\033[K'

@click.command()
@click.argument('columns', nargs=-1)
@click.option('--block', default='latest')
@click.option('--forward', type=bool, is_flag=True, default=False)
@click.option('--nobase', type=bool, is_flag=True, default=False)
@click.option('--to', default=None)
@click.option('--method', default=None)
@click.option('--data_type', default=None)
def scan(columns, block, forward, nobase, to, method, data_type):
    """Scanning transactions

    COLUMNS is list of columns to display. Some of following values
    can be used.
    (id, from, from..., type, method, to, to..., value)
    """

    svc = service.get_instance()

    tx_filters = []
    if nobase:
        tx_filters.append(lambda tx: dict_get(tx, 'dataType') != 'base')
    if to is not None:
        to = ensure_address(to)
        tx_filters.append(lambda tx: dict_get(tx, 'to') == to)
    if method is not None:
        tx_filters.append(lambda tx: dict_get(tx, ['data', 'method']) == method)
    if data_type is not None:
        tx_filters.append(lambda tx: dict_get(tx, 'dataType', 'transfer') == data_type)
    tx_filter = merge_filters(tx_filters)

    if len(columns) == 0:
        columns = DEFAULT_COLUMN_NAMES
    column_data = list(map(lambda x: TX_COLUMNS[x], columns))
    column_data.insert(0, TX_HEIGHT_COLUMN)
    printer = RowPrinter(column_data)

    id = ensure_block(block)
    sep_print = False
    while True:
        print(f'{TC_CLEAR}>Get Block {id}\r', end='')
        blk = svc.get_block(id)
        height = blk['height']
        txs = blk['confirmed_transaction_list']
        txs = list(filter(tx_filter, txs))
        if len(txs) > 0:
            if not sep_print:
                printer.print_separater()
                sep_print = True
            show_txs(printer, height, txs, not forward)
        if forward:
            id = height+1
        else:
            id = height-1