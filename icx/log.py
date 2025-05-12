import json
import sys

import click, asyncio, ccxt
from rich import traceback, style, highlighter
from rich.console import Console
from rich.text import Text

from icx import richex

from . import util, cui

console = Console(log_path=False, stderr=True, highlight=True,
                  log_time_format="[%Y-%m-%d %H:%M:%S]")
output = Console(log_path=False, stderr=False)
traceback.install(suppress=[click, asyncio, ccxt], console=console)

def json_handler(x) -> any:
  if isinstance(x, bytes):
    return '0x'+x.hex()
  raise TypeError(f'UnknownType(type={type(x)})')

def print_json(o: any, fp=sys.stdout, flush: bool = False):
  if fp == sys.stdout:
    output.print_json(data=o, indent=2, default=json_handler)
  elif fp == sys.stderr:
    console.print_json(data=o, indent=2, default=json_handler)
  else:
    json.dump(o, fp=fp, indent=2, default=json_handler)
    print('', file=fp, flush=flush)

def print(*args, **kwargs):
  output.print(*args, **kwargs)

def log(*args, _stack_offset=2, **kwargs):
  console.log(*args, _stack_offset=_stack_offset, **kwargs,)

def log_json(o: any, indent=2, highlight=True):
  console.print_json(data=o, indent=indent, default=json_handler, highlight=highlight)


class Style:
  INFO = style.Style()
  DEBUG = style.Style(dim=True)
  WARN = style.Style(color="yellow")
  ERROR = style.Style(color="red")

  SUCCESS = style.Style(color="green", bold=True, dim=False)
  FAILURE = style.Style(color="red", bold=True, dim=False)

def info(*m: str, markup=False, **kwargs):
  console.log(*m, style=Style.INFO, markup=markup, **kwargs)

def debug(*m: str, markup=False, **kwargs):
  console.log(*m, style=Style.DEBUG, markup=markup, **kwargs)

def warn(*m: str, markup=False, **kwargs):
  console.log(*m, style=Style.WARN, markup=markup, **kwargs)

def error(*m: str, markup=False, **kwargs):
  console.log(*m, style=Style.ERROR, markup=markup, **kwargs)

def status(m: str, **kwargs):
  return console.status(m, **kwargs)

def tx_result(msg: str, tx_result: dict, raw: bool = False):
  if raw:
    log_json(tx_result)
    return

  status = (
    Text("SUCCESS", Style.SUCCESS) if tx_result["status"] == 1
    else Text("FAILURE", Style.FAILURE)
  )

  fee = util.fee_of(tx_result)
  tx_hash = tx_result["txHash"]

  text = richex.format('{} {} fee={} txHash={}',
                       msg, status, util.fvalue(fee/util.ICX), tx_hash)
  highlighter.ReprHighlighter().highlight(text)
  info(text)
