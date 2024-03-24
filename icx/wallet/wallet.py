#!/usr/bin/env python3

import io
import json
import os
import sys
from typing import Optional, Union

import click
from iconsdk.wallet.wallet import KeyWallet, Wallet
from eth_keyfile import  extract_key_from_keyfile

from .. import util
from icx.config import CONTEXT_CONFIG, Config
from icx.cui import Column, RowPrinter

CONFIG_KEYSTORES='wallets'
CONFIG_BOOKMARK='bookmark'
CONTEXT_KEYSTORE='keystore.name'

def load_wallet_from_dict(src: dict, pw: str) -> Wallet:
    fd = io.BytesIO(bytes(json.dumps(src), 'utf-8'))
    sk = extract_key_from_keyfile(fd, bytes(pw, 'utf-8'))
    return KeyWallet.load(sk)

class MyWallet(Wallet):
    def __init__(self, src: Union[str,dict], password: str = None, name: str = None) -> None:
        self.src = src
        if type(src) is str:
            kstore = json.load(open(self.src, 'rb'))
        elif type(src) is dict:
            kstore = src
        else:
            raise Exception(f'InvalidTypeForKeystore(src={src})')

        if 'address' not in kstore:
            raise Exception("InvalidKeyStore(NoAddress)")
        self.__addr = kstore['address']
        self.__wallet = None
        self.__password = password
        self.__name = name
    
    @property
    def name(self) -> str:
        return self.__name

    def __get_loaded(self) -> Wallet:
        if self.__wallet is None:
            if self.__password is None:
                password = click.prompt("WalletPassword", hide_input=True)
            else:
                password = self.__password
            if type(self.src) is str:
                self.__wallet = KeyWallet.load(self.src, password)
            else:
                self.__wallet = load_wallet_from_dict(self.src, password)
        return self.__wallet
    
    def get_address(self) -> str:
        return self.__addr

    def sign(self, data: bytes) -> bytes:
        return self.__get_loaded().sign(data)

    def public_key(self, compressed: bool = True, hexadecimal: bool = True) -> Union[str, bytes]:
        return self.__get_loaded().public_key(compressed, hexadecimal)

    address = property(get_address)
    loaded = property(__get_loaded)

KEY_STORE_ENV="GOLOOP_RPC_KEY_STORE"
KEY_PASS_ENV="GOLOOP_RPC_KEY_PASSWORD"
cached_wallet = {}
default_wallet = None
def get_instance(ks: str = None, kp: str = None) -> MyWallet:
    global cached_wallet
    global default_wallet
    if ks is None:
        if default_wallet is not None:
            return default_wallet
        else:
            ks = os.getenv(KEY_STORE_ENV)
            kp = os.getenv(KEY_PASS_ENV)
    if ks is None:
        raise Exception(f'KeyStoreIsNotSpecified')

    if ks not in cached_wallet:
        wallet = MyWallet(ks, kp)
        cached_wallet[ks] = wallet
    return cached_wallet[ks]

def handleFlag(obj: dict, name: str):
    global default_wallet
    config = obj[CONTEXT_CONFIG]
    keystores = config.get(CONFIG_KEYSTORES)
    if name not in keystores:
        click.echo(f'Available keystores:{",".join(keystores.keys())}', file=sys.stderr)
        raise Exception(f'Unknown keystore name={name}')
    default_wallet = MyWallet(keystores[name])
    obj[CONTEXT_KEYSTORE] = name

def get_instance_with(obj: dict, ks: Optional[str] = None) -> MyWallet:
    if ks is None:
        return get_instance()

    config = obj[CONTEXT_CONFIG]
    keystores = config.get(CONFIG_KEYSTORES)
    if ks in keystores:
        return MyWallet(keystores[ks])
    return get_instance(ks)

def print_keystores(keystores: dict):
    if len(keystores) == 0:
        click.echo(f'No keystores are registered', file=sys.stderr)
        return
    columns = [
        Column(lambda name, info: name, 10, name='Name'),
        Column(lambda name, info: info['address'], 60, name='Address'),
    ]
    printer = RowPrinter(columns)
    printer.print_separater()
    printer.print_header()
    printer.print_separater()
    for name, value in keystores.items():
        printer.print_data(name, value)
        printer.print_separater()

@click.command()
@click.argument('name', metavar='[<name>]', type=click.STRING, required=False)
@click.argument('file', metavar='[<file>]', type=click.STRING, required=False)
@click.option('--delete', '-d', type=click.BOOL, is_flag=True, default=False)
@click.option('--verify', '-v', type=click.BOOL, is_flag=True, default=False)
@click.option('--rename', '-r', metavar='<new name>', type=click.STRING, default=None)
@click.option('--pubkey', '-p', type=click.BOOL, is_flag=True, default=False)
@click.pass_obj
def main(obj: dict, name: str = None, file: str = None, delete: bool = None, verify: bool = None, rename: str = None, pubkey: bool = None):
    '''
    Manage keystores

    \b
    With no arguments, it shows list of keystores.
    \b
    With a name and file, it imports new keystore.
        --verify : for verifying password before import
    \b
    With a name, it dumps the keystore with no option.
        --delete : to delete the keystore
        --verify : to verify password of the keystore
        --rename <new name> : to change the name of the keystore
        --pubkey : to verify password and show publickey
    '''
    config: Config = obj[CONTEXT_CONFIG]
    keystores: dict = config.get(CONFIG_KEYSTORES)

    if name is None:
        print_keystores(keystores)
        return

    if file is None:
        if not name in keystores:
            click.secho(f'No keystore named [{name}]', color='red', file=sys.stderr)
            return
        if delete:
            del keystores[name]
            config[CONFIG_KEYSTORES] = keystores
            click.echo(f'Keystore [{name}] is deleted')
            return
        elif verify:
            password = click.prompt("WalletPassword", hide_input=True)
            try:
                load_wallet_from_dict(keystores[name], password)
            except:
                click.secho(f'Fail to verify keystore', color='red', file=sys.stderr)
            click.echo(f'Keystore [{name}] is verified')
            return
        elif rename is not None:
            if rename in keystores:
                click.secho(f'There is already existing keystore [{rename}]', color='red', file=sys.stderr)
                return
            ks = keystores[name]
            del keystores[name]
            keystores[rename] = ks
            config[CONFIG_KEYSTORES] = keystores
            click.echo(f'Keystore [{name}] is renamed to [{rename}]')
            return
        elif pubkey:
            password = click.prompt("WalletPassword", hide_input=True)
            try:
                wallet = load_wallet_from_dict(keystores[name], password)
                click.echo(f'0x{wallet.get_public_key()}', file=sys.stdout)
            except:
                click.secho(f'Fail to verify keystore', color='red', file=sys.stderr)
            return
        else:
            json.dump(keystores[name], sys.stdout)
            return

    if verify:
        password = click.prompt("WalletPassword", hide_input=True)
        try:
            KeyWallet.load(file, password)
        except:
            click.secho(f'Fail to verify keystore={file}', color='red', file=sys.stderr)

    with open(file, 'rb') as fd:
        keystore = json.load(fd)
        keystores[name] = keystore
        config[CONFIG_KEYSTORES] = keystores
        click.echo(f'Wallet {name} is set as addr={keystore["address"]}')

@click.command('bookmark')
@click.argument('name', metavar='[<name>]', type=click.STRING, required=False)
@click.argument('addr', metavar='[<address>]', type=util.ADDRESS, required=False)
@click.option('--delete', '-d', type=click.BOOL, is_flag=True, default=False)
@click.pass_obj
def bookmark_main(obj: dict, name: str, addr: str, delete: bool):
    config = obj[CONTEXT_CONFIG]
    keystores = config.get(CONFIG_KEYSTORES)
    bookmark = config.get(CONFIG_BOOKMARK)
    if name is None:
        columns = [
            Column(lambda t, k, v: t.upper(),  2, format='{:2^}',name='Type'),
            Column(lambda t, k, v: k, 20, name='Name'),
            Column(lambda t, k, v: v, 42, name='Address'),
        ]
        printer = RowPrinter(columns)
        printer.print_header()
        for k, v in keystores.items():
            printer.print_data('ks', k, v['address'], underline=True)
            # click.echo(f'{k}={v["address"]}')
        for k, v in bookmark.items():
            printer.print_data('bk', k, v, underline=True)
            # click.echo(f'{k}={v}')
        return

    if delete:
        if name in bookmark:
            del(bookmark, name)
            config[CONFIG_BOOKMARK] = bookmark
        else:
            click.secho(f'No bookmark named {name}', color='red', file=sys.stderr)
            return

    if addr is None:
        click.echo(f'{name}={bookmark[name]}')
        return
    bookmark[name] = addr
    config[CONFIG_BOOKMARK] = bookmark

def ensure_address(addr: str) -> str:
    ctx = click.get_current_context()
    config = ctx.obj[CONTEXT_CONFIG]
    bookmark = config.get(CONFIG_BOOKMARK)
    if addr in bookmark:
        return bookmark[addr]
    keystore = config.get(CONFIG_KEYSTORES)
    if addr in keystore:
        return keystore[addr]['address']
    return util.ensure_address(addr)

class AddressType(click.ParamType):
    name = "address"
    def convert(self, value, param, ctx) -> str:
        if value is None:
            return None
        return ensure_address(value)

ADDRESS = AddressType()
