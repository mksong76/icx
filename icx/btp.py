import base64
import io
import sys
import click

from iconsdk.monitor import BTPMonitorSpec

from .btpdata import BTPHeader

from . import service, util

@click.group('btp')
def main():
    pass

@main.command('header', help='Show BTP Header')
@click.argument('height', metavar='<height>', type=util.INT)
@click.argument('nid', metavar='<nid>', type=util.INT)
@click.option('--output', '-o', type=click.File('wb'), default='-',
               help='Output file (default:stdout)')
@click.option('--binary', '-b', is_flag=True, help='Binary output')
@click.option('--text', '-t', is_flag=True, help='Text output')
def get_header(height: int, nid: int, output: io.RawIOBase, binary: bool, text: bool):
    svc = service.get_instance()
    res = svc.get_btp_header(height, nid)
    if text:
        hdr: BTPHeader = BTPHeader.from_binary(res)
        util.dump_json(hdr.to_json(), fp=io.TextIOWrapper(output))
    elif binary:
        bin = base64.decodestring(res.encode())
        output.write(bin)
    else:
        output.write(res.encode())

@main.command('type', help='Network type information')
@click.argument('tid', type=util.INT, metavar='<network type id>', required=False)
@click.option('--height', '-h', type=util.INT)
def get_network_info(tid: int = None, height: int = None):
    svc = service.get_instance()
    if tid is None:
        si = svc.get_btp_source_information()
        util.dump_json(si)
    else:
        ti = svc.get_btp_network_type_info(tid, height)
        util.dump_json(ti)

@main.command('net', help='Network information')
@click.argument('nid', metavar='<network id>', type=util.INT, required=False)
@click.option('--height', '-h', type=util.INT)
@click.option('--all', '-a', is_flag=True)
def get_network_info(nid: int = None, height: int = None, all: bool = False):
    svc = service.get_instance()
    if nid is None:
        si = svc.get_btp_source_information()
        tids = si['networkTypeIDs']
        for tid in tids:
            ti = svc.get_btp_network_type_info(int(tid, 0), height)
            if all:
                for nid in ti['openNetworkIDs']:
                    ni = svc.get_btp_network_info(int(nid, 0), height)
                    util.dump_json(ni)
            else:
                util.dump_json(ti)
    else:
        ni = svc.get_btp_network_info(nid, height)
        util.dump_json(ni)

@main.command('proof', help='BTP Proof')
@click.argument('nid', metavar='<network id>', type=util.INT, required=True)
@click.argument('height', metavar='<block height>', type=util.INT, required=True)
def get_proof(nid: int, height: int):
    svc = service.get_instance()
    proof = svc.get_btp_proof(height, nid)
    util.dump_json(proof)

TC_CLEAR = '\033[K'

@main.command('monitor', help='Network header monitor')
@click.argument('nid', metavar='<network id>', type=util.INT)
@click.option('--height', '-h', type=util.INT)
@click.option('--progress', '-p', type=util.INT, default=100)
@click.option('--text', '-t', is_flag=True)
def monitor_network(nid: int = None, height: int = None, progress: int=100, text: bool = False):
    svc = service.get_instance()

    if height is None:
        blk = svc.get_block('latest')
        height = blk['height']+1

    print(f'Monitor BTP Headers nid=0x{nid:x} from={height}', file=sys.stderr)
    monitor = svc.monitor(BTPMonitorSpec(height, nid, progress_interval=progress))
    while True:
        obj = monitor.read()

        if 'progress' in obj:
            print(f'{TC_CLEAR}> Block height={int(obj["progress"],0)}\r',
                  end='', file=sys.stderr, flush=True)
            continue

        print(f'{TC_CLEAR}', end='', file=sys.stderr, flush=True)
        if 'code' in obj:
            util.dump_json(obj, flush=True)
            break
        else:
            if text:
                hdr = BTPHeader.from_binary(obj['header'])
                util.dump_json(hdr.to_json())
            else:
                util.dump_json(obj, flush=True)