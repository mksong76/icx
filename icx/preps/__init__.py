#!/usr/bin/env python

import click
from . import update
from . import status

@click.group()
def main():
    pass

main.add_command(update.update_preps_json)
main.add_command(status.show_status)