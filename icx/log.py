import json
import sys

import click, asyncio, ccxt
from rich import traceback, style, highlighter
from rich.console import Console
from rich.text import Text

from . import util, richex

console = Console(log_path=False, stderr=True, highlight=False,
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


  status = richex.Styled('SUCCESS', fg='bright_green', dim=False) if tx_result["status"] == 1 \
    else richex.Styled('FAILURE', fg='bright_red', dim=False)

  # rows = [
  #   cui.Row(status, 20, '{}', 'Status'),
  #   cui.Row(tx_result['txHash'], 66, '{}', 'Tx Hash'),
  #   cui.Row(tx_result.get('dataType', 'transfer'), 10, '{}', 'Type'),
  #   cui.Row(util.fvalue(util.fee_of(tx_result)/util.ICX), 18, '{:>} ICX', 'Fee'),
  #   cui.Row(util.fvalue(tx_result.get('value', 0)/util.ICX), 18, '{:>} ICX', 'Value'),
  # ]
  # p = cui.MapPrinter(rows)
  # p.print_header()
  # p.print_data(None, underline=True)

  fee = util.fee_of(tx_result)
  tx_hash = tx_result["txHash"]

  text = Text(f'{msg} {status.value} fee={util.fvalue(fee/util.ICX)} txHash={tx_hash}')
  highlighter.ReprHighlighter().highlight(text)
  text.highlight_words(['SUCCESS'], 'bright_green')
  text.highlight_words(['FAILURE'], 'bright_red')
  info(text)