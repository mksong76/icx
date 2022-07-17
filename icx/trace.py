#!/usr/bin/env pthon3

import re
import click
from typing import List

from . import service, util

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
        for item in trace['logs']:
            msg = item['msg']
            frame = RE_FRAME.match(msg)
            if frame is None:
                click.echo(msg)
                continue

            id = frame.group('frameid')
            if id not in frame_depth:
                parent = frame.group('parent')
                if parent is None or parent not in frame_depth:
                    depth = 0
                    color = color_picker.get()
                else:
                    depth = frame_depth[parent]+1
                    color = color_picker.get(frame_colors[parent])
                frame_depth[id] = depth
                frame_colors[id] = color
                prefix = click.style(f'{"|":4s}',fg=color)
                prefixes = prefixes[0:depth]+[prefix]
            else:
                depth = frame_depth[id]
                color = frame_colors[id]

            msg = ''.join(prefixes[0:depth])+click.style(msg, fg=color)
            click.echo(msg)
