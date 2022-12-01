#!/usr/bin/env python

from os import path
import click

from . import status, update, prep
from ..network import CONTEXT_NETWORK

@click.group()
@click.option('--store', type=click.STRING, default=None, envvar='ICX_PREP_STORE', help='File to store PRep information')
@click.pass_context
def main(ctx: click.Context, store: str = None):
    ctx.ensure_object(dict)
    prep.handlePReps(ctx.obj, store)

main.add_command(prep.set_seed)
main.add_command(update.update_preps_json)
main.add_command(status.show_status)