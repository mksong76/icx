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
proposal_main = proposal.main

@click.group('asset', help='ICON Asset related operations')
@click.option('--key_store', '--ks', metavar='<name>|<file>', help='KeyStore for asset')
@click.pass_context
def assets(ctx: click.Context, key_store: str = None):
    ctx.ensure_object(dict)

assets.add_command(asset.show_asset)
assets.add_command(asset.transfer)
assets.add_command(asset.stake_auto)
assets.add_command(asset.show_delegation)
assets.add_command(asset.show_price)
assets.add_command(asset.show_reward)

@click.group('prep', help="ICON PRep related operations")
@click.option('--store', type=click.STRING, default=None, envvar='ICX_PREP_STORE', help='File to store PRep information')
@click.option('--key_store', '--ks', metavar='<name>|<file>', help='KeyStore for PRep command')
@click.pass_context
def preps(ctx: click.Context, key_store: str = None, store: str = None):
    ctx.ensure_object(dict)
    prep.handlePReps(ctx.obj, store)

preps.add_command(prep.get_prep)
preps.add_command(prep.inspect_prep)
preps.add_command(prep.register_pubkey)
preps.add_command(prep.list_preps)
preps.add_command(update.update_preps_json)
preps.add_command(status.show_status)