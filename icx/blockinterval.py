#!/usr/bin/env python3

from concurrent import futures
import base64
from typing import List
import click

from . import service, util

def get_data(svc: service.Service, hash: str) -> bytes:
    draw_base64 = svc.get_data_by_hash(util.ensure_block(hash))
    return base64.decodestring(draw_base64.encode())


class MovingAverage:
    def __init__(self, count:int):
        self.count = count
        self.items = []
        self.sum = 0
    def add(self, value:int) -> int:
        self.sum += value
        self.items.append(value)
        if len(self.items) > self.count:
            old = self.items.pop(0)
            self.sum -= old
        return self.get()
    def get(self) -> int:
        return self.sum // len(self.items)


INTERVAL_WINDOW = 30
INTERVAL_THREADS = 6

@click.command()
@click.argument('start', type=click.INT)
@click.argument('count', type=click.INT)
@click.option('--guide', help="Block interval configuration in milli-second", type=click.INT, default=1000)
@click.option('--threads', '-t', type=click.INT, default=INTERVAL_THREADS)
def block_interval(start: int, count: int, guide: int, threads: int):
    '''
    Check intervals of "count" blocks from "start" height
    '''
    svc = service.get_instance()

    guide_ms = guide*1000
    moving_average = MovingAverage(INTERVAL_WINDOW)
    executor = futures.ThreadPoolExecutor()
    items: List[futures.Future] = []

    blk = svc.get_block(start-1)
    ts = blk['time_stamp']
    height = start
    while len(items) > 0 or height < start+count:
        while len(items) < threads and height < start+count:
            ret, height = executor.submit(svc.get_block, height), height+1
            items.append(ret)
        item = items.pop(0)
        blk = item.result()
        ts2 = blk['time_stamp']
        interval, ts = ts2-ts, ts2
        interval_avg = moving_average.add(interval)
        print(f'[{height:6d}] interval={interval//1000:10,}ms ({(interval-guide_ms)/1000:9.3f}ms) average={interval_avg/1000:10.3f}ms ({(interval_avg-guide_ms)/1000:9.3f}ms)')
