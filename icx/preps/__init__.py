#!/usr/bin/env python

import click

from . import status, update
from .prep import PREP_STORE, PREPS_JSON

@click.group()
@click.option('--store', type=click.STRING, default=PREPS_JSON, envvar='ICX_PREP_STORE')
@click.pass_context
def main(ctx: click.Context, store: str):
    ctx.ensure_object(dict)
    ctx.obj[PREP_STORE] = store

main.add_command(update.update_preps_json)
main.add_command(status.show_status)