import copy
import base64
from hashlib import sha3_256
from typing import List, Tuple

import click
import coincurve
from iconsdk.libs.serializer import serialize
from iconsdk.wallet.wallet import public_key_to_address

from . import service, util

# Serialize transaction object with other information
# (serialized_bytes, tx_hash, signature)
ADDED_TX_KEYS = [ 'blockHash', 'blockHeight', 'txIndex' ]
def serialize_tx_obj(obj: dict) -> Tuple[bytes,bytes,bytes]:
    o = copy.deepcopy(obj)

    version = int(o['version'], 0) if 'version' in o else 2

    if version == 2 and 'method' in o:
        del o['method']

    tx_hash_key = 'tx_hash' if version == 2 else 'txHash'
    tx_hash = bytes.fromhex(o[tx_hash_key].lstrip('0x'))
    del o[tx_hash_key]

    signature = base64.decodestring(bytes(o['signature'], encoding='utf-8'))
    del o['signature']

    for key in ADDED_TX_KEYS:
        if key in o:
            del o[key]

    return serialize(o), tx_hash, signature


@click.command()
@click.argument('ids', nargs=-1)
@click.option('--pubkey', is_flag=True)
def verify_tx(ids: List[str], pubkey: bool = False):
    '''Verify the transaction information'''
    svc = service.get_instance()
    for id in ids:
        response = svc.get_transaction(id, full_response=True)

        tx_obj = response['result']
        message, tx_hash, signature = serialize_tx_obj(tx_obj)
        assert tx_hash == sha3_256(message).digest()

        pk = coincurve.PublicKey.from_signature_and_message(
            signature=signature, message=tx_hash, hasher=None).format(True)
        addr = public_key_to_address(pk)
        assert addr == tx_obj['from']

        if pubkey:
            click.echo(f'0x{pk.hex()}')
        else:
            click.echo(f'{id} is OK')