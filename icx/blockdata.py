#!/usr/bin/env python3

import base64
from hashlib import sha3_256
from typing import Optional, List
from . import rlp, service
import coincurve

class Binary(bytes):
    def __new__(self, *args, **kwargs) -> 'Binary':
        return bytes.__new__(Binary, *args, **kwargs)

    def __str__(self) -> str:
        return f'0x{self.hex()}'

    def to_int(self) -> 'BInteger':
        return BInteger(self)

    def to_address(self) -> 'BAddress':
        return BAddress(self)

    def to_str(self) -> 'BString':
        return BString(self)
    
    def to_json(self) -> str:
        return str(self)

    def rlp_decode(self) -> any:
        return rlp.decode_bytes(self)

    def sha3_256(self) -> 'Binary':
        return Binary(sha3_256(self).digest())

    @staticmethod
    def from_any(data: any) -> Optional['Binary']:
        if data is None:
            return None
        if isinstance(data, str):
            return Binary(base64.b64decode(data))
        else:
            return Binary(data)
    
    @staticmethod
    def to_json(data: Optional['Binary']) -> Optional[str]:
        if data is None:
            return None
        else:
            return str(data)
    
    @staticmethod
    def to_int(bs: bytes) -> int:
        return int.from_bytes(bs, byteorder='big', signed=True)

    @staticmethod
    def to_address(bs: bytes) -> str:
        if len(bs) != 21:
            raise Exception(f'invalid bytes for address (bytes=0x{bs.hex()})')

        prefix = bs[0]
        if prefix not in [0, 1]:
            raise Exception(f'invalid byte prefix={prefix} for address')
        return ('cx' if prefix else 'hx') + bs[1:].hex()

    @staticmethod
    def as_string(bs: bytes) -> str:
        return bs.decode()


def rlpitem(offset: int, convert = lambda x: x):
    def decorator(func):
        def callee_func(self):
            return convert(self[offset])
        return callee_func
    return decorator


class RLPList(tuple):
    def __new__(cls, data: any):
        if not isinstance(data, list) and not isinstance(data, tuple):
            raise Exception(f'NotAList')
        return super().__new__(cls, data)
    
    def to_bytes(self) -> bytes:
        return rlp.encode(self)

    def to_binary(self) -> Binary:
        return Binary(rlp.encode(self))

    @classmethod
    def from_binary(clz, data: any) -> 'RLPList':
        binary = Binary.from_any(data)
        return clz(binary.rlp_decode())

class BAddress(str):
    def __new__(cls, v, s: str = None):
        binary = Binary.from_any(v)
        s = Binary.to_address(binary) if s is None else s
        self = super().__new__(cls, s)
        self.__binary = binary
        return self

    def to_binary(self) -> Binary:
        return self.__binary

    @staticmethod
    def from_publickey(pk: coincurve.PublicKey) -> 'BAddress':
        return BAddress(b'\x00'+sha3_256(pk.format(compressed=False)[1:]).digest()[-20:])

    @staticmethod
    def from_str(s: str) -> 'BAddress':
        is_contract = ['hx', 'cx'].index(s[0:2])
        if is_contract < 0:
            raise Exception('invalid address prefix')
        id_part = bytes.fromhex(s[2:])
        if len(id_part) != 20:
            raise Exception('invalid address length')
        binary = bytes([is_contract])+id_part
        return BAddress(binary, s.lower())


class BString(str):
    def __new__(cls, v: any):
        binary = Binary.from_any(v)
        self = super().__new__(cls, Binary.as_string(binary))
        self.__binary = binary
        return self

    def to_binary(self) -> Binary:
        return self.__binary

    def to_json(self) -> str:
        return str(self)


class BInteger(int):
    def __new__(cls, v: any):
        binary = Binary.from_any(v)
        self = super().__new__(cls, Binary.to_int(binary))
        self.__binary = binary
        return self
    
    def to_binary(self) -> bytes:
        return self.__binary

    def to_json(self) -> str:
        return f'{self:#x}'

class Block(RLPList):
    def hash(self) -> Binary:
        return self.to_binary().sha3_256()

    @rlpitem(0, BInteger)
    def version(self) -> BInteger:
        pass

    @rlpitem(1, BInteger)
    def height(self) -> BInteger:
        pass

    @rlpitem(3, BAddress)
    def proposer(self) -> BAddress:
        pass

    @rlpitem(4, Binary)
    def previous_id(self) -> Binary:
        pass

    @rlpitem(5, Binary)
    def votes_hash(self) -> Binary:
        pass

    def votes(self, svc: service.Service) -> 'BlockVotes':
        data = svc.get_data_by_hash(str(self.votes_hash()))
        return BlockVotes(data)

    @rlpitem(6, Binary)
    def next_validators_hash(self) -> Binary:
        pass

    def next_validators(self, svc: service.Service) -> 'Validators':
        data = svc.get_data_by_hash(str(self.next_validators_hash()))
        return Validators.from_binary(data)


class Validators(RLPList):
    def at(self, idx:int) -> BAddress:
        return Binary(self[idx]).to_address()


class BlockVotes(RLPList):
    @rlpitem(0, BInteger)
    def round(self) -> BInteger:
        pass

    @rlpitem(1)
    def partset_id(self):
        pass

    def check_voted(self, blk: Block) -> List[str]:
        voted = []
        blk_hash = blk.hash()
        for v in self[2]:
            sig = v[1]
            vote_msg = rlp.encode([
                blk.height().to_binary(),
                self.round().to_binary(),
                b'\x01',
                blk_hash,
                self.partset_id(),
                v[0],
            ])
            vote_hash = Binary(vote_msg).sha3_256()
            pk = coincurve.PublicKey.from_signature_and_message(sig, vote_hash, hasher=None)
            addr = BAddress.from_publickey(pk)
            voted.append(addr)
        return voted

if __name__ == '__main__':
    svc = service.get_instance()
    blk = svc.get_block('latest')
    height = blk['height']
    hdr = Block.from_binary(svc.get_block_header_by_height(height))
    validators = hdr.next_validators(svc)
    votes = BlockVotes.from_binary(svc.get_votes_by_height(height))
    print(votes.check_voted(hdr))
