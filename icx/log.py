import json
import sys

import click
from rich.console import Console

from . import util

console = Console(log_path=False, stderr=True, highlight=False,
                  log_time_format="[%Y-%m-%d %H:%M:%S]")
output = Console(log_path=False, stderr=False)

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
    console.log('PRINT')
    json.dump(o, fp=fp, indent=2, default=json_handler)
    print('', file=fp, flush=flush)

def log(*args, **kwargs):
  console.log(*args, **kwargs)

def log_json(o: any):
  console.print_json(data=o, indent=2, default=json_handler)

def info(m: str):
  console.log(f'[#] {m}', markup=False)

def debug(m: str):
  console.log(f'[-] {m}', style="bright_black", markup=False)

def warn(m: str):
  console.log(f'[?] {m}', style="yellow", markup=False)

def error(m: str):
  console.log(f'[!] {m}', style="red", markup=False)

def tx_result(msg: str, tx_result: dict, raw: bool = False):
  if raw:
    print_json(tx_result)
    return

  status = click.style("SUCCESS", fg="green") if tx_result["status"] == 1 \
      else click.style("FAILURE", fg="red")
  # rows = [
  #   cui.Row(status, 20, '{}', 'Status'),
  #   cui.Row(tx_result['txHash'], 66, '{}', 'Tx Hash'),
  #   cui.Row(tx_result.get('dataType', 'transfer'), 10, '{}', 'Type'),
  #   cui.Row(util.fee_of(tx_result)/util.ICX, 18, '{:>12,.6f} ICX', 'Fee'),
  #   cui.Row(tx_result.get('value', 0)/util.ICX, 18, '{:>12,.6f} ICX', 'Value'),
  # ]
  # p = cui.MapPrinter(rows)
  # p.print_data(None)
  fee = util.fee_of(tx_result)
  tx_hash = tx_result["txHash"]

  debug(f'{msg} {status} fee={fee/util.ICX:,.6f} txHash={tx_hash}')