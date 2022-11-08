#!/usr/bin/env python3

import json
import os
import re
import sys
import threading
from os import link
from typing import  Dict, List, Tuple

import click
from iconsdk.builder.call_builder import CallBuilder

from . import duration
from .prep import *

SEED_SERVERS = [ "52.196.159.184:7100" ]

class PReps:
    def __init__(self, file: str = None):
        if file is None:
            self.preps = {}
        else:
            self.preps = json.load(file)
        self.cid = None

    def preps_get(self, addr: str, add: bool = True) -> Dict:
        if addr not in self.preps:
            if not add:
                return None
            entry = {}
            self.preps[addr] = entry
        else:
            entry = self.preps[addr]
        return entry

    def preps_update_p2p(self, current: str, addr: str, p2p: str, add: bool = True, type: str = None) -> bool:
        prep = self.preps_get(addr, add)
        if prep is None:
            return False
        if type is not None:
            if 'type' not in prep or type != prep['type']:
                print(f'[{current}] INSPECT INVALID_TYPE addr={addr} p2p={p2p} know={type}', file=sys.stderr)
        if P2P in prep:
            if prep[P2P] != p2p:
                print(f"[{current}] CONFLICT {addr} old={prep[P2P]} new={p2p}", file=sys.stderr)
            return False
        #print(addr, ip, file=sys.stderr)
        prep[P2P] = p2p
        return True

    def preps_apply_map(self, current: str, addr_map: dict, type: str = None) -> list:
        ips = []
        for ip, key_addr in addr_map.items():
            if key_addr == "":
                continue
            if self.preps_update_p2p(current, key_addr, ip, True, type):
                ips.append(ip)
        return ips

    def preps_apply_list(self, current: str, addr_list: list) -> list:
        ips = []
        for item in addr_list:
            ip = item['addr']
            if self.preps_update_p2p(current, item['id'], ip, True):
                ips.append(ip)
        return ips

    def preps_get_links(self, name: str, addr: str) -> Dict[str,List[float]]:
        prep = self.preps_get(addr)
        if 'name' not in prep:
            return None
        if name not in prep:
            prep[name] = {}
        return prep[name]

    def preps_add_link(self, name: str, addr1: str, addr2: str, rtt: float):
        if addr1 > addr2:
            addr1, addr2 = addr2, addr1
        links = self.preps_get_links(name, addr1)
        links2 = self.preps_get_links(name, addr2)
        if links is None or links2 is None:
            return

        if addr2 not in links:
            links[addr2] = [rtt]
        else:
            links[addr2].append(rtt)

    def preps_add_conn(self, name: str, addr: str, conn):
        RTT_REGEX=re.compile(r'{last:(?P<last>.+),avg:(?P<avg>.+)}')
        rtt = 1.0
        if 'rtt' in conn:
            m = RTT_REGEX.match(conn['rtt'])
            if m:
                rtt = duration.time_to_ms(m.group('avg'))
        self.preps_add_link(name, addr, conn['id'], rtt)

    def analyze_server(self, server, src):
        rpc = p2p_to_rpc(server)
        print(f"INSPECTING {rpc}", file=sys.stderr)
        try:
            info = node_inspect(rpc)
        except:
            return

        if self.cid is None:
            self.cid = info['cid']
            print(f'[{server}] SET NETWORK cid={info["cid"]}')
        else:
            if self.cid != info['cid']:
                print(f'[{server}] DIFFERENT NETWORK cid={info["cid"]} from={src}')
                return

        p2p = info["module"]["network"]["p2p"]
        addr = p2p['self']['id']

        self.preps_update_p2p(server, addr, p2p['self']['addr'], True)
        prep = self.preps_get(addr)
        prep[RPC] = rpc

        if 'roots' in p2p:
            founds = self.preps_apply_map(server, p2p['roots'], 'Main')
            for ip in founds:
                self.inspect_server(ip, f'{server}:roots')
        if 'seeds' in p2p:
            founds = self.preps_apply_map(server, p2p['seeds'])
            for ip in founds:
                self.inspect_server(ip, f'{server}:seeds')

        for name in ['friends', 'uncles', 'children', 'nephews']:
            if name in p2p:
                founds = self.preps_apply_list(server, p2p[name])
                for ip in founds:
                    self.inspect_server(ip, f'{server}:{name}')
                for conn in p2p[name]:
                    self.preps_add_conn('links', addr, conn)

        # for name in ['orphanages']:
        #     if name in p2p:
        #         for conn in p2p[name]:
        #             self.preps_add_conn('orphanages', addr, conn)

        if 'parent' in p2p:
            parent = p2p['parent']
            if parent and 'id' in parent:
                self.preps_add_conn('links', addr, parent)

    def update_preps(self, seed: List[str]):
        if len(seed) == 0:
            raise Exception("No seed information")
        server = p2p_to_rpc(seed[0])
        main_prep_info = icon_getPReps(server)
        idx = 0
        for prep in main_prep_info['preps']:
            if 'nodeAddress' in prep:
                addr = prep['nodeAddress']
            else:
                addr = prep['address']

            entry = self.preps_get(addr)
            entry["type"] = GRADE_TO_TYPE[prep['grade']]
            entry["name"] = prep["name"]
            entry['country'] = prep['country']
            entry['power'] = int(prep['power'], 0)
            if idx < 22:
                entry['grade'] = 'Main'
            elif idx < 100:
                entry['grade'] = 'Sub'
            else:
                entry['grade'] = 'Cand'
            idx += 1

        self.threads: List[threading.Thread]=[]
        for server in seed:
            self.inspect_server(server, 'seed')

        while len(self.threads)>0:
            th = self.threads.pop(0)
            th.join()

    def inspect_server(self, ip:str, src:str):
        th = threading.Thread(target=self.analyze_server, args=[ip, src])
        self.threads.append(th)
        th.start()

    def dump(self, file: str):
        with open(file, "w") as fd:
            print(json.dumps(self.preps, indent=2), file=fd)

@click.command('update')
@click.pass_obj
@click.argument('server', nargs=-1)
def update_preps_json(obj: dict, server: List[str], store: str):
    store = obj[PREP_STORE]
    preps = PReps()
    if len(server) == 0:
        server = SEED_SERVERS
    preps.update_preps(server)
    preps.dump(os.path.expanduser(store))
