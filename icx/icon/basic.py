#!/usr/bin/env python3

from datetime import timedelta
import click


from .. import service, util, basic
from ..cui import Header, Row, MapPrinter
from .asset import AssetService, sum_delegation, sum_stake
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

    stake_info = asset.get_stake(addr)
    staked, unstaking, _ = sum_stake(stake_info)

    if staked > 0 or unstaking > 0:
        bond_info = asset.get_bond(addr)
        total_bonded = int(bond_info['totalBonded'], 0)
        delegation = asset.get_delegation(addr)
        delegated, voting_power = sum_delegation(delegation)
        for item in [
            [ 'Staked', staked ],
            [ 'Delegated', delegated ],
            [ 'Bonded', total_bonded ],
            [ 'Voting Power', voting_power ],
            [ 'Unstaking', unstaking ],
        ]:
            if item[1] > 0:
                rows.append(
                    Row(util.format_decimals(item[1], 3),
                        24, '{:>20s} ICX', item[0]),
                )

        idx = 0
        for unstake in stake_info.get('unstakes', []):
            unstake_amount = int(unstake.get('unstake', '0x0'), 0)
            unstake_height = int(unstake.get('unstakeBlockHeight', '0x0'), 0)
            remains = timedelta(seconds=int(unstake.get('remainingBlocks', '0x0'), 0)*2)
            rows += [
                Header(f'Unstake[{idx}]', 0),
                Row(util.format_decimals(unstake_amount, 3),
                    24, '{:>20s} ICX', 'Amount'),
                Row( f'Height: {unstake_height} ( {remains} )',
                    26, '{:>26s}', 'Expires'),
            ]
            idx += 1

        idx = 0
        for bond in bond_info.get('bonds', []):
            rows += [
                Header(f'Bond[{idx}]', 0),
                Row(bond['address'], 20, '{:<20s}', 'Address'),
                Row(util.format_decimals(bond['value'], 3), 24, '{:>20s} ICX', 'Amount'),
            ]
            idx += 1

        last_height = asset.get_last_height()
        idx = 0
        for unbond in bond_info.get('unbonds', []):
            unbond_height = int(unbond.get('expireBlockHeight', '0x0'), 0)
            unbond_remain = timedelta(seconds=(unbond_height - last_height)*2)
            rows += [
                Header(f'Unbond[{idx}]', 0),
                Row(unbond['address'], 20, '{:<20s}', 'Address'),
                Row(util.format_decimals(unbond['value'], 3), 24, '{:>20s} ICX', 'Amount'),
                Row(f'Height: {unbond_height} ( {unbond_remain} )', 26, '{:>26s}', 'Expires'),
            ]
            idx += 1

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