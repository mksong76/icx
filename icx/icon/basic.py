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

    info, rows = basic.get_account(addr)

    rows += [
        Header(lambda v: 'ICON', 4, '{:^}'),
    ]
    claimable = int(asset.query_iscore(addr)['estimatedICX'], 0)
    if claimable > 0:
        info['claimable'] = claimable
        rows += [
            Row(lambda v: util.format_decimals(v['claimable'], 3), 16, '{:>12s} ICX', 'Claimable'),
        ]

    staked, unstaking, _ = sum_stake(asset.get_stake(addr))
    if staked > 0 or unstaking > 0:
        info['stake'] = {
            "staked": staked,
            "unstaking": unstaking,
        }
        rows += [
            Row(lambda v: util.format_decimals(v['stake']['staked'], 3),
                24, '{:>20s} ICX', 'Stake'),
            Row(lambda v: util.format_decimals(v['stake']['unstaking'], 3),
                24, '{:>20s} ICX', 'Unstaking'),
        ]

    if not addr.startswith('cx'):
        try:
            info['prep'] = svc.call(CallBuilder().to(util.CHAIN_SCORE)
                    .method('getPRep')
                    .params({ 'address': addr })
                    .build())
            rows += [
                Header(lambda v: 'PREP Info', 20, '{:^20s}'),
                Row(lambda v: v['prep'].get('name', ''), 20, '{:>20s}', 'Name'),
                Row(lambda v: util.format_decimals(v['prep'].get('power', '0x0'), 3),
                    20, '{:>20s}', 'Power'),
                Row(lambda v: util.format_decimals(v['prep'].get('delegated', '0x0'), 3),
                    20, '{:>20s}', 'Delegated'),
                Row(lambda v: util.format_decimals(v['prep'].get('bonded', '0x0'), 3),
                    20, '{:>20s}', 'Bonded'),
            ]
        except:
            pass

    MapPrinter(rows).print_data(info)