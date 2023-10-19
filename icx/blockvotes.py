import base64
from hashlib import sha3_256
import sys
from typing import Optional
import click
import coincurve
from . import service
from . import rlp, util


class BLOCK:
    VERSION = 0
    HEIGHT = 1
    TIMESTAMP = 2
    PROPOSER = 3
    PREVIOUS_ID = 4
    VOTES_HASH = 5
    NEXTVALIDATOR_HASH = 6
    PATCHTX_HASH = 7
    NORMALTX_HASH = 8
    LOGS_BLOOM = 9
    RESULT = 10

class VOTES:
    ROUND = 0
    PARTSET_ID = 1
    ITEMS = 2

class VOTEITEM:
    TIMESTAMP = 0
    SIGNATURE = 1

def get_next_validators(svc: service.Service = None, /, header: list = None, height: int = None):
    if svc is None:
        svc = service.get_instance()

    if header is None:
        if height is None:
            last = svc.get_block('latest')
            height = last['height']
        hdr_b64 = svc.get_block_header_by_height(height)
        hdr_bs = base64.b64decode(hdr_b64)
        header = rlp.decode_bytes(hdr_bs)

    validators_hash = header[BLOCK.NEXTVALIDATOR_HASH]
    validators_b64 = svc.get_data_by_hash(f'0x{validators_hash.hex()}')
    validators_bs = base64.b64decode(validators_b64)
    validators = rlp.decode_bytes(validators_bs)
    return list(map(lambda v: f'hx{v[1:].hex()}', validators)), height

@click.command('validators')
@click.option('--height', '-h', type=util.INT)
def show_validators(height: int = None):
    '''
    Show next validators of the specified block
    '''
    validators, height = get_next_validators(height = height)
    click.secho(f'Next validators of the block height={height}', fg='bright_black', file=sys.stderr)
    for v in validators:
        print(v)

@click.command('votes')
@click.argument('height', type=util.INT, required=False)
@click.option('--pubkey', is_flag=True)
def check_votes(height: int, pubkey: bool):
    '''
    Check votes of the block and show vote information
    '''
    svc = service.get_instance()

    if height is None:
        blk = svc.get_block('latest')
        height = blk['height']
    click.secho(f'Check votes for height={height}', fg='bright_black', file=sys.stderr)

    hdr_b64 = svc.get_block_header_by_height(height)
    hdr_bs = base64.b64decode(hdr_b64)
    hdr = rlp.decode_bytes(hdr_bs)
    hdr_hash = sha3_256(hdr_bs).digest()

    try:
        nhdr_bs = base64.b64decode(svc.get_block_header_by_height(height+1))
        nhdr = rlp.decode_bytes(nhdr_bs)
        vhash: bytes = nhdr[BLOCK.VOTES_HASH]
        votes_bs = base64.b64decode(svc.get_data_by_hash(f'0x{vhash.hex()}'))
        votes = rlp.decode_bytes(votes_bs)
    except BaseException as exc:
        votes_b64 = svc.get_votes_by_height(height)
        votes_bs = base64.b64decode(votes_b64)
        votes = rlp.decode_bytes(votes_bs)

    phdr_b64 = svc.get_block_header_by_height(height-1)
    phdr_bs = base64.b64decode(phdr_b64)
    phdr = rlp.decode_bytes(phdr_bs)

    voted = []
    for voteitem in votes[VOTES.ITEMS]:
        sig = voteitem[VOTEITEM.SIGNATURE]
        vote_msg = rlp.encode([
            hdr[BLOCK.HEIGHT],
            votes[VOTES.ROUND],
            b'\x01',
            hdr_hash,
            votes[VOTES.PARTSET_ID],
            voteitem[VOTEITEM.TIMESTAMP]
        ])
        vote_hash = sha3_256(vote_msg).digest()
        pk = coincurve.PublicKey.from_signature_and_message(sig, vote_hash, hasher=None)
        addr = f'hx{sha3_256(pk.format(compressed=False)[1:]).digest()[-20:].hex()}'
        voted.append(addr)
        if pubkey:
            print(f'{addr} {pk.format().hex()}')

    if pubkey:
        return

    validators, _ = get_next_validators(svc, header=phdr)
    proposer = f'hx{hdr[BLOCK.PROPOSER][1:].hex()}'
    for addr in validators:
        print(f'{addr} {"voted" if addr in voted else "unvoted"}{" proposer" if addr == proposer else ""}')