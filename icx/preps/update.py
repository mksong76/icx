#!/usr/bin/env python3

import json
import os
import re
import sys
import threading
from os import link
from typing import  Dict, List

import click
from iconsdk.builder.call_builder import CallBuilder

from . import duration
from .prep import *

SEED_SERVERS = [ "52.196.159.184" ]

def p2p_to_ip(p2p: str) -> str:
    ip, port = tuple(p2p.split(':'))
    return ip

class PReps:
    def __init__(self, file: str = None):
        if file is None:
            self.preps = {}
        else:
            self.preps = json.load(file)

    def preps_get(self, addr: str, add: bool = True) -> Dict:
        if addr not in self.preps:
            if not add:
                return None
            entry = {}
            self.preps[addr] = entry
        else:
            entry = self.preps[addr]
        return entry

    def preps_update_ip(self, current: str, addr: str, ip: str, add: bool = True, type: str = None) -> bool:
        prep = self.preps_get(addr, add)
        if prep is None:
            return False
        if type is not None:
            if 'type' not in prep or type != prep['type']:
                print(f'[{current}] INSPECT INVALID_TYPE addr={addr} ip={ip}', file=sys.stderr)
        if 'ip' in prep:
            if prep['ip'] != ip:
                print(f"[{current}] CONFLICT {addr} old={prep['ip']} new={ip}", file=sys.stderr)
            return False
        #print(addr, ip, file=sys.stderr)
        prep['ip'] = ip
        return True

    def preps_apply_map(self, current: str, addr_map: dict, type: str = None) -> list:
        ips = []
        for net_addr, key_addr in addr_map.items():
            if key_addr == "":
                continue
            ip = p2p_to_ip(net_addr)
            if self.preps_update_ip(current, key_addr, ip, True, type):
                ips.append(ip)
        return ips

    def preps_apply_list(self, current: str, addr_list: list) -> list:
        ips = []
        for item in addr_list:
            ip = p2p_to_ip(item['addr'])
            if self.preps_update_ip(current, item['id'], ip, True):
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

    def analyze_server(self, server):
        print(f"INSPECTING {server}", file=sys.stderr)
        try:
            info = node_inspect(server)
        except:
            return

        p2p = info["module"]["network"]["p2p"]
        addr = p2p['self']['id']

        self.preps_update_ip(server, addr, p2p_to_ip(p2p['self']['addr']), True)
        prep = self.preps_get(addr)

        if 'roots' in p2p:
            founds = self.preps_apply_map(server, p2p['roots'], 'Main')
            for ip in founds:
                self.inspect_server(ip)
        if 'seeds' in p2p:
            founds = self.preps_apply_map(server, p2p['seeds'])
            for ip in founds:
                self.inspect_server(ip)

        for name in ['friends', 'uncles', 'children', 'nephews']:
            if name in p2p:
                founds = self.preps_apply_list(server, p2p[name])
                for ip in founds:
                    self.inspect_server(ip)
                for conn in p2p[name]:
                    self.preps_add_conn('links', addr, conn)

        for name in ['orphanages']:
            if name in p2p:
                for conn in p2p[name]:
                    self.preps_add_conn('orphanages', addr, conn)

        if 'parent' in p2p:
            parent = p2p['parent']
            if parent and 'id' in parent:
                self.preps_add_conn('links', addr, parent)

    def update_preps(self, seed: List[str]):
        main_prep_info = icon_getPReps()
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
            self.inspect_server(server)

        while len(self.threads)>0:
            th = self.threads.pop(0)
            th.join()

    def inspect_server(self, ip:str):
        th = threading.Thread(target=self.analyze_server, args=[ip])
        self.threads.append(th)
        th.start()

    def dump(self, file: str):
        with open(file, "w") as fd:
            print(json.dumps(self.preps, indent=2), file=fd)

@click.command('update')
@click.argument('server', nargs=-1)
@click.option('--output', type=str, default=PREPS_JSON)
def update_preps_json(server: List[str], output: str):
    preps = PReps()
    if len(server) == 0:
        server = SEED_SERVERS
    preps.update_preps(server)
    preps.dump(output)
