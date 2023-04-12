#!/usr/bin/env python3

import locale
import sys
from audioop import add
from cProfile import label
from datetime import timedelta
from typing import List, Tuple

import click
from iconsdk.builder.call_builder import CallBuilder
from iconsdk.builder.transaction_builder import CallTransactionBuilder
from iconsdk.icon_service import SignedTransaction, Transaction
from iconsdk.wallet.wallet import Wallet

from .. import service
from ..config import CONTEXT_CONFIG, Config
from ..market import upbit
from ..util import CHAIN_SCORE, ICX, ensure_address, format_decimals
from ..cui import Column, RowPrinter
from . import wallet

CONFIG_STAKE_TARGETS = "target_balances"
CONFIG_SUPPORTING_PREPS = "supporting_preps"
CONTEXT_ASSET = 'asset'

class AssetService:
    def __init__(self, url: str = None):
        self.service = service.get_instance(url)

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

    def get_bond(self, address: str) -> dict:
        return self.service.call(CallBuilder(
            to=CHAIN_SCORE,
            method='getBond',
            params = {
                'address': address,
            }
        ))

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

def sum_bond(bond: dict) -> Tuple[int, int, int]:
    bonded = int(bond['totalBonded'], 0)
    unbonding = 0
    for unbond in bond['unbonds']:
        unbonding += int(unbond['unbond'], 0)
    votingPower = int(bond['votingPower'], 0)
    return bonded, unbonding, votingPower

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

@click.command('show')
@click.argument('address', nargs=-1)
@click.pass_obj
def show_asset(ctx: dict, address: List[str]):
    if len(address) == 0:
        wallet: Wallet = ctx[CONTEXT_ASSET]
        address = [ wallet.get_address() ]
    for item in address:
        show_asset_of(item)

def show_asset_of(addr: str):
    addr = ensure_address(addr)

    service = AssetService()
    balance = service.get_balance(addr)
    iscore = service.query_iscore(addr)
    stake = service.get_stake(addr)
    delegation = service.get_delegation(addr)
    bond = service.get_bond(addr)
    #print(json.dumps(balance, indent=2))
    #print(json.dumps(stake, indent=2))
    #print(json.dumps(delegation, indent=2))
    #print(json.dumps(bond, indent=2))

    claimable = int(iscore['estimatedICX'], 0)
    staked, unstaking, remaining_blocks = sum_stake(stake)
    delegated, voting_power = sum_delegation(delegation)
    bonded, unbonding, _ = sum_bond(bond)
    asset = balance+claimable+staked+unstaking

    entries = []
    if asset > 0 :
        entries += [
            [ 'BALANCE', balance, balance/asset ],
            [ 'CLAIMABLE', claimable, claimable/asset ],
        ]
        if unstaking > 0:
            remaining_time = timedelta(seconds=remaining_blocks*2)
            entries += [
                [ 'UNSTAKE', unstaking, unstaking/asset, f'{remaining_time}'],
            ]
        if staked > 0:
            entries += [
                [ 'STAKED', staked, staked/asset ],
                [ '- DELEGATED', delegated, delegated/staked ],
                [ '- BONDED', bonded, bonded/staked ],
                [ '- UNBONDING', unbonding, unbonding/staked ],
                [ '- REMAINS', voting_power, voting_power/staked ],
            ]
    entries += [
        [ 'ASSET', asset, 1.0 ],
    ]

    locale.setlocale(locale.LC_ALL, '')
    try :
        sym, price = upbit.getPrice('ICX')
    except:
        print(f'[!] FAIL to get price of ICX', file=sys.stderr)
        sym = 'ICX'
        price = 1

    columns = [
        Column(lambda x: x[0], 13, '{:13s}', "Name"),
        Column(lambda x: format_decimals(x[1],3), 20, '{:>16s} ICX', 'ICX'),
        Column(lambda x: x[1]*price//ICX, 16, f'{{:>12,}} {sym[:3]:3s}', sym),
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
    p.print_data(['PRICE', ICX, 0.0], reverse=True)

@click.command("auto")
@click.option("--stake", 'target', type=int, help="Amount to stake (negative for asset-X)")
@click.option("--noclaim", type=bool, is_flag=True)
@click.option('--preps', '-p', type=str, multiple=True)
@click.pass_obj
def stake_auto(ctx: dict, preps: List[str] = None, target: int = None,  noclaim: bool = False):
    service = AssetService()
    config: Config = ctx[CONTEXT_CONFIG]
    wallet: Wallet = ctx[CONTEXT_ASSET]
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
        iscore = service.query_iscore(wallet.address)
        claimable = int(iscore['estimatedICX'], 0)

    balance = service.get_balance(wallet.address)
    stakes = service.get_stake(wallet.address)
    delegation = service.get_delegation(wallet.address)
    voting_power = int(delegation['votingPower'], 0)
    staked, unstaking, _ = sum_stake(stakes)

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
        service.delegate_all(preps, wallet, 0)
    elif balance+unstaking < min_balance:
        print(f'[-] Staking LESS {(balance+unstaking-max_balance)/ICX:+.3f}', file=sys.stderr)
        if balance+unstaking+voting_power < min_balance:
            voting_power = max_balance-unstaking-balance
            service.delegate_all(preps, wallet, voting_power)
        target_balance = service.get_balance(wallet.address)
        target_balance += voting_power+unstaking
        service.stake_all(wallet, target_balance, stakes)
    else:
        service.delegate_all(preps, wallet, 0)

    delegation = service.get_delegation(wallet.address)
    stakes = service.get_stake(wallet.address)
    balance = service.get_balance(wallet.address)
    staked, unstaking, remaining_blocks = sum_stake(stakes)

    asset = claimable + balance + staked + unstaking
    remains = timedelta(seconds=remaining_blocks*2)

    locale.setlocale(locale.LC_ALL, '')
    try :
        sym, price = upbit.getPrice('ICX')
    except:
        sym = 'ICX'
        price = 1
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
    wallet: Wallet = ctx[CONTEXT_ASSET]
    delegations = service.get_delegation(wallet.get_address())
    call = CallBuilder(to=CHAIN_SCORE, method='getPReps').build()

    prep_info = service.service.call(call)
    prep_map = {}
    for prep in prep_info['preps']:
        prep_map[prep['address']] = prep

    print(f'[#] ADDRESS       : {wallet.get_address()}')
    for entry in delegations['delegations']:
        address = entry["address"]
        if address in prep_map:
            prep = prep_map[address]
            name = prep["name"]
        else:
            name = address
        value = int(entry["value"], 0)
        print(f'[#] {name[:20]:20} {address} : {format_decimals(value,3):>16s} ')

@click.group()
@click.option('--key_store', envvar='ICX_ASSET_KEY_STORE')
@click.pass_obj
def main(ctx: dict, key_store: str = None):
    '''
    Manage ICON assets (stake/delegation/claim...)
    '''
    if key_store is not None:
        ctx[CONTEXT_ASSET] = wallet.get_instance(key_store)
    else:
        ctx[CONTEXT_ASSET] = wallet.get_instance()


main.add_command(show_asset)
main.add_command(stake_auto)
main.add_command(show_delegation)