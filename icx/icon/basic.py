#!/usr/bin/env python3

import click


from .. import service, util, basic
from ..cui import Header, Row, MapPrinter
from .asset import AssetService, sum_stake
from iconsdk.builder.call_builder import CallBuilder

@click.command('account', help='ICON account information')
@click.argument('addr', type=util.ADDRESS)
def show_account(addr: str):
    svc = service.get_instance()
    asset = AssetService(svc)

    rows = basic.get_account(addr)

    rows += [
        Header('ICON', 4),
    ]
    claimable = int(asset.query_iscore(addr)['estimatedICX'], 0)
    if claimable > 0:
        rows += [
            Row(util.format_decimals(claimable, 3), 16, '{:>12s} ICX', 'Claimable')
        ]

    staked, unstaking, _ = sum_stake(asset.get_stake(addr))
    if staked > 0 or unstaking > 0:
        rows += [
            Row(lambda v: util.format_decimals(staked, 3),
                24, '{:>20s} ICX', 'Stake'),
            Row(lambda v: util.format_decimals(unstaking, 3),
                24, '{:>20s} ICX', 'Unstaking'),
        ]

    if not addr.startswith('cx'):
        try:
            prep = svc.call(CallBuilder().to(util.CHAIN_SCORE)
                    .method('getPRep')
                    .params({ 'address': addr })
                    .build())
            rows += [
                Header('PREP Info', 10),
                Row(prep.get('name', ''), 20, '{:<20s}', 'Name'),
                Row(util.format_decimals(prep.get('power', '0x0'), 3),
                    24, '{:>20s} ICX', 'Power'),
                Row(util.format_decimals(prep.get('delegated', '0x0'), 3),
                    24, '{:>20s} ICX', 'Delegated'),
                Row(util.format_decimals(prep.get('bonded', '0x0'), 3),
                    24, '{:>20s} ICX', 'Bonded'),
            ]
        except:
            pass

    rows.append(Header('END', 3))
    MapPrinter(rows).print_data(None)