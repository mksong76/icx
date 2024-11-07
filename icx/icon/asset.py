#!/usr/bin/env python3

import json
import locale
import os
import sys
from datetime import datetime, timedelta
from typing import Iterable, List, Optional, Tuple, Union

import click
from iconsdk.builder.call_builder import CallBuilder
from iconsdk.builder.transaction_builder import CallTransactionBuilder
from iconsdk.wallet.wallet import Wallet

from .. import basic, service, util
from ..config import CONTEXT_CONFIG, Config
from ..cui import Column, RowPrinter
from ..market import upbit
from ..util import (CHAIN_SCORE, ICX, DecimalType, dump_json,
                    ensure_address, format_decimals)
from ..wallet import wallet
from .prep import PRep

CONFIG_STAKE_TARGETS = "target_balances"
CONFIG_SUPPORTING_PREPS = "supporting_preps"
CONTEXT_ASSET = 'asset'

class AssetService:
    def __init__(self, svc: Union[str,service.Service,None] = None):
        if type(svc) is not service.Service:
            svc = service.get_instance(svc)
        self.service = svc

    def query_iscore(self, address: str) -> dict:
        return self.service.call(CallBuilder(
            to=CHAIN_SCORE,
            method='queryIScore',
            params = {
                "address": address
            }
        ).build())

    def claim_iscore(self, wallet: Wallet) -> dict:
        tx = CallTransactionBuilder(
            nid=1,
            from_=wallet.get_address(),
            to=CHAIN_SCORE,
            method='claimIScore'
        ).build()
        return self.service.estimate_and_send_tx(tx, wallet)

    def get_last_height(self) -> int:
        try:
            net_info = self.service.get_network_info()
            return int(net_info['latest'], 0)
        except:
            pass
        blk = self.service.get_block('latest')
        return blk['height']

    def get_balance(self, address: str) -> int:
        return self.service.get_balance(address)

    def get_score_api(self, address: str):
        return self.service.get_score_api(address)

    def get_stake(self, address: str) -> dict:
        return self.service.call(CallBuilder(
            to=CHAIN_SCORE,
            method= "getStake",
            params = {
                "address": address,
            }
        ).build())

    def stake_all(self, wallet: Wallet, remain: int = ICX, stake: dict = None ):
        balance = self.get_balance(wallet.get_address())

        staked = int(stake['stake'], 0)
        unstaking = 0
        for unstake in stake['unstakes']:
            unstaking += int(unstake['unstake'], 0)

        change = (balance+unstaking)-remain
        if change == 0:
            return

        target = staked + change
        if target < 0:
            if  staked == 0:
                return
            target = 0
            change = target-staked

        print(f'[!] Stake ADJUST {change/ICX:+.3f} to={target/ICX:.3f}', file=sys.stderr)

        tx = CallTransactionBuilder(
            nid=1,
            from_=wallet.get_address(),
            to=CHAIN_SCORE,
            method='setStake',
            params={ 'value': f'0x{target:x}' },
        ).build()
        self.service.estimate_and_send_tx(tx, wallet)


    def get_delegation(self, address: str) -> dict:
        return self.service.call(CallBuilder(
            to=CHAIN_SCORE,
            method= "getDelegation",
            params = {
                "address": address,
            }
        ).build())

    def delegate_all(self, preps: List[str], wallet: Wallet, target: int = 0, delegation: dict = None):
        if delegation is None:
            delegation = self.get_delegation(wallet.get_address())

        spreps = []
        for entry in delegation['delegations']:
            spreps.append(entry['address'])
        if preps is None or len(preps) == 0:
            preps = spreps
        prep_count = len(preps)

        voting_power = int(delegation['votingPower'], 0)
        change =  voting_power - target
        if change == 0 and set(preps) == set(spreps):
            return

        print(f'[!] Delegate ADJUST {change/ICX:+.3f}', file=sys.stderr)

        new_delegations = []
        total_power = change + int(delegation['totalDelegated'], 0)
        if total_power > 0:
            if prep_count == 0:
                raise Exception(f'NoCurrentDelegation')

            power = (total_power+prep_count-1)//prep_count
            for entry in preps:
                if total_power < power:
                    power = total_power
                total_power -= power
                new_delegations.append({
                    "address": entry,
                    "value": f'0x{power:x}'
                })

        tx = CallTransactionBuilder(
            nid=1,
            to=CHAIN_SCORE,
            method='setDelegation',
            params={ "delegations": new_delegations },
            from_=wallet.get_address(),
        ).build()
        self.service.estimate_and_send_tx(tx, wallet)

    def get_bond(self, address: str) -> dict:
        return self.service.call(CallBuilder(
            to=CHAIN_SCORE,
            method= "getBond",
            params = {
                "address": address,
            }
        ).build())

def sum_stake(stake: dict) -> Tuple[int, int, int]:
    staked = int(stake['stake'], 0)
    unstaking = 0
    remain_blocks = 0
    for unstake in stake['unstakes']:
        unstaking += int(unstake['unstake'], 0)
        remain_blocks = max(remain_blocks, int(unstake['remainingBlocks'], 0))
    return staked, unstaking, remain_blocks

def sum_delegation(delegation: dict) -> Tuple[int, int]:
    delegated = int(delegation['totalDelegated'], 0)
    votingPower = int(delegation['votingPower'], 0)
    return delegated, votingPower

def sum_bond(bond: dict) -> Tuple[int, int, int, int]:
    bonded = int(bond['totalBonded'], 0)
    unbonding = 0
    expire_height = 0
    for unbond in bond['unbonds']:
        unbonding += int(unbond['value'], 0)
        expire_height = max(expire_height, int(unbond['expireBlockHeight'], 0))
    votingPower = int(bond['votingPower'], 0)
    return bonded, unbonding, votingPower, expire_height

def get_stake_target(config: Config, addr: str, target: int = 0) -> int:
    targets = config[CONFIG_STAKE_TARGETS]
    if addr in targets:
        return targets[addr]
    else:
        return target

def set_stake_target(config: Config, addr: str, target: int):
    targets = config[CONFIG_STAKE_TARGETS]
    if addr not in targets or targets[addr] != target:
        targets[addr] = target
        config[CONFIG_STAKE_TARGETS] = targets

def set_supporting_preps(config: Config, addr: str, preps: List[str]):
    supporting_preps = config[CONFIG_SUPPORTING_PREPS]
    if addr not in preps or set(supporting_preps[addr]) != set(preps):
        supporting_preps[addr] = preps
        config[CONFIG_SUPPORTING_PREPS] = supporting_preps

def get_supporting_preps(config: Config, addr: str) -> List[str]:
    preps = config[CONFIG_SUPPORTING_PREPS]
    if addr in preps:
        return preps[addr]
    else:
        return None

def get_price() -> tuple[str,int]:
    locale.setlocale(locale.LC_ALL, '')
    try :
        sym, price = upbit.getPrice('ICX')
    except:
        sym = 'ICX'
        price = 1
    return sym, price


@click.command('show')
@click.argument('address', type=wallet.ADDRESS, nargs=-1)
@click.pass_obj
def show_asset(ctx: dict, address: List[str]):
    if len(address) == 0:
        wallet: Wallet = get_wallet()
        address = [ wallet.get_address() ]
    for item in address:
        show_asset_of(ctx, item)

def show_asset_of(ctx: dict, addr: str):
    addr = ensure_address(addr)
    config: Config = ctx[CONTEXT_CONFIG]
    target: Optional[int] = get_stake_target(config, addr, None)
    stake_desc = ''
    balance_desc = ''
    if target is not None:
        if target > 0:
            stake_desc = f'>> {target:.3f} ICX'
        else:
            balance_desc = f'>> {(-target):.3f} ICX'


    service = AssetService()
    balance = service.get_balance(addr)
    iscore = service.query_iscore(addr)
    stake = service.get_stake(addr)
    delegation = service.get_delegation(addr)
    bond = service.get_bond(addr)
    last_height = service.get_last_height()
    #print(json.dumps(balance, indent=2))
    #print(json.dumps(stake, indent=2))
    #print(json.dumps(delegation, indent=2))
    #print(json.dumps(bond, indent=2))

    claimable = int(iscore['estimatedICX'], 0)
    staked, unstaking, remaining_blocks = sum_stake(stake)
    delegated, voting_power = sum_delegation(delegation)
    bonded, unbonding, _, expire_height = sum_bond(bond)
    asset = balance+claimable+staked+unstaking

    entries = []
    if asset > 0 :
        unstaked = balance+claimable+unstaking
        entries += [
            [ 'UNSTAKED', unstaked, unstaked/asset, balance_desc ],
            [ '- BALANCE', balance, balance/unstaked, balance_desc ],
            [ '- CLAIMABLE', claimable, claimable/unstaked ],
        ]
        if unstaking > 0:
            remaining_time = timedelta(seconds=remaining_blocks*2)
            entries += [
                [ '- UNSTAKING', unstaking, unstaking/unstaked, f'{remaining_time}'],
            ]

        if staked > 0:
            entries += [
                [ 'STAKED', staked, staked/asset, stake_desc ],
                [ '- DELEGATED', delegated, delegated/staked ],
                [ '- BONDED', bonded, bonded/staked ],
                [ '- REMAINS', voting_power, voting_power/staked ],
            ]
            if unbonding > 0:
                bonding_remains = expire_height - last_height
                remaining_time = timedelta(seconds=bonding_remains*2)
                entries += [
                    [ '- UNBONDING', unbonding, unbonding/staked, f'{remaining_time}' ],
                ]

    sym, price = get_price()

    columns = [
        Column(lambda x: x[0], 13, '{:13s}', "Name"),
        Column(lambda x: format_decimals(x[1],3), 20, '{:>16s} ICX', 'ICX'),
        Column(lambda x: x[1]*price//ICX, 18, f'{{:>12,}} {sym[:3]:3s}', sym),
        Column(lambda x: x[2]*100, 8, '{:7.3f}%', 'Portion'),
        Column(lambda x: x[3] if len(x)>3 else '', 25, '{:<25}', 'Note'),
    ]

    p = RowPrinter(columns)
    p.print_spanned(1, 4, ["ADDRESS", addr], reverse=True, underline=True)
    p.print_header()
    for entry in entries:
        if entry[1] == 0 and entry[2] == 0:
            continue
        p.print_data(entry, underline=True)
    p.print_data(['ASSET', asset, 1.0, f'1 ICX = {price} {sym}'], reverse=True)

@click.command("auto")
@click.option("--stake", 'target', type=int, metavar='<amount>', help="Amount to stake in ICX (negative for asset-X)")
@click.option("--noclaim", type=bool, is_flag=True, help='Prevent claimIScore()')
@click.option('--preps', '-p', type=str, multiple=True, metavar='<prep1>,<prep2>....', help='List of PReps for delegation')
@click.option("--vpower", 'vpower', type=int, default=0, metavar='<amount>', help="Target voting power in ICX")
@click.pass_obj
def stake_auto(ctx: dict, preps: List[str] = None, vpower: int = 0, target: int = None,  noclaim: bool = False):
    service = AssetService()
    config: Config = ctx[CONTEXT_CONFIG]
    wallet: Wallet = get_wallet()
    if target is None:
        target = get_stake_target(config, wallet.get_address(), None)
    else:
        set_stake_target(config, wallet.get_address(), target)

    if len(preps) > 0:
        npreps = []
        for prep in preps:
            npreps += prep.split(',')
        preps = npreps
        set_supporting_preps(config, wallet.get_address(), preps)
    else:
        preps = get_supporting_preps(config, wallet.get_address())

    iscore = service.query_iscore(wallet.address)
    claimable = int(iscore['estimatedICX'], 0)
    if claimable >= ICX and not noclaim:
        print(f'[!] Claim claimable={claimable/ICX:.3f}', file=sys.stderr)
        service.claim_iscore(wallet)
        claimable = 0

    balance = service.get_balance(wallet.address)
    stakes = service.get_stake(wallet.address)
    delegation = service.get_delegation(wallet.address)
    votingpower = int(delegation['votingPower'], 0)
    staked, unstaking, _ = sum_stake(stakes)
    votingpower_new = vpower*ICX

    if target is None:
        min_balance = balance+unstaking
    elif target >= 0:
        min_balance = balance+staked+unstaking-target*ICX
    else:
        min_balance = -target*ICX
    if min_balance < ICX:
        raise Exception(f'Invalid target balance={format_decimals(min_balance,3)} stake={target}')
    max_balance = min_balance+ICX

    print(f'[#] Stake AUTO target_balance={format_decimals(min_balance,3)} balance={format_decimals(balance,3)} unstaking={format_decimals(unstaking,3)} ', file=sys.stderr)

    if balance+unstaking > max_balance:
        print(f'[-] Staking MORE {(balance+unstaking-max_balance)/ICX:+.3f}', file=sys.stderr)
        service.stake_all(wallet, max_balance, stakes)
        service.delegate_all(preps, wallet, votingpower_new)
    elif balance+unstaking < min_balance:
        print(f'[-] Staking LESS {(balance+unstaking-max_balance)/ICX:+.3f}', file=sys.stderr)
        if balance+unstaking+votingpower < min_balance+votingpower_new:
            votingpower = max_balance-unstaking-balance+votingpower_new
            service.delegate_all(preps, wallet, votingpower)
        target_balance = service.get_balance(wallet.address)
        target_balance += votingpower+unstaking
        service.stake_all(wallet, target_balance, stakes)
    else:
        service.delegate_all(preps, wallet, votingpower_new)

    delegation = service.get_delegation(wallet.address)
    stakes = service.get_stake(wallet.address)
    balance = service.get_balance(wallet.address)
    staked, unstaking, remaining_blocks = sum_stake(stakes)

    asset = claimable + balance + staked + unstaking
    remains = timedelta(seconds=remaining_blocks*2)

    sym, price = get_price()
    krw = (asset*price)//ICX
    print(f'[#] Asset={format_decimals(asset,3)} ( x {price:n} = {krw:n} {sym})', file=sys.stderr)
    print(f'[#] Balance={format_decimals(balance,3)} ' +
          f'Claimable={format_decimals(claimable,3)} ' +
          f'Staked={format_decimals(staked,3)} ' +
          f'Unstaking={format_decimals(unstaking,3)} ({remains})',
          file=sys.stderr)

@click.command('delegation')
@click.pass_obj
def show_delegation(ctx: dict):
    service = AssetService()
    wallet: Wallet = get_wallet()
    delegations = service.get_delegation(wallet.get_address())
    prep_info = service.service.call(CallBuilder(to=CHAIN_SCORE, method='getPReps').build())
    prep_map = {}
    for prep in prep_info['preps']:
        prep_map[prep['address']] = prep

    columns = [
        Column(lambda e, p: p['name'], 16, '{:<16.16s}', "Name"),
        Column(lambda e, p: e['address'], 42, '{:42s}', "Address"),
        Column(lambda e, p: p.commission_rate/100, 7, '{:>6.2f}%', "Comm %"),
        Column(lambda e, p: p.voter_rate*100, 7, '{:>6.2f}%', "Voter %"),
        Column(lambda e, p: format_decimals(p.delegation_required,3), 16, '{:>16}', "Delegation Req"),
        Column(lambda e, p: format_decimals(e['value'],3), 16, '{:>16s}', "Delegation"),
    ]

    p = RowPrinter(columns)
    p.print_row([
        (1, 'Wallet'),
        (p.columns-1, wallet.get_address())
    ], reverse=True, underline=True)
    p.print_header()
    for entry in delegations['delegations']:
        prep = PRep(prep_map[entry['address']])
        p.print_data(entry, prep, underline=True)

def get_wallet() -> Wallet:
    ctx = click.get_current_context()
    obj = ctx.obj
    if CONTEXT_ASSET not in obj:
        if wallet.CONTEXT_KEYSTORE in obj:
            return wallet.get_instance()
        key_store = os.environ.get('ICX_ASSET_KEY_STORE')
        obj[CONTEXT_ASSET] = wallet.get_instance(key_store)
    return obj[CONTEXT_ASSET]

def get_wallet_addr() -> Optional[str]:
    try:
        return get_wallet().get_address()
    except:
        return None

@click.command('price')
@click.argument('amount', type=DecimalType('icx', 18))
@click.option('--market', type=str)
def show_price(amount: int, market: str = None):
    sym, price = get_price()
    value = price*amount//ICX
    click.echo(f'{value:n} {sym}')

@click.command('transfer')
@click.argument('amount', type=click.STRING, metavar='<amount>')
@click.argument('to', type=wallet.ADDRESS)
@click.pass_obj
def transfer(obj: dict, to: str, amount: str):
    '''
    Transfer specified amount of native coin to specified user.
    You may use one of following patterns for <amount>.

    \b
    - "all" for <balance> - <fee>.
    - "<X>icx" for <X> ICX.
    - "<X>" for <X> LOOP.
    '''
    wallet = get_wallet()
    basic.do_transfer(wallet, to, amount)

def as_int(v: Optional[str], d: Optional[int] = None) -> Optional[int]:
    return d if v is None else int(v, 0)

def get_rewards_of(address: str, *, height: int = None, terms: int = 5) -> Iterable[dict]:
    svc = service.get_instance()

    term_info = svc.call(CallBuilder(
        to=CHAIN_SCORE, method='getPRepTerm', height=height
    ).build())
    term_start = as_int(term_info['startBlockHeight'])
    term_seq = as_int(term_info['sequence']) - 2
    latest_claimable = as_int(svc.call(
        CallBuilder(
            to=CHAIN_SCORE,
            method="queryIScore",
            params={
                "address": address,
            },
            height=height,
        ).build()
    )['estimatedICX'])
    claimed = False

    while terms > 0:
        iiss_info = svc.call(
            CallBuilder(
                to=CHAIN_SCORE, method="getIISSInfo", height=term_start+1
            ).build()
        )
        rc_start = as_int(iiss_info['rcResult']['startBlockHeight'])
        rc_end = as_int(iiss_info['rcResult']['endBlockHeight'])
        old_iscore = svc.call(
            CallBuilder(
                to=CHAIN_SCORE,
                method="queryIScore",
                params={
                    "address": address,
                },
                height=term_start,
            ).build()
        )
        new_iscore = svc.call(
            CallBuilder(
                to=CHAIN_SCORE,
                method="queryIScore",
                params={
                    "address": address,
                },
                height=term_start+1,
            ).build()
        )
        claimable = as_int(new_iscore['estimatedICX'])
        old_claimable = as_int(old_iscore['estimatedICX'])
        reward = claimable - old_claimable
        blk = svc.get_block(rc_start)
        dt = util.datetime_from_ts(blk['time_stamp'])

        claim = claimable-latest_claimable
        claimed = True if claim>0 else claimed
        yield {
            'start': rc_start,
            'end': rc_end,
            'sequence': term_seq,
            'reward': reward,
            'claimed': claimed,
            'claim': claim,
            'claimable': latest_claimable,
            'timestamp': dt.astimezone(),
        }
        latest_claimable = old_claimable
        term_start = rc_end+1
        term_seq -= 1
        terms -= 1

def show_rewards_of(address: str, *, height: int = None, terms: int = 7):
    def claim_field(e:dict) -> str:
        value = None
        if e['claim'] > 0:
            value = e['claim']
        # elif e.get('is_last') and e['claimable'] > 0:
        #     value = e['claimable']
        else:
            return ''
        return f'{format_decimals(value,3)} ICX'

    columns = [
        Column(lambda e: e['sequence'], 6, '{:>6}', "Seq"),
        Column(lambda e: e['start'], 10, '{:>10}', "Start"),
        Column(lambda e: e['end'], 10, '{:>10}', "End"),
        Column(lambda e: str(e['timestamp']), 19, '{:<19}', "Start Time"),
        Column(lambda e: format_decimals(e['reward'],3), 20, '{:>16} ICX', "Reward"),
        Column(lambda e: claim_field(e), 20, '{:>}', "Claimed"),
    ]

    rewards = list(get_rewards_of(address, height=height, terms=terms))
    if len(rewards) == 0:
        click.echo('No rewards')
        return
    claimable = rewards[0]['claimable']
    rewards.reverse()
    reward_sum = 0

    p = RowPrinter(columns)
    p.print_row([
        (2, 'ADDRESS', '>'),
        (4, address, '<'),
    ], reverse=True, underline=True)
    p.print_header()

    for info in rewards:
        reward_sum += info['reward']
        fg = 'yellow' if not info['claimed'] else None
        p.print_data(info, fg=fg, underline=info["claim"]>0)

    sym, price = get_price()
    reward_price = int(price*reward_sum)
    claimable_price = int(price*claimable)

    p.print_row([
        (4, f'Total Reward / Claimable', '>'),
        (1, f'{format_decimals(reward_sum,3)} ICX', '>'),
        (1, f'{format_decimals(claimable,3)} ICX', '>'),
    ], reverse=True)
    p.print_row([
        (4, f'1 ICX = {price:,d} KRW', '>'),
        (1, f'{format_decimals(reward_price,0)} {sym}', '>'),
        (1, f'{format_decimals(claimable_price,0)} {sym}', '>'),
    ], reverse=True)

@click.command('reward')
@click.argument('address', type=wallet.ADDRESS, nargs=-1)
@click.option('--height', '-h', type=util.INT, default=None)
@click.option('--terms', '-t', type=util.INT, default=7)
@click.pass_obj
def show_reward(obj: dict, address: list[str], height: int = None, terms: int = 5):
    if len(address) == 0:
        wallet: Wallet = get_wallet()
        address = [ wallet.get_address() ]
    for item in address:
        show_rewards_of(item, height=height, terms=terms)
