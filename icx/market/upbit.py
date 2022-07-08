#!/usr/bin/env python3

import sys
from typing import Tuple

import requests

# Example https://api.upbit.com/v1/ticker?markets=KRW-ICX
UPBIT_TICKER_URL='https://api.upbit.com/v1/ticker'

def getPrice(sym: str, market: str) -> Tuple[str,float]:
    res = requests.get(UPBIT_TICKER_URL, { 'markets': f'{market}-{sym}' })
    try:
        obj = res.json()[0]
    except Exception as e:
        print('Result:', res.json(), file=sys.stderr)
        print(e.with_traceback(), file=sys.stderr)

    if 'trade_price' in obj:
        return market, int(obj['trade_price'])
    raise Exception('InvalidResponse')
