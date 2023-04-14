#!/usr/bin/env python

import json
import sys
from os import path

import click
from iconsdk.builder.call_builder import CallBuilder

from . import asset, basic, prep, status, update

@click.group('icon', help='ICON Basic operations')
@click.pass_context
def main(ctx: click.Context):
    pass
main.add_command(basic.show_account)

@click.group('asset', help='ICON Asset related operations')
@click.option('--key_store', envvar='ICX_ASSET_KEY_STORE')
@click.pass_context
def assets(ctx: click.Context, key_store: str = None):
    ctx.ensure_object(dict)
    asset.handleAssetKeyStore(ctx.obj, key_store)

assets.add_command(asset.show_asset)
assets.add_command(asset.stake_auto)
assets.add_command(asset.show_delegation)

@click.group('prep', help="ICON PRep related operations")
@click.option('--store', type=click.STRING, default=None, envvar='ICX_PREP_STORE', help='File to store PRep information')
@click.pass_context
def preps(ctx: click.Context, store: str = None):
    ctx.ensure_object(dict)
    prep.handlePReps(ctx.obj, store)
preps.add_command(prep.set_seed)
preps.add_command(prep.get_prep)
preps.add_command(prep.inspect_prep)
preps.add_command(update.update_preps_json)
preps.add_command(status.show_status)