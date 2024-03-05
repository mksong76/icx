#!/usr/bin/env python3

from collections.abc import Iterable
from concurrent import futures
import json
import sys
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, ParseResult

import click

from .network import CONTEXT_NETWORK, CONTEXT_NODE_SEED
from . import service, util

P2P_TO_RPC = {
    7100: 9000,
    7120: 9020,
}

def is_private_ip(host: str) -> bool:
    ip = list(map(lambda x: int(x), host.split('.')))
    return ip[0] == 10 \
        or (ip[0] == 172 and ip[1] >= 16 and ip[1] <= 31) \
        or (ip[0] == 192 and ip[1] == 168) \
        or ip[0] == 127

def is_private_p2p(p2p: str) -> bool:
    host, _ = p2p.split(':')
    return is_private_ip(host)


class Inspection(dict):
    def __new__(cls, mapping, **kwargs):
        obj = super().__new__(cls, mapping, **kwargs)
        return obj

    @property
    def cid(self) -> str:
        return self['cid']

    @property
    def channel(self) -> str:
        return self['channel']

    @property
    def p2p(self) -> str:
        return self['module']['network']['p2p']['self']['addr']

    @property
    def id(self) -> str:
        return self['module']['network']['p2p']['self']['id']

class Node:
    def __init__(self, host: str, p2p_port: int, uri: str = None) -> None:
        self.__host = host
        self.__p2p_port = p2p_port
        self.__uri = uri
        self.__channel_info: Dict[str,dict] = None
        self.__inspections: Dict[str,Inspection] = {}

    @staticmethod
    def from_p2p(p2p: str, uri: Optional[str] = None) -> 'Node':
        host, port = p2p.split(':')
        return Node(host, int(port, 0), uri=uri)

    def get_p2p(self) -> str:
        return self.p2p

    @property
    def p2p(self) -> str:
        return f'{self.__host}:{self.__p2p_port}'

    @property
    def is_private(self) -> bool:
        return is_private_ip(self.__host)

    def __str__(self) -> str:
        return self.p2p

    def set_uri(self, uri: str):
        if self.__channel_info is not None:
            raise Exception('channel information already has queried')
        self.__uri = uri

    def get_uri(self) -> str:
        if self.__uri is None:
            if self.__p2p_port in P2P_TO_RPC:
                rpc_port = P2P_TO_RPC[self.__p2p_port]
            else:
                rpc_port = self.__p2p_port+1900

            self.__uri = f'http://{self.__host}:{rpc_port}'
        return self.__uri
    
    def get_url(self, path='') -> str:
        uri = self.get_uri()
        return f'{uri}{path}'

    def get_rpc(self, cid: str):
        name = self.get_channel_name_for_cid(cid)
        return self.get_url(f'/api/v3/{name}')

    def get_channel_info(self) -> Dict[str,any]:
        if self.__channel_info is None:
            channels: List[dict] = util.rest_get(self.get_url('/admin/chain'))
            channel_info = {}
            for channel in channels:
                channel_info[channel['cid']] = channel
            self.__channel_info = channel_info
        return self.__channel_info

    def get_cids(self) -> List[str]:
        return self.get_channel_info().keys()

    def is_valid_cid(self, cid: str):
        return cid in self.get_channel_info()

    def get_cid_of(self, name: str) -> str:
        info = self.get_channel_info()
        for cid, cinfo in info.items():
            if cinfo['channel'] == name:
                return cid
        return None

    def get_channel_name_for_cid(self, cid: str) -> str:
        info = self.get_channel_info()
        if cid not in info:
            return None
        return info[cid]["channel"]

    def inspect(self, cid: str, **kwargs) -> any:
        channel = self.get_channel_name_for_cid(cid)
        if channel is None:
            raise Exception(f'there is no channel with cid={cid}')
        try:
            url = self.get_url(f'/admin/chain/{channel}')
            return util.rest_get(url, **kwargs)
        except BaseException as exc:
            raise Exception(f'fail to GET url={url}') from exc

    def get_inspection(self, cid: str, **kwargs) -> Inspection:
        if not self.is_valid_cid(cid):
            raise Exception(f'invalid cid={cid}')
        if cid not in self.__inspections:
            self.do_update_inspection(cid, **kwargs)
        return self.__inspections[cid]

    def add_inspection(self, inspection: Inspection):
        cid = inspection.cid
        # if not self.is_valid_cid(cid):
        #     raise Exception(f'invalid cid={cid}')
        self.__inspections[cid] = inspection

    def has_inspection(self, cid: str) -> bool:
        return cid in self.__inspections

    def update_inspection(self, cid: str, **kwargs):
        if not self.is_valid_cid(cid):
            raise Exception(f'invalid cid={cid}')
        self.do_update_inspection(cid, **kwargs)

    def do_update_inspection(self, cid: str, **kwargs):
        inspection = Inspection(self.inspect(cid, **kwargs))
        if inspection.cid != cid:
            raise Exception(f'inspection has cid={inspection.cid} but requested cid={cid}')
        self.__inspections[cid] = inspection

class Problem(tuple):
    def __new__(cls, *args) -> 'Problem':
        return super().__new__(cls, args)

    @property
    def color(self) -> str:
        return self[0]
    
    @property
    def reason(self) -> any:
        return self[1]

class NetworkInformation:
    def __init__(self, cid: str, verbose: bool = False, public_only: bool = False) -> None:
        self.cid = cid
        self.verbose = verbose
        self.public_only = public_only
        self.p2pToNode: Dict[str,Node] = {}
        self.idToNode: Dict[str,List[Tuple[Node]]] = {}
        self.inspectingQueue  = []
        self.executor = futures.ThreadPoolExecutor()

    def inspect(self, node: Node, **kwargs):
        if self.public_only and node.is_private:
            return
        try :
            print(f'\033[KInspecting [{node}]\r', end='', flush=True, file=sys.stderr)
            inspection = node.get_inspection(self.cid)
        except Exception as e:
            if self.verbose:
                print(f'\033[KFAIL to inspect [{node}] err={e}',
                    flush=True, file=sys.stderr)
            return
        self.process_inspection(inspection, node)

    def report_address(self, node: Node, addr: str, reporter: Node):
        if addr not in self.idToNode:
            nodes = [(node, reporter)]
            self.idToNode[addr] = nodes
        else:
            nodes = self.idToNode[addr]
            for i in range(len(nodes)):
                nr = nodes[i]
                if nr[0] is node:
                    for j in range(1,len(nr)):
                        if nr[j] is reporter:
                            return
                    nodes[i] = nr + (reporter,)
                    return
            nodes.append((node, reporter))

    def request_inspect(self, node):
        ft = self.executor.submit(self.inspect, node, timeout=2.0)
        self.inspectingQueue.append(ft)

    def report_p2p(self, server: str, need_inspect: bool = True, uri: Optional[str] = None) -> Node:
        if server not in self.p2pToNode:
            node = Node.from_p2p(server, uri)
            self.p2pToNode[server] = node
            if need_inspect:
                self.request_inspect(node)
            return node

        node = self.p2pToNode[server]
        return node

    def apply_map(self, m: dict, reporter: Node, category: str):
        for k, v in m.items():
            node = self.report_p2p(k, True)
            if v != '':
                self.report_address(node, v, reporter)

    def apply_list(self, l: list, reporter: Node, category: str):
        for item in l:
            node = self.report_p2p(item['addr'], True)
            self.report_address(node, item['id'], reporter)

    def process_inspection(self, inspection: Inspection, node: Node = None):
        p2p = inspection['module']['network']['p2p']
        p2p_self = p2p['self']


        if node is None:
            node = self.report_p2p(p2p_self['addr'], False)
            node.add_inspection(inspection)
        elif p2p_self['addr'] != node.get_p2p():
            click.secho(f'Used p2p:{node.get_p2p()} broadcasting p2p:{p2p_self["addr"]}', file=sys.stderr,
                        fg='red', bold=True)
        self.report_address(node, p2p_self['id'], node)

        for category in ['uncles', 'children', 'friends', 'nephews', 'orphanages', 'others']:
            if category not in p2p:
                continue
            self.apply_list(p2p[category], node, category)

        for category in ['roots', 'seeds']:
            if category not in p2p:
                continue
            self.apply_map(p2p[category], node, category)

        if 'parent' in p2p:
            parent = p2p['parent']
            if 'id' in parent:
                n = self.report_p2p(parent['addr'], True)
                self.report_address(n, parent['id'], node)

    def process_all(self):
        while len(self.inspectingQueue) > 0:
            item: futures.Future = self.inspectingQueue.pop(0)
            try:
                item.result()
            except:
                futures.as_completed(self.inspectingQueue)
                raise

    def show_inspection(self):
        problems: Dict[str,Problem] = {}
        known_p2ps: List[str] = []
        for id, nodes in self.idToNode.items():
            if len(nodes) > 1:
                problems[id] = Problem('red', 'multiple p2p')
            else:
                for nr in nodes:
                    p2p = nr[0].get_p2p()
                    if p2p in known_p2ps:
                        problems[p2p] = Problem('yellow', 'same p2p')
                        break
                    elif self.public_only and is_private_p2p(p2p):
                        problems[p2p] = Problem('yellow', 'private ip')
                        break
                    else:
                        known_p2ps.append(p2p)

        for id, nodes in self.idToNode.items():
            id_problem = problems.get(id, None)
            for nr in nodes:
                node = nr[0]
                p2p = node.get_p2p()
                problem = id_problem or problems.get(p2p)
                color = problem.color if problem is not None else None
                if node.has_inspection(self.cid):
                    status = click.style("verified",fg='bright_green')
                else:
                    status = click.style(f'{problem[1]} ', fg=problem[0]) \
                        if problem is not None else ''
                    status += click.style(f'{len(nr[1:])} reports', fg='bright_white')
                click.secho(f'{id:<42s} : {p2p:<24s} : {status}', fg=color)
                id = ''

        inspected = 0
        for p2p, node in self.p2pToNode.items():
            if node.has_inspection(self.cid):
                inspected += 1

        print(f'Summary servers:{len(self.p2pToNode)} wallets:{len(self.idToNode)} inspected:{inspected}')

def inspect_url_of(obj: dict, server: str = None, rpc: str = None, channel: str = None, informal: bool = False) -> ParseResult:
    if rpc is None:
        if server is not None:
            rpc = f'http://{server}/api/v3'
        elif CONTEXT_NODE_SEED in obj:
            p2p = obj[CONTEXT_NODE_SEED][0]
            rpc = Node.from_p2p(p2p).get_url('/api/v3')
        elif service.default_net is not None:
            rpc, _ = service.default_net
        else:
            raise Exception('No URL is set for inspect')

    url_obj = urlparse(rpc)
    path: str = url_obj.path
    if channel is None:
        if path.endswith('v3'):
            channel = 'icon_dex'
        else:
            channel = path.split('/')[-1]
    return url_obj._replace(path=f'/admin/chain/{channel}',query="informal=true" if informal else "")

@click.command('inspect')
@click.option('--rpc', type=click.STRING)
@click.option('--channel', type=click.STRING)
@click.option('--server', type=click.STRING)
@click.option('--informal', is_flag=True)
@click.pass_obj
def show_inspection(obj: dict, server: str = None, rpc: str = None, channel: str = None, informal: bool = False):
    '''
    Inspect the channel of the server
    '''
    url = inspect_url_of(obj, server, rpc, channel, informal).geturl()
    try:
        inspection = util.rest_get(url)
    except BaseException as exc:
        raise Exception(f'Inspection failure url={url}') from exc
    util.dump_json(inspection)

@click.command('netinspect')
@click.option('--rpc', type=click.STRING)
@click.option('--channel', type=click.STRING)
@click.option('--server', type=click.STRING)
@click.option('--private', is_flag=True)
@click.pass_obj
def show_netinspection(obj: dict, server: str = None, rpc: str = None, channel: str = None, private: bool = False):
    '''
    Inspect the channel of the all nodes connected with the server
    '''
    url_obj = inspect_url_of(obj, server, rpc, channel)
    uri_obj = url_obj._replace(path="")
    url = url_obj.geturl()
    try:
        inspection = Inspection(util.rest_get(url))
    except BaseException as exc:
        raise Exception(f'fail to get inspection with url={url}') from exc

    info = NetworkInformation(inspection.cid, public_only=(not private))
    node = info.report_p2p(inspection.p2p, False, uri_obj.geturl())
    info.process_inspection(inspection, node)
    info.process_all()
    info.show_inspection()