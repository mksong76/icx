#!/usr/bin/env python3

from .. import service, util
from iconsdk.builder.call_builder import CallBuilder

GRADE_TO_TYPE = {
    "0x0": "Main",
    "0x1": "Sub",
    "0x2": "Cand",
}

PREPS_JSON="~/.preps.json"
P2P="p2p"
RPC="rpc"

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

def icon_getPReps(server: str = None) -> any:
    if server is not None:
        svc = service.get_instance(f'http://{server}/api/v3')
    else:
        svc = service.get_instance()
    call = CallBuilder(to=util.CHAIN_SCORE, method='getPReps').build()
    return svc.call(call)

def node_inspect(server: str) -> any:
    return util.rest_get(f'http://{server}/admin/chain/icon_dex?informal=true')

def node_get_chain(server: str, timeout: float = 1.0) -> any:
    return util.rest_get(f'http://{server}/admin/chain', timeout=timeout)[0]

def node_get_version(server: str, timeout: float = 1.0) -> any:
    si = util.rest_get(f'http://{server}/admin/system', timeout=timeout)
    return si['buildVersion']
