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


RE_FRAME = re.compile(r'FRAME\[(?P<frameid>\d+)\] (START parent=FRAME\[(?P<parent>\d+)]|.+)')

FRAME_COLORS = [
    'white',
    'yellow',
    'cyan',
    'green',
    'red',
    'blue',
    'magenta',
]


class ColorPicker:
    def __init__(self, colors: List[str]):
        self.color_idx = 0
        self.colors = colors

    def get(self, avoid=None) -> str:
        while True:
            color = self.colors[self.color_idx]
            self.color_idx = (self.color_idx+1)%len(self.colors)
            if avoid is None or color != avoid:
                return color


@click.command()
@click.argument('txhash')
@click.option('--raw', is_flag=True)
def get_trace(txhash: str, raw: bool):
    svc = service.get_instance()
    trace = svc.get_trace(txhash)
    if raw:
        util.dump_json(trace)
    else:
        color_picker = ColorPicker(FRAME_COLORS)
        frame_colors = {}
        frame_depth = {}
        prefixes = []
        frames = []
        for item in trace['logs']:
            msg = item['msg']
            frame = RE_FRAME.match(msg)
            depth = 0
            if frame is not None:
                id = frame.group('frameid')
                if id not in frame_depth:
                    parent = frame.group('parent')
                    if parent is None or parent not in frame_depth:
                        depth = 0
                    else:
                        parent_depth = frame_depth[parent]
                        depth = parent_depth+1
                    frame_depth[id] = depth

                    parent_color = None if parent is None else frame_colors[parent]
                    color = color_picker.get(avoid=parent_color)
                    prefix = click.style(f'{"|":4s}',fg=color)
                    frame_colors[id] = color

                    prefixes = prefixes[0:depth]+[prefix]
                else:
                    depth = frame_depth[id]
                    color = frame_colors[id]

                msg = click.style(msg, fg=color)
            if depth > 0:
                msg = ''.join(prefixes[0:depth])+msg
            print(msg)


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
