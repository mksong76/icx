#!/usr/bin/env python3

import click


from .. import service, util
from ..cui import Header, Row, MapPrinter
from .asset import AssetService
from iconsdk.builder.call_builder import CallBuilder

@click.command('account', help='ICON account information')
@click.argument('addr', type=util.ADDRESS)
def show_account(addr: str):
    svc = service.get_instance()
    asset = AssetService(svc)
    info = { 'address': addr }
    rows = [
        Header(lambda v: 'Basic', 5, '{}'),
        Row(lambda v: v['address'], 42, '{}', 'Address'),
    ]

    info['balance'] = svc.get_balance(addr)
    rows += [
        Row(lambda v: util.format_decimals(v['balance'], 3), 16, '{:>12s} ICX', 'Balance'),
    ]

    if addr.startswith('cx'):
        info['status'] = svc.get_score_status(addr)
        rows += [
            Header(lambda v: 'SCORE', 20, '{:^}'),
            Row(lambda v: v['status'].get('owner',''), 42, '{:42s}', 'Owner'),
            Row(lambda v: v['status'].get('current',{}).get('type', ''), 10, '{:10s}', 'Type'),
            Row(lambda v: v['status'].get('current',{}).get('codeHash', ''), 66, '{:66s}', 'Code Hash'),
        ]
    else:

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

        try:
            stake = asset.get_stake(addr)
            if int(stake['stake'], 0) > 0:
                info['stake'] = {
                    "stake": int( stake['stake'], 0 ),
                    "unstake": sum(map(lambda v: int(v['unstake'], 0), stake['unstakes'])),
                }
                rows += [
                    Header(lambda v: 'Stake Info', 20, '{:^20s}'),
                    Row(lambda v: util.format_decimals(v['stake']['stake'], 3),
                        20, '{:>20s}', 'Stake'),
                    Row(lambda v: util.format_decimals(v['stake']['unstake'], 3),
                        20, '{:>20s}', 'Unstake'),
                ]
        except:
            raise


    MapPrinter(rows).print_data(info)