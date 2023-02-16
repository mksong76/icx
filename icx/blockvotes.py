import base64
from hashlib import sha3_256
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


@click.command('vote')
@click.argument('height', type=util.HEXINT)
def check_votes(height: int):
    '''
    Check votes of the block and show vote information
    '''
    svc = service.get_instance()

    hdr_b64 = svc.get_block_header_by_height(height)
    hdr_bs = base64.b64decode(hdr_b64)
    hdr = rlp.decode_bytes(hdr_bs)
    hdr_hash = sha3_256(hdr_bs).digest()

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

    validators_hash = phdr[BLOCK.NEXTVALIDATOR_HASH]
    validators_b64 = svc.get_data_by_hash(f'0x{validators_hash.hex()}')
    validators_bs = base64.b64decode(validators_b64)
    validators = rlp.decode_bytes(validators_bs)
    proposer = f'hx{hdr[BLOCK.PROPOSER][1:].hex()}'
    for v in validators:
        addr = f'hx{v[1:].hex()}'
        print(f'{addr} {"voted" if addr in voted else "unvoted"}{" proposer" if addr == proposer else ""}')