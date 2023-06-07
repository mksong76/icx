#!/usr/bin/env python3

import io
import json
from typing import Tuple, List, Union

import click
from . import util

RLPValue = Union[bytes,List['RLPValue'],None]

def decode_list_bytes(bs: bytes) -> List[RLPValue]:
    items = []
    while len(bs)>0:
        obj, bs = decode_one_bytes(bs)
        items.append(obj)
    return items

def decode_one_bytes(bs: bytes) -> Tuple[RLPValue, bytes]:
    ch, bs = bs[0], bs[1:]
    if ch < 0x80:
        return bytes([ch]), bs
    elif ch < 0xB8:
        size = ch-0x80
        return bs[:size], bs[size:]
    elif ch < 0xC0:
        tag_size = ch - 0xB7
        tag, bs = bs[:tag_size], bs[tag_size:]
        size = int.from_bytes(tag, signed=False, byteorder='big')
        return bs[:size], bs[size:]
    elif ch < 0xF8:
        size = ch - 0xC0
        list_bytes, bs = bs[:size], bs[size:]
        return decode_list_bytes(list_bytes), bs
    else:
        tag_size = ch - 0xF7
        tag, bs = bs[:tag_size], bs[tag_size:]
        size = int.from_bytes(tag, signed=False, byteorder='big')
        if size == 0:
            return None, bs
        list_bytes, bs = bs[:size], bs[size:]
        return decode_list_bytes(list_bytes), bs

class EndOfFile(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

class NotEnoughData(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

def decode_list(fd: io.RawIOBase) -> List[RLPValue]:
    items = []
    while True:
        try:
            items.append(decode(fd))
        except EndOfFile as eof:
            break
    return items

def read_full(fd: io.RawIOBase, n: int) -> bytes:
    bs = fd.read(n)
    if len(bs) < n:
        raise NotEnoughData(f'NotEnoughData(size={n},read={len(bs)})')
    return bs

def decode(fd: io.RawIOBase) -> RLPValue:
    bs = fd.read(1)
    if len(bs) < 1:
        raise EndOfFile('FailToReadHeader')

    ch = bs[0]
    if ch < 0x80:
        return bytes([ch])
    elif ch < 0xB8:
        size = ch-0x80
        return read_full(fd, size)
    elif ch < 0xC0:
        tag_size = ch - 0xB7
        tag = read_full(fd, tag_size)
        size = int.from_bytes(tag, signed=False, byteorder='big')
        return read_full(fd, size)
    elif ch < 0xF8:
        size = ch - 0xC0
        bs = read_full(fd, size)
        cfd = io.BytesIO(bs)
        return decode_list(cfd)
    else:
        tag_size = ch - 0xF7
        tag = read_full(fd, tag_size)
        size = int.from_bytes(tag, signed=False, byteorder='big')
        if size == 0:
            return None
        bs = read_full(fd, size)
        cfd = io.BytesIO(bs)
        return decode_list(cfd)

def decode_bytes(bs: bytes) -> RLPValue:
    obj, bs = decode_one_bytes(bs)
    if len(bs) > 0:
        raise Exception(f'RemainingBytes(size={len(bs)}')
    return obj


def encode_bytes(bs: bytes) -> bytes:
    blen = len(bs)
    if blen == 1 and bs[0] < 0x80:
        return bs
    elif blen <= 55:
        head = bytes([0x80+blen])
        return head+bs
    else:
        tag_size = (blen.bit_length()+7)//8
        head = bytes([0x80+55+tag_size])
        tag = blen.to_bytes(tag_size, byteorder='big', signed=False,)
        return head+tag+bs

def encode(obj: RLPValue) -> bytes:
    if obj is None:
        return b'\xf8\x00'
    elif isinstance(obj, bytes):
        return encode_bytes(obj)
    elif isinstance(obj, str):
        if obj.startswith('0x'):
            return encode_bytes(bytes.fromhex(obj[2:]))
        else:
            raise Exception(f'UnknownString({obj})')
    elif isinstance(obj, list) or isinstance(obj, tuple):
        bs = b''
        for item in obj:
            bs += encode(item)
        blen = len(bs)
        if blen <= 55:
            head = bytes([0xC0+blen])
            return head+bs
        else:
            tag_size = (blen.bit_length()+7)//8
            head = bytes([0xC0+55+tag_size])
            tag = blen.to_bytes(tag_size, byteorder='big', signed=False,)
            return head+tag+bs
    else:
        raise Exception(f'UnknownType({obj})')


@click.command(help='Decode/encode RLP bytes to/from JSON')
@click.option('--input', '-i', type=click.File('rb'), default='-')
@click.option('--output', '-o', type=click.File('wb'), default='-')
@click.option('--rlp', '-r', is_flag=True)
def convert(input: io.RawIOBase, output: io.RawIOBase, rlp: bool):
    if rlp:
        output.write(encode(json.load(io.TextIOWrapper(input))))
    else:
        util.dump_json(decode(input),fp=io.TextIOWrapper(output))