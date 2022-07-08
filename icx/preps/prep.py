#!/usr/bin/env python3

from .. import service, util
from iconsdk.builder.call_builder import CallBuilder

GRADE_TO_TYPE = {
    "0x0": "Main",
    "0x1": "Sub",
    "0x2": "Cand",
}

PREPS_JSON=".preps.json"

def icon_getMainPReps() -> any:
    svc = service.get_instance()
    call = CallBuilder(to=util.CHAIN_SCORE, method='getMainPReps').build()
    return svc.call(call)

def icon_getPReps() -> any:
    svc = service.get_instance()
    call = CallBuilder(to=util.CHAIN_SCORE, method='getPReps').build()
    return svc.call(call)

def node_inspect(addr: str) -> any:
    return util.rest_get(f'http://{addr}:9000/admin/chain/icon_dex?informal=true')

def node_get_chain(ip: str) -> any:
    return util.rest_get(f'http://{ip}:9000/admin/chain')[0]

def node_get_version(ip: str) -> any:
    si = util.rest_get(f'http://{ip}:9000/admin/system')
    return si['buildVersion']
