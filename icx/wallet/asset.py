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
from ..util import CHAIN_SCORE, ICX, ensure_address
from . import wallet

CONFIG_TARGET_BALANCES = "target_balances"
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

        print(f'[!] Stake ADJUST change={change/ICX:.3f} to={target/ICX:.3f}', file=sys.stderr)

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

    def delegate_all(self, wallet: Wallet, target: int = 0, delegation: dict = None):
        if delegation is None:
            delegation = self.get_delegation(wallet.get_address())

        voting_power = int(delegation['votingPower'], 0)
        change =  voting_power - target
        if change == 0:
            return
        print(f'[!] Delegate ADJUST change={change/ICX:.3f}', file=sys.stderr)

        total_power = change + int(delegation['totalDelegated'], 0)
        delegation_count = len(delegation['delegations'])
        if delegation_count == 0:
            raise Exception(f'NoCurrentDelegation')
        new_delegations = []
        power = (total_power+delegation_count-1)//delegation_count
        for entry in delegation['delegations']:
            if total_power < power:
                power = total_power
            total_power -= power
            new_delegations.append({
                "address": entry["address"],
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

def get_target_balance(config: Config, addr: str, balance: int = 0) -> int:
    balances = config[CONFIG_TARGET_BALANCES]
    if addr in balances:
        return balances[addr]
    else:
        return balance

def set_target_balance(config: Config, addr: str, balance: int):
    balances = config[CONFIG_TARGET_BALANCES]
    if addr not in balances or balances[addr] != balance:
        balances[addr] = balance
        config[CONFIG_TARGET_BALANCES] = balances


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
    staked, unstaking, _ = sum_stake(stake)
    delegated, voting_power = sum_delegation(delegation)
    bonded, unbonding, _ = sum_bond(bond)
    asset = balance+claimable+staked+unstaking

    entries = []
    if asset > 0 :
        entries.append([ 'BALANCE', balance, balance/asset ])
        if staked > 0:
            entries += [
                [ 'STAKED', staked, staked/asset ],
                [ '- DELEGATED', delegated, delegated/staked ],
                [ '- BONDED', bonded, bonded/staked ],
                [ '- UNBONDING', unbonding, unbonding/staked ],
                [ '- REMAINS', voting_power, voting_power/staked ],
            ]
        entries += [
            [ 'UNSTAKE', unstaking, unstaking/asset ],
            [ 'CLAIMABLE', claimable, claimable/asset ],
        ]
    entries += [
        [ 'ASSET', asset, 1.0 ],
        [ 'PRICE', ICX, 0.0 ]
    ]

    locale.setlocale(locale.LC_ALL, '')
    try :
        sym, price = upbit.getPrice('ICX')
    except:
        print(f'[!] FAIL to get price of ICX', file=sys.stderr)
        sym = 'ICX'
        price = 1

    print(f'[#] ADDRESS       : {addr}')
    for entry in entries:
        print(f'[#] {entry[0]:13s} : {entry[1]//ICX:12,}.{entry[1]%ICX*1000//ICX:03d} ICX {entry[1]*price//ICX:12,} {sym} {entry[2]*100:7.3f}%')

@click.command("auto")
@click.option("--balance", type=int, help="Minimum balance to maintain", envvar="ICX_ASSET_BALANCE")
@click.option("--noclaim", type=bool, is_flag=True)
@click.pass_obj
def stake_auto(ctx: dict, balance: int = None, noclaim: bool = False):
    service = AssetService()
    config: Config = ctx[CONTEXT_CONFIG]
    wallet: Wallet = ctx[CONTEXT_ASSET]
    if balance is None:
        balance = get_target_balance(config, wallet.get_address())
    else:
        set_target_balance(config, wallet.get_address(), balance)

    min_balance = balance*ICX + ICX
    max_balance = min_balance + ICX

    print(f'[#] Target min={min_balance/ICX:.2f} max={max_balance/ICX:.3f}', file=sys.stderr)

    iscore = service.query_iscore(wallet.address)
    claimable = int(iscore['estimatedICX'], 0)
    if claimable >= ICX and not noclaim:
        print(f'[!] Claim claimable={claimable/ICX:.3f}', file=sys.stderr)
        service.claim_iscore(wallet)
        iscore = service.query_iscore(wallet.address)
        claimable = int(iscore['estimatedICX'], 0)
    #print(json.dumps(iscore, indent=2))

    balance = service.get_balance(wallet.address)
    stakes = service.get_stake(wallet.address)
    delegation = service.get_delegation(wallet.address)
    voting_power = int(delegation['votingPower'], 0)
    _, unstaking, _ = sum_stake(stakes)
    if balance+unstaking > max_balance:
        print(f'[-] Staking MORE for {(balance+unstaking-max_balance)/ICX:.3f}', file=sys.stderr)
        service.stake_all(wallet, max_balance, stakes)
        service.delegate_all(wallet, 0)
    elif balance+unstaking < min_balance:
        print(f'[-] Staking LESS for {(max_balance-balance-unstaking)/ICX:.3f}',file=sys.stderr)
        if balance+unstaking+voting_power < min_balance:
            voting_power = max_balance-unstaking-balance
            service.delegate_all(wallet, voting_power)
        target_balance = service.get_balance(wallet.address)
        target_balance += voting_power+unstaking
        service.stake_all(wallet, target_balance, stakes)
    else:
        service.delegate_all(wallet, 0)

    delegation = service.get_delegation(wallet.address)
    stakes = service.get_stake(wallet.address)
    balance = service.get_balance(wallet.address)
    staked, unstaking, remaining_blocks = sum_stake(stakes)

    asset = claimable + balance + staked + unstaking
    remains = timedelta(seconds=remaining_blocks*2)

    locale.setlocale(locale.LC_ALL, '')
    sym, price = upbit.getPrice('ICX')
    krw = (asset//ICX)*price
    print(f'[#] Asset={(asset/ICX):.3f} ( x {price:n} = {krw:n} {sym})', file=sys.stderr)
    print(f'[#] Balance={balance/ICX:.3f} ' +
          f'Claimable={claimable/ICX:.3f} ' +
          f'Staked={staked/ICX:.3f} ' +
          f'Unstaking={unstaking/ICX:.3f} ({remains})',
          file=sys.stderr)

@click.group()
@click.option('--key_store', envvar='ICX_ASSET_KEY_STORE')
@click.pass_obj
def main(ctx: dict, key_store: str = None):
    if key_store is not None:
        ctx[CONTEXT_ASSET] = wallet.get_instance(key_store)
    else:
        ctx[CONTEXT_ASSET] = wallet.get_instance()


main.add_command(show_asset)
main.add_command(stake_auto)
