#!/usr/bin/env python

import datetime
import json
from concurrent import futures
import os

import click
from iconsdk.builder.call_builder import CallBuilder

from .. import service
from ..util import CHAIN_SCORE, format_decimals
from . import semanticversion
from .prep import *

NO_IP='-'

class PRep:
    def __init__(self, prep) -> None:
        self.prep = prep
        self.futures = []

PENALTY_REASON_TO_CHECK = {
    JailFlag.Unjailing: "UnJa",
    JailFlag.DoubleSign: "DblS",
    JailFlag.LowProductivity: "LowP",
}

def candidate_reason_of_prep(prep: dict) -> Optional[str]:
    if prep.get('hasPublicKey') == '0x0':
        return 'NoPk'
    penalty = prep.get('penalty')
    if  penalty is None or penalty == '0x0':
        return None
    jail_flags = as_int(prep.get('jailFlags'))
    if jail_flags is None or jail_flags == 0:
        return PENALTY_TO_STR[penalty]
    flags = list(JailFlag.from_flags(jail_flags))
    for flag, reason in PENALTY_REASON_TO_CHECK.items():
        if flag in flags:
            return reason
    return PENALTY_TO_STR[penalty]

def type_of_prep(prep: dict) -> str:
    grade = prep['grade']
    if grade == '0x2':
        reason = candidate_reason_of_prep(prep)
        if reason is not None:
            return reason[0:4]
    return GRADE_TO_TYPE[grade]

@click.command('status')
@click.pass_obj
@click.option('--version', type=str)
@click.option("--timeout", type=click.FLOAT, default=1.5)
def show_status(obj: dict, version: str, timeout: float):
    '''
    Show status of connected servers from SEED servers
    '''
    store = obj[CONTEXT_PREP_STORE]
    #-------------------------------------------------------------------------------
    #   IP정보를 읽어 들인다.
    #
    fd = open(os.path.expanduser(store), "r")
    prep_info: dict = json.load(fd)
    fd.close

    #-------------------------------------------------------------------------------
    #   기록된 첫번째 서버의 RPC포트를 이용한다.
    rpc = None
    uri = None
    for prep in prep_info.values():
        if RPC in prep:
            rpc = prep[RPC]
            uri = f'http://{rpc}/api/v3'
            break

    #-------------------------------------------------------------------------------
    #   현재 Term정보
    #
    svc = service.get_instance(uri)
    iiss_info = svc.call(CallBuilder(to=CHAIN_SCORE, method="getIISSInfo").build())
    next_term = int(iiss_info['nextPRepTerm'], 0)

    net_info = svc.call(CallBuilder(to=CHAIN_SCORE, method="getNetworkInfo").build())
    main_preps = int(net_info['mainPRepCount'], 0)
    sub_preps = int(net_info['subPRepCount'], 0)
    total_preps = main_preps+sub_preps

    #-------------------------------------------------------------------------------
    #   현재의 prep정보(등급)을 가지고 있습니다.
    #
    preps = icon_getPReps(rpc)['preps']

    #-------------------------------------------------------------------------------
    #   getChain 과 getVersion을 모든 PREP들에게 호출한다.
    #
    now=datetime.datetime.now()
    idx=0
    items=[]
    results=[]
    executor = futures.ThreadPoolExecutor()
    for prep in preps:
        addr = prep['address']
        if 'nodeAddress' in prep:
            addr = prep['nodeAddress']
        if addr not in prep_info:
            if prep['grade'] == '0x1':
                items.append(PRep(None))
                continue
            else:
                items.append(PRep({
                    'name': prep['name'],
                    'type': type_of_prep(prep),
                    'power': int(prep['power'], 0),
                    'ip': NO_IP,
                }))
                continue

        info = prep_info[addr]
        if P2P not in info:
            if int(prep['power'], 0) > 0:
                items.append(PRep({
                    'name': prep['name'],
                    'type': type_of_prep(prep),
                    'power': int(prep['power'], 0),
                    'ip': NO_IP,
                }))
            else:
                items.append(PRep(None))
            continue

        item = PRep({
            'name': prep['name'],
            'type': type_of_prep(prep),
            'power': int(prep['power'], 0),
            'ip': server_to_ip(info[P2P]),
        })
        if RPC in info:
            server = info[RPC]
            future = executor.submit(node_get_chain, server, timeout=timeout)
            results.append(future)
            item.futures.append(future)
            future = executor.submit(node_get_version, server, timeout=timeout)
            results.append(future)
            item.futures.append(future)
        else:
            pass
        items.append(item)
    futures.as_completed(results)

    #-------------------------------------------------------------------------------
    #   최근 버전, 높이를 구한다.
    #

    top_height=0
    last_version=None
    for item in items:
        try:
            item.chain = item.futures[0].result()
            if 'height' in item.chain:
                height = item.chain['height']
                if height > top_height:
                    top_height = height
            item.version = item.futures[1].result()
            if semanticversion.is_lower_version(last_version, item.version):
                last_version = item.version
        except:
            item.chain = None
            item.version = "unknown"

    version_check = last_version
    if version is not None:
        version_check = version

    #-------------------------------------------------------------------------------
    #   화면출력
    #
    click.secho(f' {"NO":3s}| {"Name":18s} {"Grade":6s}| {"IP":15s} | {"Power":>8s} | {"Version":16s} | {"Status":16s}', reverse=True, bold=True)
    GC='\033[2m'
    GC='\033[2m'
    WC='\033[31;1m'
    IC='\033[32;1m'
    MC='\033[33;1m'
    BC='\033[34;1m'
    NC='\033[0m'
    STATUS_FORMAT=f'[%3d] %-18s (%4s): %-15s : %8s '
    NOPOWER_FORMAT=click.style(STATUS_FORMAT, fg='white', dim=True)
    CAND_FORMAT=click.style(STATUS_FORMAT, fg='red', bold=True)
    POWER_NOIP_FORMAT=click.style(STATUS_FORMAT, fg='red')
    MAIN_FORMAT=click.style(STATUS_FORMAT, fg='blue', bold=True)
    idx=0
    late_nodes=0
    updated_main=0
    updated_nodes=0
    all_nodes=0
    main_nodes=0
    for item in items:
        if item.prep is None:
            idx += 1
            continue

        args = (idx+1, item.prep['name'][:18], item.prep['type'], item.prep['ip'], format_decimals(item.prep['power']//10**3,0)+'k')
        has_power = item.prep['power'] > 0
        has_ip = item.prep['ip'] == NO_IP
        if item.prep['type'] == 'Main':
            format = MAIN_FORMAT
            main_nodes += 1
        elif item.prep['type'] != 'Sub' and has_power and idx < total_preps:
            format = CAND_FORMAT
        else:
            if has_power:
                if item.prep['ip'] == NO_IP:
                    format = POWER_NOIP_FORMAT
                else:
                    format = STATUS_FORMAT
            else:
                format = NOPOWER_FORMAT

        if item.chain is None:
            format += ': %s'
            args += (f'{MC}FAIL{NC}',)
        else:
            all_nodes += 1
            if version_check is None:
                format += ': %-7s '
                args += (item.version,)
            elif semanticversion.is_lower_version(item.version, version_check):
                format += f': {WC}%-16s{NC} '
                args += (item.version,)
            else:
                format += f': {IC}%-16s{NC} '
                args += ('[OK]',)
                updated_nodes+=1
                if item.prep['type'] == 'Main':
                    updated_main += 1

            if 'height' in item.chain and 'state' in item.chain:
                height = item.chain['height']
                state = item.chain['state']
                if height < top_height-2:
                    format += f': {WC}%8d %s{NC} (%d)'
                    args += (height, state, height-top_height)
                    late_nodes += 1
                else:
                    format += f': %8d %s'
                    args += (height, state)

        print(format%args)
        idx += 1
    format='Late: %d / %d'
    args=(late_nodes, all_nodes)

    time_next = now + datetime.timedelta(seconds=(next_term-top_height)*2)
    format+=' | NextTerm: %d / %s'
    args+=(next_term, str(time_next.strftime('%H:%M:%S')))
    if version_check is not None:
        update_status = 'Safe'
        if updated_main < main_nodes*1/3:
            update_status = 'Minor'
        elif updated_main < main_nodes*2/3:
            update_status = 'Unsafe'

        format+=' | %s Updated: %d(%d) / %d(%d) / %s'
        args+=(version_check, updated_main, main_nodes, updated_nodes, all_nodes, update_status)
    click.secho(f' {(format%args):95s} ', reverse=True, bold=True)
