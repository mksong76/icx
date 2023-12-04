#!/usr/bin/env python3

import base64
import json
import sys
from hashlib import sha3_256
from os import path
from typing import Any, List, Optional, Union

import click
import coincurve
from iconsdk.builder.call_builder import CallBuilder
from iconsdk.builder.transaction_builder import CallTransactionBuilder

from .. import service, util, wallet
from ..config import CONTEXT_CONFIG, Config
from ..cui import Column, MapPrinter, Row, Header, RowPrinter
from ..network import CONTEXT_NETWORK

GRADE_TO_TYPE = {
    "0x0": "Main",
    "0x1": "Sub",
    "0x2": "Cand",
}

STATE_TO_STR = {
    "0x0": "None",
    "0x1": "Ready",
    "0x2": "Success",
    "0x3": "Failure",
}

STATUS_TO_STR = {
    "0x0": "Active",
    "0x1": "Unregistered",
    "0x2": "Disqualified",
    "0x3": "NotReady",
}

PENALTY_TO_STR = {
    "0x0": "None",
    "0x1": "Disqualified",
    "0x2": "LowProductivity",
    "0x3": "BlockValidation",
    "0x4": "NonVote",
}

PREPS_JSON="~/.preps.{network}.json"
P2P="p2p"
RPC="rpc"

CONTEXT_PREP_SEEDS='prep.seeds'
CONTEXT_PREP_STORE='prep.store'
CONFIG_PREP_SEEDS='prep.seeds'

def p2p_to_rpc(server: str) -> str:
    ip, port = tuple(server.split(':'))
    port = int(port, 0)+(9000-7100)
    return f'{ip}:{port}'

def server_to_ip(server: str) -> str:
    ip, _ = tuple(server.split(':'))
    return ip

def icon_getMainPReps() -> any:
    svc = service.get_instance()
    call = CallBuilder(to=util.CHAIN_SCORE, method='getMainPReps').build()
    return svc.call(call)

def get_service_with_rpc(server: str=None) -> service.Service:
    if server is not None:
        return service.get_instance(f'http://{server}/api/v3')
    else:
        return service.get_instance()

def icon_getPRep(addr: str, server: str=None, start: int=None, end: int=None, height: int=None) -> any:
    svc = get_service_with_rpc(server)
    params = { 'address':addr }
    if start is not None:
        params['startRanking'] = f'0x{start:x}'
    if end is not None:
        params['endRanking'] = f'0x{end:x}'
    call = CallBuilder(to=util.CHAIN_SCORE, method='getPRep', params=params, height=height).build()
    return svc.call(call)

def icon_getBonderList(addr: str, server: str = None, *, height: int=None) -> dict:
    svc = get_service_with_rpc(server)
    params = { 'address':addr }
    call = CallBuilder(to=util.CHAIN_SCORE, method='getBonderList', params=params, height=height).build()
    return svc.call(call)

def icon_getBond(addr: str, server: str = None, *, height: int=None) -> dict:
    svc = get_service_with_rpc(server)
    params = { 'address':addr }
    call = CallBuilder(to=util.CHAIN_SCORE, method='getBond', params=params, height=height).build()
    return svc.call(call)

def icon_getPReps(server: str = None, start: int = None, height: int = None) -> any:
    svc = get_service_with_rpc(server)
    params = None
    if start is not None:
        params = { "startRanking" : start }
    call = CallBuilder(to=util.CHAIN_SCORE, method='getPReps', params=params, height=height).build()
    return svc.call(call)

def node_inspect(server: str) -> any:
    return util.rest_get(f'http://{server}/admin/chain/icon_dex?informal=true')

def node_get_chain(server: str, timeout: float = 1.0) -> any:
    return util.rest_get(f'http://{server}/admin/chain', timeout=timeout)[0]

def node_get_version(server: str, timeout: float = 1.0) -> any:
    si = util.rest_get(f'http://{server}/admin/system', timeout=timeout)
    return si['buildVersion']

class PRep(dict):
    TMain = 'Main'
    TSub = 'Sub'
    TCand = 'Cand'

    def __new__(cls, *args: Any, **kwargs: Any) -> 'PRep':
        return super().__new__(cls, *args, **kwargs)

    def get_int(self, key: any) -> int:
        return int(self.get(key, '0'), 0)
    
    @property
    def grade(self) -> str:
        return GRADE_TO_TYPE[self.get('grade')]
    
    @property
    def power(self) -> int:
        return self.get_int('power')

    @property
    def bonded(self) -> int:
        return self.get_int('bonded')
    
    @property
    def bond_rate(self) -> float:
        voted = self.bonded+self.delegated
        if voted == 0:
            return 0.0
        return self.bonded*20/voted
    
    @property
    def voter_rate(self) -> float:
        return self.get_voter_rate(1000)
    
    COMMISSION_BASE = 10000
    def get_voter_rate(self, delegation: int) -> float:
        voterRate = self.COMMISSION_BASE-self.commission_rate
        voted = self.bonded+self.delegated+delegation
        power = min(self.bonded*20, voted)
        return power*voterRate/voted/self.COMMISSION_BASE

    @property
    def delegated(self) -> int:
        return self.get_int('delegated')

    @property
    def commission_rate(self) -> int:
        return self.get_int('commission_rate')
    
    @property
    def delegation_required(self) -> int:
        return self.delegated-(self.bonded*19)


@click.command('seeds')
@click.pass_obj
@click.argument('network', type=click.STRING, required=False)
@click.argument('server', nargs=-1)
@click.option('--delete', '-d', type=click.BOOL, is_flag=True, default=False)
def set_seed(obj: dict, network: str = None, delete: bool = None, server: List[str] = None):
    '''
    Manage seed server configurations for networks
    '''
    config: Config = obj[CONTEXT_CONFIG]
    prep_seeds: dict = config[CONFIG_PREP_SEEDS]

    if network is None:
        if len(prep_seeds) == 0:
            click.echo(f'No seed servers are registered')
            return
        columns = [
            Column(lambda name, info: name, 10, name='Name'),
            Column(lambda name, info: ",".join(info), 60, name='Seed servers'),
        ]
        printer = RowPrinter(columns)
        printer.print_separater()
        printer.print_header()
        printer.print_separater()
        for name, value in prep_seeds.items():
            printer.print_data(name, value)
            printer.print_separater()
        return

    if len(server) == 0:
        if network in prep_seeds:
            if delete:
                del prep_seeds[network]
                config[CONFIG_PREP_SEEDS] = prep_seeds
                click.echo(f'Seed servers for [{network}] is deleted')
            else:
                seeds: List[str] = prep_seeds[network]
                click.echo(f'Seed servers for [{network}] : {" ".join(seeds)}')
        else:
            click.secho(f'No seed servers for [{network}]', color='red', file=sys.stderr)
        return

    prep_seeds[network] = server
    config[CONFIG_PREP_SEEDS] = prep_seeds
    click.echo(f'Seed servers for [{network}] are set')

def load_prep_store(file: str):
    with open(file, "r") as fd:
        return json.load(fd)

def search_prep(prep_info:dict, key: str) -> any:
    preps = []
    for addr, prep in prep_info.items():
        if addr == key:
            return prep
        elif key in addr:
            preps.append(prep)
        elif prep.get('address', '') == key:
            return prep
        elif key in prep.get('address', ''):
            preps.append(prep)
        elif key in prep.get('p2p', ''):
            preps.append(prep)
        elif key.lower() in prep.get('name', '').lower():
            preps.append(prep)
    if len(preps) > 0:
        return preps[0]
    return None

def find_rpc(prep_info:dict) -> Union[str,None]:
    for _, prep in prep_info.items():
        if RPC in prep:
            return prep[RPC]
    return None

@click.command('get')
@click.pass_obj
@click.argument('key')
@click.option('--raw', is_flag=True)
@click.option('--bonders', is_flag=True)
@click.option('--height', type=str, default=None)
def get_prep(obj: dict, key: str, raw: bool, bonders: bool, height: str):
    '''
    Get PRep information
    '''
    prep_info = None
    try:
        prep_info = load_prep_store(obj[CONTEXT_PREP_STORE])
        rpc = find_rpc(prep_info)
    except:
        rpc = None

    if height is not None:
        height = int(height, 0)
    preps = icon_getPReps(rpc, height=height)['preps']

    if prep_info is None:
        prep_info = {}
        for prep in preps:
            prep_info[prep['nodeAddress']] = prep


    prep_index = None

    try :
        prep_index = int(key, 0)-1
    except:
        pass

    if prep_index is None:
        prep = search_prep(prep_info, key)
        prep_addr = None
        if 'address' in prep:
            prep_addr = prep['address']

        for idx in range(len(preps)):
            if preps[idx]['address'] == prep_addr:
                prep_index = idx
    else:
        while prep_index >= len(preps):
            preps += icon_getPReps(rpc, len(preps), height=height)['preps']
        prep_addr = preps[prep_index]['address']

    if prep_index is None:
        raise click.ClickException(f'fail to find PRep key={key}')

    prep_info:dict = icon_getPRep(prep_addr, rpc, height=height)

    bonds = {}
    if bonders:
        bonder_list:dict = icon_getBonderList(prep_addr, rpc, height=height)
        for bonder in bonder_list['bonderList']:
            bond = icon_getBond(bonder, rpc, height=height)
            bonds[bonder] = bond

    if raw :
        util.dump_json(prep_info)
        if bonders:
            util.dump_json(bonder_list)
            for bond in bonds.values():
                util.dump_json(bond)
    else:
        rows = [
            Header('PRep information', 40),
            Row(lambda obj: obj.get('address'), 42, '{}', 'Address'),
            Row(lambda obj: obj.get('name'), 20, '{}', 'Name'),
            Row(lambda obj: obj.get('city'), 10, '{}', 'City'),
            Row(lambda obj: obj.get('country'), 3, '{}', 'Country'),
            Row(lambda obj: obj.get('email'), 40, '{}', 'Email'),
            Row(lambda obj: obj.get('details'), 60, '{}', 'Details'),
            Row(lambda obj: obj.get('website'), 60, '{}', 'WebSite'),
            Row(lambda obj: obj.grade, 4, '{}', 'Grade'),
            Row(lambda obj: obj.get('nodeAddress'), 42, '{}', 'Node'),
            Row(lambda obj: obj.get('p2pEndpoint'), 40, '{}', 'P2P'),
            Header('Status', 6),
            Row(lambda obj: PENALTY_TO_STR[obj.get('penalty')], 20, '{}', 'Penalty'),
            Row(lambda obj: STATUS_TO_STR[obj.get('status')], 20, '{}', 'Status'),
            Row(lambda obj: int(obj.get('lastHeight'), 0), 10, '{:>}', 'LastHeight'),
            Row(lambda obj: util.format_decimals(obj.get('irep')), 40, '{:>40}', 'iRep'),
            Row(lambda obj: int(obj.get('irepUpdateBlockHeight'),0), 40, '{:>40,}', 'iRep-Height'),
            Row(lambda obj: obj.get_int('totalBlocks'), 40, '{:>40,}', 'Total Blocks'),
            Row(lambda obj: obj.get_int('validatedBlocks'), 40, '{:>40,}', 'Validated Blocks'),
            Header('Power', 5),
            Row(lambda obj: util.format_decimals(obj.bonded), 40, '{:>36} ICX', 'Bonded'),
            Row(lambda obj: util.format_decimals(obj.delegated), 40, '{:>36} ICX', 'Delegated'),
            Row(lambda obj: util.format_decimals(obj.power), 40, '{:>36} ICX', 'Power'),
        ]

        idx = 0
        for bonder, bond in bonds.items():
            for bb in bond['bonds']:
                if bb['address'] == prep_addr:
                    rows += [
                        Header(f'Bonder[{idx}]', 20),
                        Row(bonder, 42, '{:<42}', 'Address'),
                        Row(util.format_decimals(as_int(bb['value'])), 40, '{:>36} ICX', 'Bonded'),
                    ]
            idx += 1

        rows.append(Header('END', 3))
        MapPrinter(rows).print_data(PRep(prep_info))

@click.command("inspect")
@click.pass_obj
@click.argument('key')
def inspect_prep(obj: dict, key: str):
    '''
    Inspect PRep information
    '''
    prep_info = load_prep_store(obj[CONTEXT_PREP_STORE])
    prep = search_prep(prep_info, key)
    if prep is None:
        raise click.ClickException(f'Fail to find PRep with key={key}')
    if prep is None or RPC not in prep:
        raise click.ClickException(f'RPC endpoint is unknown for prep=[{prep["name"]}]')
    rpc = prep[RPC]
    inspection = node_inspect(rpc)
    util.dump_json(inspection)

def handlePReps(obj: dict, store: str):
    # ensure CONTEXT_PREP_STORE is set
    if store is None:
        if CONTEXT_NETWORK in obj:
            network = obj[CONTEXT_NETWORK]
        else:
            network = 'default'
        store = PREPS_JSON.format(network=network)
    obj[CONTEXT_PREP_STORE] = path.expanduser(store)

    # if network is specified, then SEEDs also need to be set
    if CONTEXT_NETWORK in obj:
        network: str = obj[CONTEXT_NETWORK]
        config: Config = obj[CONTEXT_CONFIG]
        prep_seeds: dict = config[CONFIG_PREP_SEEDS]

        if network in prep_seeds:
            obj[CONTEXT_PREP_SEEDS] = prep_seeds[network]

def parse_str_to_bytes(s: str) -> bytes:
    if s.startswith('0x'):
        hs = s[2:]
    else:
        hs = s
    try:
        return bytes.fromhex(hs)
    except:
        pass
    return base64.decodebytes(s.encode())

def pk_to_adddress(pk: coincurve.PublicKey) -> str:
    return f'hx{sha3_256(pk.format(compressed=False)[1:]).digest()[-20:].hex()}'

def find_prep(preps: list[dict], node: str) -> Optional[dict]:
    for prep in preps:
        if prep['nodeAddress'] == node:
            return prep
    return None

@click.command('regpubkey', help='Register public key of PRep')
@click.pass_obj
@click.argument('pubkey', nargs=-1)
def register_pubkey(obj: dict, pubkey: list[str]):
    svc = service.get_instance()

    call = CallBuilder(to=util.CHAIN_SCORE, method='getPReps').build()
    preps = svc.call(call)['preps']

    if len(pubkey) == 0:
        click.secho(f'{"PRep Address":42s} {"Node Address":42s} {"PRep Name":20s} {"Status"}', reverse=True)
        for prep in preps:
            if int(prep['power'],0) == 0:
                continue

            if int(prep['grade'],0) > 1:
                continue

            if 'hasPublicKey' in prep:
                has_pubkey = prep['hasPublicKey'] == '0x1'
            else:
                rpk = svc.call(CallBuilder(
                    to=util.CHAIN_SCORE,
                    method="getPRepNodePublicKey",
                    params={"address": prep["address"]},

                ).build())
                has_pubkey = rpk is not None

            # util.dump_json(prep)
            status = "OK" if has_pubkey else "NG"
            fg_color = 'bright_green' if has_pubkey else 'white' if prep['grade'] != '0x0' else 'bright_yellow'
            click.secho(f'{prep["address"]} {prep["nodeAddress"] if prep["nodeAddress"] != prep["address"] else "":42s} {prep["name"][0:20]:20s} {status}', fg=fg_color)
        return

    for k in pubkey:
        bs = parse_str_to_bytes(k)
        pk = coincurve.PublicKey(bs)
        addr = pk_to_adddress(pk)
        pk_bytes = pk.format()

        prep = find_prep(preps, addr)
        if prep is None:
            click.secho(f'IGNORE {k} ({addr}) : unknown key', fg='bright_black')
            continue
        prep_addr = prep["address"]

        if prep.get('hasPublicKey','0x0') == '0x1':
            click.secho(f'SKIP {k} ({addr}) : already set for {prep_addr}', fg='bright_black')
            continue

        call = CallBuilder(
            to=util.CHAIN_SCORE,
            method="getPRepNodePublicKey",
            params={"address": prep_addr},

        ).build()
        rpk = svc.call(call)
        if rpk is not None:
            rpk_bytes = parse_str_to_bytes(rpk)
            if rpk_bytes == pk_bytes:
                click.secho(f'SKIP {k} ({addr}) : already set for {prep_addr}', fg='bright_black')
            else:
                click.secho(f'ERROR {k} ({addr}) : mismatch for {prep_addr}', fg='bright_black')
            continue

        ks = wallet.get_instance()
        register_pubkey = CallTransactionBuilder(
                from_=ks.address,
                to=util.CHAIN_SCORE,
                method="registerPRepNodePublicKey",
                nid=svc.nid,
                params={
                    "address": prep_addr,
                    'pubKey': pk_bytes,
                    }).build()
        result = svc.estimate_and_send_tx(register_pubkey, ks)
        if result['status'] == 1:
            click.secho(f'SUCCESS {k} ({addr}) for {prep_addr}')
        else:
            click.secho(f'FAIL {k} ({addr}) for {prep_addr}', fg='bright_red')

def as_bool(v: Optional[str]) -> str:
    return "None" if v is None else "Yes" if int(v, 0) else "No"
def as_int(v: Optional[str], d: Optional[int] = None) -> Optional[int]:
    return d if v is None else int(v, 0)

PREP_COLUMNS = [
    Column(lambda n, p: n, 3, "{:3d}", "NO" ),
    Column(lambda n, p: p.grade, 4, "{:<4.4s}", "Type" ),
    Column(lambda n, p: p.get('name', ''), 18, "{:<18.18s}", "Name" ),
    Column(lambda n, p: p.get('country', ''), 3, "{:<3.3s}", "C.C" ),
    Column(lambda n, p: p.power//10**21, 12, "{:>11,d}k", "Power"),
    Column(lambda n, p: p.bond_rate*100, 7, "{:>6.2f}%", "Bond %"),
    Column(lambda n, p: p.get_voter_rate(1000)*100, 7, "{:>6.2f}%", "Voter %"),
    Column(lambda n, p: p.delegation_required//10**21, 12, "{:>11,d}k", "Delegation"),
    Column(lambda n, p: p.commission_rate/100, 10, "{:>9.2f}%", 'Commission'),
]
@click.command('list')
@click.option('--height', type=util.INT, help='Height for the block to call getPReps()')
@click.option('--all', is_flag=True, help='List all (including candidates, no power)')
@click.option("--raw", is_flag=True, help='Raw JSON output')
@click.option('--addr', is_flag=True, help='Include address of PRep')
@click.option('--voter', is_flag=True, help='Sort by voter power')
def list_preps(height: int = None, raw: bool = False, all: bool = False, addr: bool = False, voter: bool = False):
    '''
    List PReps
    '''
    res = icon_getPReps(None, height=height)
    if raw:
        util.dump_json(res)
        return
    preps: list[PRep] = list(map(lambda x: PRep(x), res['preps']))
    bh = as_int(res['blockHeight'])
    columns = PREP_COLUMNS
    if addr:
        columns = columns[:]
        columns.insert(3, Column(lambda n, p: p.get('address'), 42, '{:42s}', 'Address'))
    printer = RowPrinter(columns)
    printer.print_header()
    idx = 0
    main_count = 0
    sub_count = 0
    cand_count = 0
    if voter:
        preps.sort(key=lambda x: (x.voter_rate, -x.delegation_required), reverse=True)
    for prep in preps:
        idx += 1
        grade = prep.grade

        kwargs = {}
        if grade == PRep.TCand:
            kwargs['fg'] = 'bright_red'
            kwargs['bold'] = True
            cand_count += 1
        elif grade == PRep.TMain:
            kwargs['fg'] = 'bright_blue'
            main_count += 1
        else:
            sub_count += 1

        if grade == PRep.TCand and prep.power == 0 and not all:
            continue

        printer.print_data(idx, prep, **kwargs)
    printer.print_row([
        (1, f'{len(preps):>3d}'),
        (printer.columns-1, f'Main:{main_count} Sub:{sub_count} Cand:{cand_count}'),
    ], reverse=True)