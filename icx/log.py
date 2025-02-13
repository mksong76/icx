import json
import sys
import click
from . import util, cui

def info(m: str, file=sys.stderr, **kwargs):
  click.secho(f'[#] {m}', file=file, **kwargs)

def debug(m: str, file=sys.stderr, **kwargs):
  click.secho(f'[-] {m}', file=file, **kwargs)

def warn(m: str, fg='yellow', file=sys.stderr, **kwargs):
  click.secho(f'[?] {m}', fg=fg, file=file, **kwargs)

def error(m: str, fg='red', file=sys.stderr, **kwargs):
  click.secho(f'[!] {m}', fg=fg, file=file, **kwargs)

def tx_result(msg: str, tx_result: dict, raw: bool = False):
  if raw:
    click.secho(json.dumps(tx_result, indent=2), file=sys.stderr)
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