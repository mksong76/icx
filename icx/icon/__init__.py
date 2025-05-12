#!/usr/bin/env python

import click

from . import asset, basic, prep, status, update, proposal

@click.group('icon', help='ICON Basic operations')
@click.pass_context
def main(ctx: click.Context):
    pass
main.add_command(basic.show_account)
main.add_command(proposal.main)

# for external access
proposal_group = proposal.main
asset_group = asset.asset

@click.group('prep', help="ICON PRep related operations")
@click.option('--store', type=click.STRING, default=None, envvar='ICX_PREP_STORE', help='File to store PRep information')
@click.pass_context
def preps(ctx: click.Context, store: str = None):
    ctx.ensure_object(dict)
    prep.handlePReps(ctx.obj, store)

preps.add_command(prep.get_prep)
preps.add_command(prep.inspect_prep)
preps.add_command(prep.register_pubkey)
preps.add_command(prep.list_preps)
preps.add_command(prep.show_votes)
preps.add_command(prep.show_term)
preps.add_command(update.update_preps_json)
preps.add_command(status.show_status)